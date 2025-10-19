import os
from pathlib import Path
import time
import librosa
import numpy as np
import threading
import queue
import serial 

from Buffer_Manager_Week7 import AudioBuffer
# Import all feature modules
from Mode_Extraction_Week7 import detect_mode_key
from Tempo_detection_week7 import detect_tempo
from Loudness_detection_Week7 import detect_loudness
from Rhythm_Detection_Week7 import extract_rhythm # CRITICAL FOR BEAT DETECTION
from Harmony_detection_Week7 import extract_harmony
from KNN_Week7 import preprocess_features, predict_mood
from mood_color_map import map_mood_to_genre_color, get_energy_level 

# === CONSTANTS ===
SR = 44100
WINDOW_SEC = 5.0
HOP_SEC = 2.5
WINDOW_SIZE = int(WINDOW_SEC * SR)
HOP_SIZE = int(HOP_SEC * SR)

# Loudness thresholds (Adjusted for Classical Music)
LOUDNESS_HIGH_THRESHOLD = -25.0   # dB: Max average loudness for non-high energy segment
LOUDNESS_LOW_THRESHOLD = -45.0    # dB: Min average loudness for non-low energy segment

# DMX Strobe/Beat Configuration
# CRITICAL: This threshold now applies to the rhythm feature (e.g., onset count or strength)
RHYTHM_BEAT_THRESHOLD = 0.5 
# This should match the output range of your extract_rhythm function (if it returns a float) 
# OR, if extract_rhythm returns a list/tuple, you must adjust process_audio_chunk to interpret it.

# DMX constants remain the same
CH_STROBE = 3
VAL_LED_START   = 255 # constant on

class SimpleDMX:
    def __init__(self, port: str, strobe_interval: float = 0.1):
        self.port = port
        self.num_channels = 9
        self.data = [0] * self.num_channels
        self.running = False
        self.strobe_on = False
        self.strobe_interval = float(strobe_interval) 
        self.color_to_strobe = (0, 0, 0, 0)
        self.thread = None
        self.ser = None

        try:
            self.ser = serial.Serial(
                port,
                baudrate=250000,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_TWO,
            )
            print(f"Serial port {self.port} opened successfully.")
            
            # Initialization
            self.set_channel_internal(1, 0)
            self.set_channel_internal(2, 0)
            self.set_channel_internal(CH_STROBE, VAL_LED_START) 
            self.set_channel_internal(8, 255)           
            self.set_channel_internal(9, 0)              

        except serial.SerialException as e:
            print(f"Error: Could not open serial port {self.port}.")
            print(e)
            self.ser = None

    # ... (set_channel_internal, set_channels_from_tuple, clear_color_channels remain the same) ...
    def set_channel_internal(self, ch: int, value: int):
        if 1 <= ch <= self.num_channels:
            self.data[ch - 1] = max(0, min(255, value))

    def set_channels_from_tuple(self, color_tuple):
        if self.ser and len(color_tuple) >= 3:
            r, g, b = color_tuple[:3]
            w = color_tuple[3] if len(color_tuple) > 3 else 0

            self.set_channel_internal(4, r)
            self.set_channel_internal(5, g)
            self.set_channel_internal(6, b)
            self.set_channel_internal(7, w)
        elif not self.ser:
            pass
            
    def clear_color_channels(self):
        if self.ser:
            for ch in range(4, 7 + 1):
                self.set_channel_internal(ch, 0)
            self.set_channel_internal(8, 0)
            self.set_channel_internal(CH_STROBE, 0) # VAL_LED_OFF

    # CRITICAL CHANGE: Accept beat_trigger and use it to control the strobe
    def update_lighting(self, color_rgbw, energy_level: float, beat_trigger: bool):
        if not self.ser:
            return

        hue_speed = float(energy_level)
        self.set_channels_from_tuple(color_rgbw)
        self.set_channel_internal(8, 255) # Dimmer fully on

        if beat_trigger:
            # Strobe on beat. Turn it OFF immediately after the send frame in broadcast_loop.
            # We set a fast interval, but the broadcast loop dictates the OFF state.
            self.strobe_on = True
            self.strobe_interval = 0.05 # Fast strobe flash
            self.set_channel_internal(CH_STROBE, 131) # VAL_STROBE_FAST
        else:
            # Set to constant ON (non-strobe)
            self.strobe_on = False
            self.set_channel_internal(CH_STROBE, VAL_LED_START)

    def send_frame(self):
        if not self.ser:
            return
        try:
            # DMX break (approx)
            self.ser.baudrate = 57600
            self.ser.write(b'\x00')
            self.ser.flush()
            time.sleep(0.001)
            self.ser.baudrate = 250000

            # Start code + 9 bytes
            frame = bytes([0]) + bytes(self.data)
            self.ser.write(frame)
            self.ser.flush()
            
            # If strobe was just sent (beat_trigger was True), turn it OFF immediately 
            # so the flash doesn't last for the full sleep duration.
            if self.strobe_on:
                self.set_channel_internal(CH_STROBE, VAL_LED_START)
                self.strobe_on = False # Reset the flag after sending the beat frame
                
        except serial.SerialException as e:
            print(f"Error sending DMX frame: {e}")
            self.close()

    def broadcast_loop(self):
        print("DMX broadcast thread started.")
        while self.running:
            # send_frame now handles turning the strobe off immediately after a flash.
            self.send_frame()
            sleep_time = self.strobe_interval if self.strobe_on else 0.03
            
            try:
                time.sleep(float(sleep_time)) 
            except Exception as e:
                print(f"[DMX Broadcast Error] Failed to sleep: {e}")
                self.running = False 
                break
                
        print("DMX broadcast thread stopped.")

    # ... (start_broadcast, stop_broadcast, close remain the same) ...
    def start_broadcast(self):
        if not self.ser:
            print("Cannot start broadcast: Serial port not available.")
            return
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self.broadcast_loop, daemon=True)
            self.thread.start()

    def stop_broadcast(self):
        if self.running and self.thread:
            self.running = False
            self.thread.join(timeout=3)

    def close(self):
        self.stop_broadcast()
        if self.ser and self.ser.is_open:
            self.clear_color_channels()
            self.send_frame()
            time.sleep(0.1)
            self.ser.close()
            print(f"Serial port {self.port} closed.")

