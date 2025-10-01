import os
import numpy as np
import librosa
from concurrent.futures import ThreadPoolExecutor
import csv

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

def save_moods_to_csv(mood_list, filename):
    with open(filename, mode='w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Chunk Start Time (s)', 'Mood'])
        for timestamp, mood in mood_list:
            writer.writerow([f'{timestamp:.2f}', mood])

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

    csv_filename = os.path.splitext(os.path.basename(filepath))[0] + "_moods.csv"
    save_moods_to_csv(chunk_moods, csv_filename)
    print(f"Saved moods to {csv_filename}")
    return chunk_moods

def process_files_concurrently(filepaths, max_workers=4):
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        results = list(executor.map(process_single_file, filepaths))
    return results

if __name__ == "__main__":
    file_list = input("Enter comma-separated MP3 file paths: ").strip().split(',')
    file_list = [f.strip() for f in file_list if f.strip()]
    results = process_files_concurrently(file_list)
    
    for filepath, moods in zip(file_list, results):
        print(f"\nResults for {filepath}:")
        for ts, mood in moods:
            print(f"{ts:.2f}s - Mood: {mood}")
        print()
