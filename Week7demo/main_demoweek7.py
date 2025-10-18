import os
from pathlib import Path
import time
import librosa
import numpy as np
import threading
import queue
from pyserial import SimpleDMX  # your provided DMX class

from Buffer_Manager_Week7 import AudioBuffer
from Mode_Extraction_Week7 import detect_mode_key
from Tempo_detection_week7 import detect_tempo
from Loudness_detection_Week7 import detect_loudness
from Rhythm_Detection_Week7 import extract_rhythm
from Harmony_detection_Week7 import extract_harmony
from KNN_Week7 import preprocess_features, predict_mood
from mood_color_map import map_mood_to_genre_color, get_energy_level, get_brightness_from_energy

# -------------------------
# CONFIG
# -------------------------
SR = 44100
WINDOW_SEC = 5.0
HOP_SEC = 2.5
WINDOW_SIZE = int(WINDOW_SEC * SR)
HOP_SIZE = int(HOP_SEC * SR)

# smoothing / interpolation factor for color transitions (0..1)
COLOR_LERP_FACTOR = 0.25

# -------------------------
# Helpers
# -------------------------
def get_user_inputs():
    print("=== Music-to-Light System ===")
    genres = ["classical", "rock", "blues", "hip hop and rap", "soul", "indie",
              "country", "gospel", "jazz", "folk", "electronics and dance",
              "latin", "metal", "pop", "reggae"]
    for i, g in enumerate(genres, 1):
        print(f"{i}. {g}")
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

def lerp(a, b, t):
    """Linear interpolation for 3/4-tuples; returns ints 0-255."""
    a = np.array(a, dtype=float)
    b = np.array(b, dtype=float)
    out = a + (b - a) * t
    return tuple(int(np.clip(x, 0, 255)) for x in out)

# -------------------------
# Audio chunk processing
# -------------------------
def process_audio_chunk(chunk, buffer, genre):
    buffer.update(chunk)
    windowed_audio = buffer.get_window()

    mode_key = detect_mode_key(windowed_audio)
    tempo = detect_tempo(windowed_audio)
    loudness = detect_loudness(windowed_audio)
    rhythm = extract_rhythm(windowed_audio)
    harmony = extract_harmony(windowed_audio)

    features_processed = preprocess_features(
        mode_key, tempo, loudness, rhythm[0] if isinstance(rhythm, (list, tuple)) else rhythm, harmony
    )
    mood = predict_mood(features_processed)
    mood_color = map_mood_to_genre_color(mood, genre)
    energy_level = get_energy_level(loudness)

    return mood, mood_color, loudness, energy_level, tempo, rhythm, harmony

