# Use official Python image as base
FROM python:3.9-slim

# Set the working directory
WORKDIR /app

# Copy only requirements file first (for better caching)
COPY requirements.txt .  

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy necessary JSON data file
COPY healthcaresystem.doctors.json /app/

# Copy the rest of the application files
COPY . .

# Ensure spaCy model is downloaded
RUN python -m spacy download en_core_web_sm

# Expose the port Flask runs on
EXPOSE 8080

# Use environment variable for Google Credentials (Do not store it inside the container)
ENV GOOGLE_APPLICATION_CREDENTIALS="/app/auramed-455016-7f5675f0113a.json"

# Run Flask app with Gunicorn (2 workers for better performance)
CMD ["gunicorn", "-b", "0.0.0.0:8080", "--workers=2", "app:app"]
