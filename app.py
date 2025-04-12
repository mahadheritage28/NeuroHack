import os
#os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"



from flask_cors import CORS
from flask import Flask, render_template, redirect, url_for, request, session, flash ,jsonify
from flask_pymongo import PyMongo
from auth import AuthHandler
import requests
from oauthlib.oauth2 import WebApplicationClient
from dashboard import dashboard_bp
from hospital import hospital_bp
from home_routes import home_bp
from search import search_bp
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from pymongo import MongoClient
from apscheduler.schedulers.background import BackgroundScheduler
from sos import sos_bp  # Import SOS blueprint
import firebase_admin
from firebase_admin import credentials, messaging,initialize_app
from base64 import b64decode
import json
from dotenv import load_dotenv
from doctor_query import doctor_bp  # Import the blueprint



app = Flask(__name__,static_folder='static')
CORS(app)
app.secret_key = "your_secret_key"  # Replace with a secure secret key
app.config["MONGO_URI"] = "mongodb+srv://mahadiqbalaiml27:9Gx_qVZ-tpEaHUu@healthcaresystem.ilezc.mongodb.net/healthcaresystem?retryWrites=true&w=majority&appName=Healthcaresystem"  # Replace with your MongoDB URI
app.config['HOSPITAL_UPLOAD_FOLDER'] = 'static/uploads'

mongo = PyMongo(app)
app.mongo = mongo

# Ensure 'uploads' directory exists
UPLOAD_FOLDER = os.path.join(os.getcwd(), "uploads")

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Google OAuth configuration
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_OAUTH_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET")
GOOGLE_DISCOVERY_URL = "https://accounts.google.com/.well-known/openid-configuration"
REDIRECT_URI = "https://auramed-app-156513904358.us-central1.run.app/login/google/callback"
google_client = WebApplicationClient(GOOGLE_CLIENT_ID)

# Initialize AuthHandler
auth_handler = AuthHandler(mongo)

@app.route("/")
def landing_page():
    return render_template("land.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    return auth_handler.handle_login(request)


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        return auth_handler.handle_signup(request)
    return render_template("login.html")  # Render the signup form on GET





@app.route("/login/google")
def google_login():
    google_provider_cfg = auth_handler.get_google_provider_cfg(GOOGLE_DISCOVERY_URL)
    authorization_endpoint = google_provider_cfg["authorization_endpoint"]

    request_uri = google_client.prepare_request_uri(
        authorization_endpoint,
        redirect_uri=REDIRECT_URI,  # ✅ Fixed here
        scope=["openid", "email", "profile"],
    )
    return redirect(request_uri)

@app.route("/login/google/callback")
def google_callback():
    # Handle Google callback and store user data in session
    return auth_handler.handle_google_callback(
        google_client, request, GOOGLE_DISCOVERY_URL, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET
    )

@app.route("/home")
def home():
    # Pass the session data to the template
    user_email = session.get('user_email')
    user_id = session.get('user_id')
    return render_template("home.html", user_email=user_email, user_id=user_id)

# Register the blueprint
app.register_blueprint(dashboard_bp, url_prefix='/dashboard')
# Pass the mongo object to the blueprint
dashboard_bp.mongo = mongo




@app.route('/logout', methods=['POST', 'GET'])
def logout():
    try:
        # Clear the session to log out the user
        session.clear()

        # Redirect to the landing page
        return redirect(url_for('landing_page'))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Register the hospital blueprint and pass mongo
app.register_blueprint(hospital_bp)

app.register_blueprint(home_bp)

@app.route('/hosplist')
def render_hosplist():
    return render_template('hosplist.html')

@app.route('/doclist')
def render_doclist():
    return render_template('doclist.html')

from doclist import doclist_bp  # Import the blueprint from its module
# Register the blueprint
app.register_blueprint(doclist_bp, url_prefix='/doclist')


# Register the search blueprint
app.register_blueprint(search_bp, url_prefix='/api')




@app.route('/disease')
def render_disease():
    return render_template('disease.html')



from disease import disease_blueprint
# Register the blueprint
app.register_blueprint(disease_blueprint)



client = MongoClient(app.config["MONGO_URI"])
db = client["healthcaresystem"]
appointments_collection = db["appointments"]
tests_collection = db["tests"]

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

def send_reminders():
    today = datetime.now().strftime("%Y-%m-%d")
    reminders_sent = []

    # Check for today's appointments
    appointments = appointments_collection.find({"date_time": {"$regex": f"^{today}"}})
    for appointment in appointments:
        subject = "Appointment Reminder"
        body = (f"Hello {appointment['patient_name']},\n\n"
                f"This is a reminder for your appointment today with Dr. {appointment['doctor_name']} "
                f"({appointment['doctor_specialization']}) at {appointment['doctor_hospital']}.\n\n"
                f"Thank you!")
        if send_email(appointment["patient_email"], subject, body):
            reminders_sent.append(f"Appointment reminder sent to {appointment['patient_email']}")

    # Check for today's tests
    tests = tests_collection.find({"test_date": today})
    for test in tests:
        subject = "Test Reminder"
        body = (f"Hello {test['patient_name']},\n\n"
                f"This is a reminder for your {test['test_category']} ({test['test_type']}) scheduled today at "
                f"{test['test_time']} at {test['hospital_name']}.\n\n"
                f"Thank you!")
        if send_email(test["patient_email"], subject, body):
            reminders_sent.append(f"Test reminder sent to {test['patient_email']}")

    print(f"Reminders sent: {reminders_sent}")

# Scheduler configuration
scheduler = BackgroundScheduler()
scheduler.add_job(func=send_reminders, trigger="interval", minutes=180)
scheduler.start()




# Load environment variables from .env file
load_dotenv()


# Decode the Base64 string from the environment variable
firebase_credentials_base64 = os.getenv("FIREBASE_CREDENTIALS_BASE64")
if not firebase_credentials_base64:
    raise ValueError("FIREBASE_CREDENTIALS_BASE64 environment variable is not set.")

# Decode and load the credentials
firebase_credentials = json.loads(b64decode(firebase_credentials_base64))

# Pass the decoded credentials to firebase-admin
cred = credentials.Certificate(firebase_credentials)
initialize_app(cred)

from firebase_admin import messaging

def send_notification(registration_token, title, body):
    # Create a message to send
    message = messaging.Message(
        notification=messaging.Notification(
            title=title,
            body=body,
        ),
        token=registration_token,
    )

    try:
        # Send the message
        response = messaging.send(message)
        print("Successfully sent message:", response)
        return response
    except Exception as e:
        print("Error sending message:", e)
        return None
    
from waiting_list import waiting_list_bp
app.register_blueprint(waiting_list_bp, url_prefix="/waiting-list")


@app.route('/send-notification', methods=['POST'])
def send_notification_endpoint():
    data = request.json
    registration_token = data.get('token')  # Device token
    title = data.get('title')
    body = data.get('body')

    response = send_notification(registration_token, title, body)
    if response:
        return jsonify({"success": True, "response": response}), 200
    else:
        return jsonify({"success": False, "error": "Failed to send notification"}), 500

@app.route('/firebase-messaging-sw.js')
def render_firebase():
    return app.send_static_file('firebase-messaging-sw.js')

from inventory import inventory_bp  
app.register_blueprint(inventory_bp, url_prefix='/inventory')

app.register_blueprint(sos_bp, url_prefix="/")


# Register the blueprint
app.register_blueprint(doctor_bp)


if __name__ == "__main__":
    os.makedirs("uploads", exist_ok=True)
    app.run(host="0.0.0.0", port=8080)  # Correct host and port for Cloud Run




