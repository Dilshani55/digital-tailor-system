from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models.user import User
from app.models.measurement import MeasurementProfile

measurements_bp = Blueprint("measurements", __name__)

LOCKED_FLOAT_FIELDS = [
    "bust_cm", "waist_cm", "hip_cm", "height_cm",
    "neck_cm", "shoulder_cm", "across_back_cm", "back_waist_length_cm",
    "armhole_cm", "armhole_depth_cm", "garment_length_cm",
    "bicep_cm", "sleeve_cm", "wrist_cm",
]

FIT_OPTIONS = {"close", "standard", "loose"}
FABRIC_OPTIONS = {"woven", "knit", "stretch-knit"}


def _profile_dict(profile):
    return {
        "client_name": profile.client_name,
        "email": profile.email,
        "notes": profile.notes,
        "bust_cm": profile.bust_cm,
        "waist_cm": profile.waist_cm,
        "hip_cm": profile.hip_cm,
        "height_cm": profile.height_cm,
        "neck_cm": getattr(profile, "neck_cm", None),
        "shoulder_cm": getattr(profile, "shoulder_cm", None),
        "across_back_cm": getattr(profile, "across_back_cm", None),
        "back_waist_length_cm": getattr(profile, "back_waist_length_cm", None),
        "armhole_cm": getattr(profile, "armhole_cm", None),
        "armhole_depth_cm": getattr(profile, "armhole_depth_cm", None)
            or getattr(profile, "armhole_cm", None),
        "garment_length_cm": getattr(profile, "garment_length_cm", None),
        "bicep_cm": getattr(profile, "bicep_cm", None),
        "sleeve_cm": getattr(profile, "sleeve_cm", None),
        "wrist_cm": getattr(profile, "wrist_cm", None),
        "fabric_type": profile.fabric_type,
        "fit_preference": getattr(profile, "fit_preference", "standard"),
        "unit": profile.unit,
    }


def _float_or_default(data, key, default):
    val = data.get(key, default)
    if val is None or val == "":
        return float(default)
    return float(val)


# ── SAVE MEASUREMENT PROFILE ──────────────────────────────────────────────────
@measurements_bp.route("/", methods=["POST"])
@jwt_required()
def save_measurements():
    current_user_id = get_jwt_identity()
    user = User.objects(id=current_user_id).first()

    if not user:
        return jsonify({"error": "User not found"}), 404

    data = request.get_json() or {}

    required = [
        "bust_cm", "waist_cm", "hip_cm", "height_cm",
        "neck_cm", "shoulder_cm", "across_back_cm", "back_waist_length_cm",
        "armhole_depth_cm", "garment_length_cm",
        "bicep_cm", "sleeve_cm", "wrist_cm",
    ]
    for field in required:
        if field not in data or data[field] is None or str(data[field]).strip() == "":
            return jsonify({"error": f"{field} is required"}), 400

    fabric_type = data.get("fabric_type", "woven")
    if fabric_type not in FABRIC_OPTIONS:
        return jsonify({"error": f"fabric_type must be one of {sorted(FABRIC_OPTIONS)}"}), 400

    fit_preference = data.get("fit_preference", "standard")
    if fit_preference not in FIT_OPTIONS:
        return jsonify({"error": f"fit_preference must be one of {sorted(FIT_OPTIONS)}"}), 400

    armhole_depth = float(data["armhole_depth_cm"])

    profile = MeasurementProfile(
        user_id     = user,
        client_name = data.get("client_name", "Customer Profile"),
        email       = data.get("email"),
        notes       = data.get("notes", "No notes."),
        bust_cm     = float(data["bust_cm"]),
        waist_cm    = float(data["waist_cm"]),
        hip_cm      = float(data["hip_cm"]),
        height_cm   = float(data["height_cm"]),
        neck_cm     = float(data["neck_cm"]),
        shoulder_cm = float(data["shoulder_cm"]),
        across_back_cm = float(data["across_back_cm"]),
        back_waist_length_cm = float(data["back_waist_length_cm"]),
        armhole_cm  = float(data.get("armhole_cm", armhole_depth)),
        armhole_depth_cm = armhole_depth,
        garment_length_cm = float(data["garment_length_cm"]),
        bicep_cm    = float(data["bicep_cm"]),
        sleeve_cm   = float(data["sleeve_cm"]),
        wrist_cm    = float(data["wrist_cm"]),
        fabric_type = fabric_type,
        fit_preference = fit_preference,
        unit        = data.get("unit", "cm")
    )
    profile.save()

    return jsonify({
        "message": "Measurement profile saved successfully",
        "measurement_id": str(profile.id),
        "profile": _profile_dict(profile)
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

    payload = _profile_dict(profile)
    payload["measurement_id"] = str(profile.id)
    payload["created_at"] = str(profile.created_at)
    return jsonify(payload), 200


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
        item = _profile_dict(p)
        item["measurement_id"] = str(p.id)
        item["created_at"] = str(p.created_at)
        result.append(item)

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

    for field in LOCKED_FLOAT_FIELDS:
        if field in data and data[field] is not None and str(data[field]).strip() != "":
            setattr(profile, field, float(data[field]))

    # Keep armhole_cm in sync when only armhole_depth_cm is sent
    if "armhole_depth_cm" in data and "armhole_cm" not in data:
        profile.armhole_cm = float(data["armhole_depth_cm"])

    if "fabric_type" in data:
        if data["fabric_type"] not in FABRIC_OPTIONS:
            return jsonify({"error": f"fabric_type must be one of {sorted(FABRIC_OPTIONS)}"}), 400
        profile.fabric_type = data["fabric_type"]

    if "fit_preference" in data:
        if data["fit_preference"] not in FIT_OPTIONS:
            return jsonify({"error": f"fit_preference must be one of {sorted(FIT_OPTIONS)}"}), 400
        profile.fit_preference = data["fit_preference"]

    if "unit" in data:
        profile.unit = data["unit"]

    profile.save()
    return jsonify({
        "message": "Measurement profile updated successfully",
        "profile_id": str(profile.id),
        "profile": _profile_dict(profile)
    }), 200
