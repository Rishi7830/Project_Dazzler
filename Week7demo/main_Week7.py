import time
import numpy as np
import librosa
from mood_color_map import mood_color_map
from Buffer_Manager_Week7 import AudioBuffer
from Mode_Extraction_Week7 import detect_mode_key
from Tempo_detection_week7 import detect_tempo
from Loudness_detection_Week7 import detect_loudness
from Rhythm_Detection_Week7 import extract_rhythm
from Harmony_detection_Week7 import extract_harmony
from KNN_Week7 import preprocess_features, predict_mood

SR = 44100
WINDOW_SEC = 5.0
HOP_SEC = 2.5
WINDOW_SIZE = int(WINDOW_SEC * SR)
HOP_SIZE = int(HOP_SEC * SR)

buffer = AudioBuffer(WINDOW_SIZE)

def set_terminal_color_bg(r, g, b):
    """Sets ANSI background color in terminal"""
    print(f'\x1b[48;2;{r};{g};{b}m', end='')

def reset_terminal():
    """Resets terminal color/style"""
    print('\x1b[0m', end='')

def print_mood_with_countdown(mood, rgb, remaining_time):
    """Display mood, color, and countdown timer"""
    r, g, b = rgb
    color_hex = f'#{r:02x}{g:02x}{b:02x}'
    mins, secs = divmod(int(remaining_time), 60)
    timer_display = f'{mins:02d}:{secs:02d}'
    
    # Clear line and print info with countdown
    print(f'\rMood: {mood:<12s} | RGB: ({r:3d}, {g:3d}, {b:3d}) | Hex: {color_hex} | Time: {timer_display}', end='', flush=True)
    
    # Optional: color bar
    set_terminal_color_bg(r, g, b)
    print('  ', end='')
    reset_terminal()

def load_mp3_audio(filepath, sr=SR):
    """Load MP3 file using librosa"""
    try:
        audio, _ = librosa.load(filepath, sr=sr)
        return audio
    except Exception as e:
        print(f"Error loading MP3 file: {e}")
        return None

def audio_chunks_from_file(audio_data, hop_size):
    """Generator that yields audio chunks from loaded file"""
    total_samples = len(audio_data)
    position = 0
    
    while position + hop_size <= total_samples:
        yield audio_data[position:position + hop_size]
        position += hop_size

def run_real_time_processing(mp3_filepath):
    """Process MP3 file with mood detection and countdown"""
    print(f"Loading MP3 file: {mp3_filepath}")
    audio_data = load_mp3_audio(mp3_filepath)
    
    if audio_data is None:
        print("Failed to load audio file. Exiting.")
        return
    
    total_duration = len(audio_data) / SR
    print(f"Audio loaded successfully. Duration: {total_duration:.2f} seconds\n")
    
    start_time = time.time()
    
    try:
        for chunk in audio_chunks_from_file(audio_data, HOP_SIZE):
            buffer.update(chunk)
            audio_window = buffer.get_window()

            # Extract features
            mode, key = detect_mode_key(audio_window)
            tempo = detect_tempo(audio_window)
            loudness = detect_loudness(audio_window)
            bpm, rhythm_index = extract_rhythm(audio_window)
            _, _, _, _, harmony_class = extract_harmony(audio_window)

            # Predict mood
            features = preprocess_features(mode, key, tempo, loudness, rhythm_index, harmony_class)
            mood = predict_mood(features)
            color = mood_color_map.get(mood, (255, 255, 255))

            # Calculate remaining time
            elapsed = time.time() - start_time
            remaining = max(0, total_duration - elapsed)
            
            print_mood_with_countdown(mood, color, remaining)
            
            # Sleep to maintain real-time playback sync
            time.sleep(HOP_SEC)
            
            if remaining <= 0:
                break
                
        print("\n\n✓ Processing complete!")
        
    except KeyboardInterrupt:
        reset_terminal()
        print("\n\n⏸ Processing interrupted.")

if __name__ == '__main__':
    # Replace with your MP3 file path
    mp3_file = input("Enter MP3 file path: ").strip()
    run_real_time_processing(mp3_file)
