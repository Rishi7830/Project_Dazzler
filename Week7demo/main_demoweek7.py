import os
from pathlib import Path
import time
import librosa
import numpy as np
import threading
import queue
import serial # Added for SimpleDMX

from Buffer_Manager_Week7 import AudioBuffer
from Mode_Extraction_Week7 import detect_mode_key
from Tempo_detection_week7 import detect_tempo
from Loudness_detection_Week7 import detect_loudness
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

# Loudness thresholds (tunable)
LOUDNESS_HIGH_THRESHOLD = -20   # dB, switch to high frequency/strobe above this
LOUDNESS_LOW_THRESHOLD = -40    # dB, switch to low frequency/fade below this
HIGH_ENERGY_THRESHOLD = 0.6     # Energy level threshold for high-intensity mode

# === SimpleDMX Class and Constants (from pyserial code) ===

# MH363 9-channel DMX map:
CH_PAN    = 1
CH_TILT   = 2
CH_STROBE = 3
CH_RED    = 4
CH_GREEN  = 5
CH_BLUE   = 6
CH_WHITE  = 7
CH_DIMMER = 8
CH_SOUND  = 9

# Strobe channel value helpers (Channel 3)
VAL_LED_OFF     = 0
VAL_STROBE_FAST = 131
VAL_FADE_FAST   = 181
VAL_LIGHTNING   = 244
VAL_LED_START   = 255 # constant on

class SimpleDMX:
    def __init__(self, port: str, strobe_interval: float = 0.1):
        self.port = port
        self.num_channels = 9
        self.data = [0] * self.num_channels
        self.running = False
        self.strobe_on = False
        self.strobe_interval = strobe_interval
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
            
            # Initialize to safe/active defaults for 9CH mode
            self.set_channel_internal(CH_PAN, 0)
            self.set_channel_internal(CH_TILT, 0)
            self.set_channel_internal(CH_STROBE, VAL_LED_START) # constant light
            self.set_channel_internal(CH_DIMMER, 255)           # full output
            self.set_channel_internal(CH_SOUND, 0)              # sound off

        except serial.SerialException as e:
            print(f"Error: Could not open serial port {self.port}.")
            print(e)
            self.ser = None

    def set_channel_internal(self, ch: int, value: int):
        if 1 <= ch <= self.num_channels:
            self.data[ch - 1] = max(0, min(255, value))

    def set_channels_from_tuple(self, color_tuple):
        if self.ser and len(color_tuple) >= 3: # Only need RGB, but 4 is fine too
            r, g, b = color_tuple[:3]
            w = color_tuple[3] if len(color_tuple) > 3 else 0

            self.set_channel_internal(CH_RED, r)
            self.set_channel_internal(CH_GREEN, g)
            self.set_channel_internal(CH_BLUE, b)
            self.set_channel_internal(CH_WHITE, w)
        elif not self.ser:
            print("Serial port not available. Cannot set channels from tuple.")

    def update_lighting(self, color_rgbw, energy_level: float):
        if not self.ser:
            return

        # Map energy level (0.0 to 1.0) to hue_speed for DMX class
        # Use a high hue_speed for strobe/high-frequency modes
        hue_speed = energy_level if energy_level > 0.0 else 0.0

        strobe_threshold = HIGH_ENERGY_THRESHOLD
        if hue_speed > strobe_threshold:
            self.strobe_on = True
            # Adjust strobe interval based on energy_level (faster for higher energy)
            # 0.05s max speed (20Hz), 0.5s min speed (2Hz)
            self.strobe_interval = max(0.05, 0.5 * (1.0 - energy_level)) 
            self.color_to_strobe = color_rgbw
            
            self.set_channels_from_tuple(self.color_to_strobe)
            self.set_channel_internal(CH_DIMMER, 255)
            # Use CH3 strobe band; choose fast regular strobe
            self.set_channel_internal(CH_STROBE, VAL_STROBE_FAST)
            # print(f"Set DMX: Strobe ON, Interval: {self.strobe_interval:.2f}s")
        else:
            self.strobe_on = False
            self.set_channels_from_tuple(color_rgbw)
            self.set_channel_internal(CH_DIMMER, 255)
            # Use constant on or slow fade for low energy
            self.set_channel_internal(CH_STROBE, VAL_LED_START)
            # print("Set DMX: Strobe OFF, Constant ON")

        # The send_frame is handled by the broadcast thread

    def clear_color_channels(self):
        if self.ser:
            for ch in range(CH_RED, CH_WHITE + 1):
                self.set_channel_internal(ch, 0)
            self.set_channel_internal(CH_DIMMER, 0)
            self.set_channel_internal(CH_STROBE, VAL_LED_OFF)

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
        except serial.SerialException as e:
            print(f"Error sending DMX frame: {e}")
            self.close() # Attempt to close on error

    def broadcast_loop(self):
        print("DMX broadcast thread started.")
        while self.running:
            self.send_frame()
            # If strobing, respect strobe interval, otherwise a fixed slow rate (e.g., 30Hz)
            sleep_time = self.strobe_on and self.strobe_interval or 0.03
            time.sleep(sleep_time)
        print("DMX broadcast thread stopped.")

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
            self.thread.join(timeout=2)
            if self.thread.is_alive():
                print("Warning: DMX broadcast thread did not terminate cleanly.")

    def close(self):
        self.stop_broadcast()
        if self.ser and self.ser.is_open:
            self.clear_color_channels()
            self.send_frame() # Send one final 'off' frame
            time.sleep(0.1)
            self.ser.close()
            print(f"Serial port {self.port} closed.")


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

    dmx_port = input("\nEnter DMX port (default: COM14): ").strip() or "COM14"

    return selected_genre, filepath, dmx_port


