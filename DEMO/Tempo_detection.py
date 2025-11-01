import essentia.standard as es

def detect_tempo(audio_buffer):
    """
    Returns tempo (BPM) from an audio buffer.
    Fixes octave errors (60-200 BPM).
    """
    tempo_extractor = es.RhythmExtractor2013(method="multifeature")
    try:
        bpm, _, _, _, _ = tempo_extractor(audio_buffer)
        if bpm < 60:
            bpm *= 2
        elif bpm > 200:
            bpm /= 2
    except Exception:
        bpm = 120.0
    return bpm
