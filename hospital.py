# hospital.py
from flask import  render_template,redirect,url_for
from flask import Blueprint, request, jsonify, current_app,session
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
from flask import Flask
from bson import ObjectId
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import random
import string
from datetime import datetime

app = Flask(__name__)




hospital_bp = Blueprint('hospital', __name__, template_folder='templates')

app.config['UPLOAD_FOLDER'] = 'static/hospital/'  # Change this path to where you want to store the images


@hospital_bp.route('/hoslogin')
def hoslogin():
    return render_template('hoslogin.html')

@hospital_bp.route('/hospital')
def hospital_dashboard():
    return render_template('hospital.html')

@hospital_bp.route('/register-hospital', methods=['POST'])
def register_hospital():
    data = request.json
    name = data.get('name')
    email = data.get('email')
    address = data.get('address')  # New field
    password = data.get('password')

    if not all([name, email, address, password]):
        return jsonify({"success": False, "message": "All fields are required!"}), 400

    # Access the MongoDB instance from the app context
    hospitals_collection = current_app.mongo.db.hospitals

    if hospitals_collection.find_one({"email": email}):
        return jsonify({"success": False, "message": "Email already registered!"}), 400

    hashed_password = generate_password_hash(password)
    hospitals_collection.insert_one({
        "name": name,
        "email": email,
        "address": address,  # Store the address
        "password": hashed_password
    })

    # Return success message after registration
    return jsonify({"success": True, "message": "Registration successful!You can Login now."}), 200



from flask import session, jsonify, request, current_app
from werkzeug.security import check_password_hash

@hospital_bp.route('/login-hospital', methods=['POST'])
def login_hospital():
    data = request.json
    email = data.get('email', '').strip().lower()
    password = data.get('password', '').strip()

    if not all([email, password]):
        return jsonify({"success": False, "message": "All fields are required!"}), 400

    # Access the MongoDB instance from the app context
    hospitals_collection = current_app.mongo.db.hospitals

    try:
        hospital = hospitals_collection.find_one({"email": email})

        if not hospital:
            return jsonify({"success": False, "message": "Email not registered!"}), 401

        # Check if 'password' exists in the document
        if 'password' not in hospital:
            return jsonify({"success": False, "message": "Password field is missing in the database!"}), 500

        if not check_password_hash(hospital['password'], password):
            return jsonify({"success": False, "message": "Incorrect password!"}), 401

        # Login is successful, set the email and name in the session
        session['hospital_email'] = email
        session['hospital_name'] = hospital.get("name")

        return jsonify({"success": True, "message": "Login successful!"}), 200
    except Exception as e:
        current_app.logger.error(f"Error during login: {str(e)}")
        return jsonify({"success": False, "message": "Internal server error!"}), 500


@hospital_bp.route('/get-hospital-details', methods=['GET'])
def get_hospital_details():
    # Fetch the logged-in hospital's email from the session
    email = session.get('hospital_email')
    if not email:
        return jsonify({"success": False, "message": "Not logged in!"}), 401

    # Access MongoDB to fetch the hospital details
    hospitals_collection = current_app.mongo.db.hospitals
    hospital = hospitals_collection.find_one({"email": email})
    if not hospital:
        return jsonify({"success": False, "message": "Hospital not found!"}), 404

    # Return the hospital details, excluding the password
    hospital_data = {
        "name": hospital.get("name"),
        "phone": hospital.get("phone", ""),
        "address": hospital.get("address", ""),
        "email": hospital.get("email"),
        "profile_picture": hospital.get("profile_picture", "")  # Profile picture field
    }

    return jsonify({"success": True, "data": hospital_data}), 200

#### Step 2: Saving updated hospital details
@hospital_bp.route('/update-hospital-details', methods=['POST'])
def update_hospital_details():
    # Check if the hospital is logged in
    email = session.get('hospital_email')
    if not email:
        return jsonify({"success": False, "message": "Not logged in!"}), 401

    data = request.form  # Use request.form for text fields when file uploads are involved
    name = data.get('name')
    phone = data.get('phone')
    address = data.get('address')

    # Validate required fields
    if not all([name, phone, address]):
        return jsonify({"success": False, "message": "All fields are required!"}), 400

    # Access MongoDB
    hospitals_collection = current_app.mongo.db.hospitals

    # Update data dictionary
    update_data = {
        "name": name,
        "phone": phone,
        "address": address,
    }

    # Handle profile picture upload
    profile_picture = request.files.get('profile_picture')
    if profile_picture:
        try:
            # Ensure the upload folder exists
            upload_folder = current_app.config.get('UPLOAD_FOLDER', 'uploads')
            os.makedirs(upload_folder, exist_ok=True)

            # Save the file
            filename = secure_filename(profile_picture.filename)
            profile_picture_path = os.path.join(upload_folder, filename)
            profile_picture.save(profile_picture_path)

            # Add the file path to the update data
            update_data['profile_picture'] = profile_picture_path
        except Exception as e:
            return jsonify({"success": False, "message": f"File upload failed: {str(e)}"}), 500

    # Update hospital details in the database
    try:
        hospitals_collection.update_one({"email": email}, {"$set": update_data})
    except Exception as e:
        return jsonify({"success": False, "message": f"Database update failed: {str(e)}"}), 500

    return jsonify({"success": True, "message": "Hospital details updated successfully!"}), 200



