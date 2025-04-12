from flask import Blueprint, request, jsonify, current_app
from disease_predict import DiseasePredictionModel
from docsuggest import get_specialization
from werkzeug.utils import secure_filename
import os
import cv2
import numpy as np
import joblib
from skin_predict import predict_skin_cancer, ensemble_prediction


# Initialize the blueprint
disease_blueprint = Blueprint('disease', __name__)

# Instantiate the disease prediction model
disease_model = DiseasePredictionModel()

@disease_blueprint.route('/disease/predict_disease', methods=['POST'])
def predict_disease():
    try:
        data = request.get_json()
        symptoms = data.get('symptoms')
        if not symptoms:
            return jsonify({'error': 'No symptoms provided'}), 400

        predictions = disease_model.predict(symptoms)
        return jsonify(predictions)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@disease_blueprint.route('/get_doctors', methods=['POST'])
def get_doctors():
    try:
        data = request.get_json()
        disease = data.get('disease', '').strip()
        if not disease:
            return jsonify({'error': 'Disease not specified.'}), 400

        specialization = get_specialization(disease)
        if not specialization:
            return jsonify({'doctors': [], 'message': f'No specialization found for disease: {disease}'}), 200

        doctors = current_app.mongo.db.doctors.find({"specialization": {'$regex': specialization, '$options': 'i'}})
        response_data = [{
            "name": doc.get("name", "Name not available"),
            "specialization": doc.get("specialization", "Specialization not available"),
            "description": doc.get("description", {}),
            "phone_number": doc.get("phone_number", "Not available"),
            "hospital": doc.get("hospital", "Not available"),
            "availability": doc.get("availability", {}),
            "fees": doc.get("fees", "Not specified")
        } for doc in doctors]

        return jsonify({"doctors": response_data}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    

MODELS_DIR = "models"

# Ensure the upload folder exists
@disease_blueprint.route("/predict", methods=["POST"])
def predict():
    """
    Handle image upload and return predictions.
    """
    try:
        # Access the upload folder from the app context
        upload_folder = current_app.config["UPLOAD_FOLDER"]
        os.makedirs(upload_folder, exist_ok=True)  # Ensure the upload folder exists

        if "image" not in request.files:
            return jsonify({"error": "No file part in the request."}), 400

        file = request.files["image"]

        if file.filename == "":
            return jsonify({"error": "No selected file."}), 400

        if file:
            # Save the uploaded file
            filename = secure_filename(file.filename)
            file_path = os.path.join(upload_folder, filename)
            file.save(file_path)

            # Run predictions
            results = predict_skin_cancer(file_path, "models")
            ensemble_result = ensemble_prediction(results)

            # Return results
            return jsonify({
                "Random_Forest": results.get("Random_Forest", "N/A"),
                "XGBoost": results.get("XGBoost", "N/A"),
                "Ensemble": ensemble_result
            })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
