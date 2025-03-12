import librosa
import numpy as np
import sounddevice as sd
import time

def analyze_audio(duration = 10, sample_rate=none):

    try: print(f"Recording for {duration} seconds...")
    # Load the audio file
        audio_file_path = 'scom.mp3' #change this to the file path u want for test
        y, sr = librosa.load(audio_file_path, sr=None)
        
        #cKey detection: 1 of our axis
        key = detect_key(y, sr)

        # Amplitude (RMS)
        amplitude = librosa.feature.rms(y=audio_data)
        amplitude_db = librosa.amplitude_to_db([amplitude], ref=np.max)  # Convert to dB

        # Tempo (BPM)
        tempo, beats = librosa.beat.beat_track(y=audio_data, sr=sample_rate)

        return key, amplitude_db, tempo, beats

    except Exception as e:
        print(f"Error during analysis: {e}")
        return None

def detect_key(y, sr):
    # Compute the Chroma Short-Time Fourier Transform (chroma_stft) 
    chromagram = librosa.feature.chroma_stft(y=y, sr=sr)

    # Calculate the mean chroma feature across time
    mean_chroma = np.mean(chromagram, axis=1)

    # Define the mapping of chroma indices to note names
    notes = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

    #notes_major = {'C#':-4, 'G#':-5, 'B':-4, 'F':-3, 'D#':-2, 'E':-1, 'F#':3, 'C':4, 'G':4, 'A#':4, 'D':5, 'A':5]
    #notes_minor = {'C#':-5, 'D#':-4, 'F':-4, 'G#':-4, 'A#': -4,'F#':-3, 'B':-3, 'G':-2, 'A':-1, 'D':0, 'E':0, 'C':1]
    notes_major = {'C#':1, 'G#':0, 'B':1, 'F':2, 'D#':3, 'E':4, 'F#':7, 'C':8, 'G':8, 'A#':8, 'D':9, 'A':9]
    notes_minor = {'C#':0, 'D#':1, 'F':1, 'G#':1, 'A#':1,'F#':2, 'B':2, 'G':3, 'A':4, 'D':5, 'E':5, 'C':6]
    
                   
    # Krumhansl-Schmuckler key profiles for major and minor keys
    major_profile = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
    minor_profile = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])

    # Normalize the profiles
    major_profile = major_profile / np.sum(major_profile)
    minor_profile = minor_profile / np.sum(minor_profile)

    # Prepare to store the best correlation values and associated key/mode
    best_corr = -np.inf
    detected_key = None
    detected_mode = None

    # Iterate through each of the 12 possible tonics
    for i in range(12):
        # Rotate the profiles so the candidate tonic aligns with the first element
        major_rotated = np.roll(major_profile, i)
        minor_rotated = np.roll(minor_profile, i)
    
        # Compute the similarity (dot product) between mean_chroma and each profile
        corr_major = np.dot(mean_chroma, major_rotated)
        corr_minor = np.dot(mean_chroma, minor_rotated)
    
        # Check if this major candidate is the best so far
        if corr_major > best_corr:
            best_corr = corr_major
            detected_key = notes[i]
            detected_mode = "Major"

            detected_key = notes_major[detected_key]
    
        # Check if this minor candidate is the best so far
        if corr_minor > best_corr:
            best_corr = corr_minor
            detected_key = notes[i]
            detected_mode = "Minor"

            detected_key = notes_minor[detected_key]

    
    return detected_key
    print(f"Detected Key: {detected_key} {detected_mode}")

def map_lighting(key, amplitude_db, tempo, beats)
    colour_to_output = {
        "red": [256, 0, 0], 
        "green": [0, 256, 0], 
        "blue": [0, 0, 256], 
        "yellow": [256, 256, 0], 
        "cyan": [0, 256, 256], 
        "magenta": [256, 0, 256], 
        "orange": [256, 128, 0], 
        "purple": [128, 0, 256], 
        "pink": [256, 128, 192], 
        "white": [256, 256, 256]}

    #change as required this current mapping is arbitary
    key_to_light = {
        0:"red" 
        1:"green"
        2:"blue"
        3:"yellow"
        4:"cyan"
        5:"magenta" 
        6:"orange" 
        7:"purple" 
        8:"pink"
        9:"white"}

    output_colour = colour_to_output[key_to_light[key]]
    return output colour
