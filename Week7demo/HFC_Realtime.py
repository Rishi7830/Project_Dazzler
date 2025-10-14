#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import numpy as np
from collections import deque
from dataclasses import dataclass
import essentia.standard as es
from scipy.ndimage import uniform_filter1d

# --------------- Utilities ---------------

def frame_loudness_db(frame):
    # Simple RMS loudness in dBFS; add epsilon to avoid log(0)
    rms = np.sqrt(np.mean(frame**2) + 1e-12)
    return 20.0 * np.log10(rms + 1e-12)

@dataclass
class Params:
    frame_size: int = 1024
    hop_size: int = 512
    short_smooth_sec: float = 0.25    # ~250 ms
    slow_smooth_sec: float = 1.0      # ~1 s for slower trend
    novelty_weights: tuple = (0.6, 0.2, 0.2)  # (ΔHFC, ΔHFC_slow, ΔLoud)
    percentile_window_sec: float = 15.0
    threshold_percentile: float = 85.0
    min_spacing_sec: float = 5.0
    pre_win_sec: float = 1.0
    post_win_sec: float = 0.8         # adds latency; set 0 for immediate
    hfc_jump_k: float = 0.8           # multiples of MAD
    loud_jump_db: float = 1.5         # dB change to accept
    sample_rate: int = 44100

class OnlineSmootherIIR:
    def __init__(self, hop_sec, time_const_sec):
        alpha = hop_sec / max(time_const_sec, hop_sec)
        self.alpha = float(np.clip(alpha, 0.0, 1.0))
        self.y = None

    def update_vec(self, x):
        # causal IIR y[t] = a*x[t] + (1-a)*y[t-1]
        out = np.empty_like(x, dtype=float)
        for i, xi in enumerate(x):
            if self.y is None:
                self.y = xi
            else:
                self.y = self.alpha * xi + (1 - self.alpha) * self.y
            out[i] = self.y
        return out

class PercentileThresh:
    def __init__(self, capacity):
        self.buf = deque(maxlen=capacity)

    def update(self, x_values):
        self.buf.extend(x_values)

    def percentile(self, p):
        if not self.buf:
            return 0.0
        return float(np.percentile(np.array(self.buf), p))

