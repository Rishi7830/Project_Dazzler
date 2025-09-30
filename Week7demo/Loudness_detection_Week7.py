import essentia.standard as es

def detect_loudness(audio_chunk):
    """Detect loudness (dB) from an audio chunk (e.g., 5 seconds)."""
    loudness_extractor = es.Loudness()
    loudness = loudness_extractor(audio_chunk)
    return loudness
