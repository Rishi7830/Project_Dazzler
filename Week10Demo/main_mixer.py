"""
Realtime Live Audio (Mixer/USB Input) → Feature Analysis + DMX output.
Using plughw for more resilient ALSA device access.
"""

import os
import time
import platform
import subprocess
import json
import numpy as np
import traceback
from pathlib import Path

# Import your custom feature modules
from tempo_detection import detect_tempo
from loudness_detection import detect_loudness
from mode_key_detection import detect_mode_key
from audio_analyzer import process_audio_features

# Import all necessary functions from color_mapper
from color_mapper import map_features_to_genre_color

try:
    from pyserial_new import SimpleDMX
except Exception as e:
    print(f"[WARN] Could not import SimpleDMX: {e}")
    SimpleDMX = None

# --- CONFIGURATION (HARDCODED) ---

# The DMX port connected to your DMX controller (e.g., /dev/ttyUSB0 on Linux)
DMX_PORT = "/dev/ttyUSB0" 

# The ALSA device ID for your USB mixer (Mackie ProFx). Using the plughw alias.
# CHANGE THIS LINE: hw:0,0 -> plughw:CARD=ProFx,DEV=0
MIXER_DEVICE_ID = "plughw:CARD=ProFx,DEV=0" 

# The musical genre for color mapping
SELECTED_GENRE = "indie" 
# --- END CONFIGURATION ---

# --- DMX Initialization Functions (Kept for completeness) ---

def _suggest_default_port() -> str:
    """Suggests a default DMX port based on the operating system."""
    sysname = platform.system().lower()
    if sysname.startswith("win"):
        return os.environ.get("DAZZLER_DMX_PORT", "COM3")
    if sysname == "darwin":
        return os.environ.get("DAZZLER_DMX_PORT", "/dev/tty.usbserial")
    return os.environ.get("DAZZLER_DMX_PORT", "/dev/ttyUSB1")


class _NoopDMX:
    def start_broadcast(self): print("[DMX] Broadcast disabled (no hardware)")
    def stop_broadcast(self): pass
    def close(self): pass
    def update_lighting(self, rgbw_tuple, hue_speed):
        print(f"[DMX] (noop) R{rgbw_tuple[0]} G{rgbw_tuple[1]} B{rgbw_tuple[2]} W{rgbw_tuple[3]} speed={hue_speed:.2f}")

def init_dmx_controller(port: str | None = None, num_channels: int = 18):
    if SimpleDMX is None:
        return _NoopDMX()
    port = port or _suggest_default_port()
    try:
        dmx = SimpleDMX(port=port)
        dmx.start_broadcast()
        print(f"[DMX] Started on {port} channels={num_channels}")
        return dmx
    except Exception as e:
        print(f"[DMX] Could not open {port}: {e} -> using noop")
        return _NoopDMX()


# --- REAL-TIME STREAMING AND ANALYSIS (LIVE INPUT) ---

