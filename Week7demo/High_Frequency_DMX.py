"""
High Frequency DMX Controller

This script drives DMX lights in a "high energy mode" (fast strobe, 
rapid hue cycling, high brightness). The user selects a music genre,
and the lights change according to pre-defined color palettes.
"""

import time
import random
from pyserial import SimpleDMX

# Utility Functions

def hex_to_rgbw(hex_code, brightness=1.0):
    """
    Convert HEX color code to RGBW tuple.

    Args:
        hex_code (str): Hex string like "#FF0000".
        brightness (float): Brightness scaling factor (0.0–1.0).
    Returns:
        (R, G, B, W) as integers in range 0–255.
    """
    hex_code = hex_code.lstrip("#")
    r, g, b = tuple(int(hex_code[i:i+2], 16) for i in (0, 2, 4))
    w = min(r, g, b)  # crude white channel
    return (
        int(r * brightness),
        int(g * brightness),
        int(b * brightness),
        int(w * brightness),
    )

def rotate_palette(palette):
    """
    Rotate colors in the palette to add variation.
    """
    return palette[1:] + palette[:1]

def shuffle_palette(palette):
    """
    Shuffle palette for randomness.
    """
    shuffled = palette[:]
    random.shuffle(shuffled)
    return shuffled

def brightness_from_loudness(loudness_db):
    """
    Map loudness (dB) to brightness.
    """
    if loudness_db > -15:
        return 1.0
    elif loudness_db > -25:
        return 0.8
    else:
        return 0.6

# Main DMX Runner

def run_high_frequency_dmx(loudness_db, genre, port="COM14"):
    """
    Run DMX lights in High Frequency mode (fast strobe).
    """

    # Genre → Palette mapping
    genre_palettes = {
        "Blues": ["#0000FF", "#CECECE", "#CC6CE7", "#00FFFF", "#000000"],
        "Classical": ["#FFFFFF", "#0000FF", "#00FF00", "#CECECE", "#FFDE59"],
        "Country": ["#00FF00", "#8D6F64", "#FFDE59", "#FE9900", "#0000FF"],
        "Electronica and Dance": ["#00FFFF", "#FFC0CB", "#FFDE59", "#FF0000", "#CC6CE7"],
        "Folk": ["#00FF00", "#8D6F64", "#CECECE", "#FFDE59", "#0000FF"],
        "Gospel": ["#FFFFFF", "#CC6CE7", "#CECECE", "#00FF00", "#000000"],
        "Hip-Hop and Rap": ["#FF0000", "#000000", "#FE9900", "#CC6CE7", "#FFDE59"],
        "Indie": ["#000000", "#CC6CE7", "#00FF00", "#FF0000", "#00FFFF"],
        "Jazz": ["#0000FF", "#CECECE", "#CC6CE7", "#8D6F64", "#FE9900"],
        "Latin": ["#FF0000", "#FFDE59", "#FE9900", "#FFC0CB", "#8D6F64"],
        "Metal": ["#000000", "#FF0000", "#CECECE", "#CC6CE7", "#8D6F64"],
        "Pop": ["#FFC0CB", "#FF0000", "#FE9900", "#FFDE59", "#0000FF"],
        "Reggae": ["#FE9900", "#00FF00", "#FFDE59", "#8D6F64", "#FF0000"],
        "Rock": ["#FF0000", "#000000", "#CC6CE7", "#0000FF", "#CECECE"],
        "Soul": ["#FE9900", "#FFC0CB", "#CC6CE7", "#8D6F64", "#FF0000"]
    }

    # Validate genre
    if genre not in genre_palettes:
        print(f"Genre '{genre}' not found. Defaulting to 'Pop'.")
        genre = "Pop"

    palette = genre_palettes[genre]
    print(f"Selected Genre: {genre}")
    print(f"Palette: {palette}")

    # Init DMX
    dmx = SimpleDMX(port=port, num_channels=8)
    if not dmx.ser:
        print("DMX controller not initialized.")
        return

    dmx.start_broadcast()
    print("DMX broadcast started.")

    try:
        brightness = brightness_from_loudness(loudness_db)
        print(f"Loudness: {loudness_db:.2f} dB → Brightness: {brightness:.2f}")

        # Infinite loop until user stops
        step = 0
        while True:
            # Rotate or shuffle every few cycles
            if step % 5 == 0:
                palette = rotate_palette(palette)
            if step % 10 == 0:
                palette = shuffle_palette(palette)

            for hex_val in palette:
                rgbw = hex_to_rgbw(hex_val, brightness=brightness)

                # Print debug info
                print(f"[STEP {step}] Sending RGBW={rgbw} for {hex_val}")

                # High freq update: strobe speed
                dmx.update_lighting(rgbw, hue_speed=1.0)
                time.sleep(0.15)  # strobe interval

            step += 1

    except KeyboardInterrupt:
        print("Stopping High Frequency DMX...")
    finally:
        dmx.close()
        print("DMX connection closed.")


