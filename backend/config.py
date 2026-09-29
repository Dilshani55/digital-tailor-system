import os
import secrets


def _secret(name):
    """Secret from the environment; if absent, a random per-process value (never a shared constant)."""
    return os.environ.get(name) or secrets.token_hex(32)


class Config:
    SECRET_KEY = _secret("SECRET_KEY")
    JWT_SECRET_KEY = _secret("JWT_SECRET_KEY")
    SECRETS_FROM_ENV = bool(os.environ.get("JWT_SECRET_KEY") and os.environ.get("SECRET_KEY"))

    MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/digital_tailor_db")
    MONGO_TIMEOUT_MS = int(os.environ.get("MONGO_TIMEOUT_MS", "5000"))

    CORS_ORIGINS = [o.strip() for o in os.environ.get(
        "CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,http://127.0.0.1:5173"
    ).split(",") if o.strip()]

    GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
    # Comma-separated e-mails allowed to open the researcher dashboard / CSV export (default: nobody)
    RESEARCHER_EMAILS = os.environ.get("RESEARCHER_EMAILS", "")

    # Folders
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER", os.path.join(BASE_DIR, "uploads"))
    OUTPUT_FOLDER = os.environ.get("OUTPUT_FOLDER", os.path.join(BASE_DIR, "outputs"))

    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max upload size
