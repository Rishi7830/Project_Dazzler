import serial
import time
import threading
import random 

class SimpleDMX:
    def __init__(self, port: str, num_channels: int = 512, strobe_interval: float = 0.1): # Adjusted default strobe_interval
        self.port = port
        self.num_channels = num_channels
        self.data = [0] * num_channels # Current DMX channel values
        self.running = False
        self.strobe_on = False
        self.strobe_interval = strobe_interval
        self.color_to_strobe = (0, 0, 0, 0) # The color to use when strobing
        self.thread = None 
        self.scene_edit_colors = [] # New: list to hold colors for scene_edit
        self.scene_edit_hue_speed = 0 # New: hue speed for scene_edit
        self.scene_edit_mode = False # New: flag to control the cycling

        try:
            self.ser = serial.Serial(
                port,
                baudrate=250000,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_TWO,
            )
            print(f"Serial port {self.port} opened successfully.")
        except serial.SerialException as e:
            print(f"Error: Could not open serial port {self.port}.")
            print(e)
            self.ser = None 

    def set_channel(self, ch: int, value: int):
        """Sets a single DMX channel value."""
        if self.ser and 1 <= ch <= self.num_channels:
            self.data[ch - 1] = max(0, min(255, value))
        elif not self.ser:
            print("Serial port not available. Cannot set channel.")

    def clear_color_channels(self):
        """Clears the first 4 channels (assuming RGBW)."""
        if self.ser:
            for ch in range(1, 5):
                self.set_channel(ch, 0)

    def set_channels_from_tuple(self, color_tuple):
        """Sets the first 4 channels (RGBW) from a tuple."""
        if self.ser and len(color_tuple) >= 4:
            r, g, b, w = color_tuple[:4] # Take first 4 values
            self.set_channel(1, r)
            self.set_channel(2, g)
            self.set_channel(3, b)
            self.set_channel(4, w)
        elif not self.ser:
            print("Serial port not available. Cannot set channels from tuple.")

    def update_lighting(self, color_tuple, hue_speed):
        """
        Updates the DMX state based on the color and speed from audio analysis.
        """
        if not self.ser:
            return 

        strobe_threshold = 0.2 
        if hue_speed > strobe_threshold:
            self.strobe_on = True
            self.strobe_interval = max(0.05, 1.0 / (hue_speed * 10)) 
            self.color_to_strobe = color_tuple
            self.set_channels_from_tuple(self.color_to_strobe) 
        else:
            self.strobe_on = False
            self.set_channels_from_tuple(color_tuple) 
            
        self.send_frame() 

    # --- New Scene Functions ---
    def high_one(self):
        """High energy scene with fast strobing and color changes."""
        self.update_lighting(color_tuple=(255, 0, 0, 0), hue_speed=0.9)

    def high_two(self):
        """Another high energy scene with very fast strobing and white light."""
        self.update_lighting(color_tuple=(255, 255, 255, 255), hue_speed=1.5)
    
    def medium(self):
        """Medium energy scene with slow color fades and a gentle pulse."""
        color_rgbw = (0, 0, 255, 0) 
        self.update_lighting(color_rgbw, hue_speed=0.1) 
        
    def low_one(self):
        """Low energy scene with a slow, static color change."""
        self.update_lighting(color_tuple=(255, 255, 0, 50), hue_speed=0.05)
    
    def low_two(self):
        """A different low energy scene with a slow, gentle pulse."""
        self.update_lighting(color_tuple=(0, 255, 255, 0), hue_speed=0.03)

    # --- New Scene Edit Function ---
    def scene_edit(self, colors: list, hue_speed: float):
        """
        Cycles through a user-provided list of colors.
        Args:
            colors (list): A list of RGBW tuples, e.g., [(255, 0, 0, 0), (0, 255, 0, 0)].
            hue_speed (float): Controls the speed of color changes. A high value triggers strobe.
        """
        if not self.ser:
            print("Serial port not available. Cannot run scene_edit.")
            return

        self.scene_edit_colors = colors
        self.scene_edit_hue_speed = hue_speed
        self.scene_edit_mode = True # Activate the scene_edit mode

        # The actual cycling logic will now be handled in the broadcast_loop
        # to ensure it's on a consistent thread.
        print(f"Starting scene_edit with {len(colors)} colors and hue_speed={hue_speed}")

    def stop_scene_edit(self):
        """Stops the scene_edit function from cycling colors."""
        self.scene_edit_mode = False
        print("Stopping scene_edit.")

    # --- End New Scene Edit Function ---

    def send_frame(self):
        """Sends the current DMX data frame."""
        if not self.ser:
            return

        try:
            self.ser.baudrate = 57600  # Baudrate for break
            self.ser.write(b'\x00')  # Break signal
            self.ser.flush()
            time.sleep(0.001) 
            self.ser.baudrate = 250000 
            
            frame = bytes([0]) + bytes(self.data) 
            self.ser.write(frame)
            self.ser.flush()
        except serial.SerialException as e:
            print(f"Error sending DMX frame: {e}")

    def broadcast_loop(self):
        """The main loop that continuously sends DMX frames."""
        print("DMX broadcast thread started.")
        color_index = 0
        while self.running:
            if self.scene_edit_mode:
                if self.scene_edit_colors:
                    current_color = self.scene_edit_colors[color_index]
                    self.update_lighting(current_color, self.scene_edit_hue_speed)
                    color_index = (color_index + 1) % len(self.scene_edit_colors)
                
                # The interval for the scene_edit cycle is based on hue_speed
                if self.scene_edit_hue_speed > 0.2:
                    # If strobing, the update_lighting call already handles the speed,
                    # so we just need a small delay before the next color change
                    time.sleep(1.0 / self.scene_edit_hue_speed) 
                else:
                    time.sleep(0.5) # A default delay for slow color changes
            elif self.strobe_on:
                self.set_channels_from_tuple(self.color_to_strobe)
                self.send_frame()
                time.sleep(self.strobe_interval)
                self.clear_color_channels() 
                self.send_frame()
                time.sleep(self.strobe_interval)
            else:
                self.send_frame()
                time.sleep(0.03) 
        print("DMX broadcast thread stopped.")

    def start_broadcast(self):
        """Starts the DMX broadcast thread."""
        if not self.ser:
            print("Cannot start broadcast: Serial port not available.")
            return
            
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self.broadcast_loop, daemon=True) 
            self.thread.start()

    def stop_broadcast(self):
        """Stops the DMX broadcast thread."""
        if self.running and self.thread:
            self.running = False
            self.thread.join() 

    def close(self):
        """Stops broadcast and closes the serial port."""
        self.stop_broadcast()
        if self.ser and self.ser.is_open:
            self.clear_color_channels()
            self.send_frame() 
            time.sleep(0.1) 
            self.ser.close()
            print(f"Serial port {self.port} closed.")

