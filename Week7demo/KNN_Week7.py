import numpy as np
import pandas as pd

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

def preprocess_features(mode, key, tempo, loudness, rhythm_index, harmony_class):
    mode_scaled = 1 if mode == 'major' else -1
    harmony_scaled = 1 if harmony_class == 'Simple' else -1
    tempo_scaled = (tempo - 120) / 40
    rhythm_scaled = rhythm_index * 2 - 1
    loudness_clipped = np.clip(loudness, -60, -10)
    loudness_scaled = (loudness_clipped + 60) / 25 - 1
    return [mode_scaled, harmony_scaled, tempo_scaled, rhythm_scaled, loudness_scaled]

def predict_mood(features):
    weighted_sums = np.dot(mood_df.T.values, features)
    predicted_mood = mood_df.columns[np.argmax(weighted_sums)]
    return predicted_mood
