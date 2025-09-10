import librosa
import numpy as np

# Load the audio file
audio_file_path = 'scom.mp3'
y, sr = librosa.load(audio_file_path, sr=None)

tempo,_ = librosa.beat.beat_track(y=y, sr=sr)

print (tempo)
