"""
Realtime MP3 → Feature Analysis + DMX output (no audio playback for WSL)
Dynamic version: inputs MP3 path, Genre, and DMX Port from the user.
Requires ffmpeg, local feature modules, and color_mapper.map_to_colors, pyserial.SimpleDMX
"""

import os
import time
import platform
import subprocess
from pathlib import Path
import numpy as np

# Import your custom modules
from tempo_detection import detect_tempo
from loudness_detection import detect_loudness
from mode_key_detection import detect_mode_key
from audio_analyzer import process_audio_features

# NOTE: Assuming color_mapper.py contains the map_mood_to_genre_color and get_available_genres functions
from color_mapper import map_to_colors, get_available_genres 

try:
    from pyserial import SimpleDMX
except Exception as e:
    print(f"[WARN] Could not import SimpleDMX: {e}")
    SimpleDMX = None


def get_user_inputs():
    """Prompts the user for Genre, Audio File Path, and DMX Port."""
    
    # 1. Select Genre
    genres = get_available_genres()
    print("=== Music-to-Light System Setup ===")
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

    # 2. Enter Audio File Path
    while True:
        filepath = input("\nEnter the path to your MP3 audio file: ").strip().strip('"')
        if os.path.exists(filepath):
            break
        else:
            print("File not found. Please enter a valid path.")
            
    # 3. Enter DMX Port
    default_port = _suggest_default_port()
    dmx_port = input(f"\nEnter DMX port (default: {default_port}): ").strip() or default_port
    
    return selected_genre.lower(), filepath, dmx_port

def _suggest_default_port() -> str:
    """Suggests a default DMX port based on the operating system."""
    sysname = platform.system().lower()
    if sysname.startswith("win"):
        # Commonly used DMX on Windows or /dev/ttyS0 if in WSL
        return os.environ.get("DAZZLER_DMX_PORT", "COM3") 
    if sysname == "darwin":
        # Common USB serial port on macOS
        return os.environ.get("DAZZLER_DMX_PORT", "/dev/tty.usbserial") 
    # Default for Linux/WSL
    return os.environ.get("DAZZLER_DMX_PORT", "/dev/ttyUSB0") 


class _NoopDMX:
    def start_broadcast(self): print("[DMX] Broadcast disabled (no hardware)")
    def stop_broadcast(self): pass
    def close(self): pass
    def update_lighting(self, rgbw_tuple, hue_speed):
        print(f"[DMX] (noop) R{rgbw_tuple[0]} G{rgbw_tuple[1]} B{rgbw_tuple[2]} speed={hue_speed:.2f}")

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


