from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models.design_image import DesignImage
from app.models.measurement import MeasurementProfile
from app.models.pattern_result import PatternResult
from app.models.session import Session
from app.models.user import User
from app.logic.parametric_engine import ParametricEngine
from app.logic.fabric_recommendation import validate_fabric_id, get_fabric_by_id

patterns_bp = Blueprint("patterns", __name__)


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

    # 3. Fetch design image and its features
    custom_features = data.get("detected_features") or {}

    if image_id in ["manual", "manual-selection", "none"]:
        design_image = DesignImage.objects(
            user_id   = user,
            file_path = "manual_selection.png"
        ).first()
        if not design_image:
            design_image = DesignImage(
                user_id           = user,
                file_path         = "manual_selection.png",
                detected_features = custom_features,
                confidence_score  = 1.0
            )
            design_image.save()
        elif custom_features and isinstance(custom_features, dict):
            updated_features = dict(design_image.detected_features or {})
            updated_features.update(custom_features)
            design_image.update(set__detected_features=updated_features)
            design_image.reload()
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

        if custom_features and isinstance(custom_features, dict):
            updated_features = dict(design_image.detected_features or {})
            updated_features.update(custom_features)
            design_image.update(set__detected_features=updated_features)
            design_image.reload()


    if not design_image.detected_features:
        return jsonify({
            "error": "Image has not been analysed yet. Call /api/images/{id}/analyse first."
        }), 400

    # 4. Create session to track this generation
    session = Session(
        user_id        = user,
        image_id       = design_image,
        measurement_id = measurement,
        status         = "processing"
    )
    session.save()

    try:
        # 5. Build measurement dict for engine
        measurements_dict = {
            "bust_cm":    measurement.bust_cm,
            "waist_cm":   measurement.waist_cm,
            "hip_cm":     measurement.hip_cm,
            "height_cm":  measurement.height_cm,
            "fabric_type": measurement.fabric_type
        }

        # 6. Build features dict from YOLOv8 output / user selections
        features_dict = design_image.detected_features

        # 7. Run parametric engine
        engine  = ParametricEngine(measurements_dict, features_dict)
        pattern = engine.generate()

        # 8. Save pattern result to MongoDB
        pattern_result = PatternResult(
            session_id          = session,
            pattern_coordinates = pattern["pattern_pieces"],
            yardage_metres      = 0.0,   # filled by nesting algorithm in Part 8
            garment_type        = pattern["garment_type"],
            selected_fabric_id  = selected_fabric_id,
            selected_fabric_name= selected_fabric_name
        )
        pattern_result.save()

        # 9. Update session status
        session.status = "complete"
        session.save()

        # 10. Return pattern data
        return jsonify({
            "message":             "Pattern generated successfully",
            "pattern_id":          str(pattern_result.id),
            "session_id":          str(session.id),
            "garment_type":        pattern["garment_type"],
            "fabric_type":         pattern["fabric_type"],
            "selected_fabric_id":   selected_fabric_id,
            "selected_fabric_name": selected_fabric_name,
            "pieces_count":        len(pattern["pattern_pieces"]),
            "pieces": [
                {
                    "name":         p["name"],
                    "width_cm":     p["bounding_box"]["width_cm"],
                    "height_cm":    p["bounding_box"]["height_cm"],
                    "seam_allowance_cm": p["seam_allowance_cm"]
                }
                for p in pattern["pattern_pieces"]
            ],
            "measurements_used":   pattern["measurements_used"],
            "construction_notes":  pattern["construction_notes"],
            "next_step": "Call /api/patterns/{id}/yardage to calculate fabric needed"
        }), 201

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