# === FEATURE + MOOD PROCESSING ===
def process_audio_chunk(chunk, buffer, genre):
    """Process one audio chunk and return mood, color, and energy."""
    buffer.update(chunk)
    windowed_audio = buffer.get_window()

    # Feature extraction
    mode_key = detect_mode_key(windowed_audio)
    tempo = detect_tempo(windowed_audio)
    loudness = detect_loudness(windowed_audio)
    rhythm = extract_rhythm(windowed_audio)
    harmony = extract_harmony(windowed_audio)

    # Combine features
    # features = [[mode_key], [tempo],[loudness], [rhythm], [harmony]] # Not strictly needed
    features_processed = preprocess_features(mode_key,tempo,loudness,rhythm[0],harmony)
    mood = predict_mood(features_processed)

    # Note: map_mood_to_genre_color should return an RGBW tuple (R, G, B, W) for SimpleDMX
    # Assuming map_mood_to_genre_color returns a tuple of (R, G, B)
    rgb_color = map_mood_to_genre_color(mood, genre) 
    mood_color = rgb_color + (0,) # Append 0 for White channel for simplicity
    
    energy_level = get_energy_level(loudness)

    return mood, mood_color, loudness, energy_level


# === LIGHTING CONTROLLER THREAD ===
def lighting_controller_thread(dmx: SimpleDMX, mood_queue, stop_event):
    """Thread controlling DMX lights by pulling from the queue."""
    try:
        if not dmx.ser:
            print("DMX not initialized. Lighting thread exiting early.")
            return

        dmx.start_broadcast()
        print("\nStarting DMX broadcast loop and adaptive lighting controller...")

        while not stop_event.is_set():
            try:
                # Get the latest mood data without blocking
                if not mood_queue.empty():
                    # Clear the queue to only process the very latest one
                    while mood_queue.qsize() > 1:
                        mood_queue.get_nowait()
                        
                    mood, color, loudness, energy = mood_queue.get_nowait()
                    
                    # Log the change based on loudness for a better trace
                    if loudness >= LOUDNESS_HIGH_THRESHOLD:
                        mode_desc = "High-Energy/Strobe"
                    elif loudness <= LOUDNESS_LOW_THRESHOLD:
                        mode_desc = "Low-Energy/Fade"
                    else:
                        mode_desc = "Mid-Energy"

                    print(f"  [DMX Update] Mood: {mood:12s} | Loudness: {loudness:6.2f}dB | Energy: {energy:.2f} | Mode: {mode_desc}")

                    # The SimpleDMX.update_lighting handles the logic based on energy_level
                    dmx.update_lighting(color, energy)

            except queue.Empty:
                pass # Queue is empty, just wait a bit
            except Exception as e:
                print(f"[Lighting thread] Error: {e}")
                dmx.close()
                break

            time.sleep(0.05) # Poll the queue every 50ms

    finally:
        # Cleanup is handled by the main thread's finally block
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
    # Queue size is small, as we only need the latest value for DMX
    mood_queue = queue.Queue(maxsize=1) 
    stop_event = threading.Event()
    dmx = SimpleDMX(port=dmx_port) # Instantiate DMX controller

    if not dmx.ser:
        print("Cannot start lighting. Continuing analysis only.")
        # Create a dummy thread that just prints to keep the flow the same
        lighting_thread = threading.Thread(target=lambda: print("DMX not available."), daemon=True)
    else:
        # Start lighting thread
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
                mood, mood_color, loudness, energy = process_audio_chunk(chunk, buffer, genre)
                timestamp = pos / sr
                chunk_moods.append((timestamp, mood, mood_color, loudness, energy))

                # Always attempt to put the latest data; it will overwrite the old one in maxsize=1 queue
                # Use put_nowait and handle full queue (for maxsize > 1) or simply put for maxsize=1
                if mood_queue.full():
                    mood_queue.get_nowait() # Remove the old item
                mood_queue.put_nowait((mood, mood_color, loudness, energy))


                print(f"[{timestamp:6.2f}s] Mood: {mood:12s} | Color: {mood_color} | Loudness: {loudness:6.2f}dB | Energy: {energy}")

            except Exception as e:
                print(f"Error processing chunk at {pos/sr:.2f}s: {e}")
                import traceback
                traceback.print_exc()

            pos += HOP_SIZE
            elapsed = time.time() - start_time
            sleep_time = HOP_SEC - elapsed
            # This sleep ensures the real-time processing rate matches the HOP_SEC
            if sleep_time > 0:
                time.sleep(sleep_time)

    except KeyboardInterrupt:
        print("\nStopping analysis manually (Ctrl+C).")
    except Exception as e:
        print(f"Unexpected processing error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Signal the lighting thread to stop
        stop_event.set() 
        # Wait for the lighting thread to join
        lighting_thread.join(timeout=3)
        # Close the DMX connection (sends final 'off' frame)
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
        print(f"High Energy Threshold (for DMX strobe): > {HIGH_ENERGY_THRESHOLD}")

        input("\nPress Enter to start...")

        results = process_single_file(filepath, genre, dmx_port)

        print("\n=== Analysis Complete ===")
        if results:
            moods = [mood for _, mood, _, _, _ in results]
            unique_moods = list(set(moods))
            print(f"Detected moods: {', '.join(unique_moods)}")
            mood_counts = {mood: moods.count(mood) for mood in unique_moods}
            dominant_mood = max(mood_counts.items(), key=lambda x: x[1])
            print(f"Dominant mood: {dominant_mood[0]} ({dominant_mood[1]} chunks)")
        else:
            print("No moods detected — check for feature extraction or model issues.")

    except Exception as e:
        print(f"Error in main execution: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