# -------------------------
# Lighting algorithm
# -------------------------
def adaptive_lighting_step(dmx, genre, mood, base_color_rgb, loudness_db, energy_level, tempo_bpm, rhythm, harmony, prev_rgbw):
    loud_norm = np.clip((loudness_db + 60) / 50.0, 0.0, 1.0)
    tempo_norm = np.clip((tempo_bpm - 60.0) / 120.0, 0.0, 1.0)
    rhythm_scalar = float(np.mean(rhythm)) if isinstance(rhythm, (list, tuple, np.ndarray)) else float(rhythm)
    rhythm_norm = np.clip(rhythm_scalar, 0.0, 1.0)
    harmony_norm = np.clip(harmony if 0 <= harmony <= 1 else (abs(harmony) % 1.0), 0.0, 1.0)
    energy_brightness = get_brightness_from_energy(energy_level)

    hue_speed = float(np.clip(0.6 + tempo_norm * 1.4 + harmony_norm * 0.6, 0.2, 3.0))
    phase = time.time() * (0.2 + hue_speed * 0.6)
    hue = (np.sin(phase) * 0.5 + 0.5)
    pulse = 0.5 + 0.5 * np.sin(2.0 * np.pi * rhythm_norm * (time.time() % max(1.0, (60.0 / max(tempo_bpm, 1.0)))))
    pulse = np.clip(pulse, 0.0, 1.0)
    brightness = float(np.clip(loud_norm * energy_brightness * (0.6 + 0.4 * pulse), 0.05, 1.0))

    base_r, base_g, base_b = base_color_rgb
    shift = (hue - 0.5) * (0.5 + 0.8 * harmony_norm)
    r_mul = np.clip(1.0 + shift, 0.1, 1.9)
    g_mul = np.clip(1.0 - 0.5 * shift, 0.1, 1.9)
    b_mul = np.clip(1.0 - 0.5 * (-shift), 0.1, 1.9)

    target_r = int(np.clip(base_r * r_mul * brightness, 0, 255))
    target_g = int(np.clip(base_g * g_mul * brightness, 0, 255))
    target_b = int(np.clip(base_b * b_mul * brightness, 0, 255))
    target_w = int(np.clip(255 * (0.15 + 0.85 * brightness), 0, 255))

    target_rgbw = (target_r, target_g, target_b, target_w)
    smooth_rgbw = target_rgbw if prev_rgbw is None else lerp(prev_rgbw, target_rgbw, COLOR_LERP_FACTOR)
    safe_rgbw = tuple(int(np.clip(c, 0, 255)) for c in smooth_rgbw)

    try:
        dmx.update_lighting(safe_rgbw, float(hue_speed))
    except Exception:
        try:
            dmx.set_channel(4, safe_rgbw[3])
            dmx.set_channel(3, safe_rgbw[2])
            dmx.set_channel(2, safe_rgbw[1])
            dmx.set_channel(1, safe_rgbw[0])
            dmx.send_frame()
        except Exception:
            print("[DMX fallback] RGBW:", safe_rgbw, "hue_speed:", hue_speed)

    return smooth_rgbw

# -------------------------
# Lighting thread
# -------------------------
def lighting_controller_thread(genre, dmx_port, mood_queue, stop_event):
    dmx = SimpleDMX(port=dmx_port)
    dmx.start_broadcast()
    print("\nStarting adaptive lighting controller...")

    prev_rgbw = None
    try:
        while not stop_event.is_set():
            try:
                item = mood_queue.get(timeout=0.12)
            except queue.Empty:
                continue
            try:
                mood, color, loudness, energy, tempo, rhythm, harmony = item
                prev_rgbw = adaptive_lighting_step(
                    dmx, genre, mood, color, loudness, energy, tempo, rhythm, harmony, prev_rgbw
                )
            except Exception as e:
                print(f"[Lighting thread] Error applying lighting step: {e}")
    finally:
        print("Lighting controller exiting.")
        dmx.close()

# -------------------------
# Main audio processing loop
# -------------------------
def process_single_file(filepath, genre, dmx_port):
    print(f"\nProcessing {filepath}... Genre: {genre}")
    y, sr = librosa.load(filepath, sr=SR, mono=True)
    if len(y) == 0:
        print("ERROR: Audio file is empty or invalid.")
        return []

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
            chunk = y[pos:pos+HOP_SIZE]
            if len(chunk) < HOP_SIZE:
                chunk = np.pad(chunk, (0, HOP_SIZE-len(chunk)), 'constant')

            try:
                mood, mood_color, loudness, energy, tempo, rhythm, harmony = process_audio_chunk(chunk, buffer, genre)
                timestamp = pos / sr
                chunk_moods.append((timestamp, mood, mood_color, loudness, energy))
                if not mood_queue.full():
                    mood_queue.put((mood, mood_color, loudness, energy, tempo, rhythm, harmony))
                print(f"[{timestamp:6.2f}s] Mood: {mood:12s} | Tempo: {tempo:6.2f} | Loud: {loudness:6.2f}dB | Energy: {energy}")
            except Exception as e:
                print(f"Error processing chunk at {pos/sr:.2f}s: {e}")

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
        print(f"\nProcessed {len(chunk_moods)} chunks.")

    return chunk_moods

# -------------------------
# Main
# -------------------------
def main():
    try:
        genre, filepath, dmx_port = get_user_inputs()
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

if __name__ == "__main__":
    main()
