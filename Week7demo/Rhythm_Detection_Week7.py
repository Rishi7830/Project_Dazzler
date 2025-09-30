import essentia.standard as es
import numpy as np

def extract_rhythm(audio_chunk):
    """Extract rhythm features: tempo (BPM) and rhythm stability index."""
    tempo_extractor = es.RhythmExtractor2013(method='multifeature')
    bpm, _, confidence, _, _ = tempo_extractor(audio_chunk)
    # Fix octave errors
    if bpm < 60:
        bpm *= 2
    elif bpm > 200:
        bpm /= 2
    rhythm_index = np.clip(confidence, 0, 1)  # Confidence as rhythm regularity
    return bpm, rhythm_index
