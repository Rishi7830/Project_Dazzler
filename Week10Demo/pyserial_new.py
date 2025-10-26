import serial
import time
import threading

# MH363 9-channel DMX map:
# 1: Pan (0-255 -> 0°–630°)
# 2: Tilt (0-255 -> 0°–220°)
# 3: Strobe/Shutter (bands incl. off, strobe, fade pulses, lightning, full on)
# 4: Red (0-255)
# 5: Green (0-255)
# 6: Blue (0-255)
# 7: White (0-255)
# 8: Master Dimmer (0-255)
# 9: Sound Control (0-239 none, 240-255 sound active)

CH_PAN_1   = 1
CH_TILT_1  = 2
CH_STROBE_1 = 3
CH_RED_1   = 4
CH_GREEN_1 = 5
CH_BLUE_1  = 6
CH_WHITE_1 = 7
CH_DIMMER_1 = 8
CH_SOUND_1= 9

CH_PAN_2   = 10
CH_TILT_2  = 11
CH_STROBE_2 = 12
CH_RED_2   = 13
CH_GREEN_2 = 14
CH_BLUE_2  = 15
CH_WHITE_2 = 16
CH_DIMMER_2 = 17
CH_SOUND_2 = 18

# Strobe channel value helpers (Channel 3)
VAL_LED_OFF   = 0       # explicit off band start
VAL_STROBE_FAST = 131   # in the "strobe slow->fast" band (~16–131), 131 is fast end
VAL_FADE_FAST   = 181   # in the "fade slow->fast" band (~140–181), 181 is fast end
VAL_LIGHTNING   = 244   # in the "lightning" band (~240–247)
VAL_LED_START   = 255   # constant on

class SimpleDMX:
    def __init__(self, port: str, strobe_interval: float = 0.1):
        self.port = port
        # Two 9-channel fixtures = 18 channels total
        self.num_channels = 18
        self.data = [0] * self.num_channels
        self.running = False
        self.strobe_on = False
        self.strobe_interval = strobe_interval
        self.color_to_strobe = (0, 0, 0, 0)  # r,g,b,w
        self.thread = None

        try:
            self.ser = serial.Serial(
                port,
                baudrate=250000,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_TWO,
            )
            print(f"Serial port {self.port} opened successfully.")

            # Initialize both fixtures (fixture1 channels 1..9, fixture2 channels 10..18)
            self.set_channel_internal(CH_PAN_1, 0)
            self.set_channel_internal(CH_TILT_1, 0)
            self.set_channel_internal(CH_STROBE_1, VAL_LED_START)  # constant light
            self.set_channel_internal(CH_DIMMER_1, 255)            # full output
            self.set_channel_internal(CH_SOUND_1, 0)               # sound off

            self.set_channel_internal(CH_PAN_2, 0)
            self.set_channel_internal(CH_TILT_2, 0)
            self.set_channel_internal(CH_STROBE_2, VAL_LED_START)  # constant light
            self.set_channel_internal(CH_DIMMER_2, 255)            # full output
            self.set_channel_internal(CH_SOUND_2, 0)               # sound off

            # Immediately send initial frame so hardware mirrors the default values
            self.send_frame()
            
        except serial.SerialException as e:
            print(f"Error: Could not open serial port {self.port}.")
            print(e)
            self.ser = None

    def set_channel_internal(self, ch: int, value: int):
        if 1 <= ch <= self.num_channels:
            self.data[ch - 1] = max(0, min(255, value))

    def set_channel(self, ch: int, value: int):
        if self.ser:
            self.set_channel_internal(ch, value)
        else:
            print("Serial port not available. Cannot set channel.")

    def clear_color_channels(self):
        if self.ser:
            for ch in range(CH_RED_1, CH_WHITE_1 + 1):
                self.set_channel_internal(ch, 0)
            self.set_channel_internal(CH_DIMMER_1, VAL_LED_OFF)

            for ch in range(CH_RED_2, CH_WHITE_2 + 1):
                self.set_channel_internal(ch, 0)
            self.set_channel_internal(CH_DIMMER_2, VAL_LED_OFF)

    def set_channels_from_tuple(self, color_tuple):
        if self.ser and len(color_tuple) >= 4:
            r, g, b, w = color_tuple[:4]
            self.set_channel_internal(CH_RED_1, r)
            self.set_channel_internal(CH_GREEN_1, g)
            self.set_channel_internal(CH_BLUE_1, b)
            self.set_channel_internal(CH_WHITE_1, w)

            self.set_channel_internal(CH_RED_2, r)
            self.set_channel_internal(CH_GREEN_2, g)
            self.set_channel_internal(CH_BLUE_2, b)
            self.set_channel_internal(CH_WHITE_2, w)
        elif not self.ser:
            print("Serial port not available. Cannot set channels from tuple.")

    def update_lighting(self, color_tuple, hue_speed):
        if not self.ser:
            return

        strobe_threshold = 0.2
        if hue_speed > strobe_threshold:
            self.strobe_on = True
            self.strobe_interval = max(0.05, 1.0 / (hue_speed * 10))
            self.color_to_strobe = color_tuple

            # Apply color and full dimmer
            self.set_channels_from_tuple(self.color_to_strobe)
            self.set_channel_internal(CH_DIMMER_1, 255)
            self.set_channel_internal(CH_DIMMER_2, 255)

            # Use CH3 strobe band; choose fast regular strobe by default
            self.set_channel_internal(CH_STROBE_1, VAL_STROBE_FAST)
            self.set_channel_internal(CH_STROBE_2, VAL_STROBE_FAST)
        else:
            self.strobe_on = False
            self.set_channels_from_tuple(color_tuple)
            self.set_channel_internal(CH_DIMMER_1, 255)
            self.set_channel_internal(CH_STROBE_1, VAL_LED_START)  # constant on
            self.set_channel_internal(CH_DIMMER_2, 255)
            self.set_channel_internal(CH_STROBE_2, VAL_LED_START)  # constant on

        self.send_frame()

    def send_frame(self):
        if not self.ser:
            return
        try:
            # DMX break
            self.ser.baudrate = 57600
            self.ser.write(b'\x00')
            self.ser.flush()
            time.sleep(0.001)
            self.ser.baudrate = 250000

            # Start code + 18 bytes only
            frame = bytes([0]) + bytes(self.data)
            self.ser.write(frame)
            self.ser.flush()
        except serial.SerialException as e:
            print(f"Error sending DMX frame: {e}")

    def broadcast_loop(self):
        print("DMX broadcast thread started.")
        while self.running:
            self.send_frame()
            time.sleep(self.strobe_on and self.strobe_interval or 0.03)
        print("DMX broadcast thread stopped.")

    def start_broadcast(self):
        if not self.ser:
            print("Cannot start broadcast: Serial port not available.")
            return
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self.broadcast_loop, daemon=True)
            self.thread.start()

    def stop_broadcast(self):
        if self.running and self.thread:
            self.running = False
            self.thread.join()

    def close(self):
        self.stop_broadcast()
        if self.ser and self.ser.is_open:
            self.clear_color_channels()
            self.send_frame()
            time.sleep(0.1)
            self.ser.close()
            print(f"Serial port {self.port} closed.")

