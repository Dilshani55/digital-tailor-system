from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models.design_image import DesignImage
from app.models.measurement import MeasurementProfile
from app.models.pattern_result import PatternResult
from app.models.session import Session
from app.models.user import User
from app.logic.parametric_engine import ParametricEngine
from app.logic.fabric_recommendation import validate_fabric_id, get_fabric_by_id
from app.logic.taxonomy_map import confirmed_to_cad_features
from app.logic.pattern_validator import validate_pattern

patterns_bp = Blueprint("patterns", __name__)

MANUAL_IMAGE_IDS = {"manual", "manual-selection", "none"}


def _profile_measurements(measurement):
    """Build the measurement dict passed to ParametricEngine (locked + legacy fields)."""
    return {
        "bust_cm": measurement.bust_cm,
        "waist_cm": measurement.waist_cm,
        "hip_cm": measurement.hip_cm,
        "height_cm": measurement.height_cm,
        "neck_cm": getattr(measurement, "neck_cm", 36.0),
        "shoulder_cm": getattr(measurement, "shoulder_cm", 12.0),
        "across_back_cm": getattr(measurement, "across_back_cm", 34.0),
        "back_waist_length_cm": getattr(measurement, "back_waist_length_cm", 40.0),
        "armhole_depth_cm": getattr(measurement, "armhole_depth_cm", None)
            or getattr(measurement, "armhole_cm", 20.0),
        "armhole_cm": getattr(measurement, "armhole_cm", 20.0),
        "garment_length_cm": getattr(measurement, "garment_length_cm", 65.0),
        "bicep_cm": getattr(measurement, "bicep_cm", 28.0),
        "sleeve_cm": getattr(measurement, "sleeve_cm", 55.0),
        "wrist_cm": getattr(measurement, "wrist_cm", 16.0),
        "fabric_type": measurement.fabric_type,
        "fit_preference": getattr(measurement, "fit_preference", "standard"),
    }


