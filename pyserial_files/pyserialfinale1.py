import serial
import time
import threading

class SimpleDMX:
    def __init__(self, port: str, num_channels: int = 512):
        self.port = port
        self.num_channels = num_channels
        self.data = [0] * num_channels
        self.running = False
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

    def broadcast_loop(self):
        while self.running:
            self.send_frame()
            time.sleep(0.03)

    def start_broadcast(self):
        self.running = True
        self.thread = threading.Thread(target=self.broadcast_loop)
        self.thread.daemon = True # Allows the program to exit even if this thread is still running
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
    print("\nPress Ctrl+C to exit.")

    dmx.start_broadcast()

    try:
        while True:
            user_input = input("Enter a color name: ").lower()
            if user_input in colors:
                r, g, b, w = colors[user_input]
                dmx.clear_color_channels()
                dmx.set_channel(1, r)
                dmx.set_channel(2, g)
                dmx.set_channel(3, b)
                dmx.set_channel(4, w)
                print(f"Set light to {user_input}.")
            elif user_input == "exit":
                break
            else:
                print("Invalid color. Please choose from the list above or type 'exit' to quit.")

    except KeyboardInterrupt:
        print("\nExiting program due to KeyboardInterrupt.")
    finally:
        # Turn off light and close DMX connection
        dmx.stop_broadcast()
        dmx.clear_color_channels()
        dmx.send_frame()
        time.sleep(0.1)
        dmx.close()
