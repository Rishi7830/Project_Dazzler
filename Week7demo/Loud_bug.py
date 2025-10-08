import numpy as np
import librosa
import matplotlib.pyplot as plt

AUDIO_PATH = "..//Songs_For_Demo/Subhanallah.mp3"   # <-- CHANGE to your filename!
SR = 44100
WINDOW_SEC = 5.0
HOP_SEC = 2.5
WINDOW_SIZE = int(WINDOW_SEC * SR)
HOP_SIZE = int(HOP_SEC * SR)

def rms_db(chunk):
    rms = np.sqrt(np.mean(chunk**2))
    if rms > 0:
        return 20 * np.log10(rms)
    else:
        return -80.0

y, sr = librosa.load(AUDIO_PATH, sr=SR, mono=True)
print("Audio loaded. Num samples:", len(y), "Sample rate:", sr)

loudness_vals_db = []
chunk_times = []

for pos in range(0, len(y), HOP_SIZE):
    chunk = y[pos:pos+WINDOW_SIZE]
    if len(chunk) < WINDOW_SIZE:
        chunk = np.pad(chunk, (0, WINDOW_SIZE-len(chunk)), 'constant')
    loudness_db = rms_db(chunk)
    loudness_vals_db.append(loudness_db)
    chunk_times.append(pos/sr)
    print(f"Chunk @ {pos/sr:.2f}s: RMS dB={loudness_db}")

plt.figure(figsize=(10,4))
plt.plot(chunk_times, loudness_vals_db, marker="o")
plt.xlabel("Time (s)")
plt.ylabel("Average RMS Loudness (dB)")
plt.title("Chunk-wise RMS Loudness (dB, window-normalized)")
plt.grid(True)
plt.savefig("rms_loudness_plot.png", dpi=150)
print("Saved plot to rms_loudness_plot.png")
