import serial
import time
import threading

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

        try:
            # It's good practice to open the serial port *only* when needed or when starting broadcast
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
            self.ser = None # Set to None if port fails to open

    def set_channel(self, ch: int, value: int):
        """Sets a single DMX channel value."""
        if self.ser and 1 <= ch <= self.num_channels:
            self.data[ch - 1] = max(0, min(255, value))
        elif not self.ser:
            print("Serial port not available. Cannot set channel.")

    def clear_color_channels(self):
        """Clears the first 4 channels (assuming RGBW)."""
        if self.ser:
            for ch in range(4, 7):
                self.set_channel(ch, 0)

    def set_channels_from_tuple(self, color_tuple):
        """Sets the first 4 channels (RGBW) from a tuple."""
        if self.ser and len(color_tuple) >= 4:
            r, g, b, w = color_tuple[:4] # Take first 4 values
            self.set_channel(4, r)
            self.set_channel(5, g)
            self.set_channel(6, b)
            self.set_channel(7, w)
        elif not self.ser:
            print("Serial port not available. Cannot set channels from tuple.")

    def update_lighting(self, color_tuple, hue_speed):
        """
        **THIS IS THE NEW METHOD you'll call from main.py**
        Updates the DMX state based on the color and speed from audio analysis.
        
        Args:
            color_tuple (tuple): An RGB(W) tuple like (r, g, b, w).
            hue_speed (float): A value indicating the desired speed/frequency.
                               We'll use this to determine if it's a strobe.
        """
        if not self.ser:
            # print("Cannot update lighting: Serial port not available.")
            return # Silently fail if serial port isn't open, main.py will handle errors

        # Logic to decide between static color and strobe
        # You can adjust the threshold (e.g., 0.2) for when to activate strobe
        strobe_threshold = 0.2 
        if hue_speed > strobe_threshold:
            self.strobe_on = True
            # Map hue_speed to an interval. Higher speed = shorter interval.
            # This mapping is an example; you might need to tune it.
            self.strobe_interval = max(0.05, 1.0 / (hue_speed * 10)) 
            self.color_to_strobe = color_tuple
            # When strobing, we set the color to be used, but the broadcast loop handles the on/off
            # For immediate effect, we can set the channels here too, but the loop will override it.
            # If you want the strobe to start *immediately*, you might want to send a frame here.
            # However, the broadcast loop's timing is more consistent for continuous strobing.
            self.set_channels_from_tuple(self.color_to_strobe) # Set the color to strobe
        else:
            self.strobe_on = False
            self.set_channels_from_tuple(color_tuple) # Set static color
            
        # Optional: Immediately send the update if not strobing, or to ensure the strobe color is set.
        # This can help reduce perceived latency.
        self.send_frame() 

    def send_frame(self):
        """Sends the current DMX data frame."""
        if not self.ser:
            return

        # DMX protocol requires a break and MAB (Mark After Break)
        # Switch baudrate for break, then back for data
        try:
            self.ser.baudrate = 57600  # Baudrate for break
            self.ser.write(b'\x00')  # Break signal
            self.ser.flush()
            time.sleep(0.001) # Minimum break time
            self.ser.baudrate = 250000 # Baudrate for data
            
            # DMX packet starts with a START CODE (0x00 for DMX512)
            frame = bytes([0]) + bytes(self.data) 
            self.ser.write(frame)
            self.ser.flush()
        except serial.SerialException as e:
            print(f"Error sending DMX frame: {e}")
            # Handle potential disconnection or errors here

    def broadcast_loop(self):
        """The main loop that continuously sends DMX frames."""
        print("DMX broadcast thread started.")
        while self.running:
            if self.strobe_on:
                # Send the 'on' state of the strobe
                self.set_channels_from_tuple(self.color_to_strobe)
                self.send_frame()
                time.sleep(self.strobe_interval)

                # Send the 'off' state of the strobe (all channels to 0)
                # IMPORTANT: Some DMX controllers might expect specific "off" values
                # or might interpret a break signal differently. This is a common approach.
                self.clear_color_channels() 
                self.send_frame()
                time.sleep(self.strobe_interval)
            else:
                # Not strobing, just send the current static color frame
                # The 'data' array is already set by update_lighting()
                self.send_frame()
                time.sleep(0.03) # Standard DMX refresh rate is ~30-40 Hz
        print("DMX broadcast thread stopped.")

    def start_broadcast(self):
        """Starts the DMX broadcast thread."""
        if not self.ser:
            print("Cannot start broadcast: Serial port not available.")
            return
            
        if not self.running:
            self.running = True
            # Use daemon=True so the thread exits when the main program exits
            self.thread = threading.Thread(target=self.broadcast_loop, daemon=True) 
            self.thread.start()

    def stop_broadcast(self):
        """Stops the DMX broadcast thread."""
        if self.running and self.thread:
            self.running = False
            self.thread.join() # Wait for the thread to finish

    def close(self):
        """Stops broadcast and closes the serial port."""
        self.stop_broadcast()
        if self.ser and self.ser.is_open:
            # Optionally send a clear frame before closing
            self.clear_color_channels()
            self.send_frame() 
            time.sleep(0.1) # Give it a moment to send
            self.ser.close()
            print(f"Serial port {self.port} closed.")

