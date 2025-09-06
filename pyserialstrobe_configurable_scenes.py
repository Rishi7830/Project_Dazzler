import serial
import time
import threading

class SimpleDMX:
    def __init__(self, port: str, num_channels: int = 512, strobe_interval: float = 0.5):
        self.port = port
        self.num_channels = num_channels
        self.data = [0] * num_channels
        self.running = False
        self.strobe_on = False
        self.color_to_strobe = (0, 0, 0, 0)
        self.thread = None
        self.strobe_interval = strobe_interval

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

    def set_channel(self, ch: int, value: int):
        if 1 <= ch <= self.num_channels:
            self.data[ch - 1] = max(0, min(255, value))

    def clear_color_channels(self):
        for ch in range(1, 5):
            self.set_channel(ch, 0)

    def send_frame(self):
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
                time.sleep(0.03)

    def set_channels_from_tuple(self, color_tuple):
        r, g, b, w = color_tuple
        self.clear_color_channels()
        self.set_channel(1, r)
        self.set_channel(2, g)
        self.set_channel(3, b)
        self.set_channel(4, w)

    def start_broadcast(self):
        self.running = True
        self.thread = threading.Thread(target=self.broadcast_loop)
        self.thread.daemon = True
        self.thread.start()

    def stop_broadcast(self):
        self.running = False
        if self.thread:
            self.thread.join()

    def close(self):
        self.ser.close()

if __name__ == "__main__":
    import time

    colors = {
        "red": (255, 0, 0),
        "green": (0, 255, 0),
        "blue": (0, 0, 255),
        "white": (0, 0, 255),
        "yellow": (255, 255, 0),
        "cyan": (0, 255, 255, 0),
        "magenta": (255, 0, 255, 0),
        "purple": (128, 0, 128, 0)
    }

    scenes = {}
    dmx = SimpleDMX(port="/dev/tty.usbserial-A50285BI", num_channels=8, strobe_interval=0.5)

    print("DMX Controller for SHEHDS Mini LED Spotlight")
    print("Available colors:")
    for color in colors:
        print(f"- {color.capitalize()}")
    print("\nCommand format:")
    print("• red 5 → static red for 5 seconds")
    print("• blue s 0.3 8 → strobe blue every 0.3s for 8 seconds")
    print("• Multiple commands: red 5; blue s 0.3 8; green 4")
    print("• Type 'exit' to quit")

    dmx.start_broadcast()

    try:
        while True:
            user_input = input("Enter a command: ").strip().lower()

            if not user_input:
                continue

            if user_input == "exit":
                break

            if user_input.startswith("scene "):
                # Define a scene
                scene_data = user_input[6:].strip()
                steps = scene_data.split(";")
                scene_name = "scene"  # You can extend this to allow naming
                scenes[scene_name] = []

                for step in steps:
                    parts = step.strip().split()
                    if not parts:
                        continue

                    color = parts[0]
                    strobe = len(parts) > 1 and parts[1] == 's'
                    interval = float(parts[2]) if strobe and len(parts) > 2 else 0.5
                    duration = float(parts[3]) if strobe and len(parts) > 3 else (
                        float(parts[2]) if not strobe and len(parts) > 2 else 5.0
                    )

                    if color in colors:
                        scenes[scene_name].append((color, strobe, interval, duration))
                    else:
                        print(f"Invalid color '{color}' in scene. Skipping.")

                print(f"Scene '{scene_name}' saved with {len(scenes[scene_name])} steps.")

            elif user_input.startswith("run "):
                scene_name = user_input[4:].strip()
                if scene_name not in scenes:
                    print(f"No scene named '{scene_name}' found.")
                    continue

                print(f"Running scene '{scene_name}'...")
                for color, strobe, interval, duration in scenes[scene_name]:
                    dmx.strobe_interval = interval
                    dmx.strobe_on = strobe

                    if strobe:
                        dmx.color_to_strobe = colors[color]
                        print(f"Strobing {color} every {interval}s for {duration}s.")
                    else:
                        dmx.set_channels_from_tuple(colors[color])
                        print(f"Static {color} for {duration}s.")

                    time.sleep(duration)
                    dmx.strobe_on = False
                    dmx.clear_color_channels()
                    dmx.send_frame()

            else:
                # Single command mode
                parts = user_input.split()
                if not parts:
                    continue

                color = parts[0]
                strobe = len(parts) > 1 and parts[1] == 's'
                interval = float(parts[2]) if strobe and len(parts) > 2 else 0.5
                duration = float(parts[3]) if strobe and len(parts) > 3 else (
                    float(parts[2]) if not strobe and len(parts) > 2 else 5.0
                )

                if color in colors:
                    dmx.strobe_interval = interval
                    dmx.strobe_on = strobe

                    if strobe:
                        dmx.color_to_strobe = colors[color]
                        print(f"Strobing {color} every {interval}s for {duration}s.")
                    else:
                        dmx.set_channels_from_tuple(colors[color])
                        print(f"Static {color} for {duration}s.")

                    time.sleep(duration)
                    dmx.strobe_on = False
                    dmx.clear_color_channels()
                    dmx.send_frame()
                else:
                    print("Invalid command. Try again or type 'exit'.")


    except KeyboardInterrupt:
        print("\nExiting program...")

    finally:
        dmx.stop_broadcast()
        dmx.clear_color_channels()
        dmx.send_frame()
        time.sleep(0.1)
        dmx.close()
