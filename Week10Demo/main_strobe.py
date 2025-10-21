"""
Realtime MP3 → Feature Analysis + Dual-Light DMX output.
Light 1: Hue Cycling / Color Mapping
Light 2: Daisy-Chained White Strobe (tempo or loudness based)
"""

import os
import time
import platform
import subprocess
import json
import numpy as np
import traceback
from pathlib import Path

# Custom imports (unchanged)
from tempo_detection import detect_tempo
from loudness_detection import detect_loudness
from mode_key_detection import detect_mode_key
from audio_analyzer import process_audio_features
from color_mapper import get_available_genres, genre_color_palettes, map_features_to_genre_color

try:
    from pyserial import SimpleDMX
except Exception as e:
    print(f"[WARN] Could not import SimpleDMX: {e}")
    SimpleDMX = None


# ====================================================================
# USER INPUT + DMX SETUP
# ====================================================================
def get_user_inputs():
    genres = get_available_genres()
    print("=== Music-to-Light System Setup ===")
    print("Available Genres:")
    for i, genre in enumerate(genres, 1):
        print(f"{i}. {genre.title()}")

    while True:
        choice = input(f"\nSelect genre (1-{len(genres)}): ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(genres):
            selected_genre = genres[int(choice) - 1]
            break
        print("Invalid choice. Try again.")

    while True:
        filepath = input("\nEnter the path to your MP3 audio file: ").strip().strip('"')
        if os.path.exists(Path(filepath).expanduser()):
            filepath = str(Path(filepath).expanduser())
            break
        print("File not found. Try again.")

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
    def update_lighting(self, rgbw_1, rgbw_2, hue_speed):
        print(f"[DMX] (noop) L1{rgbw_1[:3]} L2{rgbw_2[:3]} speed={hue_speed:.2f}")


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
# REAL-TIME STREAMING + DUAL LIGHT CONTROL
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
        print("[ERR] ffmpeg not found in PATH.")
        return

    countdown_colors = [(255, 0, 0, 0), (255, 128, 0, 0), (255, 255, 0, 0)]
    for i, color in enumerate(reversed(countdown_colors), start=1):
        dmx.update_lighting(color, (0, 0, 0, 0), hue_speed=0)
        print(f"Countdown: {4 - i}")
        time.sleep(1)

    bytes_per_sample = 4
    frame_bytes = audio_block * channels * bytes_per_sample
    chunk_samples = int(chunk_seconds * sample_rate)
    hop_samples = max(1, int(chunk_samples * hop_ratio))
    analysis_buffer = np.empty(0, dtype=np.float32)

    print(f"[RUN] {Path(mp3_path).name} ({genre}) - dual light mode")
    start_time = time.time()

    try:
        while True:
            raw = proc.stdout.read(frame_bytes)
            if not raw or len(raw) < frame_bytes:
                break

            block = np.frombuffer(raw, dtype=np.float32)
            analysis_buffer = np.concatenate((analysis_buffer, block))

            while analysis_buffer.size >= chunk_samples:
                time_position = (len(block) / sample_rate)
                actual_elapsed = time.time() - start_time
                sleep_needed = time_position - actual_elapsed
                if sleep_needed > 0:
                    time.sleep(sleep_needed)

                window = analysis_buffer[:chunk_samples]
                mode, key = detect_mode_key(window, sample_rate)
                tempo = detect_tempo(window, sample_rate)
                loudness = detect_loudness(window, sample_rate)
                feature_output, hue_speed = process_audio_features(
                    loudness=loudness, mode=mode, key=key, tempo=tempo
                )

                # ---------- Light 1: Hue-cycle color ----------
                r, g, b = map_features_to_genre_color(
                    loudness=loudness, tempo=tempo, genre=genre
                )
                rgbw_1 = (int(r), int(g), int(b), 0)

                # ---------- Light 2: Daisy-chain strobe ----------
                # Strobe flashes white based on loudness/tempo
                strobe_intensity = max(0, min(255, int((loudness + 60) * 4)))
                strobe_rate = 1 / max(1, tempo / 60.0)  # flash ~1 per beat
                flash = (255, 255, 255, 255) if (time.time() % strobe_rate) < (strobe_rate / 2) else (0, 0, 0, 0)
                rgbw_2 = tuple(int(x * strobe_intensity / 255) for x in flash)

                # ---------- DMX OUTPUT ----------
                dmx.update_lighting(rgbw_1, rgbw_2, hue_speed)
                print(f"[LIGHT] H1{rgbw_1[:3]} | H2{rgbw_2[:3]} | L={loudness:.1f}dB T={tempo:.1f}bpm")

                analysis_buffer = analysis_buffer[hop_samples:]

    except KeyboardInterrupt:
        print("\n[STOP] Interrupted by user")
    finally:
        proc.kill()
        proc.stdout.close()


# ====================================================================
# ENTRY POINT
# ====================================================================
if __name__ == "__main__":
    genre, mp3_file, dmx_port = get_user_inputs()
    print(f"\nGenre: {genre.title()} | File: {mp3_file} | Port: {dmx_port}\n")

    dmx = init_dmx_controller(port=dmx_port, num_channels=9)

    try:
        input("Press Enter to start the show...")
        stream_mp3_realtime(mp3_file, dmx, genre)
    finally:
        dmx.stop_broadcast()
        dmx.close()
        print("[END] DMX broadcast stopped.")
