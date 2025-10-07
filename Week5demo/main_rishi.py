"""
Realtime MP3 → Feature Analysis + DMX output (no audio playback for WSL)
Requires ffmpeg, local feature modules, and color_mapper.map_to_colors, pyserial
"""

import os
import time
import platform
import subprocess
from pathlib import Path
import numpy as np
import serial  # Using standard pyserial

from tempo_detection import detect_tempo
from loudness_detection import detect_loudness
from mode_key_detection import detect_mode_key
from audio_analyzer import process_audio_features
from color_mapper import map_to_colors


def _suggest_default_port() -> str:
    sysname = platform.system().lower()
    if sysname.startswith("win"):
        return os.environ.get("DAZZLER_DMX_PORT", "COM3")
    if sysname == "darwin":
        return os.environ.get("DAZZLER_DMX_PORT", "/dev/tty.usbserial")
    return os.environ.get("DAZZLER_DMX_PORT", "/dev/ttyUSB0")


class DMXController:
    """
    Basic DMX controller using pyserial.
    Assumes an 8-channel DMX device.
    """
    def __init__(self, port: str | None = None, num_channels: int = 8):
        self.port = port or _suggest_default_port()
        self.num_channels = num_channels
        self.serial = None
        self.is_open = False

    def start_broadcast(self):
        try:
            self.serial = serial.Serial(self.port, baudrate=250000)
            self.is_open = True
            print(f"[DMX] Started on {self.port} channels={self.num_channels}")
        except Exception as e:
            print(f"[DMX] Failed to open {self.port}: {e}")
            self.is_open = False

    def stop_broadcast(self):
        if self.serial and self.serial.is_open:
            self.serial.close()
            print("[DMX] Broadcast stopped")

    def close(self):
        self.stop_broadcast()

    def update_lighting(self, rgbw_tuple, hue_speed):
        if not self.is_open:
            print(f"[DMX] (noop) {rgbw_tuple} speed={hue_speed:.2f}")
            return
        try:
            r, g, b, w = rgbw_tuple
            # DMX frame: Start code + channel data (8 channels)
            frame = bytearray([0] + [r, g, b, w, 0, 0, 0, 0])
            self.serial.write(frame)
            print(f"[DMX] Sent {rgbw_tuple} (speed={hue_speed:.2f})")
        except Exception as e:
            print(f"[DMX] Error writing to serial: {e}")


def init_dmx_controller(port: str | None = None, num_channels: int = 8):
    dmx = DMXController(port=port, num_channels=num_channels)
    dmx.start_broadcast()
    return dmx


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

    # Countdown lights
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
    except Exception as e:
        print(f"[ERR] Exception: {e}")


if __name__ == "__main__":
    mp3_file = Path(__file__).with_name("Love Will Keep Us Alive (1999 Remaster).mp3")
    dmx = init_dmx_controller(port=None, num_channels=8)
    stream_mp3_realtime(
        mp3_path=str(mp3_file),
        dmx=dmx,
        sample_rate=44100,
        channels=1,
        audio_block=1024,
        chunk_seconds=0.25,
        hop_ratio=0.5,
        save_json=True,
    )
    try:
        dmx.stop_broadcast()
        dmx.close()
    except Exception:
        pass
```

