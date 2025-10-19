"""
Tempo Detection Module
"""

import essentia.standard as es
import numpy as np

def detect_tempo(audio_data, sample_rate):
    """
    Extract tempo/BPM from audio chunk using Essentia
    
    Args:
        audio_data (np.array): Audio samples (mono)
        sample_rate (int): Sample rate in Hz
        
    Returns:
        float: Detected tempo in BPM
    """
    
    # Initialize Essentia tempo extractor
    tempo_extractor = es.RhythmExtractor2013(method="multifeature")
    
    try:
        # Extract tempo using Essentia
        bpm, beats, beats_confidence, _, _ = tempo_extractor(audio_data.astype(np.float32))
        tempo = float(bpm)
        
        # Validate tempo range (typical music: 60-200 BPM)
        if tempo < 60:
            tempo = tempo * 2  # Double if too slow
        elif tempo > 200:
            tempo = tempo / 2  # Halve if too fast
            
    except Exception as e:
        print(f"Tempo detection error: {e}")
        # Fallback: return default tempo
        tempo = 120.0
    
    return tempo

def detect_tempo_advanced(audio_data, sample_rate, window_size=2048, hop_size=512):
    """
    Advanced tempo detection with windowed analysis
    
    Args:
        audio_data (np.array): Audio samples (mono)
        sample_rate (int): Sample rate in Hz
        window_size (int): Analysis window size
        hop_size (int): Hop between windows
        
    Returns:
        float: Average detected tempo across windows
    """
    
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
            if 60 <= bpm <= 200:  # Valid tempo range
                tempo_values.append(float(bpm))
        except:
            continue
    
    # Return median tempo if windows detected, else fallback
    if tempo_values:
        return float(np.median(tempo_values))
    else:
        return 120.0

# For testing
if __name__ == "__main__":
    import librosa
    
    # Test with a sample file
    audio_path = "test_audio.mp3"
    try:
        audio_data, sr = librosa.load(audio_path, sr=None, mono=True)
        tempo = detect_tempo(audio_data, sr)
        print(f"Detected tempo: {tempo:.1f} BPM")
    except:
        print("No test file found. Function ready for integration.")
