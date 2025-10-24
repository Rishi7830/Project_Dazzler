#!/usr/bin/env python3
"""
Real-time-style rhythm extraction for all songs in ./songs

- Two window/hop timings (default: 5s/2.5s and 10s/5s)
- Uses both Essentia (RhythmExtractor2013) and Librosa for features
- Simulates real-time by sleeping hop_seconds between windows
- Saves one Excel workbook with one sheet per song+window/hop
"""
import time
from pathlib import Path
import traceback

import numpy as np
import pandas as pd
import librosa
import essentia.standard as es

# ---------------- USER CONFIG ----------------
SONGS_DIR = Path("C:/KAVERI/NUS/CDE3301 Dazzler/test_data/mp3")          # folder containing your mp3/wav files
OUTPUT_EXCEL = "all_songs_rhythm_realtime.xlsx"

# choose two window/hop timings (seconds)
WINDOW_HOP_PAIRS_SEC = [
    (5.0, 2.5),   # window = 5s, hop = 2.5s (50% overlap)
    (10.0, 5.0),  # window = 10s, hop = 5s (50% overlap)
]

SIMULATE_REALTIME = True   # if True, sleep hop_seconds between windows (makes runtime ≈ audio length)
VERBOSE = True             # print a short status per window
# ----------------------------------------------

# initialize Essentia extractor once (faster)
rhythm_extractor = es.RhythmExtractor2013(method="multifeature")


# ----- helper utilities -----
def safe_scalar(x, default=0.0):
    """Return a scalar float from x (array/list/scalar)."""
    try:
        if x is None:
            return float(default)
        a = np.asarray(x)
        if a.size == 0:
            return float(default)
        # take mean if multiple values
        return float(np.mean(a))
    except Exception:
        return float(default)


def safe_var(arr, default=0.0):
    try:
        a = np.asarray(arr)
        if a.size <= 1:
            return float(default)
        return float(np.var(a))
    except Exception:
        return float(default)


def ts_stability_from_intervals(intervals):
    """Normalized time-signature stability from beat intervals."""
    if intervals is None or len(intervals) <= 1:
        return 0.0
    mu = np.mean(intervals)
    sd = np.std(intervals)
    # stability: 1 when sd==0, decreasing as sd increases
    val = 1.0 - (sd / (mu + 1e-9))
    # clamp 0..1
    return float(max(0.0, min(1.0, val)))


# ----- core per-window analysis -----
def analyze_frame_both(frame, sr):
    """
    Compute rhythm features on a fixed-length audio frame (numpy array).
    Returns dict with Essentia + Librosa metrics and rhythm indices.
    """

    # --- Librosa-based measures (used also to compute beat times / intervals) ---
    try:
        # onset envelope for the window
        onset_env = librosa.onset.onset_strength(y=frame, sr=sr)
        # tempo and beat positions (frames)
        # beat_track returns tempo (float or array) and beat frames
        tempo_lib, beat_frames = librosa.beat.beat_track(y=frame, sr=sr, onset_envelope=onset_env)
        tempo_lib = safe_scalar(tempo_lib, default=0.0)
        # beat times in seconds
        if len(beat_frames) > 0:
            beat_times = librosa.frames_to_time(beat_frames, sr=sr)
        else:
            beat_times = np.array([])

        # tempos / confidences
        tempo_conf_lib = float(np.mean(onset_env)) / (float(np.max(onset_env)) + 1e-9) if onset_env.size else 0.0

        # tatum confidence proxy using autocorrelation of onset envelope
        if onset_env.size > 1:
            ac = librosa.autocorrelate(onset_env, max_size=len(onset_env) - 1)
            tatum_conf_lib = float(np.max(ac) / (np.sum(ac) + 1e-9))
        else:
            tatum_conf_lib = 0.0

        # beat variance & time-signature stability
        if beat_times.size > 1:
            intervals = np.diff(beat_times)
            beat_var = float(np.var(intervals))
            ts_stab = ts_stability_from_intervals(intervals)
        else:
            beat_var = 0.0
            ts_stab = 0.0

    except Exception:
        # safe defaults if librosa fails
        tempo_lib = 0.0
        tempo_conf_lib = 0.0
        tatum_conf_lib = 0.0
        beat_var = 0.0
        ts_stab = 0.0
        beat_times = np.array([])

    # --- Essentia measures ---
    try:
        # RhythmExtractor2013 returns 5 values (API differs across versions, be robust)
        res = rhythm_extractor(frame)
        # res may be tuple/list; handle length >=1
        if isinstance(res, (list, tuple)) and len(res) >= 1:
            # typical ordering across versions: (bpm, beat_conf, beats/onsets, intervals OR tatums, tatum_conf)
            # we'll extract bpm, beat_conf and tatum_conf conservatively:
            bpm_value = safe_scalar(res[0], default=0.0)
            beat_conf_val = safe_scalar(res[1], default=0.0) if len(res) > 1 else 0.0
            # attempt to extract tatum confidence (commonly last element)
            tatum_conf_val = safe_scalar(res[-1], default=0.0) if len(res) > 1 else 0.0
        else:
            bpm_value = 0.0
            beat_conf_val = 0.0
            tatum_conf_val = 0.0
    except Exception:
        bpm_value = 0.0
        beat_conf_val = 0.0
        tatum_conf_val = 0.0

    # For consistency, use librosa-derived beat_var and ts_stab for both libraries
    beat_var_for_both = float(beat_var)
    ts_stab_for_both = float(ts_stab)

    # Build Essentia rhythm index (normalize components to 0..1 heuristically)
    ess_comp_tempo_conf = max(0.0, min(1.0, beat_conf_val))
    ess_comp_tatum_conf = max(0.0, min(1.0, tatum_conf_val))
    ess_comp_beatvar = 1.0 / (1.0 + beat_var_for_both)
    ess_components = [ess_comp_tempo_conf, ess_comp_beatvar, ess_comp_tatum_conf, ts_stab_for_both]
    ess_rhythm_index = float(np.mean(ess_components))
    ess_class = "regular" if ess_rhythm_index >= 0.5 else "irregular"

    # Librosa rhythm index (we normalize tempo_conf_lib and tatum_conf_lib to [0,1] already)
    lib_comp_tempo_conf = max(0.0, min(1.0, tempo_conf_lib))
    lib_comp_tatum_conf = max(0.0, min(1.0, tatum_conf_lib))
    lib_comp_beatvar = 1.0 / (1.0 + beat_var_for_both)
    lib_components = [lib_comp_tempo_conf, lib_comp_beatvar, lib_comp_tatum_conf, ts_stab_for_both]
    lib_rhythm_index = float(np.mean(lib_components))
    lib_class = "regular" if lib_rhythm_index >= 0.5 else "irregular"

    return {
        # Librosa outputs
        "librosa_tempo": float(tempo_lib),
        "librosa_tempo_conf": float(tempo_conf_lib),
        "librosa_tatum_conf": float(tatum_conf_lib),
        "beat_variance": float(beat_var_for_both),
        "ts_stability": float(ts_stab_for_both),
        "librosa_rhythm_index": lib_rhythm_index,
        "librosa_rhythm_class": lib_class,
        # Essentia outputs
        "essentia_bpm": float(bpm_value),
        "essentia_tempo_conf": float(ess_comp_tempo_conf),
        "essentia_tatum_conf": float(ess_comp_tatum_conf),
        "essentia_rhythm_index": ess_rhythm_index,
        "essentia_rhythm_class": ess_class,
    }