if __name__ == "__main__":
    # This block is for testing pyserial.py on its own.
    # When used with main.py, this part is not executed.
    
    # Example Usage for testing:
    # Replace with your actual serial port
    # SERIAL_PORT = "COM14" # Example for Windows
    SERIAL_PORT = "/dev/ttyUSB0" # macOS
    
    dmx = SimpleDMX(port=SERIAL_PORT, num_channels=8, strobe_interval=0.5)

    if not dmx.ser:
        print("Exiting test script: Could not initialize DMX controller.")
    else:
        dmx.start_broadcast()

        try:
            print("\n--- DMX Test Mode ---")
            print("Enter commands like: 'red', 'blue s', 'green 5', 'yellow s 0.2 3'")
            print("Format: <color> [s] [interval] [duration]")
            print(" 's' after color means strobe.")
            print(" Type 'exit' to quit.")
            
            colors_map = { # Basic color mapping for tests
                "red": (255, 0, 0, 0),
                "green": (0, 255, 0, 0),
                "blue": (0, 0, 255, 0),
                "white": (255, 255, 255, 255),
                "yellow": (255, 255, 0, 0),
                "cyan": (0, 255, 255, 0),
                "magenta": (255, 0, 255, 0),
                "off": (0, 0, 0, 0)
            }

            while True:
                user_input = input("Command: ").strip().lower()
                if user_input == "exit":
                    break

                parts = user_input.split()
                if not parts:
                    continue

                color_name = parts[0]
                if color_name not in colors_map:
                    print("Invalid color. Available: red, green, blue, white, yellow, cyan, magenta, off")
                    continue

                color_rgbw = colors_map[color_name]
                
                is_strobe = False
                strobe_interval = 0.1 # Default interval
                duration = 5.0 # Default duration for static or strobe

                if len(parts) > 1 and parts[1] == 's':
                    is_strobe = True
                    if len(parts) > 2:
                        try:
                            strobe_interval = float(parts[2])
                        except ValueError:
                            print("Invalid interval. Please enter a number.")
                            continue
                    if len(parts) > 3:
                        try:
                            duration = float(parts[3])
                        except ValueError:
                            print("Invalid duration. Please enter a number.")
                            continue
                else:
                    if len(parts) > 1:
                        try:
                            duration = float(parts[1])
                        except ValueError:
                            print("Invalid duration. Please enter a number.")
                            continue
                
                # Now, call the update_lighting method
                print(f"Updating DMX: Color={color_name}, Strobe={is_strobe}, Interval={strobe_interval}, Duration={duration}")
                
                dmx.strobe_on = is_strobe # Set the strobe flag
                dmx.strobe_interval = strobe_interval # Set interval if strobing
                
                # The update_lighting method handles setting color_to_strobe or static color
                dmx.update_lighting(color_rgbw, strobe_interval if is_strobe else 0.1) # Pass a non-strobe speed if static

                # Wait for the specified duration
                start_wait = time.time()
                while time.time() - start_wait < duration:
                    if dmx.strobe_on: # If strobing, broadcast loop handles it
                        time.sleep(0.05)
                    else: # If static, we might need to re-send the frame periodically
                        dmx.send_frame()
                        time.sleep(0.03)

                # After duration, turn off lights or reset strobe state
                dmx.strobe_on = False
                dmx.clear_color_channels()
                dmx.send_frame()

        except KeyboardInterrupt:
            print("\nExiting DMX test...")
        finally:
            dmx.close()
