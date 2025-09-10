import dmxpy
import time
import sys

# --- Part 1: DMX Setup ---
# Initialize the DMX controller. You must change the 'port' value.
# Find your port: On Windows 'COMx', macOS '/dev/cu.usbserial-Axxxxx', Linux '/dev/ttyUSBx'
try:
    # Port is set to COM4 as requested
    dmx_universe = dmxpy.DMX_init('COM4') 
except Exception as e:
    print(f"Error initializing DMX controller: {e}")
    print("Please check the port name and ensure the device is connected.")
    sys.exit()

# Set the starting DMX channel for your light fixture.
# This assumes a standard 3-channel RGB fixture where channels are consecutive.
start_channel = 1

# --- Part 2: Mood-to-Color Mapping ---
# A dictionary mapping moods to their corresponding RGB color values (0-255).
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
            dmx_universe.set_channel(start_channel, rgb_color[0])
            dmx_universe.set_channel(start_channel + 1, rgb_color[1])
            dmx_universe.set_channel(start_channel + 2, rgb_color[2])
            
            # Send the updated DMX data to the lights
            dmx_universe.render()

        else:
            print("Sorry, that mood is not in the list. Please try again.")

except KeyboardInterrupt:
    print("\nQuitting...")

finally:
    # Ensure lights turn off by setting all channels to 0
    dmx_universe.set_channel(start_channel, 0)
    dmx_universe.set_channel(start_channel + 1, 0)
    dmx_universe.set_channel(start_channel + 2, 0)
    dmx_universe.render()
    dmx_universe.stop()
    print("DMX controller stopped. Lights turned off.")
