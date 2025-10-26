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
from audio_playback import play_audio

# Import the UI class from your separate file
from dazzler_ui import DazzlerDashboard 

# Import your custom feature modules
from tempo_detection import detect_tempo
from loudness_detection import detect_loudness
from mode_key_detection import detect_mode_key
from audio_analyzer import process_audio_features

# Import all necessary functions from color_mapper, including the new mapping function
from color_mapper import get_available_genres, genre_color_palettes, map_features_to_genre_color

try:
    from pyserial_new import SimpleDMX
except Exception as e:
    print(f"[WARN] Could not import SimpleDMX: {e}")
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


class _NoopDMX:
    def start_broadcast(self): print("[DMX] Broadcast disabled (no hardware)")
    def stop_broadcast(self): pass
    def close(self): pass
    
    # NOTE: The signature for this function is changing in the custom DMX logic below
    # We will use a print that reflects the manual channel array instead of rgbw_tuple/hue_speed
    def send_array(self, dmx_array):
        # Only print the first 18 channels if the array is longer
        print(f"[DMX] (noop) Array ({len(dmx_array)} ch): {dmx_array[:18]}")

# Custom DMX class to override update_lighting with send_array for manual channel control
class ManualDMX(SimpleDMX):
    def update_lighting(self, dmx_array):
        # Assuming SimpleDMX has a `send_array` method that takes a list of values 
        # for channels 1 through N
        self.send_array(dmx_array)

