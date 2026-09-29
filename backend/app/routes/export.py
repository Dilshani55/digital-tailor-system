import os
from flask import Blueprint, request, jsonify, send_file, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models.pattern_result import PatternResult
from app.models.measurement import MeasurementProfile
from app.models.design_image import DesignImage
from app.models.session import Session
from app.models.pdf_export import PdfExport
from app.models.user import User
from app.logic.nesting_algorithm import estimate_fabric, NestingError
from app.logic.pdf_generator import PDFGenerator
from app.logic.parametric_engine import ParametricEngine
from app.logic import measurement_schema as ms

export_bp = Blueprint("export", __name__)


def _nesting_failure_response(err):
    """Structured 422 for a failed nesting. Never contains a fabric requirement."""
    return jsonify({
        "error": err.message,
        "error_code": err.error_code,
        "nesting_failed": True,
        "nesting_failure": err.details,
    }), 422


def _stored_summary(pattern):
    """
    Real values already stored for a pattern, for the history list. Anything not
    stored is None ("unavailable") — never a placeholder.
    """
    nesting = getattr(pattern, "nesting_summary", None) or {}
    try:
        image = pattern.session_id.image_id
        confirmed = (getattr(image, "confirmed_attributes", None) or {}) if image else {}
    except Exception:
        confirmed = {}
    yardage = getattr(pattern, "yardage_metres", None)
    return {
        "garment_type":     getattr(pattern, "garment_type", None) or None,
        "neckline_type":    confirmed.get("neckline_type"),
        "sleeve_length":    confirmed.get("sleeve_length"),
        "fabric_name":      getattr(pattern, "selected_fabric_name", None) or None,
        "fabric_width_cm":  nesting.get("fabric_width_cm"),
        "cutting_mode":     nesting.get("cutting_mode"),
        "yardage_metres":   yardage if yardage and yardage > 0 else None,
        "utilisation_percent": nesting.get("utilisation_percent"),
    }


_SUMMARY_KEYS = (
    "fabric_width_cm", "usable_width_cm", "cutting_mode", "fabric_length_cm", "exact_yardage_metres",
    "yardage_metres", "total_pattern_piece_area_cm2", "usable_area_cm2", "waste_cm2", "waste_percent",
    "utilisation_percent", "total_pieces", "purchasing_recommended_m", "handling_allowance_m",
)


def _summary_of(nesting):
    return {key: nesting[key] for key in _SUMMARY_KEYS}


# ── CALCULATE YARDAGE ─────────────────────────────────────────────────────────
@export_bp.route("/yardage/<pattern_id>", methods=["POST"])
@jwt_required()
def calculate_yardage(pattern_id):
    current_user_id = get_jwt_identity()

    pattern_id = pattern_id.strip("<>")
    try:
        pattern = PatternResult.objects(id=pattern_id).first()
    except Exception:
        return jsonify({"error": "Invalid pattern_id format"}), 400

    if not pattern:
        return jsonify({"error": "Pattern not found"}), 404

    if str(pattern.session_id.user_id.id) != current_user_id:
        return jsonify({"error": "Unauthorized"}), 403

    # Locked workflow step 8: do not estimate fabric if pattern validation failed
    if getattr(pattern, "validation_passed", True) is False:
        report = getattr(pattern, "validation_report", None) or {}
        return jsonify({
            "error": "Fabric estimation blocked — pattern failed geometric validation.",
            "validation_passed": False,
            "validation": report,
            "errors": report.get("errors", []),
        }), 422

    data         = request.get_json() or {}
    fabric_width = data.get("fabric_width_cm", 114)
    cutting_mode = data.get("cutting_mode", "auto")
    fabric_type  = (getattr(pattern, "measurements_snapshot", None) or {}).get("fabric_type", "woven")

    # Geometry-aware nesting (fails explicitly if any piece cannot be placed)
    try:
        nesting = estimate_fabric(pattern.pattern_coordinates, fabric_width, cutting_mode, fabric_type)
    except NestingError as err:
        return _nesting_failure_response(err)

    # Update pattern with calculated yardage
    pattern.yardage_metres = nesting["yardage_metres"]
    pattern.nesting_summary = _summary_of(nesting)
    pattern.save()

    return jsonify({
        "message":                      "Yardage calculated successfully",
        "pattern_id":                   str(pattern.id),
        "selected_fabric_id":         pattern.selected_fabric_id,
        "selected_fabric_name":       pattern.selected_fabric_name,
        "full_bolt_width_cm":         nesting["full_bolt_width_cm"],
        "usable_width_cm":            nesting["usable_width_cm"],
        "cutting_mode":               nesting["cutting_mode"],
        "cutting_method_simple":        nesting["cutting_method_simple"],
        "fabric_width_cm":            nesting["fabric_width_cm"],
        "fabric_length_cm":           nesting["fabric_length_cm"],
        "exact_yardage_metres":         nesting["exact_yardage_metres"],
        "purchasing_recommended_m":     nesting["purchasing_recommended_m"],
        "handling_allowance_m":         nesting["handling_allowance_m"],
        "yardage_metres":             nesting["yardage_metres"],
        "yardage_yards":              nesting["yardage_yards"],
        "total_pattern_piece_area_cm2": nesting["total_pattern_piece_area_cm2"],
        "total_pattern_piece_area":   nesting["total_pattern_piece_area_cm2"],
        "usable_area_cm2":              nesting["usable_area_cm2"],
        "utilisation_percent":        nesting["utilisation_percent"],
        "waste_percent":              nesting["waste_percent"],
        "waste_cm2":                  nesting["waste_cm2"],
        "usage_status":                 nesting["usage_status"],
        "usage_recommendation":         nesting["usage_recommendation"],
        "total_pieces":               nesting["total_pieces"],
        "placed_pieces":              nesting["placed_pieces"],
        "validation_checks":          nesting["validation_checks"],
        "method":                     nesting["method"],
        "assumptions":                nesting["assumptions"],
        "mode_comparison":            nesting["mode_comparison"],
        "next_step": f"Call /api/export/pdf/{pattern_id} to generate PDF"
    }), 200


