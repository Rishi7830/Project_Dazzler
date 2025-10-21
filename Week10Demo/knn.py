import numpy as np
import pandas as pd

# mood weights from the trained knn model
mood_weights = {
    "Pleasure": [12, 11, -7, -5, 0],
    "Excitement": [24, 16, 20, -10, 10],
    "Arousal": [0, -14, 21, 2, 20],
    "Distress": [0, -14, 21, 2, 10],
    "Displeasure": [-16, -2, -14, -3, 0],
    "Depression": [-8, -4, -7, 10, -10],
    "Sleepiness": [-12, 4, -16, -9, -20],
    "Relaxation": [3, 10, -20, -2, -10]
}

mood_df = pd.DataFrame(mood_weights, index=["Mode", "Harmony", "Tempo", "Rhythm", "Loudness"])

def preprocess_features(loudness: float, mode: str, key: str, tempo: float) -> list:
    """
    Convert audio analyzer features to scaled numeric features for mood prediction.

    Args:
        loudness (float): loudness in dB, e.g., -20
        mode (str): "major" or "minor"
        key (str): key name, e.g., "C", "G", "F#"
        tempo (float): tempo in BPM, e.g., 120

    Returns:
        list: [mode_scaled, harmony_scaled, tempo_scaled, rhythm_scaled, loudness_scaled]
    """
    # Mode: major -> 1, minor -> -1
    mode_scaled = 1 if mode.lower() == 'major' else -1

    # Harmony: if key has sharps/flats, assume "complex" (-1); else, "simple" (1)
    harmony_scaled = -1 if ('#' in key or 'b' in key) else 1

    # Tempo: normalized around 120 BPM, std ~40 (adjust as needed)
    tempo_scaled = (tempo - 120) / 40

    # Rhythm: not used in audio_analyzer, so set to 0
    rhythm_scaled = 0

    # Loudness: map [-60, -10] dB to [-1, 1]
    loudness_clipped = np.clip(loudness, -60, -10)
    loudness_scaled = (loudness_clipped + 60) / 25 - 1

    return [mode_scaled, harmony_scaled, tempo_scaled, rhythm_scaled, loudness_scaled]

def predict_mood(features: list) -> str:
    """
    Predict mood from preprocessed features (see preprocess_features).
    """
    weighted_sums = np.dot(mood_df.T.values, features)
    predicted_mood = mood_df.columns[np.argmax(weighted_sums)]
    return predicted_mood
