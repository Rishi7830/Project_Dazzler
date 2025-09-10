import librosa
import numpy as np
import time
import argparse
from scipy.signal import butter, filtfilt
import pygame
# import threading # Not directly used, but asyncio.to_thread uses it
import asyncio
import pyartnet
import sys
try:
    import psutil # Optional, for setting process priority
except ImportError:
    psutil = None
    print("INFO: psutil not found, cannot set process priority. Run 'pip install psutil' if desired.")


# --- DMX / Art-Net Configuration ---
QLC_LISTENING_IP = '127.0.0.1'
ARTNET_TARGET_UNIVERSE = 0
DMX_MAX_FPS = 40

# --- DMX Flash Configuration ---
# Assumes Channel 1 = Brightness/Dimmer, 2 = Red, 3 = Green, 4 = Blue
FLASH_CHANNELS = [1, 2, 3, 4] # DMX Channels (1-based)
FLASH_BRIGHTNESS_CHANNEL_INDEX = 0 # Index within FLASH_CHANNELS for brightness
FLASH_RGB_CHANNEL_INDICES = [1, 2, 3] # Indices within FLASH_CHANNELS for R, G, B

FLASH_VALUE_ON = 255 # Max brightness/color value
FLASH_VALUE_OFF = 0
FLASH_DURATION = 0.10           # Flash duration in seconds
TEST_FLASH_DURATION = 0.25      # Slightly longer for initial test visibility

# --- Color Configuration ---
# Define the sequence of colors (RGB tuples) to cycle through
FLASH_COLORS = [
    (255, 0, 0),    # Red
    (0, 255, 0),    # Green
    (0, 0, 255),    # Blue
    (255, 255, 0),  # Yellow
    (0, 255, 255),  # Cyan
    (255, 0, 255),  # Magenta
    (255, 165, 0),  # Orange
    (128, 0, 128),  # Purple
    (255, 255, 255),# White
]
current_color_index = 0 # Global index to track the next color

# --- Global DMX Array & Channel Object ---
dmx_data = np.zeros(512, dtype=np.uint8)
dmx_channel_object = None

# --- Audio Analysis Functions ---
# --- [ Keep `create_low_pass_filter` and `analyze_bass_onsets` same as before ] ---
def create_low_pass_filter(cutoff_freq, sample_rate, order=8):
    nyquist = sample_rate / 2; normal_cutoff = cutoff_freq / nyquist
    b, a = butter(order, normal_cutoff, btype='low'); return b, a

def analyze_bass_onsets(audio_file, amplitude_threshold=0.40, cutoff_freq=200, duration=None):
    print(f"Analyzing audio file: {audio_file} (Duration limit: {duration}s)...")
    try:
        y, sr = librosa.load(audio_file, sr=None, duration=duration)
        actual_duration = librosa.get_duration(y=y, sr=sr)
        print(f"Audio loaded. Sample rate: {sr}Hz, Actual Duration Analyzed: {actual_duration:.2f}s")
        if actual_duration == 0: print("Warning: Loaded audio has zero duration."); return [], sr, 0.0
        nyquist = sr / 2; normal_cutoff = cutoff_freq / nyquist
        b, a = butter(8, normal_cutoff, btype='low'); y_bass = filtfilt(b, a, y)
        max_val = np.max(np.abs(y_bass)); y_bass_norm = y_bass / max_val if max_val > 0 else y_bass
        onset_indices = [i for i in range(1, len(y_bass_norm)) if np.abs(y_bass_norm[i]) >= amplitude_threshold and np.abs(y_bass_norm[i-1]) < amplitude_threshold]
        onset_times = [(idx / sr) for idx in onset_indices]
        print(f"Analysis complete. Found {len(onset_times)} bass onsets.")
        if len(onset_times) > 1:
            intervals = np.diff(onset_times); avg_interval = np.mean(intervals)
            bass_bpm = 60 / avg_interval if avg_interval > 0 else 0
            print(f"Estimated BPM (bass onsets): {bass_bpm:.1f}")
        return onset_times, sr, actual_duration
    except Exception as e:
        print(f"ERROR during audio analysis: {e}"); raise e


