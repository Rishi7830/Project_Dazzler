"""
Realtime Live Audio (Mixer/USB Input) → Feature Analysis + DMX output.
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
import threading # New import for concurrent audio playback (though now we're just analyzing)

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

# --- UI INTEGRATION AND SETUP FUNCTIONS ---

# NOTE: The UI function will need to be updated to capture the mixer device ID instead of the file path.
# Assuming you update DazzlerDashboard to include an Audio Device dropdown/input.
# For simplicity here, I'm adapting the existing file input field to capture the device ID/name.

def get_user_inputs_from_ui():
    """Launches the UI and waits for user input via the Start Dazzling! button.
    The 'song name' field is now used for the 'Mixer Device Name/ID'.
    """
    root = tk.Tk()
    
    # Initialize the DazzlerDashboard UI
    app = DazzlerDashboard(root)
    # NOTE: You will need to modify DazzlerDashboard to list available audio devices
    # and rename song_name_var to something like audio_device_var.
    
    # Use a custom flag to signal when the Master Submit is pressed
    app.submission_successful = False
    
    def master_submit_and_close():
        """Modified submit action to get data and close the UI."""
        app.master_submit() # Run the standard submit logic (for validation/output)
        
        # Check if the submission was successful (i.e., not incomplete)
        # The file existence check is now removed for live input
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
        # **UPDATED**: This is now the mixer/device ID instead of the file path
        mixer_device_id = app.song_name_var.get().strip().strip('"') 
        dmx_port = app.com_port_var.get().strip()
        
        # Destroy the root window after we have the data
        root.destroy()
        
        return selected_genre, mixer_device_id, dmx_port
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

def _suggest_default_mixer_device() -> str:
    """Suggests a default mixer device string based on the operating system."""
    sysname = platform.system().lower()
    if sysname.startswith("win"):
        # Windows typically uses device names or indices (e.g., 'Microphone (USB Audio Device)')
        # You'll need to figure out the exact name/index for your mixer.
        return os.environ.get("DAZZLER_MIXER_DEVICE", "default")
    if sysname == "darwin":
        # macOS uses device names or 'default'
        return os.environ.get("DAZZLER_MIXER_DEVICE", "default")
    # Linux (ALSA/JACK)
    return os.environ.get("DAZZLER_MIXER_DEVICE", "hw:CARD=USBDevice,DEV=0")


class _NoopDMX:
    def start_broadcast(self): print("[DMX] Broadcast disabled (no hardware)")
    def stop_broadcast(self): pass
    def close(self): pass
    def update_lighting(self, rgbw_tuple, hue_speed):
        print(f"[DMX] (noop) R{rgbw_tuple[0]} G{rgbw_tuple[1]} B{rgbw_tuple[2]} W{rgbw_tuple[3]} speed={hue_speed:.2f}")

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

# --- REAL-TIME STREAMING AND ANALYSIS (LIVE INPUT) ---

def stream_audio_realtime(
    device_id: str,
    dmx,
    genre: str,
    sample_rate: int = 44100,
    channels: int = 2, # Changed to 2 channels for stereo mixer input
    audio_block: int = 1024,
    chunk_seconds: float = 0.25,
    hop_ratio: float = 0.5,
    save_json: bool = True,
):
    """
    Stream-capture live audio from a USB mixer device, analyze features per window,
    and update DMX lighting, strictly adhering to real-time.
    """
    
    # --- FFmpeg Command for Live Capture ---
    # The command is changed to read from a device instead of a file.
    # The format ('f') and audio device input type ('i') depend on OS.
    # Note: On Windows, use -f dshow or -f wasapi and specific device names.
    # On macOS, use -f avfoundation.
    
    sysname = platform.system().lower()
    if sysname.startswith("win"):
        input_format = "dshow" 
        # Device ID for dshow is usually "audio=<device name>" or just "<device name>"
        # Example: "audio=Microphone (USB Audio Device)"
        input_device = f"audio={device_id}" 
    elif sysname == "darwin":
        input_format = "avfoundation" 
        # Device ID is typically "<input_device_index>:<output_device_index>"
        # e.g., "0:0" for default input/output, or the device name itself
        input_device = f":{device_id}" # Assuming input is at index 'device_id' with no output
    else: # Linux (assuming ALSA)
        input_format = "alsa" 
        # Device ID is typically the ALSA device string e.g. "hw:0" or "plughw:CARD=Device,DEV=0"
        input_device = device_id
        
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", 
        # New input source parameters
        "-f", input_format, 
        "-i", input_device,
        # Output pipe parameters (same as before)
        "-f", "f32le", "-ac", str(channels), "-ar", str(sample_rate), "pipe:1",
    ]

    print(f"\n[FFMPEG] Capture command: {' '.join(cmd)}")
    print("[NOTE] If this fails, you may need to adjust the format (-f) or device ID (-i) for your OS.")

    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    except FileNotFoundError:
        print("[ERR] ffmpeg not found in PATH; install ffmpeg and retry")
        return
    except Exception as e:
        print(f"[ERR] Failed to start ffmpeg process: {e}")
        return

    # 3-2-1 countdown - now it's just a warning before DMX lights up
    countdown_colors = [(255, 0, 0, 0), (255, 128, 0, 0), (255, 255, 0, 0)]
    for i, color in enumerate(reversed(countdown_colors), start=1):
        dmx.update_lighting(color, hue_speed=0)
        print(f"Countdown: {4 - i}")
        time.sleep(1)
        
    # NOTE: No more play_audio since we are analyzing a live stream!
    # If you need to monitor the audio, use a separate tool or library like simpleaudio/pyaudio.
    
    bytes_per_sample = 4 # f32le is 4 bytes
    frame_bytes = audio_block * channels * bytes_per_sample
    chunk_samples = int(chunk_seconds * sample_rate)
    hop_samples = max(1, int(chunk_samples * hop_ratio))
    # analysis_buffer will now only hold the data for the current analysis window
    analysis_buffer = np.empty(0, dtype=np.float32) 
    results = []
    
    start_time = time.time() # Capture the exact moment the stream begins
    strobe_toggle = False    # Non-blocking strobe toggle

    print(f"[RUN] Streaming Live Audio from '{device_id}' ({genre.title()}) - chunk={chunk_seconds}s, hop={hop_ratio}")

    try:
        # The main analysis loop logic remains the same for real-time processing
        while True:
            # Read a block of audio from the ffmpeg pipe
            raw = proc.stdout.read(frame_bytes)
            if not raw or len(raw) < frame_bytes:
                # In a live stream, this usually means the process was terminated
                print("[WARN] FFMPEG stream ended unexpectedly.")
                break
            
            # This small sleep is to prevent a busy-wait loop from taking all CPU
            # if ffmpeg is sending data faster than we can process it, but usually the pipe buffers handle this.
            time.sleep(0.001) 
            
            block = np.frombuffer(raw, dtype=np.float32)
            analysis_buffer = np.concatenate((analysis_buffer, block))

            # The processing loop: run analysis whenever enough data is in the buffer
            while analysis_buffer.size >= chunk_samples:
                
                # --- Real-Time Sync Logic (Critical for live input) ---
                time_position = (len(results) * hop_samples) / sample_rate
                actual_elapsed_time = time.time() - start_time
                sleep_needed = time_position - actual_elapsed_time
                if sleep_needed > 0.005:
                    # Sleep to keep the analysis rate strictly synchronized to the real-time clock
                    time.sleep(sleep_needed)

                window = analysis_buffer[:chunk_samples]
                
                # --- Feature Analysis ---
                # NOTE: For stereo input (channels=2), detect_mode_key, detect_tempo, and 
                # detect_loudness must handle the multi-channel numpy array (e.g., average/mix down to mono).
                # Assuming your functions are already robust to this.
                window_mono = window.reshape(-1, channels).mean(axis=1) # Simple mix to mono for analysis
                
                mode, key = detect_mode_key(window_mono, sample_rate)
                tempo = detect_tempo(window_mono, sample_rate)
                loudness = detect_loudness(window_mono, sample_rate) # dB is an instantaneous measure here
                feature_output, hue_speed = process_audio_features(
                    loudness=loudness, mode=mode, key=key, tempo=tempo
                )

                # --- DMX Output Logic (Same as before) ---
                if loudness > 80:
                    # Non-blocking white strobe on high loudness
                    strobe_toggle = not strobe_toggle
                    # Set R,G,B to 0 for a pure White (W) strobe
                    rgbw = (0, 0, 0, 255) if strobe_toggle else (0, 0, 0, 0)
                    dmx.update_lighting(rgbw, hue_speed)
                else:
                    mapped_rgb = map_features_to_genre_color(loudness=loudness, tempo=tempo, genre=genre)
                    r, g, b = mapped_rgb
                    # Set W (White) to 0, use mapped RGB
                    rgbw = (int(r), int(g), int(b), 0) 
                    dmx.update_lighting(rgbw, hue_speed)

                print(f"[{time_position:6.2f}s] L:{loudness:5.2f}dB | T:{tempo:3.0f}bpm | Feature:{str(feature_output):12s} -> RGBW{rgbw}")

                # --- Data Recording ---
                results.append({
                    "time_position": time_position,
                    "features": {"mode": mode, "key": key, "tempo": float(tempo), "loudness": float(loudness)},
                    "lighting": {"feature_output": str(feature_output), "mapped_rgbw": rgbw, "hue_speed": float(hue_speed)}
                })

                # Move the buffer for the next hop
                analysis_buffer = analysis_buffer[hop_samples:]

    except KeyboardInterrupt:
        print("\n[STOP] Interrupted by user")
    except Exception as e:
        print(f"[ERR] Runtime Exception: {e}")
        proc.kill()
        traceback.print_exc()
    finally:
        # Clean up ffmpeg subprocess
        if 'proc' in locals() and proc.poll() is None:
            proc.terminate()
            proc.wait(timeout=1)
        
        # Save results (optional for live stream, but good for debugging/analysis)
        if save_json and results:
            out_dir = Path(__file__).parent / "outputs"
            out_dir.mkdir(parents=True, exist_ok=True)
            out_file = out_dir / f"lighting_data_LIVE_MIXER_{genre}_realtime.json"
            
            def convert_to_float(obj):
                if isinstance(obj, np.floating):
                    return float(obj)
                return obj
                
            with open(out_file, "w") as f:
                json.dump(results, f, indent=2, default=convert_to_float)
            print(f"\n[OK] Saved {len(results)} analysis windows to {out_file}")


if __name__ == "__main__":
    
    # 1. Get inputs from the new UI function (now asking for DEVICE ID)
    selected_genre, mixer_device_id, dmx_port = get_user_inputs_from_ui()
    
    if not mixer_device_id:
        mixer_device_id = _suggest_default_mixer_device() # Fallback for no-UI environments
    
    if not all([selected_genre, mixer_device_id, dmx_port]):
        print("\n[END] Operation cancelled or incomplete data submitted.")
    else:
        print("\n--- Configuration Summary ---")
        print(f"Genre: {selected_genre.title()}")
        print(f"Audio Device: {mixer_device_id}")
        print(f"DMX Port: {dmx_port}")
        print(f"Update Rate: {0.25} seconds (Responsive)")
        print("-----------------------------\n")

        dmx = init_dmx_controller(port=dmx_port, num_channels=18)
        
        try:
            print("Starting the live audio analysis and lighting show...")
            # **UPDATED FUNCTION CALL**
            stream_audio_realtime( 
                device_id=mixer_device_id,
                dmx=dmx,
                genre=selected_genre,
                chunk_seconds=0.25,
                hop_ratio=0.5,
                channels=2, # Assuming stereo mixer input
            )
        finally:
            dmx.stop_broadcast()
            dmx.close()
            print("\n[END] DMX broadcast stopped and port closed.")
