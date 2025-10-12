#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import numpy as np
import matplotlib.pyplot as plt
from scipy.ndimage import uniform_filter1d
from scipy.signal import find_peaks
import matplotlib.ticker as mticker
import csv
import warnings

import essentia
import essentia.standard as es

warnings.filterwarnings('ignore')

def compute_hfc_odf(
    audio,
    frame_size=1024,
    hop_size=512,
    window_type='hann'
):
    """
    Compute HFC onset detection function (ODF) from a mono signal.

    Returns:
        odf_values: np.ndarray, shape (n_frames,)
        times: np.ndarray, seconds for each ODF frame
    """
    # Analysis ops
    w = es.Windowing(type=window_type)
    fft = es.FFT()                # complex
    c2p = es.CartesianToPolar()   # -> magnitude, phase
    od = es.OnsetDetection(method='hfc')

    # Frame generator uses audio length and hop
    odf_vals = []
    for frame in es.FrameGenerator(audio, frameSize=frame_size, hopSize=hop_size, startFromZero=True):
        mag, phase = c2p(fft(w(frame)))
        odf_vals.append(od(mag, phase))

    odf_values = np.asarray(odf_vals, dtype=np.float32)

    # Time axis
    sr = es.MonoLoader.defaultSampleRate  # not reliable for file rate; compute from hop in seconds
    # Prefer using Essentia's FrameGenerator timing: derive by sample count
    # We assume the audio array is at sample_rate given by loader.
    return odf_values

def load_audio_mono(path, sample_rate=None):
    """
    Load audio as mono. If sample_rate is None, loads at file's native rate.
    Returns: audio (np.ndarray), sr (int)
    """
    if sample_rate is None:
        loader = es.MonoLoader(filename=path)
    else:
        loader = es.MonoLoader(filename=path, sampleRate=sample_rate)
    audio = loader()
    # Retrieve effective sample rate (MonoLoader has attribute but not returned)
    sr = loader.paramValue('sampleRate')
    return audio, sr

def postprocess_odf(odf_values, hop_size, sample_rate,
                    smooth_size=20, normalize=True):
    """
    Smooth ODF and build time axis.
    """
    # Smoothing
    if smooth_size and smooth_size > 1:
        odf_smooth = uniform_filter1d(odf_values, size=smooth_size)
    else:
        odf_smooth = odf_values.copy()

    # Simple normalization: subtract median and divide by MAD-like scale
    if normalize:
        med = np.median(odf_smooth)
        mad = np.median(np.abs(odf_smooth - med)) + 1e-8
        odf_smooth = (odf_smooth - med) / mad

    times = np.arange(len(odf_values)) * (hop_size / float(sample_rate))
    return odf_smooth, times

def pick_onset_peaks(odf_smooth,
                     times,
                     height_percentile=85,
                     min_distance_sec=0.05):
    """
    Peak-pick on the smoothed/normalized ODF.
    """
    # Threshold via percentile on the positive tail
    pos = odf_smooth[odf_smooth > 0]
    if len(pos) == 0:
        thr = np.percentile(odf_smooth, height_percentile)
    else:
        thr = np.percentile(pos, height_percentile)

    # Convert minimum distance from seconds to samples in ODF domain
    if len(times) >= 2:
        odf_hop_sec = times[1] - times[0]
    else:
        odf_hop_sec = 0.01
    distance = max(1, int(min_distance_sec / odf_hop_sec))

    peaks, props = find_peaks(odf_smooth, height=thr, distance=distance)
    onset_times = times[peaks]
    return peaks, onset_times, props

def analyze_hfc(file_path,
                frame_size=1024,
                hop_size=512,
                smooth_size=20,
                norm=True,
                height_percentile=85,
                min_distance_sec=0.05,
                save_csv=None,
                show_plot=True,
                title='HFC ODF with Onsets'):
    """
    End-to-end HFC onset detection and visualization.
    """
    audio, sr = load_audio_mono(file_path)
    # Compute raw ODF
    w = es.Windowing(type='hann')
    fft = es.FFT()
    c2p = es.CartesianToPolar()
    od_hfc = es.OnsetDetection(method='hfc')

    odf_vals = []
    for frame in es.FrameGenerator(audio, frameSize=frame_size, hopSize=hop_size, startFromZero=True):
        mag, ph = c2p(fft(w(frame)))
        odf_vals.append(od_hfc(mag, ph))
    odf_values = np.asarray(odf_vals, dtype=np.float32)

    # Post-process
    odf_smooth, times = postprocess_odf(odf_values, hop_size, sr, smooth_size, norm)

    # Peak picking
    peaks, onset_times, props = pick_onset_peaks(odf_smooth, times, height_percentile, min_distance_sec)

    # Optional CSV export
    if save_csv:
        with open(save_csv, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['time_sec', 'odf_raw', 'odf_proc', 'is_onset'])
            onset_set = set(np.round(onset_times, 6))
            for t, raw, proc in zip(times, odf_values, odf_smooth):
                writer.writerow([f'{t:.6f}', f'{raw:.6f}', f'{proc:.6f}', int(np.round(t,6) in onset_set)])

    # Plot
    if show_plot:
        fig, ax = plt.subplots(figsize=(12, 5))
        ax.plot(times, odf_values, alpha=0.35, label='HFC ODF (raw)')
        ax.plot(times, odf_smooth, label='HFC ODF (smoothed/normalized)', linewidth=1.5)
        ax.scatter(times[peaks], odf_smooth[peaks], color='crimson', s=25, zorder=3, label='Onset peaks')
        ax.set_title(title)
        ax.set_xlabel('Time (minutes:seconds)')
        ax.set_ylabel('ODF value')
        ax.grid(True, alpha=0.3)
        ax.legend()

        def seconds_to_minsec(x, pos):
            m = int(x // 60)
            s = int(x % 60)
            return f"{m}:{s:02d}"
        ax.xaxis.set_major_formatter(mticker.FuncFormatter(seconds_to_minsec))

        plt.tight_layout()
        plt.show()

    return {
        'sample_rate': sr,
        'times': times,
        'odf_raw': odf_values,
        'odf_proc': odf_smooth,
        'onset_indices': peaks,
        'onset_times': onset_times
    }

# Optional: section stats helper
def section_stats(times, values, sections):
    """
    sections: list of (start_time, end_time)
    returns list of dicts with min, max, mean, std per section.
    """
    out = []
    for (a, b) in sections:
        mask = (times >= a) & (times < b)
        v = values[mask]
        if len(v) == 0:
            out.append({'start': a, 'end': b, 'count': 0, 'min': None, 'max': None, 'mean': None, 'std': None})
        else:
            out.append({
                'start': a, 'end': b, 'count': int(mask.sum()),
                'min': float(v.min()), 'max': float(v.max()),
                'mean': float(v.mean()), 'std': float(v.std())
            })
    return out

if __name__ == '__main__':
    # Example usage
    result = analyze_hfc(
        file_path='scom.mp3',     # change to your audio file path
        frame_size=1024,
        hop_size=512,
        smooth_size=20,
        norm=True,
        height_percentile=85,
        min_distance_sec=0.05,
        save_csv=None,              # e.g., 'odf_onsets.csv'
        show_plot=True,
        title='HFC ODF with Onsets'
    )

    # Print first few onset times
    print("Detected onsets (s):", np.round(result['onset_times'][:20], 3))
