import os
import numpy as np
import librosa
from concurrent.futures import ThreadPoolExecutor

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

def process_single_file(filepath):
    print(f"Processing {filepath}...")
    y, sr = librosa.load(filepath, sr=SR, mono=True)
    buffer = AudioBuffer(WINDOW_SIZE)
    chunk_moods = []
    
    pos = 0
    while pos < len(y):
        chunk = y[pos:pos + HOP_SIZE]
        if len(chunk) < HOP_SIZE:
            chunk = np.pad(chunk, (0, HOP_SIZE - len(chunk)), 'constant')
        buffer.update(chunk)
        audio_win = buffer.get_window()

        mode, key = detect_mode_key(audio_win)
        tempo = detect_tempo(audio_win)
        loudness = detect_loudness(audio_win)
        bpm, rhythm_index = extract_rhythm(audio_win)
        _, _, _, _, harmony_class = extract_harmony(audio_win)

        features = preprocess_features(mode, key, tempo, loudness, rhythm_index, harmony_class)
        mood = predict_mood(features)

        timestamp = pos / SR
        chunk_moods.append((timestamp, mood))
        pos += HOP_SIZE
    
    print(f"Finished {filepath}. Moods and timestamps:")
    for ts, mood in chunk_moods:
        print(f"{ts:.2f}s: {mood}")
    
    return chunk_moods

def process_files_concurrently(filepaths, max_workers=4):
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        results = list(executor.map(process_single_file, filepaths))
    return results

if __name__ == '__main__':
    # Example usage, replace with your actual MP3 paths
    file_list = [
        "path/to/song1.mp3",
        "path/to/song2.mp3",
        # add more Mp3 file paths here
    ]
    results = process_files_concurrently(file_list)

    for file, moods in zip(file_list, results):
        print(f"\nResults for {file}:")
        for ts, mood in moods:
            print(f"{ts:.2f} s - Mood: {mood}")
        print()