def stream_audio_realtime(
    device_id: str,
    dmx,
    genre: str,
    sample_rate: int = 44100,
    channels: int = 2,
    audio_block: int = 1024,
    chunk_seconds: float = 0.25,
    hop_ratio: float = 0.5,
    save_json: bool = True,
):
    """
    Stream-capture live audio from a USB mixer device, analyze features per window.
    """
    
    # FFmpeg Command for Live Capture (Linux/ALSA)
    input_format = "alsa" 
    input_device = device_id
        
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", 
        # Input source parameters
        "-f", input_format, 
        "-i", input_device,
        # Output pipe parameters
        "-f", "f32le", "-ac", str(channels), "-ar", str(sample_rate), "pipe:1",
    ]

    print(f"\n[FFMPEG] Capture command: {' '.join(cmd)}")
    print(f"[NOTE] Attempting to open ALSA device: {device_id}")

    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    except FileNotFoundError:
        print("[ERR] ffmpeg not found in PATH; install ffmpeg and retry")
        return
    except Exception as e:
        print(f"[ERR] Failed to start ffmpeg process: {e}")
        return

    # 3-2-1 countdown
    countdown_colors = [(255, 0, 0, 0), (255, 128, 0, 0), (255, 255, 0, 0)]
    for i, color in enumerate(reversed(countdown_colors), start=1):
        dmx.update_lighting(color, hue_speed=0)
        print(f"Countdown: {4 - i}")
        time.sleep(1)
        
    bytes_per_sample = 4
    frame_bytes = audio_block * channels * bytes_per_sample
    chunk_samples = int(chunk_seconds * sample_rate)
    hop_samples = max(1, int(chunk_samples * hop_ratio))
    analysis_buffer = np.empty(0, dtype=np.float32) 
    results = []
    
    start_time = time.time()
    strobe_toggle = False    

    print(f"[RUN] Streaming Live Audio from '{device_id}' ({genre.title()}) - chunk={chunk_seconds}s, hop={hop_ratio}")

    try:
        while True:
            raw = proc.stdout.read(frame_bytes)
            if not raw or len(raw) < frame_bytes:
                print("[WARN] FFMPEG stream ended unexpectedly. Check mixer connection.")
                break
            
            time.sleep(0.001) 
            
            block = np.frombuffer(raw, dtype=np.float32)
            analysis_buffer = np.concatenate((analysis_buffer, block))

            while analysis_buffer.size >= chunk_samples:
                
                # Real-Time Sync Logic
                time_position = (len(results) * hop_samples) / sample_rate
                actual_elapsed_time = time.time() - start_time
                sleep_needed = time_position - actual_elapsed_time
                if sleep_needed > 0.005:
                    time.sleep(sleep_needed)

                window = analysis_buffer[:chunk_samples]
                
                # Mix to mono for analysis (assuming stereo input)
                window_mono = window.reshape(-1, channels).mean(axis=1) 
                
                # Feature Analysis
                mode, key = detect_mode_key(window_mono, sample_rate)
                tempo = detect_tempo(window_mono, sample_rate)
                loudness = detect_loudness(window_mono, sample_rate)
                feature_output, hue_speed = process_audio_features(
                    loudness=loudness, mode=mode, key=key, tempo=tempo
                )

                # DMX Output Logic
                if loudness > 80:
                    strobe_toggle = not strobe_toggle
                    rgbw = (0, 0, 0, 255) if strobe_toggle else (0, 0, 0, 0)
                    dmx.update_lighting(rgbw, hue_speed)
                else:
                    mapped_rgb = map_features_to_genre_color(loudness=loudness, tempo=tempo, genre=genre)
                    r, g, b = mapped_rgb
                    rgbw = (int(r), int(g), int(b), 0) 
                    dmx.update_lighting(rgbw, hue_speed)

                print(f"[{time_position:6.2f}s] L:{loudness:5.2f}dB | T:{tempo:3.0f}bpm | Feature:{str(feature_output):12s} -> RGBW{rgbw}")

                # Data Recording
                results.append({
                    "time_position": time_position,
                    "features": {"mode": mode, "key": key, "tempo": float(tempo), "loudness": float(loudness)},
                    "lighting": {"feature_output": str(feature_output), "mapped_rgbw": rgbw, "hue_speed": float(hue_speed)}
                })

                analysis_buffer = analysis_buffer[hop_samples:]

    except KeyboardInterrupt:
        print("\n[STOP] Interrupted by user")
    except Exception as e:
        print(f"[ERR] Runtime Exception: {e}")
        proc.kill()
        traceback.print_exc()
    finally:
        # Clean up ffmpeg subprocess
        if 'proc' in locals() and proc.poll() is None:
            proc.terminate()
            proc.wait(timeout=1)
        
        # Save analysis data
        if save_json and results:
            out_dir = Path(__file__).parent / "outputs"
            out_dir.mkdir(parents=True, exist_ok=True)
            out_file = out_dir / f"lighting_data_LIVE_MIXER_{genre}_realtime.json"
            
            def convert_to_float(obj):
                if isinstance(obj, np.floating):
                    return float(obj)
                return obj
                
            with open(out_file, "w") as f:
                json.dump(results, f, indent=2, default=convert_to_float)
            print(f"\n[OK] Saved {len(results)} analysis windows to {out_file}")


if __name__ == "__main__":
    
    # Use the hardcoded values
    selected_genre = SELECTED_GENRE
    mixer_device_id = MIXER_DEVICE_ID
    dmx_port = DMX_PORT
    
    print("\n--- Configuration Summary ---")
    print(f"Genre: {selected_genre.title()}")
    print(f"Audio Device: **{mixer_device_id}**")
    print(f"DMX Port: {dmx_port}")
    print(f"Update Rate: {0.25} seconds (Responsive)")
    print("-----------------------------\n")

    dmx = init_dmx_controller(port=dmx_port, num_channels=18)
    
    try:
        print("Starting the live audio analysis and lighting show...")
        stream_audio_realtime( 
            device_id=mixer_device_id,
            dmx=dmx,
            genre=selected_genre,
            chunk_seconds=0.25,
            hop_ratio=0.5,
            channels=2, # Assuming stereo mixer input
        )
    finally:
        dmx.stop_broadcast()
        dmx.close()
        print("\n[END] DMX broadcast stopped and port closed.")
