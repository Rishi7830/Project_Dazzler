# audio_preprocessor.py
import numpy as np
import sounddevice as sd
from queue import Queue, Empty
import sys
from threading import Thread
import time

class AudioPreprocessor:
    def __init__(self, sample_rate=44100, block_size=1024, target_rms_db=-18.0, device=None):
        self.sample_rate = sample_rate
        self.block_size = block_size
        self.target_rms = 10 ** (target_rms_db / 20.0)
        self.window_size = int(sample_rate * 1.0)  # 1s RMS reference
        self.ring_buffer = np.zeros(self.window_size, dtype=np.float32)
        self.buffer_pos = 0
        self.output_queue = Queue(maxsize=64)
        self.device = device
        self.stream = None
        self.thread = None
        self.is_running = False

    def _rms_normalize(self, chunk: np.ndarray) -> np.ndarray:
        n = len(chunk)
        if self.buffer_pos + n > self.window_size:
            wrap = self.window_size - self.buffer_pos
            self.ring_buffer[self.buffer_pos:] = chunk[:wrap]
            self.ring_buffer[:n - wrap] = chunk[wrap:]
            self.buffer_pos = n - wrap
        else:
            self.ring_buffer[self.buffer_pos:self.buffer_pos + n] = chunk
            self.buffer_pos += n

        current_rms = float(np.sqrt(np.mean(self.ring_buffer**2) + 1e-12))
        if current_rms > 0:
            gain = min(self.target_rms / current_rms, 2.0)  # clamp 2x
            out = np.clip(chunk * gain, -0.95, 0.95)
        else:
            out = chunk
        return out.astype(np.float32, copy=False)

    def _callback(self, indata, frames, time_info, status):
        if status:
            print(f"[Audio] {status}", file=sys.stderr)
        # mixdown to mono if needed
        if indata.ndim == 2 and indata.shape[1] > 1:
            audio = indata.mean(axis=1).astype(np.float32)
        else:
            audio = indata.reshape(-1).astype(np.float32)
        norm = self._rms_normalize(audio)
        try:
            self.output_queue.put_nowait(norm.copy())
        except:
            pass

    def start(self):
        if self.is_running:
            return
        dev = self.device if self.device is not None else sd.default.device[0]
        info = sd.query_devices(dev)
        if info['max_input_channels'] == 0:
            raise RuntimeError(f"Audio device {dev} has no input channels")
        self.is_running = True
        self.stream = sd.InputStream(
            device=dev,
            channels=1,
            samplerate=self.sample_rate,
            blocksize=self.block_size,
            dtype='float32',
            callback=self._callback,
            latency='low',
        )
        self.stream.start()
        self.thread = Thread(target=self._pump, daemon=True)
        self.thread.start()

    def _pump(self):
        # Keep a small heartbeat to allow graceful shutdowns
        while self.is_running:
            time.sleep(0.05)

    def get_normalized_chunk(self) -> np.ndarray:
        try:
            return self.output_queue.get_nowait()
        except Empty:
            return np.zeros(self.block_size, dtype=np.float32)

    def stop(self):
        self.is_running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1.0)
        if self.stream:
            try:
                self.stream.stop()
                self.stream.close()
            except:
                pass
        # drain queue
        while not self.output_queue.empty():
            try:
                self.output_queue.get_nowait()
            except Empty:
                break