# ── GENERATE PATTERN ──────────────────────────────────────────────────────────
@patterns_bp.route("/generate", methods=["POST"])
@jwt_required()
def generate_pattern():
    current_user_id = get_jwt_identity()
    user = User.objects(id=current_user_id).first()

    if not user:
        return jsonify({"error": "User not found"}), 404

    data = request.get_json() or {}

    # 1. Validate inputs
    if not data.get("measurement_id"):
        return jsonify({"error": "measurement_id is required"}), 400
    if not data.get("image_id"):
        return jsonify({"error": "image_id is required"}), 400

    measurement_id = str(data["measurement_id"]).strip("<>")
    image_id = str(data["image_id"]).strip("<>")

    # Validate fabric selection if provided
    raw_fabric_id = data.get("fabric_id") or data.get("selected_fabric_id") or "cotton-poplin"
    if validate_fabric_id(raw_fabric_id):
        selected_fab_def = get_fabric_by_id(raw_fabric_id)
        selected_fabric_id = selected_fab_def["id"]
        selected_fabric_name = selected_fab_def["name"]
    else:
        # Fallback to default cotton poplin if unrecognised string
        selected_fabric_id = "cotton-poplin"
        selected_fabric_name = "Cotton Poplin"

    # 2. Fetch measurement profile
    try:
        measurement = MeasurementProfile.objects(
            id      = measurement_id,
            user_id = user
        ).first()
    except Exception:
        return jsonify({"error": "Invalid measurement_id format"}), 400

    if not measurement:
        return jsonify({"error": "Measurement profile not found"}), 404

    # 3. Fetch design image and enforce user confirmation (locked workflow step 3)
    custom_features = data.get("detected_features") or {}
    custom_confirmed = data.get("confirmed_attributes") or {}
    is_manual = image_id in MANUAL_IMAGE_IDS

    if is_manual:
        design_image = DesignImage.objects(
            user_id   = user,
            file_path = "manual_selection.png"
        ).first()
        if not design_image:
            design_image = DesignImage(
                user_id           = user,
                file_path         = "manual_selection.png",
                detected_features = {},
                confidence_score  = 1.0
            )
            design_image.save()

        # Manual path: accept confirmed_attributes from client and persist
        heads = ["garment_type", "neckline_type", "sleeve_length", "sleeve_style"]
        if all(custom_confirmed.get(h) for h in heads):
            design_image.confirmed_attributes = {h: custom_confirmed[h] for h in heads}
            design_image.detected_features = confirmed_to_cad_features(
                design_image.confirmed_attributes
            )
            design_image.save()
        elif custom_features and isinstance(custom_features, dict):
            # Accept hyphen taxonomy packed into detected_features from older UI
            packed = {
                "garment_type": custom_features.get("garment_type"),
                "neckline_type": custom_features.get("neckline_type")
                    or custom_features.get("neckline"),
                "sleeve_length": custom_features.get("sleeve_length")
                    or custom_features.get("sleeves"),
                "sleeve_style": custom_features.get("sleeve_style") or "regular-sleeve",
            }
            if all(packed.values()) and "-" in str(packed.get("neckline_type", "")):
                design_image.confirmed_attributes = packed
                design_image.detected_features = confirmed_to_cad_features(packed)
                design_image.save()
            else:
                updated = dict(design_image.detected_features or {})
                updated.update(custom_features)
                design_image.detected_features = updated
                design_image.save()
    else:
        try:
            design_image = DesignImage.objects(
                id      = image_id,
                user_id = user
            ).first()
        except Exception:
            return jsonify({"error": "Invalid image_id format"}), 400

        if not design_image:
            return jsonify({"error": "Design image not found"}), 404

    confirmed = getattr(design_image, "confirmed_attributes", None) or {}
    required_heads = ["garment_type", "neckline_type", "sleeve_length", "sleeve_style"]
    if not all(confirmed.get(h) for h in required_heads):
        return jsonify({
            "error": "Garment features must be confirmed before pattern generation. "
                     "Call POST /api/images/{id}/confirm-attributes first."
        }), 400

    # Prefer CAD features derived from confirmed taxonomy
    features_dict = confirmed_to_cad_features(confirmed)
    design_image.detected_features = features_dict
    design_image.save()

    # 4. Create session to track this generation
    session = Session(
        user_id        = user,
        image_id       = design_image,
        measurement_id = measurement,
        status         = "processing"
    )
    session.save()

    try:
        # 5. Build measurement dict for engine (locked measurement set + legacy)
        measurements_dict = _profile_measurements(measurement)

        # 6–7. Run parametric engine with confirmed CAD features
        engine  = ParametricEngine(measurements_dict, features_dict)
        pattern = engine.generate()

        # 8. Geometric pattern validation (locked workflow step 8)
        validation = validate_pattern(
            pattern["pattern_pieces"],
            garment_type=pattern.get("garment_type", "blouse"),
            fabric_type=pattern.get("fabric_type", "woven"),
            sleeves=features_dict.get("sleeves", "short sleeve"),
            measurements_used=pattern.get("measurements_used"),
            drafting_block=pattern.get("drafting_block"),
        )

        # 9. Save pattern result to MongoDB
        pattern_result = PatternResult(
            session_id          = session,
            pattern_coordinates = pattern["pattern_pieces"],
            yardage_metres      = 0.0,
            garment_type        = pattern["garment_type"],
            selected_fabric_id  = selected_fabric_id,
            selected_fabric_name= selected_fabric_name,
            validation_report   = validation,
            validation_passed   = bool(validation.get("passed")),
        )
        pattern_result.save()

        # 10. Update session status
        session.status = "complete" if validation.get("passed") else "validation_failed"
        session.save()

        status_code = 201
        message = (
            "Pattern generated successfully"
            if validation.get("passed")
            else "Pattern generated but failed geometric validation — fabric estimate blocked"
        )

        # 11. Return pattern data (fabric estimate blocked if validation failed)
        return jsonify({
            "message":             message,
            "pattern_id":          str(pattern_result.id),
            "session_id":          str(session.id),
            "garment_type":        pattern["garment_type"],
            "fabric_type":         pattern["fabric_type"],
            "selected_fabric_id":   selected_fabric_id,
            "selected_fabric_name": selected_fabric_name,
            "pieces_count":        len(pattern["pattern_pieces"]),
            "drafting_block":      pattern.get("drafting_block"),
            "validation":          validation,
            "validation_passed":   bool(validation.get("passed")),
            "fabric_estimate_blocked": not bool(validation.get("passed")),
            "pieces": [
                {
                    "name":         p["name"],
                    "width_cm":     p["bounding_box"]["width_cm"],
                    "height_cm":    p["bounding_box"]["height_cm"],
                    "seam_allowance_cm": p["seam_allowance_cm"],
                    "outline":      p.get("outline"),
                    "grain_line":   p.get("grain_line"),
                    "cut_on_fold":  p.get("cut_on_fold"),
                    "cut_count":    p.get("cut_count"),
                }
                for p in pattern["pattern_pieces"]
            ],
            "pattern_pieces":      pattern["pattern_pieces"],
            "measurements_used":   pattern["measurements_used"],
            "construction_notes":  pattern["construction_notes"],
            "next_step": (
                "Call /api/export/yardage/{id} to calculate fabric needed"
                if validation.get("passed")
                else "Fix validation errors before requesting fabric estimate"
            )
        }), status_code

    except Exception as e:
        session.status = "failed"
        session.save()
        return jsonify({"error": f"Pattern generation failed: {str(e)}"}), 500


