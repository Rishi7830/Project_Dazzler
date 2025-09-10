import serial
import time
import threading

class SimpleDMX:
    def __init__(self, port: str, num_channels: int = 512):
        self.port = port
        self.num_channels = num_channels
        self.data = [0] * num_channels

        self.running = True
        self.lock = threading.Lock()

        # Current color and speed
        self.current_color = (0, 0, 0, 0)
        self.hue_speed = 0.5  # default strobe interval
        self.strobe_on = False

        # Thread for broadcast loop
        self.thread = threading.Thread(target=self._broadcast_loop)
        self.thread.daemon = True

        # Initialize serial
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
            exit()

        self.thread.start()

    def _set_channels_from_tuple(self, color_tuple):
        r, g, b, w = color_tuple
        self.data[0:4] = [r, g, b, w]

    def _send_frame(self):
        # Send DMX frame
        frame = bytes([0]) + bytes(self.data)
        self.ser.write(frame)
        self.ser.flush()

    def _broadcast_loop(self):
        while self.running:
            with self.lock:
                color = self.current_color
                interval = self.hue_speed
                strobe = self.strobe_on

            if strobe:
                # Strobe on
                self._set_channels_from_tuple(color)
                self._send_frame()
                time.sleep(interval)
                # Clear for off phase
                self._set_channels_from_tuple((0, 0, 0, 0))
                self._send_frame()
                time.sleep(interval)
            else:
                # Static color
                self._set_channels_from_tuple(color)
                self._send_frame()
                time.sleep(0.03)

    def update(self, color, hue_speed=0.5, strobe=False):
        """Update DMX output immediately."""
        with self.lock:
            self.current_color = color
            self.hue_speed = hue_speed
            self.strobe_on = strobe

    def stop(self):
        self.running = False
        self.thread.join()
        self._set_channels_from_tuple((0, 0, 0, 0))
        self._send_frame()
        self.ser.close()


# Example usage
if __name__ == "__main__":
    colors = {
        "red": (255, 0, 0, 0),
        "green": (0, 255, 0, 0),
        "blue": (0, 0, 255, 0),
        "white": (0, 0, 0, 255)
    }

    dmx = SimpleDMX(port="/dev/tty.usbserial-A50285BI")

    try:
        while True:
            cmd = input("Enter color: ").strip().lower()
            if cmd == "exit":
                break
            elif cmd in colors:
                dmx.update(colors[cmd], hue_speed=0.2, strobe=True)
            else:
                print("Invalid color")
    except KeyboardInterrupt:
        pass
    finally:
        dmx.stop()
