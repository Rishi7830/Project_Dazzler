# tempo_detection.py

import essentia.standard as es

def detect_tempo(audio_buffer, sample_rate=44100): # Added sample_rate argument
    """
    Returns a dummy tempo (BPM) from a short audio buffer.
    (Real-time BPM on 0.25s chunks is unreliable; setting a fixed value to
     allow other features to drive hue_speed, or a better fallback.)
    """
    try:
        # Essentia's RhythmExtractor2013 on a 0.25s chunk will be highly unreliable or fail.
        # We will keep the call, but rely on the fallback.
        tempo_extractor = es.RhythmExtractor2013(method="multifeature")
        bpm, _, _, _, _ = tempo_extractor(audio_buffer)

        # The octave correction is sound, but only if BPM is detected.
        if bpm == 0:
             # If tempo is 0, it means detection failed on this chunk.
             raise ValueError("Tempo detection failed (returned 0)")
        if bpm < 60:
            bpm *= 2
        elif bpm > 200:
            bpm /= 2

    except Exception:
        # Fallback: Since tempo is unreliable, use a constant and let loudness/genre
        # logic in audio_analyzer.py drive the speed.
        # Setting a sensible default to keep tempo_to_hue_speed calculation in range.
        bpm = 128.0 # Use 128 as a non-zero, mid-range default
        
    return bpm
