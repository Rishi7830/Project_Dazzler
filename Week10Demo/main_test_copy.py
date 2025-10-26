"""
Realtime MP3 → Feature Analysis + DMX output.
Includes Real-Time Synchronization, Loudness-Based Color Mapping, and Dynamic Loudness Strobe.
Controls two 9-channel DMX fixtures:
- Fixture 1 (Channels 1-9): Dynamic Light Show (Hue Cycle, Strobe)
- Fixture 2 (Channels 10-18): Static Purple
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
# NOTE: The 'audio_playback' module and 'dazzler_ui' module are assumed to exist.
from audio_playback import play_audio 

# Import the UI class from your separate file
from dazzler_ui import DazzlerDashboard 

# Import your custom feature modules
from tempo_detection import detect_tempo
from loudness_detection import detect_loudness
from mode_key_detection import detect_mode_key
from audio_analyzer import process_audio_features
# Import your custom feature modules
from Harmony_Detection import extract_harmony
from Rhythm_Detection import extract_rhythm
from knn_prediction import preprocess_features, predict_mood # Import mood prediction

# Import all necessary functions from color_mapper, including the new mapping function
from color_mapper import get_available_genres, genre_color_palettes, map_features_to_genre_color

# Correct import for your provided SimpleDMX class (assuming it's in a file named pyserial_new.py)
try:
    from pyserial_new import (
        SimpleDMX, 
        CH_DIMMER_1, CH_RED_1, CH_GREEN_1, CH_BLUE_1, CH_WHITE_1, CH_STROBE_1, CH_SOUND_1, 
        CH_DIMMER_2, CH_RED_2, CH_GREEN_2, CH_BLUE_2, CH_WHITE_2, CH_STROBE_2, CH_SOUND_2, 
        VAL_LED_START, VAL_STROBE_FAST, VAL_FADE_FAST, VAL_LIGHTNING, VAL_LED_OFF # <-- ADDED MISSING CONSTANTS
    )
except Exception as e:
    print(f"[WARN] Could not import SimpleDMX or constants: {e}")
    SimpleDMX = None

# UI INTEGRATION AND SETUP FUNCTIONS (NO CHANGES)
def get_user_inputs_from_ui():
    """Launches the UI and waits for user input via the Start Dazzling! button."""
    root = tk.Tk()
    app = DazzlerDashboard(root)
    app.submission_successful = False
    
    def master_submit_and_close():
        app.master_submit()
        if app.genre_var.get() and app.com_port_var.get() and app.song_name_var.get():
            app.submission_successful = True
            root.quit()
        else:
            print("Validation failed in UI. Please check inputs.")

    app.master_button.config(command=master_submit_and_close)
    root.mainloop()
    
    if app.submission_successful:
        selected_genre = app.genre_var.get().lower()
        filepath = app.song_name_var.get().strip().strip('"')
        dmx_port = app.com_port_var.get().strip()
        
        if not os.path.exists(Path(filepath).expanduser()):
             print(f"[ERR] File not found: {filepath}. Please re-run and check the path.")
             return None, None, None
             
        root.destroy()
        return selected_genre, filepath, dmx_port
    else:
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

# The _NoopDMX must be modified to mimic the main loop's channel setting
class _NoopDMX:
    def __init__(self):
        self.data = [0] * 18 # Initialize internal data array
    def start_broadcast(self): print("[DMX] Broadcast disabled (no hardware)")
    def stop_broadcast(self): pass
    def close(self): pass
    # Mimic the real DMX object's methods for logging
    def set_channel_internal(self, ch: int, value: int):
        if 1 <= ch <= 18:
            self.data[ch - 1] = max(0, min(255, value))
    def send_frame(self): 
        # Log the state of the first and second fixture
        print(f"[DMX] (noop) F1: R{self.data[CH_RED_1-1]} G{self.data[CH_GREEN_1-1]} B{self.data[CH_BLUE_1-1]} | F2: R{self.data[CH_RED_2-1]} B{self.data[CH_BLUE_2-1]}")
    # Placeholder set_channel for the countdown
    def set_channel(self, ch: int, value: int):
        self.set_channel_internal(ch, value)

def init_dmx_controller(port: str | None = None, num_channels: int = 18):
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
    and update DMX lighting using dmx.set_channel_internal() and dmx.send_frame().

    Fixture 1 (Ch1–9): Loudness/Tempo-based dynamic color & strobe
    Fixture 2 (Ch10–18): Mood-based static color
    """
    mp3_path = str(mp3_path)
    if not Path(mp3_path).exists():
        print(f"[ERR] File not found: {mp3_path}")
        return

    # --- FFmpeg audio stream setup ---
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-i", mp3_path,
        "-f", "f32le", "-ac", str(channels), "-ar", str(sample_rate), "pipe:1",
    ]
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    except FileNotFoundError:
        print("[ERR] ffmpeg not found in PATH; install ffmpeg and retry")
        return

    # --- Countdown effect before start ---
    countdown_colors = [(255, 0, 0, 0), (255, 128, 0, 0), (255, 255, 0, 0)]
    for i, color in enumerate(reversed(countdown_colors), start=1):
        dmx.set_channel(CH_RED_1, color[0])
        dmx.set_channel(CH_GREEN_1, color[1])
        dmx.set_channel(CH_BLUE_1, color[2])
        dmx.send_frame()
        print(f"Countdown: {4 - i}")
        time.sleep(1)

    # Start playback in the same process (optional)
    play_audio(mp3_path)

    bytes_per_sample = 4
    frame_bytes = audio_block * channels * bytes_per_sample
    chunk_samples = int(chunk_seconds * sample_rate)
    hop_samples = max(1, int(chunk_samples * hop_ratio))
    analysis_buffer = np.empty(0, dtype=np.float32)
    results = []

    start_time = time.time()
    previous_loudness = 0.0
    strobe_toggle = False
    LOUDNESS_JUMP_THRESHOLD = 5.0  # dB increase for strobe trigger

    print(f"[RUN] Streaming {Path(mp3_path).name} ({genre.title()})")
    print(f"[INFO] Mood-driven Fixture 2, Loudness-driven Fixture 1")

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

                # --- Feature extraction ---
                mode, key = detect_mode_key(window, sample_rate)
                tempo = detect_tempo(window, sample_rate)
                loudness = detect_loudness(window, sample_rate)
                rhythm = extract_rhythm(window)
                harmony = extract_harmony(window)

                # --- Mood prediction ---
                features_processed = preprocess_features(mode, tempo, loudness, rhythm, harmony)
                mood = predict_mood(features_processed)

                # --- Feature-based processing for master fixture ---
                feature_output, hue_speed = process_audio_features(
                    loudness=loudness, mode=mode, key=key, tempo=tempo
                )

                # ========== FIXTURE 1 (MASTER): loudness-driven ==========
                log_strobe = False
                strobe_channel_value = VAL_LED_START

                if loudness - previous_loudness > LOUDNESS_JUMP_THRESHOLD:
                    strobe_toggle = not strobe_toggle
                    r, g, b, w = (255, 255, 255, 0) if strobe_toggle else (0, 0, 0, 0)
                    strobe_channel_value = VAL_STROBE_FAST
                    log_strobe = True
                else:
                    mapped_rgb = map_features_to_genre_color(loudness=loudness, tempo=tempo, genre=genre)
                    r, g, b = mapped_rgb
                    w = 0

                dimmer_value = np.clip(np.interp(loudness, [40, 100], [50, 255]), 0, 255).astype(int)
                speed_value = np.clip(np.interp(hue_speed, [0, 1], [0, 239]), 0, 239).astype(int)

                dmx.set_channel_internal(CH_RED_1, int(r))
                dmx.set_channel_internal(CH_GREEN_1, int(g))
                dmx.set_channel_internal(CH_BLUE_1, int(b))
                dmx.set_channel_internal(CH_WHITE_1, int(w))
                dmx.set_channel_internal(CH_DIMMER_1, dimmer_value)
                dmx.set_channel_internal(CH_STROBE_1, strobe_channel_value)
                dmx.set_channel_internal(CH_SOUND_1, speed_value)

                # ========== FIXTURE 2 (SLAVE): mood-driven ==========
                # Map mood to color palette (define your mood-color mapping)
                mood_colors = {
                    "Happy": (255, 200, 0),
                    "Calm": (0, 128, 255),
                    "Energetic": (255, 0, 128),
                    "Sad": (100, 100, 255),
                    "Tense": (255, 64, 0),
                    "Romantic": (255, 0, 255),
                }
                mood_rgb = mood_colors.get(mood, (128, 128, 128))  # default grey if undefined
                r2, g2, b2 = mood_rgb
                w2 = 0
                dimmer2 = 255  # always on

                dmx.set_channel_internal(CH_RED_2, int(r2))
                dmx.set_channel_internal(CH_GREEN_2, int(g2))
                dmx.set_channel_internal(CH_BLUE_2, int(b2))
                dmx.set_channel_internal(CH_WHITE_2, int(w2))
                dmx.set_channel_internal(CH_DIMMER_2, dimmer2)
                dmx.set_channel_internal(CH_STROBE_2, VAL_LED_START)
                dmx.set_channel_internal(CH_SOUND_2, 0)

                # --- Send frame ---
                dmx.send_frame()

                # --- Log info ---
                rgbw_master = (int(r), int(g), int(b), int(w))
                rgbw_slave = (int(r2), int(g2), int(b2), int(w2))
                if log_strobe:
                    print(f"[{time_position:6.2f}s] L:{loudness:5.2f}dB (+{loudness - previous_loudness:.2f}dB JUMP!) | T:{tempo:3.0f}bpm | Mood:{mood:10s} | Fixture1->STROBE | Fixture2->RGB{rgbw_slave[:3]}")
                else:
                    print(f"[{time_position:6.2f}s] L:{loudness:5.2f}dB | T:{tempo:3.0f}bpm | Mood:{mood:10s} | F1->RGB{rgbw_master[:3]} | F2->RGB{rgbw_slave[:3]}")

                # --- Record and cleanup ---
                previous_loudness = loudness
                results.append({
                    "time_position": time_position,
                    "features": {"mode": mode, "key": key, "tempo": float(tempo), "loudness": float(loudness)},
                    "mood": mood,
                    "lighting": {
                        "master_rgbw": rgbw_master,
                        "slave_rgbw": rgbw_slave,
                        "feature_output": str(feature_output),
                        "dimmer_master": dimmer_value,
                    },
                })
                analysis_buffer = analysis_buffer[hop_samples:]

        proc.stdout.close()
        proc.wait()

        # --- Save JSON results ---
        if save_json and results:
            out_dir = Path(__file__).parent / "outputs"
            out_dir.mkdir(parents=True, exist_ok=True)
            out_file = out_dir / f"lighting_data_{Path(mp3_path).stem}_{genre}_realtime.json"
            def convert_to_float(obj):
                if isinstance(obj, np.floating):
                    return float(obj)
                return obj
            with open(out_file, "w") as f:
                json.dump(results, f, indent=2, default=convert_to_float)
            print(f"\n[OK] Saved {len(results)} analysis windows to {out_file}")

    except KeyboardInterrupt:
        print("\n[STOP] Interrupted by user")
    except Exception as e:
        print(f"[ERR] Runtime Exception: {e}")
        proc.kill()
        traceback.print_exc()
    finally:
        pass


if __name__ == "__main__":
    
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

        # Initialize DMX for 18 channels
        dmx = init_dmx_controller(port=dmx_port, num_channels=18)
        
        try:
            print("Starting the music and lighting show...")
            stream_mp3_realtime(
                mp3_path=mp3_file_path,
                dmx=dmx,
                genre=selected_genre,
                chunk_seconds=0.25,
                hop_ratio=0.5,
            )
        finally:
            # The close() method in SimpleDMX already handles stopping broadcast and clearing channels
            dmx.close() 
            print("\n[END] DMX broadcast stopped and port closed.")
