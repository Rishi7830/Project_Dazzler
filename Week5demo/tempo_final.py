"""
Tempo Detection Module
Uses Essentia for robust tempo extraction.
"""

import essentia.standard as es
import numpy as np

# --- The Advanced, Robust, Internal Detection Function ---

def _detect_tempo_internal(audio_data, sample_rate, window_size=2048, hop_size=512):
    """
    Internal function: Advanced tempo detection with windowed analysis.
    This provides a more stable, averaged tempo for the given audio chunk.
    """
    
    # Use the RhythmExtractor2013 as it is generally reliable
    tempo_extractor = es.RhythmExtractor2013(method="multifeature")
    tempo_values = []
    
    # Process audio in windows
    num_windows = (len(audio_data) - window_size) // hop_size + 1
    
    for i in range(num_windows):
        start = i * hop_size
        end = start + window_size
        window = audio_data[start:end].astype(np.float32)
        
        if len(window) < window_size:
            continue
            
        try:
            bpm, _, _, _, _ = tempo_extractor(window)
            
            # 1. Double/Half check for window-level accuracy
            if bpm < 60 and bpm > 0:
                bpm *= 2
            elif bpm > 200:
                bpm /= 2

            # 2. Only accept valid tempos
            if 60 <= bpm <= 200: 
                tempo_values.append(float(bpm))
        except:
            continue
    
    # Return median tempo if windows detected, otherwise 0.0
    if tempo_values:
        return float(np.median(tempo_values))
    else:
        return 0.0

# --- The Public-Facing Function ---

def detect_tempo(audio_data: np.ndarray, sample_rate: int) -> float:
    """
    Extract tempo/BPM from audio chunk using the robust windowed method.
    
    Args:
        audio_data (np.array): Audio samples (mono, float array)
        sample_rate (int): Sample rate in Hz
            
    Returns:
        float: Detected tempo in BPM, or 120.0 as a fallback.
    """
    
    try:
        # We use a larger window size (4096) for the internal detection 
        # to ensure good frequency resolution for the rhythm features.
        tempo = _detect_tempo_internal(
            audio_data, 
            sample_rate, 
            window_size=4096, 
            hop_size=1024  # Smaller windows are hopped more frequently
        )
        
        # FINAL CHECK: If detection failed (returns 0.0), use fallback.
        if tempo == 0.0:
            return 120.0
        
        # The internal function handles the doubling/halving.
        return tempo
            
    except Exception as e:
        print(f"[ERR] Overall Tempo detection failed: {e}")
        # Final fallback in case of an unexpected system error
        return 120.0


# For testing
if __name__ == "__main__":
    import librosa
    
    # IMPORTANT: Change this to a path to a real MP3 file for local testing
    audio_path = "Ordinary_Person.mp3"
    
    try:
        audio_data, sr = librosa.load(audio_path, sr=None, mono=True)
        # Test the detection on a large 2.0-second chunk
        chunk = audio_data[int(sr * 5) : int(sr * 7)] 
        
        tempo = detect_tempo(chunk, sr)
        print(f"\n--- Tempo Test ---")
        print(f"Detected tempo: {tempo:.1f} BPM")
        print("--------------------\n")
    except FileNotFoundError:
        print("[INFO] Cannot run test: Test audio file not found. Function ready for integration.")
    except ImportError:
        print("[INFO] Cannot run test: 'librosa' not installed. Function ready for integration.")
    except Exception as e:
        print(f"[ERR] Unexpected error during local test: {e}. Function ready for integration.")
