import essentia.standard as es

def detect_tempo(audio_chunk):
    """Detect tempo (BPM) from an audio chunk (e.g., 5 seconds)."""
    tempo_extractor = es.RhythmExtractor2013(method='multifeature')
    bpm, _, confidence, _, _ = tempo_extractor(audio_chunk)
    # Fix octave errors as in your code
    if bpm < 60:
        bpm *= 2
    elif bpm > 200:
        bpm /= 2
    return bpm, confidence
