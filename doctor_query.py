import json
import spacy
import pytz
import random
import string
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app
import dateparser
from flask import jsonify, session, current_app

# Load spaCy's English NLP model
nlp = spacy.load("en_core_web_sm")

doctor_bp = Blueprint("doctor_bp", __name__)

def load_doctors_data(file_path):
    """Loads doctors' data from the JSON file."""
    with open(file_path, 'r') as file:
        return json.load(file)

import os

# Change path to relative (inside the container)
file_path = os.path.join(os.getcwd(), "healthcaresystem.doctors.json")
DOCTOR_DATA = load_doctors_data(file_path)

def extract_keywords(query):
    """Uses NLP to extract relevant keywords from the query and map them to specializations."""
    keyword_mapping = {
        "ear": "ENT Specialist",
        "nose": "ENT Specialist",
        "throat": "ENT Specialist",
        "brain": "Neurology",
        "neurologist": "Neurology",
        "nervous system": "Neurology",
        "skin": "Dermatologist",
        "dermatologist": "Dermatologist",
        "heart": "Cardiologist",
        "cardiologist": "Cardiologist",
        "bones": "Orthopedic Surgeon",
        "bone": "Orthopedic Surgeon",
        "joint": "Orthopedic Surgeon",
        "muscle": "Orthopedic Surgeon",
        "children": "Pediatrician",
        "child": "Pediatrician",
        "pediatrician": "Pediatrician",
        "urinary system": "Urologist",
        "urologist": "Urologist",
        "medicine": "General Medicine",
        "fever": "General Medicine",
        "infection": "General Medicine"
    }
    
    doc = nlp(query.lower())
    keywords = [token.lemma_ for token in doc if token.pos_ in ["NOUN", "PROPN", "ADJ"]]
    
    mapped_keywords = set()
    for word in keywords:
        if word in keyword_mapping:
            mapped_keywords.add(keyword_mapping[word])
        else:
            mapped_keywords.add(word)
    
    return mapped_keywords

def search_doctors(data, query):
    """Searches for one doctor based on extracted keywords and returns a single-line response."""
    keywords = extract_keywords(query)
    if not keywords:
        return {"fulfillmentText": "I couldn't understand the query. Please ask about a medical specialization or condition."}

    for doctor in data:
        specialization = doctor.get("specialization", "").strip()
        if any(keyword == specialization for keyword in keywords):
            return {
                "fulfillmentText": f"Dr. {doctor.get('name', 'Unknown')} at {doctor.get('hospital', 'Unknown hospital')}, Fees: {doctor.get('fees', 'Not available')} INR."
            }

    return {"fulfillmentText": "No matching doctors found."}



from bson import ObjectId
def clean_string(value):
    """Removes surrounding quotes from a string if present."""
    if isinstance(value, str):
        return value.strip().strip('"')
    return value

@doctor_bp.route("/webhook", methods=["POST"])
def webhook():
    """Handles requests from Dialogflow webhook."""
    req = request.get_json()
    print("Received request:", json.dumps(req, indent=2))  # Debugging

    intent_name = req.get("queryResult", {}).get("intent", {}).get("displayName")
    parameters = req.get("queryResult", {}).get("parameters", {})

    print(f"Extracted Parameters: {parameters}")  # Debugging

    if intent_name == "BookAppointment":
        doctor_name = parameters.get("doctor_name", "").strip()
        date = parameters.get("date", "").strip()
        time = parameters.get("time", "").strip()
        user_name = parameters.get("user_name", "").strip()
        user_email = parameters.get("user_email", "").strip()
        user_phone = parameters.get("user_phone", "").strip()

        print(f"Extracted Doctor: {doctor_name}, Date: {date}, Time: {time}, Name: {user_name}, Email: {user_email}, Phone: {user_phone}")  # Debugging

        # Check for missing required fields
        if not all([doctor_name, date, time, user_name, user_email, user_phone]):
            return jsonify({"fulfillmentText": "❌ Missing required details (doctor name, date, time, or patient details)."})

        # Call create_appointment with all required parameters
        response = create_appointment(doctor_name, date, time, user_name, user_email, user_phone)
        print("Webhook Response:", response.get_json())  # Debugging
        return response  # Ensure Dialogflow gets the correct response

    elif intent_name == "FindDoctor":
        query_text = req.get("queryResult", {}).get("queryText", "").strip()
        print(f"Searching for doctors using query: {query_text}")  # Debugging

        # Fetch doctor data from MongoDB
        doctors_collection = current_app.mongo.db.doctors
        doctor_data = list(doctors_collection.find({}))  # Convert cursor to list

        # Call search_doctors and log response
        response = search_doctors(doctor_data, query_text)
        print("Search Response:", response)  # Debugging
        return jsonify(response)

    return jsonify({"fulfillmentText": "❌ Intent not recognized by webhook."})



