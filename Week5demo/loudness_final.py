"""
Loudness Detection Module (RMS-based)
Uses NumPy/Math for highly reliable Loudness detection in dBFS.
"""

import numpy as np
import math

def detect_loudness(audio_data: np.ndarray, sample_rate: int) -> float:
    """
    Detects loudness using the Root Mean Square (RMS) and converts it to dBFS.
    
    This function will produce standard negative dB values (e.g., -60.0 to 0.0) 
    which are essential for mapping to light intensity/brightness accurately.
    
    Args:
        audio_data (np.array): Audio samples (mono, float array, typically -1.0 to 1.0)
        sample_rate (int): Sample rate in Hz (not used in this specific calculation, but kept for signature)
        
    Returns:
        float: RMS loudness in dBFS
    """
    
    try:
        # 1. Calculate the Root Mean Square (RMS)
        # This gives us a single value representing the overall 'energy' of the audio chunk.
        rms = np.sqrt(np.mean(audio_data**2))
        
        # 2. Convert RMS to dBFS (Decibels Full Scale)
        # 20 * log10(Amplitude) is the formula for power/voltage ratios.
        # max(1e-9, rms) is used to prevent math.log10(0) if the audio is completely silent.
        loudness_db = float(20 * math.log10(max(1e-9, rms)))
        
    except Exception as e:
        # Fallback for unexpected math or data type errors
        print(f"[ERR] RMS loudness calculation error: {e}")
        loudness_db = -60.0 # Safe fallback: corresponds to 'very quiet'
        
    return loudness_db

# --- Optional/Supporting Functions (kept for context, but not called by main.py) ---

def get_loudness_category(loudness_db: float) -> str:
    """Categorize loudness level for easier interpretation."""
    if loudness_db < -40:
        return 'quiet'
    elif loudness_db < -20:
        return 'moderate'
    elif loudness_db < -10:
        return 'loud'
    else:
        return 'very_loud'

# For testing (requires librosa)
if __name__ == "__main__":
    try:
        import librosa
        # IMPORTANT: Change this to a path to a real MP3 file for local testing
        audio_path = "Ordinary_Person.mp3" 
        
        audio_data, sr = librosa.load(audio_path, sr=None, mono=True)
        # Test the detection on a loud 2.0-second chunk (5s to 7s)
        chunk = audio_data[int(sr * 5) : int(sr * 7)] 
        
        loudness = detect_loudness(chunk, sr)
        category = get_loudness_category(loudness)
        print(f"\n--- Loudness Test ---")
        print(f"Test Chunk Loudness: {loudness:.2f} dB ({category})")
        
        # Check an empty/silent chunk
        silent_chunk = np.zeros(sr, dtype=np.float32)
        silent_loudness = detect_loudness(silent_chunk, sr)
        print(f"Silent Chunk Loudness: {silent_loudness:.2f} dB ({get_loudness_category(silent_loudness)})")
        print("---------------------\n")
        
    except FileNotFoundError:
        print("[INFO] Cannot run test: 'Ordinary_Person.mp3' not found. Function ready for integration.")
    except ImportError:
        print("[INFO] Cannot run test: 'librosa' not installed. Function ready for integration.")
    except Exception as e:
        print(f"[ERR] Unexpected error during local test: {e}. Function ready for integration.")
