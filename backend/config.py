import os

class Config:
    SECRET_KEY     = os.environ.get("SECRET_KEY", "your-secret-key-here")
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "jwt-secret-key")

    MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/digital_tailor_db")

    MONGODB_SETTINGS = {
        "db":   "digital_tailor_db",
        "host": "localhost",
        "port": 27017
    }

    # Folders
    BASE_DIR       = os.path.abspath(os.path.dirname(__file__))
    UPLOAD_FOLDER  = os.path.join(BASE_DIR, "uploads")
    OUTPUT_FOLDER  = os.path.join(BASE_DIR, "outputs")

    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max upload size
