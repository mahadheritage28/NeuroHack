from flask import Blueprint, request, jsonify, session, current_app,redirect, url_for
from werkzeug.utils import secure_filename
import os
from bson import ObjectId
import re
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import datetime
import schedule
import time
import threading
from bson.json_util import dumps
from pytz import timezone



dashboard_bp = Blueprint('dashboard', __name__)
UPLOAD_FOLDER = "static/uploads"
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}


def get_mongo():
    print("Initializing MongoDB connection.")
    return dashboard_bp.mongo

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@dashboard_bp.route('/profile', methods=['GET'])
def get_profile():
    try:
        if 'user_id' not in session:
            return jsonify({"error": "Unauthorized access"}), 403

        user_id = session['user_id']
        user = current_app.mongo.db.users.find_one({"_id": ObjectId(user_id)})
        print(user)
        if not user:
            return jsonify({"error": "User not found"}), 404

        return jsonify({
            "user_id": user_id,
            "name": user.get("name", ""),
            "email": user.get("email", ""),
            "phone_number": user.get("phone_number", ""),
            "profile_picture": user.get("profile_picture", "")
        })
    except Exception as e:
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500



@dashboard_bp.route('/profile/<user_id>', methods=['POST'])
def update_profile(user_id):
    print(f"Received profile update request for user_id: {user_id}")
    if 'user_id' not in session or session['user_id'] != user_id:
        return jsonify({"error": "Unauthorized access."}), 403
    
    print(f"Session user_id: {session.get('user_id')}, Requested user_id: {user_id}")


    try:
        user = current_app.mongo.db.users.find_one({"_id": ObjectId(user_id)})
        if not user:
            return jsonify({"error": "User not found."}), 404

        # Extract form data
        data = request.form
        name = data.get("name")
        email = data.get("email")
        phone = data.get("phone")

        # Validate email format (optional, depending on requirements)
        if email and not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            return jsonify({"error": "Invalid email format."}), 400

        # Validate phone number format (optional, based on requirements)
        if phone and not phone.isdigit():
            return jsonify({"error": "Invalid phone number format."}), 400

        # Handle profile picture upload
        if 'profile_picture' in request.files:
            file = request.files['profile_picture']
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                filepath = os.path.join(UPLOAD_FOLDER, filename)
                file.save(filepath)
                current_app.mongo.db.users.update_one(
                    {"_id": ObjectId(user_id)},
                    {"$set": {"profile_picture": f"/{filepath}"}}
                )
            else:
                return jsonify({"error": "Invalid file type for profile picture."}), 400

        # Update user profile fields
        update_fields = {}
        if name:
            update_fields["name"] = name
        if email:
            update_fields["email"] = email
        if phone:
            update_fields["phone_number"] = phone

        if update_fields:
            current_app.mongo.db.users.update_one(
                {"_id": ObjectId(user_id)},
            {"$set": update_fields}
            )
    

        return jsonify({"message": "Profile updated successfully!"})

    except Exception as e:
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500

# Email Configuration (use environment variables or set directly)
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
EMAIL_ADDRESS = "auramed1628@gmail.com"
EMAIL_PASSWORD = "kxmg wngq ksyp pzss"

@dashboard_bp.route('/save-health-data', methods=['POST'])
def save_health_data():
    try:
        data = request.get_json()

        # Validate input
        user_email = data.get('userEmail')
        if not user_email:
            return jsonify({"error": "User email is required"}), 400

        user = dashboard_bp.mongo.db.users.find_one({"email": user_email})
        if not user:
            return jsonify({"error": "User not found"}), 404

        # Validate required health fields
        required_fields = ["sex", "age", "height", "weight", "bloodPressure", "sugarLevel"]
        for field in required_fields:
            if field not in data or not data[field]:
                return jsonify({"error": f"{field} is required"}), 400

        # Validate lastPeriod if provided
        last_period = data.get('lastPeriod')
        if last_period:
            try:
                datetime.strptime(last_period, "%Y-%m-%d")  # Adjust the format if needed
            except ValueError:
                return jsonify({"error": "Invalid lastPeriod date format. Expected YYYY-MM-DD"}), 400

        # Get the current IST time in ISO 8601 format
        ist_timezone = timezone('Asia/Kolkata')
        current_time_ist = datetime.now(ist_timezone).isoformat()

        health_data = {
            "sex": data['sex'],
            "age": data['age'],
            "height": data['height'],
            "weight": data['weight'],
            "bloodPressure": data['bloodPressure'],
            "sugarLevel": data['sugarLevel'],
            "lastPeriod": last_period,
            "updatedAt": current_time_ist
        }

        # Fetch the current health data
        current_health_data = user.get("health_data")
        if current_health_data:
            # Append the current health data to the health_data_record array
            dashboard_bp.mongo.db.users.update_one(
                {"email": user_email},
                {"$push": {"health_data_record": current_health_data}}
            )

        # Update the user's health data
        result = dashboard_bp.mongo.db.users.update_one(
            {"email": user_email},
            {"$set": {"health_data": health_data}}
        )

        if result.matched_count == 0:
            return jsonify({"error": "Failed to update health data"}), 500

        return jsonify({"message": "Health data saved successfully!", "health_data": health_data})
    except Exception as e:
        print("Error in save_health_data:", str(e))  # Log error
        return jsonify({"error": "An unexpected error occurred."}), 500



