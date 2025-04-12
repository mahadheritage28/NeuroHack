import os
import subprocess
import requests
import speech_recognition as sr
from flask import Blueprint, request, jsonify,session
from werkzeug.utils import secure_filename
from twilio.rest import Client
from dotenv import load_dotenv
from pymongo import MongoClient
from datetime import datetime
from googletrans import Translator
import datetime
import time
import threading
from google.cloud import storage
import whisper
from io import BytesIO
import numpy as np
import soundfile as sf
import tempfile
import json

sos_bp = Blueprint("sos", __name__)


# Load environment variables
load_dotenv()

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
GCS_BUCKET_NAME = os.getenv("GCS_BUCKET_NAME")  # Google Cloud Storage Bucket Name

HOSPITAL_PHONE_NUMBERS = ["+918582892588", "+919831455224"]

# Initialize Twilio client
twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# Initialize Flask Blueprint
sos_bp = Blueprint("sos", __name__)

# Explicitly set environment variable
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/app/auramed-455016-7f5675f0113a.json"

# Now create the storage client
storage_client = storage.Client()
bucket = storage_client.bucket(GCS_BUCKET_NAME)  # Use the env-configured bucket


# MongoDB client
mongo_client = MongoClient("mongodb+srv://mahadiqbalaiml27:9Gx_qVZ-tpEaHUu@healthcaresystem.ilezc.mongodb.net/healthcaresystem?retryWrites=true&w=majority&appName=Healthcaresystem")
db = mongo_client["healthcaresystem"]
hospital_collection = db["hospitals"]

@sos_bp.route("/sos/upload", methods=["POST"])
def upload_audio():
    """Handles the audio upload to Google Cloud Storage and sends an SOS."""
    print("📥 Received audio upload request.")

    if "audio" not in request.files:
        print("❌ No audio file found in request.")
        return jsonify({"error": "No audio file uploaded"}), 400

    file = request.files["audio"]
    latitude = request.form.get("latitude")
    longitude = request.form.get("longitude")
    hospital_names = request.form.get("hospitals")  # JSON list of hospital names

    print(f"📍 Received location: Latitude = {latitude}, Longitude = {longitude}")
    print(f"🏥 Received hospital names: {hospital_names}")

    hospital_names = json.loads(hospital_names) if hospital_names else []
    hospital_numbers = []

    if hospital_names:
        print("🔍 Fetching hospital phone numbers from MongoDB...")
        hospitals_data = hospital_collection.find({"name": {"$in": hospital_names}}, {"phone_number": 1, "_id": 0})
        
        for hospital in hospitals_data:
            phone_number = hospital.get("phone_number")
            if phone_number:
                hospital_numbers.append(phone_number)

    if not hospital_numbers:
        print("⚠️ No hospital phone numbers found.")
    else:
        print(f"📞 Sending SOS to: {hospital_numbers}")

    # Upload file to GCS
    blob = bucket.blob(f"sos_audio/{secure_filename(file.filename)}")
    blob.upload_from_file(file, content_type="audio/wav")
    gcs_url = f"https://storage.googleapis.com/{bucket.name}/{blob.name}"
    print(f"✅ Audio uploaded successfully: {gcs_url}")

    # Transcribe and send SOS
    print("📝 Transcribing audio...")
    audio_bytes = blob.download_as_bytes()
    audio_file = BytesIO(audio_bytes)
    emergency_message = transcribe_and_translate(audio_file)

    if latitude and longitude:
        user_address = reverse_geocode(latitude, longitude)
        if user_address:
            emergency_message += f" Sent from Location: {user_address}"
            print(f"📍 User address identified: {user_address}")

    # Send SOS alert to fetched hospital numbers
    send_sos_alert(emergency_message, hospital_numbers)

    return jsonify({
        "message": "SOS sent successfully!",
        "file": file.filename,
        "gcs_url": gcs_url,
        "transcribed_message": emergency_message
    })
