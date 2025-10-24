"""
Realtime MP3 → Feature Analysis + DMX output.
FINAL VERSION: Optimized for stable real-time performance (1.0s update interval).
"""

import os
import time
import platform
import subprocess
import json
import numpy as np
import traceback
from pathlib import Path

# --- Import your custom feature modules ---
from tempo_detection import detect_tempo
from loudness_detection import detect_loudness
from mode_key_detection import detect_mode_key
from audio_analyzer import process_audio_features 

# Import all necessary functions from color_mapper
from color_mapper import get_available_genres, map_features_to_genre_color 

# DMX setup (using a mock class if SimpleDMX is unavailable)
try:
    from pyserial import SimpleDMX 
except Exception as e:
    print(f"[WARN] Could not import SimpleDMX: {e}")
    SimpleDMX = None

# ====================================================================
# USER INPUT AND SETUP FUNCTIONS
# ====================================================================

def get_user_inputs():
    """Prompts the user for Genre, Audio File Path, and DMX Port."""
    
    genres = get_available_genres()
    print("=== Music-to-Light System Setup ===")
    print("Available Genres:")
    for i, genre in enumerate(genres, 1):
        print(f"{i}. {genre.title()}")
        
    while True:
        try:
            choice = input(f"\nSelect genre (1-{len(genres)}): ").strip()
            if choice.isdigit() and 1 <= int(choice) <= len(genres):
                selected_genre = genres[int(choice) - 1]
                break
            else:
                print("Invalid choice. Please enter a number from the list.")
        except ValueError:
            print("Please enter a valid number.")

    while True:
        filepath = input("\nEnter the path to your MP3 audio file: ").strip().strip('"')
        if os.path.exists(Path(filepath).expanduser()):
            filepath = str(Path(filepath).expanduser())
            break
        else:
            print("File not found. Please enter a valid path.")
            
    default_port = _suggest_default_port()
    dmx_port = input(f"\nEnter DMX port (default: {default_port}): ").strip() or default_port
    
    return selected_genre.lower(), filepath, dmx_port

def _suggest_default_port() -> str:
    """Suggests a default DMX port based on the operating system."""
    sysname = platform.system().lower()
    if sysname.startswith("win"):
        return os.environ.get("DAZZLER_DMX_PORT", "COM3") 
    if sysname == "darwin":
        return os.environ.get("DAZZLER_DMX_PORT", "/dev/tty.usbserial") 
    return os.environ.get("DAZZLER_DMX_PORT", "/dev/ttyUSB0") 


class _NoopDMX:
    """Mock DMX class for when hardware is not connected."""
    def start_broadcast(self): print("[DMX] Broadcast disabled (no hardware)")
    def stop_broadcast(self): pass
    def close(self): pass
    def update_lighting(self, rgbw_tuple, hue_speed):
        r, g, b, w = rgbw_tuple
        print(f"[{time.time():.2f}] [DMX_MOCK] R{r:3} G{g:3} B{b:3} W{w:3} speed={hue_speed:.2f}")

def init_dmx_controller(port: str | None = None, num_channels: int = 9):
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


# ====================================================================
# REAL-TIME STREAMING AND ANALYSIS (COMPUTATIONALLY OPTIMIZED)
# ====================================================================

