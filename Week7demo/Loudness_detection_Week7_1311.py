import numpy as np
import librosa

def detect_loudness(audio_buffer):
    """
    Returns chunk-wise average loudness in dB (RMS method).
    Uses librosa for more robust and accurate calculation.
    """
    # Calculate RMS energy
    rms = librosa.feature.rms(y=audio_buffer)[0]
    
    # Convert to dB, with a minimum threshold for silence
    db = librosa.amplitude_to_db(rms, ref=np.max)
    
    # Return the average dB for the chunk
    return np.mean(db)
