import os
from pathlib import Path
import time
import librosa
import numpy as np
import csv
import threading
import queue
# Ensure you have 'pyserial' installed and that SimpleDMX is the correct class
from pyserial import SimpleDMX 

# Import your custom modules
# NOTE: These modules must be functional and return valid data types!
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

# ====================================================================
# CONFIGURATION CONSTANTS (Optimized for Responsiveness)
# ====================================================================
SR = 44100
WINDOW_SEC = 2.5    # Window for good feature stability
HOP_SEC = 0.25      # CRITICAL: Faster update rate (4 times per second)
WINDOW_SIZE = int(WINDOW_SEC * SR)
HOP_SIZE = int(HOP_SEC * SR)
LOUDNESS_HIGH_THRESHOLD = -20
LOUDNESS_LOW_THRESHOLD = -40
# ====================================================================

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

def save_moods_to_csv(mood_list, filename):
    with open(filename, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(['Chunk Start Time (s)', 'Mood', 'Color (RGB)', 'Loudness (dB)', 'Energy Level'])
        for data in mood_list:
            timestamp, mood, color, loudness, energy = data
            writer.writerow([f'{timestamp:.2f}', mood, str(color), f'{loudness:.2f}', energy])

def process_audio_chunk(chunk, buffer, genre):
    buffer.update(chunk)
    windowed_audio = buffer.get_window()
    
    # Feature Extraction
    mode_key = detect_mode_key(windowed_audio)
    tempo = detect_tempo(windowed_audio)
    loudness = detect_loudness(windowed_audio)
    rhythm = extract_rhythm(windowed_audio)
    harmony = extract_harmony(windowed_audio)
    
    # Mood Prediction
    features_processed = preprocess_features(mode_key, tempo, loudness, rhythm[0], harmony)
    mood = predict_mood(features_processed)
    
    # Color and Energy Mapping
    mood_color = map_mood_to_genre_color(mood, genre)
    energy_level = get_energy_level(loudness)
    
    return mood, mood_color, loudness, energy_level

def lighting_controller_thread(genre, dmx_port, mood_queue, stop_event):
    # Initialize DMX device
    try:
        dmx = SimpleDMX(port=dmx_port)
        dmx.start_broadcast()
    except Exception as e:
        print(f"[ERROR] Could not initialize SimpleDMX on port {dmx_port}: {e}")
        return # Exit the thread if DMX fails
        
    print(f"\n[DMX Thread] Starting adaptive lighting controller on {dmx_port}...")
    
    # Track the last received mood data for debugging
    last_mood_data = ("N/A", (0, 0, 0), -99.0, "low")
    
    try:
        while not stop_event.is_set():
            try:
                # Use get_nowait() to check the queue without blocking
                mood, color, loudness, energy = mood_queue.get_nowait()
                
                # Check if the state has actually changed to prevent redundant DMX calls
                if (mood, color, loudness, energy) != last_mood_data:
                    last_mood_data = (mood, color, loudness, energy)
                    
                    # LOGGING CHANGE
                    print(f"[DMX Thread] NEW STATE - Mood: {mood}, Loudness: {loudness:.2f}dB, Color: {color}, Energy: {energy}")

                    # DMX Control Logic based on Loudness/Energy
                    if loudness >= LOUDNESS_HIGH_THRESHOLD:
                        # High energy sections use High Frequency/Dynamic DMX
                        run_high_frequency_dmx_chunk(dmx, color, energy)
                    elif loudness <= LOUDNESS_LOW_THRESHOLD:
                        # Low energy sections use Low Frequency/Smooth DMX
                        run_low_frequency_dmx_chunk(dmx, color, energy)
                    else:
                        # Mid-range uses Low Frequency/Smooth DMX (default)
                        run_low_frequency_dmx_chunk(dmx, color, energy)
                        
            except queue.Empty:
                # This is normal when waiting for the next audio chunk to process
                pass
            except Exception as e:
                print(f"[DMX Thread] Runtime Error during DMX action: {e}")
            
            # Short sleep to prevent 100% CPU usage while waiting for queue
            time.sleep(0.01) 

    finally:
        print("[DMX Thread] Lighting controller exiting. Closing DMX connection.")
        dmx.close()

def process_single_file(filepath, genre, dmx_port):
    print(f"\nProcessing {filepath}... Genre: {genre}")
    
    # Load the audio file
    try:
        y, sr = librosa.load(filepath, sr=SR, mono=True)
    except Exception as e:
        print(f"ERROR: Failed to load audio file: {e}")
        return []

    if len(y) == 0:
        print("ERROR: Audio file is empty or invalid.")
        return []
    print(f"Loaded audio file. Duration: {len(y) / sr:.2f} seconds")

    buffer = AudioBuffer(WINDOW_SIZE)
    chunk_moods = []
    mood_queue = queue.Queue(maxsize=20) # Queue to buffer upcoming DMX commands
    stop_event = threading.Event()

    # Start the DMX control thread
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
                # 1. Process the audio chunk and extract features
                mood, mood_color, loudness, energy = process_audio_chunk(chunk, buffer, genre)
                timestamp = pos / sr
                
                chunk_moods.append((timestamp, mood, mood_color, loudness, energy))
                
                # 2. Put the new state into the queue for the DMX thread
                try:
                    mood_queue.put_nowait((mood, mood_color, loudness, energy))
                except queue.Full:
                    # If the queue is full, the DMX thread is falling behind.
                    # Drop the data to maintain real-time performance (skip a frame).
                    print(f"WARNING: Queue full at {timestamp:.2f}s. Skipping DMX update.")

                # 3. Print the analysis result
                print(f"[{timestamp:6.2f}s] Mood: {mood:12s} | Color: {mood_color} | Loudness: {loudness:6.2f}dB | Energy: {energy}")
            
            except Exception as e:
                print(f"Error processing chunk at {pos/sr:.2f}s: {e}")
                import traceback
                traceback.print_exc()
            
            pos += HOP_SIZE
            
            # 4. Time control for real-time processing
            elapsed = time.time() - start_time
            sleep_time = HOP_SEC - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)
            # If sleep_time <= 0, we are behind schedule!

    except KeyboardInterrupt:
        print("\nStopping analysis manually (Ctrl+C).")
    except Exception as e:
        print(f"Unexpected processing error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Stop the DMX thread gracefully
        stop_event.set()
        lighting_thread.join(timeout=3)
        
        print(f"\nProcessed {len(chunk_moods)} chunks.")
        output_file = f"mood_analysis_{Path(filepath).stem}_{genre.replace(' ', '_')}.csv"
        save_moods_to_csv(chunk_moods, output_file)
        print(f"Results saved to: {output_file}")
    return chunk_moods

def main():
    try:
        genre, filepath, dmx_port = get_user_inputs()
        
        print(f"\n--- System Configuration ---")
        print(f"Genre: {genre}")
        print(f"Audio file: {filepath}")
        print(f"DMX port: {dmx_port}")
        print(f"Processing window: {WINDOW_SEC}s, Hop size: {HOP_SEC}s")
        print(f"Loudness thresholds: High > {LOUDNESS_HIGH_THRESHOLD}dB, Low < {LOUDNESS_LOW_THRESHOLD}dB")
        print("----------------------------")
        
        input("\nPress Enter to start real-time music analysis and lighting control...")
        results = process_single_file(filepath, genre, dmx_port)
        
        print("\n=== Analysis Complete ===")
        if results:
            moods = [mood for _, mood, _, _, _ in results]
            unique_moods = list(set(moods))
            print(f"Detected moods: {', '.join(unique_moods)}")
            
            mood_counts = {mood: moods.count(mood) for mood in unique_moods}
            if mood_counts:
                dominant_mood = max(mood_counts.items(), key=lambda x: x[1])
                print(f"Dominant mood: {dominant_mood[0]} ({dominant_mood[1]} chunks)")
            else:
                print("No mood chunks recorded.")
        else:
            print("No moods detected — check file loading or feature extraction.")
            
    except Exception as e:
        print(f"FATAL ERROR in main execution: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
