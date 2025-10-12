import serial
import time
import threading

# Define the specific channel mapping for the Behringer MH363
CH_PAN = 1
CH_TILT = 2
CH_STROBE = 3 # Strobe/LED Start channel
CH_RED = 4
CH_GREEN = 5
CH_BLUE = 6
CH_WHITE = 7
CH_DIMMER = 8 # Master Dimmer is critical for light output
CH_SOUND = 9

# Define values for the Strobe/LED Start channel (CH 3)
VAL_LED_START = 255 # Value for constant light

class SimpleDMX:
    def __init__(self, port: str, num_channels: int = 512, strobe_interval: float = 0.1):
        self.port = port
        # We must use at least 8 channels for the MH363 to work correctly
        self.num_channels = max(8, num_channels) 
        self.data = [0] * self.num_channels
        self.running = False
        self.strobe_on = False
        self.strobe_interval = strobe_interval
        self.color_to_strobe = (0, 0, 0, 0)
        self.thread = None

        try:
            # THIS IS WHERE THE ERROR OCCURRED: Now fixed by renaming the file 
            # so Python correctly finds the external 'serial' library.
            self.ser = serial.Serial(
                port,
                baudrate=250000,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_TWO,
            )
            print(f"Serial port {self.port} opened successfully.")
            
            # 1. Initialize non-color channels to safe/active states
            self.set_channel_internal(CH_PAN, 0)
            self.set_channel_internal(CH_TILT, 0)
            # Set Strobe to LED START for static color (CH 3)
            self.set_channel_internal(CH_STROBE, VAL_LED_START) 
            # Set Dimmer to FULL (CH 8) to ensure LEDs are visible
            self.set_channel_internal(CH_DIMMER, 255) 

        except serial.SerialException as e:
            # THIS IS WHERE THE SECOND ERROR OCCURRED
            print(f"Error: Could not open serial port {self.port}.")
            print(e)
            self.ser = None

    def set_channel_internal(self, ch: int, value: int):
        """Internal helper to set DMX channel data (0-255 clipping applied)."""
        if 1 <= ch <= self.num_channels:
            self.data[ch - 1] = max(0, min(255, value))

    def set_channel(self, ch: int, value: int):
        """Sets a single DMX channel value and checks serial port availability."""
        if self.ser:
            self.set_channel_internal(ch, value)
        else:
            print("Serial port not available. Cannot set channel.")

    def clear_color_channels(self):
        """Clears RGBW color channels (4-7) and turns off the master dimmer (CH 8)."""
        if self.ser:
            # Clear RGBW (Channels 4, 5, 6, 7)
            for ch in range(CH_RED, CH_WHITE + 1):
                self.set_channel_internal(ch, 0)
            # Turn off master dimmer (Channel 8)
            self.set_channel_internal(CH_DIMMER, 0) 
            # Set strobe to LED OFF (Channel 3)
            self.set_channel_internal(CH_STROBE, 0)


    def set_channels_from_tuple(self, color_tuple):
        """Sets the RGBW channels (4-7) from a tuple (R, G, B, W)."""
        if self.ser and len(color_tuple) >= 4:
            r, g, b, w = color_tuple[:4]
            self.set_channel_internal(CH_RED, r)
            self.set_channel_internal(CH_GREEN, g)
            self.set_channel_internal(CH_BLUE, b)
            self.set_channel_internal(CH_WHITE, w)
        elif not self.ser:
            print("Serial port not available. Cannot set channels from tuple.")


    def update_lighting(self, color_tuple, hue_speed):
        """
        Updates the DMX state based on the color and speed from audio analysis,
        managing Dimmer (CH 8) and Strobe (CH 3).
        """
        if not self.ser:
            return

        strobe_threshold = 0.2
        if hue_speed > strobe_threshold:
            self.strobe_on = True
            # Map hue_speed to an interval. Higher speed = shorter interval.
            self.strobe_interval = max(0.05, 1.0 / (hue_speed * 10))
            self.color_to_strobe = color_tuple
            
            # Set the color and Master Dimmer to full
            self.set_channels_from_tuple(self.color_to_strobe)
            self.set_channel_internal(CH_DIMMER, 255)
            # Set CH 3 to a fast strobe value (e.g., 100)
            self.set_channel_internal(CH_STROBE, 100) 
            
        else:
            self.strobe_on = False
            self.set_channels_from_tuple(color_tuple) # Set static color (CH 4-7)
            self.set_channel_internal(CH_DIMMER, 255) # Set Master Dimmer to full (CH 8)
            self.set_channel_internal(CH_STROBE, VAL_LED_START) # Set to constant on (CH 3)

        self.send_frame()

    def send_frame(self):
        """Sends the current DMX data frame."""
        if not self.ser:
            return

        # DMX protocol requires a break and MAB (Mark After Break)
        try:
            self.ser.baudrate = 57600
            self.ser.write(b'\x00')
            self.ser.flush()
            time.sleep(0.001) 
            self.ser.baudrate = 250000
            
            # DMX packet starts with a START CODE (0x00 for DMX512)
            frame = bytes([0]) + bytes(self.data)
            self.ser.write(frame)
            self.ser.flush()
        except serial.SerialException as e:
            print(f"Error sending DMX frame: {e}")

    def broadcast_loop(self):
        """The main loop that continuously sends DMX frames."""
        print("DMX broadcast thread started.")
        while self.running:
            # We send frames repeatedly, adjusting the delay based on strobe state
            self.send_frame()
            if self.strobe_on:
                time.sleep(self.strobe_interval)
            else:
                time.sleep(0.03) # Standard refresh rate
        print("DMX broadcast thread stopped.")

    def start_broadcast(self):
        """Starts the background thread to continuously send DMX data."""
        if not self.ser:
            print("Cannot start broadcast: Serial port not available.")
            return
            
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self.broadcast_loop, daemon=True)
            self.thread.start()

    def stop_broadcast(self):
        """Stops the background DMX thread."""
        if self.running and self.thread:
            self.running = False
            self.thread.join()

    def close(self):
        """Stops broadcast, clears lights, and closes the serial port."""
        self.stop_broadcast()
        if self.ser and self.ser.is_open:
            # Send a clear frame before closing to turn off the light
            self.clear_color_channels()
            self.send_frame()
            time.sleep(0.1) 
            self.ser.close()
            print(f"Serial port {self.port} closed.")

