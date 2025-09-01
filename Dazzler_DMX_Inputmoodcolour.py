import PyDMXControl.controllers as controllers
import time

# --- Part 1: DMX Setup ---
# Initialize the DMX controller. You must change the 'port' value to match
# your specific Enttec Open DMX USB interface.
# On Windows: 'COMx' (e.g., 'COM3')
# On macOS: '/dev/cu.usbserial-Axxxxx'
# On Linux: '/dev/ttyUSBx'
dmx = controllers.uDMXController('/dev/tty.usbserial-A50285BI')

# Set the starting DMX channel for your light fixture.
# This assumes an RGB light where the channels are consecutive.
# e.g., Channel 1 = Red, Channel 2 = Green, Channel 3 = Blue.
start_channel = 1

# --- Part 2: Mood-to-Color Mapping ---
# A dictionary mapping moods to their corresponding RGB color values (0-255).s
mood_colors = {
    'calm':      (0, 0, 255),    # Deep Blue
    'energetic': (255, 255, 0),  # Yellow
    'angry':     (255, 0, 0),    # Red
    'happy':     (0, 255, 0),    # Green
    'sad':       (0, 0, 128),    # Dark Blue
    'romantic':  (255, 105, 180),# Pink
    'excited':   (255, 165, 0),  # Orange
    'mysterious':(128, 0, 128)   # Purple
}

# --- User Input and DMX Control Loop ---

print("DMX controller ready for mood input.")
print(f"Available moods: {', '.join(mood_colors.keys())}")
print("Type 'exit' or press Ctrl+C to quit.")

try:
    while True:
        user_input = input("Enter a mood: ").lower().strip()

        if user_input == 'exit':
            break

        if user_input in mood_colors:
            rgb_color = mood_colors[user_input]
            
            print(f"Setting lights to '{user_input}' color: RGB{rgb_color}")

            # Set the DMX channels with the new color values
            dmx.set_channel(start_channel, rgb_color[0])
            dmx.set_channel(start_channel + 1, rgb_color[1])
            dmx.set_channel(start_channel + 2, rgb_color[2])
            
            # Send the updated DMX data to the lights
            dmx.send_update()

        else:
            print("Sorry, that mood is not in the list. Please try again.")

except KeyboardInterrupt:
    print("\nQuitting...")

finally:
    dmx.set_channel(start_channel, 0)
    dmx.set_channel(start_channel + 1, 0)
    dmx.set_channel(start_channel + 2, 0)
    dmx.send_update()
    dmx.stop()
    print("DMX controller stopped. Lights turned off.")
