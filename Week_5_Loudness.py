"""
Loudness Detection for our Week 5 demo
"""
import numpy as np
import librosa
import essentia.standard as es

def detect_loudness(audio_data, sample_rate, window_size=2048, hop_size=512):
    """
    Extract loudness from audio using Essentia
    
    Args:
        audio_data (np.array): Audio samples
        sample_rate (int): Sample rate in Hz
        window_size (int): Analysis window size
        hop_size (int): Hop between windows
    
    Returns:
        list: Loudness values for each window
    """
    
    # Initialize Essentia loudness extractor
    loudness_extractor = es.Loudness()
    
    loudness_values = []
    
    # Process audio in windows
    num_windows = (len(audio_data) - window_size) // hop_size + 1
    
    for i in range(num_windows):
        start = i * hop_size
        end = start + window_size
        window = audio_data[start:end].astype(np.float32)
        
        # Extract loudness for this window
        try:
            loudness = float(loudness_extractor(window))
        except:
            # Fallback calculation if Essentia fails
            rms = np.sqrt(np.mean(window**2))
            loudness = float(20 * np.log10(max(1e-9, rms)))
        
        loudness_values.append(loudness)
        
        # Optional: Print each window's result
        time_sec = start / sample_rate
        print(f"Window {i+1}: Time {time_sec:.2f}s, Loudness = {loudness:.3f} dB")
    
    return loudness_values

# Example usage for your pipeline
def process_mp3_loudness(mp3_path):
    """
    Process an MP3 file and return loudness values
    """
    # Load audio file
    audio_data, sample_rate = librosa.load(mp3_path, sr=None, mono=True)
    
    print(f"Processing {mp3_path}")
    print(f"Duration: {len(audio_data)/sample_rate:.2f} seconds")
    
    # Extract loudness
    loudness_values = detect_loudness(audio_data, sample_rate)
    
    print(f"Extracted {len(loudness_values)} loudness values")
    return loudness_values

# For your parallel processing pipeline
def detect_loudness_simple(audio_chunk, sample_rate):
    """
    Simplified function for parallel processing
    Returns average loudness of the audio chunk
    """
    loudness_extractor = es.Loudness()
    
    try:
        loudness = float(loudness_extractor(audio_chunk.astype(np.float32)))
    except:
        # Fallback calculation
        rms = np.sqrt(np.mean(audio_chunk**2))
        loudness = float(20 * np.log10(max(1e-9, rms)))
    
    return loudness

# Test the function
if __name__ == "__main__":
    mp3_file = "your_audio.mp3"  # Replace with your file
    loudness_values = process_mp3_loudness(mp3_file)
    
    print(f"Average loudness: {np.mean(loudness_values):.3f} dB")
    print(f"Max loudness: {np.max(loudness_values):.3f} dB")
    print(f"Min loudness: {np.min(loudness_values):.3f} dB")

