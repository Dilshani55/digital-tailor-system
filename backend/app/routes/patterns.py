import time
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models.design_image import DesignImage
from app.models.measurement import MeasurementProfile
from app.models.pattern_result import PatternResult
from app.models.session import Session
from app.models.user import User
from app.logic.parametric_engine import ParametricEngine
from app.logic.fabric_recommendation import validate_fabric_id, get_fabric_by_id
from app.logic.taxonomy_map import confirmed_to_cad_features
from app.logic.drafting.ease import DraftingError
from app.logic import feature_schema
from app.logic import measurement_schema as ms
from datetime import datetime, timezone

patterns_bp = Blueprint("patterns", __name__)

MANUAL_IMAGE_IDS = {"manual", "manual-selection", "none"}


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

    # Validate fabric selection. No silent substitution: a missing or unknown
    # fabric id is a client error, never replaced by another fabric.
    raw_fabric_id = data.get("fabric_id") or data.get("selected_fabric_id")
    if not raw_fabric_id:
        return jsonify({
            "error": "fabric_id is required. Select a fabric from the catalog (GET /api/fabric/catalog).",
            "error_code": "FABRIC_ID_REQUIRED",
        }), 400
    if not validate_fabric_id(raw_fabric_id):
        return jsonify({
            "error": f"Unknown fabric_id '{raw_fabric_id}'. Select a fabric from the catalog (GET /api/fabric/catalog).",
            "error_code": "INVALID_FABRIC_ID",
        }), 400
    selected_fab_def = get_fabric_by_id(raw_fabric_id)
    selected_fabric_id = selected_fab_def["id"]
    selected_fabric_name = selected_fab_def["name"]

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

    # 3. Design specification. ONLY the user-confirmed, taxonomy-validated attributes
    #    are canonical. Client-supplied "detected_features" are ignored entirely.
    client_confirmed = data.get("confirmed_attributes")
    is_manual = image_id in MANUAL_IMAGE_IDS

    if is_manual:
        # Manual mode (no image / no classifier): the user's selections ARE the design.
        clean, field_errors = feature_schema.validate_attributes(client_confirmed)
        if field_errors:
            first = next(iter(field_errors.values()))
            return jsonify({
                "error": first["message"],
                "error_code": "INVALID_DESIGN_ATTRIBUTES",
                "field_errors": field_errors,
            }), 400
        design_image = DesignImage.objects(
            user_id   = user,
            file_path = "manual_selection.png"
        ).first()
        if not design_image:
            design_image = DesignImage(
                user_id           = user,
                file_path         = "manual_selection.png",
                detected_features = {},
                confidence_score  = 0.0   # no model ran; nothing to report
            )
        cad = confirmed_to_cad_features(clean)
        design_image.confirmed_attributes = clean
        design_image.detected_features = dict(cad, source="user_confirmed")
        design_image.design_spec = feature_schema.build_design_spec(clean, None, cad)
        design_image.confirmed_at = datetime.now(timezone.utc)
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

    stored_confirmed = getattr(design_image, "confirmed_attributes", None) or {}
    if not all(stored_confirmed.get(h) for h in feature_schema.HEADS):
        return jsonify({
            "error": "Garment features must be confirmed before pattern generation. "
                     "Call POST /api/images/{id}/confirm-attributes first.",
            "error_code": "DESIGN_NOT_CONFIRMED",
        }), 400

    clean, field_errors = feature_schema.validate_attributes(stored_confirmed)
    if field_errors:
        first = next(iter(field_errors.values()))
        return jsonify({
            "error": f"Stored confirmed attributes are invalid: {first['message']}",
            "error_code": "INVALID_DESIGN_ATTRIBUTES",
            "field_errors": field_errors,
        }), 400

    # If the client also sent its confirmed attributes they must equal what is stored,
    # otherwise the user's latest correction was never confirmed on the server.
    if not is_manual and client_confirmed:
        client_clean, _ = feature_schema.validate_attributes(client_confirmed)
        if client_clean != clean:
            return jsonify({
                "error": "The confirmed design sent by the client differs from the confirmed design "
                         "stored on the server. Re-confirm the design features and try again.",
                "error_code": "CONFIRMED_DESIGN_MISMATCH",
                "stored_confirmed_attributes": clean,
            }), 409

    # Unsupported designs are rejected explicitly — never replaced by another design.
    report = feature_schema.support_report(clean, with_scope=True)
    if not report["supported"]:
        return jsonify({
            "error": feature_schema.unsupported_message(report),
            "error_code": "UNSUPPORTED_DESIGN",
            "unsupported_features": report["unsupported"],
        }), 422

    features_dict = confirmed_to_cad_features(clean)
    design_spec = getattr(design_image, "design_spec", None) or {}
    if design_spec.get("attributes") != clean:
        # Confirmed before design_spec existed: rebuild it from the stored prediction + confirmation.
        design_spec = feature_schema.build_design_spec(
            clean, getattr(design_image, "garment_attributes", None), features_dict)
    design_spec["support"] = report      # always reflect the current engine support levels
    design_image.detected_features = dict(features_dict, source="user_confirmed")
    design_image.design_spec = design_spec
    design_image.save()

    # 3b. Body measurements: only validated, canonical-cm values may reach the engine.
    #     Nothing is defaulted — missing/implausible values are field-level errors.
    measurements_dict, m_code, m_errors = ms.engine_measurements(measurement)
    if m_errors:
        return jsonify(ms.error_response_body(m_errors, code=m_code)), 422
    measurements_snapshot = {
        "schema_version": ms.SCHEMA_VERSION,
        "canonical_unit": ms.CANONICAL_UNIT,
        "canonical_cm": {k: measurements_dict[k] for k in ms.FIELD_KEYS},
        "original_values": getattr(measurement, "original_values", None) or {},
        "fabric_type": measurements_dict["fabric_type"],
        "fit_preference": measurements_dict["fit_preference"],
    }

    # 4. Create session to track this generation
    session = Session(
        user_id        = user,
        image_id       = design_image,
        measurement_id = measurement,
        status         = "processing"
    )
    session.save()

    try:
        # 5. Engine input = the validated measurements from step 3b (never defaults).
        # 6–7. Run parametric engine with confirmed CAD features
        t0 = time.perf_counter()
        engine  = ParametricEngine(measurements_dict, features_dict, design_spec=design_spec)
        pattern = engine.generate()
        generation_time_sec = round(time.perf_counter() - t0, 4)

        # 8. Geometry validation. The engine already raised DraftingError if either the base
        #    block or the final pattern failed; these reports are stored as research evidence.
        validation = dict(pattern["validation"]["final_pattern"])
        validation["base_block"] = pattern["validation"]["base_block"]
        validation["passed"] = bool(validation["passed"] and validation["base_block"]["passed"])

        # 9. Save pattern result to MongoDB
        pattern_result = PatternResult(
            session_id          = session,
            pattern_coordinates = pattern["pattern_pieces"],
            yardage_metres      = 0.0,
            garment_type        = pattern["garment_type"],
            selected_fabric_id  = selected_fabric_id,
            selected_fabric_name= selected_fabric_name,
            validation_report   = validation,
            design_spec         = design_spec,
            base_block          = pattern["base_block"],
            measurements_snapshot = measurements_snapshot,
            validation_passed   = bool(validation.get("passed")),
            generation_time_sec = generation_time_sec,
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
            "design_spec":         design_spec,
            "engine_version":      pattern["engine_version"],
            "disclaimer":          pattern["disclaimer"],
            "base_block":          pattern["base_block"],
            "final_pattern":       pattern["final_pattern"],
            "armhole_sleeve":      pattern["armhole_sleeve"],
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
            "measurements_snapshot": measurements_snapshot,
            "construction_notes":  pattern["construction_notes"],
            "next_step": (
                "Call /api/export/yardage/{id} to calculate fabric needed"
                if validation.get("passed")
                else "Fix validation errors before requesting fabric estimate"
            )
        }), status_code

    except DraftingError as e:
        # Unsupported/contradictory design, undraftable measurements or failed geometry validation.
        session.status = "rejected"
        session.save()
        return jsonify(e.to_dict()), 422

    except Exception:
        session.status = "failed"
        session.save()
        current_app.logger.exception("Pattern generation failed")
        return jsonify({"error": "The pattern could not be generated. Please try again.",
                        "error_code": "GENERATION_FAILED"}), 500


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

    from app.models.pdf_export import PdfExport
    exports = PdfExport.objects(pattern_id=pattern).order_by("-exported_at")
    spec = pattern.design_spec or {}
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
        "pattern_pieces": pattern.pattern_coordinates,
        "design_attributes": spec.get("attributes") or {},
        "validation": pattern.validation_report or {},
        "validation_passed": bool(pattern.validation_passed),
        "measurements_snapshot": pattern.measurements_snapshot or {},
        "exports": [{"export_id": str(e.id), "filename": e.file_path, "exported_at": str(e.exported_at)} for e in exports],
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

    sessions = list(Session.objects(user_id=user))
    session_ids = [s.id for s in sessions]
    # customer (measurement profile) of each session, without dereferencing each pattern's session
    profile_of_session = {}
    for s in sessions:
        ref = s._data.get("measurement_id")
        profile_of_session[s.id] = str(getattr(ref, "id", ref)) if ref is not None else None

    patterns = PatternResult.objects(
        session_id__in=session_ids
    ).order_by("-generated_at")

    result = []
    for p in patterns:
        session_ref = p._data.get("session_id")
        result.append({
            "pattern_id":     str(p.id),
            "measurement_id": profile_of_session.get(getattr(session_ref, "id", session_ref)),
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
