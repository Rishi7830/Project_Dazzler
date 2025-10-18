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
# ====================================================================

def map_features_to_genre_color(loudness, tempo, genre):
    """
    Maps music features to a color from the genre's palette based on loudness.
    
    The color changes across the palette based on the current loudness level.
    NOTE: Loudness is expected to be in negative dBFS (e.g., -60.0 to 0.0).
    """
    
    palette = genre_color_palettes.get(genre, genre_color_palettes["pop"])
    palette_len = len(palette)
    
    # Define the dB range that maps to the color indices
    # We define a common range for music: -50dB (very quiet) to -5dB (loudest peak)
    QUIETEST_DB = -50.0 
    LOUDEST_DB = -5.0   
    
    try:
        # 1. Clip the incoming loudness to the defined range
        clipped_loudness = max(QUIETEST_DB, min(LOUDEST_DB, loudness))

        # 2. Normalize the clipped loudness to a 0.0 to 1.0 range
        # We shift the negative range to a positive scale (0=quietest, 1=loudest)
        loudness_range = LOUDEST_DB - QUIETEST_DB # Example: -5 - (-50) = 45.0
        normalized_value = (clipped_loudness - QUIETEST_DB) / loudness_range
        
        # 3. Scale the normalized value to the palette index range [0, palette_len - 1]
        index = int(normalized_value * (palette_len - 1))
        
        # Ensure the index is within the valid range
        index = min(index, palette_len - 1)
            
    except Exception as e:
        print(f"[ERR] Color mapping logic failed: {e}")
        # Fallback to the first color if any calculation fails
        index = 0
            
    return palette[index]

# ====================================================================
# UTILITY FUNCTIONS 
# ====================================================================

def get_energy_level(loudness_db):
    """
    Map loudness (dB) to an energy level. 
    NOTE: This function needs to use the same dB range definition as the mapper.
    """
    # Use thresholds consistent with the -50.0 to -5.0 dBFS range
    if loudness_db > -10.0: 
        return "high"
    elif loudness_db > -25.0: 
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
    # Test the new color mapping logic with realistic negative loudness values
    test_genre = "soul"
    preview_genre_palette(test_genre)

    print("\n=== Testing Loudness-Based Color Mapping (Negative dB) ===")
    
    # Range is -50.0 to -5.0. 5 colors means steps are 45/4 = 11.25 apart (approx)
    test_loudness_values = [
        -60.0, # Too quiet -> maps to index 0
        -48.0, # Quiet -> maps to index 0
        -30.0, # Medium-Quiet -> maps to index 1 or 2
        -15.0, # Medium-Loud -> maps to index 3
        -6.0,  # Loud -> maps to index 4
        0.0    # Too loud -> maps to index 4
    ]
    
    for loudness in test_loudness_values:
        # Note: Tempo is passed but unused in this version
        mapped_color = map_features_to_genre_color(loudness=loudness, tempo=0, genre=test_genre)
        print(f"Loudness: {loudness:5.1f} dB -> Mapped Color: RGB{mapped_color} -> Index:{genre_color_palettes[test_genre].index(mapped_color)}")
