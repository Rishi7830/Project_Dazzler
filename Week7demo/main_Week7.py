import time
import numpy as np
import librosa
import os

from mood_color_map import mood_color_map
from Buffer_Manager_Week7 import AudioBuffer
from Mode_Extraction_Week7 import detect_mode_key
from Tempo_detection_week7 import detect_tempo
from Loudness_detection_Week7 import detect_loudness
from Rhythm_Detection_Week7 import extract_rhythm
from Harmony_detection_Week7 import extract_harmony
from KNN_Week7 import preprocess_features, predict_mood

SR = 44100
WINDOW_SEC = 5.0
HOP_SEC = 2.5
WINDOW_SIZE = int(WINDOW_SEC * SR)
HOP_SIZE = int(HOP_SEC * SR)

buffer = AudioBuffer(WINDOW_SIZE)

def rgb_to_ansi_bg(r, g, b):
    return f"\033[48;2;{r};{g};{b}m"

def reset_ansi():
    return "\033[0m"

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def print_color_block(rgb, lines=20, width=80):
    bg_code = rgb_to_ansi_bg(*rgb)
    reset_code = reset_ansi()
    clear_screen()
    # Print a block of color
    for _ in range(lines):
        print(f"{bg_code}{' ' * width}{reset_code}")

def print_mood_info(mood, rgb):
    r, g, b = rgb
    print(f"Mood: {mood:<12s} RGB: ({r:3d}, {g:3d}, {b:3d})")

def countdown():
    for i in [1, 2, 3]:
        clear_screen()
        print(f"{i}")
        time.sleep(1)
    clear_screen()
    print("Start playing your song NOW!")

def audio_source_from_mp3(file_path):
    y, sr = librosa.load(file_path, sr=SR, mono=True)
    print(f"Loaded {file_path} ({len(y)/sr:.2f} seconds of audio)")
    pos = 0
    while pos < len(y):
        chunk = y[pos:pos + HOP_SIZE]
        if len(chunk) < HOP_SIZE:
            chunk = np.pad(chunk, (0, HOP_SIZE - len(chunk)), 'constant')
        yield chunk.astype(np.float32)
        pos += HOP_SIZE

def run_real_time_processing(mp3_path):
    source = audio_source_from_mp3(mp3_path)
    start_time = time.time()
    
    for chunk in source:
        buffer.update(chunk)
        audio_win = buffer.get_window()

        mode, key = detect_mode_key(audio_win)
        tempo = detect_tempo(audio_win)
        loudness = detect_loudness(audio_win)
        bpm, rhythm_index = extract_rhythm(audio_win)
        _, _, _, _, harmony_class = extract_harmony(audio_win)

        features = preprocess_features(mode, key, tempo, loudness, rhythm_index, harmony_class)
        mood = predict_mood(features)

        color = mood_color_map.get(mood, (255, 255, 255))
        print_color_block(color)
        print_mood_info(mood, color)

        elapsed = time.time() - start_time
        remaining = max(0, (len(buffer.buffer) / SR) - elapsed)
        time
