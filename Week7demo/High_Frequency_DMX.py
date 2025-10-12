"""
High Frequency DMX Controller

This script drives DMX lights in a "high energy mode" (fast strobe, 
rapid hue cycling, high brightness) based on real-time mood and energy data.
"""

import time
import random
from dmx_controller import SimpleDMX



# Utility Functions

def rgb_to_rgbw(rgb_color, brightness=1.0):
    """
    Convert RGB color tuple to RGBW tuple.

    Args:
        rgb_color (tuple): RGB tuple like (255, 0, 0).
        brightness (float): Brightness scaling factor (0.0–1.0).
    Returns:
        (R, G, B, W) as integers in range 0–255.
    """
    r, g, b = rgb_color
    w = min(r, g, b)  # crude white channel
    return (
        int(r * brightness),
        int(g * brightness),
        int(b * brightness),
        int(w * brightness),
    )

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

def energy_to_brightness(energy_level):
    """Map energy level to brightness."""
    energy_map = {
        "high": 1.0,
        "medium": 0.8,
        "low": 0.6
    }
    return energy_map.get(energy_level, 0.7)

def energy_to_strobe_speed(energy_level):
    """Map energy level to strobe speed (seconds between flashes)."""
    speed_map = {
        "high": 0.05,    # Very fast strobe
        "medium": 0.1,   # Medium strobe
        "low": 0.2       # Slower strobe
    }
    return speed_map.get(energy_level, 0.1)

def energy_to_variation_count(energy_level):
    """Map energy level to number of color variations."""
    variation_map = {
        "high": 8,       # Many variations
        "medium": 5,     # Medium variations
        "low": 3         # Few variations
    }
    return variation_map.get(energy_level, 5)

def create_color_variations(base_color, count=5):
    """
    Create variations of a base color for dynamic lighting.
    
    Args:
        base_color (tuple): RGB base color
        count (int): Number of variations to create
    
    Returns:
        List of RGB color tuples
    """
    variations = [base_color]  # Start with original
    r, g, b = base_color
    
    for i in range(count - 1):
        # Create variations by adjusting brightness and hue
        factor = 0.7 + (i * 0.1)  # Brightness factor
        
        # Add some randomness while keeping color character
        r_var = min(255, max(0, int(r * factor + random.randint(-20, 20))))
        g_var = min(255, max(0, int(g * factor + random.randint(-20, 20))))
        b_var = min(255, max(0, int(b * factor + random.randint(-20, 20))))
        
        variations.append((r_var, g_var, b_var))
    
    return variations

# Main DMX Functions

def run_high_frequency_dmx_chunk(dmx, mood_color, energy_level, duration=5.0):
    import time
    def rgb_to_rgbw(rgb_color, brightness=1.0):
        r, g, b = rgb_color
        w = min(r, g, b)
        return (int(r * brightness), int(g * brightness), int(b * brightness), int(w * brightness))
    def energy_to_strobe_speed(energy_level):
        return {"high": 0.05, "medium": 0.1, "low": 0.2}.get(energy_level, 0.1)
    brightness = {"high": 1.0, "medium": 0.8, "low": 0.6}.get(energy_level, 1.0)
    color_variations = [mood_color] * 8 # Customize your ramp here if wanted
    strobe_speed = energy_to_strobe_speed(energy_level)
    start_time = time.time()
    color_index = 0
    while time.time() - start_time < duration:
        rgbw = rgb_to_rgbw(color_variations[color_index % len(color_variations)], brightness)
        dmx.update_lighting(rgbw, hue_speed=1.0)
        time.sleep(strobe_speed)
        color_index += 1

def run_high_frequency_dmx(loudness_db, genre, port="COM4"):
    """
    Legacy function for standalone operation (kept for compatibility).
    Run DMX lights in High Frequency mode (fast strobe).
    """

    # Genre → Palette mapping (legacy)
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
        # Map loudness to brightness
        if loudness_db > -15:
            brightness = 1.0
        elif loudness_db > -25:
            brightness = 0.8
        else:
            brightness = 0.6
            
        print(f"Loudness: {loudness_db:.2f} dB → Brightness: {brightness:.2f}")

        # Infinite loop until user stops
        step = 0
        while True:
            # Rotate or shuffle every few cycles
            if step % 5 == 0:
                palette = palette[1:] + palette[:1]  # rotate
            if step % 10 == 0:
                random.shuffle(palette)

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

# Test function
def test_high_frequency_dmx():
    """Test the high frequency DMX controller."""
    print("Testing High Frequency DMX Controller...")
    
    test_colors = [
        ((255, 0, 0), "high"),    # Red, high energy
        ((0, 255, 0), "medium"),  # Green, medium energy
        ((0, 0, 255), "low"),     # Blue, low energy
        ((255, 255, 0), "high"),  # Yellow, high energy
    ]
    
    for color, energy in test_colors:
        print(f"\nTesting: Color {color}, Energy {energy}")
        run_high_frequency_dmx_chunk(color, energy, duration=2.0)
        time.sleep(0.5)
    
    print("Test complete!")

if __name__ == "__main__":
    # Run test
    test_high_frequency_dmx()








