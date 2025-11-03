import numpy as np
import librosa
from queue import Empty
import time
import threading
import sys

class OnsetDetector:
    def __init__(self, sample_rate=44100, block_size=512, hop_length=256, threshold=0.35):
        self.sample_rate = sample_rate
        self.block_size = block_size
        self.hop_length = hop_length
        self.threshold = threshold
        self.onset_frames = []
        self.is_running = False
        self.detection_thread = None
        self.dmx_trigger_callback = None

    def set_dmx_callback(self, callback):
        self.dmx_trigger_callback = callback

    def detect_onsets(self, normalized_chunk):
        self.onset_frames.append(normalized_chunk)
        
        if len(self.onset_frames) >= 2:
            frame = np.concatenate(self.onset_frames)
            self.onset_frames = []
            
            try:
                onset_env = librosa.onset.onset_strength(
                    y=frame, 
                    sr=self.sample_rate, 
                    hop_length=self.hop_length,
                    aggregate=np.median,
                    fmax=8000,
                    n_fft=1024
                )
                
                onsets = librosa.util.peak_pick(
                    onset_env, 
                    pre_max=3, post_max=3,
                    pre_avg=3, post_avg=3,
                    delta=self.threshold,
                    wait=8
                )
                
                if len(onsets) > 0:
                    latest_onset_frame = onsets[-1]
                    onset_strength = onset_env[latest_onset_frame] # Get the strength of the peak
                    onset_time = librosa.frames_to_time(latest_onset_frame, sr=self.sample_rate, hop_length=self.hop_length)
                    return onset_time, onset_strength # Return both time and strength
                    
            except Exception as e:
                print(f"Onset detection error: {e}", file=sys.stderr)
        
        return None

    def detection_loop(self, preprocessor):
        print("Onset detector thread started—processing audio.")
        
        while self.is_running:
            chunk = preprocessor.get_normalized_chunk()
            if np.any(chunk):
                onset_info = self.detect_onsets(chunk) # Now returns a tuple (time, strength)
                
                if onset_info is not None:
                    onset_time, onset_strength = onset_info
                    if self.dmx_trigger_callback:
                        self.dmx_trigger_callback(onset_time, onset_strength, chunk)
            
            time.sleep(0.005)

    def start(self, preprocessor):
        if self.is_running:
            return
        self.is_running = True
        self.detection_thread = threading.Thread(target=self.detection_loop, args=(preprocessor,))
        self.detection_thread.daemon = True
        self.detection_thread.start()

    def stop(self):
        self.is_running = False
        if self.detection_thread and self.detection_thread.is_alive():
            self.detection_thread.join(timeout=1.0)
        print("Onset detector stopped.")
