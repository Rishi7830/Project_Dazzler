"""
Realtime MP3 -> Feature Analysis + DMX output + Synchronized External Playback
Uses a two-path system (WSL path for FFmpeg, Windows path for playback)
and the reliable 'cmd.exe /c start' command to launch the MP3 on the host.
"""

import os
import time
import platform
import subprocess
from pathlib import Path
import numpy as np

# Assuming these modules are available in the directory
from tempo_detection import detect_tempo
from loudness_detection import detect_loudness
from mode_key_detection import detect_mode_key
from audio_analyzer import process_audio_features
from color_mapper import map_to_colors

try:
    from pyserial import SimpleDMX
except Exception as e:
    print(f"[WARN] Could not import SimpleDMX: {e}. DMX will be simulated.")
    SimpleDMX = None


def _suggest_default_port() -> str:
    """Suggests the default DMX port based on OS."""
    sysname = platform.system().lower()
    if sysname.startswith("win"):
        return os.environ.get("DAZZLER_DMX_PORT", "/dev/ttyUSB2")
    if sysname == "darwin":
        return os.environ.get("DAZZLER_DMX_PORT", "/dev/tty.usbserial")
    return os.environ.get("DAZZLER_DMX_PORT", "/dev/ttyUSB2")


class _NoopDMX:
    """Mock DMX controller for when hardware or pyserial is unavailable."""
    def start_broadcast(self): 
        if not hasattr(self, '_started'):
             print("[DMX] Broadcast simulation started (using _NoopDMX)")
             self._started = True
    def stop_broadcast(self): pass
    def close(self): pass
    def update_lighting(self, rgbw_tuple, hue_speed):
        pass # No print to avoid lag

def init_dmx_controller(port: str | None = None, num_channels: int = 9):
    """Initializes the DMX controller or returns a no-op fallback."""
    if SimpleDMX is None:
        return _NoopDMX()
    port = port or _suggest_default_port()
    try:
        dmx = SimpleDMX(port=port)
        dmx.start_broadcast()
        print(f"[DMX] Started real controller on {port} channels={num_channels}")
        return dmx
    except Exception as e:
        print(f"[DMX] Could not open {port}: {e} -> using noop")
        return _NoopDMX()


def start_external_player(mp3_path_win: str):
    """
    Starts an external music player process asynchronously using the 
    Windows path and the reliable 'cmd.exe /c start' command.
    """
    if 'wsl' in platform.platform().lower():
        try:
            # Use 'cmd.exe /c start' to open the file using the Windows default application.
            # We use Popen with a list for clean argument passing, especially with spaces.
            # The empty string "" after 'start' is crucial to handle paths with spaces correctly.
            subprocess.Popen(['cmd.exe', '/c', 'start', '', mp3_path_win], 
                             stdout=subprocess.DEVNULL, 
                             stderr=subprocess.DEVNULL)
            print(f"[PLAY] Launched external playback via cmd.exe: {mp3_path_win}")
            return True
        except FileNotFoundError as e:
             # This means cmd.exe or a related Windows component is not found in PATH
             print(f"[FAIL] Could not launch external player via cmd.exe: {e}")
             print("[FAIL] Please start the song manually on your Windows host *now* to sync analysis.")
             return False

    # Fallback for native Linux/macOS systems 
    try:
        subprocess.Popen(["xdg-open", mp3_path_win], start_new_session=True)
        print(f"[PLAY] Launched external playback (xdg-open): {mp3_path_win}")
        return True
    except FileNotFoundError:
        print("[FAIL] Could not start external player. Please play the song manually now.")
        return False


