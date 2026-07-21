import os
from flask import Blueprint, request, jsonify, send_file, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models.pattern_result import PatternResult
from app.models.measurement import MeasurementProfile
from app.models.design_image import DesignImage
from app.models.session import Session
from app.models.pdf_export import PdfExport
from app.models.user import User
from app.logic.nesting_algorithm import NestingAlgorithm
from app.logic.pdf_generator import PDFGenerator
from app.logic.parametric_engine import ParametricEngine
from app.logic.ease_rules import apply_ease

export_bp = Blueprint("export", __name__)


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

    data         = request.get_json() or {}
    fabric_width = data.get("fabric_width_cm", 114)

    # Run nesting algorithm
    nester  = NestingAlgorithm(
        pattern_pieces  = pattern.pattern_coordinates,
        fabric_width_cm = fabric_width
    )
    nesting = nester.run()

    # Update pattern with calculated yardage
    pattern.yardage_metres = nesting["yardage_metres"]
    pattern.save()

    return jsonify({
        "message":             "Yardage calculated successfully",
        "pattern_id":          str(pattern.id),
        "fabric_width_cm":     nesting["fabric_width_cm"],
        "fabric_length_cm":    nesting["fabric_length_cm"],
        "yardage_metres":      nesting["yardage_metres"],
        "yardage_yards":       nesting["yardage_yards"],
        "utilisation_percent": nesting["utilisation_percent"],
        "waste_cm2":           nesting["waste_cm2"],
        "total_pieces":        nesting["total_pieces"],
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

    # Check yardage has been calculated
    if pattern.yardage_metres == 0.0:
        # Run nesting algorithm automatically if yardage hasn't been saved yet
        nester  = NestingAlgorithm(
            pattern_pieces  = pattern.pattern_coordinates,
            fabric_width_cm = 114
        )
        nesting = nester.run()
        pattern.yardage_metres = nesting["yardage_metres"]
        pattern.save()

    try:
        # Get session data
        session    = pattern.session_id
        meas_obj   = session.measurement_id
        image_obj  = session.image_id

        measurements = {
            "bust_cm":    meas_obj.bust_cm,
            "waist_cm":   meas_obj.waist_cm,
            "hip_cm":     meas_obj.hip_cm,
            "height_cm":  meas_obj.height_cm,
            "fabric_type": meas_obj.fabric_type
        }
        features = image_obj.detected_features

        # Regenerate nesting data for PDF layout
        nester  = NestingAlgorithm(
            pattern_pieces  = pattern.pattern_coordinates,
            fabric_width_cm = 114
        )
        nesting = nester.run()

        # Rebuild pattern data for PDF (includes construction notes)
        engine       = ParametricEngine(measurements, features)
        pattern_data = engine.generate()

        # Set up output path
        output_dir = current_app.config["OUTPUT_FOLDER"]
        os.makedirs(output_dir, exist_ok=True)
        filename   = f"pattern_{pattern_id}.pdf"
        out_path   = os.path.join(output_dir, filename)

        # Generate PDF
        generator = PDFGenerator(
            pattern_data = pattern_data,
            nesting_data = nesting,
            measurements = measurements,
            features     = features,
            output_path  = out_path
        )
        generator.generate()

        # Save export record to MongoDB
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
        result.append({
            "export_id":   str(e.id),
            "pattern_id":  str(e.pattern_id.id),
            "filename":    e.file_path,
            "download_url": f"/api/export/download/{str(e.id)}",
            "exported_at": str(e.exported_at)
        })

    return jsonify({
        "total":   len(result),
        "exports": result
    }), 200
