"""
Loudness Detection Module
Uses Essentia for loudness extraction from audio chunks
"""

import essentia.standard as es
import numpy as np
import math

def detect_loudness(audio_data, sample_rate):
    """
    Extract loudness from audio chunk using Essentia
    
    Args:
        audio_data (np.array): Audio samples (mono)
        sample_rate (int): Sample rate in Hz
        
    Returns:
        float: Detected loudness in dB
    """
    
    # Initialize Essentia extractors
    loudness_extractor = es.Loudness()
    
    try:
        # Extract loudness using Essentia
        loudness = float(loudness_extractor(audio_data.astype(np.float32)))
        
    except Exception as e:
        print(f"Loudness detection error: {e}")
        # Fallback calculation using RMS
        rms = np.sqrt(np.mean(audio_data**2))
        loudness = float(20 * math.log10(max(1e-9, rms)))
    
    return loudness

def detect_loudness_windowed(audio_data, sample_rate, window_size=2048, hop_size=512):
    """
    Advanced loudness detection with windowed analysis
    
    Args:
        audio_data (np.array): Audio samples (mono)
        sample_rate (int): Sample rate in Hz
        window_size (int): Analysis window size
        hop_size (int): Hop between windows
        
    Returns:
        float: Average loudness across windows in dB
    """
    
    loudness_extractor = es.Loudness()
    loudness_values = []
    
    # Process audio in windows
    num_windows = (len(audio_data) - window_size) // hop_size + 1
    
    for i in range(num_windows):
        start = i * hop_size
        end = start + window_size
        window = audio_data[start:end].astype(np.float32)
        
        if len(window) < window_size:
            # Pad window if too short
            window = np.pad(window, (0, window_size - len(window)), mode='constant')
        
        try:
            loudness = float(loudness_extractor(window))
            loudness_values.append(loudness)
        except:
            # Fallback calculation
            rms = np.sqrt(np.mean(window**2))
            loudness = float(20 * math.log10(max(1e-9, rms)))
            loudness_values.append(loudness)
    
    # Return average loudness
    if loudness_values:
        return float(np.mean(loudness_values))
    else:
        return -60.0  # Very quiet fallback

def detect_rms_loudness(audio_data, sample_rate):
    """
    Simple RMS-based loudness detection
    
    Args:
        audio_data (np.array): Audio samples (mono)
        sample_rate (int): Sample rate in Hz
        
    Returns:
        float: RMS loudness in dB
    """
    
    try:
        # Calculate RMS
        rms = np.sqrt(np.mean(audio_data**2))
        # Convert to dB
        loudness_db = float(20 * math.log10(max(1e-9, rms)))
        
    except Exception as e:
        print(f"RMS loudness error: {e}")
        loudness_db = -60.0  # Very quiet fallback
    
    return loudness_db

def get_loudness_category(loudness_db):
    """
    Categorize loudness level for easier interpretation
    
    Args:
        loudness_db (float): Loudness in dB
        
    Returns:
        str: Loudness category ('quiet', 'moderate', 'loud', 'very_loud')
    """
    
    if loudness_db < -40:
        return 'quiet'
    elif loudness_db < -20:
        return 'moderate'
    elif loudness_db < -10:
        return 'loud'
    else:
        return 'very_loud'

# For testing
if __name__ == "__main__":
    import librosa
    
    # Test with a sample file
    audio_path = "test_audio.mp3"
    try:
        audio_data, sr = librosa.load(audio_path, sr=None, mono=True)
        loudness = detect_loudness(audio_data, sr)
        category = get_loudness_category(loudness)
        print(f"Detected loudness: {loudness:.2f} dB ({category})")
    except:
        print("No test file found. Function ready for integration.")
