from flask import Blueprint, request, jsonify, current_app
from bson import ObjectId
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

search_bp = Blueprint('search', __name__)

@search_bp.route('/search', methods=['GET'])
def search():
    query = request.args.get('query', '').lower()
    if not query:
        return jsonify({"error": "No search query provided"}), 400
    
    mongo = current_app.mongo
    hospitals_collection = mongo.db.hospitals
    doctors_collection = mongo.db.doctors

    # Search for hospitals matching the query
    hospitals = list(hospitals_collection.find(
        {"name": {"$regex": query, "$options": "i"}},
        {"_id": 0, "name": 1, "address": 1}
    ))

    # Search for doctors matching the query and include their id
    doctors = list(doctors_collection.find(
        {"name": {"$regex": query, "$options": "i"}},
        {"_id": 0, "id": 1, "name": 1, "hospital": 1, "specialization": 1}
    ))

    return jsonify({
        "hospitals": hospitals,
        "doctors": doctors
    })

@search_bp.route('/get_doctor_id', methods=['GET'])
def get_doctor_id():
    doctor_name = request.args.get('name')

    if not doctor_name:
        return jsonify({"error": "Doctor name is required"}), 400

    mongo = current_app.mongo
    doctors_collection = mongo.db.doctors

    # Debugging log
    print(f"Searching for doctor with name: {doctor_name}")

    doctor = doctors_collection.find_one({"name": doctor_name})

    if doctor:
        # Convert ObjectId to string before returning
        doctor_id = str(doctor.get('_id'))  # _id is the default field for ObjectId in MongoDB
        return jsonify({"doctorId": doctor_id}), 200
    else:
        return jsonify({"error": "Doctor not found"}), 404
    

# Endpoint to fetch all hospitals
@search_bp.route('/hospitals', methods=['GET'])
def fetch_all_hospitals():
    mongo = current_app.mongo
    hospitals_collection = mongo.db.hospitals
    hospitals = list(hospitals_collection.find({}, {"name": 1}))  # Fetch only hospital names
    for hospital in hospitals:
        hospital["_id"] = str(hospital["_id"])  # Convert ObjectId to string
    return jsonify(hospitals)

# Endpoint to fetch a specific hospital by its ID
@search_bp.route('/hospitals/<hospital_id>', methods=['GET'])
def fetch_hospital_by_id(hospital_id):
    if not ObjectId.is_valid(hospital_id):
        return jsonify({"error": "Invalid hospital ID"}), 400

    mongo = current_app.mongo
    hospitals_collection = mongo.db.hospitals
    hospital = hospitals_collection.find_one({"_id": ObjectId(hospital_id)})

    if not hospital:
        return jsonify({"error": "Hospital not found"}), 404

    hospital["_id"] = str(hospital["_id"])  # Convert ObjectId to string for JSON serialization
    return jsonify(hospital)

@search_bp.route('/requestBed', methods=['POST'])
def handle_bed_request():
    try:
        data = request.json
        print("Received data:", data)  # Debugging line
        
        hospital_id = data.get("hospitalId")
        bed_type = data.get("bedType")  # Get bed type
        user_name = data.get("userName")
        user_email = data.get("userEmail")

        # Validate required fields
        if not (hospital_id and bed_type and user_name and user_email):
            print("Validation failed: Missing required fields")  # Debugging line
            return jsonify({"error": "All fields are required"}), 400

        mongo = current_app.mongo
        hospitals_collection = mongo.db.hospitals
        users_collection = mongo.db.users  # Access the users collection

        # Fetch hospital details
        print("Fetching hospital details for ID:", hospital_id)  # Debugging line
        hospital = hospitals_collection.find_one({"_id": ObjectId(hospital_id)})

        if not hospital:
            print("Hospital not found for ID:", hospital_id)  # Debugging line
            return jsonify({"error": "Hospital not found"}), 404

        # Fetch user phone number from users collection using the provided email
        print("Fetching user details for email:", user_email)  # Debugging line
        user = users_collection.find_one({"email": user_email})

        if not user:
            print("User not found for email:", user_email)  # Debugging line
            return jsonify({"error": "User not found"}), 404

        user_phone = user.get("phone_number", "Not Provided")  # Using "phone_number" field
        print("User phone:", user_phone)  # Debugging line

        hospital_email = hospital.get("email")
        if not hospital_email:
            print("Hospital email not available")  # Debugging line
            return jsonify({"error": "Hospital email not available"}), 500

        # Email preparation
        print("Preparing email to send")  # Debugging line
        sender_email = "auramed1628@gmail.com"  # Replace with your email
        sender_password = "kxmg wngq ksyp pzss"  # Replace with your email password

        subject = "Urgent: Bed Request Notification"
        body = f"""
        Dear {hospital['name']},

        I hope this message finds you well.

        {user_name} (Email: {user_email}, Phone: {user_phone}) has expressed interest in securing a bed at your facility. They are specifically looking for a {bed_type} bed.

        Please kindly reach out to the user at the contact details provided above to further assist them with the bed request.

        We would appreciate your prompt response in this matter.

        Thank you for your time and assistance.

        Best regards,
        AuraMed
        """

        print("Email content prepared:")  # Debugging line
        print("Subject:", subject)  # Debugging line
        print("Body:", body)  # Debugging line

        # Send email
        try:
            print("Attempting to send email...")  # Debugging line
            server = smtplib.SMTP("smtp.gmail.com", 587)
            server.starttls()
            server.login(sender_email, sender_password)
            message = MIMEMultipart()
            message["From"] = sender_email
            message["To"] = hospital_email
            message["Subject"] = subject
            message.attach(MIMEText(body, "plain"))
            server.send_message(message)
            server.quit()
            print("Email sent successfully")  # Debugging line
            return jsonify({"message": "Bed request sent successfully"}), 200
        except Exception as e:
            print("Failed to send email:", str(e))  # Debugging line
            return jsonify({"error": f"Failed to send email: {str(e)}"}), 500

    except Exception as e:
        print("Error in handling bed request:", str(e))  # Debugging line
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500



@search_bp.route('/fetch_notifications', methods=['POST'])
def fetch_notifications():
    """Fetch reminders for the user based on their email."""
    try:
        data = request.json
        email = data.get('email')
        if not email:
            return jsonify({"error": "Email is required"}), 400

        db = current_app.mongo.db

        # Fetch user reminders by email
        user = db.users.find_one({"email": email}, {"reminders": 1})
        if not user or "reminders" not in user:
            return jsonify([])  # Return empty list if no reminders

        reminders = user.get("reminders", [])
        return jsonify(reminders)

    except Exception as e:
        current_app.logger.error(f"Error fetching notifications: {e}")
        return jsonify({"error": "Failed to fetch notifications"}), 500


@search_bp.route('/mark_notification_as_read', methods=['POST'])
def mark_notification_as_read():
    """Mark a notification as read and delete it from the database."""
    try:
        data = request.json
        email = data.get('email')
        index = data.get('index')

        if not email or index is None:
            return jsonify({"error": "Invalid input"}), 400

        db = current_app.mongo.db

        # Use $unset and $pull to remove a specific reminder
        db.users.update_one(
            {"email": email},
            {"$unset": {f"reminders.{index}": 1}}
        )
        db.users.update_one(
            {"email": email},
            {"$pull": {"reminders": None}}
        )

        return jsonify({"success": True})

    except Exception as e:
        current_app.logger.error(f"Error marking notification as read: {e}")
        return jsonify({"error": "Failed to mark notification as read"}), 500