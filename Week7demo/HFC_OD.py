#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from scipy.ndimage import uniform_filter1d
import essentia.standard as es
import warnings
warnings.filterwarnings('ignore')

# -------- Settings (edit) --------
AUDIO_FILE = 'scom.mp3'           # path to audio
SAVE_PNG = 'hfc_odf_only.png'       # output image file
FRAME_SIZE = 1024
HOP_SIZE = 512
SMOOTH_SIZE = 20                    # set to 0 or 1 to disable smoothing overlay
TITLE = 'HFC ODF Timeline'
# ---------------------------------

def seconds_to_minsec(x, pos):
    m = int(x // 60); s = int(x % 60); return f"{m}:{s:02d}"

def load_audio(path):
    loader = es.MonoLoader(filename=path)
    audio = loader()
    sr = loader.paramValue('sampleRate')
    return audio, sr

def compute_hfc_odf(audio, frame_size=1024, hop_size=512):
    w = es.Windowing(type='hann'); fft = es.FFT(); c2p = es.CartesianToPolar()
    od = es.OnsetDetection(method='hfc')
    vals = []
    for frame in es.FrameGenerator(audio, frameSize=frame_size, hopSize=hop_size, startFromZero=True):
        mag, ph = c2p(fft(w(frame)))
        vals.append(od(mag, ph))
    return np.asarray(vals, dtype=np.float32)

def main():
    audio, sr = load_audio(AUDIO_FILE)
    odf = compute_hfc_odf(audio, FRAME_SIZE, HOP_SIZE)
    times = np.arange(len(odf)) * (HOP_SIZE / float(sr))

    # Optional smoothing for display
    if SMOOTH_SIZE and SMOOTH_SIZE > 1:
        odf_smooth = uniform_filter1d(odf, size=SMOOTH_SIZE)
    else:
        odf_smooth = None

    # Plot
    fig, ax = plt.subplots(figsize=(14, 5))
    ax.fill_between(times, odf, color='#1f77b4', alpha=0.85, step='mid',
                    label='HFC Onset Detection Function (ODF)')
    if odf_smooth is not None:
        ax.plot(times, odf_smooth, color='white', linewidth=1.1, alpha=0.9, label='Smoothed ODF')

    ax.set_title(TITLE)
    ax.set_xlabel('Time (minutes:seconds)')
    ax.set_ylabel('ODF Value')
    ax.grid(True, alpha=0.3)
    ax.legend(loc='upper right')
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(seconds_to_minsec))

    plt.tight_layout()
    plt.savefig(SAVE_PNG, dpi=150, bbox_inches='tight')
    plt.close(fig)

if __name__ == '__main__':
    main()
