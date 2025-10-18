import math

# ====================================================================
# GENRE COLOR PALETTES
# ====================================================================
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
# FEATURE-BASED COLOR MAPPING
# ====================================================================
def map_features_to_genre_color(loudness: float, tempo: float, genre: str):
    """
    Maps loudness to a smooth RGB color by interpolating between palette colors.
    """
    palette = genre_color_palettes.get(genre, genre_color_palettes["pop"])
    n = len(palette)
    MAX_LOUDNESS = 60.0

    # Clamp loudness
    safe_loudness = max(0.0, min(loudness, MAX_LOUDNESS))

    # Scale loudness to [0, n-1] for interpolation
    pos = (safe_loudness / MAX_LOUDNESS) * (n - 1)
    idx_low = int(pos)
    idx_high = min(idx_low + 1, n - 1)
    t = pos - idx_low  # fractional distance between colors

    r = int((1 - t) * palette[idx_low][0] + t * palette[idx_high][0])
    g = int((1 - t) * palette[idx_low][1] + t * palette[idx_high][1])
    b = int((1 - t) * palette[idx_low][2] + t * palette[idx_high][2])

    return (r, g, b)

def calculate_hue_speed(loudness: float, tempo: float):
    """
    Dynamically calculate the hue cycling speed based on loudness and tempo.
    """
    # Normalize loudness (0-60 dB)
    loud_norm = min(max(loudness / 60.0, 0.0), 1.0)

    # Normalize tempo (60-200 BPM)
    tempo_norm = min(max((tempo - 60) / (200 - 60), 0.0), 1.0)

    # Combine loudness and tempo to determine speed
    hue_speed = 0.5 + loud_norm * 2.0 + tempo_norm * 1.5
    return hue_speed

# ====================================================================
# UTILITY FUNCTIONS
# ====================================================================
def get_energy_level(loudness_db):
    """Map loudness (dB) to energy level for lighting intensity."""
    if loudness_db > 40:
        return "high"
    elif loudness_db > 20:
        return "medium"
    else:
        return "low"

def get_brightness_from_energy(energy_level):
    """Map energy level to brightness value (0.0 - 1.0)."""
    energy_map = {"high": 1.0, "medium": 0.7, "low": 0.4}
    return energy_map.get(energy_level, 0.5)

def get_available_genres():
    """Return list of supported genres."""
    return list(genre_color_palettes.keys())

def rgb_to_hex(rgb):
    """Convert RGB tuple to hex string."""
    return "#{:02x}{:02x}{:02x}".format(*rgb)

def preview_genre_palette(genre):
    """Print color palette for a genre."""
    genre = genre.lower()
    if genre not in genre_color_palettes:
        print(f"Genre '{genre}' not found.")
        return
    palette = genre_color_palettes[genre]
    print(f"\nColor palette for '{genre}':")
    for i, color in enumerate(palette, 1):
        hex_color = rgb_to_hex(color)
        print(f"  {i}. RGB{color} -> {hex_color}")

# ====================================================================
# SELF-TEST
# ====================================================================
if __name__ == "__main__":
    test_genre = "soul"
    preview_genre_palette(test_genre)
    test_loudness_values = [0.0, 11.0, 12.0, 25.0, 36.5, 59.9, 80.0]
    test_tempo = 120

    print("\n=== Testing Loudness-Based Smooth Color Mapping ===")
    for loudness in test_loudness_values:
        mapped_color = map_features_to_genre_color(loudness, test_tempo, test_genre)
        hue_speed = calculate_hue_speed(loudness, test_tempo)
        print(f"Loudness: {loudness:5.1f} dB -> RGB{mapped_color} -> {rgb_to_hex(mapped_color)} | Hue Speed: {hue_speed:.2f}")
