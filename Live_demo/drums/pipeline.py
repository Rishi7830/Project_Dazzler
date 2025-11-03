import sounddevice as sd
import time
import numpy as np
import threading
import signal
import sys
from audio_preprocessor import AudioPreprocessor
from onset_detector import OnsetDetector
from pyserial_dmx import SimpleDMX, CH_RED, CH_GREEN, CH_BLUE, CH_DIMMER

# --- Configuration ---
DMX_PORT = 'COM14'  # <<< CHANGE THIS to your DMX adapter's COM port
# ---------------------

shutdown_flag = False

def signal_handler(sig, frame):
    global shutdown_flag
    if not shutdown_flag:
        print("\nInterrupt received—shutting down...")
        shutdown_flag = True

def dmx_trigger_callback(dmx_controller, onset_time, onset_strength, audio_chunk):
    # This function is called every time an onset is detected
    if not dmx_controller or not dmx_controller.ser:
        return # Do nothing if DMX is not available

    # 1. Calculate loudness (RMS) and map to Dimmer channel
    rms = np.sqrt(np.mean(audio_chunk**2))
    dimmer = min(int(rms * 255 * 5), 255) # Multiplier makes it more sensitive
    dmx_controller.set_channel_internal(CH_DIMMER, dimmer)

    # 2. Calculate a color based on time and set RGB channels
    hue_offset = int(time.time() * 50) % 360
    color_r = int(127 + 127 * np.sin(np.radians(hue_offset)))
    color_g = int(127 + 127 * np.sin(np.radians(hue_offset + 120)))
    color_b = int(127 + 127 * np.sin(np.radians(hue_offset + 240)))
    dmx_controller.set_channel_internal(CH_RED, color_r)
    dmx_controller.set_channel_internal(CH_GREEN, color_g)
    dmx_controller.set_channel_internal(CH_BLUE, color_b)

    # 3. Print detailed log for analysis
    print(f"🎵 Onset Detected: Strength={onset_strength:.2f} | RMS={rms:.4f} | Dimmer={dimmer} | RGB=({color_r},{color_g},{color_b})")

class DazzlerPipeline:
    def __init__(self, sample_rate=44100, block_size=512, audio_device_id=1, dmx_port=DMX_PORT):
        self.sample_rate = sample_rate
        self.block_size = block_size
        self.audio_device_id = audio_device_id
        self.dmx_port = dmx_port
        self.preprocessor = None
        self.detector = None
        self.dmx_controller = None

    def start(self):
        global shutdown_flag
        signal.signal(signal.SIGINT, signal_handler)
        
        print("=== Dazzler Real-Time Audio & DMX Pipeline ===")
        print(f"Audio Config: Sample Rate={self.sample_rate}Hz, Block Size={self.block_size}, Device={self.audio_device_id}")
        print(f"DMX Config: Port={self.dmx_port}")
        
        # --- Initialize Audio ---
        try:
            sd.check_input_settings(device=self.audio_device_id, channels=1, samplerate=self.sample_rate)
            device_info = sd.query_devices(self.audio_device_id)
            print(f"✓ Audio Device verified: {device_info['name']}")
        except Exception as e:
            print(f"Fatal: Error accessing audio device {self.audio_device_id}: {e}", file=sys.stderr)
            sys.exit(1)
            
        # --- Initialize DMX ---
        self.dmx_controller = SimpleDMX(port=self.dmx_port)
        if not self.dmx_controller.ser:
            print("Warning: DMX controller failed to initialize. Running in audio-only mode.", file=sys.stderr)
        
        # --- Initialize Pipeline Components ---
        self.preprocessor = AudioPreprocessor(sample_rate=self.sample_rate, block_size=self.block_size, device=self.audio_device_id)
        self.detector = OnsetDetector(sample_rate=self.sample_rate, block_size=self.block_size, threshold=0.35)
        
        # Pass the dmx_controller object to the callback
        self.detector.set_dmx_callback(lambda time, strength, chunk: dmx_trigger_callback(self.dmx_controller, time, strength, chunk))
        
        print("✓ Components initialized—starting threads...")
        
        # --- Start Threads ---
        self.preprocessor.start()
        self.dmx_controller.start_broadcast() # Start DMX refresh loop
        time.sleep(1.0)
        
        if not self.preprocessor.is_running:
             print("Fatal: Preprocessor failed to start stream. Exiting.", file=sys.stderr)
             self.stop()
             return

        self.detector.start(self.preprocessor)
        
        print("🚀 Pipeline running! Play music through ProFx mixer. Ctrl+C to stop.")
        
        while not shutdown_flag:
            time.sleep(0.1)
            
        self.stop()

    def stop(self):
        print("Stopping pipeline components...")
        if self.detector: self.detector.stop()
        if self.preprocessor: self.preprocessor.stop()
        if self.dmx_controller: self.dmx_controller.close() # Safely closes DMX port
        
        print("\n=== Pipeline Shutdown Complete ===")

if __name__ == "__main__":
    pipeline = DazzlerPipeline(audio_device_id=1, dmx_port=DMX_PORT)
    pipeline.start()
