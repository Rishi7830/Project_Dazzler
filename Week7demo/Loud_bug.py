import numpy as np
import librosa
import matplotlib.pyplot as plt
import essentia.standard as es

# --- Set parameters ---
AUDIO_PATH = "../Songs_For_demo/Subhanallah.mp3"  # <-- change this!
SR = 44100
WINDOW_SEC = 5.0
HOP_SEC = 2.5
WINDOW_SIZE = int(WINDOW_SEC * SR)
HOP_SIZE = int(HOP_SEC * SR)

# --- Load audio ---
y, sr = librosa.load(AUDIO_PATH, sr=SR, mono=True)
print("Audio loaded. Num samples:", len(y), "Sample rate:", sr)

loudness_extractor = es.Loudness()
loudness_vals_db = []
chunk_times = []

for pos in range(0, len(y), HOP_SIZE):
    chunk = y[pos:pos + WINDOW_SIZE]
    if len(chunk) < WINDOW_SIZE:
        chunk = np.pad(chunk, (0, WINDOW_SIZE - len(chunk)), 'constant')
    raw_loudness = loudness_extractor(chunk)
    # Convert to dB
    if raw_loudness > 0:
        loudness_db = 10 * np.log10(raw_loudness)
    else:
        loudness_db = -80.0
    loudness_db = np.clip(loudness_db, -80, 0)
    loudness_vals_db.append(loudness_db)
    chunk_times.append(pos / sr)
    print(f"Chunk {pos // HOP_SIZE}: Raw loudness={raw_loudness}, dB={loudness_db}")

# --- Plot ---
plt.figure(figsize=(10, 4))
plt.plot(chunk_times, loudness_vals_db, marker="o")
plt.xlabel("Time (s)")
plt.ylabel("Loudness (dB)")
plt.title("Essentia Loudness per Chunk (dB scale)")
plt.grid(True)
plt.savefig("loudness_bug_plot.png", dpi=150)
print("Loudness dB plot saved as loudness_bug_plot.png")
