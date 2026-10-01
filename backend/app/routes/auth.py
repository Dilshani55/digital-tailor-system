from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from app.models.user import User
import bcrypt
import json
import re
import urllib.parse
import urllib.request
from datetime import timedelta
from flask import current_app

auth_bp = Blueprint("auth", __name__)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MIN_PASSWORD_LENGTH = 8
GOOGLE_TOKENINFO = "https://oauth2.googleapis.com/tokeninfo?id_token="


def verify_google_credential(credential, client_id):
    """Returns Google's verified claims for an ID token issued to OUR client id, else None."""
    try:
        with urllib.request.urlopen(GOOGLE_TOKENINFO + urllib.parse.quote(credential), timeout=8) as resp:
            claims = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None
    if claims.get("aud") != client_id or str(claims.get("email_verified")).lower() != "true" or not claims.get("email"):
        return None
    return claims

def _find_user(*emails):
    """First user matching any of the given e-mails (lower-case first; older accounts may be mixed case)."""
    for e in emails:
        user = User.objects(email=e).first()
        if user:
            return user
    return None


# ── REGISTER ──────────────────────────────────────────────────────────────────
@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json() or {}

    # 1. Validate required fields
    required = ["full_name", "email", "password"]
    for field in required:
        if field not in data or not data[field]:
            return jsonify({"error": f"{field} is required"}), 400

    if not EMAIL_RE.match(str(data["email"]).strip()):
        return jsonify({"error": "Please enter a valid email address."}), 400
    if len(str(data["password"])) < MIN_PASSWORD_LENGTH:
        return jsonify({"error": "Password must be at least 8 characters."}), 400

    # 2. Check if email already exists (e-mail addresses are compared case-insensitively)
    email = str(data["email"]).strip().lower()
    if _find_user(email):
        return jsonify({"error": "Email already registered"}), 409

    # 3. Hash the password
    hashed = bcrypt.hashpw(
        data["password"].encode("utf-8"),
        bcrypt.gensalt()
    ).decode("utf-8")

    # 4. Save new user to MongoDB
    user = User(
        full_name = str(data["full_name"]).strip(),
        email     = email,
        password  = hashed
    )
    user.save()

    # 5. Return success
    return jsonify({
        "message": "Registration successful",
        "user_id": str(user.id),
        "full_name": user.full_name,
        "email": user.email
    }), 201


# ── LOGIN ─────────────────────────────────────────────────────────────────────
@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json() or {}

    # 1. Validate required fields
    if not data.get("email") or not data.get("password"):
        return jsonify({"error": "Email and password are required"}), 400

    # 2. Find user by email
    user = _find_user(str(data["email"]).strip().lower(), str(data["email"]).strip())
    if not user:
        return jsonify({"error": "Invalid email or password"}), 401

    # 3. Check password
    password_match = bcrypt.checkpw(
        data["password"].encode("utf-8"),
        user.password.encode("utf-8")
    )
    if not password_match:
        return jsonify({"error": "Invalid email or password"}), 401

    # 4. Generate JWT token (expires in 24 hours)
    token = create_access_token(
        identity = str(user.id),
        expires_delta = timedelta(hours=24)
    )

    # 5. Return token + user info
    return jsonify({
        "message": "Login successful",
        "token": token,
        "user": {
            "id":        str(user.id),
            "full_name": user.full_name,
            "email":     user.email
        }
    }), 200


# ── GOOGLE LOGIN ──────────────────────────────────────────────────────────────
@auth_bp.route("/google-login", methods=["POST"])
def google_login():
    """Signs in with a Google ID token that Google itself vouches for (never a client-supplied email)."""
    client_id = current_app.config.get("GOOGLE_CLIENT_ID")
    if not client_id:
        return jsonify({"error": "Google sign-in is not set up on this server.",
                        "error_code": "GOOGLE_NOT_CONFIGURED"}), 503
    data = request.get_json(silent=True) or {}
    credential = data.get("credential")
    if not credential or not isinstance(credential, str):
        return jsonify({"error": "A Google sign-in credential is required."}), 400
    claims = verify_google_credential(credential, client_id)
    if not claims:
        return jsonify({"error": "Google could not verify that sign-in. Please try again.",
                        "error_code": "GOOGLE_VERIFICATION_FAILED"}), 401

    email = claims["email"]
    user = User.objects(email=email).first()
    if not user:
        # Google-only account: an unusable random password (nobody can log in with a password)
        import secrets
        hashed = bcrypt.hashpw(secrets.token_hex(32).encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        user = User(full_name=claims.get("name") or email.split("@")[0], email=email, password=hashed)
        user.save()

    token = create_access_token(identity=str(user.id), expires_delta=timedelta(hours=24))
    return jsonify({
        "message": "Google login successful",
        "token": token,
        "user": {"id": str(user.id), "full_name": user.full_name, "email": user.email},
    }), 200


# ── CHANGE PASSWORD (signed-in user, current password required) ──────────────
@auth_bp.route("/change-password", methods=["POST"])
@jwt_required()
def change_password():
    """
    The only way to change a password in the app: the signed-in user proves they know the current one.
    There is deliberately no "forgot password" e-mail flow, because the system has no e-mail service; an
    operator can set a new password on the server with tools/reset_password.py.
    A wrong current password answers 400 (not 401), so the client does not treat it as an expired session.
    """
    user = User.objects(id=get_jwt_identity()).first()
    if not user:
        return jsonify({"error": "User not found"}), 404
    data = request.get_json(silent=True) or {}
    current, new = data.get("current_password"), data.get("new_password")
    if not isinstance(current, str) or not current or not isinstance(new, str) or not new:
        return jsonify({"error": "The current password and a new password are required.",
                        "error_code": "PASSWORD_FIELDS_REQUIRED"}), 400
    if len(new) < MIN_PASSWORD_LENGTH:
        return jsonify({"error": f"The new password must be at least {MIN_PASSWORD_LENGTH} characters.",
                        "error_code": "PASSWORD_TOO_SHORT"}), 400
    if len(new.encode("utf-8")) > 72:                      # bcrypt reads only the first 72 bytes
        return jsonify({"error": "The new password is too long (72 bytes at most).",
                        "error_code": "PASSWORD_TOO_LONG"}), 400
    if not bcrypt.checkpw(current.encode("utf-8"), user.password.encode("utf-8")):
        return jsonify({"error": "The current password is not correct.", "error_code": "CURRENT_PASSWORD_WRONG"}), 400
    if new == current:
        return jsonify({"error": "The new password must be different from the current one.",
                        "error_code": "PASSWORD_UNCHANGED"}), 400
    user.password = bcrypt.hashpw(new.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    user.save()
    return jsonify({"message": "Password changed."}), 200


# ── GET PROFILE (protected route example) ────────────────────────────────────
@auth_bp.route("/profile", methods=["GET"])
@jwt_required()
def profile():
    # Get user ID from JWT token
    current_user_id = get_jwt_identity()
    user = User.objects(id=current_user_id).first()

    if not user:
        return jsonify({"error": "User not found"}), 404

    return jsonify({
        "id":         str(user.id),
        "full_name":  user.full_name,
        "email":      user.email,
        "created_at": str(user.created_at)
    }), 200
