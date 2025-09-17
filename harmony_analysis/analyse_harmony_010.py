# analyse_harmony_compare_libs.py
import numpy as np
import pandas as pd
import queue
from threading import Thread
import time
import librosa
import essentia.standard as es
from pathlib import Path

# ----------------------------
# SETTINGS
# ----------------------------
SR = 44100
OUTPUT_EXCEL = "harmony_analysis_compare_libs.xlsx"
SONG_FOLDER = "songs"  # folder with mp3 files

# Two analysis configs (window, hop in seconds)
WINDOW_HOP_CONFIGS = [
    (20.0, 5.0),   # long/stable window
    (10.0, 2.0)    # shorter/more reactive window
]

# ----------------------------
# Essentia Algorithms
# ----------------------------
window = es.Windowing(type="hann")
spectrum = es.Spectrum()
peaks = es.SpectralPeaks(orderBy="magnitude", magnitudeThreshold=0.0001,
                         minFrequency=40, maxFrequency=5000, maxPeaks=60)
hpcp = es.HPCP(size=36, referenceFrequency=440, harmonics=4, bandPreset=True)
key_extractor = es.KeyExtractor(profileType="edma")

def harmony_essentia(frame, sr, frame_size=4096, hop_size=2048):
    """Essentia HPCP + Key"""
    hpcp_frames = []
    for audio_frame in es.FrameGenerator(frame, frameSize=frame_size,
                                         hopSize=hop_size, startFromZero=True):
        spec = spectrum(window(audio_frame))
        freqs, mags = peaks(spec)
        hpcp_frame = hpcp(freqs, mags)
        hpcp_frames.append(hpcp_frame)

    if not hpcp_frames:
        return np.zeros(36), "unknown", "unknown", 0.0, "Complex"

    hpcp_mean = np.mean(hpcp_frames, axis=0)
    key, scale, strength = key_extractor(frame)
    harmony_class = "Simple" if strength >= 0.7 else "Complex"
    return hpcp_mean, key, scale, strength, harmony_class

# ----------------------------
# Librosa Harmony
# ----------------------------
def harmony_librosa(frame, sr, hop_size=2048):
    """Librosa Chroma + Tonnetz"""
    chroma = librosa.feature.chroma_cqt(y=frame, sr=sr, hop_length=hop_size)
    tonnetz = librosa.feature.tonnetz(y=frame, sr=sr)

    chroma_mean = np.mean(chroma, axis=1) if chroma.size else np.zeros(12)
    tonnetz_mean = np.mean(tonnetz, axis=1) if tonnetz.size else np.zeros(6)

    # Classify complexity: if chroma distribution is flat = complex
    if np.max(chroma_mean) - np.min(chroma_mean) > 0.3:
        harmony_class = "Simple"
    else:
        harmony_class = "Complex"

    return chroma_mean, tonnetz_mean, harmony_class

# ----------------------------
# Analysis Thread
# ----------------------------
def analysis_thread_func(analysis_window_sec, analysis_hop_sec,
                         results_queue, audio_queue):
    """Run both Essentia + Librosa in real-time simulation"""
    analysis_buffer = np.zeros(int(analysis_window_sec * SR), dtype=np.float32)
    hop_samples = int(analysis_hop_sec * SR)
    samples_since_last = 0

    while True:
        chunk = audio_queue.get()
        if chunk is None:
            break

        chunk_len = len(chunk)
        analysis_buffer = np.roll(analysis_buffer, -chunk_len)
        analysis_buffer[-chunk_len:] = chunk
        samples_since_last += chunk_len

        if samples_since_last >= hop_samples:
            samples_since_last = 0

            e_hpcp, e_key, e_scale, e_strength, e_class = harmony_essentia(analysis_buffer, SR)
            l_chroma, l_tonnetz, l_class = harmony_librosa(analysis_buffer, SR)

            results_queue.put({
                "time": time.time(),
                # Essentia
                "essentia_key": e_key,
                "essentia_scale": e_scale,
                "essentia_strength": e_strength,
                "essentia_class": e_class,
                "essentia_hpcp": e_hpcp.tolist(),
                # Librosa
                "librosa_chroma": l_chroma.tolist(),
                "librosa_tonnetz": l_tonnetz.tolist(),
                "librosa_class": l_class,
            })

    results_queue.put(None)

# ----------------------------
# Offline Simulation: All Songs
# ----------------------------
def run_offline_songs():
    all_dfs = {}

    for mp3_file in Path(SONG_FOLDER).glob("*.mp3"):
        y, sr = librosa.load(mp3_file, sr=SR, mono=True)
        print(f"\n🎵 Processing {mp3_file.name}")

        for (analysis_window_sec, analysis_hop_sec) in WINDOW_HOP_CONFIGS:
            audio_queue = queue.Queue()
            results_queue = queue.Queue()
            analyst = Thread(target=analysis_thread_func,
                             args=(analysis_window_sec, analysis_hop_sec,
                                   results_queue, audio_queue))
            analyst.start()

            # Feed audio in chunks with pacing
            chunk_size = 2048
            for i in range(0, len(y), chunk_size):
                chunk = y[i:i+chunk_size]
                audio_queue.put(chunk)
                time.sleep(len(chunk)/SR)  # simulate real-time

            audio_queue.put(None)

            # Collect results
            results = []
            while True:
                result = results_queue.get()
                if result is None:
                    break
                result["song"] = mp3_file.stem
                result["window_size_sec"] = analysis_window_sec
                result["hop_size_sec"] = analysis_hop_sec
                results.append(result)

            analyst.join()
            df = pd.DataFrame(results)

            sheet_name = f"{mp3_file.stem} (win{analysis_window_sec}_hop{analysis_hop_sec})"
            all_dfs[sheet_name[:31]] = df  # Excel sheet name limit

            print(f"✅ Finished {mp3_file.name} with win={analysis_window_sec}, hop={analysis_hop_sec}")

    # Save each config as separate sheet
    with pd.ExcelWriter(OUTPUT_EXCEL) as writer:
        for sheet_name, df in all_dfs.items():
            df.to_excel(writer, sheet_name=sheet_name, index=False)

    print(f"\n✅ Saved harmony results for all songs to {OUTPUT_EXCEL}")

# ----------------------------
# MAIN
# ----------------------------
if __name__ == "__main__":
    run_offline_songs()
