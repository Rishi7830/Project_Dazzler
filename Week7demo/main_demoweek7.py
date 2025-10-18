import os
from pathlib import Path
import time
import librosa
import numpy as np
import csv
import threading
import queue
import colorsys
from pyserial import SimpleDMX  # ensure you have pyserial.SimpleDMX installed

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
    genres = ["classical", "rock", "blues", "hip hop and rap", "soul", "indie",
              "country", "gospel", "jazz", "folk", "electronics and dance",
              "latin", "metal", "pop", "reggae"]
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


# ============================================================
# CSV EXPORT
# ============================================================
def save_moods_to_csv(mood_list, filename):
    with open(filename, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(['Chunk Start Time (s)', 'Mood', 'Color (RGB)', 'Loudness (dB)', 'Energy Level', 'Tempo'])
        for data in mood_list:
            timestamp, mood, color, loudness, energy, tempo = data
            writer.writerow([f'{timestamp:.2f}', mood, str(color), f'{loudness:.2f}', energy, f'{tempo:.1f}'])


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
    prev_mood = None
    prev_color = (0, 0, 0)

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
                    rgb = (int(r * 255), int(g * 255), int(b * 255))

                    # Smooth transition from previous color (lerp)
                    r = int(prev_color[0] + 0.3 * (rgb[0] - prev_color[0]))
                    g = int(prev_color[1] + 0.3 * (rgb[1] - prev_color[1]))
                    b = int(prev_color[2] + 0.3 * (rgb[2] - prev_color[2]))
                    prev_color = (r, g, b)

                    # Send DMX color
                    dmx.set_channels([r, g, b])
                    dmx.render()

                    # Debug info
                    print(f"[Light] Mood={mood:10s} | Tempo={tempo:6.1f} BPM | Loudness={loudness:6.1f} dB | RGB={prev_color}")

                    prev_mood = mood

            except queue.Empty:
                pass
            except Exception as e:
                print(f"[Lighting thread] Error: {e}")

            time.sleep(0.05)  # ~20 FPS updates for smooth transitions
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
        return []
    print(f"Loaded audio file. Duration: {len(y) / sr:.2f} seconds")

    buffer = AudioBuffer(WINDOW_SIZE)
    chunk_moods = []
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
                chunk_moods.append((timestamp, mood, mood_color, loudness, energy, tempo))
                if not mood_queue.full():
                    mood_queue.put((mood, mood_color, loudness, energy, tempo))
                print(f"[{timestamp:6.2f}s] Mood: {mood:12s} | Color: {mood_color} | Loudness: {loudness:6.2f}dB | Energy: {energy} | Tempo: {tempo:.1f}")
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
        stop_event.set()
        lighting_thread.join(timeout=2)
        print(f"\nProcessed {len(chunk_moods)} chunks.")
        output_file = f"mood_analysis_{Path(filepath).stem}_{genre.replace(' ', '_')}.csv"
        save_moods_to_csv(chunk_moods, output_file)
        print(f"Results saved to: {output_file}")
    return chunk_moods


# ============================================================
# MAIN ENTRY POINT
# ============================================================
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
        input("\nPress Enter to start...")
        results = process_single_file(filepath, genre, dmx_port)
        print("\n=== Analysis Complete ===")
        if results:
            moods = [mood for _, mood, _, _, _, _ in results]
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
