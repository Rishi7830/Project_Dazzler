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
        self.scene_on = False
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
            print(f"Error: Could not open serial port {port}. Please check the port name and connection.")
            print(e)
            exit()

    def set_channel(self, ch: int, value: int):
        if 1 <= ch <= self.num_channels:
            self.data[ch-1] = max(0, min(255, value))

    def clear_color_channels(self):
        self.set_channel(1, 0)
        self.set_channel(2, 0)
        self.set_channel(3, 0)
        self.set_channel(4, 0)

    def send_frame(self):
        self.ser.baudrate = 57600
        self.ser.write(b'\x00')
        self.ser.flush()
        time.sleep(0.001)
        self.ser.baudrate = 250000
        frame = bytes([0]) + bytes(self.data)
        self.ser.write(frame)
        self.ser.flush()

    def set_channels_from_tuple(self, color_tuple):
        r, g, b, w = color_tuple
        self.clear_color_channels()
        self.set_channel(1, r)
        self.set_channel(2, g)
        self.set_channel(3, b)
        self.set_channel(4, w)

    def broadcast_loop(self, colors):
        color_names = list(colors.keys())
        scene_color_index = 0
        strobe_counter = 0
        strobe_limit = 2

        while self.running:
            if self.scene_on:
                current_color_name = color_names[scene_color_index]
                current_color = colors[current_color_name]
                
                self.set_channels_from_tuple(current_color)
                self.send_frame()
                time.sleep(0.05)  # Time the light is on
                self.clear_color_channels()
                self.send_frame()
                time.sleep(0.05)  # Time the light is off

                strobe_counter += 1
                if strobe_counter >= strobe_limit:
                    strobe_counter = 0
                    scene_color_index = (scene_color_index + 1) % len(color_names)
            elif self.strobe_on:
                self.set_channels_from_tuple(self.color_to_strobe)
                self.send_frame()
                time.sleep(0.05)
                self.clear_color_channels()
                self.send_frame()
                time.sleep(0.05)
            else:
                self.send_frame()
                time.sleep(0.03)

    def start_broadcast(self, colors):
        self.running = True
        self.thread = threading.Thread(target=self.broadcast_loop, args=(colors,))
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

    dmx = SimpleDMX(port="COM4", num_channels=8)

    print("DMX Controller for your SHEHDS Mini LED Spotlight.")
    print("Available colors:")
    for color in colors.keys():
        print(f"- {color.capitalize()}")
    print("\nTo strobe a color, type the color name followed by 's' (e.g., 'red s').")
    print("To start a color scene, type 'scene'.")
    print("Press Ctrl+C to exit.")

    dmx.start_broadcast(colors)

    try:
        while True:
            user_input = input("Enter a command: ").lower().split()
            command = user_input[0]
            
            dmx.strobe_on = False
            dmx.scene_on = False

            if command in colors:
                if len(user_input) > 1 and user_input[1] == 's':
                    dmx.strobe_on = True
                    dmx.color_to_strobe = colors[command]
                    print(f"Set light to strobing {command}.")
                else:
                    dmx.set_channels_from_tuple(colors[command])
                    print(f"Set light to static {command}.")
            elif command == "scene":
                dmx.scene_on = True
                print("Starting scene mode.")
            elif command == "exit":
                break
            else:
                print("Invalid command. Please choose from the list or type 'exit' to quit.")

    except KeyboardInterrupt:
        print("\nExiting program due to KeyboardInterrupt.")
    finally:
        dmx.stop_broadcast()
        dmx.clear_color_channels()
        dmx.send_frame()
        time.sleep(0.1)
        dmx.close()
