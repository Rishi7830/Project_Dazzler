import numpy as np
import librosa
import matplotlib.pyplot as plt
from Loudness_detection_Week7 import detect_loudness

# -- Settings --
AUDIO_PATH = "../Songs_For_Demo/Subhanallah.mp3"
SR = 44100
WINDOW_SEC = 5.0
HOP_SEC = 2.5
WINDOW_SIZE = int(WINDOW_SEC * SR)
HOP_SIZE = int(HOP_SEC * SR)

# -- Load Audio --
y, sr = librosa.load(AUDIO_PATH, sr=SR, mono=True)
print("Audio loaded. Num samples:", len(y), "Sample rate:", sr)

loudness_vals = []
chunk_times = []

# -- Simple Windowed Processing --
for pos in range(0, len(y) - WINDOW_SIZE + 1, HOP_SIZE):
    windowed_chunk = y[pos:pos+WINDOW_SIZE]
    loudness = detect_loudness(windowed_chunk)
    loudness_vals.append(loudness)
    chunk_times.append(pos / sr)

# For last partial window (optional):
if pos + WINDOW_SIZE < len(y):
    windowed_chunk = np.pad(y[pos:], (0, WINDOW_SIZE - len(y[pos:])), "constant")
    loudness = detect_loudness(windowed_chunk)
    loudness_vals.append(loudness)
    chunk_times.append(pos / sr)

# -- Plot Loudness Profile --
plt.figure(figsize=(10, 4))
plt.plot(chunk_times, loudness_vals, marker="o")
plt.xlabel("Time (s)")
plt.ylabel("Loudness (dB)")
plt.title("Chunk-wise Loudness (Direct Windowing)")
plt.grid(True)
plt.savefig("loudness_direct_plot.png", dpi=150)
print("Plot saved as 'loudness_direct_plot.png'")