def stream_mp3_realtime(
    mp3_path_wsl: str,
    mp3_path_win: str,
    dmx,
    sample_rate: int = 44100,
    channels: int = 1,
    audio_block: int = 1024,
    chunk_seconds: float = 0.25,
    hop_ratio: float = 0.5,
    save_json: bool = True,
):
    """
    Stream-decode MP3 in real time (using WSL path for FFmpeg), 
    analyze features, and update DMX lighting.
    The audio is played externally (using Windows path for playback).
    """
    if not Path(mp3_path_wsl).exists():
        print(f"[ERR] File not found by FFmpeg (WSL Path): {mp3_path_wsl}")
        return

    # 1. Setup FFmpeg decoding process
    cmd = [
        "ffmpeg",
        "-hide_banner", "-loglevel", "error",
        "-i", mp3_path_wsl,  # FFmpeg uses the WSL path to read the file
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

    # 2. 3-2-1 Countdown & DMX Initialization
    countdown_colors = [
        (255,   0,   0, 0),  # Red for 3
        (255, 128,   0, 0),  # Orange for 2
        (255, 255,   0, 0)   # Yellow for 1
    ]
    dmx.start_broadcast()

    for i, color in enumerate(reversed(countdown_colors), start=1):
        dmx.update_lighting(color, hue_speed=0)
        print(f"Countdown: {4 - i}")
        time.sleep(1)
        
    # Start audio playback on the host system immediately after the countdown
    start_external_player(mp3_path_win) # Windows Player uses the WIN path
    
    # Set lights to initial black before starting analysis
    dmx.update_lighting((0, 0, 0, 0), hue_speed=0)
    print("[OK] Starting audio analysis.")


    # 3. Setup buffers and counters for real-time processing
    bytes_per_sample = 4
    frame_bytes = audio_block * channels * bytes_per_sample
    chunk_samples = int(chunk_seconds * sample_rate)
    hop_samples = max(1, int(chunk_samples * hop_ratio))
    analysis_buffer = np.empty(0, dtype=np.float32)
    results = []

    start_time = time.time()

    print(f"[RUN] Streaming {mp3_path_wsl} at {sample_rate} Hz - chunk={chunk_seconds}s, hop={hop_ratio}")

    try:
        while True:
            raw = proc.stdout.read(frame_bytes)
            
            if not raw or len(raw) < frame_bytes:
                break

            block = np.frombuffer(raw, dtype=np.float32)
            
            # --- ANALYSIS BUFFERING ---
            analysis_buffer = np.concatenate((analysis_buffer, block))

            # --- REAL-TIME ANALYSIS ---
            while analysis_buffer.size >= chunk_samples:
                elapsed = time.time() - start_time
                if len(results) % 10 == 0:
                    print(f"Progress: {elapsed:.2f} seconds")

                window = analysis_buffer[:chunk_samples]
                mode, key = detect_mode_key(window, sample_rate)
                tempo = detect_tempo(window, sample_rate)
                loudness = detect_loudness(window, sample_rate)

                # Feature processing and DMX update
                color_name, hue_speed = process_audio_features(
                    loudness=loudness, mode=mode, key=key, tempo=tempo
                )
                color_dict = map_to_colors(color_name, hue_speed)
                r, g, b = color_dict["primary_color"]["rgb"]
                rgbw = (int(r), int(g), int(b), 0) 
                dmx.update_lighting(rgbw, hue_speed)

                # Save results
                results.append({
                    "time_position": (len(results) * hop_samples) / sample_rate,
                    "features": {
                        "mode": mode, "key": key, "tempo": float(tempo), "loudness": float(loudness)
                    },
                    "lighting": {
                        "color": color_name, "rgbw": rgbw, "hue_speed": float(hue_speed)
                    }
                })

                # Advance buffer by the hop size
                analysis_buffer = analysis_buffer[hop_samples:]

        # Clean up FFmpeg process when stream ends
        proc.stdout.close()
        proc.wait()

        # Save results after analysis finishes
        if save_json and results:
            out_dir = Path(__file__).parent / "outputs"
            out_dir.mkdir(parents=True, exist_ok=True)
            out_file = out_dir / f"lighting_data_{Path(mp3_path_wsl).stem}_realtime.json"
            import json
            with open(out_file, "w") as f:
                json.dump(results, f, indent=2)
            print(f"[OK] Saved {len(results)} analysis windows to {out_file}")

    except KeyboardInterrupt:
        print("\n[STOP] Interrupted by user")

    except Exception as e:
        print(f"[ERR] Runtime Exception: {e}")

    finally:
        pass


if __name__ == "__main__":
    dmx = None
    try:
        # 1. Define the Windows Absolute Path (for the Player)
        # We use a raw string (r"...") to avoid issues with backslashes
        mp3_file_win = r"C:\Users\Rishi Moorthy\Desktop\Love Will Keep Us Alive (1999 Remaster).mp3"
        
        # 2. Convert to the corresponding WSL Path (for FFmpeg)
        # This assumes your C drive is mounted at /mnt/c, which is standard in WSL.
        mp3_file_wsl = mp3_file_win.replace("C:", "/mnt/c").replace("\\", "/") 
        
        dmx = init_dmx_controller(port="/dev/ttyUSB2", num_channels=9)
        
        stream_mp3_realtime(
            mp3_path_wsl=mp3_file_wsl,
            mp3_path_win=mp3_file_win,
            dmx=dmx,
            sample_rate=44100,
            channels=1, 
            audio_block=1024,
            chunk_seconds=0.25,
            hop_ratio=0.5,
            save_json=True,
        )
    except Exception as e:
        print(f"An error occurred in the main process: {e}")
    finally:
        if dmx:
            try:
                dmx.stop_broadcast()
                dmx.close()
            except Exception:
                pass
        print("[OK] Application finished.")




