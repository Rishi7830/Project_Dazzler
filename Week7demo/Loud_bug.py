import numpy as np
import librosa
import matplotlib.pyplot as plt

from Buffer_Manager_Week7 import AudioBuffer
from Loudness_detection_Week7 import detect_loudness

# --- Set your parameters here ---
AUDIO_PATH = "your_audio_file.mp3"  # change to your local file
SR = 44100
WINDOW_SEC = 5.0
HOP_SEC = 2.5
WINDOW_SIZE = int(WINDOW_SEC * SR)
HOP_SIZE = int(HOP_SEC * SR)

# --- Load your audio file using librosa ---
y, sr = librosa.load(AUDIO_PATH, sr=SR, mono=True)
print("Audio loaded. Num samples:", len(y), "Sample rate:", sr)

# --- Initialize your buffer manager, loudness tracking arrays ---
buffer = AudioBuffer(WINDOW_SIZE)
loudness_vals = []
chunk_times = []

# --- Walk through the audio, chunk by chunk, using your buffer logic ---
for pos in range(0, len(y), HOP_SIZE):
    chunk = y[pos:pos + HOP_SIZE]
    if len(chunk) < HOP_SIZE:
        chunk = np.pad(chunk, (0, HOP_SIZE - len(chunk)), "constant")
    buffer.update(chunk)  # use your class!
    window = buffer.get_window()
    loudness = detect_loudness(window)
    loudness_vals.append(loudness)
    chunk_times.append(pos / sr)

# --- Plot the loudness profile ---
plt.figure(figsize=(10, 4))
plt.plot(chunk_times, loudness_vals, marker="o")
plt.xlabel("Time (s)")
plt.ylabel("Loudness (dB)")
plt.title("Chunk-wise Loudness using Dazzler Buffer Manager")
plt.grid(True)
plt.show()