# --- DMX Control Functions (Async) ---
async def trigger_dmx_flash(duration=FLASH_DURATION):
    """Coroutine to perform a quick DMX flash with changing colors. Runs in asyncio loop."""
    global dmx_data, dmx_channel_object, current_color_index, FLASH_COLORS

    if dmx_channel_object is None: print("DEBUG ERROR: DMX channel object not initialized."); return

    # --- Get DMX channel numbers (0-based index for dmx_data) ---
    # Ensure channels are valid (1-512) and get their 0-based indices
    dmx_indices = [ch - 1 for ch in FLASH_CHANNELS if 0 <= (ch - 1) < 512]
    if len(dmx_indices) != len(FLASH_CHANNELS):
        print(f"DEBUG WARNING: Some configured flash channels {FLASH_CHANNELS} are out of DMX range (1-512).")
    if not dmx_indices:
        print("DEBUG ERROR: No valid flash channels configured."); return
    if len(FLASH_RGB_CHANNEL_INDICES) != 3:
        print("DEBUG ERROR: FLASH_RGB_CHANNEL_INDICES must have 3 values (for R, G, B)."); return
    if FLASH_BRIGHTNESS_CHANNEL_INDEX >= len(dmx_indices):
        print("DEBUG ERROR: FLASH_BRIGHTNESS_CHANNEL_INDEX is out of bounds for configured channels."); return
    for idx in FLASH_RGB_CHANNEL_INDICES:
        if idx >= len(dmx_indices):
            print(f"DEBUG ERROR: FLASH_RGB_CHANNEL_INDICES contains index {idx} out of bounds."); return


    # --- Select Color ---
    if not FLASH_COLORS:
        print("DEBUG ERROR: FLASH_COLORS list is empty!"); return
    selected_color = FLASH_COLORS[current_color_index]
    next_color_index = (current_color_index + 1) % len(FLASH_COLORS)

    # --- Prepare DMX Values ---
    brightness_dmx_index = dmx_indices[FLASH_BRIGHTNESS_CHANNEL_INDEX]
    r_dmx_index = dmx_indices[FLASH_RGB_CHANNEL_INDICES[0]]
    g_dmx_index = dmx_indices[FLASH_RGB_CHANNEL_INDICES[1]]
    b_dmx_index = dmx_indices[FLASH_RGB_CHANNEL_INDICES[2]]

    print(f"DEBUG: Flash Triggered Async! Color: {selected_color} (Idx: {current_color_index}). Channels B:{brightness_dmx_index+1}, R:{r_dmx_index+1}, G:{g_dmx_index+1}, B:{b_dmx_index+1} ON (Duration: {duration}s).")

    try:
        # --- Flash ON ---
        dmx_data[brightness_dmx_index] = FLASH_VALUE_ON # Set brightness channel
        dmx_data[r_dmx_index] = selected_color[0]      # Set Red channel
        dmx_data[g_dmx_index] = selected_color[1]      # Set Green channel
        dmx_data[b_dmx_index] = selected_color[2]      # Set Blue channel

        dmx_channel_object.set_values(dmx_data)

        # Update color index for the *next* flash *after* setting the current one
        current_color_index = next_color_index

        await asyncio.sleep(duration)

        # --- Flash OFF ---
        print(f"DEBUG: Flash OFF Async. Resetting channels B,R,G,B to {FLASH_VALUE_OFF}.")
        # Reset *all* configured channels involved in the flash
        for idx in dmx_indices:
            dmx_data[idx] = FLASH_VALUE_OFF
        # Explicitly ensure the main B,R,G,B are off (redundant if FLASH_CHANNELS only contains these 4)
        dmx_data[brightness_dmx_index] = FLASH_VALUE_OFF
        dmx_data[r_dmx_index] = FLASH_VALUE_OFF
        dmx_data[g_dmx_index] = FLASH_VALUE_OFF
        dmx_data[b_dmx_index] = FLASH_VALUE_OFF

        dmx_channel_object.set_values(dmx_data)

    except Exception as e:
        print(f"Error during DMX flash execution: {e}")


