"""
Audio Analyzer Module (File 4)
Combines loudness, mode/key, and tempo data to generate color and hue cycling speed
"""

import numpy as np
from typing import Tuple
# audio_analyzer.py

def process_audio_features(loudness: float, mode: str, key: str, tempo: float) -> Tuple[tuple, float]:
    """
    Process audio features and convert to color and hue cycling speed.
    
    CRITICAL FIX: Overriding tempo-based hue_speed with loudness for responsiveness.
    """
    
    # 1. Generate base color from key and mode
    base_color = key_to_color(key, mode)
    
    # 2. Adjust color saturation/brightness based on loudness
    adjusted_color = adjust_color_by_loudness(base_color, loudness)
    
    L_MIN = 5.0   # The quietest part for a slow-moving light
    L_MAX = 100.0 # The loudest part for max speed (Based on your logs maxing at ~220 dB, 100 is a safe threshold)
    normalized_loudness = np.clip((loudness - L_MIN) / (L_MAX - L_MIN), 0.0, 1.0)
    hue_speed = 0.1 + (normalized_loudness * 1.9) # Range 0.1 (low) to 2.0 (high)
    feature_output = adjusted_color 
    
    return feature_output, float(hue_speed)

def key_to_color(key: str, mode: str) -> tuple:
    """
    Map musical key and mode to RGB color
    
    Args:
        key (str): Musical key
        mode (str): Musical mode
        
    Returns:
        tuple: RGB color (r, g, b)
    """
    
    # Key to hue mapping (0-360 degrees on color wheel)
    key_hues = {
        "C": 0,     # Red
        "C#": 30,   # Red-Orange
        "Db": 30,   # Red-Orange
        "D": 60,    # Yellow
        "D#": 90,   # Yellow-Green
        "Eb": 90,   # Yellow-Green
        "E": 120,   # Green
        "F": 150,   # Green-Cyan
        "F#": 180,  # Cyan
        "Gb": 180,  # Cyan
        "G": 210,   # Cyan-Blue
        "G#": 240,  # Blue
        "Ab": 240,  # Blue
        "A": 270,   # Blue-Magenta
        "A#": 300,  # Magenta
        "Bb": 300,  # Magenta
        "B": 330    # Magenta-Red
    }
    
    hue = key_hues.get(key, 0)  # Default to C (red)
    
    # Adjust saturation and brightness based on mode
    if mode.lower() == "major":
        saturation = 0.8  # Bright and saturated
        brightness = 0.9  # Bright
    elif mode.lower() == "minor":
        saturation = 0.6  # Less saturated
        brightness = 0.6  # Darker
    else:
        saturation = 0.7  # Neutral
        brightness = 0.75
    
    # Convert HSB to RGB
    rgb = hsb_to_rgb(hue, saturation, brightness)
    return rgb

def hsb_to_rgb(hue: float, saturation: float, brightness: float) -> tuple:
    """
    Convert HSB/HSV color to RGB
    
    Args:
        hue (float): Hue in degrees (0-360)
        saturation (float): Saturation (0.0-1.0)
        brightness (float): Brightness/Value (0.0-1.0)
        
    Returns:
        tuple: RGB values (0-255)
    """
    
    import colorsys
    
    # Normalize hue to 0-1
    h = hue / 360.0
    s = saturation
    v = brightness
    
    # Convert to RGB (0-1 range)
    r, g, b = colorsys.hsv_to_rgb(h, s, v)
    
    # Scale to 0-255 range
    return (int(r * 255), int(g * 255), int(b * 255))

def adjust_color_by_loudness(color: tuple, loudness: float) -> tuple:
    """
    Adjust color brightness/intensity based on loudness
    
    Args:
        color (tuple): RGB color tuple
        loudness (float): Loudness in dB
        
    Returns:
        tuple: Adjusted RGB color
    """
    
    r, g, b = color
    
    # Map loudness to brightness multiplier
    # Typical music loudness range: -60 dB (quiet) to -10 dB (loud)
    # Map to brightness multiplier: 0.3 to 1.2
    
    # Normalize loudness to 0-1 range
    loudness_normalized = np.clip((loudness + 60) / 50, 0, 1)
    
    # Brightness multiplier: 0.3 (dark) to 1.2 (bright)
    brightness_mult = 0.3 + (loudness_normalized * 0.9)
    
    # Apply multiplier
    r_adj = int(np.clip(r * brightness_mult, 0, 255))
    g_adj = int(np.clip(g * brightness_mult, 0, 255))
    b_adj = int(np.clip(b * brightness_mult, 0, 255))
    
    return (r_adj, g_adj, b_adj)

