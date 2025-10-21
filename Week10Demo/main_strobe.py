"""
Realtime MP3 → Feature Analysis + Dual Light DMX output.
FINAL VERSION: Light 1 hue cycles based on song features,
Light 2 (daisy-chained) strobes in tempo-synchronized bursts.
"""

import os
import time
import platform
import subprocess
import json
import numpy as np
import traceback
from pathlib import Path

# === Custom feature modules ===
from tempo_detection import detect_tempo
from loudness_detection import detect_loudness
from mode_key_detection import detect_mode_key
from audio_analyzer import process_audio_features

# === Color mapping ===
from color_mapper import get_available_genres, genre_color_palettes, map_features_to_genre_color

try:
    from pyserial import SimpleDMX
except Exception as e:
    print(f"[WARN] Could not import SimpleDMX: {e}")
    SimpleDMX = None


# ====================================================================
# USER INPUT + DMX INITIALIZATION
# ====================================================================

def get_user_inputs():
    genres = get_available_genres()
    print("=== Music-to-Light System Setup ===")
    for i, genre in enumerate(genres, 1):
        print(f"{i}. {genre.title()}")
    while True:
        choice = input(f"\nSelect genre (1-{len(genres)}): ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(genres):
            selected_genre = genres[int(choice) - 1]
            break
        print("Invalid choice. Please enter a number from the list.")
    while True:
        filepath = input("\nEnter the path to your MP3 audio file: ").strip().strip('"')
        if os.path.exists(Path(filepath).expanduser()):
            filepath = str(Path(filepath).expanduser())
            break
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
    def update_dual_lighting(self, rgbw1, rgbw2, hue_speed):  # mimic real call
        print(f"[DMX-NOOP] Light1={rgbw1}  Light2={rgbw2}  speed={hue_speed:.2f}")


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
        print(f"[DMX] Could not open {port}: {e} → using noop")
        return _NoopDMX()


# ====================================================================
# REAL-TIME STREAMING + LIGHT CONTROL
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
    save_json: bool = True,
):
    """Stream MP3 → extract features → control dual lights (hue cycle + strobe)."""
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
        print("[ERR] ffmpeg not found; install ffmpeg and retry.")
        return

    # Countdown before start
    countdown_colors = [(255, 0, 0, 0), (255, 128, 0, 0), (255, 255, 0, 0)]
    for i, color in enumerate(reversed(countdown_colors), start=1):
        dmx.update_dual_lighting(color, (0, 0, 0, 0), 0)
        print(f"Countdown: {4 - i}")
        time.sleep(1)

    bytes_per_sample = 4
    frame_bytes = audio_block * channels * bytes_per_sample
    chunk_samples = int(chunk_seconds * sample_rate)
    hop_samples = max(1, int(chunk_samples * hop_ratio))
    analysis_buffer = np.empty(0, dtype=np.float32)
    results = []
    hue_offset = 0.0
    start_time = time.time()

    print(f"[RUN] Streaming {Path(mp3_path).name} ({genre.title()})")

    try:
        while True:
            raw = proc.stdout.read(frame_bytes)
            if not raw or len(raw) < frame_bytes:
                break
            block = np.frombuffer(raw, dtype=np.float32)
            analysis_buffer = np.concatenate((analysis_buffer, block))

            while analysis_buffer.size >= chunk_samples:
                time_position = (len(results) * hop_samples) / sample_rate
                actual_elapsed = time.time() - start_time
                sleep_needed = time_position - actual_elapsed
                if sleep_needed > 0.005:
                    time.sleep(sleep_needed)

                window = analysis_buffer[:chunk_samples]
                mode, key = detect_mode_key(window, sample_rate)
                tempo = detect_tempo(window, sample_rate)
                loudness = detect_loudness(window, sample_rate)
                feature_output, hue_speed = process_audio_features(
                    loudness=loudness, mode=mode, key=key, tempo=tempo
                )

                # Light 1 → hue cycling color
                mapped_rgb = map_features_to_genre_color(loudness=loudness, tempo=tempo, genre=genre)
                hue_offset = (hue_offset + hue_speed * 5) % 360  # hue motion
                r, g, b = mapped_rgb
                light1 = (int(r), int(g), int(b), 0)

                # Light 2 → tempo-based strobe
                strobe_phase = int((time.time() * tempo / 60) % 2)
                if strobe_phase == 0:
                    light2 = (255, 255, 255, 255)
                else:
                    light2 = (0, 0, 0, 0)

                # Send to DMX (dual lights)
                dmx.update_dual_lighting(light1, light2, hue_speed)

                print(f"[{time_position:6.2f}s] Loud:{loudness:5.2f}dB | T:{tempo:3.0f} | "
                      f"RGB1={light1[:3]} | STROBE={strobe_phase}")

                results.append({
                    "time_position": time_position,
                    "features": {
                        "mode": mode, "key": key, "tempo": float(tempo), "loudness": float(loudness)
                    },
                    "light1": light1,
                    "light2": light2,
                    "hue_speed": float(hue_speed)
                })

                analysis_buffer = analysis_buffer[hop_samples:]

        proc.stdout.close()
        proc.wait()

        if save_json and results:
            out_dir = Path(__file__).parent / "outputs"
            out_dir.mkdir(parents=True, exist_ok=True)
            out_file = out_dir / f"lighting_dual_{Path(mp3_path).stem}_{genre}.json"
            with open(out_file, "w") as f:
                json.dump(results, f, indent=2)
            print(f"[OK] Saved {len(results)} windows → {out_file}")

    except KeyboardInterrupt:
        print("\n[STOP] Interrupted by user")
    except Exception as e:
        print(f"[ERR] Runtime Exception: {e}")
        traceback.print_exc()
        proc.kill()


# ====================================================================
# MAIN ENTRY
# ====================================================================

if __name__ == "__main__":
    selected_genre, mp3_file_path, dmx_port = get_user_inputs()

    print("\n--- Configuration Summary ---")
    print(f"Genre: {selected_genre.title()}")
    print(f"File: {mp3_file_path}")
    print(f"DMX Port: {dmx_port}")
    print(f"Channels: Light1(1-4), Light2(5-9)\n")

    dmx = init_dmx_controller(port=dmx_port, num_channels=9)

    try:
        input("Press Enter to start the show...")
        stream_mp3_realtime(mp3_file_path, dmx, selected_genre)
    finally:
        dmx.stop_broadcast()
        dmx.close()
        print("\n[END] DMX broadcast stopped and port closed.")
