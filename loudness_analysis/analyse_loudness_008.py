import numpy as np
import pandas as pd
import librosa
import sounddevice as sd
import essentia.standard as es
import math
import traceback
from pathlib import Path

# --------- USER CONFIG ----------
SONGS_DIR = Path("songs")  # folder containing your mp3 files
WINDOW_HOP_PAIRS = [
    (1024, 218),
    (2048, 512),
]
OUTPUT_EXCEL = "all_songs_loudness.xlsx"
# --------------------------------

def make_callback(y, sr, window_size, hop_size, channels, results_list):
    rms_extractor = es.RMS()
    loudness_extractor = es.Loudness()

    buffer = np.zeros(0, dtype=np.float32)
    idx = 0

    def callback(outdata, frames, time, status):
        nonlocal buffer, idx
        try:
            start = idx
            end = idx + frames
            chunk = y[start:end]
            idx += frames

            if len(chunk) < frames:
                pad_width = frames - len(chunk)
                chunk = np.pad(chunk, (0, pad_width), mode="constant")

            if channels == 1:
                out = chunk.reshape(-1, 1)
            else:
                out = np.repeat(chunk.reshape(-1, 1), channels, axis=1)
            outdata[:] = out

            # rolling buffer for analysis
            if len(buffer) < window_size:
                buffer = np.concatenate((buffer, chunk.astype(np.float32)))
                if len(buffer) < window_size:
                    frame_for_analysis = np.pad(buffer, (window_size - len(buffer), 0), mode="constant")
                else:
                    frame_for_analysis = buffer[-window_size:]
            else:
                buffer = np.concatenate((buffer, chunk.astype(np.float32)))
                buffer = buffer[-window_size:]
                frame_for_analysis = buffer

            # Essentia RMS & Loudness
            try:
                e_rms = float(rms_extractor(frame_for_analysis))
            except Exception:
                e_rms = float(np.sqrt(np.mean(frame_for_analysis**2)))

            try:
                e_loud = float(loudness_extractor(frame_for_analysis))
            except Exception:
                e_loud = float(20 * math.log10(max(1e-9, np.sqrt(np.mean(frame_for_analysis**2)))))

            # Librosa RMS & loudness(dB)
            lr_rms = float(np.sqrt(np.mean(frame_for_analysis**2)))
            lr_loud_db = float(librosa.amplitude_to_db([lr_rms], ref=1.0)[0])

            time_sec = min(idx, len(y)) / sr
            results_list.append({
                "time_sec": time_sec,
                "essentia_rms": e_rms,
                "essentia_loudness": e_loud,
                "librosa_rms": lr_rms,
                "librosa_loudness_db": lr_loud_db
            })
        except Exception:
            traceback.print_exc()
            raise sd.CallbackStop()
    return callback

all_results = {}

for song_path in SONGS_DIR.glob("*.mp3"):
    print(f"\n🎵 Processing {song_path.name}")
    try:
        y, sr = librosa.load(song_path, sr=None, mono=True)
    except Exception as e:
        print(f"⚠️ Could not load {song_path.name}: {e}")
        continue

    song_key = song_path.stem[:14]  # truncate song name to max 14 chars
    channels = 2

    for window_size, hop_size in WINDOW_HOP_PAIRS:
        print(f"▶ {song_path.name}: win={window_size}, hop={hop_size}")
        results = []
        cb = make_callback(y, sr, window_size, hop_size, channels, results)

        try:
            with sd.OutputStream(samplerate=sr,
                                 channels=channels,
                                 callback=cb,
                                 blocksize=hop_size):
                sd.sleep(int(math.ceil(len(y) / sr * 1000)) + 200)
        except Exception as e:
            print(f"⚠️ Error in {song_path.name}, win={window_size}, hop={hop_size}: {e}")

        print(f"✅ Done: {len(results)} frames")
        sheet_name = f"{song_key}_w{window_size}_h{hop_size}"
        all_results[sheet_name] = pd.DataFrame(results)

# save everything into one Excel file
with pd.ExcelWriter(OUTPUT_EXCEL, engine="openpyxl") as writer:
    for sheet_name, df in all_results.items():
        # ✅ don't reset writer.sheets each time
        safe_sheet = sheet_name[:31]  # Excel max sheet name length = 31
        df.to_excel(writer, sheet_name=safe_sheet, index=False)

print(f"\n💾 All songs saved in {OUTPUT_EXCEL}")
