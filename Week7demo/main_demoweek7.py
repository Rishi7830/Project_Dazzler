import os
from pathlib import Path
import time
import librosa
import numpy as np
import threading
import queue
import colorsys
from pyserial import SimpleDMX  # your DMX class

from Buffer_Manager_Week7 import AudioBuffer
from Mode_Extraction_Week7 import detect_mode_key
from Tempo_detection_week7 import detect_tempo
from Loudness_detection_Week7 import detect_loudness
from Rhythm_Detection_Week7 import extract_rhythm
from Harmony_detection_Week7 import extract_harmony
from KNN_Week7 import preprocess_features, predict_mood
from mood_color_map import map_mood_to_genre_color, get_energy_level


# ============================================================
# CONSTANTS
# ============================================================
SR = 44100
WINDOW_SEC = 5.0
HOP_SEC = 2.5
WINDOW_SIZE = int(WINDOW_SEC * SR)
HOP_SIZE = int(HOP_SEC * SR)
LOUDNESS_HIGH_THRESHOLD = -20
LOUDNESS_LOW_THRESHOLD = -40


# ============================================================
# USER INPUTS
# ============================================================
def get_user_inputs():
    print("=== Music-to-Light System ===")
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


# ============================================================
# AUDIO CHUNK PROCESSING
# ============================================================
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
    mood_color = map_mood_to_genre_color(mood, genre)
    energy_level = get_energy_level(loudness)
    return mood, mood_color, loudness, energy_level, tempo


# ============================================================
# LIGHTING CONTROLLER THREAD
# ============================================================
def lighting_controller_thread(genre, dmx_port, mood_queue, stop_event):
    dmx = SimpleDMX(port=dmx_port)
    dmx.start_broadcast()
    print("\nStarting adaptive lighting controller...")

    hue = 0.0
    brightness = 0.5
    prev_color = (0, 0, 0, 0)

    try:
        while not stop_event.is_set():
            try:
                if not mood_queue.empty():
                    mood, color, loudness, energy, tempo = mood_queue.get_nowait()

                    # Map loudness (-60dB → 0dB) to brightness 0–1
                    brightness = np.clip((loudness + 60) / 60.0, 0.0, 1.0)

                    # Map tempo to hue cycling speed (0.1–1.0 range)
                    hue_speed = np.clip(tempo / 200.0, 0.1, 1.0)

                    # Cycle hue smoothly
                    hue = (hue + hue_speed * 0.02) % 1.0

                    # Convert HSV → RGB
                    r, g, b = colorsys.hsv_to_rgb(hue, 1.0, brightness)
                    rgbw = (int(r * 255), int(g * 255), int(b * 255), 0)

                    # Smooth transition (lerp)
                    r = int(prev_color[0] + 0.3 * (rgbw[0] - prev_color[0]))
                    g = int(prev_color[1] + 0.3 * (rgbw[1] - prev_color[1]))
                    b = int(prev_color[2] + 0.3 * (rgbw[2] - prev_color[2]))
                    w = int(prev_color[3] + 0.3 * (rgbw[3] - prev_color[3]))
                    prev_color = (r, g, b, w)

                    # Update DMX lighting using your method
                    dmx.update_lighting(prev_color, hue_speed)

                    print(f"[Light] Mood={mood:10s} | Tempo={tempo:6.1f} BPM | Loudness={loudness:6.1f} dB | RGBW={prev_color}")

            except Exception as e:
                print(f"[Lighting thread] Error: {e}")

            time.sleep(0.05)  # smooth updates
    finally:
        print("Lighting controller exiting.")
        dmx.close()


# ============================================================
# MAIN AUDIO PROCESSING LOOP
# ============================================================
def process_single_file(filepath, genre, dmx_port):
    print(f"\nProcessing {filepath}... Genre: {genre}")
    y, sr = librosa.load(filepath, sr=SR, mono=True)
    if len(y) == 0:
        print("ERROR: Audio file is empty or invalid.")
        return
    print(f"Loaded audio file. Duration: {len(y) / sr:.2f} seconds")

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
                mood, mood_color, loudness, energy, tempo = process_audio_chunk(chunk, buffer, genre)
                timestamp = pos / sr
                if not mood_queue.full():
                    mood_queue.put((mood, mood_color, loudness, energy, tempo))
                print(f"[{timestamp:6.2f}s] Mood: {mood:12s} | Loudness: {loudness:6.2f}dB | Tempo: {tempo:5.1f}")
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
        print("\nProcessing complete. Lighting stopped.")


# ============================================================
# MAIN ENTRY POINT
# ============================================================
def main():
    genre, filepath, dmx_port = get_user_inputs()
    print(f"\nConfiguration:")
    print(f"Genre: {genre}")
    print(f"Audio file: {filepath}")
    print(f"DMX port: {dmx_port}")
    print(f"Processing window: {WINDOW_SEC}s, hop: {HOP_SEC}s")
    input("\nPress Enter to start...\n")
    process_single_file(filepath, genre, dmx_port)


if __name__ == "__main__":
    main()