if __name__ == "__main__":
    # Example Usage for testing:
    SERIAL_PORT = "COM14" 
    
    dmx = SimpleDMX(port=SERIAL_PORT, num_channels=8, strobe_interval=0.5)

    if not dmx.ser:
        print("Exiting test script: Could not initialize DMX controller.")
    else:
        dmx.start_broadcast()

        try:
            print("\n--- DMX Test Mode ---")
            print("Enter commands like: 'high_one', 'scene_edit', 'stop_edit', 'exit'")
            
            scenes_map = {
                "high_one": dmx.high_one,
                "high_two": dmx.high_two,
                "medium": dmx.medium,
                "low_one": dmx.low_one,
                "low_two": dmx.low_two,
                "off": dmx.clear_color_channels,
                "stop_edit": dmx.stop_scene_edit, # New command to stop the cycling
            }

            while True:
                user_input = input("Command: ").strip().lower()
                if user_input == "exit":
                    break
                
                if user_input == "scene_edit":
                    colors = [(255, 0, 0, 0), (0, 255, 0, 0), (0, 0, 255, 0)]
                    hue_speed = float(input("Enter a hue speed for cycling (e.g., 0.1 for slow, 0.8 for fast/strobe): "))
                    dmx.scene_edit(colors, hue_speed)
                    continue

                if user_input in scenes_map:
                    print(f"Activating scene: {user_input}")
                    dmx.stop_scene_edit() # Stop any cycling before starting a new scene
                    scenes_map[user_input]()
                    time.sleep(10)
                    dmx.strobe_on = False
                    dmx.clear_color_channels()
                else:
                    print("Invalid scene. Available: high_one, high_two, medium, low_one, low_two, off, scene_edit, stop_edit")

        except KeyboardInterrupt:
            print("\nExiting DMX test...")
        finally:
            dmx.close()
