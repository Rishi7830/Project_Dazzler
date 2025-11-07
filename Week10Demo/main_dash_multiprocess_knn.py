"""
Realtime MP3 → Feature Analysis + DMX output.
Controls TWO lights:
- Light 1: 5-second Mood Color (brightness = loudness)
- Light 2: Real-time Genre/Tempo Color (brightness = loudness)
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
from tempo_detection import detect_tempo
from loudness_detection import detect_loudness
from mode_key_detection import detect_mode_key
from audio_analyzer import process_audio_features # Used for Light 2's hue_speed

# Import all necessary functions from color_mapper, including the new mapping function
from color_mapper import get_available_genres, genre_color_palettes, map_features_to_genre_color # Used for Light 2

# +++ 1. IMPORT MOOD PREDICTOR +++
try:
    from knn_prediction import MoodPredictor 
except ImportError:
    print("[ERR] Could not find 'knn_prediction.py'. Mood prediction disabled.")
    MoodPredictor = None
import joblib
# ++++++++++++++++++++++++++++++++

try:
    from pyserial import SimpleDMX
except Exception as e:
    print(f"[WARN] Could not import SimpleDMX: {e}")
    SimpleDMX = None

# UI INTEGRATION AND SETUP FUNCTIONS
def get_user_inputs_from_ui():
    # ... (This function is unchanged)
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
    # ... (This function is unchanged)
    """Suggests a default DMX port based on the operating system."""
    sysname = platform.system().lower()
    if sysname.startswith("win"):
        return os.environ.get("DAZZLER_DMX_PORT", "COM3")
    if sysname == "darwin":
        return os.environ.get("DAZZLER_DMX_PORT", "/dev/tty.usbserial")
    return os.environ.get("DAZZLER_DMX_PORT", "/dev/ttyUSB1")

# +++ 2. MODIFIED DMX CLASS +++
# This class now accepts TWO light values.
#
#    ******************************************************************
#    * IMPORTANT: You MUST update your *real* SimpleDMX class         *
#    * to accept these new arguments in its update_lighting method.   *
#    * You will need to map mood_rgbw and genre_rgbw to separate      *
#    * DMX channels (e.g., channels 1-4 and 5-8).                     *
#    ******************************************************************
#
class _NoopDMX:
    def start_broadcast(self): print("[DMX] Broadcast disabled (no hardware)")
    def stop_broadcast(self): pass
    def close(self): pass
    
    # --- UPDATED SIGNATURE ---
    def update_lighting(self, mood_rgbw, genre_rgbw, hue_speed):
        print(f"[DMX] (noop) Mood Light:   R{mood_rgbw[0]} G{mood_rgbw[1]} B{mood_rgbw[2]} W{mood_rgbw[3]}")
        print(f"[DMX] (noop) Genre Light:  R{genre_rgbw[0]} G{genre_rgbw[1]} B{genre_rgbw[2]} W{genre_rgbw[3]}")
        print(f"[DMX] (noop) Shared Speed: {hue_speed:.2f}")

def init_dmx_controller(port: str | None = None, num_channels: int = 9):
    # ... (This function is unchanged)
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

# +++ 3. NEW MOOD-COLOR MAPPING FUNCTION +++
def get_mood_color(mood_name: str, loudness: float) -> tuple:
    """
    Maps a predicted mood and real-time loudness to an (R, G, B, W) tuple.
    Colors are based on Russell's circumplex model (your image).
    """
    # (R, G, B) colors from your image at full brightness
    MOOD_COLOR_MAP = {
        "Pleasure":     (255, 255, 0),   # Yellow
        "Excitement":   (255, 128, 0),   # Orange
        "Arousal":      (255, 0, 0),     # Red
        "Distress":     (200, 0, 100),   # Magenta/Red-Purple
        "Displeasure":  (100, 0, 200),   # Purple
        "Depression":   (0, 0, 150),     # Dark Blue
        "Sleepiness":   (0, 50, 0),      # Dark Green
        "Relaxation":   (0, 200, 50),    # Light Green
    }
    # Default color for "Initializing", "N/A", or "Pred. Err"
    DEFAULT_COLOR = (0, 0, 128) # Neutral Blue
    
    # 1. Get the base color for the current mood
    base_r, base_g, base_b = MOOD_COLOR_MAP.get(mood_name, DEFAULT_COLOR)
    
    # 2. Scale brightness based on real-time loudness
    # We map loudness from a quiet level (-60dB) to just before strobe (80dB)
    # to a brightness scale of 10% (min) to 100% (max).
    brightness_scale = np.interp(loudness, [-60, 80], [0.1, 1.0])
    brightness_scale = float(np.clip(brightness_scale, 0.1, 1.0))

    # 3. Calculate final color and return as (R, G, B, W) tuple
    r = int(base_r * brightness_scale)
    g = int(base_g * brightness_scale)
    b = int(base_b * brightness_scale)
    
    return (r, g, b, 0)

# +++ 4. MODIFIED REAL-TIME STREAMING FUNCTION +++
# +++ 4. MODIFIED REAL-TIME STREAMING FUNCTION +++
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
    and update DMX lighting, strictly adhering to real-time.
    """
    mp3_path = str(mp3_path)
    if not Path(mp3_path).exists():
        print(f"[ERR] File not found: {mp3_path}")
        return

    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-i", mp3_path,
        "-f", "f32le", "-ac", str(channels), "-ar", str(sample_rate), "pipe:1",
    ]

    # +++ 1. INITIALIZE PROC TO NONE +++
    proc = None 
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    except FileNotFoundError:
        print("[ERR] ffmpeg not found in PATH; install ffmpeg and retry")
        return
    except Exception as e:
        print(f"[ERR] Could not start ffmpeg: {e}")
        return

    # 3-2-1 countdown
    countdown_colors = [(255, 0, 0, 0), (255, 128, 0, 0), (255, 255, 0, 0)]
    for i, color in enumerate(reversed(countdown_colors), start=1):
        dmx.update_lighting(color, color, hue_speed=0)
        print(f"Countdown: {4 - i}")
        time.sleep(1)

    # --- Initialize Mood Predictor ---
    print("[ML] Loading MoodPredictor model...")
    predictor = None
    if MoodPredictor:
        predictor = MoodPredictor(model_path='knn_model.joblib', scaler_path='scaler.joblib')
        if predictor.model is None:
            print("[ERR] Failed to load ML model. Mood prediction will be disabled.")
            predictor = None
    
    bytes_per_sample = 4
    frame_bytes = audio_block * channels * bytes_per_sample
    chunk_samples = int(chunk_seconds * sample_rate)
    hop_samples = max(1, int(chunk_samples * hop_ratio))
    analysis_buffer = np.empty(0, dtype=np.float32)
    results = []
    
    start_time = time.time()
    strobe_toggle = False    
    current_predicted_mood = "Initializing"
    last_mood_prediction_time = -5.0
    mood_prediction_interval = 5.0

    print(f"[RUN] Streaming {Path(mp3_path).name} ({genre.title()}) - Mood updates every {mood_prediction_interval}s")

    try:
        while True:
            raw = proc.stdout.read(frame_bytes)
            if not raw or len(raw) < frame_bytes:
                break # Song finished
            
            time.sleep(0.001) 
            block = np.frombuffer(raw, dtype=np.float32)
            analysis_buffer = np.concatenate((analysis_buffer, block))

            while analysis_buffer.size >= chunk_samples:
                
                # ... (time_position, sleep_needed logic) ...
                time_position = (len(results) * hop_samples) / sample_rate
                actual_elapsed_time = time.time() - start_time
                sleep_needed = time_position - actual_elapsed_time
                if sleep_needed > 0.005:
                    time.sleep(sleep_needed)
                    
                window = analysis_buffer[:chunk_samples]

                # ... (feature, mood, and lighting logic) ...
                # --- 1. Calculate Real-time Features ---
                mode_str, key = detect_mode_key(window, sample_rate)
                tempo = detect_tempo(window, sample_rate)
                loudness = detect_loudness(window, sample_rate)
                
                # --- 2. Calculate Mood (every 5 seconds) ---
                if (time_position - last_mood_prediction_time) >= mood_prediction_interval:
                    if predictor:
                        harmony = 'simple' 
                        rhythm = np.random.uniform(0.3, 0.7)
                        try:
                            mode_numeric = 1 if mode_str == 'major' else 0 
                            features_list = [mode_numeric, harmony, tempo, rhythm, loudness]
                            current_predicted_mood = predictor.predict_mood(features_list)
                            last_mood_prediction_time = time_position
                        except Exception as e:
                            current_predicted_mood = "Pred. Err"
                    else:
                        current_predicted_mood = "N/A"

                # --- 3. Calculate Lighting Outputs ---
                _feature_output, hue_speed = process_audio_features(
                    loudness=loudness, mode=mode_str, key=key, tempo=tempo
                )

                if loudness > 80:
                    strobe_toggle = not strobe_toggle
                    strobe_rgbw = (255, 255, 255, 0) if strobe_toggle else (0, 0, 0, 0)
                    dmx.update_lighting(strobe_rgbw, strobe_rgbw, hue_speed)
                    mood_rgbw = strobe_rgbw
                    genre_rgbw = strobe_rgbw
                
                else:
                    mood_rgbw = get_mood_color(current_predicted_mood, loudness)
                    mapped_rgb = map_features_to_genre_color(loudness=loudness, tempo=tempo, genre=genre)
                    genre_rgbw = (int(mapped_rgb[0]), int(mapped_rgb[1]), int(mapped_rgb[2]), 0)
                    dmx.update_lighting(mood_rgbw, genre_rgbw, hue_speed)

                # --- 4. Print and Store Results ---
                print(f"[{time_position:6.2f}s] Mood:{current_predicted_mood:12s} | L:{loudness:5.2f}dB | T:{tempo:3.0f}bpm -> MoodRGB{mood_rgbw[:3]} | GenreRGB{genre_rgbw[:3]}")

                results.append({
                    "time_position": time_position,
                    "features": {"mode": mode_str, "key": key, "tempo": float(tempo), "loudness": float(loudness)},
                    "mood_prediction": current_predicted_mood,
                    "lighting": {
                        "mood_light": mood_rgbw, 
                        "genre_light": genre_rgbw, 
                        "hue_speed": float(hue_speed)
                    }
                })

                analysis_buffer = analysis_buffer[hop_samples:]

        # +++ 2. ADDED NORMAL SHUTDOWN +++
        # This runs when the 'while True' loop breaks (song ends)
        print("\n[INFO] Song stream finished. Cleaning up ffmpeg.")
        if proc.stdout:
            proc.stdout.close()
        proc.wait() # Wait for ffmpeg to exit cleanly

    except KeyboardInterrupt:
        print("\n[STOP] Interrupted by user")
        # 'finally' block will handle cleanup
    
    except Exception as e:
        print(f"[ERR] Runtime Exception: {e}")
        traceback.print_exc()
        # 'finally' block will handle cleanup

    finally:
        # +++ 3. SAFER CLEANUP BLOCK +++
        # This runs on ANY exit (normal, error, or Ctrl+C)
        # We only kill the process if it exists AND is still running
        if proc and proc.poll() is None:
            print("[INFO] Forcibly terminating ffmpeg process...")
            proc.kill()
            proc.wait()

    # --- JSON Saving (now outside the try/except/finally) ---
    if save_json and results:
        out_dir = Path(__file__).parent / "outputs"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / f"lighting_data_{Path(mp3_path).stem}_{genre}_realtime.json"
        
        def convert_to_float(obj):
            if isinstance(obj, (np.floating, np.integer)):
                return float(obj)
            if isinstance(obj, np.ndarray):
                return obj.tolist()
            return obj
            
        with open(out_file, "w") as f:
            json.dump(results, f, indent=2, default=convert_to_float)
        print(f"\n[OK] Saved {len(results)} analysis windows to {out_file}")


if __name__ == "__main__":
    # ... (This whole section is unchanged) ...
    
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