# ── GET PATTERN ───────────────────────────────────────────────────────────────
@patterns_bp.route("/<pattern_id>", methods=["GET"])
@jwt_required()
def get_pattern(pattern_id):
    current_user_id = get_jwt_identity()

    pattern_id = pattern_id.strip("<>")
    try:
        pattern = PatternResult.objects(id=pattern_id).first()
    except Exception:
        return jsonify({"error": "Invalid pattern_id format"}), 400

    if not pattern:
        return jsonify({"error": "Pattern not found"}), 404

    # Security check via session → user
    if str(pattern.session_id.user_id.id) != current_user_id:
        return jsonify({"error": "Unauthorized"}), 403

    return jsonify({
        "pattern_id":   str(pattern.id),
        "garment_type": pattern.garment_type,
        "yardage_metres": pattern.yardage_metres,
        "selected_fabric_id": pattern.selected_fabric_id,
        "selected_fabric_name": pattern.selected_fabric_name,
        "nesting_summary": pattern.nesting_summary or {},
        "pieces_count": len(pattern.pattern_coordinates),
        "pieces": [
            {
                "name":      p.get("name"),
                "width_cm":  p.get("bounding_box", {}).get("width_cm"),
                "height_cm": p.get("bounding_box", {}).get("height_cm")
            }
            for p in pattern.pattern_coordinates
        ],
        "generated_at": str(pattern.generated_at)
    }), 200


# ── GET ALL PATTERNS FOR USER ─────────────────────────────────────────────────
@patterns_bp.route("/", methods=["GET"])
@jwt_required()
def get_all_patterns():
    current_user_id = get_jwt_identity()
    user = User.objects(id=current_user_id).first()

    if not user:
        return jsonify({"error": "User not found"}), 404

    sessions = Session.objects(user_id=user)
    session_ids = [s.id for s in sessions]

    patterns = PatternResult.objects(
        session_id__in=session_ids
    ).order_by("-generated_at")

    result = []
    for p in patterns:
        result.append({
            "pattern_id":     str(p.id),
            "garment_type":   p.garment_type,
            "yardage_metres": p.yardage_metres,
            "selected_fabric_id": p.selected_fabric_id,
            "selected_fabric_name": p.selected_fabric_name,
            "nesting_summary": p.nesting_summary or {},
            "pieces_count":   len(p.pattern_coordinates),
            "generated_at":   str(p.generated_at)
        })

    return jsonify({
        "total":    len(result),
        "patterns": result
    }), 200
