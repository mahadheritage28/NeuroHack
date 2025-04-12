
import pandas as pd
import numpy as np
from sklearn.preprocessing import LabelEncoder
from sklearn.svm import SVC
from sklearn.naive_bayes import GaussianNB
from sklearn.ensemble import RandomForestClassifier
import statistics

class DiseasePredictionModel:
    def __init__(self):
        # Load and preprocess training data
        self.data = pd.read_csv('Training.csv').dropna(axis=1)
        self.encoder = LabelEncoder()
        self.data["prognosis"] = self.encoder.fit_transform(self.data["prognosis"])

        # Prepare feature and target variables
        self.X = self.data.iloc[:, :-1]
        self.y = self.data.iloc[:, -1]

        # Initialize models
        self.final_svm_model = SVC()
        self.final_nb_model = GaussianNB()
        self.final_rf_model = RandomForestClassifier(random_state=18)

        # Train models
        self.final_svm_model.fit(self.X, self.y)
        self.final_nb_model.fit(self.X, self.y)
        self.final_rf_model.fit(self.X, self.y)

        # Store symptoms and class mappings
        symptoms = self.X.columns.values
        self.symptom_index = {val: idx for idx, val in enumerate(symptoms)}

        self.predictions_classes = self.encoder.classes_

    def predict(self, symptoms):
        # Check if symptoms are passed as a list or comma-separated string
        if isinstance(symptoms, str):
            symptoms = symptoms.split(",")
        elif not isinstance(symptoms, list):
            raise ValueError("Symptoms should be a string (comma-separated) or a list of symptoms.")

        # Create input vector
        input_data = [0] * len(self.symptom_index)
        for symptom in symptoms:
            index = self.symptom_index.get(symptom.strip())
            if index is not None:
                input_data[index] = 1
            else:
                print(f"Warning: {symptom.strip()} not found in symptom index.")  # Debugging missing symptoms

        input_data = np.array(input_data).reshape(1, -1)
        print("Input Vector: ", input_data)


        # Get predictions from all models
        rf_prediction = self.predictions_classes[self.final_rf_model.predict(input_data)[0]]
        nb_prediction = self.predictions_classes[self.final_nb_model.predict(input_data)[0]]
        svm_prediction = self.predictions_classes[self.final_svm_model.predict(input_data)[0]]

        print("RF Prediction: ", rf_prediction)
        print("NB Prediction: ", nb_prediction)
        print("SVM Prediction: ", svm_prediction)


        # Combine predictions
        try:
            final_prediction = statistics.mode([rf_prediction, nb_prediction, svm_prediction])
            print("Final Prediction: ", final_prediction)

        except statistics.StatisticsError:
            # Handle the case where there is no unique mode, fallback to one of the predictions
            final_prediction = rf_prediction  # Fallback to RandomForest prediction

        return {
            "rf_model_prediction": rf_prediction,
            "naive_bayes_prediction": nb_prediction,
            "svm_model_prediction": svm_prediction,
            "final_prediction": final_prediction,
        }
