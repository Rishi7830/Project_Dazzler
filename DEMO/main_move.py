import os
import time
import platform
import subprocess
import json
import numpy as np
import traceback
from pathlib import Path
import tkinter as tk
import random

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

# Correct import for your provided SimpleDMX class (assuming it's in a file named pyserial_new.py)
try:
    from pyserial_move import (
        SimpleDMX,
        CH_DIMMER_1, CH_RED_1, CH_GREEN_1, CH_BLUE_1, CH_WHITE_1, CH_STROBE_1, CH_SOUND_1,
        CH_DIMMER_2, CH_RED_2, CH_GREEN_2, CH_BLUE_2, CH_WHITE_2, CH_STROBE_2, CH_SOUND_2,
        CH_PAN_2, CH_TILT_2, # <--- DMX CHANNELS for Fixture 2
        VAL_LED_START, VAL_STROBE_FAST, VAL_FADE_FAST, VAL_LIGHTNING, VAL_LED_OFF
    )
except Exception as e:
    print(f"[WARN] Could not import SimpleDMX or constants: {e}")
    # Define required constants for the NoopDMX to work if import fails
    CH_PAN_2, CH_TILT_2 = 10, 11
    VAL_LED_START = 0
    SimpleDMX = None

# --- DMX MOVEMENT CONSTANTS (FINAL SCENE CONFIGURATION) ---
PAN_CENTER = 150        # Keep Pan center consistent
TILT_CENTER = 80        # Faces light toward the stage floor/audience (down)

# Interpolation factor for smooth transitions between scenes (0.08 is a smooth fade)
INTERP_ALPHA = 0.08 

LOUDNESS_LOW_THRESHOLD = 50.0  # dB threshold for starting movement (Scene 2)
LOUDNESS_MED_THRESHOLD = 80.0  # dB threshold for increasing movement speed (Scene 3)

# SCENE 1 (Low Loudness < 50dB): Slow Up Drift
DRIFT_AMP = 30          # Amplitude for subtle tilt movement
DRIFT_SPEED_FREQ = 0.05 # Very slow movement (approx 20 seconds per cycle)
MOVEMENT_FIXED_PAN = PAN_CENTER

# SCENE 2 (Medium Loudness 50-80dB): Medium Rotation
AMP_PAN_MED = 80        # Wide horizontal sweep (160 DMX range)
AMP_TILT_MED = 25       # <-- REDUCED from 40 to 25. Keeps tilt range lower.
FREQ_MED = 0.5          # Medium speed movement (2 seconds per cycle)

# SCENE 3 (High Loudness >= 80dB): Fast Rotation
AMP_PAN_HIGH = 100      # Very wide horizontal sweep (200 DMX range)
AMP_TILT_HIGH = 35      # <-- REDUCED from 50 to 35. Keeps tilt range lower.
FREQ_HIGH = 1.0         # Fastest speed movement (1 second per cycle)

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
            # Need to handle case where CH_PAN_2/CH_TILT_2 might not exist, but assume they do
            if ch - 1 < len(self.data):
                self.data[ch - 1] = max(0, min(255, value))
    def send_frame(self): 
        # Log the state of the first and second fixture
        f1_r = self.data[CH_RED_1-1]
        f1_g = self.data[CH_GREEN_1-1]
        f1_b = self.data[CH_BLUE_1-1]
        f2_r = self.data[CH_RED_2-1]
        f2_g = self.data[CH_GREEN_2-1]
        f2_b = self.data[CH_BLUE_2-1]
        f2_tilt = self.data[CH_TILT_2-1] # Log Tilt for Fixture 2
        f2_pan = self.data[CH_PAN_2-1]
        print(f"[DMX] (noop) F1: R{f1_r} G{f1_g} B{f1_b} | F2: RGB{f2_r, f2_g, f2_b} PAN:{f2_pan} TILT:{f2_tilt}")
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


