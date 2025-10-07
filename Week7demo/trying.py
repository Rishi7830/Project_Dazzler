import os
from pathlib import Path
import time
import librosa
import numpy as np
import csv  # kept in case you re-enable CSV later
import threading
import queue

from Buffer_Manager_Week7 import AudioBuffer
from Mode_Extraction_Week7 import detect_mode_key
from Tempo_detection_week7 import detect_tempo
from Loudness_detection_Week7 import detect_loudness
from Rhythm_Detection_Week7 import extract_rhythm
from Harmony_detection_Week7 import extract_harmony
from KNN_Week7 import preprocess_features, predict_mood
from mood_color_map import map_mood_to_genre_color, get_energy_level
from High_Frequency_DMX import run_high_frequency_dmx_chunk
from Low_Frequency_DMX import run_low_frequency_dmx_chunk

# Constants
SR = 44100
WINDOW_SEC = 5.0
HOP_SEC = 2.5
WINDOW_SIZE = int(WINDOW_SEC * SR)
HOP_SIZE = int(HOP_SEC * SR)

# Loudness thresholds (tune to your material after viewing logs)
LOUDNESS_HIGH_THRESHOLD = -20.0
LOUDNESS_LOW_THRESHOLD = -40.0

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

    # Genre
    while True:
        try:
            choice = int(input(f"\nSelect genre (1-{len(genres)}): "))
            if 1 <= choice <= len(genres):
                selected_genre = genres[choice - 1]
                break
            else:
                print("Invalid choice. Try again.")
        except ValueError:
            print("Please enter a valid number.")

    # Audio path
    while True:
        filepath = input("\nEnter the path to your audio file: ").strip().strip('"')
        if os.path.exists(filepath):
            break
        else:
            print("File not found. Please enter a valid path.")

    # DMX port
    dmx_port = input("\nEnter DMX port (default: COM14): ").strip() or "COM14"

    return selected_genre, filepath, dmx_port

def process_audio_chunk(chunk, buffer, genre):
    # Update buffer and get window
    buffer.update(chunk)
    windowed_audio = buffer.get_window()
    if windowed_audio is None or len(windowed_audio) == 0:
        raise ValueError("Empty windowed_audio from buffer")

    # Feature extraction with guards
    mode_key = detect_mode_key(windowed_audio, SR)
    tempo = detect_tempo(windowed_audio, SR)
    loudness = detect_loudness(windowed_audio)
    rhythm = extract_rhythm(windowed_audio, SR)
    harmony = extract_harmony(windowed_audio, SR)

    # Validate/coerce
    if mode_key is None:
        mode_key = "C"
    if tempo is None or not np.isfinite(tempo):
        tempo = 120.0
    if loudness is None or not np.isfinite(loudness):
        loudness = -30.0
    if rhythm is None:
        rhythm = []
    if harmony is None:
        harmony = []

    # Build features vector
    # Ensure preprocess_features knows how to handle categorical 'mode_key'
    # If not, remove it or encode it there.
    features = [mode_key, tempo, loudness] + list(rhythm) + list(harmony)

    # Predict mood
    features_processed = preprocess_features([features])
    mood = predict_mood(features_processed)[0]

    # Map to color and energy
    mood_color = map_mood_to_genre_color(mood, genre)
    energy_level = get_energy_level(loudness)

    return mood, mood_color, loudness, energy_level

