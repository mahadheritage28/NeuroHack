import json
import pandas as pd

# Load the JSON data for doctors
def load_doctor_data():
    file_path = "healthcaresystem.doctors.json"
    with open(file_path, "r") as file:
        data = json.load(file)
    return pd.DataFrame(data).drop('_id', axis=1)

# Load the JSON data for disease-specialization mapping
def load_disease_data():
    with open('disease_specialization.json', 'r') as file:
        return json.load(file)

# Get specialization based on the disease
def get_specialization(disease_name):
    disease_data = load_disease_data()
    for entry in disease_data:
        if entry['disease'].lower() == disease_name.lower():
            return entry['specialization']
    return "Specialization not found, try checking the spelling!"

# Get doctor details based on specialization
def get_doctor_details(specialization):
    doctor_df = load_doctor_data()
    doctor_info = doctor_df[doctor_df['specialization'].str.lower() == specialization.lower()]
    if not doctor_info.empty:
        return doctor_info.to_dict(orient='records')
    return []