def stream_mp3_realtime(
    mp3_path: str,
    dmx,
    genre: str,
    sample_rate: int = 44100,
    channels: int = 1,
    audio_block: int = 1024, # Read size from ffmpeg pipe
    chunk_seconds: float = 2.0, # Analysis window: 2.0s (Key to lag fix)
    hop_ratio: float = 0.5,     # Update frequency: 50% overlap, 1.0s effective update
    save_json: bool = True,
):
    """
    Stream-decode MP3 in real time, analyze features per window,
    and update DMX lighting, strictly adhering to real-time.
    """
    mp3_path = str(mp3_path)
    if not Path(mp3_path).exists():
        print(f"[ERR] File not found: {mp3_path}")
        return

    # FFMPEG Command: Decodes MP3 to raw float32le audio data
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-i", mp3_path,
        "-f", "f32le", "-ac", str(channels), "-ar", str(sample_rate), "pipe:1",
    ]

    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    except FileNotFoundError:
        print("[ERR] ffmpeg not found in PATH; install ffmpeg and retry")
        return

    # Countdown to give time for DMX initialization
    countdown_colors = [(255, 0, 0, 0), (255, 128, 0, 0), (255, 255, 0, 0)]
    print("\n--- Starting in 3 seconds ---")
    for i, color in enumerate(reversed(countdown_colors), start=1):
        dmx.update_lighting(color, hue_speed=0)
        print(f"Counting down: {4 - i}...")
        time.sleep(1)

    bytes_per_sample = 4
    frame_bytes = audio_block * channels * bytes_per_sample
    chunk_samples = int(chunk_seconds * sample_rate)
    hop_samples = max(1, int(chunk_samples * hop_ratio)) 
    analysis_buffer = np.empty(0, dtype=np.float32)
    results = []
    
    start_time = time.time() 
    
    print(f"\n[RUN] Streaming {Path(mp3_path).name} ({genre.title()}) - Update Rate: {chunk_seconds * hop_ratio:.1f}s")

    try:
        while True:
            # 1. Read a small block from ffmpeg
            raw = proc.stdout.read(frame_bytes)
            if not raw or len(raw) < frame_bytes:
                break
            
            block = np.frombuffer(raw, dtype=np.float32)
            analysis_buffer = np.concatenate((analysis_buffer, block))

            # 2. Process windows as they become available
            while analysis_buffer.size >= chunk_samples:
                
                # Calculate the IDEAL time position for this analysis window
                time_position = (len(results) * hop_samples) / sample_rate
                
                # --- CRITICAL SYNCHRONIZATION BLOCK ---
                actual_elapsed_time = time.time() - start_time
                sleep_needed = time_position - actual_elapsed_time
                
                if sleep_needed > 0.005: 
                    time.sleep(sleep_needed)
                # -------------------------------------
                
                window = analysis_buffer[:chunk_samples]
                
                # --- 3. Feature Extraction ---
                mode, key = detect_mode_key(window, sample_rate)
                tempo = detect_tempo(window, sample_rate) 
                loudness = detect_loudness(window, sample_rate) # Should now be -dBFS!

                # --- 4. Decision & Mapping ---
                feature_output, hue_speed = process_audio_features(
                    loudness=loudness, mode=mode, key=key, tempo=tempo
                )
                
                # FIX: map_features_to_genre_color only accepts 3 arguments. 
                # We remove 'mode' and 'key' to match the function signature.
                mapped_rgb = map_features_to_genre_color(
                    loudness=loudness, 
                    tempo=tempo, 
                    genre=genre
                )
                
                r, g, b = mapped_rgb
                rgbw = (int(r), int(g), int(b), 0) 
                
                # --- 5. DMX Output ---
                dmx.update_lighting(rgbw, hue_speed)
                
                # --- 6. Logging ---
                print(f"[{time_position:6.2f}s] L:{loudness:5.2f}dB | T:{tempo:3.0f}bpm | Mode:{mode:6s} | Key:{key:5s} -> RGB{rgbw[:3]}")

                results.append({
                    "time_position": time_position,
                    "features": {
                        "mode": mode, "key": key, "tempo": float(tempo), "loudness": float(loudness)
                    },
                    "lighting": {
                        "feature_output": str(feature_output), "mapped_rgbw": rgbw, "hue_speed": float(hue_speed)
                    }
                })

                # Move the buffer by the hop size
                analysis_buffer = analysis_buffer[hop_samples:]

        proc.stdout.close()
        proc.wait()

        # Save analysis data
        if save_json and results:
            out_dir = Path(__file__).parent / "outputs"
            out_dir.mkdir(parents=True, exist_ok=True)
            out_file = out_dir / f"lighting_data_{Path(mp3_path).stem}_{genre}_realtime.json"
            
            def convert_to_float(obj):
                if isinstance(obj, np.floating):
                    return float(obj)
                return obj
                
            with open(out_file, "w") as f:
                json.dump(results, f, indent=2, default=convert_to_float)
            print(f"\n[OK] Saved {len(results)} analysis windows to {out_file}")

    except KeyboardInterrupt:
        print("\n[STOP] Interrupted by user")
    except Exception as e:
        print(f"[ERR] Runtime Exception: {e}")
        proc.kill()
        traceback.print_exc()
    finally:
        pass


if __name__ == "__main__":
    
    # 1. Get User Inputs
    selected_genre, mp3_file_path, dmx_port = get_user_inputs()
    
    # Configuration calculation for display
    CHUNK = 2.0
    HOP_RATIO = 0.5
    update_interval = CHUNK * HOP_RATIO
    
    print("\n--- Configuration Summary ---")
    print(f"Genre: {selected_genre.title()}")
    print(f"File: {mp3_file_path}")
    print(f"DMX Port: {dmx_port}")
    print(f"Analysis Window: {CHUNK}s | Update Interval: {update_interval}s") 
    print("-----------------------------\n")

    # 2. Initialize DMX
    dmx = init_dmx_controller(port=dmx_port, num_channels=9) 
    
    # 3. Run Stream
    try:
        input("Press [ENTER] to start the music and lighting show... (Ctrl+C to stop)\n")
        stream_mp3_realtime(
            mp3_path=mp3_file_path,
            dmx=dmx,
            genre=selected_genre,
            chunk_seconds=CHUNK, 
            hop_ratio=HOP_RATIO,     
        )
    finally:
        # 4. Clean up DMX
        dmx.stop_broadcast()
        dmx.close()
        print("\n[END] DMX broadcast stopped and port closed.")