# ── GENERATE PDF ──────────────────────────────────────────────────────────────
@export_bp.route("/pdf/<pattern_id>", methods=["POST"])
@jwt_required()
def generate_pdf(pattern_id):
    current_user_id = get_jwt_identity()

    pattern_id = pattern_id.strip("<>")
    try:
        pattern = PatternResult.objects(id=pattern_id).first()
    except Exception:
        return jsonify({"error": "Invalid pattern_id format"}), 400

    if not pattern:
        return jsonify({"error": "Pattern not found"}), 404

    if str(pattern.session_id.user_id.id) != current_user_id:
        return jsonify({"error": "Unauthorized"}), 403

    # Locked workflow step 8: block PDF when geometric validation failed
    if getattr(pattern, "validation_passed", True) is False:
        report = getattr(pattern, "validation_report", None) or {}
        return jsonify({
            "error": "PDF export blocked — pattern failed geometric validation.",
            "validation_passed": False,
            "validation": report,
            "errors": report.get("errors", []),
        }), 422

    snapshot = getattr(pattern, "measurements_snapshot", None) or {}
    fabric_type = snapshot.get("fabric_type", "woven")

    # Fabric layout: reuse the width / mode the user estimated with; otherwise estimate now (114 cm, auto).
    summary = getattr(pattern, "nesting_summary", None) or {}
    width = summary.get("fabric_width_cm") or 114
    mode = summary.get("cutting_mode") or "auto"
    try:
        nesting = estimate_fabric(pattern.pattern_coordinates, width, mode, fabric_type)
    except NestingError as err:
        return _nesting_failure_response(err)
    if not summary:
        pattern.yardage_metres = nesting["yardage_metres"]
        pattern.nesting_summary = _summary_of(nesting)
        pattern.save()

    try:
        session    = pattern.session_id
        image_obj  = session.image_id
        features = {}
        if image_obj:
            image_obj.reload()
            features = image_obj.detected_features or {}

        # The measurements the pattern was GENERATED from (not the profile as it is edited today).
        if snapshot.get("canonical_cm"):
            measurements = dict(snapshot["canonical_cm"], fabric_type=fabric_type,
                                fit_preference=snapshot.get("fit_preference", "standard"))
        else:
            measurements, m_code, m_errors = ms.engine_measurements(session.measurement_id)
            if m_errors:
                return jsonify(ms.error_response_body(m_errors, code=m_code)), 422

        engine       = ParametricEngine(measurements, features, design_spec=(pattern.design_spec or None))
        pattern_data = engine.generate()

        output_dir = current_app.config["OUTPUT_FOLDER"]
        os.makedirs(output_dir, exist_ok=True)
        filename   = f"pattern_{pattern_id}.pdf"
        out_path   = os.path.join(output_dir, filename)

        generator = PDFGenerator(
            pattern_data = pattern_data,
            nesting_data = nesting,
            measurements = measurements,
            features     = features,
            output_path  = out_path,
            fabric_name  = pattern.selected_fabric_name,
            garment_title = f"{(pattern.garment_type or 'garment').title()} sewing pattern",
        )
        generator.generate()

        pdf_export = PdfExport(
            pattern_id = pattern,
            file_path  = filename
        )
        pdf_export.save()

        return jsonify({
            "message":    "PDF generated successfully",
            "export_id":  str(pdf_export.id),
            "pattern_id": pattern_id,
            "filename":   filename,
            "pages":      generator.info["pages"],
            "print_scale": "1:1 (print at 100% / Actual size)",
            "download_url": f"/api/export/download/{str(pdf_export.id)}"
        }), 201

    except Exception as e:
        return jsonify({"error": f"PDF generation failed: {str(e)}"}), 500


