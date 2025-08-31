import serial
import time
import sys

# --- Part 1: DMX Setup ---
def send_dmx(port, channel_data):
    try:
        # Initialize the serial port. The baud rate is a DMX standard.
        ser = serial.Serial(port, baudrate=250000, bytesize=8, stopbits=2, parity='N', timeout=1)
        
        # Send the DMX start code (0x00)
        ser.write(bytes([0x00]))
        
        # Create a 512-byte DMX frame
        dmx_frame = [0] * 512
        for channel, value in channel_data.items():
            if 1 <= channel <= 512:
                dmx_frame[channel - 1] = value

        # Send the DMX frame
        ser.write(bytes(dmx_frame))
        
        ser.close()
        return True
    except Exception as e:
        print(f"Error: {e}")
        return False

# --- Part 2: Mood-to-Color Mapping ---
mood_colors = {
    'calm':       (0, 0, 255),  # Deep Blue
    'energetic':  (255, 255, 0),# Yellow
    'angry':      (255, 0, 0),  # Red
    'happy':      (0, 255, 0),  # Green
    'sad':        (0, 0, 128),  # Dark Blue
    'romantic':   (255, 105, 180),# Pink
    'excited':    (255, 165, 0),# Orange
    'mysterious': (128, 0, 128) # Purple
}

# Set the starting DMX channel for your light fixture.
start_channel = 1

# --- User Input and DMX Control Loop ---
print("DMX controller ready for mood input.")
print(f"Available moods: {', '.join(mood_colors.keys())}")
print("Type 'exit' or press Ctrl+C to quit.")

while True:
    user_input = input("Enter a mood: ").lower().strip()

    if user_input == 'exit':
        break

    if user_input in mood_colors:
        rgb_color = mood_colors[user_input]
        
        print(f"Setting lights to '{user_input}' color: RGB{rgb_color}")

        channel_data = {
            start_channel: rgb_color[0],
            start_channel + 1: rgb_color[1],
            start_channel + 2: rgb_color[2],
            start_channel + 3: 255  # Set the dimmer channel to full intensity
        }

        if not send_dmx('COM4', channel_data):
            break

    else:
        print("Sorry, that mood is not in the list. Please try again.")

# Turn the lights off when the program exits
send_dmx('COM4', {start_channel + 3: 0})

print("DMX controller stopped. Lights turned off.")
