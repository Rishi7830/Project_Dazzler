import time
import tkinter as tk
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
root = tk.Tk()
root.geometry('400x400')
root.title('Real-Time Mood Color')

def update_color(rgb):
    r, g, b = rgb
    color_hex = f'#{r:02x}{g:02x}{b:02x}'
    root.configure(bg=color_hex)
    root.update()

# Countdown colors: red, orange, yellow
countdown_colors = [(255, 0, 0), (255, 165, 0), (255, 255, 0)]

def countdown():
    for i, color in enumerate(reversed(countdown_colors), start=1):
        update_color(color)
        print(f"Countdown: {4 - i}")
        time.sleep(1)

def audio_source():
    import numpy as np
    while True:
        # Replace this with your real audio source yielding HOP_SIZE length numpy arrays
        yield np.random.uniform(-1, 1, HOP_SIZE).astype('float32')

def run_real_time_processing():
    for chunk in audio_source():
        buffer.update(chunk)
        audio_window = buffer.get_window()

        mode, key = detect_mode_key(audio_window)
        tempo = detect_tempo(audio_window)
        loudness = detect_loudness(audio_window)
        bpm, rhythm_index = extract_rhythm(audio_window)
        _, _, _, _, harmony_class = extract_harmony(audio_window)

        features = preprocess_features(mode, key, tempo, loudness, rhythm_index, harmony_class)
        mood = predict_mood(features)

        color = mood_color_map.get(mood, (255, 255, 255))  # default white
        update_color(color)

        time.sleep(HOP_SEC)

if __name__ == '__main__':
    countdown()
    run_real_time_processing()
    root.mainloop()