# --- HELPER FUNCTION TO GENERATE NUMERIC ENERGY ---
def calculate_numeric_energy(loudness):
    """Calculates a numeric energy level (0.0 to 1.0) based on loudness and adjusted thresholds."""
    
    loudness_range = LOUDNESS_HIGH_THRESHOLD - LOUDNESS_LOW_THRESHOLD
    if loudness_range <= 0:
        return 0.5 
    
    scale = (loudness - LOUDNESS_LOW_THRESHOLD) / loudness_range
    
    return float(max(0.0, min(1.0, scale)))


# === FEATURE + MOOD PROCESSING ===
def process_audio_chunk(chunk, buffer, genre):
    """
    Process one audio chunk and return mood, color, loudness, 
    NUMERIC energy (float), DESCRIPTIVE energy (string), and BEAT TRIGGER (bool).
    """
    buffer.update(chunk)
    windowed_audio = buffer.get_window()

    # Feature extraction
    mode_key = detect_mode_key(windowed_audio)
    tempo = detect_tempo(windowed_audio)
    loudness = detect_loudness(windowed_audio)
    rhythm = extract_rhythm(windowed_audio)
    harmony = extract_harmony(windowed_audio)
    
    # --- RHYTHM BEAT TRIGGER LOGIC ---
    # ASSUMPTION: The first element of 'rhythm' is a quantifiable measure of beat strength/onset.
    # If your extract_rhythm is only returning one value (e.g., onset strength), use [0]. 
    # If it returns a list of onsets, you might need more complex logic.
    rhythm_strength = rhythm[0] if isinstance(rhythm, (list, tuple)) and rhythm else 0.0
    beat_trigger = rhythm_strength > RHYTHM_BEAT_THRESHOLD
    
    # --- DEBUGGING STEP: Check if features are changing ---
    if os.environ.get('DEBUG_FEATURES') == '1':
        print(f"  [DEBUG_FEAT] Mode={mode_key}, Tempo={tempo:.1f}, Loudness={loudness:.2f}, Rhythm={rhythm_strength:.2f}, Beat={beat_trigger}")

    # Combine features
    features_processed = preprocess_features(mode_key,tempo,loudness,rhythm_strength,harmony)
    
    # Predict mood, default to a neutral/safe mood if classification fails
    try:
        mood = predict_mood(features_processed)
    except Exception:
        mood = "Calmness"
        
    rgb_color = map_mood_to_genre_color(mood, genre) 
    mood_color = rgb_color + (0,) # RGBW

    numeric_energy = calculate_numeric_energy(loudness) 
    descriptive_energy = get_energy_level(loudness) 

    return mood, mood_color, loudness, numeric_energy, descriptive_energy, beat_trigger