# REAL-TIME STREAMING AND ANALYSIS


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
        dmx.set_channel(CH_RED_1, color[0])
        dmx.set_channel(CH_GREEN_1, color[1])
        dmx.set_channel(CH_BLUE_1, color[2])
        dmx.send_frame()
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
    
    # DYNAMIC LOUDNESS VARIABLES FOR STROBE (Fixture 1)
    previous_loudness = 0.0
    LOUDNESS_JUMP_THRESHOLD = 25.0


    # TIMED COLOR FIXTURE 2 (SLAVE) SETUP (Channels 10-18)
    COLOR_CHANGE_INTERVAL = 5.0 # Change color every 5 seconds
    
    # Palette provided by user
    INDEPENDENT_PALETTE = [
        (255, 69, 0),    # OrangeRed
        (255, 20, 147),  # DeepPink
        (0, 128, 0),     # Green
        (160, 32, 240),  # Purple
        (165, 42, 42)    # Brown
    ]
    
    # Initial state for Fixture 2 Color Cycle
    current_slave_color = random.choice(INDEPENDENT_PALETTE)
    last_color_change_time = 0.0

    # Initialize current DMX Pan/Tilt values for smoothing
    current_pan = float(PAN_CENTER)
    current_tilt = float(TILT_CENTER)

    # Set Fixture 2 constants (Dimmer, Strobe, Sound)
    dmx.set_channel_internal(CH_DIMMER_2, 255)       # Full Dimmer
    dmx.set_channel_internal(CH_STROBE_2, VAL_LED_START) # Constant Light
    dmx.set_channel_internal(CH_SOUND_2, 0)          # Sound Control Off

    # Apply the initial color (R, G, B, W=0)
    R2, G2, B2, W2 = current_slave_color[0], current_slave_color[1], current_slave_color[2], 0
    dmx.set_channel_internal(CH_RED_2, R2)
    dmx.set_channel_internal(CH_GREEN_2, G2)
    dmx.set_channel_internal(CH_BLUE_2, B2)
    dmx.set_channel_internal(CH_WHITE_2, W2)

    # Apply initial fixed Pan and Tilt
    dmx.set_channel_internal(CH_PAN_2, int(current_pan)) 
    dmx.set_channel_internal(CH_TILT_2, int(current_tilt)) 

    # Send the frame immediately to set the slave fixture's initial state
    dmx.send_frame()
    
    print(f"[RUN] Streaming {Path(mp3_path).name} ({genre.title()}) - chunk={chunk_seconds}s, hop={hop_ratio}")
    print(f"[INFO] Fixture 2: Color cycling ({COLOR_CHANGE_INTERVAL}s) + Dynamic 3-Scene Movement with Smoothing (Alpha={INTERP_ALPHA}).")
    print(f"[INFO] PAN CENTER: {PAN_CENTER} (Right Biased Center) | TILT CENTER: {TILT_CENTER} (Stage Focused)")
    print(f"[INFO] TILT AMP: Scene 2={AMP_TILT_MED} / Scene 3={AMP_TILT_HIGH} (Reduced vertical sweep)")

    try:
        while True:
            raw = proc.stdout.read(frame_bytes)
            if not raw or len(raw) < frame_bytes:
                break
            
            time.sleep(0.001)
            block = np.frombuffer(raw, dtype=np.float32)
            analysis_buffer = np.concatenate((analysis_buffer, block))

            while analysis_buffer.size >= chunk_samples:
                
                # Timing Correction 
                time_position = (len(results) * hop_samples) / sample_rate
                actual_elapsed_time = time.time() - start_time
                sleep_needed = time_position - actual_elapsed_time
                if sleep_needed > 0.005:
                    time.sleep(sleep_needed)


                window = analysis_buffer[:chunk_samples]

                # Feature Analysis
                mode, key = detect_mode_key(window, sample_rate)
                tempo = detect_tempo(window, sample_rate)
                loudness = detect_loudness(window, sample_rate)
                
                feature_output, hue_speed = process_audio_features(
                    loudness=loudness, mode=mode, key=key, tempo=tempo
                )

                # 1. Calculate Fixture 1 (Master) Color/Strobe 
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

                # 2a. Update Fixture 2 (Slave) Timed Color Cycle
                if time_position - last_color_change_time >= COLOR_CHANGE_INTERVAL:
                    
                    new_color = random.choice(INDEPENDENT_PALETTE)
                    while new_color == current_slave_color and len(INDEPENDENT_PALETTE) > 1:
                        new_color = random.choice(INDEPENDENT_PALETTE)
                    
                    current_slave_color = new_color
                    last_color_change_time = time_position

                    # Update Fixture 2 RGB (W remains 0)
                    R2, G2, B2 = current_slave_color
                    
                    # Apply to DMX channels 10, 11, 12 (Color channels)
                    dmx.set_channel_internal(CH_RED_2, R2)
                    dmx.set_channel_internal(CH_GREEN_2, G2)
                    dmx.set_channel_internal(CH_BLUE_2, B2)
                    dmx.set_channel_internal(CH_WHITE_2, W2)
                    
                # 2b. Calculate Fixture 2 TARGET Movement (Pan/Tilt Scenes) 
                
                # Default to Scene 0 (Stationary/Center, though interpolation handles the transition)
                target_pan = float(PAN_CENTER)
                target_tilt = float(TILT_CENTER)
                movement_status = "SCENE 0: STATIONARY"

                if loudness >= LOUDNESS_MED_THRESHOLD: 
                    # SCENE 3: High Loudness (>= 80dB) - Fast Rotation
                    pan_amplitude = AMP_PAN_HIGH
                    tilt_amplitude = AMP_TILT_HIGH # Uses REDUCED tilt amplitude
                    frequency = FREQ_HIGH
                    
                    # Sine/Cosine for coordinated circular/figure-eight movement
                    target_pan = PAN_CENTER + pan_amplitude * np.sin(2 * np.pi * frequency * time_position)
                    target_tilt = TILT_CENTER + tilt_amplitude * np.cos(2 * np.pi * frequency * time_position)
                    
                    movement_status = f"SCENE 3: FAST ROTATION (Pan Amp:{pan_amplitude}, Tilt Amp:{tilt_amplitude})"

                elif loudness >= LOUDNESS_LOW_THRESHOLD:
                    # SCENE 2: Medium Loudness (50-80dB) - Medium Rotation
                    pan_amplitude = AMP_PAN_MED
                    tilt_amplitude = AMP_TILT_MED # Uses REDUCED tilt amplitude
                    frequency = FREQ_MED
                    
                    # Sine/Cosine for coordinated circular/figure-eight movement
                    target_pan = PAN_CENTER + pan_amplitude * np.sin(2 * np.pi * frequency * time_position)
                    target_tilt = TILT_CENTER + tilt_amplitude * np.cos(2 * np.pi * frequency * time_position)
                    
                    movement_status = f"SCENE 2: MEDIUM ROTATION (Pan Amp:{pan_amplitude}, Tilt Amp:{tilt_amplitude})"

                else: 
                    # SCENE 1: Low Loudness (< 50dB) - Slow Up Drift (Tilt Only)
                    target_pan = MOVEMENT_FIXED_PAN
                    target_tilt = TILT_CENTER + DRIFT_AMP * np.sin(2 * np.pi * DRIFT_SPEED_FREQ * time_position)
                    
                    movement_status = f"SCENE 1: SLOW TILT DRIFT (Freq:{DRIFT_SPEED_FREQ}Hz)"

                # 2c. SMOOTHING IMPLEMENTATION
                # Blend the current value towards the calculated target value (Linear Interpolation)
                current_pan = current_pan * (1 - INTERP_ALPHA) + target_pan * INTERP_ALPHA
                current_tilt = current_tilt * (1 - INTERP_ALPHA) + target_tilt * INTERP_ALPHA

                # Clip the smoothed float values to the DMX integer range (0-255)
                final_pan_dmx = np.clip(current_pan, 0, 255).astype(int)
                final_tilt_dmx = np.clip(current_tilt, 0, 255).astype(int)
                
                # Apply Pan and Tilt updates
                dmx.set_channel_internal(CH_PAN_2, final_pan_dmx) 
                dmx.set_channel_internal(CH_TILT_2, final_tilt_dmx) 
                
                # 3. Update Fixture 1 (Master) Channel Data (Ch 1-9)
                dmx.set_channel_internal(CH_RED_1, int(r))
                dmx.set_channel_internal(CH_GREEN_1, int(g))
                dmx.set_channel_internal(CH_BLUE_1, int(b))
                dmx.set_channel_internal(CH_WHITE_1, int(w))
                dmx.set_channel_internal(CH_DIMMER_1, dimmer_value)
                dmx.set_channel_internal(CH_STROBE_1, strobe_channel_value)
                speed_value = np.clip(np.interp(hue_speed, [0, 1], [0, 239]), 0, 239).astype(int)
                dmx.set_channel_internal(CH_SOUND_1, speed_value)

                # 4. Send the full DMX frame (Updates both fixtures)
                dmx.send_frame()

                # 5. Logging and Cleanup
                rgbw_master = (int(r), int(g), int(b), int(w))
                rgbw_slave = (R2, G2, B2, W2)
                
                
                if log_strobe:
                    print(f"[{time_position:6.2f}s] L:{loudness:5.2f}dB (+{loudness - previous_loudness:.2f}dB JUMP!) | T:{tempo:3.0f}bpm | F1->STROBE | F2->{movement_status} (P:{final_pan_dmx}, T:{final_tilt_dmx})")
                else:
                    print(f"[{time_position:6.2f}s] L:{loudness:5.2f}dB | T:{tempo:3.0f}bpm | Feature:{str(feature_output):12s} | F1->RGB{rgbw_master[:3]} | F2->{movement_status} (P:{final_pan_dmx}, T:{final_tilt_dmx})")
                
                previous_loudness = loudness
                
                results.append({
                    "time_position": time_position,
                    "features": {"mode": mode, "key": key, "tempo": float(tempo), "loudness": float(loudness)},
                    "lighting": {
                        "feature_output": str(feature_output), 
                        "master_rgbw": rgbw_master, 
                        "slave_rgbw": rgbw_slave, 
                        "dimmer_master": dimmer_value,
                        "slave_pan": final_pan_dmx,
                        "slave_tilt": final_tilt_dmx,
                        "movement_status": movement_status
                    }
                })

                analysis_buffer = analysis_buffer[hop_samples:]

        proc.stdout.close()
        proc.wait()

        # ... (JSON Saving logic is unchanged)
        if save_json and results:
            out_dir = Path(__file__).parent / "outputs"
            out_dir.mkdir(parents=True, exist_ok=True)
            out_file = out_dir / f"lighting_data_{Path(mp3_file_path).stem}_{genre}_realtime.json"
            
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