def get_logged_in_email():
    """Check if the hospital is logged in by verifying the session."""
    email = session.get('hospital_email')
    if not email:
        return None, jsonify({"success": False, "message": "Not logged in!"}), 401
    return email, None



@hospital_bp.route('/get-doctors', methods=['GET'])
def get_doctors():
    email, error_response = get_logged_in_email()
    if error_response:
        return error_response

    # Fetch the hospital name using email
    hospitals_collection = current_app.mongo.db.hospitals
    hospital = hospitals_collection.find_one({"email": email})
    if not hospital:
        return jsonify({"success": False, "message": "Hospital not found!"}), 404

    hospital_name = hospital.get("name")

    # Fetch doctors belonging to this hospital
    doctors_collection = current_app.mongo.db.doctors
    doctors = list(doctors_collection.find({"hospital": hospital_name}))

    # Transform the data for frontend consumption
    doctor_data = [
        {
            "name": doctor.get("name"),
            "specialization": doctor.get("specialization"),
            "availability": doctor.get("availability"),
            "description": doctor.get("description", {}),
        }
        for doctor in doctors
    ]

    return jsonify({"success": True, "data": doctor_data}), 200


@hospital_bp.route('/update-doctor-availability', methods=['POST'])
def update_doctor_availability():
    email, error_response = get_logged_in_email()
    if error_response:
        return error_response

    data = request.json
    doctor_name = data.get("name")
    new_availability = data.get("availability")

    if not all([doctor_name, new_availability]):
        return jsonify({"success": False, "message": "Doctor name and availability are required!"}), 400

    # Update the doctor's availability
    doctors_collection = current_app.mongo.db.doctors
    doctor = doctors_collection.find_one({"name": doctor_name})

    if not doctor:
        return jsonify({"success": False, "message": "Doctor not found!"}), 404

    # Append new availability to the existing availability
    existing_availability = doctor.get("availability", {})
    for date, slots in new_availability.items():
        if date not in existing_availability:
            existing_availability[date] = slots  # Add new date if not already present
        else:
            # Append the new time slots for the existing date
            existing_availability[date].update(slots)

    # Save the updated availability
    result = doctors_collection.update_one(
        {"name": doctor_name},
        {"$set": {"availability": existing_availability}}
    )

    return jsonify({"success": True, "message": "Availability updated successfully!"}), 200



@hospital_bp.before_app_request
def setup_upload_folder():
    """Ensure the upload folder exists."""
    upload_folder = current_app.config.get('HOSPITAL_UPLOAD_FOLDER', 'hospital_uploads')
    if not os.path.exists(upload_folder):
        os.makedirs(upload_folder)

@hospital_bp.route('/get_appointments', methods=['GET'])
def get_appointments():
    # Fetch the logged-in hospital's name from the session
    hospital_name = session.get('hospital_name')
    if not hospital_name:
        return jsonify({"success": False, "message": "Not logged in!"}), 401

    # Use the 'mongo' object to access the 'appointments' collection
    appointments_collection = current_app.mongo.db.appointments
    appointments = list(appointments_collection.find({"doctor_hospital": hospital_name}, {'_id': 0}))
    return jsonify(appointments)

@hospital_bp.route('/update_status', methods=['POST'])
def update_status():
    data = request.json
    appointment_id = data['appointment_id']
    status = data['status']

    appointments_collection = current_app.mongo.db.appointments
    appointments_collection.update_one(
        {'appointment_id': appointment_id},
        {'$set': {'status': status}}
    )
    return jsonify({'success': True})



def send_email(to_email, subject, body):
    try:
        smtp_server = "smtp.gmail.com"
        smtp_port = 587
        sender_email = "auramed1628@gmail.com"  # Replace with your email
        sender_password = "kxmg wngq ksyp pzss"  # Replace with your app-specific password

        message = MIMEMultipart()
        message["From"] = sender_email
        message["To"] = to_email
        message["Subject"] = subject
        message.attach(MIMEText(body, "plain"))

        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, to_email, message.as_string())
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False