# ----- main loop over songs and window/hop pairs -----
def process_all_songs():
    all_sheets = {}
    files = sorted([p for p in SONGS_DIR.glob("*") if p.suffix.lower() in [".mp3", ".wav", ".flac", ".m4a", ".ogg"]])
    if not files:
        print(f"No audio files found in {SONGS_DIR.resolve()}")
        return

    for song_path in files:
        print(f"\n--- Processing: {song_path.name}")
        try:
            y, sr = librosa.load(str(song_path), sr=None, mono=True)
        except Exception as exc:
            print(f"Could not load {song_path.name}: {exc}")
            continue

        song_key = song_path.stem[:14]  # truncate to 14 chars for readability

        for win_sec, hop_sec in WINDOW_HOP_PAIRS_SEC:
            try:
                window_len = int(round(win_sec * sr))
                hop_len = int(round(hop_sec * sr))
                if window_len <= 0 or hop_len <= 0:
                    print("Invalid window/hop (too small), skipping this pair.")
                    continue

                print(f" Window={win_sec}s (samples {window_len}), Hop={hop_sec}s (samples {hop_len})")

                results = []
                # iterate start positions from 0 to end by hop_len, include final partial window (pad with zeros)
                start = 0
                total_samples = len(y)
                while start < total_samples:
                    end = start + window_len
                    if end <= total_samples:
                        frame = y[start:end]
                    else:
                        # pad final window with zeros so windows cover full duration
                        frame = np.pad(y[start:total_samples], (0, end - total_samples), mode="constant")

                    t_start_sec = start / sr
                    t_end_sec = min(end, total_samples) / sr

                    # analyze the fixed-length frame
                    try:
                        feats = analyze_frame_both(frame, sr)
                    except Exception:
                        traceback.print_exc()
                        feats = {
                            "librosa_tempo": 0.0, "librosa_tempo_conf": 0.0, "librosa_tatum_conf": 0.0,
                            "beat_variance": 0.0, "ts_stability": 0.0, "librosa_rhythm_index": 0.0, "librosa_rhythm_class": "unknown",
                            "essentia_bpm": 0.0, "essentia_tempo_conf": 0.0, "essentia_tatum_conf": 0.0,
                            "essentia_rhythm_index": 0.0, "essentia_rhythm_class": "unknown"
                        }

                    row = {
                        "start_sec": t_start_sec,
                        "end_sec": t_end_sec,
                        **feats
                    }
                    results.append(row)

                    if VERBOSE:
                        print(f" t={t_start_sec:.2f}s  lib_bpm={feats['librosa_tempo']:.1f}  lib_idx={feats['librosa_rhythm_index']:.3f}  ess_bpm={feats['essentia_bpm']:.1f}  ess_idx={feats['essentia_rhythm_index']:.3f}")

                    # simulate real-time pacing by waiting hop_sec (unless disabled)
                    if SIMULATE_REALTIME:
                        time.sleep(hop_sec)

                    start += hop_len

                # collect into sheet
                sheet_name = f"{song_key}_w{win_sec}_h{hop_sec}"
                # Excel sheet name max 31 chars -> truncate safely
                sheet_name = sheet_name[:31]
                all_sheets[sheet_name] = pd.DataFrame(results)

            except Exception:
                print("Error while processing window/hop pair:")
                traceback.print_exc()
                continue

    # Save all sheets to Excel (only if we have data)
    if all_sheets:
        with pd.ExcelWriter(OUTPUT_EXCEL, engine="openpyxl") as writer:
            for sheet, df in all_sheets.items():
                # write each dataframe into its own sheet
                df.to_excel(writer, sheet_name=sheet, index=False)
        print(f"\n✅ All results saved to: {OUTPUT_EXCEL}")
    else:
        print("\n⚠️ No results generated; nothing saved.")


if __name__ == "__main__":
    process_all_songs()
