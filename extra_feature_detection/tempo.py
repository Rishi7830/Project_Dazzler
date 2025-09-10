import librosa
import numpy as np
import time
import serial
import argparse
from scipy.signal import butter, filtfilt
import pygame
import threading

def create_low_pass_filter(cutoff_freq, sample_rate, order=8):
    """Create a low-pass filter for bass frequency isolation"""
    nyquist = sample_rate / 2
    normal_cutoff = cutoff_freq / nyquist
    b, a = butter(order, normal_cutoff, btype='low')
    return b, a

def analyze_bass_onsets(audio_file, amplitude_threshold=0.40, cutoff_freq=200, duration=None):
    """
    Analyze the audio file to detect bass onsets and return their timestamps.
    Uses the same onset detection method as the reference code.
    """
    print(f"Analyzing audio file: {audio_file}")
    
    # Load the audio file
    y, sr = librosa.load(audio_file, sr=None, duration=duration)
    duration = librosa.get_duration(y=y, sr=sr)
    print(f"Audio loaded. Sample rate: {sr}Hz, Duration: {duration:.2f}s")
    
    # Apply low-pass filter to isolate bass frequencies
    nyquist = sr / 2
    normal_cutoff = cutoff_freq / nyquist
    b, a = butter(8, normal_cutoff, btype='low')
    y_bass = filtfilt(b, a, y)
    
    # Normalize the bass waveform
    max_val = np.max(np.abs(y_bass))
    if max_val > 0:
        y_bass_norm = y_bass / max_val
    else:
        y_bass_norm = y_bass
    
    # Find bass onset points (rising edges crossing threshold)
    onset_indices = []
    for i in range(1, len(y_bass_norm)):
        if np.abs(y_bass_norm[i]) >= amplitude_threshold and np.abs(y_bass_norm[i-1]) < amplitude_threshold:
            onset_indices.append(i)
    
    # Convert indices to timestamps
    onset_times = [(idx / sr) for idx in onset_indices]
    
    print(f"Analysis complete. Found {len(onset_times)} bass onsets.")
    
    # Optional: Calculate estimated BPM if enough onsets were found
    if len(onset_times) > 1:
        intervals = np.diff(onset_times)
        avg_interval = np.mean(intervals)
        bass_bpm = 60 / avg_interval if avg_interval > 0 else 0
        print(f"Estimated BPM (bass onsets): {bass_bpm:.1f}")
    
    return onset_times, sr

def led_control_thread(arduino, bass_onsets, start_time, colour):
    """Thread function to control LED timing based on detected bass onsets"""
    print("LED control thread started")
    onset_index = 0
    
    while onset_index < len(bass_onsets):
        current_time = time.time() - start_time
        
        # Check if we need to trigger the next onset
        if onset_index < len(bass_onsets) and current_time >= bass_onsets[onset_index]:
            arduino.write(colour)
            print(f"LED flash at {current_time:.2f}s (onset #{onset_index+1})")
            onset_index += 1
        
        # Small sleep to avoid consuming too much CPU
        time.sleep(0.001)
    
    print("LED control thread completed")