@hospital_bp.route('/upload_prescription', methods=['POST'])
def upload_prescription():
    appointment_id = request.form.get('appointment_id')
    file = request.files.get('prescription')

    if not appointment_id or not file:
        return jsonify({'success': False, 'error': 'Appointment ID and file are required'}), 400

    upload_folder = current_app.config['HOSPITAL_UPLOAD_FOLDER']
    filename = file.filename
    file_path = os.path.join(upload_folder, filename)
    file.save(file_path)

    relative_file_path = os.path.join('static', 'uploads', filename).replace("\\", "/")
    appointments_collection = current_app.mongo.db.appointments
    uploads_collection = current_app.mongo.db.uploads

    appointment = appointments_collection.find_one({'appointment_id': appointment_id})
    if not appointment:
        return jsonify({'success': False, 'error': 'Invalid appointment ID'}), 400

    patient_email = appointment.get('patient_email')
    hospital_name = appointment.get('doctor_hospital', 'Unknown')
    doctor_name = appointment.get('doctor_name', 'Unknown')

    new_prescription = {
        'filename': filename,
        'uploaded_at': datetime.utcnow(),
        'file_path': relative_file_path
    }

    if uploads_collection.find_one({'email': patient_email}):
        uploads_collection.update_one(
            {'email': patient_email},
            {'$push': {'prescription': new_prescription}}
        )
    else:
        uploads_collection.insert_one({
            'email': patient_email,
            'prescription': [new_prescription]
        })

    appointments_collection.update_one(
        {'appointment_id': appointment_id},
        {'$set': {'prescription': relative_file_path}}
    )

    reminder_message = f"Prescription uploaded for appointment at {hospital_name} with {doctor_name}."
    users_collection = current_app.mongo.db.users
    users_collection.update_one(
        {'email': patient_email},
        {'$push': {'reminders': reminder_message}}
    )

    # Send email notification
    subject = "Prescription Uploaded Successfully"
    body = (
        f"Dear Patient,\n\n"
        f"Your prescription for the appointment at {hospital_name} with Dr. {doctor_name} has been successfully uploaded.\n\n"
        f"File Name: {filename}\n"
        f"Access it from your portal.\n\n"
        f"Best Regards,\nHospital Team"
    )
    email_status = send_email(patient_email, subject, body)
    if not email_status:
        return jsonify({'success': True, 'message': 'Prescription uploaded but email notification failed'}), 200

    return jsonify({'success': True, 'message': 'Prescription uploaded and email notification sent successfully'}), 200




@hospital_bp.route('/get_tests', methods=['GET'], endpoint='hospital_get_tests')
def get_tests():
    """Fetch all tests from the database for the logged-in hospital and return them as JSON."""
    hospital_name = session.get('hospital_name')
    if not hospital_name:
        return jsonify({"success": False, "message": "Not logged in!"}), 401

    tests = list(current_app.mongo.db.tests.find({"hospital_name": hospital_name}))
    for test in tests:
        test['_id'] = str(test['_id'])  # Convert ObjectId to string
    return jsonify(tests)



@hospital_bp.route('/upload_report', methods=['POST'], endpoint='hospital_upload_report')
def upload_report():
    test_slot_code = request.form.get('test_slot_code')
    file = request.files.get('file')

    if not test_slot_code:
        return jsonify({'error': 'Test slot code is required'}), 400
    if not file:
        return jsonify({'error': 'No file provided'}), 400

    filename = secure_filename(file.filename)
    save_path = os.path.join(current_app.root_path, 'static/uploads', filename)
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    file.save(save_path)

    test = current_app.mongo.db.tests.find_one({'test_slot_code': test_slot_code})
    if not test:
        return jsonify({'error': 'Test not found'}), 404

    patient_email = test.get('patient_email', 'Unknown')
    hospital_name = test.get('hospital_name', 'Unknown')
    test_type = test.get('test_type', 'Unknown')

    current_app.mongo.db.uploads.update_one(
        {'email': patient_email},
        {'$push': {'report': {
            'filename': filename,
            'uploaded_at': datetime.utcnow(),
            'file_path': f"/static/uploads/{filename}"
        }}},
        upsert=True
    )

    current_app.mongo.db.tests.update_one(
        {'test_slot_code': test_slot_code},
        {'$set': {
            'report': f"/static/uploads/{filename}",
            'status': 'completed'
        }}
    )

    reminder_message = f"Your report '{filename}' for the test '{test_type}' has been successfully uploaded."
    users_collection = current_app.mongo.db.users
    users_collection.update_one(
        {'email': patient_email},
        {'$push': {'reminders': reminder_message}}
    )

    # Send email notification
    subject = "Test Report Uploaded Successfully"
    body = (
        f"Dear Patient,\n\n"
        f"Your report for the test '{test_type}' at {hospital_name} has been successfully uploaded.\n\n"
        f"File Name: {filename}\n"
        f"Access it from your portal.\n\n"
        f"Best Regards,\nHospital Team"
    )
    email_status = send_email(patient_email, subject, body)
    if not email_status:
        return jsonify({'message': 'Report uploaded but email notification failed', 'filename': filename}), 200

    return jsonify({'message': 'Report uploaded and email notification sent successfully', 'filename': filename}), 200




