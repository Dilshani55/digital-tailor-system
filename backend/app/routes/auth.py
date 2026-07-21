from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from app.models.user import User
import bcrypt
from datetime import timedelta

auth_bp = Blueprint("auth", __name__)

# ── REGISTER ──────────────────────────────────────────────────────────────────
@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json() or {}

    # 1. Validate required fields
    required = ["full_name", "email", "password"]
    for field in required:
        if field not in data or not data[field]:
            return jsonify({"error": f"{field} is required"}), 400

    # 2. Check if email already exists
    if User.objects(email=data["email"]).first():
        return jsonify({"error": "Email already registered"}), 409

    # 3. Hash the password
    hashed = bcrypt.hashpw(
        data["password"].encode("utf-8"),
        bcrypt.gensalt()
    ).decode("utf-8")

    # 4. Save new user to MongoDB
    user = User(
        full_name = data["full_name"],
        email     = data["email"],
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
    user = User.objects(email=data["email"]).first()
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
