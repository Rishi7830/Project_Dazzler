import librosa
import essentia.standard as es
import numpy as np
import pandas as pd
import time
import os

# -----------------------------
# Config
# -----------------------------
SONG_FOLDER = "songs"
CHUNK_DURATION = 2.0   # seconds per step
OUTPUT_FILE = "tempo_all_songs.xlsx"

# Window/hop configs (samples at 44.1kHz)
WINDOW_HOP_CONFIGS = [
    (1024, 128),
    (1024, 256),
    (2048, 256),
    (2048, 512),
    (4096, 512),
    (4096, 1024),
    (8192, 1024),
    (8192, 2048),
]

# -----------------------------
# Essentia Tempo Extractor
# -----------------------------
essentia_tempo = es.RhythmExtractor2013(method="multifeature")

# -----------------------------
# Excel Writer (multi-sheet)
# -----------------------------
with pd.ExcelWriter(OUTPUT_FILE, engine="openpyxl") as writer:

    # Loop over all mp3 files in folder
    for filename in os.listdir(SONG_FOLDER):
        if not filename.lower().endswith(".mp3"):
            continue

        song_path = os.path.join(SONG_FOLDER, filename)
        song_name = os.path.splitext(filename)[0]
        print(f"\n🎵 Processing song: {song_name}")

        # Load audio
        y, sr = librosa.load(song_path, sr=None, mono=True)
        total_duration = librosa.get_duration(y=y, sr=sr)

        # Loop over all configs
        for window_size, hop_size in WINDOW_HOP_CONFIGS:
            print(f"   ▶ Config: window={window_size}, hop={hop_size}")

            num_chunks = int(total_duration // CHUNK_DURATION)
            results = []

            for i in range(num_chunks):
                start_sample = int(i * CHUNK_DURATION * sr)
                end_sample = int((i + 1) * CHUNK_DURATION * sr)
                chunk = y[start_sample:end_sample]

                if len(chunk) == 0:
                    continue

                # ---- Librosa local tempo ----
                onset_env = librosa.onset.onset_strength(
                    y=chunk, sr=sr, hop_length=hop_size, n_fft=window_size
                )
                tempo_local = librosa.beat.tempo(
                    onset_envelope=onset_env,
                    sr=sr,
                    hop_length=hop_size,
                    aggregate=None,
                )
                tempo_librosa_val = float(np.median(tempo_local)) if tempo_local.size > 0 else 0.0

                # ---- Essentia tempo ----
                bpm, beats, beats_confidence, _, _ = essentia_tempo(chunk)
                tempo_essentia_val = float(bpm)

                # ---- Store result ----
                timestamp = i * CHUNK_DURATION
                results.append({
                    "Time (s)": timestamp,
                    "Librosa BPM": tempo_librosa_val,
                    "Essentia BPM": tempo_essentia_val
                })

                # ---- Real-time pacing ----
                time.sleep(CHUNK_DURATION)  # matches wall-clock time

            # -----------------------------
            # Save results to a sheet
            # -----------------------------
            df = pd.DataFrame(results)

            # Convert samples → ms for naming
            win_time_ms = round((window_size / sr) * 1000, 1)
            hop_time_ms = round((hop_size / sr) * 1000, 1)

            sheet_name = f"{song_name[:20]}_{win_time_ms}ms,{hop_time_ms}ms"
            df.to_excel(writer, sheet_name=sheet_name, index=False)

print(f"\n✅ All songs processed. Results saved in {OUTPUT_FILE}")
