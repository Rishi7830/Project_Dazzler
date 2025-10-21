"""
Realtime MP3 → Feature Analysis + Dual DMX Output.
FINAL VERSION: Light 1 = hue cycling | Light 2 = strobe pulse.
"""

import os
import time
import platform
import subprocess
import json
import numpy as np
import traceback
from pathlib import Path

# --- Feature + Mapping imports (unchanged) ---
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
# USER INPUT AND SETUP FUNCTIONS
# ====================================================================

def get_user_inputs():
    genres = get_available_genres()
    print("=== Music-to-Light System Setup ===")
    for i, g in enumerate(genres, 1):
        print(f"{i}. {g.title()}")

    while True:
        choice = input(f"\nSelect genre (1-{len(genres)}): ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(genres):
            selected_genre = genres[int(choice) - 1]
            break
        print("Invalid choice. Try again.")

    while True:
        filepath = input("\nEnter MP3 path: ").strip().strip('"')
        if os.path.exists(Path(filepath).expanduser()):
            filepath = str(Path(filepath).expanduser())
            break
        print("File not found. Try again.")

    default_port1 = _suggest_default_port()
    dmx_port1 = input(f"\nEnter DMX port for Light 1 (default: {default_port1}): ").strip() or default_port1
    default_port2 = "/dev/ttyUSB1" if "USB0" in dmx_port1 else "/dev/ttyUSB0"
    dmx_port2 = input(f"Enter DMX port for Light 2 (strobe) (default: {default_port2}): ").strip() or default_port2

    return selected_genre.lower(), filepath, dmx_port1, dmx_port2


def _suggest_default_port():
    sysname = platform.system().lower()
    if sysname.startswith("win"):
        return os.environ.get("DAZZLER_DMX_PORT", "COM3")
    if sysname == "darwin":
        return os.environ.get("DAZZLER_DMX_PORT", "/dev/tty.usbserial")
    return os.environ.get("DAZZLER_DMX_PORT", "/dev/ttyUSB0")


class _NoopDMX:
    def start_broadcast(self): print("[DMX] (noop) start")
    def stop_broadcast(self): pass
    def close(self): pass
    def update_lighting(self, rgbw_tuple, hue_speed):
        print(f"[DMX] (noop) R{rgbw_tuple[0]} G{rgbw_tuple[1]} B{rgbw_tuple[2]} W{rgbw_tuple[3]} speed={hue_speed:.2f}")


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
    dmx_main,
    dmx_strobe,
    genre: str,
    sample_rate: int = 44100,
    channels: int = 1,
    audio_block: int = 1024,
    chunk_seconds: float = 0.25,
    hop_ratio: float = 0.5,
    save_json: bool = True,
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
        print("[ERR] ffmpeg not found. Install ffmpeg and retry.")
        return

    # Countdown before playback
    for i, color in enumerate([(255, 0, 0, 0), (255, 128, 0, 0), (255, 255, 0, 0)]):
        dmx_main.update_lighting(color, 0)
        dmx_strobe.update_lighting((255, 255, 255, 0), 1.0)
        print(f"Countdown: {3 - i}")
        time.sleep(1)

    bytes_per_sample = 4
    frame_bytes = audio_block * channels * bytes_per_sample
    chunk_samples = int(chunk_seconds * sample_rate)
    hop_samples = max(1, int(chunk_samples * hop_ratio))
    analysis_buffer = np.empty(0, dtype=np.float32)
    results = []
    start_time = time.time()

    print(f"[RUN] Streaming {Path(mp3_path).name} ({genre.title()})")

    try:
        while True:
            raw = proc.stdout.read(frame_bytes)
            if not raw or len(raw) < frame_bytes:
                break
            time.sleep(0.001)
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
                r, g, b = map_features_to_genre_color(loudness=loudness, tempo=tempo, genre=genre)
                rgbw_main = (int(r), int(g), int(b), 0)
                rgbw_strobe = (255, 255, 255, 0)

                # Light 1 → Color reactive
                dmx_main.update_lighting(rgbw_main, hue_speed)
                # Light 2 → White strobe always active
                dmx_strobe.update_lighting(rgbw_strobe, 1.0)

                print(f"[{time_position:6.2f}s] Loud:{loudness:5.2f}dB | Tempo:{tempo:3.0f} | RGB{rgbw_main[:3]}")
                results.append({
                    "time": time_position,
                    "loudness": float(loudness),
                    "tempo": float(tempo),
                    "lighting": {"main": rgbw_main, "strobe": rgbw_strobe}
                })
                analysis_buffer = analysis_buffer[hop_samples:]

        proc.stdout.close()
        proc.wait()
        if save_json and results:
            out_dir = Path(__file__).parent / "outputs"
            out_dir.mkdir(parents=True, exist_ok=True)
            out_path = out_dir / f"dual_lighting_{Path(mp3_path).stem}_{genre}.json"
            with open(out_path, "w") as f:
                json.dump(results, f, indent=2)
            print(f"[OK] Saved results → {out_path}")

    except KeyboardInterrupt:
        print("\n[STOP] User interrupted.")
    except Exception as e:
        print(f"[ERR] Runtime error: {e}")
        traceback.print_exc()
        proc.kill()
    finally:
        pass


# ====================================================================
# MAIN ENTRY
# ====================================================================

if __name__ == "__main__":
    genre, mp3_file, port1, port2 = get_user_inputs()
    print(f"\n--- Config ---\nGenre: {genre.title()}\nFile: {mp3_file}\nLight 1: {port1}\nLight 2: {port2}\n-----------------\n")

    dmx_main = init_dmx_controller(port=port1)
    dmx_strobe = init_dmx_controller(port=port2)

    try:
        input("Press Enter to start music + dual lighting...")
        stream_mp3_realtime(mp3_file, dmx_main, dmx_strobe, genre)
    finally:
        dmx_main.stop_broadcast()
        dmx_strobe.stop_broadcast()
        dmx_main.close()
        dmx_strobe.close()
        print("\n[END] All DMX ports closed.")
