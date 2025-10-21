import math

# Define genre palettes (MOOD COLORS AND MOOD MAPPING REMOVED)
genre_color_palettes = {
    "classical": [(255, 255, 224), (211, 211, 211), (169, 169, 169), (255, 165, 0), (128, 0, 0)],
    "rock": [(255, 0, 0), (0, 0, 0), (128, 0, 128), (75, 0, 130), (0, 0, 255)],
    "blues": [(0, 255, 255), (128, 128, 128), (255, 255, 255), (255, 255, 0), (255, 165, 0)],
    "hip hop and rap": [(255, 69, 0), (255, 223, 0), (128, 0, 128), (0, 255, 255), (0, 0, 255)],
    "soul": [(128, 0, 128), (255, 192, 203), (0, 0, 255), (165, 42, 42), (255, 165, 0)],
    "indie": [(255, 69, 0), (255, 20, 147), (0, 128, 0), (255, 255, 255), (165, 42, 42)],
    "country": [(255, 165, 0), (255, 255, 224), (255, 0, 0), (165, 42, 42), (0, 128, 0)],
    "gospel": [(255, 255, 255), (139, 69, 19), (160, 82, 45), (128, 0, 128), (0, 128, 0)],
    "jazz": [(0, 0, 255), (255, 140, 0), (128, 128, 128), (255, 255, 255), (128, 0, 128)],
    "folk": [(0, 128, 0), (255, 140, 0), (255, 0, 0), (255, 192, 203), (165, 42, 42)],
    "electronics and dance": [(0, 255, 255), (128, 0, 128), (255, 0, 0), (255, 192, 203), (34, 139, 34)],
    "latin": [(255, 255, 0), (255, 0, 0), (255, 165, 0), (165, 42, 42), (0, 128, 0)],
    "metal": [(0, 0, 0), (139, 0, 0), (128, 0, 128), (105, 105, 105), (165, 42, 42)],
    "pop": [(0, 0, 255), (255, 192, 203), (255, 0, 0), (0, 128, 0), (255, 255, 0)],
    "reggae": [(255, 165, 0), (0, 128, 0), (255, 255, 0), (255, 0, 0), (255, 255, 255)]
}

# ====================================================================
# FEATURE-BASED COLOR MAPPING (LOUDNESS-BASED CYCLE)
# This function is now the central logic for color selection in main.py
# ====================================================================

def map_features_to_genre_color(loudness, tempo, genre):
    """
    Maps music features to a color from the genre's palette based on loudness.
    
    The color changes across the palette based on the current loudness level,
    since the tempo detection was initially unreliable in the short windows.
    """
    
    palette = genre_color_palettes.get(genre, genre_color_palettes["pop"])
    palette_len = len(palette)
    
    # Define a maximum loudness value for normalization. 
    # Max loudness for professional audio is usually around 0 dB, but streamed/uncompressed
    # data often lives in a range (e.g., -60dB to 0dB, but relative loudness is what matters).
    # Using 60.0 dB as a safe, generous max for mapping indices.
    MAX_LOUDNESS = 60.0 
    
    try:
        # Prevent negative loudness values
        safe_loudness = max(0, loudness)
        
        # Calculate the loudness step value for each color in the palette
        # e.g., for 5 colors and 60 max dB, each step is 12 dB.
        loudness_step = MAX_LOUDNESS / palette_len
        
        # Determine the color index by finding which step the loudness falls into
        index = int(safe_loudness / loudness_step)
        
        # Ensure the index is within the valid range [0, palette_len - 1]
        index = min(index, palette_len - 1)
        
    except Exception:
        # Fallback to the first color if any calculation fails
        index = 0
        
    return palette[index]

# ====================================================================
# UTILITY FUNCTIONS (Simplified)
# The unused functions (color_distance, closest_color, map_mood_to_genre_color, etc.)
# have been removed as they are no longer needed for the simplified logic.
# ====================================================================

def get_energy_level(loudness_db):
    """Map loudness (dB) to energy level for lighting intensity."""
    # Assuming the input loudness_db is relative (e.g., max is around 40-50 dB in logs)
    # The logic in main.py passes the raw loudness detected from the chunk.
    # We will keep the thresholds general.
    if loudness_db > 40: # High volume
        return "high"
    elif loudness_db > 20: # Medium volume
        return "medium"
    else:
        return "low"

def get_brightness_from_energy(energy_level):
    """Map energy level to brightness value (0.0 - 1.0)."""
    energy_map = {
        "high": 1.0,
        "medium": 0.7,
        "low": 0.4
    }
    return energy_map.get(energy_level, 0.5)

def get_available_genres():
    """Get list of available genres."""
    return list(genre_color_palettes.keys())

def rgb_to_hex(rgb):
    """Convert RGB tuple to hex string."""
    return "#{:02x}{:02x}{:02x}".format(*rgb)

def preview_genre_palette(genre):
    """Print the color palette for a genre."""
    genre = genre.lower()
    if genre not in genre_color_palettes:
        print(f"Genre '{genre}' not found.")
        return
    
    palette = genre_color_palettes[genre]
    print(f"\nColor palette for '{genre}':")
    for i, color in enumerate(palette, 1):
        hex_color = rgb_to_hex(color)
        print(f"  {i}. RGB{color} -> {hex_color}")

if __name__ == "__main__":
    # Test the new color mapping function logic with sample loudness values
    test_genre = "soul"
    preview_genre_palette(test_genre)

    print("\n=== Testing Loudness-Based Color Mapping ===")
    
    # Loudness mapping steps for 5 colors, 60 MAX_LOUDNESS: 0-11, 12-23, 24-35, 36-47, 48-60
    test_loudness_values = [
        0.0, 11.0, 12.0, 25.0, 36.5, 59.9, 80.0 # Test low, boundary, high, and overflow
    ]
    
    for loudness in test_loudness_values:
        mapped_color = map_features_to_genre_color(loudness=loudness, tempo=0, genre=test_genre)
        print(f"Loudness: {loudness:4.1f} dB -> Mapped Color: RGB{mapped_color} -> {rgb_to_hex(mapped_color)}")
