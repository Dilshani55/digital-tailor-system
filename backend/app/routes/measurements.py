from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models.user import User
from app.models.measurement import MeasurementProfile
from app.logic import measurement_schema as ms

measurements_bp = Blueprint("measurements", __name__)


def _canonical_of(profile):
    """Canonical-cm values currently stored on a profile (None where not measured)."""
    out = {}
    for key in ms.FIELD_KEYS:
        value = getattr(profile, key, None)
        if key == "armhole_depth_cm" and value is None:
            value = getattr(profile, "armhole_cm", None)
        out[key] = value
    return out


def _profile_dict(profile):
    canonical = _canonical_of(profile)
    missing = ms.missing_fields(canonical)
    payload = {
        "client_name": profile.client_name,
        "email": profile.email,
        "notes": profile.notes,
        "fabric_type": profile.fabric_type,
        "fit_preference": getattr(profile, "fit_preference", "standard"),
        "unit": profile.unit,
        "canonical_unit": ms.CANONICAL_UNIT,
        "original_values": getattr(profile, "original_values", None) or {},
        "complete": not missing,
        "missing_fields": missing,
        "measurement_schema_version": getattr(profile, "measurement_schema_version", 1),
    }
    payload.update(canonical)
    payload["armhole_cm"] = canonical["armhole_depth_cm"]   # legacy alias for older clients
    return payload


def _merge(errors, extra):
    for key, items in extra.items():
        errors.setdefault(key, []).extend(items)


def _bad_request(errors):
    return jsonify(ms.error_response_body(errors)), 400


def _choice_errors(data, errors, existing=None):
    """Validate fabric_type / fit_preference when provided (or defaulting on create)."""
    fabric = data.get("fabric_type", None if existing else "woven")
    fit = data.get("fit_preference", None if existing else "standard")
    if fabric is not None and fabric not in ms.FABRIC_TYPES:
        errors["fabric_type"] = [{"code": "INVALID_CHOICE",
                                 "message": f"fabric_type must be one of {', '.join(ms.FABRIC_TYPES)}."}]
    if fit is not None and fit not in ms.FIT_PREFERENCES:
        errors["fit_preference"] = [{"code": "INVALID_CHOICE",
                                    "message": f"fit_preference must be one of {', '.join(ms.FIT_PREFERENCES)}."}]
    return fabric, fit


# ── SCHEMA (fields, canonical unit, ranges) ───────────────────────────────────
@measurements_bp.route("/schema", methods=["GET"])
@jwt_required()
def measurement_schema():
    return jsonify(ms.schema_payload()), 200


# ── SAVE MEASUREMENT PROFILE ──────────────────────────────────────────────────
@measurements_bp.route("/", methods=["POST"])
@jwt_required()
def save_measurements():
    current_user_id = get_jwt_identity()
    user = User.objects(id=current_user_id).first()

    if not user:
        return jsonify({"error": "User not found"}), 404

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Request body must be a JSON object.",
                        "error_code": "INVALID_BODY"}), 400

    errors = {}
    unit, unit_err = ms.normalize_unit(data.get("unit"))
    if unit_err:
        errors["unit"] = [unit_err]
        return _bad_request(errors)

    canonical, original, parse_errors = ms.convert_input(data, unit)
    _merge(errors, parse_errors)
    fabric_type, fit_preference = _choice_errors(data, errors)

    # A profile needs the core four; the remaining nine are needed to generate a pattern.
    for key in ms.CORE_FIELDS:
        if key not in canonical and key not in errors:
            errors[key] = [{"code": "REQUIRED", "message": f"{ms.LABELS[key]} is required."}]

    _merge(errors, ms.validate_canonical(canonical))
    if errors:
        return _bad_request(errors)

    profile = MeasurementProfile(
        user_id     = user,
        client_name = data.get("client_name") or "Customer Profile",
        email       = data.get("email"),
        notes       = data.get("notes", "No notes."),
        fabric_type = fabric_type,
        fit_preference = fit_preference,
        original_values = original,
        unit        = unit,
        measurement_schema_version = ms.SCHEMA_VERSION,
        **canonical,
    )
    if "armhole_depth_cm" in canonical:
        profile.armhole_cm = canonical["armhole_depth_cm"]
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

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Request body must be a JSON object.",
                        "error_code": "INVALID_BODY"}), 400

    errors = {}
    unit, unit_err = ms.normalize_unit(data.get("unit"))
    if unit_err:
        return _bad_request({"unit": [unit_err]})

    canonical_new, original_new, parse_errors = ms.convert_input(data, unit)
    _merge(errors, parse_errors)
    fabric_type, fit_preference = _choice_errors(data, errors, existing=profile)

    # Validate the MERGED profile, but only report problems that involve edited fields.
    merged = {k: v for k, v in _canonical_of(profile).items() if v is not None}
    merged.update(canonical_new)
    _merge(errors, ms.validate_canonical(merged, only=set(canonical_new)))
    if errors:
        return _bad_request(errors)

    for key, value in canonical_new.items():
        setattr(profile, key, value)
    if "armhole_depth_cm" in canonical_new:
        profile.armhole_cm = canonical_new["armhole_depth_cm"]
    if original_new:
        stored = dict(getattr(profile, "original_values", None) or {})
        stored.update(original_new)
        profile.original_values = stored
        profile.unit = unit

    if "client_name" in data:
        profile.client_name = data["client_name"]
    if "email" in data:
        profile.email = data["email"]
    if "notes" in data:
        profile.notes = data["notes"]
    if fabric_type is not None:
        profile.fabric_type = fabric_type
    if fit_preference is not None:
        profile.fit_preference = fit_preference

    profile.save()
    return jsonify({
        "message": "Measurement profile updated successfully",
        "profile_id": str(profile.id),
        "profile": _profile_dict(profile)
    }), 200
