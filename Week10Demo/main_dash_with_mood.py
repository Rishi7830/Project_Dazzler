"""
Realtime MP3 → Feature Analysis + DMX output.
Includes Real-Time Synchronization, Loudness-Based Color Mapping, and White Strobe.
"""

import os
import time
import platform
import subprocess
import json
import numpy as np
import traceback
from pathlib import Path
import tkinter as tk
import multiprocessing
from audio_playback import play_audio

# Import the UI class from your separate file
from dazzler_ui import DazzlerDashboard

# Import your custom feature modules
from Tempo_Detection import detect_tempo
from loudness_detection import detect_loudness
from Harmony_Detection import extract_harmony
from Rhythm_Detection import extract_rhythm
from Mode_Detection import detect_mode_key
from audio_analyzer import process_audio_features
from knn_prediction import preprocess_features, predict_mood # Import mood prediction

# Import all necessary functions from color_mapper, including the new mapping function
from color_mapper import get_available_genres, genre_color_palettes, map_features_to_genre_color

try:
    from pyserial import SimpleDMX
except Exception as e:
    print(f"[WARN] Could not import SimpleDMX: {e}")
    SimpleDMX = None

# UI INTEGRATION AND SETUP FUNCTIONS

def get_user_inputs_from_ui():
    """Launches the UI and waits for user input via the Start Dazzling! button."""
    root = tk.Tk()

    # Initialize the DazzlerDashboard UI
    app = DazzlerDashboard(root)

    # Use a custom flag to signal when the Master Submit is pressed
    app.submission_successful = False

    def master_submit_and_close():
        """Modified submit action to get data and close the UI."""
        app.master_submit() # Run the standard submit logic (for validation/output)

        # Check if the submission was successful (i.e., not incomplete)
        if app.genre_var.get() and app.com_port_var.get() and app.song_name_var.get():
            app.submission_successful = True
            root.quit() # Stop the mainloop to allow the script to continue
        else:
            # If submission failed due to validation, keep the window open
            print("Validation failed in UI. Please check inputs.")


    app.master_button.config(command=master_submit_and_close)

    root.mainloop()

    if app.submission_successful:
        # Retrieve the data from the UI instance variables
        selected_genre = app.genre_var.get().lower()
        filepath = app.song_name_var.get().strip().strip('"')
        dmx_port = app.com_port_var.get().strip()

        # Check if the file path is valid before proceeding
        if not os.path.exists(Path(filepath).expanduser()):
             # This file check could also be added to the UI validation
             print(f"[ERR] File not found: {filepath}. Please re-run and check the path.")
             return None, None, None

        # Destroy the root window after we have the data
        root.destroy()

        return selected_genre, filepath, dmx_port
    else:
        # If the user closed the window or submission failed
        root.destroy()
        return None, None, None


def _suggest_default_port() -> str:
    """Suggests a default DMX port based on the operating system."""
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


