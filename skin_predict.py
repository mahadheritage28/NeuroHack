import os
import joblib
import numpy as np
import cv2
from flask import current_app


def predict_skin_cancer(image_path, models_dir="models", img_size=(128, 128)):
    """
    Predict skin cancer classification using trained models.
    """
    # Load and preprocess the input image
    img = cv2.imread(image_path)
    if img is None:
        raise ValueError("Image not found or unable to read.")
    print(f"Original image shape: {img.shape}")  # Debugging log

    if not isinstance(img_size, tuple) or len(img_size) != 2:
        raise ValueError("Invalid img_size argument. Expected a tuple with (width, height).")

    img = cv2.resize(img, img_size) / 255.0  # Normalize
    print(f"Resized image shape: {img.shape}")  # Debugging log

    img_flat = img.flatten().reshape(1, -1)  # Flatten for classical models
    print(f"Flattened image shape: {img_flat.shape}")  # Debugging log

    results = {}
    for model_file in os.listdir(models_dir):
        model_path = os.path.join(models_dir, model_file)
        if model_file.endswith('.joblib'):
            # Load the model
            model = joblib.load(model_path)
            # Get probabilities
            prob = model.predict_proba(img_flat)[0] * 100
            # Format the result
            results[model_file.split('_')[0]] = f"Cancer: {prob[0]:.2f}%, Non-Cancer: {prob[1]:.2f}%"

    return results


def ensemble_prediction(results):
    """
    Use majority voting to determine the final prediction.

    Args:
    - results (dict): Dictionary containing model predictions in the format:
      {'ModelName': 'Cancer: XX.XX%, Non-Cancer: YY.YY%'}

    Returns:
    - str: Final prediction ("Cancer" or "Non-Cancer").
    """
    # Extract Cancer and Non-Cancer probabilities
    cancer_votes = 0
    non_cancer_votes = 0

    for model, result in results.items():
        if "Error" in result or "Prediction failed" in result:
            continue  # Skip models that failed to predict

        # Parse probabilities from the string
        cancer_prob = float(result.split('Cancer: ')[1].split('%')[0])
        non_cancer_prob = float(result.split('Non-Cancer: ')[1].split('%')[0])

        # Increment vote for the higher probability class
        if cancer_prob > non_cancer_prob:
            cancer_votes += 1
        else:
            non_cancer_votes += 1

    # Determine final prediction based on majority voting
    if cancer_votes > non_cancer_votes:
        return "Final Prediction: Cancer"
    elif non_cancer_votes > cancer_votes:
        return "Final Prediction: Non-Cancer"
    else:
        return "Final Prediction: Tie (Equal Votes)"
