import essentia.standard as es

def detect_mode_key(audio_chunk):
    """Detect mode and key from an audio chunk (5 seconds)."""
    key_extractor = es.KeyExtractor()
    key, scale, _ = key_extractor(audio_chunk)
    mode = 'minor' if 'minor' in scale.lower() else 'major'
    return mode, key
