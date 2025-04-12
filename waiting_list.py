from flask import Blueprint, jsonify, session,request
from pymongo import MongoClient
from datetime import datetime, timedelta

# Blueprint setup
waiting_list_bp = Blueprint("waiting_list", __name__)

# MongoDB connection setup
client = MongoClient("mongodb+srv://mahadiqbalaiml27:9Gx_qVZ-tpEaHUu@healthcaresystem.ilezc.mongodb.net/healthcaresystem?retryWrites=true&w=majority&appName=Healthcaresystem")
db = client["healthcaresystem"]
collection = db["appointments"]

def predict_wait_time(appointment_id):
    # Fetch all appointments excluding completed ones
    appointments = list(collection.find({"status": {"$ne": "completed"}}))

    # Sort appointments by creation time
    appointments.sort(key=lambda x: datetime.strptime(x["created_at"], "%Y-%m-%d %H:%M:%S"))

    # Find the target appointment
    target_appointment = None
    for index, appointment in enumerate(appointments):
        if appointment["appointment_id"] == appointment_id:
            target_appointment = appointment
            break

    if not target_appointment:
        return None

    # Calculate wait time
    estimated_time_per_appointment = timedelta(minutes=15)  # Average 15-20 mins per appointment
    total_wait_time = estimated_time_per_appointment * index

    # Get the current time and add the wait time to determine appointment time
    appointment_datetime = datetime.now() + total_wait_time

    return {
        "appointment_id": target_appointment["appointment_id"],
        "patient_name": target_appointment["patient_name"],
        "doctor_name": target_appointment["doctor_name"],
        "estimated_wait_time": str(total_wait_time),
        "appointment_start_time": appointment_datetime.strftime("%Y-%m-%d %H:%M:%S")
    }

@waiting_list_bp.route("/get-waiting-list", methods=["GET"])
def get_waiting_list():
    print("Fetching waiting list for logged-in user...")  # Debugging line
    user_email = session.get("user_email")

    if not user_email:
        print("User not logged in.")  # Debugging line
        return jsonify({"error": "User not logged in."}), 401

    print(f"Logged-in user email: {user_email}")  # Debugging line

    # Ensure the query filters for the correct email and status
    ongoing_appointments = list(collection.find({"patient_email": user_email, "status": "ongoing"}))

    if not ongoing_appointments:
        print("No ongoing appointment found for today.")  # Debugging line
        return jsonify({"message": "No ongoing appointment found for today."}), 404

    print(f"Ongoing appointments found: {ongoing_appointments}")  # Debugging line

    # Process each appointment to predict wait time
    response_data = []
    for appointment in ongoing_appointments:
        wait_time_info = predict_wait_time(appointment["appointment_id"])
        
        if not wait_time_info:
            print(f"Could not calculate wait time for appointment ID: {appointment['appointment_id']}")  # Debugging line
            continue

        response_entry = {
            "appointment_id": appointment["appointment_id"],
            "patient_name": appointment["patient_name"],
            "doctor_name": appointment["doctor_name"],
            "doctor_specialization": appointment["doctor_specialization"],
            "doctor_hospital": appointment["doctor_hospital"],
            "date_time": appointment["date_time"],
            "status": appointment["status"],
            "wait_time_info": wait_time_info
        }
        response_data.append(response_entry)

    if not response_data:
        return jsonify({"error": "Could not calculate wait time for any ongoing appointments."}), 500

    print(f"Final response data: {response_data}")  # Debugging line
    return jsonify(response_data)


video_call_collection = db["video_call"]  # Replace with your collection name

@waiting_list_bp.route("/video-call-requests", methods=["POST"])
def video_call_request():
    try:
        # Parse request data
        data = request.json

        # Validate required fields
        required_fields = ["doctor", "patient", "status", "timestamp"]
        if not all(field in data for field in required_fields):
            return jsonify({"error": "Missing required fields."}), 400

        # Insert data into MongoDB
        result = video_call_collection.insert_one(data)

        # Respond with success message
        return jsonify({"message": "Video call request created successfully.", "id": str(result.inserted_id)}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500
