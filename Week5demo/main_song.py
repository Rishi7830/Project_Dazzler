"""
Realtime MP3 → Feature Analysis + DMX output + Audio Playback
Requires:
  - ffmpeg in PATH
  - sounddevice
  - local modules: tempo_detection, loudness_detection, mode_key_detection, audio_analyzer, color_mapper
  - pyserial.SimpleDMX (your local DMX class)
"""

import os
import time
import platform
import subprocess
from pathlib import Path
import threading
import numpy as np
import sounddevice as sd

from tempo_detection import detect_tempo
from loudness_detection import detect_loudness
from mode_key_detection import detect_mode_key
from audio_analyzer import process_audio_features
from color_mapper import map_to_colors

# Import your SimpleDMX
try:
    from pyserial import SimpleDMX
except Exception as e:
    print(f"[WARN] Could not import SimpleDMX: {e}")
    SimpleDMX = None


def _suggest_default_port() -> str:
    sysname = platform.system().lower()
    if sysname.startswith("win"):
        return os.environ.get("DAZZLER_DMX_PORT", "/dev/ttyUSB0")
    if sysname == "darwin":
        return os.environ.get("DAZZLER_DMX_PORT", "/dev/ttyUSB0")
    return os.environ.get("DAZZLER_DMX_PORT", "/dev/ttyUSB0")


class _NoopDMX:
    def start_broadcast(self): print("[DMX] Broadcast disabled (no hardware)")
    def stop_broadcast(self): pass
    def close(self): pass
    def update_lighting(self, rgbw_tuple, hue_speed):
        print(f"[DMX] (noop) {rgbw_tuple} speed={hue_speed:.2f}")


def init_dmx_controller(port: str | None = None, num_channels: int = 8):
    if SimpleDMX is None:
        return _NoopDMX()
    port = port or _suggest_default_port()
    try:
        dmx = SimpleDMX(port=port, num_channels=num_channels)
        dmx.start_broadcast()
        print(f"[DMX] Started on {port} channels={num_channels}")
        return dmx
    except Exception as e:
        print(f"[DMX] Could not open {port}: {e} -> using noop")
        return _NoopDMX()


def play_mp3(mp3_path: str, sample_rate: int = 44100, channels: int = 2, blocksize: int = 1024):
    """Play MP3 audio through laptop speakers using ffmpeg + sounddevice."""
    cmd = [
        "ffmpeg",
        "-hide_banner", "-loglevel", "error",
        "-i", mp3_path,
        "-f", "f32le",
        "-ac", str(channels),
        "-ar", str(sample_rate),
        "pipe:1"
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, bufsize=blocksize * channels * 4)
    stream = sd.OutputStream(samplerate=sample_rate, channels=channels, dtype="float32", blocksize=blocksize)
    stream.start()
    bytes_per_frame = blocksize * channels * 4
    try:
        while True:
            raw = proc.stdout.read(bytes_per_frame)
            if not raw:
                break
            block = np.frombuffer(raw, dtype=np.float32)
            stream.write(block.reshape(-1, channels))
    except KeyboardInterrupt:
        print("\n[STOP] Interrupted by user")
    finally:
        stream.stop()
        stream.close()
        proc.stdout.close()
        proc.wait()


def stream_mp3_realtime(
    mp3_path: str,
    dmx,
    sample_rate: int = 44100,
    channels: int = 1,
    audio_block: int = 1024,
    chunk_seconds: float = 0.25,
    hop_ratio: float = 0.5,
    save_json: bool = True,
):
    """Stream-decode MP3, analyze audio features, update DMX lighting."""
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

    # Countdown before start
    countdown_colors = [(255,0,0,0),(255,128,0,0),(255,255,0,0)]
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
    print(f"[RUN] Streaming {mp3_path} at {sample_rate} Hz - chunk={chunk_seconds}s, hop={hop_ratio}")

    try:
        while True:
            raw = proc.stdout.read(frame_bytes)
            if not raw or len(raw) < frame_bytes:
                break

            block = np.frombuffer(raw, dtype=np.float32)
            analysis_buffer = np.concatenate((analysis_buffer, block))

            while analysis_buffer.size >= chunk_samples:
                elapsed = time.time() - start_time
                print(f"Progress: {elapsed:.2f} seconds")

                window = analysis_buffer[:chunk_samples]
                mode, key = detect_mode_key(window, sample_rate)
                tempo = detect_tempo(window, sample_rate)
                loudness = detect_loudness(window, sample_rate)

                color_name, hue_speed = process_audio_features(
                    loudness=loudness, mode=mode, key=key, tempo=tempo
                )
                color_dict = map_to_colors(color_name, hue_speed)
                r, g, b = color_dict["primary_color"]["rgb"]
                rgbw = (int(r), int(g), int(b), 0)
                dmx.update_lighting(rgbw, hue_speed)

                results.append({
                    "time_position": (len(results) * hop_samples) / sample_rate,
                    "features": {
                        "mode": mode,
                        "key": key,
                        "tempo": float(tempo),
                        "loudness": float(loudness)
                    },
                    "lighting": {
                        "color": color_name,
                        "rgbw": rgbw,
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
                json.dump(results, f, indent=2)
            print(f"[OK] Saved {len(results)} analysis windows to {out_file}")

    except KeyboardInterrupt:
        print("\n[STOP] Interrupted by user")


if __name__ == "__main__":
    mp3_file = Path(__file__).with_name("Love Will Keep Us Alive (1999 Remaster).mp3")
    dmx = init_dmx_controller(port="/dev/ttyUSB0", num_channels=8)

    # Run analysis + DMX in a thread
    analysis_thread = threading.Thread(
        target=stream_mp3_realtime,
        args=(str(mp3_file), dmx),
        daemon=True
    )
    # Run audio playback in a thread
    playback_thread = threading.Thread(
        target=play_mp3,
        args=(str(mp3_file),),
        daemon=True
    )

    analysis_thread.start()
    playback_thread.start()

    # Wait until audio finishes
    playback_thread.join()

    # Stop DMX after playback
    try:
        dmx.stop_broadcast()
        dmx.close()
    except Exception:
        pass