# The __main__ block is preserved for testing dmx_controller.py independently
if __name__ == "__main__":
    # Example Usage for testing:
    # Replace with your actual serial port
    SERIAL_PORT = "/dev/ttyUSB0" # macOS or Linux (or "COMx" on Windows)
    
    # Initialize with 8 channels for the MH363
    dmx = SimpleDMX(port=SERIAL_PORT, num_channels=8, strobe_interval=0.5)

    if not dmx.ser:
        print("Exiting test script: Could not initialize DMX controller.")
    else:
        dmx.start_broadcast()

        try:
            print("\n--- DMX Test Mode for Behringer MH363 ---")
            print("Channels 3 (LED Start), 4-7 (RGBW), 8 (Dimmer) are managed.")
            input("Press Enter to turn RED light ON for 5 seconds...")
            dmx.update_lighting((255, 0, 0, 0), 0.1) # Red, no strobe
            time.sleep(5)
            
            input("Press Enter to turn GREEN STROBE ON for 5 seconds...")
            dmx.update_lighting((0, 255, 0, 0), 1.0) # Green, high speed strobe
            time.sleep(5)

            input("Press Enter to turn OFF and exit...")
            dmx.strobe_on = False
            dmx.clear_color_channels() 
            dmx.send_frame()

        except KeyboardInterrupt:
            print("\nExiting DMX test...")
        finally:
            dmx.close()