# === LIGHTING CONTROLLER THREAD ===
def lighting_controller_thread(dmx: SimpleDMX, mood_queue, stop_event):
    """Thread controlling DMX lights by pulling the latest data from the queue."""
    try:
        if not dmx.ser:
            print("DMX not initialized. Lighting thread exiting early.")
            return

        dmx.start_broadcast()
        print("\nStarting DMX broadcast loop and adaptive lighting controller...")

        while not stop_event.is_set():
            try:
                if not mood_queue.empty():
                    while mood_queue.qsize() > 1:
                        mood_queue.get_nowait()
                        
                    # CRITICAL: Receive the new beat_trigger flag
                    mood, color, loudness, energy, beat_trigger = mood_queue.get_nowait()
                    
                    loudness = float(loudness)
                    energy = float(energy)

                    # Determine the mode description for logging based on beat and loudness
                    if beat_trigger:
                        mode_desc = "Beat-Triggered Strobe"
                    elif loudness >= LOUDNESS_HIGH_THRESHOLD:
                        mode_desc = "High-Loudness Continuous"
                    elif loudness <= LOUDNESS_LOW_THRESHOLD:
                        mode_desc = "Low-Loudness Fade"
                    else:
                        mode_desc = "Mid-Loudness"

                    print(f"  [DMX Update] Mood: {mood:12s} | Loudness: {loudness:6.2f}dB | Energy: {energy:.2f} (Numeric) | Mode: {mode_desc}")

                    # CRITICAL: Pass the beat_trigger to the DMX controller
                    dmx.update_lighting(color, energy, beat_trigger)

            except queue.Empty:
                pass
            except Exception as e:
                print(f"[Lighting thread] Unhandled Error: {e}")
                import traceback
                traceback.print_exc()
                dmx.close() 
                break

            time.sleep(0.05) 

    finally:
        print("Lighting controller thread instructed to exit.")


# === MAIN AUDIO PROCESSING LOOP ===
def process_single_file(filepath, genre, dmx_port):
    """Main audio processor with real-time lighting."""
    
    # ... (File loading and initialization remains the same) ...
    y, sr = librosa.load(filepath, sr=SR, mono=True)
    if len(y) == 0:
        print("ERROR: Audio file is empty or invalid.")
        return []

    print(f"Loaded audio file. Duration: {len(y) / sr:.2f} seconds")

    buffer = AudioBuffer(WINDOW_SIZE)
    chunk_moods = []
    mood_queue = queue.Queue(maxsize=1) 
    stop_event = threading.Event()
    dmx = SimpleDMX(port=dmx_port)

    if not dmx.ser:
        print("Cannot start lighting. Continuing analysis only.")
        lighting_thread = threading.Thread(target=lambda: print("DMX not available."), daemon=True)
    else:
        lighting_thread = threading.Thread(
            target=lighting_controller_thread,
            args=(dmx, mood_queue, stop_event),
            daemon=True
        )
    lighting_thread.start()


    try:
        pos = 0
        print("\nStarting real-time analysis and lighting...")
        print("Press Ctrl+C to stop.\n")

        while pos < len(y):
            start_time = time.time()
            chunk = y[pos:pos + HOP_SIZE]
            if len(chunk) < HOP_SIZE:
                chunk = np.pad(chunk, (0, HOP_SIZE - len(chunk)), 'constant')

            try:
                # CRITICAL: Receive the new beat_trigger
                mood, mood_color, loudness, numeric_energy, descriptive_energy, beat_trigger = process_audio_chunk(chunk, buffer, genre)
                timestamp = pos / sr
                
                chunk_moods.append((timestamp, mood, mood_color, loudness, descriptive_energy))

                if mood_queue.full():
                    mood_queue.get_nowait()
                # CRITICAL: Queue the new beat_trigger
                mood_queue.put_nowait((mood, mood_color, loudness, numeric_energy, beat_trigger)) 


                print(f"[{timestamp:6.2f}s] Mood: {mood:12s} | Color: {mood_color} | Loudness: {loudness:6.2f}dB | Energy: {descriptive_energy} | Beat: {beat_trigger}")

            except Exception as e:
                print(f"Error processing chunk at {pos/sr:.2f}s: {e}")
                import traceback
                traceback.print_exc()

            pos += HOP_SIZE
            elapsed = time.time() - start_time
            sleep_time = HOP_SEC - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

    except KeyboardInterrupt:
        print("\nStopping analysis manually (Ctrl+C).")
    except Exception as e:
        print(f"Unexpected processing error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Cleanup
        stop_event.set() 
        lighting_thread.join(timeout=3)
        if 'dmx' in locals() and dmx.ser:
            dmx.close() 

        print(f"\nProcessed {len(chunk_moods)} chunks.")
        
    return chunk_moods


# === MAIN EXECUTION ===
def main():
    try:
        genre, filepath, dmx_port = get_user_inputs()

        print(f"\nConfiguration:")
        print(f"Genre: {genre}")
        print(f"Audio file: {filepath}")
        print(f"DMX port: {dmx_port}")
        print(f"Processing window: {WINDOW_SEC}s")
        print(f"Hop size: {HOP_SEC}s")
        print(f"Loudness thresholds: High > {LOUDNESS_HIGH_THRESHOLD}dB, Low < {LOUDNESS_LOW_THRESHOLD}dB")
        print(f"Rhythm Beat Trigger Threshold: > {RHYTHM_BEAT_THRESHOLD}")
        
        print("\nNOTE: To debug feature values, run with: DEBUG_FEATURES=1 python3 main_demoweek7.py")

        input("\nPress Enter to start...")

        results = process_single_file(filepath, genre, dmx_port)

        print("\n=== Analysis Complete ===")
        # ... (rest of the results printout) ...

    except Exception as e:
        print(f"Error in main execution: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
