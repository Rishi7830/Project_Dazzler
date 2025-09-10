import librosa
import essentia.standard as es
import numpy as np
import pandas as pd
import os

# -----------------------------
# Config
# -----------------------------
SONGS_FOLDER = "songs"   # folder containing mp3 files

# Window/Hop timings (seconds)
timings = [
    (2.0, 0.5),
    (2.0, 1.0),
    (4.0, 1.0),
    (4.0, 2.0),
    (8.0, 2.0),
    (8.0, 4.0),
    (12.0, 4.0),
    (12.0, 6.0)
]

# Librosa key profiles
major_profile = np.array([6.35,2.23,3.48,2.33,4.38,4.09,
                          2.52,5.19,2.39,3.66,2.29,2.88])
minor_profile = np.array([6.33,2.68,3.52,5.38,2.60,3.53,
                          2.54,4.75,3.98,2.69,3.34,3.17])
major_profile /= major_profile.sum()
minor_profile /= minor_profile.sum()
KEYS = ["C","C#","D","D#","E","F","F#","G","G#","A","A#","B"]

# -----------------------------
# Mode analysis for one song
# -----------------------------
def analyze_mode(y, sr, window_sec, hop_sec):
    window_size = int(window_sec * sr)
    hop_size = int(hop_sec * sr)
    key_extractor = es.KeyExtractor(frameSize=window_size, hopSize=hop_size)

    results = []
    num_frames = int((len(y) - window_size) / hop_size)

    for i in range(num_frames):
        start = i * hop_size
        end = start + window_size
        frame = y[start:end]
        if len(frame) < window_size:
            continue

        # Essentia
        key, scale, strength = key_extractor(frame)

        # Librosa
        chroma = librosa.feature.chroma_cqt(y=frame, sr=sr, hop_length=hop_size)
        chroma_avg = chroma.mean(axis=1)

        major_corr = [np.corrcoef(np.roll(major_profile, k), chroma_avg)[0,1] for k in range(12)]
        minor_corr = [np.corrcoef(np.roll(minor_profile, k), chroma_avg)[0,1] for k in range(12)]

        if max(major_corr) >= max(minor_corr):
            mode_lib = "major"
            key_idx = int(np.argmax(major_corr))
        else:
            mode_lib = "minor"
            key_idx = int(np.argmax(minor_corr))

        key_lib = KEYS[key_idx]

        time_sec = start / sr
        results.append({
            "time_sec": time_sec,
            "essentia_key": key,
            "essentia_mode": scale,
            "essentia_strength": strength,
            "librosa_key": key_lib,
            "librosa_mode": mode_lib
        })

    return pd.DataFrame(results)

# -----------------------------
# Process all songs
# -----------------------------
for file in os.listdir(SONGS_FOLDER):
    if file.endswith(".mp3"):
        song_path = os.path.join(SONGS_FOLDER, file)
        print(f"\n▶ Analyzing {file}")

        # Load audio
        y, sr = librosa.load(song_path, sr=None, mono=True)

        # Excel writer (one file per song)
        output_file = f"mode_results_{os.path.splitext(file)[0]}.xlsx"
        with pd.ExcelWriter(output_file) as writer:
            for window_sec, hop_sec in timings:
                print(f"   → window={window_sec}s, hop={hop_sec}s")
                df = analyze_mode(y, sr, window_sec, hop_sec)
                sheet_name = f"{window_sec:.1f}s_{hop_sec:.1f}s"
                df.to_excel(writer, sheet_name=sheet_name, index=False)

        print(f"✅ Saved results to {output_file}")
