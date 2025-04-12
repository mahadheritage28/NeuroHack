from flask import render_template, redirect, url_for, request, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import re
import requests
from oauthlib.oauth2 import WebApplicationClient

class AuthHandler:
    def __init__(self, mongo):
        self.mongo = mongo
    
    def validate_password(self, password):
        """
        Validates if the password is strong based on the following criteria:
        - At least 8 characters.
        - Contains at least one uppercase letter.
        - Contains at least one lowercase letter.
        - Contains at least one number.
        - Contains at least one special character.
        - Does not contain spaces.
        """
        if len(password) < 8:
            return False
        if not re.search(r"[A-Z]", password):
            return False
        if not re.search(r"[a-z]", password):
            return False
        if not re.search(r"[0-9]", password):
            return False
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
            return False
        if re.search(r"\s", password):
            return False
        return True
    
    def handle_login(self, request):
        if request.method == "POST":
            email = request.form.get("email")
            password = request.form.get("password")
            
            user = self.mongo.db.users.find_one({"email": email})
            
            if user and check_password_hash(user["password"], password):
                session["user_email"] = email
                session["user_id"] = str(user["_id"])
                return jsonify({"success": True, "redirect_url": url_for("home")})
            else:
                return jsonify({"success": False, "message": "Invalid credentials"})
        
        return render_template("login.html")
    
    def handle_signup(self, request):
        if request.method == "POST":
            name = request.form.get("name")
            email = request.form.get("email")
            password = request.form.get("password")
            
            if not self.validate_password(password):
                return jsonify({
                    "success": False,
                    "message": "Password must be at least 8 characters long, include an uppercase letter, a lowercase letter, a number, and a special character."
                })
            
            if self.mongo.db.users.find_one({"email": email}):
                return jsonify({"success": False, "message": "Email already registered. Please log in."})
            
            hashed_password = generate_password_hash(password)
            user = {
                "name": name,
                "email": email,
                "password": hashed_password,
                "phone_number": "",
            }
            
            inserted_user = self.mongo.db.users.insert_one(user)
            
            session["user_email"] = email
            session["user_id"] = str(inserted_user.inserted_id)
            
            return jsonify({"success": True, "redirect_url": url_for("home")})
        
        return jsonify({"success": False, "message": "Invalid request method"})
    
    def get_google_provider_cfg(self, discovery_url):
        return requests.get(discovery_url).json()
    
    REDIRECT_URI = "https://auramed-app-156513904358.us-central1.run.app/login/google/callback"
    
    def handle_google_callback(self, client, request, discovery_url, client_id, client_secret):
        try:
            print("🔹 Google OAuth Callback Started")
            
            code = request.args.get("code")
            if not code:
                print("❌ Error: Missing authorization code")
                return "Error: Missing authorization code", 400
            
            print("✅ Authorization Code Received:", code)
            
            google_provider_cfg = self.get_google_provider_cfg(discovery_url)
            token_endpoint = google_provider_cfg["token_endpoint"]
            
            print("🔹 Preparing Token Request...")
            
            token_url, headers, body = client.prepare_token_request(
                token_endpoint,
                authorization_response=request.url,
                redirect_uri=self.REDIRECT_URI,
                code=code,
            )
            
            print("🔹 Sending Token Request to:", token_url)
            
            token_response = requests.post(
                token_url, headers=headers, data=body, auth=(client_id, client_secret)
            )
            
            print("🔹 Token Response Status:", token_response.status_code)
            if token_response.status_code != 200:
                print("❌ OAuth Error:", token_response.text)
                return f"OAuth Error: {token_response.text}", 500
            
            client.parse_request_body_response(token_response.text)
            
            userinfo_endpoint = google_provider_cfg["userinfo_endpoint"]
            uri, headers, body = client.add_token(userinfo_endpoint)
            userinfo_response = requests.get(uri, headers=headers, data=body)
            
            user_info = userinfo_response.json()
            email = user_info.get("email")
            name = user_info.get("name", "User")
            
            print(f"✅ User Info Received: {name} ({email})")
            
            if not email:
                return "OAuth Error: Email not received", 500
            
            user = self.mongo.db.users.find_one({"email": email})
            if not user:
                print("🔹 New User Detected - Creating Account...")
                user_id = self.mongo.db.users.insert_one({
                    "name": name,
                    "email": email,
                    "password": None,
                    "phone_number": "",
                }).inserted_id
            else:
                print("🔹 Existing User Found")
                user_id = user["_id"]
            
            session["user_email"] = email
            session["user_id"] = str(user_id)
            print("✅ Login Successful - Redirecting to Home")
            
            return redirect(url_for("home"))
        
        except Exception as e:
            print("❌ OAuth Exception:", str(e))
            return "Internal Server Error", 500