# --- Helper Function to Schedule Flash from Thread ---
def schedule_flash_from_thread(loop):
    """Safely schedules the async flash task from another thread."""
    if loop and loop.is_running():
        # Schedule the *creation* of the flash task onto the loop
        # Pass the current desired duration if needed, or let the default be used
        loop.call_soon_threadsafe(asyncio.create_task, trigger_dmx_flash(FLASH_DURATION))
    else:
        print("DEBUG WARN: Event loop not running, cannot schedule flash from thread.")


# --- Pygame Audio Player & Onset Trigger (Synchronous - To be run in thread) ---
def play_audio_sync_and_trigger(audio_file, stop_event, bass_onsets, loop):
    """Plays audio, checks onsets, and triggers DMX via the asyncio loop."""
    print("DEBUG: Audio playback & trigger thread started.")
    mixer_loaded = False
    start_time_ns = 0
    onset_index = 0

    try:
        # --- Load Audio (Mixer assumed initialized) ---
        print(f"DEBUG: Loading audio file: {audio_file}")
        if not pygame.mixer.get_init(): raise RuntimeError("Mixer not initialized")
        pygame.mixer.music.load(audio_file)
        mixer_loaded = True
        print("DEBUG: Audio loaded.")

        # --- Play and Record Start Time ---
        if stop_event.is_set(): print("DEBUG: Stop event set before playback start."); return

        print("DEBUG: Calling pygame.mixer.music.play()...")
        pygame.mixer.music.play()
        start_time_ns = time.monotonic_ns() # Record start time *immediately* after play
        print(f"DEBUG: Playback started, recorded start_time_ns: {start_time_ns}")

        # --- Main Wait and Trigger Loop ---
        while pygame.mixer.get_init() and pygame.mixer.music.get_busy() and not stop_event.is_set():
            # --- Onset Check ---
            if onset_index < len(bass_onsets):
                current_time_ns = time.monotonic_ns()
                elapsed_time = (current_time_ns - start_time_ns) / 1e9

                if elapsed_time >= bass_onsets[onset_index]:
                    print(f"!!! Onset #{onset_index + 1} detected at {elapsed_time:.3f}s (Target: {bass_onsets[onset_index]:.3f}s) -> Scheduling Flash !!!") # DEBUG
                    # Use helper to schedule the async task from this thread
                    schedule_flash_from_thread(loop)
                    onset_index += 1
            # --- End Onset Check ---

            # Limit check rate
            pygame.time.Clock().tick(120) # Check timing more frequently (e.g., 120Hz)

        # --- After Loop ---
        if not pygame.mixer.get_init(): print("DEBUG: Mixer was uninitialized during playback loop.")
        elif stop_event.is_set(): print("DEBUG: Playback interrupted by stop_event."); pygame.mixer.music.stop()
        else: print("DEBUG: Playback finished normally.")

    except pygame.error as pg_err: print(f"ERROR in audio playback thread (Pygame Error): {pg_err}")
    except Exception as e: print(f"ERROR in audio playback thread (Other Error): {e}")
    finally:
        # --- Cleanup ---
        print("DEBUG: Audio playback & trigger thread finished.")
        # Ensure stop_event is set upon any exit path from this thread
        if loop and loop.is_running() and not stop_event.is_set():
            loop.call_soon_threadsafe(stop_event.set)