def transcribe_and_translate(audio_file):
    """Converts WebM to WAV and transcribes speech."""
    try:
        print("🎙️ Loading Whisper model...")
        model = whisper.load_model("medium")

        # Define a custom temp directory in your project
        temp_dir = os.path.join(os.getcwd(), "temp_files")
        os.makedirs(temp_dir, exist_ok=True)  # Ensure the folder exists

        # Save BytesIO to a WebM file
        webm_path = os.path.join(temp_dir, "sos_audio.webm")
        with open(webm_path, "wb") as f:
            f.write(audio_file.read())

        # Ensure FFmpeg has permission
        os.chmod(webm_path, 0o777)

        # Convert WebM to WAV
        wav_path = os.path.join(temp_dir, "sos_audio.wav")
        convert_cmd = [
            "ffmpeg", "-y", "-i", webm_path,  # Input WebM file
            "-ar", "16000", "-ac", "1", "-f", "wav",  # Convert to 16kHz mono WAV
            wav_path  # Output WAV file
        ]
        
        subprocess.run(convert_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        print(f"✅ Converted WebM to WAV: {wav_path}")

        # Transcribe the WAV file with Whisper
        result = model.transcribe(wav_path, task="translate")

        # Clean up files
        os.remove(webm_path)
        os.remove(wav_path)

        translated_text = result["text"]
        print(f"🌍 Transcription Output: {translated_text}")
        return translated_text

    except subprocess.CalledProcessError as e:
        print(f"🚨 FFmpeg Error: {e.stderr.decode()}")
        return None
    except Exception as e:
        print(f"🚨 Error in transcribe_and_translate: {e}")
        return None
    
def reverse_geocode(latitude, longitude):
    """Gets address from latitude and longitude using Google Maps API."""
    print("📍 Performing reverse geocoding...")
    base_url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {"latlng": f"{latitude},{longitude}", "key": GOOGLE_MAPS_API_KEY}

    try:
        response = requests.get(base_url, params=params)
        if response.status_code == 200:
            data = response.json()
            if data["status"] == "OK":
                address = data["results"][0]["formatted_address"]
                print(f"📍 Address Retrieved: {address}")
                return address
        print("⚠️ Reverse geocoding failed, returning 'Unknown location'.")
        return "Unknown location"
    except Exception as e:
        print(f"🚨 Error in reverse_geocode: {e}")
        return "Unknown location"


def send_sos_alert(emergency_message, hospital_numbers):
    """Sends an SOS alert via Twilio to specified hospitals."""
    print("🚀 Sending emergency alerts to hospitals...")

    if not hospital_numbers:
        print("⚠️ No hospitals found to send SOS alerts.")
        return

    for number in hospital_numbers:
        try:
            print(f"📞 Initiating call to {number}...")
            call = twilio_client.calls.create(
                twiml=f'<Response><Say>{emergency_message}</Say></Response>',
                to=number,
                from_=TWILIO_PHONE_NUMBER
            )
            print(f"✅ Call placed successfully to {number}: {call.sid}")

            print(f"📩 Sending SMS to {number}...")
            message = twilio_client.messages.create(
                body=emergency_message,
                from_=TWILIO_PHONE_NUMBER,
                to=number
            )
            print(f"✅ SMS sent successfully to {number}: {message.sid}")

        except Exception as e:
            print(f"🚨 Twilio Error for {number}: {e}")


reminder_collection = db["medicine_reminders"]


# Update the schedule_reminder endpoint
@sos_bp.route("/schedule-reminder", methods=["POST"])
def schedule_reminder():
    try:
        data = request.json
        reminder = {
            "medicineName": data["medicineName"],
            "days": data["days"],  # List of days (e.g., ["Monday", "Wednesday", "Friday"])
            "times": data["times"],  # List of times (e.g., ["09:00", "14:00", "20:00"])
            "phone": data["phone"],
        }
        reminder_collection.insert_one(reminder)
        return jsonify({"message": "Reminder scheduled successfully!"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Modify the process_reminders function
def process_reminders():
    while True:
        try:
            # Get the current day and time
            current_day = datetime.datetime.now().strftime("%A")  # e.g., "Monday"
            current_time = datetime.datetime.now().strftime("%H:%M")  # e.g., "09:00"

            # Find reminders that match the current day and time
            reminders = reminder_collection.find({"days": current_day, "times": current_time})
            for reminder in reminders:
                message_body = f"Reminder: Take your medicine {reminder['medicineName']} now."
                try:
                    # Send SMS using Twilio
                    twilio_client.messages.create(
                        body=message_body,
                        from_=TWILIO_PHONE_NUMBER,
                        to=reminder["phone"],
                    )
                    print(f"SMS sent to {reminder['phone']} successfully.")
                except Exception as sms_error:
                    print(f"Failed to send SMS to {reminder['phone']}: {sms_error}")

            time.sleep(60)  # Check every minute
        except Exception as e:
            print(f"Error in process_reminders: {e}")



# Start the reminder thread
reminder_thread = threading.Thread(target=process_reminders, daemon=True)
reminder_thread.start()
