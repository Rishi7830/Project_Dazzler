import librosa
import numpy as np
import sounddevice as sd
import time

def analyze_audio(duration=5, sample_rate=44100):
    """
    Records audio from the microphone, analyzes it, and returns key, amplitude, octave, and tempo.

    Args:
        duration (int): Recording duration in seconds.
        sample_rate (int): Sample rate of the audio.

    Returns:
        tuple: (key, amplitude, octave, tempo) or None if analysis fails.
    """
    try:
        print(f"Recording for {duration} seconds...")
        audio_data = sd.rec(int(duration * sample_rate), samplerate=sample_rate, channels=1, dtype=np.float32)
        sd.wait()  # Wait for recording to finish
        audio_data = audio_data.flatten()  # Flatten to 1D array

        # Key Estimation (using Tonnetz features)
        chroma = librosa.feature.chroma_cqt(y=audio_data, sr=sample_rate)
        tonnetz = librosa.feature.tonnetz(y=audio_data, sr=sample_rate)
        key = np.argmax(tonnetz.mean(axis=1))  # Rough key estimation

        # Amplitude (RMS)
        amplitude = librosa.feature.rms(y=audio_data)
        amplitude_db = librosa.amplitude_to_db([amplitude], ref=np.max)  # Convert to dB

        # Octave (Rough estimate using spectral centroid)
        spectral_centroid = librosa.feature.spectral_centroid(y=audio_data, sr=sample_rate)[0].mean()
        if spectral_centroid > 0:
            octave = round(np.log2(spectral_centroid / 440) + 4)  # Ensure no math errors
        else:
            octave = 0  # Default if centroid is too low

        # Tempo (BPM)
        tempo, beats = librosa.beat.beat_track(y=audio_data, sr=sample_rate)

        return key, amplitude_db, octave, tempo, beats

    except Exception as e:
        print(f"Error during analysis: {e}")
        return None

if __name__ == "__main__":
    analysis_result = analyze_audio()

    if analysis_result:
        key, amplitude_db, octave, tempo, beats = analysis_result
        print(f"Key Estimate: {key}")
        print(f"Amplitude (dB):", amplitude_db)
        print(f"Octave: {octave}")
        print(f"Tempo (BPM): {float(tempo):.2f}")
        print(f"Beat Frames:", beats)
