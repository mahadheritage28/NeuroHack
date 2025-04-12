# In doclist.py (Blueprint for Doctor and Appointment Management)
from flask import Blueprint, jsonify, request, render_template,current_app
from bson.objectid import ObjectId
import random, string, smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import pytz  # Import for timezone handling

doclist_bp = Blueprint('doclist', __name__)



def generate_appointment_id():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=6))

@doclist_bp.route('/specializations', methods=['GET'])
def fetch_specializations():
    hospital = request.args.get('hospital')
    if not hospital:
        return jsonify({"error": "Hospital is required"}), 400

    specializations = [
        "Cardiologist",
        "Neurology",
        "Orthopedics",
        "Pediatrics",
        "General Medicine"
    ]

    return jsonify(specializations)



@doclist_bp.route('/doctors', methods=['GET'], endpoint='fetch_doctors_list')
def fetch_doctors():
    hospital = request.args.get('hospital')
    if not hospital:
        return jsonify({"error": "Hospital parameter is required"}), 400

    doctors_collection = current_app.mongo.db.doctors
    query = {'hospital': hospital}
    doctors = doctors_collection.find(query)
    doctor_list = [
        {
            "id": str(doc["_id"]),
            "name": doc["name"],
            "specialization": doc.get("specialization", "General"),
            "hospital": doc["hospital"],
            "degrees": doc.get("degrees", []),
            "experience": doc.get("experience", "Not specified"),
            "achievements": doc.get("achievements", [])
        }
        for doc in doctors
    ]

    return jsonify(doctor_list if doctor_list else [])

@doclist_bp.route('/doctor/<doctor_id>', methods=['GET'], endpoint='fetch_doctor_details_view')
def fetch_doctor_details(doctor_id):
    doctors_collection = current_app.mongo.db.doctors
    doctor = doctors_collection.find_one({"_id": ObjectId(doctor_id)})

    if not doctor:
        return jsonify({"error": "Doctor not found"}), 404

    description = doctor.get("description", {})
    doctor_details = {
        "name": doctor.get("name"),
        "specialization": doctor.get("specialization"),
        "phone_number": doctor.get("phone_number"),
        "hospital": doctor.get("hospital"),
        "fees": doctor.get("fees"),
        "degrees": description.get("degrees", []),
        "experience": description.get("experience", "Not specified"),
        "achievements": description.get("achievements", []),
        "availability": doctor.get("availability", {})
    }

    return jsonify(doctor_details)

@doclist_bp.route('/appointment', methods=['POST'])
def create_appointment():
    data = request.json
    print("Received data:", data)

    required_fields = [
        'patient_name', 'doctor_name', 'doctor_specialization',
        'doctor_hospital', 'phone', 'email', 'date_time'
    ]

    if not all(field in data for field in required_fields):
        return jsonify({"error": "All fields are required"}), 400

    try:
        date, time = data['date_time'].split('T')
        time = time[:5]  # Truncate to match HH:MM format if seconds are included
    except ValueError:
        return jsonify({"error": "Invalid date_time format. Use ISO 8601 format: YYYY-MM-DDTHH:MM:SS"}), 400

    doctors_collection = current_app.mongo.db.doctors
    appointments_collection = current_app.mongo.db.appointments
    users_collection = current_app.mongo.db.users

    doctor = doctors_collection.find_one({"name": data['doctor_name']})
    if not doctor:
        return jsonify({"error": "Doctor not found"}), 404

    availability = doctor.get('availability', {})
    print("Doctor's availability:", availability)

    if date not in availability or time not in availability[date] or availability[date][time] <= 0:
        available_slots = [
            f"{available_time} ({slots} slots)"
            for available_time, slots in availability.get(date, {}).items() if slots > 0
        ]
        return jsonify({
            "error": "No available slots for the requested date and time.",
            "available_slots": available_slots
        }), 400

    appointment_id = generate_appointment_id()

    ist_timezone = pytz.timezone('Asia/Kolkata')
    created_at = datetime.now(ist_timezone).strftime('%Y-%m-%d %H:%M:%S')

    appointment = {
        "appointment_id": appointment_id,
        "patient_name": data['patient_name'],
        "doctor_name": data['doctor_name'],
        "doctor_specialization": data['doctor_specialization'],
        "doctor_hospital": data['doctor_hospital'],
        "patient_phone": data['phone'],
        "patient_email": data['email'],
        "date_time": data['date_time'],
        "status": "ongoing",
        "created_at": created_at
    }

    appointments_collection.insert_one(appointment)

    doctors_collection.update_one(
        {"name": data['doctor_name']},
        {"$inc": {f"availability.{date}.{time}": -1}}
    )

    # Retrieve user's health data and health record
    user_doc = users_collection.find_one(
        {"email": data['email']}, 
        {"health_data": 1, "health_data_record": 1, "_id": 0}
    )

    health_data = user_doc.get("health_data", "No health data available") if user_doc else "No health data available"
    health_data_record = user_doc.get("health_data_record", []) if user_doc else []

    # Send confirmation email to patient
    send_confirmation_email(
        data['email'], data['patient_name'], data['doctor_name'],
        data['doctor_specialization'], data['doctor_hospital'],
        data['date_time'], appointment_id
    )

    # Send email to doctor with patient details and full health data
    doctor_email = doctor.get("email")
    if doctor_email:
        send_email_to_doctor(
            doctor_email, data['doctor_name'], data['patient_name'],
            data['doctor_specialization'], data['doctor_hospital'],
            data['date_time'], appointment_id, health_data, health_data_record
        )

    return jsonify({
        "message": "Appointment booked successfully",
        "appointment_id": appointment_id
    })


