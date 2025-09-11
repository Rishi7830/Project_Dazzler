"""
Realtime MP3 → Playback + Feature Analysis + DMX output
Requires:
  - ffmpeg in PATH (for decoding MP3 to PCM stream)
  - python-sounddevice
  - local modules: tempo_detection, loudness_detection, mode_key_detection,
    audio_analyzer.process_audio_features, color_mapper.map_to_colors
  - local pyserial.SimpleDMX (wrapper around pySerial) or falls back to no-op
"""
import os
import sys
import time
import platform
import subprocess
from pathlib import Path

import numpy as np
import sounddevice as sd  # pip install sounddevice

from tempo_detection import detect_tempo
from loudness_detection import detect_loudness
from mode_key_detection import detect_mode_key
from audio_analyzer import process_audio_features
from color_mapper import map_to_colors

# --- DMX wiring (copied from earlier pattern) ---
try:
    from pyserial import SimpleDMX
except Exception:
    SimpleDMX = None

def _suggest_default_port() -> str:
    sysname = platform.system().lower()
    if sysname.startswith("win"):
        return os.environ.get("DAZZLER_DMX_PORT", "COM3")
    if sysname == "darwin":
        return os.environ.get("DAZZLER_DMX_PORT", "/dev/tty.usbserial")
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

# --- Realtime streaming from MP3 via FFmpeg + playback via sounddevice ---
def stream_mp3_realtime(
    mp3_path: str,
    dmx,
    sample_rate: int = 44100,
    channels: int = 1,
    audio_block: int = 1024,       # playback block (samples per channel)
    chunk_seconds: float = 0.25,   # analysis window length
    hop_ratio: float = 0.5,        # analysis hop = 50% overlap
    save_json: bool = True,
):
    """
    Stream-decode MP3 in real time, play audio, analyze per window, update DMX.
    """
    mp3_path = str(mp3_path)
    if not Path(mp3_path).exists():
        print(f"[ERR] File not found: {mp3_path}")
        return

    # FFmpeg command to decode MP3 → 32-bit float PCM, mono, desired SR
    cmd = [
        "ffmpeg",
        "-hide_banner", "-loglevel", "error",
        "-i", mp3_path,
        "-f", "f32le",
        "-ac", str(channels),
        "-ar", str(sample_rate),
        "pipe:1",  # stdout
    ]
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    except FileNotFoundError:
        print("[ERR] ffmpeg not found in PATH; install ffmpeg and retry")
        return

    # Playback stream
    stream = sd.OutputStream(
        samplerate=sample_rate,
        channels=channels,
        dtype="float32",
        blocksize=audio_block,
    )
    stream.start()

    # Analysis buffer and bookkeeping
    bytes_per_sample = 4  # float32
    frame_bytes = audio_block * channels * bytes_per_sample
    chunk_samples = int(chunk_seconds * sample_rate)
    hop_samples = max(1, int(chunk_samples * hop_ratio))
    analysis_buffer = np.empty(0, dtype=np.float32)
    results = []

    print(f"[RUN] Streaming {mp3_path} at {sample_rate} Hz, block={audio_block}, chunk={chunk_seconds}s, hop={hop_ratio*100:.0f}%")

    try:
        while True:
            # Read one playback block from ffmpeg
            raw = proc.stdout.read(frame_bytes)
            if not raw or len(raw) < frame_bytes:
                break  # end of stream

            # Convert to array and play
            block = np.frombuffer(raw, dtype=np.float32)
            # If mono, block shape is (audio_block * 1,)
            stream.write(block.reshape(-1, channels))

            # Append to analysis buffer (operate on mono 1-D)
            analysis_buffer = np.concatenate((analysis_buffer, block))

            # Run analysis whenever we have at least one analysis window
            while analysis_buffer.size >= chunk_samples:
                window = analysis_buffer[:chunk_samples]

                # Feature extraction (parallel in original main, sequential here per window)
                # If desired, this can dispatch to a ProcessPool for larger windows.
                mode, key = detect_mode_key(window, sample_rate)
                tempo = detect_tempo(window, sample_rate)
                loudness = detect_loudness(window, sample_rate)

                # Map features to lighting command
                color_name, hue_speed = process_audio_features(
                    loudness=loudness, mode=mode, key=key, tempo=tempo
                )
                color_dict = map_to_colors(color_name, hue_speed)
                r, g, b = color_dict["primary_color"]["rgb"]
                rgbw = (int(r), int(g), int(b), 0)

                # DMX update in real time
                dmx.update_lighting(rgbw, hue_speed)

                # Optional: collect a summary row
                results.append({
                    "time_position": (len(results) * hop_samples) / sample_rate,
                    "features": {"mode": mode, "key": key, "tempo": float(tempo), "loudness": float(loudness)},
                    "lighting": {"color": color_name, "rgbw": rgbw, "hue_speed": float(hue_speed)},
                })

                # Advance buffer by hop
                analysis_buffer = analysis_buffer[hop_samples:]

        # Drain and close
        stream.stop(); stream.close()
        proc.stdout.close(); proc.wait()

        # Save run JSON next to script
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
        try:
            stream.stop(); stream.close()
        except Exception:
            pass
        try:
            proc.terminate()
        except Exception:
            pass

if __name__ == "__main__":
    # Choose file next to this script by default
    mp3_file = Path(__file__).with_name("scom.mp3")
    dmx = init_dmx_controller(port=None, num_channels=8)

    # Lower chunk_seconds for faster lighting response; trade-off stability/CPU
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

    # Always stop DMX on exit
    try:
        dmx.stop_broadcast(); dmx.close()
    except Exception:
        pass