def init_dmx_controller(port: str | None = None, num_channels: int = 18):
    if SimpleDMX is None:
        return _NoopDMX()
    port = port or _suggest_default_port()
    try:
        # We need to wrap SimpleDMX to use our manual send_array approach
        # For this exercise, we will assume SimpleDMX has a `send_array` or similar
        # method that takes a list of 18 values for the channels.
        if SimpleDMX is not None:
             dmx = SimpleDMX(port=port)
             dmx.start_broadcast()
             print(f"[DMX] Started on {port} channels={num_channels}")
             return dmx
        else:
             return _NoopDMX()

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
    and update DMX lighting, strictly adhering to real-time.
    Controls two 9-channel fixtures.
    """
    mp3_path = str(mp3_path)
    if not Path(mp3_path).exists():
        print(f"[ERR] File not found: {mp3_path}")
        return

    # ffmpeg setup (NO CHANGE)
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-i", mp3_path,
        "-f", "f32le", "-ac", str(channels), "-ar", str(sample_rate), "pipe:1",
    ]
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    except FileNotFoundError:
        print("[ERR] ffmpeg not found in PATH; install ffmpeg and retry")
        return

    # 3-2-1 countdown (NO CHANGE)
    countdown_colors = [(255, 0, 0, 0), (255, 128, 0, 0), (255, 255, 0, 0)]
    for i, color in enumerate(reversed(countdown_colors), start=1):
        # NOTE: Using placeholder update for countdown as we don't have a specific `update_lighting` for a list
        # We'll rely on the DMX object having a simple initial setting capability
        if not isinstance(dmx, _NoopDMX):
            # For a real SimpleDMX object, you might need dmx.set_channel(1, 255) etc.
            # Assuming a basic method for this temporary step:
            dmx.set_channel(1, color[0])
            dmx.set_channel(2, color[1])
            dmx.set_channel(3, color[2])
            dmx.send_update()
        print(f"Countdown: {4 - i}")
        time.sleep(1)
        
    play_audio(mp3_path)
    bytes_per_sample = 4
    frame_bytes = audio_block * channels * bytes_per_sample
    chunk_samples = int(chunk_seconds * sample_rate)
    hop_samples = max(1, int(chunk_samples * hop_ratio))
    analysis_buffer = np.empty(0, dtype=np.float32)
    results = []
    
    start_time = time.time()
    strobe_toggle = False
    
    # --- DYNAMIC LOUDNESS VARIABLES FOR STROBE ---
    previous_loudness = 0.0 
    LOUDNESS_JUMP_THRESHOLD = 5.0 # Must jump 5 dB from previous chunk to strobe
    # ---------------------------------------------

    # --- STATIC PURPLE FIXTURE SETTINGS (Fixture 2, Channels 10-18) ---
    # Assuming a 9-channel fixture in Mode 2 (RGBW + Control/Strobe/Dimmer/Speed)
    # The channels are usually: 
    # 1: Control (Dimmer), 2: R, 3: G, 4: B, 5: W, 6: Strobe, 7: Color Macro, 8: Speed/Control, 9: Reserved
    
    # Purple RGB (approx 128, 0, 128) - Maximize Dimmer/Control for full brightness
    STATIC_PURPLE_CHANNELS = [
        255,  # Ch 10 (Control/Dimmer - Max brightness)
        128,  # Ch 11 (R)
        0,    # Ch 12 (G)
        128,  # Ch 13 (B)
        0,    # Ch 14 (W)
        0,    # Ch 15 (Strobe - Off)
        0,    # Ch 16 (Color Macro - Off)
        0,    # Ch 17 (Speed/Control - Off/Static)
        0,    # Ch 18 (Reserved)
    ]
    # ------------------------------------------------------------------

    print(f"[RUN] Streaming {Path(mp3_path).name} ({genre.title()}) - chunk={chunk_seconds}s, hop={hop_ratio}")
    print(f"[INFO] Dynamic Strobe Threshold: +{LOUDNESS_JUMP_THRESHOLD} dB increase.")

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

                mode, key = detect_mode_key(window, sample_rate)
                tempo = detect_tempo(window, sample_rate)
                loudness = detect_loudness(window, sample_rate)
                
                feature_output, hue_speed = process_audio_features(
                    loudness=loudness, mode=mode, key=key, tempo=tempo
                )

                # 1. Calculate Fixture 1 (Master) Color
                
                # Default to dynamic color
                mapped_rgb = map_features_to_genre_color(loudness=loudness, tempo=tempo, genre=genre)
                r, g, b = mapped_rgb
                rgbw_master = (int(r), int(g), int(b), 0)
                
                log_strobe = False
                # Check for Loudness Jump (Strobe Trigger)
                if loudness - previous_loudness > LOUDNESS_JUMP_THRESHOLD:
                    # Override color to white/black flash
                    strobe_toggle = not strobe_toggle
                    rgbw_master = (255, 255, 255, 0) if strobe_toggle else (0, 0, 0, 0)
                    log_strobe = True
                
                # 2. Build Fixture 1 (Master) Channel Data (Ch 1-9)
                
                # Assuming the master light uses a similar 9-channel mode:
                # Ch 1: Dimmer/Control, Ch 2-5: RGBW, Ch 6: Strobe, Ch 7-9: Speed/Control/Macro
                # Note: We use the hue_speed on the DMX object for control, not a channel value.
                # If SimpleDMX requires speed control via a channel, this part needs adjustment.
                
                # We'll use Channel 1 for the intensity (dimmer) based on loudness for flair.
                # Map loudness (e.g., 40-100dB) to dimmer (0-255)
                dimmer_value = np.clip(np.interp(loudness, [40, 100], [50, 255]), 0, 255).astype(int)
                
                # Use a high value for speed channel (Ch 8) based on hue_speed. 
                # Scaling hue_speed (0-1) to DMX channel range (0-255)
                speed_value = np.clip(np.interp(hue_speed, [0, 1], [0, 255]), 0, 255).astype(int)

                MASTER_CHANNELS = [
                    dimmer_value,        # Ch 1 (Control/Dimmer)
                    rgbw_master[0],      # Ch 2 (R)
                    rgbw_master[1],      # Ch 3 (G)
                    rgbw_master[2],      # Ch 4 (B)
                    rgbw_master[3],      # Ch 5 (W)
                    0,                   # Ch 6 (Strobe - keep off, as we strobe by color)
                    0,                   # Ch 7 (Color Macro)
                    speed_value,         # Ch 8 (Speed/Control)
                    0,                   # Ch 9 (Reserved)
                ]
                
                # 3. Combine Master and Static Slave Channels (Total 18 Channels)
                dmx_array = MASTER_CHANNELS + STATIC_PURPLE_CHANNELS

                # 4. Send Array
                if not isinstance(dmx, _NoopDMX):
                    # For a real SimpleDMX, this is the crucial call:
                    dmx.send_array(dmx_array)
                else:
                    # Use the no-op fallback
                    dmx.send_array(dmx_array)


                # 5. Logging and Cleanup
                if log_strobe:
                    print(f"[{time_position:6.2f}s] L:{loudness:5.2f}dB (+{loudness - previous_loudness:.2f}dB JUMP!) | T:{tempo:3.0f}bpm | Fixture 1 -> STROBE")
                else:
                    print(f"[{time_position:6.2f}s] L:{loudness:5.2f}dB | T:{tempo:3.0f}bpm | Feature:{str(feature_output):12s} | Fixture 1 -> RGB{rgbw_master[:3]}")
                
                # Update loudness for next iteration
                previous_loudness = loudness
                
                results.append({
                    "time_position": time_position,
                    "features": {"mode": mode, "key": key, "tempo": float(tempo), "loudness": float(loudness)},
                    "lighting": {"feature_output": str(feature_output), "master_rgbw": rgbw_master, "slave_rgbw": STATIC_PURPLE_CHANNELS[1:5], "hue_speed_mapped": speed_value}
                })

                analysis_buffer = analysis_buffer[hop_samples:]

        proc.stdout.close()
        proc.wait()

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
            if not isinstance(dmx, _NoopDMX):
                 # Turn off lights gracefully by sending 0 to all channels (or just dimmer/RGB)
                 dmx.send_array([0] * 18) 
                 dmx.stop_broadcast()
                 dmx.close()
            print("\n[END] DMX broadcast stopped and port closed.")
