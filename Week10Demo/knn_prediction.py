import joblib
import numpy as np


class MoodPredictor:
    """
    A class to load a trained KNN model and scaler to predict moods from audio features.
    """
    def __init__(self, model_path='knn_model.joblib', scaler_path='scaler.joblib'):
        """
        Initializes the predictor by loading the model and scaler from file.
        """
        self.model = None
        self.scaler = None
        try:
            loaded_model = joblib.load(model_path)
            loaded_scaler = joblib.load(scaler_path)
            if loaded_model is None or loaded_scaler is None:
                raise ValueError("Loaded model or scaler is None. Files may be corrupt or incompatible.")
            
            self.model = loaded_model
            self.scaler = loaded_scaler
            print("✅ Successfully loaded and validated model and scaler.")

        except FileNotFoundError:
            print(f"❌ Error: Model or scaler file not found.")
            print("Please make sure model files are in the same folder and the training script has been run.")
        except Exception as e:
            print(f"❌ An error occurred while loading model files: {e}")

    def predict_mood(self, features):
        """
        Predicts the mood for a set of 5 raw features.

        Args:
            features (list): A list containing the 5 features in the correct order:
                             [mode, harmony, tempo, rhythm, loudness].

        Returns:
            str: The predicted mood as a string, or an error message.
        """
        if self.model is None or self.scaler is None:
            return "Model/scaler not loaded. Cannot make a prediction."

        try:
            mode_numeric = features[0]
            harmony_numeric = 1 if features[1] == 'simple' else 0
            tempo_numeric = features[2]
            rhythm_numeric = features[3]
            loudness_numeric = features[4]

            numeric_features = np.array([[
                mode_numeric, harmony_numeric, tempo_numeric, rhythm_numeric, loudness_numeric
            ]])
            features_scaled = self.scaler.transform(numeric_features)
            predicted_label_numeric = self.model.predict(features_scaled)

            labels = np.array(["Pleasure", "Excitement", "Arousal", "Distress", "Displeasure", "Depression", "Sleepiness", "Relaxation"])
            predicted_mood = labels[predicted_label_numeric[0]]

            return predicted_mood

        except Exception as e:
            return f"An error occurred during prediction: {e}"


