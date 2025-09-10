"""
Mode and Key Detection Module
Uses Essentia for musical key and mode extraction from audio chunks
"""

import essentia.standard as es
import numpy as np

def detect_mode_key(audio_data, sample_rate):
    """
    Extract musical mode and key from audio chunk using Essentia
    
    Args:
        audio_data (np.array): Audio samples (mono)
        sample_rate (int): Sample rate in Hz
        
    Returns:
        tuple: (mode, key) e.g., ("major", "C")
    """
    
    # Initialize Essentia key extractor
    key_extractor = es.KeyExtractor()
    
    try:
        # Extract key and scale using Essentia
        key, scale, strength = key_extractor(audio_data.astype(np.float32))
        
        # Clean up the results
        mode = scale.lower() if scale else "major"  # Default to major
        detected_key = key if key else "C"  # Default to C
        
        # Map common scale names to mode
        if "minor" in mode:
            mode = "minor"
        else:
            mode = "major"
            
    except Exception as e:
        print(f"Mode/Key detection error: {e}")
        # Fallback to defaults
        mode = "major"
        detected_key = "C"
    
    return mode, detected_key

def detect_mode_key_windowed(audio_data, sample_rate, window_size=8192, hop_size=4096):
    """
    Advanced mode/key detection with windowed analysis
    Uses larger windows as key detection needs more context
    
    Args:
        audio_data (np.array): Audio samples (mono)
        sample_rate (int): Sample rate in Hz
        window_size (int): Analysis window size (larger for key detection)
        hop_size (int): Hop between windows
        
    Returns:
        tuple: (mode, key) - most common detected across windows
    """
    
    key_extractor = es.KeyExtractor()
    key_detections = []
    mode_detections = []
    
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
            key, scale, strength = key_extractor(window)
            
            if strength > 0.5:  # Only accept confident detections
                key_detections.append(key)
                if "minor" in scale.lower():
                    mode_detections.append("minor")
                else:
                    mode_detections.append("major")
                    
        except:
            continue
    
    # Find most common key and mode
    if key_detections and mode_detections:
        # Most common key
        unique_keys, counts = np.unique(key_detections, return_counts=True)
        most_common_key = unique_keys[np.argmax(counts)]
        
        # Most common mode
        unique_modes, counts = np.unique(mode_detections, return_counts=True)
        most_common_mode = unique_modes[np.argmax(counts)]
        
        return most_common_mode, most_common_key
    else:
        return "major", "C"  # Fallback

def get_key_number(key_name):
    """
    Convert key name to number for easier processing
    
    Args:
        key_name (str): Key name like "C", "F#", etc.
        
    Returns:
        int: Key number (0-11)
    """
    
    key_map = {
        "C": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3,
        "E": 4, "F": 5, "F#": 6, "Gb": 6, "G": 7, "G#": 8,
        "Ab": 8, "A": 9, "A#": 10, "Bb": 10, "B": 11
    }
    
    return key_map.get(key_name, 0)  # Default to C (0)

def get_mode_brightness(mode):
    """
    Get relative brightness/darkness of mode for color mapping
    
    Args:
        mode (str): Mode name ("major" or "minor")
        
    Returns:
        float: Brightness value (0.0-1.0)
    """
    
    if mode.lower() == "major":
        return 0.8  # Bright
    elif mode.lower() == "minor":
        return 0.4  # Dark
    else:
        return 0.6  # Neutral

def detect_advanced_mode_key(audio_data, sample_rate):
    """
    Advanced detection with additional musical features
    
    Args:
        audio_data (np.array): Audio samples (mono)
        sample_rate (int): Sample rate in Hz
        
    Returns:
        dict: Extended results with confidence and features
    """
    
    key_extractor = es.KeyExtractor()
    
    try:
        key, scale, strength = key_extractor(audio_data.astype(np.float32))
        
        mode = "minor" if "minor" in scale.lower() else "major"
        key_num = get_key_number(key)
        brightness = get_mode_brightness(mode)
        
        return {
            "mode": mode,
            "key": key,
            "key_number": key_num,
            "brightness": brightness,
            "confidence": float(strength)
        }
        
    except Exception as e:
        print(f"Advanced mode/key detection error: {e}")
        return {
            "mode": "major",
            "key": "C",
            "key_number": 0,
            "brightness": 0.6,
            "confidence": 0.0
        }

# For testing
if __name__ == "__main__":
    import librosa
    
    # Test with a sample file
    audio_path = "test_audio.mp3"
    try:
        audio_data, sr = librosa.load(audio_path, sr=None, mono=True)
        mode, key = detect_mode_key(audio_data, sr)
        advanced_results = detect_advanced_mode_key(audio_data, sr)
        print(f"Detected: {key} {mode}")
        print(f"Advanced results: {advanced_results}")
    except:
        print("No test file found. Function ready for integration.")