import re

def normalize_name(name):
    """Standardizes the doctor name to match database format."""
    name = name.strip()
    name = re.sub(r"\bDoctor\b", "Dr.", name, flags=re.IGNORECASE).strip()  # Convert "Doctor" to "Dr."
    return name

def format_time(time_str):
    """Formats time to remove seconds (HH:MM:SS -> HH:MM)."""
    return time_str[:5] if len(time_str) >= 5 else time_str  # Extract only HH:MM

def create_appointment(doctor_name, date, time, user_name, user_email, user_phone):
    """Creates an appointment in the database."""
    doctors_collection = current_app.mongo.db.doctors
    appointments_collection = current_app.mongo.db.appointments

    # Normalize doctor name
    doctor_name_cleaned = normalize_name(doctor_name)

    # Format time correctly
    formatted_time = format_time(time)

    # Find doctor in database (case-insensitive match)
    doctor = doctors_collection.find_one({"name": {"$regex": f"^{doctor_name_cleaned}$", "$options": "i"}})
    
    if not doctor:
        print(f"❌ Doctor {doctor_name_cleaned} not found in database!")  # Debugging
        return jsonify({"fulfillmentText": f"❌ Doctor {doctor_name_cleaned} not found. Please check the name."})

    availability = doctor.get("availability", {})
    
    # Debugging: Print available slots
    print(f"✅ Doctor Found: {doctor_name_cleaned}. Availability for {date}: {availability.get(date, {})}")

    if date not in availability or formatted_time not in availability[date]:
        return jsonify({
            "fulfillmentText": f"❌ No slots available for {doctor_name_cleaned} on {date} at {formatted_time}."
        })

    if availability[date][formatted_time] <= 0:
        return jsonify({
            "fulfillmentText": f"❌ Fully booked! Please choose another time."
        })

    # Generate unique appointment ID
    appointment_id = str(ObjectId())

    # Get current time in IST (India Standard Time)
    ist_timezone = pytz.timezone("Asia/Kolkata")
    created_at = datetime.now(ist_timezone).strftime("%Y-%m-%d %H:%M:%S")
    date_time = f"{date} {formatted_time}"  # Store full date and time

    # Create appointment entry
    appointment = {
        "appointment_id": appointment_id,
        "doctor_name": doctor_name_cleaned,
        "doctor_specialization": doctor.get("specialization"),
        "doctor_hospital": doctor.get("hospital"),
        "date": date,
        "time": formatted_time,  # Ensure the correct format is stored
        "date_time": date_time,
        "patient_name": user_name,
        "patient_email": user_email,
        "patient_phone": user_phone,
        "status": "ongoing",
        "created_at": created_at
    }

    # Insert appointment into MongoDB
    appointments_collection.insert_one(appointment)

    # Update availability
    doctors_collection.update_one(
        {"name": doctor_name_cleaned},
        {"$inc": {f"availability.{date}.{formatted_time}": -1}}
    )

    # Log successful booking
    print(f"✅ Appointment booked: {appointment}")

    return jsonify({
        "fulfillmentText": f"✅ Appointment booked with {doctor_name_cleaned} on {date} at {formatted_time}. Your appointment ID is {appointment_id}."
    })