import os
from pathlib import Path
import time
import librosa
import numpy as np
import threading
import queue
import serial 

from Buffer_Manager_Week7 import AudioBuffer
# Feature Modules (must be present in your directory)
from Mode_Extraction_Week7 import detect_mode_key
from Tempo_detection_week7 import detect_tempo 
from Loudness_detection_week7 import detect_loudness
from Rhythm_Detection_Week7 import extract_rhythm 
from Harmony_detection_Week7 import extract_harmony
from KNN_Week7 import preprocess_features, predict_mood
from mood_color_map import map_mood_to_genre_color, get_energy_level 

# === CONSTANTS ===
SR = 44100
WINDOW_SEC = 5.0
HOP_SEC = 2.5
WINDOW_SIZE = int(WINDOW_SEC * SR)
HOP_SIZE = int(HOP_SEC * SR)

# Loudness thresholds (Used for mode and brightness scaling)
LOUDNESS_HIGH_THRESHOLD = -25.0   
LOUDNESS_LOW_THRESHOLD = -45.0    

# CRITICAL NEW CONSTANTS for Change Detection (Blinding)
# Loudness: Absolute dB increase to trigger a change (e.g., jump of 5 dB)
LOUDNESS_JUMP_THRESHOLD = 5.0  # dB
# Tempo: Absolute BPM increase to trigger a change (e.g., jump of 15 BPM)
TEMPO_JUMP_THRESHOLD = 15.0 # BPM 

# DMX Channel Constants
CH_PAN    = 1
CH_TILT   = 2
CH_STROBE = 3
CH_RED    = 4
CH_GREEN  = 5
CH_BLUE   = 6
CH_WHITE  = 7
CH_DIMMER = 8
CH_SOUND  = 9

# Strobe channel value helpers
VAL_LED_OFF     = 0
VAL_STROBE_FLASH = 131 # Use a single value for a sharp flash
VAL_LED_START   = 255 # constant on (non-strobe state)

class SimpleDMX:
    def __init__(self, port: str):
        self.port = port
        self.num_channels = 9
        self.data = [0] * self.num_channels
        self.running = False
        self.flash_on = False # Use flash_on to signal a momentary event
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
            self.set_channel_internal(CH_PAN, 0)
            self.set_channel_internal(CH_TILT, 0)
            self.set_channel_internal(CH_STROBE, VAL_LED_START) 
            self.set_channel_internal(CH_DIMMER, 255)           
            self.set_channel_internal(CH_SOUND, 0)              

        except serial.SerialException as e:
            print(f"Error: Could not open serial port {self.port}.")
            print(e)
            self.ser = None

    def set_channel_internal(self, ch: int, value: int):
        if 1 <= ch <= self.num_channels:
            self.data[ch - 1] = max(0, min(255, value))

    def set_channels_from_tuple(self, color_tuple):
        if self.ser and len(color_tuple) >= 3:
            r, g, b = color_tuple[:3]
            w = color_tuple[3] if len(color_tuple) > 3 else 0
            self.set_channel_internal(CH_RED, r)
            self.set_channel_internal(CH_GREEN, g)
            self.set_channel_internal(CH_BLUE, b)
            self.set_channel_internal(CH_WHITE, w)
        elif not self.ser:
            pass

    # CRITICAL CHANGE: Blink based on 'blink_trigger', use loudness for dimming only
    def update_lighting(self, color_rgbw, loudness: float, blink_trigger: bool):
        if not self.ser:
            return

        self.set_channels_from_tuple(color_rgbw)

        # 1. Handle Strobe/Blink
        if blink_trigger:
            self.flash_on = True
            # Set strobe to flash mode for one frame
            self.set_channel_internal(CH_STROBE, VAL_STROBE_FLASH)
        else:
            # Revert to constant on (or a slower tempo strobe if desired, but constant on is safer)
            self.flash_on = False
            self.set_channel_internal(CH_STROBE, VAL_LED_START) 

        # 2. Handle Dimmer/Brightness based on continuous Loudness
        if loudness <= LOUDNESS_LOW_THRESHOLD:
            dimmer_value = 50 
        elif loudness >= LOUDNESS_HIGH_THRESHOLD:
            dimmer_value = 255
        else:
            # Scale brightness in the mid-range
            mid_range = LOUDNESS_HIGH_THRESHOLD - LOUDNESS_LOW_THRESHOLD
            loudness_scale = (loudness - LOUDNESS_LOW_THRESHOLD) / mid_range
            dimmer_value = int(50 + loudness_scale * (255 - 50))
            
        self.set_channel_internal(CH_DIMMER, dimmer_value)


    def send_frame(self):
        if not self.ser:
            return
        try:
            # DMX break and start code
            self.ser.baudrate = 57600
            self.ser.write(b'\x00')
            self.ser.flush()
            time.sleep(0.001)
            self.ser.baudrate = 250000

            # Send frame
            frame = bytes([0]) + bytes(self.data)
            self.ser.write(frame)
            self.ser.flush()
            
            # CRITICAL: If a flash was sent, revert the channel immediately 
            # so the next frame will be constant-on, creating a momentary flash.
            if self.flash_on:
                self.set_channel_internal(CH_STROBE, VAL_LED_START) 
                self.flash_on = False
                            
        except serial.SerialException as e:
            print(f"Error sending DMX frame: {e}")
            self.close()

    def broadcast_loop(self):
        while self.running:
            self.send_frame()
            time.sleep(0.03) 
                
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
    loudness_range = LOUDNESS_HIGH_THRESHOLD - LOUDNESS_LOW_THRESHOLD
    if loudness_range <= 0: return 0.5 
    scale = (loudness - LOUDNESS_LOW_THRESHOLD) / loudness_range
    return float(max(0.0, min(1.0, scale)))


