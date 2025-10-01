import os
from pathlib import Path
import time
import librosa
import numpy as np
from concurrent.futures import ThreadPoolExecutor
import csv
import threading
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

# Global variables for DMX control
dmx_controller = None
lighting_active = False

def get_user_inputs():
    """Get user inputs for genre and song file."""
    print("=== Music-to-Light System ===")
    print("\nAvailable genres:")
    genres = [
        "classical", "rock", "blues", "hip hop and rap", "soul", 
        "indie", "country", "gospel", "jazz", "folk", 
        "electronics and dance", "latin", "metal", "pop", "reggae"
    ]
    
    for i, genre in enumerate(genres, 1):
        print(f"{i}. {genre}")
    
    # Get genre selection
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
    
    # Get song file
    while True:
        filepath = input("\nEnter the path to your audio file: ").strip().strip('"')
        if os.path.exists(filepath):
            break
        else:
            print("File not found. Please enter a valid path.")
    
    # Get lighting mode
    print("\nLighting modes:")
    print("1. High Frequency (fast strobe, high energy)")
    print("2. Low Frequency (smooth fades, relaxed)")
    
    while True:
        try:
            mode_choice = int(input("Select lighting mode (1-2): "))
            if mode_choice in [1, 2]:
                lighting_mode = "high" if mode_choice == 1 else "low"
                break
            else:
                print("Invalid choice. Please select 1 or 2.")
        except ValueError:
            print("Please enter a valid number.")
    
    # Get DMX port
    dmx_port = input("\nEnter DMX port (default: COM14): ").strip() or "COM14"
    
    return selected_genre, filepath, lighting_mode, dmx_port