def play_audio_and_sync_leds(audio_file, arduino_port, bass_onsets, arduino_baud=9600, colour):
    """Play the audio file and synchronize LED flashes with the detected bass onsets"""
    # Initialize pygame for audio playback
    pygame.mixer.init()
    pygame.init()
    
    # Connect to Arduino
    try:
        arduino = serial.Serial(arduino_port, arduino_baud, timeout=1)
        print(f"Connected to Arduino on {arduino_port}")
        time.sleep(2)  # Give the Arduino time to reset
    except Exception as e:
        print(f"Error connecting to Arduino: {e}")
        return
    
    try:
        # Load and play the audio
        print(f"Loading audio for playback: {audio_file}")
        pygame.mixer.music.load(audio_file)
        
        print("\n=== STARTING PLAYBACK AND LED SYNCHRONIZATION ===\n")
        print("3...")
        time.sleep(1)
        print("2...")
        time.sleep(1)
        print("1...")
        time.sleep(1)
        print("GO!")
        
        # Start playing the audio
        pygame.mixer.music.play()
        start_time = time.time()
        
        # Start LED control in a separate thread
        led_thread = threading.Thread(target=led_control_thread, 
                                     args=(arduino, bass_onsets, start_time, colour))
        led_thread.start()
        
        # Wait until the song finishes
        while pygame.mixer.music.get_busy():
            pygame.time.Clock().tick(10)
        
        # Wait for LED thread to complete
        led_thread.join()
        
        print("\n=== PLAYBACK AND LED SYNCHRONIZATION COMPLETE ===")
        
    except Exception as e:
        print(f"Error during playback: {e}")
    finally:
        # Cleanup
        pygame.mixer.quit()
        pygame.quit()
        arduino.close()
        print("Resources cleaned up.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Play audio and synchronize LED flashes with bass onsets')
    parser.add_argument('audio_file', type=str, help='Path to MP3/FLAC audio file')
    parser.add_argument('arduino_port', type=str, help='Serial port for Arduino communication (e.g., COM3, /dev/ttyUSB0)')
    parser.add_argument('--arduino-baud', type=int, default=9600,
                        help='Baud rate for Arduino communication')
    parser.add_argument('--threshold', type=float, default=0.40,
                        help='Amplitude threshold for bass detection (0.0-1.0)')
    parser.add_argument('--cutoff-freq', type=int, default=200,
                        help='Cutoff frequency for bass detection in Hz')
    parser.add_argument('--duration', type=float, default=None,
                        help='Duration in seconds to analyze (default: entire file)')
    
    args = parser.parse_args()
    
    # Step 1: Analyze the audio file to find bass onsets
    bass_onsets, sample_rate = analyze_bass_onsets(
        audio_file=args.audio_file,
        amplitude_threshold=args.threshold,
        cutoff_freq=args.cutoff_freq,
        duration=args.duration
    )
    key = detect_key(y,sr)
    colour = map_lighting(key)
    
    # Step 2: Play the audio and synchronize LED flashes
    play_audio_and_sync_leds(
        audio_file=args.audio_file,
        arduino_port=args.arduino_port,
        bass_onsets=bass_onsets,
        arduino_baud=args.arduino_baud,
        colour
    )
def detect_key(y, sr):
    # Compute the Chroma Short-Time Fourier Transform (chroma_stft) 
    chromagram = librosa.feature.chroma_stft(y=y, sr=sr)

    # Calculate the mean chroma feature across time
    mean_chroma = np.mean(chromagram, axis=1)

    # Define the mapping of chroma indices to note names
    notes = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

    #notes_major = {'C#':-4, 'G#':-5, 'B':-4, 'F':-3, 'D#':-2, 'E':-1, 'F#':3, 'C':4, 'G':4, 'A#':4, 'D':5, 'A':5]
    #notes_minor = {'C#':-5, 'D#':-4, 'F':-4, 'G#':-4, 'A#': -4,'F#':-3, 'B':-3, 'G':-2, 'A':-1, 'D':0, 'E':0, 'C':1]
    notes_major = {'C#':1, 'G#':0, 'B':1, 'F':2, 'D#':3, 'E':4, 'F#':7, 'C':8, 'G':8, 'A#':8, 'D':9, 'A':9]
    notes_minor = {'C#':0, 'D#':1, 'F':1, 'G#':1, 'A#':1,'F#':2, 'B':2, 'G':3, 'A':4, 'D':5, 'E':5, 'C':6]
    
                   
    # Krumhansl-Schmuckler key profiles for major and minor keys
    major_profile = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
    minor_profile = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])

    # Normalize the profiles
    major_profile = major_profile / np.sum(major_profile)
    minor_profile = minor_profile / np.sum(minor_profile)

    # Prepare to store the best correlation values and associated key/mode
    best_corr = -np.inf
    detected_key = None
    detected_mode = None

    # Iterate through each of the 12 possible tonics
    for i in range(12):
        # Rotate the profiles so the candidate tonic aligns with the first element
        major_rotated = np.roll(major_profile, i)
        minor_rotated = np.roll(minor_profile, i)
    
        # Compute the similarity (dot product) between mean_chroma and each profile
        corr_major = np.dot(mean_chroma, major_rotated)
        corr_minor = np.dot(mean_chroma, minor_rotated)
    
        # Check if this major candidate is the best so far
        if corr_major > best_corr:
            best_corr = corr_major
            detected_key = notes[i]
            detected_mode = "Major"

            detected_key = notes_major[detected_key]
    
        # Check if this minor candidate is the best so far
        if corr_minor > best_corr:
            best_corr = corr_minor
            detected_key = notes[i]
            detected_mode = "Minor"

            detected_key = notes_minor[detected_key]

    
    return detected_key
    print(f"Detected Key: {detected_key} {detected_mode}")

def map_lighting(key):
    colour_to_output = {
        "red": [256, 0, 0], 
        "green": [0, 256, 0], 
        "blue": [0, 0, 256], 
        "yellow": [256, 256, 0], 
        "cyan": [0, 256, 256], 
        "magenta": [256, 0, 256], 
        "orange": [256, 128, 0], 
        "purple": [128, 0, 256], 
        "pink": [256, 128, 192], 
        "white": [256, 256, 256]}

    #change as required this current mapping is arbitary
    key_to_light = {
        0:"red",
        1:"green",
        2:"blue",
        3:"yellow",
        4:"cyan",
        5:"magenta", 
        6:"orange",
        7:"purple",
        8:"pink",
        9:"white"}

    output_colour = colour_to_output[key_to_light[key]]
    return output colour