# === USER INPUT ===
def get_user_inputs():
    print("=== Music-to-Light System ===")
    print("\nAvailable genres:")
    genres = [
        "classical", "rock", "blues", "hip hop and rap", "soul", "indie",
        "country", "gospel", "jazz", "folk", "electronics and dance",
        "latin", "metal", "pop", "reggae"
    ]
    for i, genre in enumerate(genres, 1):
        print(f"{i}. {genre}")

    while True:
        try:
            choice = int(input(f"\nSelect genre (1-{len(genres)}): "))
            if 1 <= choice <= len(genres):
                selected_genre = genres[choice - 1]
                break
            else:
                print("Invalid choice. Please try again.")
        except ValueError:
            print("Please enter a valid number.")

    while True:
        filepath = input("\nEnter the path to your audio file: ").strip().strip('"')
        if os.path.exists(filepath):
            break
        else:
            print("File not found. Please enter a valid path.")

    dmx_port = input("\nEnter DMX port (default: /dev/ttyUSB0): ").strip() or "/dev/ttyUSB0"

    return selected_genre, filepath, dmx_port


# === FEATURE + MOOD PROCESSING ===
def process_audio_chunk(chunk, buffer, genre):
    """
    Process one audio chunk and return mood, color, loudness, tempo, 
    and descriptive energy.
    """
    buffer.update(chunk)
    windowed_audio = buffer.get_window()

    # Feature extraction
    mode_key = detect_mode_key(windowed_audio)
    tempo = detect_tempo(windowed_audio) 
    loudness = detect_loudness(windowed_audio)
    rhythm = extract_rhythm(windowed_audio)
    harmony = extract_harmony(windowed_audio)
    
    rhythm_strength = rhythm[0] if isinstance(rhythm, (list, tuple)) and rhythm else 0.0
    
    if os.environ.get('DEBUG_FEATURES') == '1':
        print(f"  [DEBUG_FEAT] Mode={mode_key}, Tempo={tempo:.1f}, Loudness={loudness:.2f}, Rhythm={rhythm_strength:.2f}")

    # Combine features
    features_processed = preprocess_features(mode_key,tempo,loudness,rhythm_strength,harmony)
    
    try:
        mood = predict_mood(features_processed)
    except Exception:
        mood = "Calmness" 
        
    rgb_color = map_mood_to_genre_color(mood, genre) 
    mood_color = rgb_color + (0,) # RGBW

    descriptive_energy = get_energy_level(loudness) 

    return mood, mood_color, loudness, tempo, descriptive_energy