# --- Main Orchestration (Async) ---
async def main(args):
    global dmx_data, dmx_channel_object, current_color_index # Add current_color_index here

    analysis_duration = None # Analyze the whole file unless specified otherwise
    # Or set a limit like: analysis_duration = 60.0
    bass_onsets, sample_rate, audio_duration = [], 0, 0.0

    print("Starting main orchestration...")
    loop = asyncio.get_running_loop()
    current_color_index = 0 # Reset color index at the start

    # --- Pre-initialize Pygame ---
    pygame_initialized = False
    print("DEBUG: Pre-initializing Pygame...")
    try:
        # Increased buffer size might help reduce playback glitches on some systems
        pygame.mixer.pre_init(frequency=44100, size=-16, channels=2, buffer=2048)
        pygame.init(); pygame.display.init(); pygame.mixer.init()
        pygame_initialized = True; print("DEBUG: Pygame pre-initialized successfully.")
    except Exception as e: print(f"FATAL: Failed to pre-initialize Pygame: {e}. Exiting."); return
    # --- End Pre-initialize ---

    artnet_node = None
    audio_thread_coro = None
    stop_event = asyncio.Event() # Used now mainly to signal thread to stop early

    try:
        # 1. Analyze Audio
        print("Running audio analysis...")
        try:
            # Analyze the *entire* audio file for onsets first
            full_onsets, sample_rate, audio_duration = await loop.run_in_executor(
                None, analyze_bass_onsets,
                args.audio_file, args.threshold, args.cutoff_freq, None # duration=None
            )
            if not full_onsets: print("No onsets found in the entire file. Exiting."); return

            # If analysis_duration is set, filter the onsets (optional)
            if analysis_duration:
                 bass_onsets = [t for t in full_onsets if t <= analysis_duration]
                 print(f"Filtered onsets to first {analysis_duration}s: {len(bass_onsets)} remain.")
                 if not bass_onsets: print("No onsets found within the analysis duration. Exiting."); return
            else:
                 bass_onsets = full_onsets # Use all detected onsets
                 print(f"Using all {len(bass_onsets)} detected onsets from the full file.")

        except Exception as e: print(f"Exiting due to error during audio analysis: {e}"); return

        # 2. Setup DMX
        print("Setting up Art-Net node...")
        artnet_node = pyartnet.ArtNetNode(QLC_LISTENING_IP, 6454, max_fps=DMX_MAX_FPS, start_refresh_task=True)
        # await asyncio.sleep(0.1) # May not be needed with start_refresh_task=True
        universe = artnet_node.add_universe(ARTNET_TARGET_UNIVERSE)
        dmx_channel_object = universe.add_channel(start=1, width=512) # Covers the whole universe

        # Ensure initial state is off
        dmx_data[:] = FLASH_VALUE_OFF
        dmx_channel_object.set_values(dmx_data)
        print("Art-Net node setup complete. Initial DMX state set to OFF.")

        # --- Quick DMX Test ---
        print("Performing initial DMX test flash...")
        await trigger_dmx_flash(duration=TEST_FLASH_DURATION) # This will use the first color
        await asyncio.sleep(0.5) # Wait after the test flash turns off
        print("DMX test flash complete.")
        # --- End DMX Test ---

        # --- Countdown ---
        print("\n=== GET READY ===")
        for i in range(3, 0, -1): print(f"{i}..."); await asyncio.sleep(1)
        print("GO!")
        # --- End Countdown ---

        # 3. Start Audio Playback & Trigger Thread
        print("Starting audio playback & trigger thread...")
        audio_thread_coro = asyncio.to_thread(
            play_audio_sync_and_trigger, args.audio_file, stop_event, bass_onsets, loop
        )

        # 4. Wait for audio thread to complete (or be interrupted)
        print("Waiting for audio playback thread to complete...")
        # We run the thread via asyncio.to_thread, so awaiting it waits for completion
        await audio_thread_coro
        print("Audio playback thread has completed.")

        print("\n=== PLAYBACK AND DMX SYNCHRONIZATION COMPLETE ===")

    except KeyboardInterrupt:
        print("\nInterrupted by user (Ctrl+C). Cleaning up...")
        stop_event.set() # Signal thread
    except Exception as e:
        print(f"\nAn error occurred in main orchestration: {e}")
        import traceback
        traceback.print_exc() # Print detailed traceback
        stop_event.set() # Signal thread
    finally:
        # --- Cleanup ---
        print("Main function cleanup started...")
        stop_event.set() # Ensure stop is signaled

        # Wait briefly for the thread to potentially acknowledge the stop signal
        await asyncio.sleep(0.2)

        # Wait for audio thread *if it was started* and hasn't finished yet
        if audio_thread_coro and not audio_thread_coro.done():
            print("Ensuring audio thread is finished...")
            try:
                # Wait for the thread task wrapper (it might already be done)
                await asyncio.wait_for(audio_thread_coro, timeout=5.0)
                print("Audio thread awaited successfully during cleanup.")
            except asyncio.TimeoutError:
                print("Warning: Timeout waiting for audio thread during cleanup.")
            except asyncio.InvalidStateError:
                print("Info: Audio thread coroutine was already awaited or finished.")
            except Exception as e_audio_await:
                print(f"Error awaiting audio thread during cleanup: {e_audio_await}")

        # Final DMX blackout
        if dmx_channel_object:
            print("Sending final blackout...")
            dmx_data[:] = FLASH_VALUE_OFF
            dmx_channel_object.set_values(dmx_data)
            await asyncio.sleep(0.1) # Small extra delay

        # Stop Art-Net Node
        if artnet_node:
            print("Stopping Art-Net node...")
            await artnet_node.stop() # Gracefully stop the node's background tasks
            print("Art-Net node stopped.")

        # --- Quit Pygame ---
        if pygame_initialized:
            print("DEBUG: Quitting Pygame from main finally block...")
            # Ensure mixer is stopped before quitting
            try:
                if pygame.mixer.get_init():
                    pygame.mixer.music.stop()
                    pygame.mixer.quit()
                pygame.display.quit() # Quit display module if initialized
                pygame.quit() # General Pygame quit
                print("DEBUG: Pygame quit.")
            except Exception as e_pg_quit:
                print(f"Warning: Error during Pygame quit: {e_pg_quit}")
        # --- End Pygame Quit ---

        print("Main function finished.")