def send_email_to_doctor(doctor_email, doctor_name, patient_name, specialization, hospital, date_time, appointment_id, health_data, health_data_record):
    subject = f"New Appointment: {patient_name}"
    
    health_data_str = f"""
    Health Data:
    - Sex: {health_data.get("sex", "N/A")}
    - Age: {health_data.get("age", "N/A")}
    - Height: {health_data.get("height", "N/A")}
    - Weight: {health_data.get("weight", "N/A")}
    - Blood Pressure: {health_data.get("bloodPressure", "N/A")}
    - Sugar Level: {health_data.get("sugarLevel", "N/A")}
    - Last Period: {health_data.get("lastPeriod", "N/A")}
    - Last Updated: {health_data.get("updatedAt", "N/A")}
    """

    health_data_record_str = "\nHealth Data Record:\n"
    for record in health_data_record:
        health_data_record_str += f"""
    - Updated At: {record.get("updatedAt", "N/A")}
      * Sex: {record.get("sex", "N/A")}
      * Age: {record.get("age", "N/A")}
      * Height: {record.get("height", "N/A")}
      * Weight: {record.get("weight", "N/A")}
      * Blood Pressure: {record.get("bloodPressure", "N/A")}
      * Sugar Level: {record.get("sugarLevel", "N/A")}
      * Last Period: {record.get("lastPeriod", "N/A")}
    """

    body = f"""
    Hello Dr. {doctor_name},

    A new appointment has been scheduled.

    Appointment Details:
    - Patient Name: {patient_name}
    - Specialization: {specialization}
    - Hospital: {hospital}
    - Date & Time: {date_time}
    - Appointment ID: {appointment_id}

    {health_data_str}
    {health_data_record_str}

    Please review the details before the appointment.

    Regards,
    AuraMed Team
    """

    # Sending email using the provided SMTP details
    msg = MIMEMultipart()
    msg['From'] = 'auramed1628@gmail.com'
    msg['To'] = doctor_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login('auramed1628@gmail.com', 'kxmg wngq ksyp pzss')
        server.sendmail(msg['From'], msg['To'], msg.as_string())
        server.quit()
        print(f"Email sent to {doctor_email}")
    except Exception as e:
        print(f"Error sending email: {str(e)}")

def send_confirmation_email(patient_email, patient_name, doctor_name, doctor_specialization, doctor_hospital, date_time, appointment_id):
    msg = MIMEMultipart()
    msg['From'] = 'auramed1628@gmail.com'
    msg['To'] = patient_email
    msg['Subject'] = 'Appointment Confirmation Details'

    body = f"""
    Dear {patient_name},

    Greetings from The AuraMed!

    We are pleased to confirm your appointment booking. Below are the details:

    - **Patient Name**: {patient_name}
    - **Doctor Name**: {doctor_name}
    - **Specialization**: {doctor_specialization}
    - **Hospital Name**: {doctor_hospital}
    - **Appointment Date and Time**: {date_time}
    - **Appointment ID**: {appointment_id}

    Please arrive 15 minutes before the scheduled time.

    Regards,
    AuraMed Team
    """
    msg.attach(MIMEText(body, 'plain'))

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login('auramed1628@gmail.com', 'kxmg wngq ksyp pzss')
        server.sendmail(msg['From'], msg['To'], msg.as_string())
        server.quit()
        print(f"Email sent to {patient_email}")
    except Exception as e:
        print(f"Error sending email: {str(e)}")