# === LIGHTING CONTROLLER THREAD ===
def lighting_controller_thread(dmx: SimpleDMX, mood_queue, stop_event):
    """Thread controlling DMX lights by pulling the latest data from the queue."""
    try:
        if not dmx.ser:
            return

        dmx.start_broadcast()
        print("\nStarting DMX broadcast loop and change-reactive controller...")

        while not stop_event.is_set():
            try:
                if not mood_queue.empty():
                    # Keep only the latest item
                    while mood_queue.qsize() > 1:
                        mood_queue.get_nowait()
                        
                    # CRITICAL: Receive blink_trigger
                    mood, color, loudness, blink_trigger = mood_queue.get_nowait()
                    
                    loudness = float(loudness)

                    if blink_trigger:
                        mode_desc = "JUMP-FLASH TRIGGERED"
                    elif loudness >= LOUDNESS_HIGH_THRESHOLD:
                         mode_desc = "High-Loudness (Bright)"
                    elif loudness <= LOUDNESS_LOW_THRESHOLD:
                        mode_desc = "Low-Loudness (Dim)"
                    else:
                        mode_desc = "Mid-Loudness (Scaling Dimmer)"

                    print(f"  [DMX Update] Mood: {mood:12s} | Loudness: {loudness:6.2f}dB | Mode: {mode_desc}")

                    # CRITICAL: Pass blink_trigger and loudness to the DMX controller
                    dmx.update_lighting(color, loudness, blink_trigger)

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
    print(f"\nProcessing {filepath}...")
    print(f"Genre: {genre}")

    y, sr = librosa.load(filepath, sr=SR, mono=True)
    if len(y) == 0:
        print("ERROR: Audio file is empty or invalid.")
        return []

    print(f"Loaded audio file. Duration: {len(y) / sr:.2f} seconds")

    buffer = AudioBuffer(WINDOW_SIZE)
    chunk_moods = []
    # Queue structure: mood, color, loudness, blink_trigger
    mood_queue = queue.Queue(maxsize=1) 
    stop_event = threading.Event()
    dmx = SimpleDMX(port=dmx_port)

    # State variables for change detection
    prev_loudness = None
    prev_tempo = None

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
                mood, mood_color, loudness, tempo, descriptive_energy = process_audio_chunk(chunk, buffer, genre)
                timestamp = pos / sr
                
                # --- CRITICAL BLINK LOGIC FORMULA ---
                blink_trigger = False
                if prev_loudness is not None and prev_tempo is not None:
                    # Calculate positive change (jump up)
                    delta_loudness = loudness - prev_loudness
                    delta_tempo = tempo - prev_tempo
                    
                    # The flash triggers only if both a significant Loudness INCREASE
                    # AND a significant Tempo INCREASE occurred.
                    if (delta_loudness >= LOUDNESS_JUMP_THRESHOLD and 
                        delta_tempo >= TEMPO_JUMP_THRESHOLD):
                        blink_trigger = True
                # -----------------------------------
                
                # Update state for the next chunk
                prev_loudness = loudness
                prev_tempo = tempo
                
                chunk_moods.append((timestamp, mood, mood_color, loudness, descriptive_energy))

                if mood_queue.full():
                    mood_queue.get_nowait()
                
                # CRITICAL: Queue the required data including blink_trigger
                mood_queue.put_nowait((mood, mood_color, loudness, blink_trigger)) 

                # Log output
                jump_status = "JUMP!" if blink_trigger else "Steady"
                print(f"[{timestamp:6.2f}s] Mood: {mood:12s} | Loudness: {loudness:6.2f}dB | Tempo: {tempo:5.1f} | Change: {jump_status}")

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
        print(f"\n*** JUMP TRIGGER FORMULA ***")
        print(f"Blink only if:")
        print(f"  Loudness increases by >= {LOUDNESS_JUMP_THRESHOLD} dB")
        print(f"  AND Tempo increases by >= {TEMPO_JUMP_THRESHOLD} BPM")
        
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