def tempo_to_hue_speed(tempo: float) -> float:
    """
    Map tempo (BPM) to hue cycling speed
    
    Args:
        tempo (float): Tempo in BPM
        
    Returns:
        float: Hue cycling speed (0.0-2.0)
    """
    
    # Typical tempo range: 60-180 BPM
    # Map to cycling speed: 0.1 (slow) to 2.0 (fast)
    
    # Normalize tempo to 0-1 range
    tempo_normalized = np.clip((tempo - 60) / 120, 0, 1)
    
    # Speed range: 0.1 to 2.0
    hue_speed = 0.1 + (tempo_normalized * 1.9)
    
    return float(hue_speed)

def get_genre_modifier(mode: str, tempo: float, loudness: float) -> dict:
    """
    Estimate genre characteristics and apply modifiers
    
    Args:
        mode (str): Musical mode
        tempo (float): Tempo in BPM
        loudness (float): Loudness in dB
        
    Returns:
        dict: Genre modifiers for color/speed adjustments
    """
    
    # Simple genre classification based on features
    if tempo > 140 and loudness > -15:
        genre = "electronic/dance"
        color_modifier = 1.2  # More vibrant
        speed_modifier = 1.5  # Faster cycling
    elif tempo < 80 and mode == "minor":
        genre = "ballad/ambient"
        color_modifier = 0.7  # Softer colors
        speed_modifier = 0.5  # Slower cycling
    elif tempo > 120 and mode == "major":
        genre = "pop/rock"
        color_modifier = 1.0  # Standard
        speed_modifier = 1.0  # Standard
    elif tempo < 100 and loudness < -25:
        genre = "classical/acoustic"
        color_modifier = 0.8  # Refined colors
        speed_modifier = 0.7  # Gentle cycling
    else:
        genre = "general"
        color_modifier = 1.0
        speed_modifier = 1.0
    
    return {
        "estimated_genre": genre,
        "color_modifier": color_modifier,
        "speed_modifier": speed_modifier
    }

def process_audio_features_advanced(loudness: float, mode: str, key: str, tempo: float) -> dict:
    """
    Advanced processing with genre detection and modifiers
    
    Args:
        loudness (float): Loudness in dB
        mode (str): Musical mode
        key (str): Musical key
        tempo (float): Tempo in BPM
        
    Returns:
        dict: Extended results with genre info
    """
    
    # Get base color and speed
    base_color, base_speed = process_audio_features(loudness, mode, key, tempo)
    
    # Get genre modifiers
    genre_info = get_genre_modifier(mode, tempo, loudness)
    
    # Apply modifiers
    r, g, b = base_color
    modified_color = (
        int(np.clip(r * genre_info["color_modifier"], 0, 255)),
        int(np.clip(g * genre_info["color_modifier"], 0, 255)),
        int(np.clip(b * genre_info["color_modifier"], 0, 255))
    )
    
    modified_speed = base_speed * genre_info["speed_modifier"]
    
    return {
        "color_rgb": modified_color,
        "hue_speed": float(modified_speed),
        "genre_info": genre_info,
        "original_color": base_color,
        "original_speed": base_speed
    }

# For testing
if __name__ == "__main__":
    # Test the processing
    test_loudness = -20.0  # dB
    test_mode = "major"
    test_key = "G"
    test_tempo = 128.0  # BPM
    
    color, speed = process_audio_features(test_loudness, test_mode, test_key, test_tempo)
    print(f"Color: {color}, Hue Speed: {speed:.2f}")
    
    advanced_result = process_audio_features_advanced(test_loudness, test_mode, test_key, test_tempo)
    print(f"Advanced result: {advanced_result}")