# ── DOWNLOAD PDF ──────────────────────────────────────────────────────────────
@export_bp.route("/download/<export_id>", methods=["GET"])
@jwt_required()
def download_pdf(export_id):
    current_user_id = get_jwt_identity()

    export_id = export_id.strip("<>")
    try:
        pdf_export = PdfExport.objects(id=export_id).first()
    except Exception:
        return jsonify({"error": "Invalid export_id format"}), 400

    if not pdf_export:
        return jsonify({"error": "Export not found"}), 404

    # Security check
    if str(pdf_export.pattern_id.session_id.user_id.id) != current_user_id:
        return jsonify({"error": "Unauthorized"}), 403

    output_dir = current_app.config["OUTPUT_FOLDER"]
    file_path  = os.path.join(output_dir, pdf_export.file_path)

    if not os.path.exists(file_path):
        return jsonify({"error": "PDF file not found on server"}), 404

    return send_file(
        file_path,
        mimetype    = "application/pdf",
        as_attachment = True,
        download_name = f"drafting_guide_{export_id}.pdf"
    )


# ── DELETE PDF EXPORT ─────────────────────────────────────────────────────────
@export_bp.route("/<export_id>", methods=["DELETE"])
@jwt_required()
def delete_export(export_id):
    current_user_id = get_jwt_identity()

    export_id = export_id.strip("<>")
    try:
        pdf_export = PdfExport.objects(id=export_id).first()
    except Exception:
        return jsonify({"error": "Invalid export_id format"}), 400

    if not pdf_export:
        return jsonify({"error": "Export not found"}), 404

    # Security check
    if str(pdf_export.pattern_id.session_id.user_id.id) != current_user_id:
        return jsonify({"error": "Unauthorized"}), 403

    # Attempt to delete PDF file from disk
    output_dir = current_app.config["OUTPUT_FOLDER"]
    file_path  = os.path.join(output_dir, pdf_export.file_path)
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
        except Exception:
            pass

    # Delete record from MongoDB
    pdf_export.delete()

    return jsonify({"message": "Export deleted successfully"}), 200


# ── GET ALL EXPORTS FOR USER ──────────────────────────────────────────────────
@export_bp.route("/", methods=["GET"])
@jwt_required()
def get_all_exports():
    current_user_id = get_jwt_identity()
    user = User.objects(id=current_user_id).first()

    if not user:
        return jsonify({"error": "User not found"}), 404

    sessions    = Session.objects(user_id=user)
    session_ids = [s.id for s in sessions]
    patterns    = PatternResult.objects(session_id__in=session_ids)
    pattern_ids = [p.id for p in patterns]
    exports     = PdfExport.objects(
                      pattern_id__in=pattern_ids
                  ).order_by("-exported_at")

    result = []
    for e in exports:
        item = {
            "export_id":   str(e.id),
            "pattern_id":  str(e.pattern_id.id),
            "filename":    e.file_path,
            "download_url": f"/api/export/download/{str(e.id)}",
            "exported_at": str(e.exported_at)
        }
        item.update(_stored_summary(e.pattern_id))
        result.append(item)

    return jsonify({
        "total":   len(result),
        "exports": result
    }), 200