@dashboard_bp.route('/get-health-data', methods=['GET'])
def get_health_data():
    user_email = request.args.get('userEmail')

    if not user_email:
        return jsonify({"error": "User email is missing"}), 400

    user = dashboard_bp.mongo.db.users.find_one({"email": user_email})

    if not user:
        return jsonify({"error": "User not found"}), 404

    if 'health_data' in user:
        health_data = user['health_data']

        # Blood Pressure Analysis (BP)
        systolic, diastolic = map(int, health_data["bloodPressure"].split('/'))
        
        # BP Analysis based on general normal range and age group
        bp_analysis = get_bp_analysis(health_data["age"], systolic, diastolic)

        # Blood Sugar Analysis
        sugar_analysis = get_sugar_analysis(health_data["sugarLevel"], health_data.get("postMealSugarLevel"), health_data.get("hbA1c"))

        # Add analysis to health data
        health_data.update({
            "bpAnalysis": bp_analysis,
            "sugarAnalysis": sugar_analysis
        })

        return jsonify({"healthData": health_data})
    else:
        return jsonify({"error": "No health data found for the user."}), 404

def get_bp_analysis(age, systolic, diastolic):
    # Ensure age is treated as an integer
    age = int(age)
    
    # Ideal BP Ranges for different age groups
    ideal_ranges = {
        (20, 29): (116, 120, 76, 80),  # Min systolic, Max systolic, Min diastolic, Max diastolic
        (30, 39): (120, 124, 80, 84),
        (40, 49): (124, 130, 84, 86),
        (50, 59): (130, 134, 86, 88),
        (60, float('inf')): (134, 139, 88, 90),
    }

    # Determine the appropriate BP range for the given age
    for age_group, (min_sys, max_sys, min_dia, max_dia) in ideal_ranges.items():
        if age_group[0] <= age <= (age_group[1] if isinstance(age_group[1], int) else float('inf')):
            break

    # BP Analysis
    if systolic < min_sys and diastolic < min_dia:
        bp_analysis = "Low BP: Your blood pressure is lower than the ideal range. You may feel dizzy or fatigued. Consider consulting a doctor."
    elif min_sys <= systolic <= max_sys and min_dia <= diastolic <= max_dia:
        bp_analysis = "Ideal BP: Your blood pressure is within the healthy range. Keep up the good work!"
    elif systolic > max_sys or diastolic > max_dia:
        bp_analysis = "High BP: Your blood pressure is higher than the ideal range. You may be at risk of hypertension. Consider monitoring your health or consulting a doctor."
    else:
        bp_analysis = "Please consult a doctor: The blood pressure values entered are inconsistent or out of the expected range."

    return bp_analysis

