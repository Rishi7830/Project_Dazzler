from pydmxcontroller import PyDMXController
import time
import random

# --- Part 1: DMX Setup ---
# Initialize the DMX controller.
# IMPORTANT: You must change the 'port' value to match your specific
# Enttec Open DMX USB interface.
# On Windows: 'COMx' (e.g., 'COM3')
# On macOS: '/dev/cu.usbserial-Axxxxx'
# On Linux: '/dev/ttyUSBx'
try:
    dmx = PyDMXController(port='/dev/ttyUSB0')#need to add the computer port
except Exception as e:
    print(f"Error initializing DMX controller: {e}")
    print("Please check the port name and ensure the device is connected.")
    exit()

# Set the starting DMX channel for your light fixture.
# This assumes an RGB light where the channels are consecutive.
# e.g., Channel 1 = Red, Channel 2 = Green, Channel 3 = Blue.
start_channel = 1 

# --- Part 2: Mood-to-Color Mapping ---
# A dictionary mapping moods to their corresponding RGB color values (0-255).
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

# --- Main Control Loop ---

def get_mood_from_audio():
    """
    This is a placeholder function.
    In your final project, this function will contain your audio analysis logic
    and return a string representing the detected mood.
    """
    # For demonstration, we'll just randomly select a mood from our list
    moods = list(mood_colors.keys())
    return random.choice(moods)

print("DMX controller ready. Simulating mood-based lighting.")
print("Press Ctrl+C to stop.")

try:
    # Continuously check for mood and update lights
    while True:
        current_mood = get_mood_from_audio()
        print(f"Detected mood: {current_mood}")
        
        if current_mood in mood_colors:
            rgb_color = mood_colors[current_mood]

            # Set the DMX channels with the new color values
            dmx.set_channel(start_channel, rgb_color[0])
            dmx.set_channel(start_channel + 1, rgb_color[1])
            dmx.set_channel(start_channel + 2, rgb_color[2])
            
            # Send the updated DMX data to the lights
            dmx.send_update()

        # Wait a few seconds before the next update
        time.sleep(3)

except KeyboardInterrupt:
    print("\nStopping the light show...")

finally:
    dmx.set_channel(start_channel, 0)
    dmx.set_channel(start_channel + 1, 0)
    dmx.set_channel(start_channel + 2, 0)
    dmx.send_update()
    dmx.stop()
    print("DMX controller stopped. Lights turned off.")
