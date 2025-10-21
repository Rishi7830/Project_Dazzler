import time, math, sys
from pathlib import Path
import numpy as np


# Dependencies: pip install essentia numpy
import essentia.standard as es
touch ../ONSET/__init__.py


# ---- Tunable parameters (from your training) ----
FRAME_SIZE = 1024
HOP_SIZE = 512
W_WEIGHTS = (0.6, 0.2, 0.2)     # (ΔHFC_fast, ΔHFC_slow, ΔLoud)
PERCENTILE = 90.0               # rolling percentile threshold
PERC_WINDOW_SEC = 15.0          # window for adaptive threshold
MIN_SPACING_SEC = 8.0           # minimum spacing between boundaries
PRE_WIN_SEC = 1.0               # pre window for confirmation
POST_WIN_SEC = 0.8              # post window for confirmation (controls latency)
HFC_JUMP_K = 1.2                # MAD-scaled HFC jump threshold
LOUD_JUMP_DB = 2.5              # absolute loudness jump threshold (dB)

# --------------------------------------------------

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
    # HFC ODF proxy: sum_k k * |X[k]|^2 (bin index weighted power)
    win = np.hanning(len(frame)).astype(np.float32)
    frw = frame * win
    fftv = np.fft.rfft(frw)
    mag = np.abs(fftv).astype(np.float32)
    return float(np.sum(np.arange(len(mag)) * (mag**2)))

def simulate_realtime_mp3(mp3_path):
    if not Path(mp3_path).exists():
        print('File not found:', mp3_path)
        return

    # Load audio
    loader = es.MonoLoader(filename=str(mp3_path))
    audio = loader()
    sr = loader.paramValue('sampleRate')
    hop_sec = HOP_SIZE / sr

    # Frame the audio
    frames = list(es.FrameGenerator(audio, frameSize=FRAME_SIZE, hopSize=HOP_SIZE, startFromZero=True))
    if not frames:
        print('No frames read; check file.', file=sys.stderr)
        return

    # Causal smoothers
    ema_fast = CausalEMA(hop_sec, 0.25)
    ema_slow = CausalEMA(hop_sec, 1.0)
    ema_loud = CausalEMA(hop_sec, 0.25)
    ema_nov = CausalEMA(hop_sec, 0.25)

    # Buffers
    perc_window = max(1, int(PERC_WINDOW_SEC / hop_sec))
    novelty_buf = []             # for rolling percentile
    hfc_hist = []                # for confirmation window
    loud_hist = []

    preN = max(1, int(PRE_WIN_SEC / hop_sec))
    postN = max(1, int(POST_WIN_SEC / hop_sec))
    min_spacing = MIN_SPACING_SEC

    last_emit_time = -1e9

    # MAD scaler for HFC fast
    def mad_scale(arr):
        if len(arr) < 20:
            return 1.0
        med = np.median(arr)
        mad = np.median(np.abs(np.asarray(arr) - med))
        return float(max(mad, 1e-6))

    print('Simulating real-time playback...')
    t_start = time.perf_counter()

    for i, fr in enumerate(frames):
        t_audio = i * hop_sec

        # Feature extraction per frame
        hfc_raw = compute_hfc_val(fr)
        loud_db = frame_loudness_db(fr)

        hfc_f = ema_fast.push(hfc_raw)
        hfc_s = ema_slow.push(hfc_raw)
        loud_s = ema_loud.push(loud_db)

        # Maintain histories
        hfc_hist.append(hfc_f)
        loud_hist.append(loud_s)

        # Deltas (absolute)
        if len(hfc_hist) >= 2:
            d_hfc_fast = abs(hfc_hist[-1] - hfc_hist[-2])
        else:
            d_hfc_fast = 0.0
        if len(hfc_hist) >= 2:
            d_hfc_slow = abs(hfc_s - (hfc_hist[-2] if len(hfc_hist)>=2 else hfc_s))
        else:
            d_hfc_slow = 0.0
        if len(loud_hist) >= 2:
            d_loud = abs(loud_hist[-1] - loud_hist[-2])
        else:
            d_loud = 0.0

        # Novelty and smoothing (fix: compute before smoothing, then smooth)
        w1, w2, w3 = W_WEIGHTS
        novelty_raw = w1*d_hfc_fast + w2*d_hfc_slow + w3*d_loud
        novelty = ema_nov.push(novelty_raw)

        # Rolling percentile threshold (online approximation)
        novelty_buf.append(novelty)
        if len(novelty_buf) > perc_window:
            novelty_buf.pop(0)
        thr = rolling_percentile(novelty_buf, PERCENTILE)

        # Candidate decision
        over_thr = novelty > thr
        spacing_ok = (t_audio - last_emit_time) >= min_spacing

        # Post confirmation using pre/post windows
        if over_thr and spacing_ok and len(hfc_hist) >= (preN + postN + 2):
            pre_h = hfc_hist[-(preN + postN + 1) : -(postN + 1)] if (preN + postN + 1) <= len(hfc_hist) else hfc_hist[:-1]
            post_h = hfc_hist[-postN:] if postN > 0 else []

            pre_l = loud_hist[-(preN + postN + 1) : -(postN + 1)] if (preN + postN + 1) <= len(loud_hist) else loud_hist[:-1]
            post_l = loud_hist[-postN:] if postN > 0 else []

            if len(pre_h) >= 1 and len(post_h) >= 1:
                h_pre = float(np.mean(pre_h[-preN:])) if preN > 0 else 0.0
                h_post = float(np.mean(post_h))
                l_pre = float(np.mean(pre_l[-preN:])) if preN > 0 else 0.0
                l_post = float(np.mean(post_l))

                scale = mad_scale(hfc_hist[-min(len(hfc_hist), int(5.0/hop_sec)):])
                h_jump = abs(h_post - h_pre) / max(scale, 1e-6)
                l_jump = abs(l_post - l_pre)

                if (h_jump >= HFC_JUMP_K) or (l_jump >= LOUD_JUMP_DB):
                    print(f'[BOUNDARY] t={t_audio:.3f}s  novelty={novelty:.4f}  thr={thr:.4f}  h_jump={h_jump:.2f}  l_jump={l_jump:.2f}')
                    last_emit_time = t_audio

        # Sleep to simulate real-time wall-clock
        t_elapsed = time.perf_counter() - t_start
        t_should = t_audio
        delay = t_should - t_elapsed
        if delay > 0:
            time.sleep(min(delay, 0.1))

    print('Done.')

if __name__ == '__main__':
    try:
        mp3_path = input('Enter MP3 file path: ').strip()
    except EOFError:
        print('No input provided.')
        sys.exit(1)
    simulate_realtime_mp3(mp3_path)

# --- Add this to expose a reusable onset detection class ---
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
        # post-confirmation logic simplified for pipeline speed
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


# --- Add this to expose a reusable onset detection class ---
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