def save_moods_to_csv(mood_list, filename):
    """Save mood analysis results to CSV."""
    with open(filename, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(['Chunk Start Time (s)', 'Mood', 'Color (RGB)', 'Loudness (dB)', 'Energy Level'])
        for data in mood_list:
            timestamp, mood, color, loudness, energy = data
            writer.writerow([f'{timestamp:.2f}', mood, str(color), f'{loudness:.2f}', energy])

def process_audio_chunk(chunk, buffer, genre):
    """Process a single audio chunk and return mood, color, and energy data."""
    # Update buffer
    buffer.update(chunk)
    windowed_audio = buffer.get_window()
    
    # Extract features
    mode_key = detect_mode_key(windowed_audio, SR)
    tempo = detect_tempo(windowed_audio, SR)
    loudness = detect_loudness(windowed_audio)
    rhythm = extract_rhythm(windowed_audio, SR)
    harmony = extract_harmony(windowed_audio, SR)
    
    # Combine features
    features = [mode_key, tempo, loudness] + rhythm + harmony
    
    # Preprocess and predict mood
    features_processed = preprocess_features([features])
    mood = predict_mood(features_processed)[0]
    
    # Map mood to color based on genre
    mood_color = map_mood_to_genre_color(mood, genre)
    
    # Get energy level for lighting intensity
    energy_level = get_energy_level(loudness)
    
    return mood, mood_color, loudness, energy_level

def lighting_controller_thread(lighting_mode, genre, dmx_port, mood_queue):
    """Thread function to control DMX lighting based on mood data."""
    global dmx_controller, lighting_active
    
    try:
        lighting_active = True
        print(f"Starting {lighting_mode} frequency lighting controller...")
        
        while lighting_active:
            if not mood_queue.empty():
                # Get latest mood data
                mood_data = mood_queue.get()
                mood, color, loudness, energy = mood_data
                
                print(f"Lighting: {mood} -> {color} (Energy: {energy})")
                
                # Trigger appropriate lighting mode
                if lighting_mode == "high":
                    run_high_frequency_dmx_chunk(color, energy, dmx_port, duration=5.0)
                else:
                    run_low_frequency_dmx_chunk(color, energy, dmx_port, duration=5.0)
            
            time.sleep(0.1)  # Small delay to prevent excessive CPU usage
            
    except Exception as e:
        print(f"Lighting controller error: {e}")
    finally:
        lighting_active = False

def process_single_file(filepath, genre, lighting_mode, dmx_port):
    """Process audio file with real-time lighting control."""
    print(f"Processing {filepath}...")
    print(f"Genre: {genre}")
    print(f"Lighting mode: {lighting_mode}")
    
    # Load audio
    y, sr = librosa.load(filepath, sr=SR, mono=True)
    
    # Initialize buffer
    buffer = AudioBuffer(WINDOW_SIZE)
    
    # Initialize data storage
    chunk_moods = []
    
    # Initialize mood queue for lighting thread
    import queue
    mood_queue = queue.Queue(maxsize=10)
    
    # Start lighting controller thread
    lighting_thread = threading.Thread(
        target=lighting_controller_thread,
        args=(lighting_mode, genre, dmx_port, mood_queue)
    )
    lighting_thread.daemon = True
    lighting_thread.start()
    
    try:
        pos = 0
        chunk_count = 0
        
        print("\nStarting real-time analysis and lighting...")
        print("Press Ctrl+C to stop.")
        
        while pos < len(y):
            start_time = time.time()
            
            # Extract audio chunk
            chunk = y[pos:pos + HOP_SIZE]
            if len(chunk) < HOP_SIZE:
                chunk = np.pad(chunk, (0, HOP_SIZE - len(chunk)), 'constant')
            
            # Process chunk
            mood, mood_color, loudness, energy_level = process_audio_chunk(chunk, buffer, genre)
            
            # Store results
            timestamp = pos / SR
            chunk_moods.append((timestamp, mood, mood_color, loudness, energy_level))
            
            # Send to lighting controller
            mood_data = (mood, mood_color, loudness, energy_level)
            if not mood_queue.full():
                mood_queue.put(mood_data)
            
            # Print progress
            print(f"[{timestamp:6.2f}s] Mood: {mood:12s} | Color: {mood_color} | Loudness: {loudness:5.2f}dB | Energy: {energy_level}")
            
            # Move to next chunk
            pos += HOP_SIZE
            chunk_count += 1
            
            # Maintain real-time processing (wait for chunk duration)
            elapsed = time.time() - start_time
            sleep_time = HOP_SEC - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)
        
    except KeyboardInterrupt:
        print("\nStopping analysis...")
    finally:
        # Stop lighting controller
        global lighting_active
        lighting_active = False
        lighting_thread.join(timeout=2)
        
        print(f"\nProcessed {len(chunk_moods)} chunks.")
        
        # Save results to CSV
        output_file = f"mood_analysis_{Path(filepath).stem}_{genre.replace(' ', '_')}.csv"
        save_moods_to_csv(chunk_moods, output_file)
        print(f"Results saved to: {output_file}")
        
        return chunk_moods

def main():
    """Main execution function."""
    try:
        # Get user inputs
        genre, filepath, lighting_mode, dmx_port = get_user_inputs()
        
        print(f"\nConfiguration:")
        print(f"Genre: {genre}")
        print(f"Audio file: {filepath}")
        print(f"Lighting mode: {lighting_mode}")
        print(f"DMX port: {dmx_port}")
        print(f"Processing window: {WINDOW_SEC}s")
        print(f"Hop size: {HOP_SEC}s")
        
        input("\nPress Enter to start...")
        
        # Process the file
        results = process_single_file(filepath, genre, lighting_mode, dmx_port)
        
        print("\n=== Analysis Complete ===")
        if results:
            moods = [mood for _, mood, _, _, _ in results]
            unique_moods = list(set(moods))
            print(f"Detected moods: {', '.join(unique_moods)}")
            
            # Summary statistics
            mood_counts = {mood: moods.count(mood) for mood in unique_moods}
            dominant_mood = max(mood_counts.items(), key=lambda x: x[1])
            print(f"Dominant mood: {dominant_mood[0]} ({dominant_mood[1]} chunks)")
    
    except Exception as e:
        print(f"Error in main execution: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