@hospital_bp.route('/update_status_test', methods=['POST'], endpoint='hospital_update_status')
def update_status():
    """Update the test status to 'completed'."""
    data = request.json
    test_slot_code = data.get('test_slot_code')  # Match with the frontend
    if not test_slot_code:
        return jsonify({'error': 'Test slot code is required'}), 400

    result = current_app.mongo.db.tests.update_one(
        {'test_slot_code': test_slot_code},
        {'$set': {'status': 'completed'}}
    )

    if result.modified_count == 0:
        return jsonify({'error': 'Test not found or already updated'}), 404

    return jsonify({'message': 'Test status updated to completed'}), 200


@hospital_bp.route('/bed_availability', methods=['GET'])
def get_bed_availability():
    """Fetch the bed availability from the database for the logged-in hospital."""
    hospital_name = session.get('hospital_name')
    if not hospital_name:
        return jsonify({"success": False, "message": "Not logged in!"}), 401

    hospitals_collection = current_app.mongo.db.hospitals
    hospital_data = hospitals_collection.find_one({"name": hospital_name})

    if not hospital_data or 'bed_availability' not in hospital_data:
        return jsonify([])

    bed_availability = hospital_data['bed_availability']
    formatted_data = [
        {"type": bed_type, "available": count}
        for bed_type, count in bed_availability.items()
    ]

    return jsonify(formatted_data)

@hospital_bp.route('/update_bed', methods=['POST'])
def update_bed():
    """Update the bed availability in the database."""
    data = request.json
    bed_type = data.get('type')
    available = data.get('available')

    if not bed_type or available is None:
        return jsonify({"error": "Invalid input"}), 400

    hospitals_collection = current_app.mongo.db.hospitals
    
    # Update the specific bed type
    hospitals_collection.update_one(
        {},
        {"$set": {f"bed_availability.{bed_type}": available}}
    )

    return jsonify({"message": "Bed availability updated"})




@hospital_bp.route('/add-doctor', methods=['POST'])
def add_doctor():
    """
    Route to add a new doctor to the database.
    """
    try:
        data = request.json
        if not data:
            return jsonify({"error": "Invalid data"}), 400

        # Access the MongoDB collection using current_app
        
        doctors_collection = current_app.mongo.db.doctors

        # Insert doctor data into the "doctors" collection
        doctors_collection.insert_one(data)
        return jsonify({"message": "Doctor added successfully"}), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@hospital_bp.route('/get_test_slots', methods=['GET'])
def get_test_slots():
    hospital_name = session.get('hospital_name')
    if not hospital_name:
        return jsonify({"success": False, "message": "Not logged in!"}), 401

    try:
        db = current_app.mongo.db
        hospital_data = db.hospitals.find_one({"name": hospital_name})
        if not hospital_data or "test_availability" not in hospital_data:
            return jsonify({}), 200

        return jsonify(hospital_data["test_availability"]), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500



@hospital_bp.route('/update_test_slot', methods=['POST'])
def update_test_slot():
    try:
        db = current_app.mongo.db
        data = request.json

        # Extract fields from the request
        category = data.get("category")
        test_name = data.get("testName")
        price = data.get("price")
        date = data.get("date")
        time = data.get("time")
        slots = data.get("slots")

        if not (category and test_name and price and date and time and slots):
            return jsonify({"error": "Missing required fields."}), 400

        # Fetch or create the hospital document
        hospital_data = db.hospitals.find_one()
        if not hospital_data:
            hospital_data = {
                "test_availability": {
                    category: {
                        test_name: {
                            "price": price,
                            date: {time: {"slots": int(slots)}}
                        }
                    }
                }
            }
            db.hospitals.insert_one(hospital_data)
        else:
            # Update or initialize test_availability
            test_availability = hospital_data.get("test_availability", {})

            # Add category if it doesn't exist
            if category not in test_availability:
                test_availability[category] = {}

            # Add test name if it doesn't exist
            if test_name not in test_availability[category]:
                test_availability[category][test_name] = {"price": price}
            else:
                # Update the price if it has changed
                test_availability[category][test_name]["price"] = price

            # Add or update the date and time slots
            if date not in test_availability[category][test_name]:
                test_availability[category][test_name][date] = {}

            test_availability[category][test_name][date][time] = {"slots": int(slots)}

            # Save the updated test_availability back to the database
            db.hospitals.update_one(
                {"_id": hospital_data["_id"]},
                {"$set": {"test_availability": test_availability}}
            )

        return jsonify({"message": "Test slot updated successfully!"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

