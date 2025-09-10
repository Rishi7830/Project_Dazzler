import serial
import time
import threading

class SimpleDMX:
    def __init__(self, port: str, num_channels: int = 512):
        self.port = port
        self.num_channels = num_channels
        self.data = [0] * num_channels
        self.running = False
        self.strobe_on = False
        self.strobe_interval = 0.1 # Default value
        self.color_to_strobe = (0, 0, 0, 0)
        self.thread = None

        try:
            self.ser = serial.Serial(
                port,
                baudrate=250000,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_TWO,
            )
        except serial.SerialException as e:
            print(f"Error: Could not open serial port {port}.")
            print(e)
            # A more robust solution would be to handle this gracefully
            self.ser = None 
    
    def set_channel(self, ch: int, value: int):
        if 1 <= ch <= self.num_channels:
            self.data[ch - 1] = max(0, min(255, value))
    
    def clear_color_channels(self):
        # Assuming channels 1-4 are RGBW
        for ch in range(1, 5):
            self.set_channel(ch, 0)
    
    def set_channels_from_tuple(self, color_tuple):
        r, g, b, w = color_tuple
        self.set_channel(1, r)
        self.set_channel(2, g)
        self.set_channel(3, b)
        self.set_channel(4, w)

    def update_lighting(self, color_tuple, hue_speed):
        """
        Public method to be called by the main audio loop to update the DMX state
        """
        # A low hue_speed means no strobe, just a solid color
        if hue_speed < 0.2:
            self.strobe_on = False
            self.set_channels_from_tuple(color_tuple)
        else:
            self.strobe_on = True
            self.strobe_interval = 1.0 / (hue_speed * 10) # Example: map speed to frequency
            self.color_to_strobe = color_tuple
        
    def send_frame(self):
        if not self.ser:
            return
        # DMX protocol requires a break and MAB
        self.ser.baudrate = 57600
        self.ser.write(b'\x00')
        self.ser.flush()
        time.sleep(0.001)
        self.ser.baudrate = 250000
        frame = bytes([0]) + bytes(self.data)
        self.ser.write(frame)
        self.ser.flush()

    def broadcast_loop(self):
        while self.running:
            if self.strobe_on:
                self.set_channels_from_tuple(self.color_to_strobe)
                self.send_frame()
                time.sleep(self.strobe_interval)
                self.clear_color_channels()
                self.send_frame()
                time.sleep(self.strobe_interval)
            else:
                self.send_frame()
                time.sleep(0.03) # DMX standard refresh rate is around 30-40Hz

    def start_broadcast(self):
        if not self.ser:
            return
        self.running = True
        self.thread = threading.Thread(target=self.broadcast_loop, daemon=True)
        self.thread.start()

    def stop_broadcast(self):
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join()

    def close(self):
        if self.ser and self.ser.is_open:
            self.ser.close()

if __name__ == "__main__":
    dmx = SimpleDMX(port="/dev/tty.usbserial-A50285BI", num_channels=8)
    # The example code for user input would no longer be needed as the class
    # is now designed for external control via the `update_lighting` method.
    dmx.start_broadcast()
    try:
        while True:
            # Placeholder for where you would receive new color/speed data
            # and call dmx.update_lighting()
            time.sleep(1) 
    except KeyboardInterrupt:
        print("\nExiting program...")
    finally:
        dmx.stop_broadcast()
        dmx.close()