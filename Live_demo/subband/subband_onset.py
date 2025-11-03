# subband_onset.py
import numpy as np
from collections import deque
import scipy.signal as ss
import time

def design_bandpass(sr, lo_hz, hi_hz, order=4):
    nyq = 0.5 * sr
    lo = max(1.0, lo_hz) / nyq
    hi = min(hi_hz, 0.99 * nyq) / nyq
    sos = ss.butter(order, [lo, hi], btype='band', output='sos')
    zi = ss.sosfilt_zi(sos)
    return sos, zi

class SubBandOnsetDetector:
    def __init__(
        self,
        sample_rate=44100,
        frame_size=1024,
        hop_size=1024,
        low_band=(20, 500),
        mid_band=(500, 2000),
        high_band=(2000, 20000),
        perc_window_sec=8.0,
        percentile=90.0,
        min_space_sec=0.12,   # per-band min spacing
        smooth_tau_sec=0.12,  # EMA smoothing on novelty
    ):
        self.sr = sample_rate
        self.N = frame_size
        self.H = hop_size
        # Design filters and keep streaming states
        self.low_sos, self.low_state = design_bandpass(self.sr, *low_band)
        self.mid_sos, self.mid_state = design_bandpass(self.sr, *mid_band)
        self.high_sos, self.high_state = design_bandpass(self.sr, *high_band)

        # Previous spectra for flux
        self.prev = {
            'low': np.zeros(self.N // 2 + 1, dtype=np.float32),
            'mid': np.zeros(self.N // 2 + 1, dtype=np.float32),
            'high': np.zeros(self.N // 2 + 1, dtype=np.float32),
        }

        # Novelty buffers and thresholds
        self.perc_window = int(max(1, perc_window_sec * (self.sr / self.H)))
        self.buffers = {
            'low': deque(maxlen=self.perc_window),
            'mid': deque(maxlen=self.perc_window),
            'high': deque(maxlen=self.perc_window),
        }
        self.percentile = percentile

        # EMA smoothing for novelty
        self.alpha = (self.H / self.sr) / max(smooth_tau_sec, (self.H / self.sr))
        self.ema = {'low': 0.0, 'mid': 0.0, 'high': 0.0}

        # Peak spacing
        self.min_space_frames = int(max(1, min_space_sec * (self.sr / self.H)))
        self.last_fire = {'low': -99999, 'mid': -99999, 'high': -99999}
        self.frame_index = 0

        # Windows
        self.window = np.hanning(self.N).astype(np.float32)

    def _filter(self, band, x):
        if band == 'low':
            y, self.low_state = ss.sosfilt(self.low_sos, x, zi=self.low_state)
        elif band == 'mid':
            y, self.mid_state = ss.sosfilt(self.mid_sos, x, zi=self.mid_state)
        else:
            y, self.high_state = ss.sosfilt(self.high_sos, x, zi=self.high_state)
        return y

    def _flux(self, band, x):
        # Filter band, window, FFT magnitude
        y = self._filter(band, x) * self.window
        mag = np.abs(np.fft.rfft(y)).astype(np.float32)
        # Half-wave rectified spectral flux
        d = mag - self.prev[band]
        d[d < 0] = 0.0
        flux = float(np.sum(d))
        self.prev[band] = mag
        return flux

    def _ema(self, band, v):
        self.ema[band] = self.alpha * v + (1 - self.alpha) * self.ema[band]
        return self.ema[band]

    def process(self, chunk):
        """Return per-band onsets and intensities for this chunk."""
        # Ensure exact frame size (pad or trim)
        x = np.zeros(self.N, dtype=np.float32)
        n = min(len(chunk), self.N)
        x[:n] = chunk[:n]

        flux_vals = {b: self._flux(b, x) for b in ('low', 'mid', 'high')}
        # Smooth novelty
        nov = {b: self._ema(b, flux_vals[b]) for b in flux_vals}

        # Rolling percentile thresholds
        thr = {}
        onsets = {}
        intensities = {}
        for b in ('low', 'mid', 'high'):
            self.buffers[b].append(nov[b])
            arr = np.array(self.buffers[b], dtype=np.float32)
            t = float(np.percentile(arr, self.percentile)) if len(arr) > 8 else float(np.mean(arr) + 1e-6)
            thr[b] = t
            # Peak decision with spacing
            can_fire = (self.frame_index - self.last_fire[b]) >= self.min_space_frames
            if nov[b] > t and can_fire:
                onsets[b] = True
                intensities[b] = max(0.0, nov[b] - t)
                self.last_fire[b] = self.frame_index
            else:
                onsets[b] = False
                intensities[b] = 0.0

        self.frame_index
