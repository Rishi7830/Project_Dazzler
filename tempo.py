import librosa
import librosa.display
import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import butter, filtfilt

def analyze_audio(audio_file_path, amplitude_threshold=0.40, duration=180):
    """
    Analyze bass onsets in an audio file and output graphs and onset timings.
    
    Parameters:
    -----------
    audio_file_path : str
        Path to the audio file
    amplitude_threshold : float
        Amplitude threshold for bass detection (default: 0.40)
    duration : int
        Duration in seconds to analyze (default: 180 seconds / 3 minutes)
    """
    print(f"Loading audio file: {audio_file_path}")
    
    # Load the audio file
    y, sr = librosa.load(audio_file_path, sr=None, duration=duration)
    
    # Get file duration
    actual_duration = librosa.get_duration(y=y, sr=sr)
    print(f"Analyzing {actual_duration:.2f} seconds of audio")
    
    # Calculate BPM using librosa's beat tracking
    tempo, beats = librosa.beat.beat_track(y=y, sr=sr)
    beat_times = librosa.frames_to_time(beats, sr=sr)
    
    # Ensure tempo is a scalar value
    if isinstance(tempo, np.ndarray):
        tempo = float(tempo[0])  # Take the first value if it's an array
    
    print(f"Estimated BPM (librosa): {tempo:.1f}")
    
    # Apply low-pass filter to isolate bass frequencies
    cutoff_freq = 200  # Hz
    nyquist = sr / 2
    filter_order = 8
    normal_cutoff = cutoff_freq / nyquist
    
    b, a = butter(filter_order, normal_cutoff, btype='low')
    y_bass = filtfilt(b, a, y)
    
    # Normalize the bass waveform
    max_val = np.max(np.abs(y_bass))
    if max_val > 0:
        y_bass_norm = y_bass / max_val
    else:
        y_bass_norm = y_bass
    
    # Find bass onset points (rising edges crossing threshold)
    onset_indices = []
    for i in range(1, len(y_bass_norm)):
        if np.abs(y_bass_norm[i]) >= amplitude_threshold and np.abs(y_bass_norm[i-1]) < amplitude_threshold:
            onset_indices.append(i)
    
    # Convert indices to timestamps
    onset_times = [(idx / sr) for idx in onset_indices]
    
    print(f"Detected {len(onset_times)} bass onsets")
    
    # Initialize bass_bpm variable
    bass_bpm = None
    
    # # Calculate bass onset BPM (if we have at least 2 onsets)
    # if len(onset_times) > 1:
    #     intervals = np.diff(onset_times)
    #     avg_interval = np.mean(intervals)
    #     bass_bpm = 60 / avg_interval if avg_interval > 0 else 0
    #     print(f"Estimated BPM (bass onsets): {bass_bpm:.1f}")
    
    # # Create visualization
    # plt.figure(figsize=(15, 10))
    
    # # Plot 1: Original waveform
    # plt.subplot(3, 1, 1)
    # times = np.linspace(0, actual_duration, len(y))
    # plt.plot(times, y, alpha=0.6)
    # plt.title('Original Waveform')
    # plt.xlim(0, actual_duration)
    
    # # Mark detected onsets
    # for onset in onset_times:
    #     plt.axvline(x=onset, color='r', linestyle='--', alpha=0.7)
    
    # # Plot 2: Bass waveform with threshold lines
    # plt.subplot(3, 1, 2)
    # bass_times = np.linspace(0, actual_duration, len(y_bass_norm))
    # plt.plot(bass_times, y_bass_norm, color='b', alpha=0.7, label='Bass Waveform')
    
    # # Add threshold lines
    # plt.axhline(y=amplitude_threshold, color='r', linestyle='-', alpha=0.5, label=f'+Threshold ({amplitude_threshold})')
    # plt.axhline(y=-amplitude_threshold, color='r', linestyle='-', alpha=0.5, label=f'-Threshold ({-amplitude_threshold})')
    
    # # Mark onset points
    # for onset in onset_times:
    #     plt.axvline(x=onset, color='g', linestyle='-', alpha=0.7)
    
    # plt.title(f'Bass Frequencies (Threshold = {amplitude_threshold})')
    # plt.legend()
    # plt.ylim(-1.1, 1.1)
    # plt.xlim(0, actual_duration)
    
    # # Plot 3: Absolute bass amplitude with threshold
    # plt.subplot(3, 1, 3)
    # plt.plot(bass_times, np.abs(y_bass_norm), color='k', alpha=0.7, label='Absolute Bass Amplitude')
    # plt.axhline(y=amplitude_threshold, color='r', linestyle='-', alpha=0.7, label=f'Threshold ({amplitude_threshold})')
    
    # # Mark onsets
    # for onset in onset_times:
    #     plt.axvline(x=onset, color='g', linestyle='-', alpha=0.7)
    
    # plt.title('Absolute Bass Amplitude')
    # plt.legend()
    # plt.xlim(0, actual_duration)
    # plt.ylim(0, 1.1)
    
    # plt.tight_layout()
    # output_filename = f"{audio_file_path.split('.')[0]}_analysis"
    # plt.savefig(f"{output_filename}.png", dpi=300)
    # plt.show()
    
    return {
        'onset_times': onset_times,
        'bpm_librosa': tempo,
        # 'bpm_bass_onsets': bass_bpm
    }

if __name__ == "__main__":
    # Change this to your audio file
    audio_file = "scom.mp3"
    
    try:
        # Analyze 3 minutes with amplitude threshold of 0.40
        results = analyze_audio(audio_file, amplitude_threshold=0.40, duration=180)
        
        # Print onset times array
        print("\nBass onset times (seconds):")
        print(results['onset_times'])
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"\nError analyzing audio: {e}")
        print("Make sure you have installed all dependencies: librosa, matplotlib, numpy, scipy")