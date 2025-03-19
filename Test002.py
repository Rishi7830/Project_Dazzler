import librosa 
import numpy as np

def get_amplitude(mp3_file):
    """Extracts and returns the amplitude of MP3 file."""
    y, sr = librosa.load(mp3_file, sr=None)  # Loads the mp3 file
    amplitude = librosa.feature.rms(y=y)
    amplitude_db = librosa.amplitude_to_db(amplitude, ref=np.max)  # Converts to dB
    return amplitude_db.mean()  # Return average amplitude

def analyze_audio(mp3_file):
    """Analyzes key, octave, and tempo of MP3 file."""
    try:
        y, sr = librosa.load(mp3_file, sr=None)  # Loads the MP3 file
        
        # Key
        tonnetz = librosa.feature.tonnetz(y=y, sr=sr)
        key = np.argmax(tonnetz.mean(axis=1))

        # Octave
        spectral_centroid = librosa.feature.spectral_centroid(y=y, sr=sr).mean()
        octave = round(np.log2(spectral_centroid / 440) + 4) if spectral_centroid > 0 else 0

        # Tempo
        tempo, beats = librosa.beat.beat_track(y=y, sr=sr)

        return key, octave, tempo, beats
    except Exception as e:
        print(f"Error: {e}")
        return None

if __name__ == "__main__":
    mp3_file = "your_audio.mp3"  # MP3 file path input :)
    amplitude = get_amplitude(mp3_file)
    analysis_result = analyze_audio(mp3_file)

    if analysis_result:
        key, octave, tempo, beats = analysis_result
        print(f"Key Estimate: {key}")
        print(f"Amplitude (dB): {amplitude:.2f}")
        print(f"Octave: {octave}")
        print(f"Tempo (BPM): {tempo:.2f}")
        print(f"Beat Frames:", beats)
