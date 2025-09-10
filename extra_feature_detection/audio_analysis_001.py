import essentia.standard as es
import numpy as np
import matplotlib.pyplot as plt
import os

# --- 1. Configuration ---
# You can change these parameters to fit your needs.

# IMPORTANT: Replace this with the path to your audio file.
# The script includes a fallback to generate a simple test tone if the file is not found.
file_path = "believer.mp3" 

# Audio processing settings
sample_rate = 44100
window_size = 2048  # The size of the analysis window (in samples)
hop_size = 1024     # The step size between consecutive windows (in samples)

# --- 2. Audio Loading ---
# We use MonoLoader to load the audio file as a single-channel signal.

audio = None
if os.path.exists(file_path):
    print(f"Loading audio file: {file_path}")
    # Load the audio file. Essentia's loader normalizes it to [-1, 1]
    audio = es.MonoLoader(filename=file_path, sampleRate=sample_rate)()
else:
    print(f"Warning: Audio file not found at '{file_path}'.")
    print("Generating a 5-second 440Hz sine wave as a fallback.")
    # Generate a fallback audio signal if the file doesn't exist
    duration_seconds = 5
    frequency = 440  # A4 note
    audio = es.Sine(frequency=frequency, sampleRate=sample_rate)(duration_seconds * sample_rate)


# --- 3. Algorithm Initialization ---
# We instantiate all the Essentia algorithms we'll need. This is more efficient
# than creating them inside the loop.

# This algorithm splits the audio into overlapping frames (windows)
frame_generator = es.FrameGenerator(audio, frameSize=window_size, hopSize=hop_size, startFromZero=True)

# Windowing function to apply to each frame
window = es.Windowing(type='hann', zeroPadding=0)

# Computes the frequency spectrum of a windowed frame
spectrum = es.Spectrum()

# --- Feature Extractors ---

# Loudness (Dynamics)
# EBUR128 is a standard for perceived loudness measurement.
loudness_algo = es.Loudness()

# Spectral Centroid (Timbre/Brightness)
# The "center of mass" of the spectrum, indicating brightness.
centroid_algo = es.Centroid(range=sample_rate/2)

# Spectral Contrast (Timbre/Texture)
# Measures the difference between peaks and valleys in the spectrum.
contrast_algo = es.SpectralContrast(frameSize=window_size, sampleRate=sample_rate)

# Dissonance (Timbre/Dissonance)
# Measures the sensation of sensory dissonance.
# Finds the frequency and magnitude of the most prominent peaks in the spectrum.
spectral_peaks_algo = es.SpectralPeaks(sampleRate=sample_rate)

dissonance_algo = es.Dissonance()

# Tonal Features (Key/Mode)
# Extracts key, scale, and other tonal information.
tonal_algo = es.TonalExtractor()

# --- Global Feature Extraction (for features that need the whole signal) ---

# Rhythm/Tempo
# NOTE: RhythmExtractor2013 works on the entire audio signal. In a real-time
# scenario, you would use a streaming beat tracker like `BeatTrackerMultiFeature`
# which maintains state between frames. For this example, we calculate it once.
rhythm_algo = es.RhythmExtractor2013(method="multifeature")
# After (Line 82 in the updated file)
global_bpm, _, _, _, _ = rhythm_algo(audio)

print("-" * 30)
print("Global Feature Analysis (run once on the whole file):")
print(f"  - Overall BPM: {global_bpm:.2f}")
print("-" * 30)


# --- 4. Main Processing Loop ---
# We iterate through each frame provided by the FrameGenerator.

print("Starting windowed feature extraction...")
print(f"Window Size: {window_size} samples (~{window_size/sample_rate:.2f}s)")
print(f"Hop Size: {hop_size} samples (~{hop_size/sample_rate:.2f}s)")
print("-" * 30)


# This list will store the results for each frame
all_frame_features = []

