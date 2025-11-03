import numpy as np
import sounddevice as sd
from queue import Queue, Empty
import time
from threading import Thread
import sys

class AudioPreprocessor:
    def __init__(self, sample_rate=44100, block_size=512, target_rms_db=-18, window_sec=1.0, device=1):
        self.sample_rate = sample_rate
        self.block_size = block_size
        self.target_rms = 10**(target_rms_db / 20.0)
        self.window_size = int(sample_rate * window_sec)
        self.ring_buffer = np.zeros(self.window_size)
        self.buffer_pos = 0
        self.output_queue = Queue(maxsize=30)
        self.is_running = False
        self.device = device
        self.stream = None
        self.stream_thread = None

    def rms_normalize(self, audio_chunk):
        chunk_len = len(audio_chunk)
        if self.buffer_pos + chunk_len > self.window_size:
            wrap = self.window_size - self.buffer_pos
            self.ring_buffer[self.buffer_pos:] = audio_chunk[:wrap]
            self.ring_buffer[:chunk_len - wrap] = audio_chunk[wrap:]
            self.buffer_pos = chunk_len - wrap
        else:
            self.ring_buffer[self.buffer_pos:self.buffer_pos + chunk_len] = audio_chunk
            self.buffer_pos += chunk_len

        current_rms = np.sqrt(np.mean(self.ring_buffer**2))
        
        if current_rms > 0:
            gain = min(self.target_rms / current_rms, 2.0)
            normalized = audio_chunk * gain
            normalized = np.clip(normalized, -0.95, 0.95)
        else:
            normalized = audio_chunk

        return normalized

    def audio_callback(self, indata, frames, time_info, status):
        if status:
            print(f"Audio warning: {status}", file=sys.stderr)
        
        if len(indata.shape) > 1 and indata.shape[1] > 1:
            audio = indata.mean(axis=1).astype(np.float32)
        else:
            audio = indata.flatten().astype(np.float32)
        
        normalized = self.rms_normalize(audio)
        
        try:
            self.output_queue.put_nowait(normalized.copy())
        except:
            pass # Silently drop if queue is full, should be rare

    def start(self):
        try:
            device_info = sd.query_devices(self.device)
            if device_info['max_input_channels'] == 0:
                raise ValueError(f"Device {self.device} has no input channels.")
            
            print(f"Starting preprocessor on device {self.device}: {device_info['name']}")
            
            self.is_running = True
            
            self.stream_thread = Thread(target=self._run_stream)
            self.stream_thread.daemon = True
            self.stream_thread.start()
            
        except Exception as e:
            print(f"Failed to start audio device: {e}", file=sys.stderr)
            raise

    def _run_stream(self):
        try:
            self.stream = sd.InputStream(
                device=self.device,
                channels=min(2, sd.query_devices(self.device)['max_input_channels']),
                samplerate=self.sample_rate,
                blocksize=self.block_size,
                dtype='float32',
                callback=self.audio_callback,
                latency='low'
            )
            self.stream.start()
            print(f"Preprocessor running—input normalized to ~{-20 * np.log10(self.target_rms):.1f} dBFS RMS.")
            
            while self.is_running:
                time.sleep(0.1)
                
        except Exception as e:
            print(f"Stream error: {e}", file=sys.stderr)
            self.is_running = False
        finally:
            if self.stream and self.stream.active:
                self.stream.stop()
                self.stream.close()

    def stop(self):
        self.is_running = False
        if self.stream_thread and self.stream_thread.is_alive():
             self.stream_thread.join(timeout=1.0)
        while not self.output_queue.empty():
            try:
                self.output_queue.get_nowait()
            except Empty:
                break
        print("Preprocessor stopped.")

    def get_normalized_chunk(self):
        try:
            return self.output_queue.get_nowait()
        except Empty:
            return np.zeros(self.block_size, dtype=np.float32)
