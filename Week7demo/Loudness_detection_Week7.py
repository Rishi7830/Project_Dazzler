import numpy as np

def detect_loudness(audio_buffer):
    """
    Returns chunk-wise average loudness in dB (RMS method).
    """
    rms = np.sqrt(np.mean(audio_buffer ** 2))
    if rms > 0:
        loudness_db = 20 * np.log10(rms)
    else:
        loudness_db = -80.0  # Fallback for silence and errors
    return loudness_db
