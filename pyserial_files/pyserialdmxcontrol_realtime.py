import serial
import time
import sys
import random

# --- Part 1: DMX Setup ---
def send_dmx(port, channel_data):
    """Sends DMX data over the serial port."""
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

# --- Part 3: Feature Extraction Function ---
def get_current_mood():
    """
    This is an empty function for your feature extraction logic.
    Replace this with your actual code that detects and returns the current mood.
    For now, it will return a random mood to show the lights changing in real-time.
    """
    # Example: Return a random mood from the list
    moods = list(mood_colors.keys())
    return random.choice(moods)

# --- Part 4: Main Real-Time Control Loop ---
if __name__ == "__main__":
    
    # Set the starting DMX channel for your light fixture.
    start_channel = 1
    
    print("DMX controller ready for real-time mood input.")
    print("Press Ctrl+C to quit.")

    try:
        while True:
            # Get the current mood from your feature extraction function
            current_mood = get_current_mood()

            if current_mood in mood_colors:
                rgb_color = mood_colors[current_mood]
                
                print(f"Current mood: '{current_mood}'. Setting lights to RGB{rgb_color}")

                channel_data = {
                    start_channel: rgb_color[0],
                    start_channel + 1: rgb_color[1],
                    start_channel + 2: rgb_color[2],
                    start_channel + 3: 255  # Dimmer channel to full intensity
                }

                if not send_dmx('COM4', channel_data):
                    print("Exiting due to DMX communication error.")
                    break
            else:
                print("Mood not found in color mapping. Please check your feature extraction output.")
            
            # Optional: Add a small delay to control the update speed
            time.sleep(1) # Updates every 1 second

    except KeyboardInterrupt:
        print("\nQuitting...")

    finally:
        # Turn the lights off when the program exits
        send_dmx('COM4', {start_channel + 3: 0})
        print("DMX controller stopped. Lights turned off.")