def get_sugar_analysis(fasting_sugar, post_meal_sugar=None, hbA1c=None):
    # Ensure all values are treated as numbers (float or int)
    fasting_sugar = float(fasting_sugar)  # Convert fasting_sugar to a float
    sugar_analysis = ""  # Initialize sugar_analysis to an empty string

    # Fasting Blood Sugar Analysis
    if fasting_sugar < 100:
        sugar_analysis += "Normal fasting blood sugar."
    elif 100 <= fasting_sugar <= 125:
        sugar_analysis += "Prediabetes - Fasting Blood Sugar (FBS) is higher than normal."
    else:
        sugar_analysis += "Diabetes - Fasting Blood Sugar (FBS) is too high."

    # Post-Meal Blood Sugar Analysis (if available)
    if post_meal_sugar is not None:
        post_meal_sugar = float(post_meal_sugar)  # Convert post_meal_sugar to a float
        if post_meal_sugar < 140:
            sugar_analysis += " Normal post-meal blood sugar."
        elif 140 <= post_meal_sugar <= 199:
            sugar_analysis += " Prediabetes - Post-meal blood sugar is higher than normal."
        else:
            sugar_analysis += " Diabetes - Post-meal blood sugar is too high."

    # HbA1c Analysis (if available)
    if hbA1c is not None:
        hbA1c = float(hbA1c)  # Convert hbA1c to a float
        if hbA1c < 5.7:
            sugar_analysis += " Normal HbA1c."
        elif 5.7 <= hbA1c <= 6.4:
            sugar_analysis += " Prediabetes - HbA1c is higher than normal."
        else:
            sugar_analysis += " Diabetes - HbA1c is too high."

    return sugar_analysis




from datetime import datetime, timedelta  # Correct import

def send_email_reminder():
    users = dashboard_bp.mongo.db.users.find()
    for user in users:
        last_updated = user.get('health_data', {}).get('updatedAt')
        if last_updated:
            if isinstance(last_updated, str):
                last_updated = datetime.strptime(last_updated, "%Y-%m-%dT%H:%M:%S")
            minutes_since_update = (datetime.now() - last_updated).total_seconds() / 60
            if minutes_since_update > 10:
                email = user.get('email')
                if email:
                    send_reminder_email(email)
                dashboard_bp.mongo.db.users.update_one(
                    {'_id': user['_id']},
                    {'$push': {'reminders': 'Please update your health data. It has been more than 10 minutes.'}}
                )


def send_reminder_email(email):
    subject = "Reminder to Update Your Health Data"
    body = "It's been a month since you updated your health data. Please take a moment to update your health information."

    msg = MIMEMultipart()
    msg['From'] = EMAIL_ADDRESS
    msg['To'] = email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            server.sendmail(EMAIL_ADDRESS, email, msg.as_string())
    except Exception as e:
        print(f"Error sending email to {email}: {e}")


schedule.every(60).minutes.do(send_email_reminder)

def run_scheduler():
    while True:
        schedule.run_pending()
        time.sleep(1)

def start_scheduler():
    threading.Thread(target=run_scheduler, daemon=True).start()

start_scheduler()


@dashboard_bp.route('/getUserAppointments', methods=['GET'])
def get_user_appointments():
    email = request.args.get('email')
    if not email:
        return jsonify({"message": "Email is required."}), 400

    mongo = get_mongo()
    appointments_collection = mongo.db.appointments

    active_appointments = list(appointments_collection.find(
        {"patient_email": email, "status": "ongoing"},
        {"_id": 0}
    ))
    completed_appointments = list(appointments_collection.find(
        {"patient_email": email, "status": "completed"},
        {"_id": 0}
    ))

    return jsonify({"active": active_appointments, "completed": completed_appointments})



@dashboard_bp.route('/getDoctorAvailability', methods=['GET'])
def get_doctor_availability():
    doctor_name = request.args.get('doc_name')
    if not doctor_name:
        return jsonify({"message": "Doctor name is required."}), 400

    mongo = get_mongo()
    doctors_collection = mongo.db.doctors

    doctor = doctors_collection.find_one({"name": doctor_name}, {"_id": 0, "availability": 1})
    if doctor:
        return jsonify(doctor['availability'])
    return jsonify({"message": "Doctor not found."}), 404


@dashboard_bp.route('/adjustAppointment', methods=['POST'])
def adjust_appointment():
    data = request.json
    email = data.get('email')
    old_date_time = data.get('oldSlot')
    new_slot = data.get('newSlot')

    if not email or not old_date_time or not new_slot:
        return jsonify({"message": "Email, oldSlot, and newSlot are required."}), 400

    mongo = get_mongo()
    appointments_collection = mongo.db.appointments

    result = appointments_collection.update_one(
        {"patient_email": email, "date_time": old_date_time},
        {"$set": {"date_time": new_slot}}
    )

    if result.modified_count:
        return jsonify({"message": "Appointment updated successfully."}), 200
    return jsonify({"message": "Failed to update appointment."}), 400


