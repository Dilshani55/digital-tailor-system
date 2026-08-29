from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models.user import User
from app.models.measurement import MeasurementProfile

measurements_bp = Blueprint("measurements", __name__)

# ── SAVE MEASUREMENT PROFILE ──────────────────────────────────────────────────
@measurements_bp.route("/", methods=["POST"])
@jwt_required()
def save_measurements():
    current_user_id = get_jwt_identity()
    user = User.objects(id=current_user_id).first()

    if not user:
        return jsonify({"error": "User not found"}), 404

    data = request.get_json() or {}

    required = ["bust_cm", "waist_cm", "hip_cm", "height_cm"]
    for field in required:
        if field not in data or data[field] is None:
            return jsonify({"error": f"{field} is required"}), 400

    profile = MeasurementProfile(
        user_id     = user,
        client_name = data.get("client_name", "Customer Profile"),
        email       = data.get("email"),
        notes       = data.get("notes", "No notes."),
        bust_cm     = float(data["bust_cm"]),
        waist_cm    = float(data["waist_cm"]),
        hip_cm      = float(data["hip_cm"]),
        height_cm   = float(data["height_cm"]),
        shoulder_cm = float(data.get("shoulder_cm", 12.0)),
        neck_cm     = float(data.get("neck_cm", 36.0)),
        armhole_cm  = float(data.get("armhole_cm", 20.0)),
        sleeve_cm   = float(data.get("sleeve_cm", 55.0)),
        garment_length_cm = float(data.get("garment_length_cm", 65.0)),
        fabric_type = data.get("fabric_type", "woven"),
        unit        = data.get("unit", "cm")
    )
    profile.save()

    return jsonify({
        "message": "Measurement profile saved successfully",
        "measurement_id": str(profile.id),
        "profile": {
            "client_name": profile.client_name,
            "email": profile.email,
            "notes": profile.notes,
            "bust_cm": profile.bust_cm,
            "waist_cm": profile.waist_cm,
            "hip_cm": profile.hip_cm,
            "height_cm": profile.height_cm,
            "shoulder_cm": profile.shoulder_cm,
            "neck_cm": profile.neck_cm,
            "armhole_cm": profile.armhole_cm,
            "sleeve_cm": profile.sleeve_cm,
            "garment_length_cm": profile.garment_length_cm,
            "fabric_type": profile.fabric_type,
            "unit": profile.unit
        }
    }), 201


# ── GET MEASUREMENT PROFILE ───────────────────────────────────────────────────
@measurements_bp.route("/<measurement_id>", methods=["GET"])
@jwt_required()
def get_measurement(measurement_id):
    current_user_id = get_jwt_identity()

    measurement_id = measurement_id.strip("<>")
    try:
        profile = MeasurementProfile.objects(id=measurement_id).first()
    except Exception:
        return jsonify({"error": "Invalid measurement_id"}), 400

    if not profile:
        return jsonify({"error": "Measurement profile not found"}), 404

    if str(profile.user_id.id) != current_user_id:
        return jsonify({"error": "Unauthorized"}), 403

    return jsonify({
        "measurement_id": str(profile.id),
        "client_name": profile.client_name or "Customer Profile",
        "email": profile.email,
        "notes": profile.notes,
        "bust_cm": profile.bust_cm,
        "waist_cm": profile.waist_cm,
        "hip_cm": profile.hip_cm,
        "height_cm": profile.height_cm,
        "shoulder_cm": profile.shoulder_cm,
        "neck_cm": profile.neck_cm,
        "armhole_cm": profile.armhole_cm,
        "sleeve_cm": profile.sleeve_cm,
        "garment_length_cm": profile.garment_length_cm,
        "fabric_type": profile.fabric_type,
        "unit": profile.unit,
        "created_at": str(profile.created_at)
    }), 200


