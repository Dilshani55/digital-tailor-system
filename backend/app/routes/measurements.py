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
        bust_cm     = float(data["bust_cm"]),
        waist_cm    = float(data["waist_cm"]),
        hip_cm      = float(data["hip_cm"]),
        height_cm   = float(data["height_cm"]),
        fabric_type = data.get("fabric_type", "woven"),
        unit        = data.get("unit", "cm")
    )
    profile.save()

    return jsonify({
        "message": "Measurement profile saved successfully",
        "measurement_id": str(profile.id),
        "profile": {
            "client_name": profile.client_name,
            "bust_cm": profile.bust_cm,
            "waist_cm": profile.waist_cm,
            "hip_cm": profile.hip_cm,
            "height_cm": profile.height_cm,
            "fabric_type": profile.fabric_type
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
        "bust_cm": profile.bust_cm,
        "waist_cm": profile.waist_cm,
        "hip_cm": profile.hip_cm,
        "height_cm": profile.height_cm,
        "fabric_type": profile.fabric_type,
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
            "bust_cm": p.bust_cm,
            "waist_cm": p.waist_cm,
            "hip_cm": p.hip_cm,
            "height_cm": p.height_cm,
            "fabric_type": p.fabric_type,
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
