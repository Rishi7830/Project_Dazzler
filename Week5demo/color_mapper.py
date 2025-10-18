import math

# Define mood colors
mood_color_map = {
    "Pleasure": (255, 215, 0),     # Gold Yellow
    "Excitement": (255, 69, 0),    # Orange Red
    "Arousal": (255, 0, 0),        # Red
    "Distress": (139, 0, 0),       # Dark Red
    "Displeasure": (128, 0, 128),  # Purple
    "Depression": (0, 0, 139),     # Dark Blue
    "Sleepiness": (0, 0, 255),     # Blue
    "Relaxation": (135, 206, 250)  # Light Sky Blue
}

# Define genre palettes based on the study (each color as RGB tuples)
genre_color_palettes = {
    "classical": [(255, 255, 224), (211, 211, 211), (169, 169, 169), (255, 165, 0), (128, 0, 0)],  # White, Yellow, Grey, Orange, Blue
    "rock": [(255, 0, 0), (0, 0, 0), (128, 0, 128), (75, 0, 130), (0, 0, 255)],                    # Red, Black, Purple, Blue, Yellow
    "blues": [(0, 255, 255), (128, 128, 128), (255, 255, 255), (255, 255, 0), (255, 165, 0)],       # Blue, Cyan, Grey, Yellow, Orange
    "hip hop and rap": [(255, 69, 0), (255, 223, 0), (128, 0, 128), (0, 255, 255), (0, 0, 255)],     # Orange, Yellow, Purple, Blue, Yellow
    "soul": [(128, 0, 128), (255, 192, 203), (0, 0, 255), (165, 42, 42), (255, 165, 0)],             # Purple, Pink, Blue, Brown, Orange
    "indie": [(255, 69, 0), (255, 20, 147), (0, 128, 0), (255, 255, 255), (165, 42, 42)],            # Orange, Blue, Pink, Green, Brown
    "country": [(255, 165, 0), (255, 255, 224), (255, 0, 0), (165, 42, 42), (0, 128, 0)],             # Orange, Yellow, Red, Brown, Green
    "gospel": [(255, 255, 255), (139, 69, 19), (160, 82, 45), (128, 0, 128), (0, 128, 0)],           # White, Brown, Brown, Purple, Green
    "jazz": [(0, 0, 255), (255, 140, 0), (128, 128, 128), (255, 255, 255), (128, 0, 128)],           # Blue, Orange, Grey, White, Purple
    "folk": [(0, 128, 0), (255, 140, 0), (255, 0, 0), (255, 192, 203), (165, 42, 42)],                # Green, Orange, Red, Pink, Brown
    "electronics and dance": [(0, 255, 255), (128, 0, 128), (255, 0, 0), (255, 192, 203), (34, 139, 34)], # Cyan, Purple, Red, Pink, Green
    "latin": [(255, 255, 0), (255, 0, 0), (255, 165, 0), (165, 42, 42), (0, 128, 0)],               # Yellow, Red, Orange, Brown, Green
    "metal": [(0, 0, 0), (139, 0, 0), (128, 0, 128), (105, 105, 105), (165, 42, 42)],               # Black, Dark Red, Purple, Grey, Brown
    "pop": [(0, 0, 255), (255, 192, 203), (255, 0, 0), (0, 128, 0), (255, 255, 0)],                 # Blue, Pink, Red, Green, Yellow
    "reggae": [(255, 165, 0), (0, 128, 0), (255, 255, 0), (255, 0, 0), (255, 255, 255)]             # Orange, Green, Yellow, Red, White
}

def color_distance(c1, c2):
    """Calculate Euclidean distance between two RGB colors."""
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(c1, c2)))

def closest_color(target_rgb, palette):
    """Find the closest color from palette to target_rgb."""
    return min(palette, key=lambda color: color_distance(target_rgb, color))

def map_mood_to_genre_color(mood, genre):
    """Map a mood to the closest color in the specified genre's palette."""
    genre = genre.lower()
    
    if genre not in genre_color_palettes:
        print(f"Warning: Genre '{genre}' not recognized. Using 'pop' as default.")
        genre = "pop"
    
    if mood not in mood_color_map:
        print(f"Warning: Mood '{mood}' not recognized. Using 'Relaxation' as default.")
        mood = "Relaxation"
    
    mood_color = mood_color_map[mood]
    palette = genre_color_palettes[genre]
    
    # Find closest color in genre palette
    mapped_color = closest_color(mood_color, palette)
    
    return mapped_color

def rgb_to_hex(rgb):
    """Convert RGB tuple to hex string."""
    return "#{:02x}{:02x}{:02x}".format(*rgb)

def hex_to_rgb(hex_code):
    """Convert hex string to RGB tuple."""
    hex_code = hex_code.lstrip("#")
    return tuple(int(hex_code[i:i+2], 16) for i in (0, 2, 4))

def get_energy_level(loudness_db):
    """Map loudness (dB) to energy level for lighting intensity."""
    if loudness_db > -15:
        return "high"
    elif loudness_db > -25:
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

def get_available_moods():
    """Get list of available moods."""
    return list(mood_color_map.keys())

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

def preview_mood_colors():
    """Print all mood colors."""
    print("\nMood color mapping:")
    for mood, color in mood_color_map.items():
        hex_color = rgb_to_hex(color)
        print(f"  {mood:12s}: RGB{color} -> {hex_color}")

# Test function
def test_mapping():
    """Test the mood to genre color mapping."""
    print("=== Testing Mood to Genre Color Mapping ===")
    
    test_cases = [
        ("Excitement", "rock"),
        ("Relaxation", "jazz"),
        ("Pleasure", "pop"),
        ("Depression", "blues"),
        ("Arousal", "metal")
    ]
    
    for mood, genre in test_cases:
        original_color = mood_color_map[mood]
        mapped_color = map_mood_to_genre_color(mood, genre)
        
        print(f"\n{mood} + {genre}:")
        print(f"  Original mood color: RGB{original_color} -> {rgb_to_hex(original_color)}")
        print(f"  Mapped genre color:  RGB{mapped_color} -> {rgb_to_hex(mapped_color)}")
        print(f"  Color distance: {color_distance(original_color, mapped_color):.2f}")

if __name__ == "__main__":
    # Run tests
    test_mapping()
    print("\n" + "="*50)
    preview_mood_colors()
    print("\n" + "="*50)
    preview_genre_palette("rock")