# ── GET ALL MEASUREMENT PROFILES FOR USER ─────────────────────────────────────
@measurements_bp.route("/", methods=["GET"])
@jwt_required()
def get_all_measurements():
    current_user_id = get_jwt_identity()
    user = User.objects(id=current_user_id).first()

    if not user:
        return jsonify({"error": "User not found"}), 404

    profiles = MeasurementProfile.objects(user_id=user).order_by("-created_at")

    result = []
    for p in profiles:
        result.append({
            "measurement_id": str(p.id),
            "client_name": p.client_name or "Customer Profile",
            "email": p.email,
            "notes": p.notes,
            "bust_cm": p.bust_cm,
            "waist_cm": p.waist_cm,
            "hip_cm": p.hip_cm,
            "height_cm": p.height_cm,
            "shoulder_cm": p.shoulder_cm,
            "neck_cm": p.neck_cm,
            "armhole_cm": p.armhole_cm,
            "sleeve_cm": p.sleeve_cm,
            "garment_length_cm": p.garment_length_cm,
            "fabric_type": p.fabric_type,
            "unit": p.unit,
            "created_at": str(p.created_at)
        })

    return jsonify({
        "total": len(result),
        "measurements": result
    }), 200


# ── DELETE MEASUREMENT PROFILE ────────────────────────────────────────────────
@measurements_bp.route("/<measurement_id>", methods=["DELETE"])
@jwt_required()
def delete_measurement(measurement_id):
    current_user_id = get_jwt_identity()

    measurement_id = measurement_id.strip("<>")
    try:
        profile = MeasurementProfile.objects(id=measurement_id).first()
    except Exception:
        return jsonify({"error": "Invalid measurement_id"}), 400

    if not profile:
        return jsonify({"error": "Measurement profile not found"}), 404

    if str(profile.user_id.id) != current_user_id:
        return jsonify({"error": "Unauthorized"}), 403

    profile.delete()
    return jsonify({"message": "Measurement profile deleted successfully"}), 200


# ── UPDATE MEASUREMENT PROFILE ────────────────────────────────────────────────
@measurements_bp.route("/<measurement_id>", methods=["PUT"])
@jwt_required()
def update_measurement(measurement_id):
    current_user_id = get_jwt_identity()
    measurement_id = measurement_id.strip("<>")
    
    try:
        profile = MeasurementProfile.objects(id=measurement_id).first()
    except Exception:
        return jsonify({"error": "Invalid measurement_id"}), 400

    if not profile:
        return jsonify({"error": "Measurement profile not found"}), 404

    if str(profile.user_id.id) != current_user_id:
        return jsonify({"error": "Unauthorized"}), 403

    data = request.get_json() or {}

    if "client_name" in data:
        profile.client_name = data["client_name"]
    if "email" in data:
        profile.email = data["email"]
    if "notes" in data:
        profile.notes = data["notes"]
    if "bust_cm" in data:
        profile.bust_cm = float(data["bust_cm"])
    if "waist_cm" in data:
        profile.waist_cm = float(data["waist_cm"])
    if "hip_cm" in data:
        profile.hip_cm = float(data["hip_cm"])
    if "height_cm" in data:
        profile.height_cm = float(data["height_cm"])
    if "shoulder_cm" in data:
        profile.shoulder_cm = float(data["shoulder_cm"])
    if "neck_cm" in data:
        profile.neck_cm = float(data["neck_cm"])
    if "armhole_cm" in data:
        profile.armhole_cm = float(data["armhole_cm"])
    if "sleeve_cm" in data:
        profile.sleeve_cm = float(data["sleeve_cm"])
    if "garment_length_cm" in data:
        profile.garment_length_cm = float(data["garment_length_cm"])
    if "fabric_type" in data:
        profile.fabric_type = data["fabric_type"]
    if "unit" in data:
        profile.unit = data["unit"]

    profile.save()
    return jsonify({"message": "Measurement profile updated successfully", "profile_id": str(profile.id)}), 200
