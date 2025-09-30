import essentia.standard as es
import numpy as np

# All Essentia objects as per your original code
windowing = es.Windowing(type='hann')
spectrum = es.Spectrum()
spectral_peaks = es.SpectralPeaks(
    orderBy='magnitude', magnitudeThreshold=0.0001,
    minFrequency=40, maxFrequency=5000, maxPeaks=60
)
hpcp = es.HPCP(size=36, referenceFrequency=440, harmonics=4, bandPreset=True)
key_extractor = es.KeyExtractor(profileType='edma')

def extract_harmony(audio_buffer):
    """
    Returns HPCP mean, key, scale, key strength,
    and harmony class ("Simple"/"Complex") for the window.
    "Simple" = strong key, "Complex" = weak key.
    """
    frame_size = 4096
    hop_size = 2048
    hpcp_frames = []
    for frame in es.FrameGenerator(
        audio_buffer, frameSize=frame_size, hopSize=hop_size, startFromZero=True
    ):
        spec = spectrum(windowing(frame))
        freqs, mags = spectral_peaks(spec)
        hpcp_frame = hpcp(freqs, mags)
        hpcp_frames.append(hpcp_frame)
    hpcp_mean = np.mean(hpcp_frames, axis=0) if hpcp_frames else np.zeros(36)

    key, scale, strength = key_extractor(audio_buffer)
    harmony_class = "Simple" if strength >= 0.7 else "Complex"
    return hpcp_mean, key, scale, strength, harmony_class
