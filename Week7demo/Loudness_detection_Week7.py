import essentia.standard as es
import numpy as np

def detect_loudness(audio_buffer):
    print("Audio buffer min/max:", np.min(audio_buffer), np.max(audio_buffer)) #for debugging
    """
    Returns loudness in dB from an audio buffer.
    """
    loudness_extractor = es.Loudness()
    try:
        loudness = loudness_extractor(audio_buffer)
    except Exception:
        loudness = -60.0  # Quiet fallback

    print("Raw loudness:", loudness)
    if np.isnan(loudness) or loudness > 0 or loudness < -80:
        print("Anomalous loudness detected:", loudness)
        loudness = -30

    return loudness
