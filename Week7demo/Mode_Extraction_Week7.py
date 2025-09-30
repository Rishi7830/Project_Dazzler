import essentia.standard as es

def detect_mode_key(audio_buffer):
    """
    Returns mode ("major"/"minor") and key (e.g., "C") from an audio buffer.
    """
    key_extractor = es.KeyExtractor()
    try:
        key, scale, _ = key_extractor(audio_buffer)
        mode = "minor" if "minor" in scale.lower() else "major"
        key = key if key else "C"  # Default
    except Exception:
        mode, key = "major", "C"  # Fallback
    return mode, key
