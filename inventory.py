from flask import Blueprint, jsonify, session, request, current_app
from flask_pymongo import PyMongo
from flask_cors import CORS
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import smtplib

inventory_bp = Blueprint('inventory', __name__, template_folder='templates')

CORS(inventory_bp)

@inventory_bp.route('/get_inventory', methods=['GET'])
def get_inventory():
    try:
        hospital_name = session.get('hospital_name')
        if not hospital_name:
            return jsonify({"error": "Unauthorized: No hospital_name in session"}), 401

        current_app.logger.info(f"Fetching inventory for hospital: {hospital_name}")

        db = current_app.mongo.db

        hospital_data = db.hospitals.find_one(
            {"name": hospital_name},
            {"_id": 0, "inventory": 1}
        )

        if not hospital_data or "inventory" not in hospital_data:
            return jsonify({"message": "No inventory found for this hospital"}), 404

        return jsonify(hospital_data["inventory"])

    except Exception as e:
        current_app.logger.error(f"Error fetching inventory: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500


@inventory_bp.route('/update_inventory', methods=['POST'])
def update_inventory():
    try:
        hospital_name = session.get('hospital_name')
        if not hospital_name:
            return jsonify({"error": "Unauthorized: No hospital_name in session"}), 401

        data = request.json
        if not data or "inventory" not in data:
            return jsonify({"error": "Invalid data: 'inventory' field is required"}), 400

        # Validate each item in the inventory
        for item in data["inventory"]:
            if not all(key in item for key in ["name", "category", "stock"]):
                return jsonify({"error": "Invalid inventory format"}), 400

        db = current_app.mongo.db
        result = db.hospitals.update_one(
            {"name": hospital_name},
            {"$set": {"inventory": data["inventory"]}}
        )

        if result.matched_count == 0:
            return jsonify({"error": "Hospital not found"}), 404

        return jsonify({"message": "Inventory updated successfully!"})

    except Exception as e:
        current_app.logger.error(f"Error updating inventory: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500



def send_low_inventory_reminders(app):
    with app.app_context():
        try:
            db = app.mongo.db
            hospitals = db.hospitals.find({}, {"name": 1, "email": 1, "inventory": 1, "_id": 0})

            smtp_server = "smtp.gmail.com"
            smtp_port = 587
            sender_email = "auramed1628@gmail.com"
            sender_password = "kxmg wngq ksyp pzss"

            for hospital in hospitals:
                low_stock_items = []
                hospital_name = hospital["name"]
                email = hospital.get("email")
                inventory = hospital.get("inventory", [])

                # Check low stock items across all categories
                for item in inventory:
                    if item.get("quantity", 0) < 10:  # Use 'quantity' instead of 'stock'
                        low_stock_items.append(f"{item['category'].capitalize()}: {item['name']} (Quantity: {item['quantity']})")

                if low_stock_items and email:
                    subject = f"Low Inventory Alert for {hospital_name}"
                    body = (
                        f"Dear {hospital_name},\n\n"
                        "The following items in your inventory are low in stock:\n\n"
                        + "\n".join(low_stock_items)
                        + "\n\nPlease restock these items at the earliest.\n\nBest Regards,\nInventory Management Team"
                    )

                    try:
                        message = MIMEMultipart()
                        message["From"] = sender_email
                        message["To"] = email
                        message["Subject"] = subject
                        message.attach(MIMEText(body, "plain"))

                        with smtplib.SMTP(smtp_server, smtp_port) as server:
                            server.starttls()
                            server.login(sender_email, sender_password)
                            server.sendmail(sender_email, email, message.as_string())

                        app.logger.info(f"Low inventory reminder sent to {email}")
                    except Exception as e:
                        app.logger.error(f"Error sending email to {email}: {e}")

        except Exception as e:
            app.logger.error(f"Error in send_low_inventory_reminders: {str(e)}")
