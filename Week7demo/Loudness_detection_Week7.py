import essentia.standard as es
import numpy as np

def detect_loudness(audio_buffer):
    """
    Returns loudness in dB from an audio buffer.
    """
    loudness_extractor = es.Loudness()
    try:
        loudness = loudness_extractor(audio_buffer)
        # Convert from Stevens' law (linear) to dB, safely handling zeros/negatives
        if loudness > 0:
            loudness_db = 10 * np.log10(loudness)
        else:
            loudness_db = -80.0  # Very quiet fallback
    except Exception:
        loudness_db = -80.0  # Quiet fallback for any failure
    # Optionally clip to sane dB range
    loudness_db = np.clip(loudness_db, -80, 0)
    return loudness_db