def lighting_controller_thread(dmx_port, mood_queue):
    lighting_active = True
    try:
        print("\nStarting adaptive lighting controller (loudness-based mode switching)...")
        while lighting_active:
            if not mood_queue.empty():
                mood, color, loudness, energy = mood_queue.get()

                # Decide lighting mode
                try:
                    if loudness >= LOUDNESS_HIGH_THRESHOLD:
                        print(f"[DMX] Loudness {loudness:.2f} >= {LOUDNESS_HIGH_THRESHOLD}: HIGH frequency/strobe")
                        run_high_frequency_dmx_chunk(color, energy, dmx_port, duration=5.0)
                    elif loudness <= LOUDNESS_LOW_THRESHOLD:
                        print(f"[DMX] Loudness {loudness:.2f} <= {LOUDNESS_LOW_THRESHOLD}: LOW frequency/fade")
                        run_low_frequency_dmx_chunk(color, energy, dmx_port, duration=5.0)
                    else:
                        print(f"[DMX] Loudness {loudness:.2f}: MID -> LOW frequency")
                        run_low_frequency_dmx_chunk(color, energy, dmx_port, duration=5.0)
                except Exception as e:
                    import traceback
                    print(f"[DMX ERROR] {e}")
                    traceback.print_exc()

            time.sleep(0.05)
    except Exception as e:
        print(f"[Lighting thread error] {e}")
    finally:
        lighting_active = False

def process_single_file(filepath, genre, dmx_port):
    print(f"\nProcessing {filepath}...")
    print(f"Genre: {genre}")

    # Load audio and print details
    y, sr = librosa.load(filepath, sr=SR, mono=True)
    print(f"Loaded audio file. Duration: {len(y)/sr:.2f} seconds")
    print(f"Audio shape={y.shape}, dtype={y.dtype}, first10={y[:10]}")
    print(f"WINDOW_SIZE={WINDOW_SIZE}, HOP_SIZE={HOP_SIZE}, total_samples={len(y)}")

    if len(y) == 0:
        print("ERROR: Audio file is empty or could not be loaded.")
        return

    # Initialize pipeline
    buffer = AudioBuffer(WINDOW_SIZE)
    mood_queue = queue.Queue(maxsize=16)

    # Start DMX thread
    lighting_thread = threading.Thread(
        target=lighting_controller_thread,
        args=(dmx_port, mood_queue),
        daemon=True
    )
    lighting_thread.start()

    try:
        pos = 0
        chunk_count = 0

        print("\nStarting real-time analysis and lighting...")
        print("Press Ctrl+C to stop.\n")

        while pos < len(y):
            start_time = time.time()
            chunk_idx = pos // HOP_SIZE

            # Slice chunk and pad to hop size
            chunk = y[pos:pos + HOP_SIZE]
            if len(chunk) < HOP_SIZE:
                chunk = np.pad(chunk, (0, HOP_SIZE - len(chunk)), 'constant')

            # Prove loop is running
            print(f"[loop] idx={chunk_idx} pos={pos} len(chunk)={len(chunk)}")

            # Per-chunk guarded processing
            try:
                mood, mood_color, loudness, energy_level = process_audio_chunk(chunk, buffer, genre)
                # Validate
                if mood is None or mood_color is None or not np.isfinite(loudness):
                    raise ValueError(f"Invalid outputs: mood={mood}, color={mood_color}, loudness={loudness}")
            except Exception as e:
                import traceback
                print(f"[error] chunk {chunk_idx} failed: {e}")
                traceback.print_exc()
                # Fallbacks to keep pipeline moving and DMX active
                mood, mood_color, loudness, energy_level = ("neutral", (128,128,128), -30.0, 0.5)

            # Send to DMX thread
            if not mood_queue.full():
                mood_queue.put((mood, mood_color, loudness, energy_level))

            # Progress line
            timestamp = pos / sr
            print(f"[{timestamp:6.2f}s] Mood: {mood:12s} | Color: {mood_color} | Loudness: {loudness:5.2f}dB | Energy: {energy_level}")

            # Advance
            pos += HOP_SIZE
            chunk_count += 1

            # Real-time pacing
            elapsed = time.time() - start_time
            sleep_time = HOP_SEC - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

    except KeyboardInterrupt:
        print("\nStopping analysis...")
    finally:
        # Allow DMX thread to drain and exit
        time.sleep(0.3)
        print(f"\nProcessed {chunk_count} chunks.")
        # No CSV writeout per request: DMX output only.

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

        process_single_file(filepath, genre, dmx_port)

        print("\n=== Analysis Complete ===")

    except Exception as e:
        print(f"Error in main execution: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
