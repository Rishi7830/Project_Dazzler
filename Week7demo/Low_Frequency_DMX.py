"""
Low Frequency DMX Controller

This script drives DMX lights in a "low energy mode" (smooth fades,
slower transitions, dimmer brightness). The user selects a music genre,
and the lights shift colors gradually for a chill atmosphere.
"""

import time
import random
from pyserial import SimpleDMX

# Utility Functions

def hex_to_rgbw(hex_code, brightness=1.0):
    """
    Convert HEX color code to RGBW tuple.
    """
    hex_code = hex_code.lstrip("#")
    r, g, b = tuple(int(hex_code[i:i+2], 16) for i in (0, 2, 4))
    w = min(r, g, b)
    return (
        int(r * brightness),
        int(g * brightness),
        int(b * brightness),
        int(w * brightness),
    )

def crossfade_colors(rgbw1, rgbw2, steps=20):
    """
    Generate intermediate colors for a smooth crossfade.
    """
    for i in range(steps + 1):
        t = i / steps
        yield tuple(int(a + (b - a) * t) for a, b in zip(rgbw1, rgbw2))

def brightness_from_loudness(loudness_db):
    """
    Map loudness (dB) to brightness (quieter → dimmer).
    """
    if loudness_db > -15:
        return 0.6
    elif loudness_db > -25:
        return 0.5
    else:
        return 0.3

# Main DMX Runner

def run_low_frequency_dmx(loudness_db, genre, port="COM14"):
    """
    Run DMX lights in Low Frequency mode (smooth fading).
    """

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

    if genre not in genre_palettes:
        print(f"Genre '{genre}' not found. Defaulting to 'Classical'.")
        genre = "Classical"

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

        step = 0
        while True:
            # Cycle through palette with crossfades
            for i in range(len(palette)):
                c1 = hex_to_rgbw(palette[i], brightness=brightness)
                c2 = hex_to_rgbw(palette[(i + 1) % len(palette)], brightness=brightness)

                print(f"[STEP {step}] Crossfading {palette[i]} → {palette[(i+1)%len(palette)]}")

                for rgbw in crossfade_colors(c1, c2, steps=30):
                    dmx.update_lighting(rgbw, hue_speed=0.05)  # smooth transition
                    time.sleep(0.1)  # slow cycle

                step += 1

    except KeyboardInterrupt:
        print("Stopping Low Frequency DMX...")
    finally:
        dmx.close()
        print("DMX connection closed.")


# Entry Point

if __name__ == "__main__":
    print("=== Low Frequency DMX Controller ===")
    try:
        loudness_db = float(input("Enter loudness (in dB, e.g., -22): "))
    except ValueError:
        loudness_db = -25.0

    genre = input("Enter genre (Pop, Rock, EDM, HipHop, Classical): ").strip()

    run_low_frequency_dmx(loudness_db, genre)
