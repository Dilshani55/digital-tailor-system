import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'digital-tailor-secret-key-2026')
    MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017/digital_tailor_db')
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
    OUTPUT_FOLDER = os.path.join(BASE_DIR, 'outputs')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max upload
