import essentia.standard as es
import numpy as np
import os
import matplotlib.pyplot as plt

# --- 1. Configuration ---

# IMPORTANT: Replace this with the path to your audio file.
file_path = "believer.mp3" 

# Audio processing settings
sample_rate = 44100

# Short window for timbral features (e.g., brightness, loudness)
short_window_size = 2048  # ~46 ms
short_hop_size = 1024       # ~23 ms

# Long window for tonal/rhythmic features (e.g., key, BPM)
long_window_size = 88200 # ~2 seconds
long_hop_size = 22050    # ~0.5 seconds

# --- 2. Audio Loading ---
audio = None
if os.path.exists(file_path):
    print(f"Loading audio file: {file_path}")
    audio = es.MonoLoader(filename=file_path, sampleRate=sample_rate)()
else:
    print(f"Warning: Audio file not found at '{file_path}'. Generating fallback.")
    audio = es.Sine(frequency=440, sampleRate=sample_rate)(5 * sample_rate)


# --- 3. Algorithm Initialization ---

# We now have TWO frame generators for multi-resolution analysis
short_frame_generator = es.FrameGenerator(audio, frameSize=short_window_size, hopSize=short_hop_size)
long_frame_generator = es.FrameGenerator(audio, frameSize=long_window_size, hopSize=long_hop_size)

# General algorithms
window = es.Windowing(type='hann')
spectrum = es.Spectrum()

# --- Short-window feature extractors ---
loudness_algo = es.Loudness()
centroid_algo = es.Centroid(range=sample_rate/2)
spectral_peaks_algo = es.SpectralPeaks(sampleRate=sample_rate)
dissonance_algo = es.Dissonance()

# --- Long-window feature extractors ---
tonal_algo = es.TonalExtractor()
bpm_estimator_algo = es.PercivalBpmEstimator(sampleRate=sample_rate, frameSize=long_window_size, hopSize=long_hop_size)


# --- 4. Main Processing Loop ---
# We process the long frames first to get stable tonal/rhythmic data.

print("Starting multi-resolution feature analysis...")
print(f"Short Window: {short_window_size/sample_rate:.2f}s | Long Window: {long_window_size/sample_rate:.2f}s")
print("-" * 30)

# Store long-window results first
long_window_features = []
for long_frame in long_frame_generator:
    # Get spectrum for the long frame
    long_frame_spectrum = spectrum(window(long_frame))
    
    # Tonal features
    (
        _, _, _, _, _, _,
        key, scale, strength, _, _, _
    ) = tonal_algo(long_frame_spectrum)
    
    # BPM estimation
    bpm = bpm_estimator_algo(long_frame)
    
    long_window_features.append({
        'bpm': bpm,
        'key_strength': float(strength.flatten()[0]) if strength.size > 0 else 0.0,
    })

# Now, process short frames and map the long-frame data to them
all_frame_features = []
long_feature_index = 0
# Calculate how many short frames correspond to one long frame hop
hop_ratio = long_hop_size // short_hop_size

for frame_count, short_frame in enumerate(short_frame_generator):
    # Determine which long-window feature to use for this short frame
    if frame_count % hop_ratio == 0 and long_feature_index < len(long_window_features) - 1:
        long_feature_index += 1
    
    # Get spectrum for the short frame
    short_frame_spectrum = spectrum(window(short_frame))
    
    # --- Calculate short-window features ---
    loudness_val = loudness_algo(short_frame)
    centroid = centroid_algo(short_frame_spectrum)
    peak_frequencies, peak_magnitudes = spectral_peaks_algo(short_frame_spectrum)
    dissonance_val = dissonance_algo(peak_frequencies, peak_magnitudes)
    
    # Combine short-window features with the corresponding long-window features
    frame_features = {
        'frame_index': frame_count,
        'loudness': loudness_val,
        'spectral_centroid': centroid,
        'dissonance': dissonance_val,
        'bpm': long_window_features[long_feature_index]['bpm'],
        'key_strength': long_window_features[long_feature_index]['key_strength'],
    }
    all_frame_features.append(frame_features)


# --- 5. Display Results ---
print("Processing complete.")
print(f"Extracted features for {len(all_frame_features)} frames.\n")

# Print features for a few selected frames
for i in range(min(5, len(all_frame_features))):
    features = all_frame_features[i]
    print(f"--- Frame {features['frame_index']} ---")
    print(f"  Loudness: {features['loudness']:.2f}")
    print(f"  Spectral Centroid: {features['spectral_centroid']:.2f} Hz")
    print(f"  Dissonance: {features['dissonance']:.4f}")
    print(f"  Key Strength (long window): {features['key_strength']:.2f}")
    print(f"  BPM (long window): {features['bpm']:.2f}")


# --- 6. Plotting Results ---
print("\nGenerating feature graphs...")

# Prepare data for plotting
frame_indices = [f['frame_index'] for f in all_frame_features]
loudness = [f['loudness'] for f in all_frame_features]
centroids = [f['spectral_centroid'] for f in all_frame_features]
dissonances = [f['dissonance'] for f in all_frame_features]
key_strengths = [f['key_strength'] for f in all_frame_features]
bpms = [f['bpm'] for f in all_frame_features]

# Create a figure with 5 subplots
fig, axs = plt.subplots(5, 1, figsize=(12, 12), sharex=True)
fig.suptitle('Multi-Resolution Audio Feature Analysis', fontsize=16)

# Plot 1: Loudness (short window)
axs[0].plot(frame_indices, loudness, color='b')
axs[0].set_ylabel('Loudness')
axs[0].grid(True, alpha=0.5)

# Plot 2: Spectral Centroid (short window)
axs[1].plot(frame_indices, centroids, color='r')
axs[1].set_ylabel('Spectral Centroid (Hz)')
axs[1].grid(True, alpha=0.5)

# Plot 3: Dissonance (short window)
axs[2].plot(frame_indices, dissonances, color='g')
axs[2].set_ylabel('Dissonance')
axs[2].grid(True, alpha=0.5)

# Plot 4: Key Strength (long window)
axs[3].plot(frame_indices, key_strengths, color='m')
axs[3].set_ylabel('Key Strength')
axs[3].grid(True, alpha=0.5)

# Plot 5: Streaming BPM (long window)
axs[4].plot(frame_indices, bpms, color='c')
axs[4].set_ylabel('Streaming BPM')
axs[4].set_xlabel('Frame Index')
axs[4].grid(True, alpha=0.5)

# Improve layout and save the figure
plt.tight_layout(rect=[0, 0, 1, 0.96])
plt.savefig('features_graph_multires.png')

print("Successfully saved graphs to 'features_graph_multires.png'")
