import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.neighbors import KNeighborsClassifier



# Load the dataset
file_path = 'week6_demo_data.csv'
data = pd.read_csv(file_path)

data['mode_scaled'] = data['mode'].map({1: 1, 0: -1}) 
data['harmony_scaled'] = data['harmony'].map({'simple': 1, 'complex': -1})
scaler = StandardScaler()
data[['tempo_scaled', 'loudness_scaled']] = scaler.fit_transform(data[['tempo', 'loudness']])
data['rhythm_scaled'] = 0


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

def calculate_weighted_sum(row, mood_df):
    return np.dot(mood_df.T.values, row) 
features = data[['mode_scaled', 'harmony_scaled', 'tempo_scaled', 'rhythm_scaled', 'loudness_scaled']]
weighted_sums = features.apply(lambda row: calculate_weighted_sum(row, mood_df), axis=1)
predicted_moods = weighted_sums.apply(lambda x: mood_df.columns[np.argmax(x)])
data['predicted_mood'] = predicted_moods

print(data[['track_id', 'mode_scaled', 'harmony_scaled', 'tempo_scaled', 'loudness_scaled', 'predicted_mood']].head())

# data.to_csv('predicted_mood_data.csv', index=False)



features = data[['mode_scaled', 'harmony_scaled', 'tempo_scaled', 'rhythm_scaled', 'loudness_scaled']]

mood_mapping = {mood: idx for idx, mood in enumerate(mood_df.columns)}
data['mood_label'] = data['predicted_mood'].map(mood_mapping)

X = features
y = data['mood_label']

scaler = StandardScaler()
X = scaler.fit_transform(X)


knn = KNeighborsClassifier(n_neighbors=5)
knn.fit(X, y)





def predict_mood_for_chunk(knn_model, scaler, features, chunk_start=0, chunk_end=5):
    """
    Predict the mood for a 5-second chunk based on the features (mode, harmony, tempo, rhythm, loudness).
    knn_model: Trained KNN classifier
    scaler: StandardScaler to transform the input features
    features: The features list for the chunk in question
    chunk_start: Start time of the chunk in seconds (default is 0)
    chunk_end: End time of the chunk in seconds (default is 5)
    """
    
    chunk_features = np.array(features).reshape(1, -1)
    chunk_features_scaled = scaler.transform(chunk_features)
    
    predicted_label = knn_model.predict(chunk_features_scaled)
    predicted_mood = list(mood_mapping.keys())[list(mood_mapping.values()).index(predicted_label[0])]
    
    return predicted_mood


#print(f"Predicted mood for this chunk: {predicted_mood}")
