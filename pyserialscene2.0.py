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
        self.colors_to_strobe = []  # List of colors for strobing
        self.strobe_index = 0
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
            if self.strobe_on and self.colors_to_strobe:
                # Guard against race condition: colors_to_strobe might be cleared during loop
                if len(self.colors_to_strobe) == 0:
                    continue

                color = self.colors_to_strobe[self.strobe_index]
                self.set_channels_from_tuple(color)
                self.send_frame()
                time.sleep(self.strobe_interval)

                self.clear_color_channels()
                self.send_frame()
                time.sleep(self.strobe_interval)

                # Only advance index if list is still valid
                if len(self.colors_to_strobe) > 0:
                    self.strobe_index = (self.strobe_index + 1) % len(self.colors_to_strobe)
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
    colors = {
        "red": (255, 0, 0, 0),
        "green": (0, 255, 0, 0),
        "blue": (0, 0, 255, 0),
        "white": (0, 0, 0, 255),
        "yellow": (255, 255, 0, 0),
        "cyan": (0, 255, 255, 0),
        "magenta": (255, 0, 255, 0),
        "purple": (128, 0, 128, 0)
    }

    scenes = {}
    dmx = SimpleDMX(port="/dev/tty.usbserial-A50285BI", num_channels=8, strobe_interval=0.5)

    print("DMX Controller for SHEHDS Mini LED Spotlight")
    print("Available colors:", ", ".join(colors.keys()))
    print("\nCommand format:")
    print("• red 5 → static red for 5 seconds")
    print("• red,blue s 0.3 8 → strobe red and blue alternately every 0.3s for 8s")
    print("• Multiple commands: red 5; blue,green s 0.3 8; yellow 4")
    print("• Type 'scene <name> ...' to save a scene")
    print("• Type 'run <name>' to play a scene")
    print("• Type 'exit' to quit\n")

    dmx.start_broadcast()

    def parse_color_list(color_str):
        color_names = color_str.split(",")
        color_list = []
        for c in color_names:
            c = c.strip()
            if c in colors:
                color_list.append(colors[c])
            else:
                print(f"Invalid color '{c}' - skipping.")
        return color_list

    try:
        while True:
            user_input = input("Enter a command: ").strip().lower()

            if not user_input:
                continue

            if user_input == "exit":
                break

            if user_input.startswith("scene "):
                # Store named scene
                parts = user_input.split(maxsplit=2)
                if len(parts) < 3:
                    print("Usage: scene <name> <steps...>")
                    continue

                scene_name = parts[1]
                steps = parts[2].split(";")
                scenes[scene_name] = []

                for step in steps:
                    step_parts = step.strip().split()
                    if not step_parts:
                        continue

                    color_list = parse_color_list(step_parts[0])
                    strobe = len(step_parts) > 1 and step_parts[1] == 's'
                    interval = float(step_parts[2]) if strobe and len(step_parts) > 2 else 0.5
                    duration = float(step_parts[3]) if strobe and len(step_parts) > 3 else (
                        float(step_parts[1]) if not strobe and len(step_parts) > 1 else 5.0
                    )

                    if color_list:
                        scenes[scene_name].append((color_list, strobe, interval, duration))

                print(f"Scene '{scene_name}' saved with {len(scenes[scene_name])} steps.")

            elif user_input.startswith("run "):
                scene_name = user_input[4:].strip()
                if scene_name not in scenes:
                    print(f"No scene named '{scene_name}' found.")
                    continue

                print(f"Running scene '{scene_name}'...")

                def run_scene_steps(steps):
                    for i, (color_list, strobe, interval, duration) in enumerate(steps):
                        dmx.strobe_interval = interval
                        dmx.strobe_on = strobe
                        dmx.strobe_index = 0

                        if strobe:
                            dmx.colors_to_strobe = color_list
                            print(f"Strobing {len(color_list)} colors every {interval}s for {duration}s.")
                        else:
                            dmx.colors_to_strobe = []
                            dmx.set_channels_from_tuple(color_list[0])
                            print(f"Static {'/'.join([k for k,v in colors.items() if v in color_list])} for {duration}s.")

                        start_time = time.time()
                        while time.time() - start_time < duration:
                            time.sleep(0.05)

                        # End this step
                        dmx.strobe_on = False
                        dmx.colors_to_strobe = []

                        # ❗ Do NOT clear after static step, only clear after last step
                        if strobe:
                            dmx.clear_color_channels()
                            dmx.send_frame()

                    # ✅ Clear after the final step in the scene
                    dmx.clear_color_channels()
                    dmx.send_frame()


                threading.Thread(target=run_scene_steps, args=(scenes[scene_name],), daemon=True).start()

            else:
                # Single command mode
                parts = user_input.split()
                if not parts:
                    continue

                color_list = parse_color_list(parts[0])
                strobe = len(parts) > 1 and parts[1] == 's'
                interval = float(parts[2]) if strobe and len(parts) > 2 else 0.5
                duration = float(parts[3]) if strobe and len(parts) > 3 else (
                    float(parts[1]) if not strobe and len(parts) > 1 else 5.0
                )

                if color_list:
                    dmx.strobe_interval = interval
                    dmx.strobe_on = strobe
                    dmx.strobe_index = 0

                    if strobe:
                        dmx.colors_to_strobe = color_list
                        print(f"Strobing {len(color_list)} colors every {interval}s for {duration}s.")
                    else:
                        dmx.set_channels_from_tuple(color_list[0])
                        print(f"Static {'/'.join([k for k,v in colors.items() if v in color_list])} for {duration}s.")

                    start_time = time.time()
                    while time.time() - start_time < duration:
                        time.sleep(0.05)

                    dmx.strobe_on = False
                    dmx.colors_to_strobe = []
                    dmx.clear_color_channels()
                    dmx.send_frame()
                else:
                    print("Invalid color(s). Try again.")

    except KeyboardInterrupt:
        print("\nExiting program...")

    finally:
        dmx.stop_broadcast()
        dmx.clear_color_channels()
        dmx.send_frame()
        time.sleep(0.1)
        dmx.close()