class OnlineBoundaryDetector:
    def __init__(self, params: Params):
        self.p = params
        hop_sec = params.hop_size / params.sample_rate

        # Essentia ops
        self.win = es.Windowing(type='hann')
        self.fft = es.FFT()
        self.c2p = es.CartesianToPolar()
        self.od = es.OnsetDetection(method='hfc')

        # State buffers
        self.hfc_s = []        # smoothed short
        self.hfc_sl = []       # smoothed slow
        self.loud_s = []       # smoothed short
        self.time = []         # seconds for each frame center
        self.last_time = 0.0

        # Causal smoothers
        self.hfc_smoother = OnlineSmootherIIR(hop_sec, params.short_smooth_sec)
        self.hfc_slow_smoother = OnlineSmootherIIR(hop_sec, params.slow_smooth_sec)
        self.loud_smoother = OnlineSmootherIIR(hop_sec, params.short_smooth_sec)

        # Novelty and threshold
        cap = int(params.percentile_window_sec / hop_sec)
        self.nov_hist = PercentileThresh(capacity=max(cap, 1))
        self.novelty = []

        # Gating and stats
        self.mad_hist = deque(maxlen=2000)  # for robust HFC scale (MAD)
        self.cooldown_until = -1.0
        self.pending_candidate = None  # (t_peak)

        # ring buffers for pre/post means
        self.hfc_ring = deque(maxlen=int(3 * params.pre_win_sec / hop_sec))
        self.loud_ring = deque(maxlen=int(3 * params.pre_win_sec / hop_sec))

    def process_chunk(self, audio_chunk):
        p = self.p
        hop = p.hop_size
        fs = p.sample_rate
        hop_sec = hop / fs

        # STFT framing over the chunk
        frames = list(es.FrameGenerator(audio_chunk, frameSize=p.frame_size, hopSize=hop, startFromZero=True))
        if not frames:
            return []

        # Compute HFC and per-frame loudness
        hfc_raw = []
        loud_raw = []
        for fr in frames:
            mag, ph = self.c2p(self.fft(self.win(fr)))
            hfc_raw.append(self.od(mag, ph))
            loud_raw.append(frame_loudness_db(fr))
        hfc_raw = np.asarray(hfc_raw, dtype=float)
        loud_raw = np.asarray(loud_raw, dtype=float)

        # Causal smoothing
        hfc_sm = self.hfc_smoother.update_vec(hfc_raw)
        hfc_sl = self.hfc_slow_smoother.update_vec(hfc_raw)
        loud_sm = self.loud_smoother.update_vec(loud_raw)

        # Append to state and build times
        n = len(hfc_sm)
        t0 = self.last_time
        times = t0 + np.arange(n) * hop_sec
        self.last_time = times[-1] + hop_sec

        self.hfc_s.extend(hfc_sm.tolist())
        self.hfc_sl.extend(hfc_sl.tolist())
        self.loud_s.extend(loud_sm.tolist())
        self.time.extend(times.tolist())

        # maintain MAD history for scaling
        self.mad_hist.extend(hfc_sm.tolist())
        med = np.median(self.mad_hist) if self.mad_hist else 0.0
        mad = np.median(np.abs(np.array(self.mad_hist) - med)) + 1e-8

        # Novelty components (first differences)
        def diff_abs(x):  # compute on the new part only
            if len(x) < 2:
                return np.zeros_like(x)
            d = np.abs(np.diff(x))
            return np.concatenate([[d[0]], d])  # align lengths
        d_hfc = diff_abs(hfc_sm)
        d_hfc_slow = diff_abs(hfc_sl)
        d_loud = diff_abs(loud_sm)

        w1, w2, w3 = p.novelty_weights
        novelty = w1 * d_hfc + w2 * d_hfc_slow + w3 * d_loud
        self.novelty.extend(novelty.tolist())
        self.nov_hist.update(novelty.tolist())

        # Online peak picking with spacing and confirmation
        events = []
        thresh = self.nov_hist.percentile(p.threshold_percentile)

        for i in range(n):
            t = times[i]
            if t < self.cooldown_until:
                continue

            # local maximum in a small causal window (compare to previous sample only to stay causal)
            is_peak = novelty[i] > thresh
            if is_peak:
                # Stage 1: mark candidate
                if self.pending_candidate is None:
                    self.pending_candidate = t

            # Stage 2: confirm using post window once enough time passed
            if self.pending_candidate is not None:
                cand_t = self.pending_candidate
                if t - cand_t >= p.post_win_sec:
                    # Compute pre/post means over windows
                    pre_mask = (np.array(self.time) >= cand_t - p.pre_win_sec) & (np.array(self.time) < cand_t)
                    post_mask = (np.array(self.time) >= cand_t) & (np.array(self.time) < cand_t + p.post_win_sec)

                    h_pre = np.mean(np.array(self.hfc_s)[pre_mask]) if np.any(pre_mask) else med
                    h_post = np.mean(np.array(self.hfc_s)[post_mask]) if np.any(post_mask) else h_pre
                    l_pre = np.mean(np.array(self.loud_s)[pre_mask]) if np.any(pre_mask) else -60.0
                    l_post = np.mean(np.array(self.loud_s)[post_mask]) if np.any(post_mask) else l_pre

                    h_jump = abs(h_post - h_pre) / mad
                    l_jump = abs(l_post - l_pre)

                    if (h_jump >= p.hfc_jump_k) or (l_jump >= p.loud_jump_db):
                        events.append({'time': cand_t, 'h_jump_mad': float(h_jump), 'l_jump_db': float(l_jump)})
                        self.cooldown_until = cand_t + p.min_spacing_sec

                    self.pending_candidate = None  # reset whether accepted or not

        return events

# --------------- Offline chunked runner ---------------

def stream_from_file(filename, chunk_seconds=1.0, params=Params()):
    # Load whole file mono at target sample rate (Essentia decodes native rate by default)
    audio = es.MonoLoader(filename=filename)()
    sr = es.MonoLoader(filename=filename).paramValue('sampleRate')
    params.sample_rate = sr

    # Chunk the raw samples
    N = len(audio)
    chunk_len = int(chunk_seconds * sr)
    for start in range(0, N, chunk_len):
        yield audio[start:start+chunk_len]

# --------------- Demo main ---------------

if __name__ == '__main__':
    params = Params()
    detector = OnlineBoundaryDetector(params)

    audio_file = 'scom.mp3'  # change this path
    events_all = []
    for chunk in stream_from_file(audio_file, chunk_seconds=0.5, params=params):
        ev = detector.process_chunk(chunk)
        if ev:
            events_all.extend(ev)

    # Print detected boundaries at the end (or push to your MQTT in real time)
    for e in events_all:
        print(f"{e['time']:.3f}")
