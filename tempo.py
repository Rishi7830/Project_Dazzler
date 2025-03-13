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

def led_control_thread(arduino, bass_onsets, start_time):
    """Thread function to control LED timing based on detected bass onsets"""
    print("LED control thread started")
    onset_index = 0
    
    while onset_index < len(bass_onsets):
        current_time = time.time() - start_time
        
        # Check if we need to trigger the next onset
        if onset_index < len(bass_onsets) and current_time >= bass_onsets[onset_index]:
            arduino.write(b'1')
            print(f"LED flash at {current_time:.2f}s (onset #{onset_index+1})")
            onset_index += 1
        
        # Small sleep to avoid consuming too much CPU
        time.sleep(0.001)
    
    print("LED control thread completed")

def play_audio_and_sync_leds(audio_file, arduino_port, bass_onsets, arduino_baud=9600):
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
                                     args=(arduino, bass_onsets, start_time))
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
    
    # Step 2: Play the audio and synchronize LED flashes
    play_audio_and_sync_leds(
        audio_file=args.audio_file,
        arduino_port=args.arduino_port,
        bass_onsets=bass_onsets,
        arduino_baud=args.arduino_baud
    )
