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
    "gospel": [(255, 255, 255), (139, 69, 19), (160, 82, 45)],                                       # White, Brown
    "jazz": [(0, 0, 255), (255, 140, 0), (128, 128, 128), (255, 255, 255)],                           # Blue, Orange, Purple, Grey
    "folk": [(0, 128, 0), (255, 140, 0), (255, 0, 0), (255, 192, 203), (0, 128, 0)],                  # Green, Orange, Red, Pink, Green
    "electronics and dance": [(0, 255, 255), (128, 0, 128), (255, 0, 0), (255, 192, 203), (34, 139, 34)], # Cyan, Purple, Red, Pink, Green
    "latin": [(255, 255, 0), (255, 0, 0), (165, 42, 42), (0, 128, 0)],                               # Yellow, Orange, Red, Brown, Green
    "metal": [(0, 0, 0), (139, 0, 139), (128, 0, 128), (105, 105, 105), (165, 42, 42)],               # Black, Red, Purple, Grey, Brown
    "pop": [(0, 0, 255), (255, 192, 203), (255, 105, 180), (0, 128, 0), (255, 255, 0)],               # Blue, Pink, Red, Green, Yellow
    "reggae": [(255, 165, 0), (0, 128, 0), (255, 255, 0), (255, 0, 0), (255, 255, 255)]               # Orange, Green, Yellow, Red, White
}

def color_distance(c1, c2):
    # Euclidean distance between two RGB colors
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(c1, c2)))

def closest_color(target_rgb, palette):
    # Find the closest color from palette to target_rgb
    return min(palette, key=lambda color: color_distance(target_rgb, color))

def map_mood_to_genre_color(mood, genre):
    genre = genre.lower()
    if genre not in genre_color_palettes:
        raise ValueError(f"Genre '{genre}' not recognized. Please use a valid genre.")
    mood_color = mood_color_map.get(mood)
    if not mood_color:
        raise ValueError(f"Mood '{mood}' not recognized. Please use a valid mood.")
    palette = genre_color_palettes[genre]
    return closest_color(mood_color, palette)

# Example usage:
if __name__ == "__main__":
    # User selects genre once at start
    user_genre = input("Enter the genre of the song: ").strip().lower()

    # Simulated mood chunks (5s each)
    moods_in_chunks = ["Pleasure", "Excitement", "Distress", "Relaxation", "Sleepiness"]

    for i, mood in enumerate(moods_in_chunks):
        mapped_color = map_mood_to_genre_color(mood, user_genre)
        print(f"Chunk {i*5} to {i*5+5}s: Mood '{mood}' maps to color {mapped_color} for genre '{user_genre}'")
