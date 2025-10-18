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

# Constants
SR = 44100
WINDOW_SEC = 5.0
HOP_SEC = 2.5
WINDOW_SIZE = int(WINDOW_SEC * SR)
HOP_SIZE = int(HOP_SEC * SR)
LOUDNESS_HIGH_THRESHOLD = -20
LOUDNESS_LOW_THRESHOLD = -40


# === User Input ===
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
                print("Invalid choice. Try again.")
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


# === Color Mapping ===
def map_features_to_color(loudness, tempo):
    """
    Generate RGBW color and hue speed based on loudness & tempo.
    Louder → brighter; Faster → more blueish tone.
    """
    loud_norm = np.clip((loudness + 60) / 50, 0.0, 1.0)  # normalize -60–0dB
    tempo_norm = np.clip((tempo - 60) / 120, 0.0, 1.0)   # normalize 60–180 BPM

    # Compute base color: blend red (slow) → blue (fast)
    red = int(255 * (1 - tempo_norm))
    blue = int(255 * tempo_norm)
    green = int(100 + 155 * loud_norm)
    white = int(80 * loud_norm)

    hue_speed = 0.5 + tempo_norm * 1.5  # faster tempo → quicker hue cycling
    return (red, green, blue, white), hue_speed


# === Audio Chunk Processing ===
def process_audio_chunk(chunk, buffer):
    buffer.update(chunk)
    windowed_audio = buffer.get_window()

    # Extract relevant features
    tempo = detect_tempo(windowed_audio)
    loudness = detect_loudness(windowed_audio)

    return tempo, loudness


# === Lighting Controller Thread ===
def lighting_controller_thread(dmx_port, mood_queue, stop_event):
    dmx = SimpleDMX(port=dmx_port)
    dmx.start_broadcast()
    print("\n[Lighting] Controller started...")

    try:
        while not stop_event.is_set():
            try:
                if not mood_queue.empty():
                    tempo, loudness = mood_queue.get_nowait()
                    rgbw, hue_speed = map_features_to_color(loudness, tempo)
                    dmx.update_lighting(rgbw, hue_speed)
            except queue.Empty:
                pass
            except Exception as e:
                print(f"[Lighting thread] Error: {e}")
            time.sleep(0.1)
    finally:
        print("Lighting controller exiting.")
        dmx.close()


# === Main Audio Loop ===
def process_single_file(filepath, genre, dmx_port):
    print(f"\nProcessing {filepath}... Genre: {genre}")
    y, sr = librosa.load(filepath, sr=SR, mono=True)
    if len(y) == 0:
        print("ERROR: Audio file empty or invalid.")
        return

    print(f"Loaded audio file. Duration: {len(y) / sr:.2f} seconds")

    buffer = AudioBuffer(WINDOW_SIZE)
    mood_queue = queue.Queue(maxsize=10)
    stop_event = threading.Event()

    lighting_thread = threading.Thread(
        target=lighting_controller_thread,
        args=(dmx_port, mood_queue, stop_event),
        daemon=True
    )
    lighting_thread.start()

    try:
        pos = 0
        print("\nStarting analysis and lighting...")
        print("Press Ctrl+C to stop.\n")
        while pos < len(y):
            start_time = time.time()
            chunk = y[pos:pos + HOP_SIZE]
            if len(chunk) < HOP_SIZE:
                chunk = np.pad(chunk, (0, HOP_SIZE - len(chunk)), 'constant')

            try:
                tempo, loudness = process_audio_chunk(chunk, buffer)
                if not mood_queue.full():
                    mood_queue.put((tempo, loudness))
                print(f"[{pos / sr:6.2f}s] Tempo: {tempo:6.2f} BPM | Loudness: {loudness:6.2f} dB")
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
        print("\nAnalysis complete. Lighting thread stopped.")


# === Entry Point ===
def main():
    try:
        genre, filepath, dmx_port = get_user_inputs()
        print(f"\nConfiguration:")
        print(f"Genre: {genre}")
        print(f"Audio: {filepath}")
        print(f"DMX Port: {dmx_port}")
        print(f"Window: {WINDOW_SEC}s | Hop: {HOP_SEC}s\n")
        input("Press Enter to start...")
        process_single_file(filepath, genre, dmx_port)
    except Exception as e:
        print(f"Error in main(): {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
