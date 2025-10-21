"""
Realtime MP3 → Feature Analysis + Dual DMX Output.
Light 1: Hue Cycling (music-reactive)
Light 2: White Strobe (auto pulse)
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
from color_mapper import get_available_genres, genre_color_palettes, map_features_to_genre_color

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
    def update_lighting(self, rgbw_tuple, hue_speed, start_channel=1):
        print(f"[DMX] (noop) ch{start_channel}-{start_channel+3}: RGBW={rgbw_tuple} speed={hue_speed:.2f}")


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
# REAL-TIME STREAMING AND DUAL DMX LIGHTING
# ====================================================================

def stream_mp3_realtime(
    mp3_path: str,
    dmx,
    genre: str,
    sample_rate: int = 44100,
    channels: int = 1,
    audio_block: int = 1024,
    chunk_seconds: float = 0.25,
    hop_ratio: float = 0.5,
):
    """Stream MP3 → Analyze → Update both lights (hue + strobe)."""
    mp3_path = str(mp3_path)
    if not Path(mp3_path).exists():
        print(f"[ERR] File not found: {mp3_path}")
        return

    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-i", mp3_path,
        "-f", "f32le", "-ac", str(channels), "-ar", str(sample_rate), "pipe:1",
    ]

    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    except FileNotFoundError:
        print("[ERR] ffmpeg not found in PATH; install ffmpeg and retry")
        return

    # Countdown (Light 1 only)
    countdown_colors = [(255, 0, 0, 0), (255, 128, 0, 0), (255, 255, 0, 0)]
    for i, color in enumerate(reversed(countdown_colors), start=1):
        dmx.update_lighting(color, hue_speed=0, start_channel=1)
        print(f"Countdown: {4 - i}")
        time.sleep(1)

    # Stream setup
    bytes_per_sample = 4
    frame_bytes = audio_block * channels * bytes_per_sample
    chunk_samples = int(chunk_seconds * sample_rate)
    hop_samples = max(1, int(chunk_samples * hop_ratio))
    analysis_buffer = np.empty(0, dtype=np.float32)
    start_time = time.time()
    
    print(f"[RUN] Streaming {Path(mp3_path).name} ({genre.title()})")

    try:
        strobe_on = False
        strobe_interval = 0.15  # seconds between flashes
        last_strobe = time.time()
        
        while True:
            raw = proc.stdout.read(frame_bytes)
            if not raw or len(raw) < frame_bytes:
                break

            block = np.frombuffer(raw, dtype=np.float32)
            analysis_buffer = np.concatenate((analysis_buffer, block))

            while analysis_buffer.size >= chunk_samples:
                time_position = (len(analysis_buffer) / sample_rate)
                actual_elapsed = time.time() - start_time
                sleep_needed = time_position - actual_elapsed
                if sleep_needed > 0.005:
                    time.sleep(sleep_needed)

                window = analysis_buffer[:chunk_samples]
                analysis_buffer = analysis_buffer[hop_samples:]

                mode, key = detect_mode_key(window, sample_rate)
                tempo = detect_tempo(window, sample_rate)
                loudness = detect_loudness(window, sample_rate)
                feature_output, hue_speed = process_audio_features(
                    loudness=loudness, mode=mode, key=key, tempo=tempo
                )
                mapped_rgb = map_features_to_genre_color(
                    loudness=loudness, tempo=tempo, genre=genre
                )
                rgbw1 = (int(mapped_rgb[0]), int(mapped_rgb[1]), int(mapped_rgb[2]), 0)

                # --- Light 1: Hue Cycling ---
                dmx.update_lighting(rgbw1, hue_speed, start_channel=1)

                # --- Light 2: White Strobe ---
                now = time.time()
                if now - last_strobe >= strobe_interval:
                    strobe_on = not strobe_on
                    color2 = (255, 255, 255, 0) if strobe_on else (0, 0, 0, 0)
                    dmx.update_lighting(color2, 0, start_channel=5)
                    last_strobe = now

                print(f"[{time_position:5.2f}s] L:{loudness:5.2f}dB | T:{tempo:3.0f}bpm | RGB1:{rgbw1[:3]} | Strobe:{'ON' if strobe_on else 'off'}")

        proc.stdout.close()
        proc.wait()

    except KeyboardInterrupt:
        print("\n[STOP] Interrupted by user.")
    except Exception as e:
        print(f"[ERR] {e}")
        traceback.print_exc()


if __name__ == "__main__":
    selected_genre, mp3_file_path, dmx_port = get_user_inputs()

    print("\n--- Configuration Summary ---")
    print(f"Genre: {selected_genre.title()}")
    print(f"File: {mp3_file_path}")
    print(f"DMX Port: {dmx_port}")
    print("-----------------------------\n")

    dmx = init_dmx_controller(port=dmx_port, num_channels=9)
    
    try:
        input("Press Enter to start the music and lighting show...")
        stream_mp3_realtime(
            mp3_path=mp3_file_path,
            dmx=dmx,
            genre=selected_genre,
        )
    finally:
        dmx.stop_broadcast()
        dmx.close()
        print("\n[END] DMX broadcast stopped and port closed.")