@dashboard_bp.route('/getUserTests', methods=['GET'])
def get_user_tests():
    email = request.args.get('email')
    if not email:
        return jsonify({"message": "Email is required."}), 400

    mongo = get_mongo()
    tests_collection = mongo.db.tests

    active_tests = list(tests_collection.find(
        {"patient_email": email, "status": "ongoing"},
        {"_id": 0}
    ))
    completed_tests = list(tests_collection.find(
        {"patient_email": email, "status": "completed"},
        {"_id": 0}
    ))

    return jsonify({"active": active_tests, "completed": completed_tests})


@dashboard_bp.route('/cancel', methods=['DELETE'])
def cancel_item():
    email = request.args.get('email')
    slot = request.args.get('slot')

    if not email or not slot:
        return jsonify({"message": "Email and slot are required."}), 400

    mongo = get_mongo()
    appointments_collection = mongo.db.appointments

    result = appointments_collection.delete_one({"patient_email": email, "date_time": slot})
    if result.deleted_count:
        return jsonify({"message": "Appointment cancelled successfully."}), 200

    tests_collection = mongo.db.tests
    result = tests_collection.delete_one({"patient_email": email, "test_slot_code": slot})
    if result.deleted_count:
        return jsonify({"message": "Test cancelled successfully."}), 200

    return jsonify({"message": "Slot not found."}), 404


@dashboard_bp.route('/getAvailableSlotsForRescheduling', methods=['GET'])
def get_available_slots_for_rescheduling():
    test_slot_code = request.args.get('testSlotCode')

    if not test_slot_code:
        return jsonify({"error": "Test Slot Code is required"}), 400

    try:
        test = current_app.mongo.db.tests.find_one({"test_slot_code": test_slot_code})
        if not test:
            return jsonify({"error": "Test with the given Test Slot Code not found"}), 404

        test_category = test.get('test_category')
        test_type = test.get('test_type')
        test_date = test.get('test_date')
        test_time = test.get('test_time')

        if not (test_category and test_type and test_date and test_time):
            return jsonify({"error": "Incomplete test information for the given Test Slot Code"}), 400

        hospital = current_app.mongo.db.hospitals.find_one({"name": test.get("hospital_name")})
        if not hospital:
            return jsonify({"error": f"Hospital '{test.get('hospital_name')}' data not found"}), 404

        test_availability = hospital.get('test_availability', {}).get(test_category, {}).get(test_type, {})
        available_slots = {
            date: {
                time: data['slots'] for time, data in times.items()
                if isinstance(data, dict) and data.get('slots', 0) > 0
            }
            for date, times in test_availability.items() if isinstance(times, dict)
        }

        if not available_slots:
            return jsonify({"error": "No available slots for rescheduling"}), 404

        return jsonify({
            "current_date": test_date,
            "current_time": test_time,
            "available_slots": available_slots
        })

    except Exception as e:
        return jsonify({"error": "Internal server error"}), 500

