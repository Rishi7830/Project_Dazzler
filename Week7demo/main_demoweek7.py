import os
from pathlib import Path
import time
import librosa
import numpy as np
import queue
import threading

from pyserial import SimpleDMX  # Your DMX class

from Buffer_Manager_Week7 import AudioBuffer
from Mode_Extraction_Week7 import detect_mode_key
from Tempo_detection_week7 import detect_tempo
from Loudness_detection_Week7 import detect_loudness
from Rhythm_Detection_Week7 import extract_rhythm
from Harmony_detection_Week7 import extract_harmony
from KNN_Week7 import preprocess_features, predict_mood

from color_mapper import map_features_to_genre_color, get_energy_level, get_brightness_from_energy, get_available_genres

# ---------------- Configuration ----------------
SR = 44100
WINDOW_SEC = 5.0
HOP_SEC = 2.5
WINDOW_SIZE = int(WINDOW_SEC * SR)
HOP_SIZE = int(HOP_SEC * SR)
UPDATE_INTERVAL = 0.3  # seconds between DMX updates

# ---------------- User Input ----------------
def get_user_inputs():
    print("=== Music-to-Light System ===")
    genres = get_available_genres()
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
    dmx_port = input("\nEnter DMX port (default: COM14 or /dev/ttyUSB0): ").strip() or "COM14"
    return selected_genre, filepath, dmx_port

# ---------------- Audio Chunk Processing ----------------
def process_audio_chunk(chunk, buffer, genre):
    buffer.update(chunk)
    windowed_audio = buffer.get_window()
    mode_key = detect_mode_key(windowed_audio)
    tempo = detect_tempo(windowed_audio)
    loudness = detect_loudness(windowed_audio)
    rhythm = extract_rhythm(windowed_audio)
    harmony = extract_harmony(windowed_audio)
    features_processed = preprocess_features(mode_key, tempo, loudness, rhythm[0], harmony)
    mood = predict_mood(features_processed)
    mood_color = map_features_to_genre_color(loudness, tempo, genre)
    energy_level = get_energy_level(loudness)
    return mood, mood_color, loudness, energy_level

# ---------------- Lighting Thread ----------------
def lighting_controller_thread(genre, dmx_port, mood_queue, stop_event):
    dmx = SimpleDMX(port=dmx_port)
    dmx.start_broadcast()
    print("\nStarting adaptive lighting controller...")
    last_color = None
    last_update_time = 0
    try:
        while not stop_event.is_set():
            try:
                mood, color, loudness, energy = mood_queue.get(timeout=0.2)
                now = time.time()
                if color != last_color or (now - last_update_time) > UPDATE_INTERVAL:
                    brightness = get_brightness_from_energy(energy)
                    scaled_color = tuple(int(c * brightness) for c in color) + (0,)  # RGBW
                    dmx.update_lighting(scaled_color, hue_speed=0.0)
                    last_color = color
                    last_update_time = now
            except queue.Empty:
                continue
            except Exception as e:
                print(f"[Lighting thread] Error: {e}")
    finally:
        print("Lighting controller exiting.")
        dmx.close()

# ---------------- Main Audio Processing ----------------
def process_single_file(filepath, genre, dmx_port):
    print(f"\nProcessing {filepath}... Genre: {genre}")
    y, sr = librosa.load(filepath, sr=SR, mono=True)
    if len(y) == 0:
        print("ERROR: Audio file is empty or invalid.")
        return []

    buffer = AudioBuffer(WINDOW_SIZE)
    mood_queue = queue.Queue(maxsize=10)
    stop_event = threading.Event()

    lighting_thread = threading.Thread(
        target=lighting_controller_thread,
        args=(genre, dmx_port, mood_queue, stop_event),
        daemon=True
    )
    lighting_thread.start()

    try:
        pos = 0
        print("Starting real-time analysis and lighting...")
        print("Press Ctrl+C to stop.\n")
        while pos < len(y):
            start_time = time.time()
            chunk = y[pos:pos + HOP_SIZE]
            if len(chunk) < HOP_SIZE:
                chunk = np.pad(chunk, (0, HOP_SIZE - len(chunk)), 'constant')
            try:
                mood, mood_color, loudness, energy = process_audio_chunk(chunk, buffer, genre)
                timestamp = pos / sr
                if not mood_queue.full():
                    mood_queue.put((mood, mood_color, loudness, energy))
                print(f"[{timestamp:6.2f}s] Mood: {mood:12s} | Color: {mood_color} | Loudness: {loudness:6.2f}dB | Energy: {energy}")
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
    finally:
        stop_event.set()
        lighting_thread.join(timeout=2)
        print(f"\nProcessed {(pos // HOP_SIZE) + 1} chunks.")

# ---------------- Main Entry ----------------
def main():
    try:
        genre, filepath, dmx_port = get_user_inputs()
        print(f"\nConfiguration:")
        print(f"Genre: {genre}")
        print(f"Audio file: {filepath}")
        print(f"DMX port: {dmx_port}")
        print(f"Processing window: {WINDOW_SEC}s")
        print(f"Hop size: {HOP_SEC}s")
        input("\nPress Enter to start...")
        process_single_file(filepath, genre, dmx_port)
    except Exception as e:
        print(f"Error in main execution: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
