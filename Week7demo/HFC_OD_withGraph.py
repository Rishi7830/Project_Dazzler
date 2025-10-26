#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import numpy as np
import matplotlib.pyplot as plt
from scipy.ndimage import uniform_filter1d
from scipy.signal import find_peaks
import matplotlib.ticker as mticker
import warnings
import essentia
import essentia.standard as es
import os

warnings.filterwarnings('ignore')

def compute_hfc_odf(audio, frame_size=1024, hop_size=512, window_type='hann'):
    """
    Compute HFC onset detection function (ODF) from a mono signal.
    Returns: odf_values (np.ndarray)
    """
    w = es.Windowing(type=window_type)
    fft = es.FFT()
    c2p = es.CartesianToPolar()
    od = es.OnsetDetection(method='hfc')

    odf_vals = []
    for frame in es.FrameGenerator(audio, frameSize=frame_size, hopSize=hop_size, startFromZero=True):
        mag, phase = c2p(fft(w(frame)))
        odf_vals.append(od(mag, phase))
    return np.asarray(odf_vals, dtype=np.float32)

def load_audio_mono(path, sample_rate=None):
    """
    Load audio as mono. Returns: audio (np.ndarray), sr (int)
    """
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Audio file not found: {path}")
    if sample_rate is None:
        loader = es.MonoLoader(filename=path)
    else:
        loader = es.MonoLoader(filename=path, sampleRate=sample_rate)
    audio = loader()
    sr = loader.paramValue('sampleRate')
    return audio, sr

def postprocess_odf(odf_values, hop_size, sample_rate, smooth_size=20, normalize=True):
    """
    Smooth ODF and build time axis.
    """
    odf_smooth = uniform_filter1d(odf_values, size=smooth_size) if smooth_size > 1 else odf_values.copy()
    if normalize:
        med = np.median(odf_smooth)
        mad = np.median(np.abs(odf_smooth - med)) + 1e-8
        odf_smooth = (odf_smooth - med) / mad
    times = np.arange(len(odf_values)) * (hop_size / float(sample_rate))
    return odf_smooth, times

def pick_onset_peaks(odf_smooth, times, height_percentile=85, min_distance_sec=0.05):
    """
    Peak-pick on the smoothed/normalized ODF.
    """
    pos = odf_smooth[odf_smooth > 0]
    thr = np.percentile(pos, height_percentile) if len(pos) > 0 else np.percentile(odf_smooth, height_percentile)
    odf_hop_sec = times[1] - times[0] if len(times) >= 2 else 0.01
    distance = max(1, int(min_distance_sec / odf_hop_sec))
    peaks, props = find_peaks(odf_smooth, height=thr, distance=distance)
    onset_times = times[peaks]
    return peaks, onset_times, props

def analyze_hfc(file_path, frame_size=1024, hop_size=512, smooth_size=20, norm=True,
                height_percentile=85, min_distance_sec=0.05):
    """
    End-to-end HFC onset detection.
    Returns a dict with times, ODF values, and detected onsets.
    """
    audio, sr = load_audio_mono(file_path)

    # Compute raw ODF
    odf_values = compute_hfc_odf(audio, frame_size, hop_size)

    # Post-process
    odf_smooth, times = postprocess_odf(odf_values, hop_size, sr, smooth_size, norm)

    # Peak picking
    peaks, onset_times, _ = pick_onset_peaks(odf_smooth, times, height_percentile, min_distance_sec)

    return {
        'sample_rate': sr,
        'times': times,
        'odf_raw': odf_values,
        'odf_proc': odf_smooth,
        'onset_indices': peaks,
        'onset_times': onset_times
    }

if __name__ == '__main__':
    # Ask user for the audio file path
    while True:
        file_path = input("Enter the path to the audio file (e.g., scom.mp3): ").strip()
        if os.path.isfile(file_path):
            break
        else:
            print("File not found. Please try again.")

    # Analyze audio
    result = analyze_hfc(file_path)

    times = result['times']
    odf_raw = result['odf_raw']
    odf_proc = result['odf_proc']
    peaks = result['onset_indices']

    # Plot directly
    plt.figure(figsize=(12, 5))
    plt.plot(times, odf_raw, alpha=0.3, label='HFC ODF (raw)')
    plt.plot(times, odf_proc, label='HFC ODF (smoothed/normalized)', linewidth=1.5)
    plt.scatter(times[peaks], odf_proc[peaks], color='crimson', s=25, label='Onset peaks')
    plt.title('HFC ODF with Onsets')
    plt.xlabel('Time (minutes:seconds)')
    plt.ylabel('ODF Value')
    plt.grid(True, alpha=0.3)
    plt.legend()

    # Format x-axis as min:sec
    def sec_to_minsec(x, pos):
        m = int(x // 60)
        s = int(x % 60)
        return f"{m}:{s:02d}"
    plt.gca().xaxis.set_major_formatter(mticker.FuncFormatter(sec_to_minsec))

    plt.tight_layout()
    plt.show()

    # Print first few onset times
    print("Detected onsets (s):", np.round(result['onset_times'][:20], 3))