def stream_mp3_realtime(
    mp3_path: str,
    dmx,
    genre: str, # Added genre parameter
    sample_rate: int = 44100,
    channels: int = 1,
    audio_block: int = 1024,
    chunk_seconds: float = 0.25,
    hop_ratio: float = 0.5,
    save_json: bool = True,
):
    """
    Stream-decode MP3 in real time, analyze features per window,
    update DMX lighting, print progress, and skip audio playback in WSL.
    """
    mp3_path = str(mp3_path)
    if not Path(mp3_path).exists():
        print(f"[ERR] File not found: {mp3_path}")
        return

    cmd = [
        "ffmpeg",
        "-hide_banner", "-loglevel", "error",
        "-i", mp3_path,
        "-f", "f32le",
        "-ac", str(channels),
        "-ar", str(sample_rate),
        "pipe:1",
    ]

    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    except FileNotFoundError:
        print("[ERR] ffmpeg not found in PATH; install ffmpeg and retry")
        return

    # 3-2-1 countdown: lights and terminal in sync
    countdown_colors = [
        (255,   0,   0, 0),  # Red for 3
        (255, 128,   0, 0),  # Orange for 2
        (255, 255,   0, 0)   # Yellow for 1
    ]
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

    print(f"[RUN] Streaming {mp3_path} ({genre}) at {sample_rate} Hz - chunk={chunk_seconds}s, hop={hop_ratio}")

    try:
        while True:
            raw = proc.stdout.read(frame_bytes)
            if not raw or len(raw) < frame_bytes:
                break

            block = np.frombuffer(raw, dtype=np.float32)
            analysis_buffer = np.concatenate((analysis_buffer, block))

            while analysis_buffer.size >= chunk_samples:
                elapsed = time.time() - start_time
                time_position = (len(results) * hop_samples) / sample_rate
                
                # --- Analysis ---
                window = analysis_buffer[:chunk_samples]
                mode, key = detect_mode_key(window, sample_rate)
                tempo = detect_tempo(window, sample_rate)
                loudness = detect_loudness(window, sample_rate)

                # Use your audio_analyzer and color_mapper modules
                # NOTE: I am assuming process_audio_features is what determines the 'mood' (color_name)
                # and 'hue_speed' based on the features.
                color_name, hue_speed = process_audio_features(
                    loudness=loudness, mode=mode, key=key, tempo=tempo
                )
                
                # Use map_mood_to_genre_color (from color_mapper) to get the genre-mapped color
                mapped_rgb = map_mood_to_genre_color(color_name, genre)
                
                r, g, b = mapped_rgb
                # Assuming W channel is 0 for RGB effects
                rgbw = (int(r), int(g), int(b), 0) 
                
                # --- DMX Output ---
                dmx.update_lighting(rgbw, hue_speed)
                
                # --- Logging ---
                print(f"[{time_position:6.2f}s] L:{loudness:5.2f}dB | T:{tempo:3.0f}bpm | Mood:{color_name:12s} -> RGB{rgbw[:3]}")


                results.append({
                    "time_position": time_position,
                    "features": {
                        "mode": mode,
                        "key": key,
                        "tempo": float(tempo),
                        "loudness": float(loudness)
                    },
                    "lighting": {
                        "color_name": color_name,
                        "mapped_rgbw": rgbw,
                        "hue_speed": float(hue_speed)
                    }
                })

                analysis_buffer = analysis_buffer[hop_samples:]

        proc.stdout.close()
        proc.wait()

        if save_json and results:
            out_dir = Path(__file__).parent / "outputs"
            out_dir.mkdir(parents=True, exist_ok=True)
            out_file = out_dir / f"lighting_data_{Path(mp3_path).stem}_realtime.json"
            import json
            with open(out_file, "w") as f:
                # Use a custom function or lambda to handle numpy float types
                # which are not JSON serializable, if necessary.
                def convert_to_float(obj):
                    if isinstance(obj, np.floating):
                        return float(obj)
                    return obj
                    
                json.dump(results, f, indent=2, default=convert_to_float)
            print(f"\n[OK] Saved {len(results)} analysis windows to {out_file}")

    except KeyboardInterrupt:
        print("\n[STOP] Interrupted by user")

    except Exception as e:
        print(f"[ERR] Exception: {e}")
        proc.kill() # Ensure ffmpeg process is stopped

    finally:
        pass


if __name__ == "__main__":
    # --- Get User Inputs ---
    selected_genre, mp3_file_path, dmx_port = get_user_inputs()
    
    print("\n--- Configuration Summary ---")
    print(f"Genre: {selected_genre.title()}")
    print(f"File: {mp3_file_path}")
    print(f"DMX Port: {dmx_port}")
    print("-----------------------------\n")

    # --- Initialize DMX ---
    dmx = init_dmx_controller(port=dmx_port, num_channels=9) 
    
    # --- Run Stream ---
    try:
        stream_mp3_realtime(
            mp3_path=mp3_file_path,
            dmx=dmx,
            genre=selected_genre, # Pass the genre to the streaming function
            sample_rate=44100,
            channels=1,
            audio_block=1024,
            chunk_seconds=0.25,
            hop_ratio=0.5,
            save_json=True,
        )
    finally:
        # --- Clean up DMX ---
        dmx.stop_broadcast()
        dmx.close()
        print("\n[END] DMX broadcast stopped and port closed.")
