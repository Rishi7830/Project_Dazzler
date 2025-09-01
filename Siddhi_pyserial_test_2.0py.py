import serial
import time

class SimpleDMX:
    def __init__(self, port: str, num_channels: int = 512):
        self.port = port
        self.num_channels = num_channels
        self.data = [0] * num_channels

        # Open raw serial for DMX (250000 baud, 8N2)
        self.ser = serial.Serial(
            port,
            baudrate=250000,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_TWO,
        )

    def set_channel(self, ch: int, value: int):
        """Set DMX channel (1–512) to value (0–255)."""
        if 1 <= ch <= self.num_channels:
            self.data[ch-1] = max(0, min(255, value))

    def send_frame(self):
        """Send one DMX frame (break + data)."""
        # Send BREAK (low for at least 88 µs). pyserial hack: baudrate trick
        self.ser.baudrate = 57600  # slower baudrate forces longer low (break)
        self.ser.write(b'\x00')
        self.ser.flush()
        time.sleep(0.001)  # ~1ms break
        self.ser.baudrate = 250000

        # Start code + channel data
        frame = bytes([0]) + bytes(self.data)  # 0 = DMX start code
        self.ser.write(frame)
        self.ser.flush()

    def close(self):
        self.ser.close()


if __name__ == "__main__":
    # Pick the port manually (check with `python -m serial.tools.list_ports`)
    dmx = SimpleDMX(port="/dev/ttyUSB0", num_channels=8)

    # Hardcode some values
    dmx.set_channel(1, 255)   # Channel 1 full
    dmx.set_channel(2, 128)   # Channel 2 half
    dmx.set_channel(3, 64)    # Channel 3 low
    dmx.set_channel(4, 0)     # Channel 4 off
    dmx.set_channel(5, 200)
    dmx.set_channel(6, 50)
    dmx.set_channel(7, 10)
    dmx.set_channel(8, 255)

    try:
        while True:
            dmx.send_frame()
            time.sleep(0.03)  # ~30Hz refresh
    except KeyboardInterrupt:
        dmx.close()
