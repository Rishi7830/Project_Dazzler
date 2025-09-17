import os
import time
from pathlib import Path
import numpy as np
from tempo_detection import detect_tempo
from loudness_detection import detect_loudness
from mode_key_detection import detect_mode_key
from audio_analyzer import process_audio_features
from color_mapper import map_to_colors

try:
    from pyserial import SimpleDMX
except Exception:
    SimpleDMX = None

# Your existing _suggest_default_port and _NoopDMX and init_dmx_controller...

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

    # Countdown effect 3, 2, 1 on DMX lights
    countdown_colors = [
        (255, 0, 0, 0),  # red
        (255, 128, 0, 0),  # orange
        (255, 255, 0, 0),  # yellow
    ]
    for color in countdown_colors[::-1]:  # countdown 3,2,1
        dmx.update_lighting(color, hue_speed=0)
        time.sleep(1)

    # We do NOT start audio playback stream (sounddevice) here to avoid errors in WSL.

    bytes_per_sample = 4  # float32
    frame_bytes = audio_block * channels * bytes_per_sample
    chunk_samples = int(chunk_seconds * sample_rate)
    hop_samples = max(1, int(chunk_samples * hop_ratio))
    analysis_buffer = np.empty(0, dtype=np.float32)
    results = []

    print(f"[RUN] Streaming {mp3_path} at {sample_rate} Hz")

    try:
        while True:
            raw = proc.stdout.read(frame_bytes)
            if not raw or len(raw) < frame_bytes:
                break

            block = np.frombuffer(raw, dtype=np.float32)
            analysis_buffer = np.concatenate((analysis_buffer, block))

            while analysis_buffer.size >= chunk_samples:
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
                    "time_position": (len(results)*hop_samples)/sample_rate,
                    "features": {"mode": mode, "key": key, "tempo": float(tempo), "loudness": float(loudness)},
                    "lighting": {"color": color_name, "rgbw": rgbw, "hue_speed": float(hue_speed)}
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

    finally:
        pass  # No playback stream to stop in WSL


if __name__ == "__main__":
    mp3_file = Path(__file__).with_name("scom.mp3")
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