for frame_count, frame in enumerate(frame_generator):
    # --- Per-Frame Feature Calculation ---
    
    # Get the spectrum for the current frame
    frame_spectrum = spectrum(window(frame))
    
    # --- Run algorithms ---
    # Note: Some algorithms take the time-domain frame, others take the spectrum.
    
    # Loudness (from frame)
    # LoudnessEBUR128 needs larger chunks to be accurate. We pass the frame
    # but it internally buffers to compute loudness over a larger time scale.
    # The result is a tuple, we are interested in integratedLoudness and loudnessRange
    loudness_val = loudness_algo(frame)

    # Spectral Centroid (from spectrum)
    centroid = centroid_algo(frame_spectrum)

    # Spectral Contrast (from spectrum)
    # Returns spectral_contrast and spectral_valley
    s_contrast, s_valley = contrast_algo(frame_spectrum)
    
    # Spectral Peaks (from spectrum) - needed for Dissonance
    peak_frequencies, peak_magnitudes = spectral_peaks_algo(frame_spectrum)


    # Dissonance (from spectrum)
    # Dissonance (from peaks) - It takes the peak frequencies and magnitudes as input
    dissonance_val = dissonance_algo(peak_frequencies, peak_magnitudes)
    
    # Tonal features (from spectrum)
    # This algorithm is complex and returns many values.
    (
        chords_key, chords_scale, _, _, _, chords_strength,
        key, scale, strength, _, _, _
    ) = tonal_algo(frame_spectrum)

    # Store the results for this frame in a dictionary
    frame_features = {
        'frame_index': frame_count,
        'loudness': loudness_val,
        'spectral_centroid': centroid,
        'spectral_contrast': s_contrast.tolist(), # Convert numpy array to list
        'dissonance': dissonance_val,
        'key': f"{key} {scale}",
        # After
        'key_strength': float(strength.flatten()[0]) if strength.size > 0 else 0.0,
    }
    all_frame_features.append(frame_features)


# --- 5. Display Results ---
# Print the features extracted from a few selected frames.

print("Processing complete.")
print(f"Extracted features for {len(all_frame_features)} frames.\n")

# Print features for the first 5 frames as an example
for i in range(min(5, len(all_frame_features))):
    features = all_frame_features[i]
    print(f"--- Frame {features['frame_index']} ---")
    print(f"  Loudness: {features['loudness']:.2f} LUFS")
    print(f"  Spectral Centroid (Brightness): {features['spectral_centroid']:.2f} Hz")
    print(f"  Dissonance: {features['dissonance']:.4f}")
    print(f"  Key: {features['key']} (Strength: {features['key_strength']:.2f})")
    # Spectral contrast is a vector, so we'll just print the first few values
    print(f"  Spectral Contrast (first 3 bands): {[f'{x:.2f}' for x in features['spectral_contrast'][:3]]}")

# You can now access all features like this:
# first_frame_loudness = all_frame_features[0]['loudness']


# --- 6. NEW: Plotting Results ---
# We will now visualize the extracted features over time.

print("\nGenerating feature graphs...")

# Prepare data for plotting by extracting it from our list of dictionaries
frame_indices = [f['frame_index'] for f in all_frame_features]
loudness = [f['loudness'] for f in all_frame_features]
centroids = [f['spectral_centroid'] for f in all_frame_features]
dissonances = [f['dissonance'] for f in all_frame_features]
key_strengths = [f['key_strength'] for f in all_frame_features]

# Create a figure with 4 subplots, arranged vertically
fig, axs = plt.subplots(4, 1, figsize=(12, 10), sharex=True)
fig.suptitle('Audio Feature Analysis over Time', fontsize=16)

# Plot 1: Loudness
axs[0].plot(frame_indices, loudness, color='b')
axs[0].set_ylabel('Loudness')
axs[0].grid(True, alpha=0.5)

# Plot 2: Spectral Centroid (Brightness)
axs[1].plot(frame_indices, centroids, color='r')
axs[1].set_ylabel('Spectral Centroid (Hz)')
axs[1].grid(True, alpha=0.5)

# Plot 3: Dissonance
axs[2].plot(frame_indices, dissonances, color='g')
axs[2].set_ylabel('Dissonance')
axs[2].grid(True, alpha=0.5)

# Plot 4: Key Strength
axs[3].plot(frame_indices, key_strengths, color='m')
axs[3].set_ylabel('Key Strength')
axs[3].set_xlabel('Frame Index')
axs[3].grid(True, alpha=0.5)

# Improve layout and save the figure
plt.tight_layout(rect=[0, 0, 1, 0.96])
plt.savefig('features_graph.png')

print("Successfully saved graphs to 'features_graph.png'")
