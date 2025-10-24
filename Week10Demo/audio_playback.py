# You first need to install the pygame library.
# Open your terminal or command prompt and type:
# pip install pygame

import pygame
import time
import os

def play_audio(file_path):
    """
    Initializes pygame and plays an audio file (like MP3).
    NOTE: This version has no error handling.

    Args:
        file_path (str): The full or relative path to the audio file.
    """
    # Initialize the pygame mixer
    #    time.sleep(3)
    pygame.mixer.init()
    
    # Load the audio file
    pygame.mixer.music.load(file_path)
    
    # Play the audio
    pygame.mixer.music.play()
    
    print(f"Playing: {file_path}")