# --- Script Entry Point ---
# --- [ Keep the __main__ block the same as the previous version ] ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Play audio and synchronize color-changing DMX flashes with bass onsets via Art-Net.')
    parser.add_argument('audio_file', type=str, help='Path to MP3/FLAC/WAV audio file')
    parser.add_argument('--threshold', type=float, default=0.40, help='Bass onset amplitude threshold (0.0-1.0)')
    parser.add_argument('--cutoff-freq', type=int, default=200, help='Bass low-pass filter cutoff frequency (Hz)')
    # parser.add_argument('--analysis-duration', type=float, default=None, help='Limit analysis and playback sync to the first N seconds (optional)') # Add if needed
    args = parser.parse_args()

    # Attempt to set higher process priority on Windows
    if psutil and sys.platform == "win32":
        try:
            p = psutil.Process()
            # Consider REALTIME_PRIORITY_CLASS for maximum priority, but use with caution
            # p.nice(psutil.REALTIME_PRIORITY_CLASS)
            p.nice(psutil.HIGH_PRIORITY_CLASS)
            print("INFO: Process priority set to High.")
        except Exception as e_prio: print(f"Warning: Could not set process priority: {e_prio}")
    elif psutil and (sys.platform == "linux" or sys.platform == "darwin"):
         try:
            p = psutil.Process()
            # Lower nice value means higher priority (-20 is highest)
            p.nice(-10) # Set a higher priority
            print("INFO: Process nice value set to -10 (higher priority).")
         except Exception as e_prio: print(f"Warning: Could not set process priority (nice): {e_prio}")


    try:
        asyncio.run(main(args))
    except RuntimeError as e:
        if "Cannot run the event loop while another loop is running" in str(e):
            print("INFO: asyncio event loop is already running (might happen in some IDEs). Trying to get existing loop.")
            # This usually won't work correctly if called from the top level script,
            # but leaving the check here for informational purposes.
            # loop = asyncio.get_event_loop()
            # if not loop.is_running():
            #    loop.run_until_complete(main(args))
        else:
            print(f"RuntimeError occurred when starting asyncio: {e}")
    except Exception as e:
        print(f"An unexpected error occurred at the top level: {e}")
        import traceback
        traceback.print_exc()
