import essentia.standard as es

def detect_loudness(audio_buffer):
    """
    Returns loudness in dB from an audio buffer.
    """
    loudness_extractor = es.Loudness()
    try:
        loudness = loudness_extractor(audio_buffer)
    except Exception:
        loudness = -60.0  # Quiet fallback
    return loudness