# REAL-TIME STREAMING AND ANALYSIS (WITH TIMING CORRECTION)
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
    """
    Stream-decode MP3 in real time, analyze features per window,
    and update DMX lighting: Fixture1=loudness, Fixture2=mood.
    """
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

    # Countdown
    countdown_colors = [(255, 0, 0, 0), (255, 128, 0, 0), (255, 255, 0, 0)]
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
    strobe_toggle = False
    previous_loudness = 0.0
    LOUDNESS_JUMP_THRESHOLD = 5.0

    print(f"[RUN] Streaming {Path(mp3_path).name} ({genre.title()}) - chunk={chunk_seconds}s, hop={hop_ratio}")
    print(f"[INFO] Fixture 1: loudness-driven, Fixture 2: mood-driven")

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
                actual_elapsed_time = time.time() - start_time
                sleep_needed = time_position - actual_elapsed_time
                if sleep_needed > 0.005:
                    time.sleep(sleep_needed)

                window = analysis_buffer[:chunk_samples]

                # Extract features
                mode, key = detect_mode_key(window, sample_rate)
                tempo = detect_tempo(window)
                loudness = detect_loudness(window, sample_rate)
                rhythm = extract_rhythm(window)
                harmony = extract_harmony(window)

                # Mood prediction
                features_processed = preprocess_features(mode, tempo, loudness, rhythm, harmony)
                mood = predict_mood(features_processed)

                # Process features for DMX (hue_speed, etc.)
                feature_output, hue_speed = process_audio_features(loudness=loudness, mode=mode, key=key, tempo=tempo)

                # --- Fixture 1: Loudness-driven ---
                log_strobe = False
                strobe_value = 0
                if loudness - previous_loudness > LOUDNESS_JUMP_THRESHOLD:
                    strobe_toggle = not strobe_toggle
                    strobe_value = 255  # fast strobe
                    log_strobe = True
                    r1, g1, b1, w1 = (255, 255, 255, 0) if strobe_toggle else (0, 0, 0, 0)
                else:
                    r1, g1, b1 = map_features_to_genre_color(loudness=loudness, tempo=tempo, genre=genre)
                    w1 = 0
                dimmer1 = int(np.clip(np.interp(loudness, [40, 100], [50, 255]), 0, 255))

                dmx.set_channel_internal(CH_RED_1, int(r1))
                dmx.set_channel_internal(CH_GREEN_1, int(g1))
                dmx.set_channel_internal(CH_BLUE_1, int(b1))
                dmx.set_channel_internal(CH_WHITE_1, int(w1))
                dmx.set_channel_internal(CH_DIMMER_1, dimmer1)
                dmx.set_channel_internal(CH_STROBE_1, strobe_value)
                dmx.set_channel_internal(CH_SOUND_1, int(np.clip(hue_speed * 239, 0, 239)))

                # --- Fixture 2: Mood-driven ---
                # Map mood -> RGB (e.g., via a new color mapper function)
                r2, g2, b2 = map_features_to_genre_color(mood=mood, loudness=loudness, tempo=tempo, genre=genre)
                w2 = 0
                dimmer2 = 255
                dmx.set_channel_internal(CH_RED_2, int(r2))
                dmx.set_channel_internal(CH_GREEN_2, int(g2))
                dmx.set_channel_internal(CH_BLUE_2, int(b2))
                dmx.set_channel_internal(CH_WHITE_2, int(w2))
                dmx.set_channel_internal(CH_DIMMER_2, dimmer2)
                dmx.set_channel_internal(CH_STROBE_2, 0)
                dmx.set_channel_internal(CH_SOUND_2, 0)

                # Send DMX frame
                dmx.send_frame()

                # Logging
                if log_strobe:
                    print(f"[{time_position:6.2f}s] L:{loudness:5.2f}dB (+{loudness - previous_loudness:.2f}dB) | T:{tempo:3.0f}bpm | Fixture 1 -> STROBE | Fixture 2 -> Mood:{mood}")
                else:
                    print(f"[{time_position:6.2f}s] L:{loudness:5.2f}dB | T:{tempo:3.0f}bpm | Fixture1 RGB:{r1,g1,b1} | Fixture2 Mood:{mood}")

                previous_loudness = loudness

                results.append({
                    "time_position": time_position,
                    "features": {"mode": mode, "key": key, "tempo": float(tempo), "loudness": float(loudness)},
                    "mood": mood,
                    "lighting": {
                        "fixture1_rgbw": (r1, g1, b1, w1),
                        "fixture2_rgbw": (r2, g2, b2, w2),
                        "dimmer1": dimmer1,
                        "dimmer2": dimmer2,
                    }
                })

                analysis_buffer = analysis_buffer[hop_samples:]

        proc.stdout.close()
        proc.wait()

        # Save JSON
        if save_json and results:
            out_dir = Path(__file__).parent / "outputs"
            out_dir.mkdir(parents=True, exist_ok=True)
            out_file = out_dir / f"lighting_data_{Path(mp3_path).stem}_{genre}_realtime.json"
            with open(out_file, "w") as f:
                json.dump(results, f, indent=2)
            print(f"\n[OK] Saved {len(results)} analysis windows to {out_file}")

    except KeyboardInterrupt:
        print("\n[STOP] Interrupted by user")
    except Exception as e:
        print(f"[ERR] Runtime Exception: {e}")
        proc.kill()
        traceback.print_exc()


if __name__ == "__main__":

    multiprocessing.freeze_support()
    # 1. Get inputs from the new UI function
    selected_genre, mp3_file_path, dmx_port = get_user_inputs_from_ui()

    if not all([selected_genre, mp3_file_path, dmx_port]):
        print("\n[END] Operation cancelled or incomplete data submitted.")
    else:
        print("\n--- Configuration Summary ---")
        print(f"Genre: {selected_genre.title()}")
        print(f"File: {mp3_file_path}")
        print(f"DMX Port: {dmx_port}")
        print(f"Update Rate: {0.25} seconds (Responsive)")
        print("-----------------------------\n")

        dmx = init_dmx_controller(port=dmx_port, num_channels=9)

        playback_process = None
        analysis_process = None
        try:

            print("Preparing processes for audio playback and analysis...")

            # 3. Create the process for audio playback
            playback_process = multiprocessing.Process(
                target=play_audio,
                args=(mp3_file_path,)
            )

            # 4. Create the process for real-time analysis and DMX control
            analysis_process = multiprocessing.Process(
                target=stream_mp3_realtime,
                args=(mp3_file_path, dmx, selected_genre)
                # You can add chunk_seconds, hop_ratio, etc., to args if needed
            )

            print("\n[START] Starting audio playback and lighting analysis...")
            print("Press Ctrl+C in this terminal to stop all processes.")

            # 5. Start the processes
            # Give analysis a 1-second head-start to initialize
            analysis_process.start()
            time.sleep(1)
            playback_process.start()

            # 6. Wait for processes to finish
            # The script will wait here until analysis (or playback) is done
            analysis_process.join()
            playback_process.join()

        except KeyboardInterrupt:
            print("\n[STOP] Keyboard interrupt detected. Terminating processes...")
        finally:
            # 7. Cleanly terminate all child processes
            if playback_process and playback_process.is_alive():
                playback_process.terminate()
                playback_process.join()
                print("Playback process terminated.")

            if analysis_process and analysis_process.is_alive():
                analysis_process.terminate()
                analysis_process.join()
                print("Analysis process terminated.")

            # 8. Close the DMX port from the main process
            dmx.stop_broadcast()
            dmx.close()
            print("\n[END] DMX broadcast stopped and port closed.")
