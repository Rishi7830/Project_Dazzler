import essentia.standard as es
import numpy as np

def extract_rhythm(audio_buffer):
    """
    Returns rhythm regularity index (0–1: higher = more regular)
    and tempo (BPM) from an audio buffer.
    """
    tempo_extractor = es.RhythmExtractor2013(method="multifeature")
    try:
        bpm, _, confidence, _, _ = tempo_extractor(audio_buffer)
        # Fix octave errors
        if bpm < 60:
            bpm *= 2
        elif bpm > 200:
            bpm /= 2
        rhythm_index = np.clip(confidence, 0, 1)
    except Exception:
        bpm = 120.0
        rhythm_index = 0.0
    return rhythm_index
