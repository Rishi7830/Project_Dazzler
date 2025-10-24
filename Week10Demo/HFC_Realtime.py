import time, math, sys
from pathlib import Path
import numpy as np

# Dependencies: pip install essentia numpy
import essentia.standard as es

# ---- Tunable parameters ----
FRAME_SIZE = 1024
HOP_SIZE = 512
W_WEIGHTS = (0.6, 0.2, 0.2)
PERCENTILE = 90.0
PERC_WINDOW_SEC = 15.0
MIN_SPACING_SEC = 8.0
PRE_WIN_SEC = 1.0
POST_WIN_SEC = 0.8
HFC_JUMP_K = 1.2
LOUD_JUMP_DB = 2.5

class CausalEMA:
    def __init__(self, hop_sec, tau_sec):
        a = hop_sec / max(tau_sec, hop_sec)
        self.a = float(np.clip(a, 0.0, 1.0))
        self.y = None
    def push(self, x):
        if self.y is None:
            self.y = float(x)
        else:
            self.y = self.a*float(x) + (1.0-self.a)*self.y
        return self.y

def rolling_percentile(values, perc):
    arr = np.asarray(values, dtype=float)
    if len(arr) == 0:
        return 0.0
    return float(np.percentile(arr, perc))

def frame_loudness_db(frame):
    rms = float(np.sqrt(np.mean(frame**2) + 1e-12))
    return 20.0 * math.log10(rms + 1e-12)

def compute_hfc_val(frame):
    win = np.hanning(len(frame)).astype(np.float32)
    frw = frame * win
    fftv = np.fft.rfft(frw)
    mag = np.abs(fftv).astype(np.float32)
    return float(np.sum(np.arange(len(mag)) * (mag**2)))

def mad_scale(arr):
    if len(arr) < 20:
        return 1.0
    med = np.median(arr)
    mad = np.median(np.abs(np.asarray(arr) - med))
    return float(max(mad, 1e-6))

class RealtimeOnsetDetector:
    def __init__(self, sample_rate=44100):
        self.hop_sec = HOP_SIZE / sample_rate
        self.ema_fast = CausalEMA(self.hop_sec, 0.25)
        self.ema_slow = CausalEMA(self.hop_sec, 1.0)
        self.ema_loud = CausalEMA(self.hop_sec, 0.25)
        self.ema_nov = CausalEMA(self.hop_sec, 0.25)
        self.novelty_buf = []
        self.hfc_hist = []
        self.loud_hist = []
        self.preN = max(1, int(PRE_WIN_SEC / self.hop_sec))
        self.postN = max(1, int(POST_WIN_SEC / self.hop_sec))
        self.min_spacing = MIN_SPACING_SEC
        self.last_emit_time = -1e9
        self.last_audio_time = 0.0

    def is_onset(self, frame, curr_time):
        hfc_raw = compute_hfc_val(frame)
        loud_db = frame_loudness_db(frame)
        hfc_f = self.ema_fast.push(hfc_raw)
        hfc_s = self.ema_slow.push(hfc_raw)
        loud_s = self.ema_loud.push(loud_db)
        self.hfc_hist.append(hfc_f)
        self.loud_hist.append(loud_s)
        d_hfc_fast = abs(self.hfc_hist[-1] - self.hfc_hist[-2]) if len(self.hfc_hist) >= 2 else 0.0
        d_hfc_slow = abs(hfc_s - (self.hfc_hist[-2] if len(self.hfc_hist) >= 2 else hfc_s)) if len(self.hfc_hist) >= 2 else 0.0
        d_loud = abs(self.loud_hist[-1] - self.loud_hist[-2]) if len(self.loud_hist) >= 2 else 0.0
        w1, w2, w3 = W_WEIGHTS
        novelty_raw = w1 * d_hfc_fast + w2 * d_hfc_slow + w3 * d_loud
        novelty = self.ema_nov.push(novelty_raw)
        self.novelty_buf.append(novelty)
        if len(self.novelty_buf) > max(1, int(PERC_WINDOW_SEC / self.hop_sec)):
            self.novelty_buf.pop(0)
        thr = rolling_percentile(self.novelty_buf, PERCENTILE)
        over_thr = novelty > thr
        spacing_ok = (curr_time - self.last_emit_time) >= self.min_spacing
        if over_thr and spacing_ok and len(self.hfc_hist) >= (self.preN + self.postN + 2):
            scale = mad_scale(self.hfc_hist[-min(len(self.hfc_hist), int(5.0 / self.hop_sec)):])
            h_pre = float(np.mean(self.hfc_hist[-self.preN:])) if self.preN > 0 else 0.0
            h_post = float(np.mean(self.hfc_hist[-self.postN:])) if self.postN > 0 else 0.0
            l_pre = float(np.mean(self.loud_hist[-self.preN:])) if self.preN > 0 else 0.0
            l_post = float(np.mean(self.loud_hist[-self.postN:])) if self.postN > 0 else 0.0
            h_jump = abs(h_post - h_pre) / max(scale, 1e-6)
            l_jump = abs(l_post - l_pre)
            if (h_jump >= HFC_JUMP_K) or (l_jump >= LOUD_JUMP_DB):
                self.last_emit_time = curr_time
                return True, loud_db
        return False, loud_db
