import serial
import time
import threading

# DMX Channel Mapping for your specific light
CH_STROBE = 3  # This channel controls shutter and strobe
CH_RED    = 4
CH_GREEN  = 5
CH_BLUE   = 6
CH_WHITE  = 7
CH_DIMMER = 8  # MASTER DIMMER - Crucial for light output

# Values for Channel 3 (Strobe/Shutter)
VAL_STROBE_FAST = 131    # A value for a fast strobe effect
VAL_LED_START   = 255    # Value to keep the shutter open for solid colors

class SimpleDMX:
    def __init__(self, port: str):
        self.port = port
        self.num_channels = 9 
        self.data = [0] * self.num_channels
        self.running = False
        self.ser = None
        self.thread = None

        try:
            self.ser = serial.Serial(
                port,
                baudrate=250000,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_TWO,
            )
            print(f"✅ Serial port {self.port} opened successfully.")

        except serial.SerialException as e:
            print(f"❌ Error: Could not open serial port {self.port}.")
            print(e)
            self.ser = None

    def set_channel_internal(self, ch: int, value: int):
        if 1 <= ch <= self.num_channels:
            self.data[ch - 1] = max(0, min(255, value))

    def update_lighting(self, color_tuple, is_strobe=False):
        if not self.ser: return

        # Set color channels
        r, g, b, w = color_tuple[:4]
        self.set_channel_internal(CH_RED, r)
        self.set_channel_internal(CH_GREEN, g)
        self.set_channel_internal(CH_BLUE, b)
        self.set_channel_internal(CH_WHITE, w)

        # **CRUCIAL: Set dimmer to full brightness**
        self.set_channel_internal(CH_DIMMER, 255)

        # **CRUCIAL: Set shutter/strobe mode**
        if is_strobe:
            self.set_channel_internal(CH_STROBE, VAL_STROBE_FAST)
        else:
            self.set_channel_internal(CH_STROBE, VAL_LED_START)

    def turn_off(self):
        # Turn light off by setting master dimmer to 0
        self.set_channel_internal(CH_DIMMER, 0)

    def send_frame(self):
        if not self.ser: return
        try:
            self.ser.baudrate = 57600
            self.ser.write(b'\x00')
            self.ser.flush()
            time.sleep(0.001)
            self.ser.baudrate = 250000
            frame = bytes([0]) + bytes(self.data)
            self.ser.write(frame)
            self.ser.flush()
        except serial.SerialException as e:
            print(f"Error sending DMX frame: {e}")

    def broadcast_loop(self):
        while self.running:
            self.send_frame()
            time.sleep(0.03)

    def start_broadcast(self):
        if not self.ser: return
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self.broadcast_loop, daemon=True)
            self.thread.start()
            print("📡 DMX broadcast thread started.")

    def stop_broadcast(self):
        if self.running:
            self.running = False
            if self.thread:
                self.thread.join()

    def close(self):
        self.stop_broadcast()
        if self.ser and self.ser.is_open:
            self.turn_off()
            self.send_frame()
            time.sleep(0.1)
            self.ser.close()
            print(f"🔌 Serial port {self.port} closed.")
