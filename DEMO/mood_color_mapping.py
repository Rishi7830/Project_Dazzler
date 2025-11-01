"""
Provides a function to map mood names to RGB color tuples
based on the mood wheel in the MIT "Mood-Based Music" paper (Figure 3-1).
"""

# This dictionary stores the mapping of moods to their RGB color codes.
# Keys are lowercase for easier matching.
MOOD_COLOR_MAP = {
    "distress": (255, 0, 0),       # Red
    "arousal": (255, 165, 0),     # Orange
    "excitement": (255, 200, 0),  # Yellow-orange
    "pleasure": (255, 255, 0),    # Yellow
    "relaxation": (144, 238, 144), # Light green
    "sleepiness": (0, 100, 0),      # Dark green
    "depression": (0, 0, 139),      # Dark blue
    "displeasure": (128, 0, 128)   # Purple
}

def get_mood_color(mood):
    """
    Gets the RGB color tuple (0-255) for a given mood string.

    This function is case-insensitive and strips whitespace.

    Args:
        mood (str): The name of the mood (e.g., "Pleasure", "distress").

    Returns:
        tuple: An (R, G, B) tuple of integers (0-255), or None if the
               mood is not found in the map.
    """
    if not isinstance(mood, str):
        return None
    
    # Process the string to be lowercase and remove leading/trailing spaces
    processed_mood = mood.lower().strip()
    
    # Use .get() to safely retrieve the value.
    # It returns the color if the key exists, and None otherwise.
    return MOOD_COLOR_MAP.get(processed_mood)