if __name__ == "__main__":
    SERIAL_PORT = "/dev/ttyUSB0"
    dmx = SimpleDMX(port=SERIAL_PORT, strobe_interval=0.5)

    if not dmx.ser:
        print("Exiting test script: Could not initialize DMX controller.")
    else:
        dmx.start_broadcast()

        try:
            print("\n--- DMX Test Mode for Behringer MH363 (9CH) ---")
            print("CH3 (strobe), CH4-7 (RGBW), CH8 (dimmer) managed.")

            colors_map = {
                "red": (255, 0, 0, 0),
                "green": (0, 255, 0, 0),
                "blue": (0, 0, 255, 0),
                "white": (0, 0, 0, 255),
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
                    print("Invalid color. Available:", ", ".join(colors_map.keys()))
                    continue

                color_rgbw = colors_map[color_name]

                is_strobe = False
                duration = 5.0
                # Optional: 's [speed 0.3..2.0] [duration]'
                if len(parts) > 1 and parts[1] == 's':
                    is_strobe = True
                    speed = 1.0
                    if len(parts) > 2:
                        try:
                            speed = float(parts[2])
                        except ValueError:
                            print("Invalid speed. Using default 1.0.")
                    if len(parts) > 3:
                        try:
                            duration = float(parts[3])
                        except ValueError:
                            print("Invalid duration. Using default 5.0.")
                    dmx.update_lighting(color_rgbw, speed)
                else:
                    if len(parts) > 1:
                        try:
                            duration = float(parts[1])
                        except ValueError:
                            print("Invalid duration. Using default 5.0.")
                    dmx.update_lighting(color_rgbw, 0.0)

                start_wait = time.time()
                while time.time() - start_wait < duration:
                    time.sleep(0.03)

                dmx.strobe_on = False
                dmx.clear_color_channels()
                dmx.send_frame()

        except KeyboardInterrupt:
            print("\nExiting DMX test...")
        finally:
            dmx.close()




