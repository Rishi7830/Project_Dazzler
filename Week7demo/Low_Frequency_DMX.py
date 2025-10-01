"""
Low Frequency DMX Controller

This script drives DMX lights in a "low energy mode" (smooth fades,
slower transitions, dimmer brightness) based on real-time mood and energy data.
"""

import time
import random
from pyserial import SimpleDMX
import serial

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

def energy_to_brightness(energy_level):
    """Map energy level to brightness (low energy = dimmer)."""
    energy_map = {
        "high": 0.8,     # Moderate brightness for low-freq mode
        "medium": 0.6,   # Medium brightness
        "low": 0.4       # Low brightness
    }
    return energy_map.get(energy_level, 0.5)

def energy_to_fade_speed(energy_level):
    """Map energy level to fade transition speed."""
    speed_map = {
        "high": 0.05,    # Faster transitions
        "medium": 0.1,   # Medium transitions
        "low": 0.2       # Slower, more relaxed transitions
    }
    return speed_map.get(energy_level, 0.1)

def energy_to_fade_steps(energy_level):
    """Map energy level to number of fade steps (smoothness)."""
    steps_map = {
        "high": 15,      # Fewer steps = faster transitions
        "medium": 25,    # Medium smoothness
        "low": 40        # More steps = smoother, slower transitions
    }
    return steps_map.get(energy_level, 25)

def create_ambient_colors(base_color, count=3):
    """
    Create ambient color variations for smooth transitions.
    
    Args:
        base_color (tuple): RGB base color
        count (int): Number of ambient colors to create
    
    Returns:
        List of RGB color tuples
    """
    colors = [base_color]  # Start with original
    r, g, b = base_color
    
    # Create warmer and cooler variations
    for i in range(1, count):
        factor = 0.8 + (i * 0.1)  # Brightness variation
        
        # Create subtle variations
        if i % 2 == 0:  # Warmer tones
            r_var = min(255, int(r * factor + 10))
            g_var = max(0, int(g * factor - 5))
            b_var = max(0, int(b * factor - 10))
        else:  # Cooler tones
            r_var = max(0, int(r * factor - 10))
            g_var = max(0, int(g * factor - 5))
            b_var = min(255, int(b * factor + 10))
        
        colors.append((r_var, g_var, b_var))
    
    return colors

# Main DMX Functions

def run_low_frequency_dmx_chunk(mood_color, energy_level, port="COM14", duration=5.0):
    """
    Run DMX lights for a single chunk (5 seconds) in Low Frequency mode.
    
    Args:
        mood_color (tuple): RGB color tuple for the mood
        energy_level (str): Energy level ("high", "medium", "low")
        port (str): DMX serial port
        duration (float): Duration to run lights (seconds)
    """
    try:
        # Initialize DMX
        dmx = SimpleDMX(port=port, num_channels=8)
        if not dmx.ser:
            print(f"Warning: DMX controller not initialized on {port}")
            return
        
        dmx.start_broadcast()
        
        # Get parameters based on energy level
        brightness = energy_to_brightness(energy_level)
        fade_speed = energy_to_fade_speed(energy_level)
        fade_steps = energy_to_fade_steps(energy_level)
        
        # Create ambient color variations
        ambient_colors = create_ambient_colors(mood_color, 3)
        
        print(f"Low-freq DMX: Color {mood_color}, Energy {energy_level}, Brightness {brightness:.2f}")
        
        start_time = time.time()
        color_index = 0
        
        while time.time() - start_time < duration:
            # Get current and next colors for crossfading
            current_color = ambient_colors[color_index % len(ambient_colors)]
            next_color = ambient_colors[(color_index + 1) % len(ambient_colors)]
            
            # Convert to RGBW
            current_rgbw = rgb_to_rgbw(current_color, brightness)
            next_rgbw = rgb_to_rgbw(next_color, brightness)
            
            # Perform crossfade
            for fade_color in crossfade_colors(current_rgbw, next_rgbw, fade_steps):
                if time.time() - start_time >= duration:
                    break
                
                # Send to DMX
                if dmx.ser and dmx.ser.is_open:
                    try:
                        dmx.update_lighting(fade_color, hue_speed=0.3)
                    except serial.SerialTimeoutException:
                        print("DMX write timeout, skipping frame")
                    except Exception as e:
                        print(f"DMX write error: {e}")
                
                # Wait for fade step
                time.sleep(fade_speed)
            
            # Move to next color
            color_index += 1
        
        dmx.close()
        
    except Exception as e:
        print(f"Low frequency DMX error: {e}")

def run_low_frequency_dmx(loudness_db, genre, port="COM14"):
    """
    Legacy function for standalone operation (kept for compatibility).
    Run DMX lights in Low Frequency mode (smooth fading).
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
        print(f"Genre '{genre}' not found. Defaulting to 'Jazz'.")
        genre = "Jazz"

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
        # Map loudness to brightness (quieter → dimmer)
        if loudness_db > -15:
            brightness = 0.6
        elif loudness_db > -25:
            brightness = 0.5
        else:
            brightness = 0.3
            
        print(f"Loudness: {loudness_db:.2f} dB → Brightness: {brightness:.2f}")

        # Continuous smooth fading
        step = 0
        while True:
            # Cycle through palette colors
            for i in range(len(palette)):
                current_hex = palette[i]
                next_hex = palette[(i + 1) % len(palette)]

                # Convert to RGBW
                current_rgbw = hex_to_rgbw(current_hex, brightness)
                next_rgbw = hex_to_rgbw(next_hex, brightness)

                print(f"[STEP {step}] Fading from {current_hex} to {next_hex}")

                # Smooth crossfade (30 steps)
                for fade_color in crossfade_colors(current_rgbw, next_rgbw, steps=30):
                    dmx.update_lighting(fade_color, hue_speed=0.3)
                    time.sleep(0.15)  # Gentle transition

                step += 1

    except KeyboardInterrupt:
        print("Stopping Low Frequency DMX...")
    finally:
        dmx.close()
        print("DMX connection closed.")

# Test function
def test_low_frequency_dmx():
    """Test the low frequency DMX controller."""
    print("Testing Low Frequency DMX Controller...")
    
    test_colors = [
        ((255, 0, 0), "high"),    # Red, high energy
        ((0, 255, 0), "medium"),  # Green, medium energy
        ((0, 0, 255), "low"),     # Blue, low energy
        ((135, 206, 250), "low"), # Light blue (relaxation), low energy
    ]
    
    for color, energy in test_colors:
        print(f"\nTesting: Color {color}, Energy {energy}")
        run_low_frequency_dmx_chunk(color, energy, duration=3.0)
        time.sleep(0.5)
    
    print("Test complete!")

if __name__ == "__main__":
    # Run test
    test_low_frequency_dmx()
