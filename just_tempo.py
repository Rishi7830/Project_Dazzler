import librosa
import numpy as np

# Load the audio file
audio_file_path = 'scom.mp3'
y, sr = librosa.load(audio_file_path, sr=None)