@dashboard_bp.route('/rescheduleTest', methods=['POST'])
def reschedule_test():
    data = request.get_json()

    user_email = data.get('email')
    old_slot = data.get('oldSlot')
    new_date = data.get('newDate')
    new_time = data.get('newTime')

    if not user_email or not old_slot or not new_date or not new_time:
        return jsonify({"error": "Missing required fields"}), 400

    try:
        # Find the old test booking
        test = current_app.mongo.db.tests.find_one({"test_slot_code": old_slot, "patient_email": user_email})

        if not test:
            return jsonify({"error": "Test booking not found"}), 404

        test_category = test.get('test_category')
        test_name = test.get('test_type')

        if not test_category or not test_name:
            return jsonify({"error": "Test category or name not found in booking"}), 400

        # Query the hospital collection for slot availability
        hospital = current_app.mongo.db.hospitals.find_one({})  # Adjust query as necessary

        if not hospital:
            return jsonify({"error": "Hospital data not found"}), 404

        test_availability = hospital.get('test_availability', {}).get(test_category, {}).get(test_name, {})

        # Check if the new date and time slot is available
        if (
            not test_availability.get(new_date) or
            not test_availability[new_date].get(new_time) or
            test_availability[new_date][new_time].get('slots', 0) <= 0
        ):
            return jsonify({"error": "The selected date and time slot is not available"}), 400

        # Decrease slot count for the new slot
        current_app.mongo.db.hospitals.update_one(
            {f"test_availability.{test_category}.{test_name}.{new_date}.{new_time}.slots": {"$gt": 0}},
            {"$inc": {f"test_availability.{test_category}.{test_name}.{new_date}.{new_time}.slots": -1}}
        )

        # Increase slot count for the old slot
        old_date = test.get('test_date')
        old_time = test.get('test_time')
        current_app.mongo.db.hospitals.update_one(
            {f"test_availability.{test_category}.{test_name}.{old_date}.{old_time}.slots": {"$gte": 0}},
            {"$inc": {f"test_availability.{test_category}.{test_name}.{old_date}.{old_time}.slots": 1}}
        )

        # Update the test booking with new date and time
        current_app.mongo.db.tests.update_one(
            {"test_slot_code": old_slot, "user_email": user_email},
            {"$set": {"test_date": new_date, "test_time": new_time}}
        )

        return jsonify({"message": "Test rescheduled successfully"})

    except Exception as e:
        print(f"Error rescheduling test: {e}")
        return jsonify({"error": "Internal server error"}), 500





# Path to the 'uploads' directory inside the 'static' folder
PROFILE_FOLDER = os.path.join(os.getcwd(), 'static', 'uploads')

# Create the 'uploads' folder if it doesn't exist
if not os.path.exists(PROFILE_FOLDER):
    os.makedirs(PROFILE_FOLDER)

# Allowed file extensions
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'pdf', 'png', 'jpg', 'jpeg'}

from datetime import datetime
from werkzeug.utils import secure_filename
import os

@dashboard_bp.route('/upload/<file_type>', methods=['POST'])
def upload_file(file_type):
    if 'file' not in request.files or 'email' not in request.form:
        return jsonify({"error": "Missing file or email"}), 400

    file = request.files['file']
    email = request.form['email']

    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    if file and allowed_file(file.filename):
        # Secure the filename
        filename = secure_filename(file.filename)
        
        # Define the relative and absolute file paths
        relative_file_path = f"static/uploads/{filename}"
        absolute_file_path = os.path.join(os.getcwd(), relative_file_path)
        
        # Save the file to the server
        os.makedirs(os.path.dirname(absolute_file_path), exist_ok=True)
        file.save(absolute_file_path)

        # Save metadata to MongoDB with the relative path
        uploads_collection = current_app.mongo.db.uploads
        uploads_collection.update_one(
            {"email": email},
            {
                "$push": {
                    file_type: {
                        "filename": filename,
                        "uploaded_at": datetime.utcnow(),
                        "file_path": f"/{relative_file_path}"  # Use relative path
                    }
                }
            },
            upsert=True
        )
        return jsonify({"message": f"{file_type.capitalize()} uploaded successfully"}), 200

    return jsonify({"error": "Invalid file type"}), 400


@dashboard_bp.route('/prescriptions', methods=['GET'])
def get_prescriptions():
    email = request.args.get('email')
    if not email:
        return jsonify({"error": "Email is required"}), 400

    uploads_collection = current_app.mongo.db.uploads
    user_data = uploads_collection.find_one({"email": email}, {"_id": 0, "prescription": 1})

    if not user_data or not user_data.get("prescription"):
        return jsonify([])

    prescriptions = user_data.get("prescription", [])
    for item in prescriptions:
        if 'file_path' in item:
            # Ensure file paths are formatted correctly for URLs
            item['file_path'] = item['file_path'].replace("\\", "/")
    return jsonify(prescriptions)


@dashboard_bp.route('/reports', methods=['GET'])
def get_reports():
    email = request.args.get('email')
    if not email:
        return jsonify({"error": "Email is required"}), 400

    uploads_collection = current_app.mongo.db.uploads
    user_data = uploads_collection.find_one({"email": email}, {"_id": 0, "report": 1})

    reports = user_data.get("report", []) if user_data else []

    # Ensure file_path is returned as a relative URL
    for item in reports:
        if 'file_path' in item:
            item['file_path'] = item['file_path'].replace("C:/Users/ASUS/healthcare", "")

    return jsonify(reports)

