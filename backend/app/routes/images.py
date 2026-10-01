import time
import os
from flask import Blueprint, request, jsonify, current_app, send_from_directory
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models.design_image import DesignImage
from app.models.user import User
from app.utils.helpers import allowed_file, save_image, get_image_dimensions, InvalidImageError
from app.logic import feature_schema

images_bp = Blueprint("images", __name__)

MODEL_UNAVAILABLE_MESSAGE = (
    "The AI garment model is not available on this server, so the photo cannot be analysed. "
    "You can still choose the design manually."
)


def _model_unavailable():
    return jsonify({"error": MODEL_UNAVAILABLE_MESSAGE, "error_code": "MODEL_UNAVAILABLE"}), 503


# ── AI MODEL STATUS ───────────────────────────────────────────────────────────
@images_bp.route("/model-status", methods=["GET"])
@jwt_required()
def get_model_status():
    """Tells the client, truthfully, whether photo analysis is possible (no internal paths exposed)."""
    try:
        from app.ai.garment_models import models_status
        status = models_status()
    except Exception as e:
        current_app.logger.warning(f"Model code unavailable: {e}")
        status = {"available": False}
    if not status.get("available"):
        return jsonify({"available": False, "message": MODEL_UNAVAILABLE_MESSAGE}), 200
    return jsonify({
        "available": True,
        "complete": status.get("complete"),
        "model_type": status.get("model_type"),
        "model_version": status.get("model_version"),
        "checkpoint_sha256": status.get("checkpoint_sha256"),
        # per feature: is its model there, which architecture, and is it ever answered automatically
        "models": {head: {"available": m["available"], "architecture": m["architecture"], "sha256": m.get("sha256"),
                          "answers_automatically": status["thresholds"].get(head) is not None}
                   for head, m in status.get("models", {}).items()},
    }), 200


# ── UPLOAD DESIGN IMAGE ───────────────────────────────────────────────────────
@images_bp.route("/upload", methods=["POST"])
@jwt_required()
def upload_image():
    current_user_id = get_jwt_identity()
    user = User.objects(id=current_user_id).first()

    if not user:
        return jsonify({"error": "User not found"}), 404

    # 1. Check if file exists in request
    file = None
    if "image" in request.files:
        file = request.files["image"]
    elif len(request.files) > 0:
        file = list(request.files.values())[0]

    if not file or file.filename == "":
        return jsonify({"error": "No image file provided"}), 400

    # 3. Check file extension
    if not allowed_file(file.filename):
        return jsonify({
            "error": "Invalid file type. Only JPG, JPEG, PNG, WEBP allowed"
        }), 400

    # 4. Save image to uploads folder
    upload_folder = current_app.config["UPLOAD_FOLDER"]
    os.makedirs(upload_folder, exist_ok=True)

    try:
        filename = save_image(file, upload_folder)
    except InvalidImageError as err:
        return jsonify({"error": str(err), "error_code": "INVALID_IMAGE"}), 400
    filepath = os.path.join(upload_folder, filename)

    # 5. Get image dimensions
    width, height = get_image_dimensions(filepath)

    # 6. Save record to MongoDB
    design_image = DesignImage(
        user_id             = user,
        file_path           = filename,
        detected_features   = {},     # empty for now — YOLOv8 fills this later
        confidence_score    = 0.0
    )
    design_image.save()

    return jsonify({
        "message":    "Image uploaded successfully",
        "image_id":   str(design_image.id),
        "filename":   filename,
        "dimensions": {
            "width":  width,
            "height": height
        },
        "status": "uploaded — ready for analysis"
    }), 201


def _locate_garment(filepath):
    """
    Finds the garment so the models see a garment crop, as they did in training (whole photos are less
    accurate - docs/AI_EVIDENCE.md). Never raises: without a detector or a confident box the full image is used.
    """
    region = {"detector_available": False, "detected_class": None, "detector_score": None, "box_xyxy": None,
              "crop_box_xyxy": None, "used": "full_image", "supported_garment": None, "note": None}
    try:
        from PIL import Image, ImageOps
        from app.ai import garment_detector as gd
        d = gd.detect_garment(filepath)
        region.update(detector_available=d["available"], detected_class=d["class"], detector_score=d["score"],
                      box_xyxy=d["box_xyxy"], note=d.get("reason"))
        if d["box_xyxy"]:
            with Image.open(filepath) as im:
                w, h = ImageOps.exif_transpose(im).size
            region["crop_box_xyxy"] = [round(v, 1) for v in gd.pad_box(d["box_xyxy"], w, h)]
            region["used"] = "garment_crop"
            region["supported_garment"] = d["class"] == gd.SUPPORTED_CLASS
            if not region["supported_garment"]:
                region["note"] = (f"This photo looks like {'a dress' if d['class'] == 'dress' else 'outerwear (jacket/coat)'}. "
                                  "Only blouses and T-shirts can be drafted; the suggestions below may not apply.")
    except Exception as e:  # noqa: BLE001 - detection is optional; the classifier still runs on the full image
        current_app.logger.warning(f"Garment detection skipped: {e}")
        region["note"] = "Garment detection unavailable; the whole photo was analysed."
    return region


# ── ANALYSE IMAGE WITH YOLOV8 ─────────────────────────────────────────────────
@images_bp.route("/<image_id>/analyse", methods=["POST"])
@jwt_required()
def analyse_image(image_id):
    current_user_id = get_jwt_identity()

    image_id = image_id.strip("<>")
    try:
        design_image = DesignImage.objects(id=image_id).first()
    except Exception:
        return jsonify({"error": "Invalid or missing image_id"}), 400

    if not design_image:
        return jsonify({"error": "Image not found"}), 404

    # 2. Security check
    if str(design_image.user_id.id) != current_user_id:
        return jsonify({"error": "Unauthorized"}), 403

    # 3. Check image file exists on disk
    upload_folder = current_app.config["UPLOAD_FOLDER"]
    filepath = os.path.join(upload_folder, design_image.file_path)

    if not os.path.exists(filepath):
        return jsonify({"error": "Image file not found on server"}), 404

    # 4. The four garment models suggest garment type, neckline, sleeve length and sleeve style. They only
    #    suggest: the user confirms the design, and only the confirmed design reaches the pattern engine.
    garment_attributes = {}
    try:
        from app.ai.garment_models import GarmentModelError, models_status, predict_attributes
    except Exception as e:  # torch/ultralytics not installed
        current_app.logger.warning(f"Model code unavailable: {e}")
        return _model_unavailable()
    try:
        if not models_status()["available"]:
            return _model_unavailable()
    except Exception as e:
        current_app.logger.warning(f"Garment models unavailable: {e}")
        return _model_unavailable()
    try:
        t0 = time.perf_counter()
        garment_region = _locate_garment(filepath)
        garment_attributes = predict_attributes(filepath, bbox=garment_region["crop_box_xyxy"])
        garment_attributes["garment_region"] = garment_region
        analysis_time_sec = round(time.perf_counter() - t0, 4)
        # Keep every genuine prediction; only ADD scope flags.
        garment_attributes = feature_schema.annotate_predictions(garment_attributes)
    except GarmentModelError as e:
        current_app.logger.warning(f"Image could not be analysed: {e}")
        return jsonify({
            "error": "This photo could not be analysed. Try another photo or choose the design manually.",
            "error_code": "IMAGE_NOT_ANALYSABLE",
        }), 422
    except Exception as e:
        current_app.logger.warning(f"Garment analysis failed: {e}")
        return jsonify({
            "error": "AI garment analysis failed. Please choose the design manually.",
            "error_code": "ANALYSIS_FAILED",
        }), 500

    predictions = (garment_attributes or {}).get("predictions") or {}
    pred_confidence = 0.0
    conf_values = [
        (predictions.get(h) or {}).get("confidence")
        for h in ("garment_type", "neckline_type", "sleeve_length", "sleeve_style")
    ]
    conf_values = [c for c in conf_values if isinstance(c, (int, float))]
    if conf_values:
        pred_confidence = sum(conf_values) / len(conf_values)

    requires_confirmation = bool(
        (garment_attributes or {}).get("requires_user_confirmation", True)
    )

    # Neutral placeholders until the user confirms the design (overwritten on confirm); explicitly
    # flagged as "not detected" and never presented as analysis results.
    features = {
        "source": "default_not_detected",
        "neckline": "round neck",
        "sleeves": "short sleeve",
        "darts": "bust dart",
        "seams": "side seam",
        "garment_type": "blouse",
    }

    # 5. Persist predictions; clear any prior confirmation (re-analyse resets gate)
    design_image.detected_features = features
    design_image.garment_attributes = garment_attributes
    design_image.confirmed_attributes = {}
    design_image.design_spec = {}
    design_image.confirmed_at = None
    # confidence_score = mean top-1 score of the models that answered (a real model output).
    design_image.confidence_score = pred_confidence
    design_image.analysis_time_sec = analysis_time_sec
    design_image.save()

    return jsonify({
        "message": "Image analysed successfully",
        "image_id": str(design_image.id),
        "detected_features": features,
        "garment_attributes": garment_attributes,
        "confidence_score": design_image.confidence_score,
        "confidence_score_definition": "mean top-1 score over the garment models that answered",
        "detected_features_source": features.get("source", "unknown"),
        "requires_user_confirmation": requires_confirmation,
        "requires_user_verification": requires_confirmation,  # alias for older clients
        "unsupported_heads": (garment_attributes or {}).get("unsupported_heads", []),
        "unsupported_message": (garment_attributes or {}).get("unsupported_message"),
        "garment_region": (garment_attributes or {}).get("garment_region"),
        "confirmed_attributes": {},
        "status": "analysis complete — confirm garment features before pattern generation"
    }), 200


from datetime import datetime, timezone

# Single source of truth: app.logic.feature_schema (kept as a dict of lists for older imports).
ACTIVE_TAXONOMY = {head: list(values) for head, values in feature_schema.TAXONOMY.items()}


# ── DESIGN FEATURE SCHEMA (taxonomy + engine support levels) ─────────────────
@images_bp.route("/design-schema", methods=["GET"])
@jwt_required()
def design_schema():
    return jsonify(feature_schema.schema_payload()), 200


# ── GET IMAGE DETAILS ─────────────────────────────────────────────────────────
@images_bp.route("/<image_id>", methods=["GET"])
@jwt_required()
def get_image(image_id):
    current_user_id = get_jwt_identity()

    image_id = image_id.strip("<>")
    try:
        design_image = DesignImage.objects(id=image_id).first()
    except Exception:
        return jsonify({"error": "Invalid or missing image_id"}), 400

    if not design_image:
        return jsonify({"error": "Image not found"}), 404

    if str(design_image.user_id.id) != current_user_id:
        return jsonify({"error": "Unauthorized"}), 403

    return jsonify({
        "image_id":             str(design_image.id),
        "filename":             design_image.file_path,
        "detected_features":    design_image.detected_features,
        "garment_attributes":   getattr(design_image, "garment_attributes", {}),
        "confirmed_attributes": getattr(design_image, "confirmed_attributes", {}),
        "design_spec":          getattr(design_image, "design_spec", {}),
        "confirmed_at":          str(design_image.confirmed_at) if getattr(design_image, "confirmed_at", None) else None,
        "confidence_score":     design_image.confidence_score,
        "uploaded_at":          str(design_image.uploaded_at)
    }), 200


# ── CONFIRM GARMENT ATTRIBUTES (MILESTONE M14) ──────────────────────────────
@images_bp.route("/<image_id>/confirm-attributes", methods=["POST"])
@jwt_required()
def confirm_attributes(image_id):
    current_user_id = get_jwt_identity()

    image_id = image_id.strip("<>")
    try:
        design_image = DesignImage.objects(id=image_id).first()
    except Exception:
        return jsonify({"error": "Invalid or missing image_id"}), 400

    if not design_image:
        return jsonify({"error": "Image not found"}), 404

    if str(design_image.user_id.id) != current_user_id:
        return jsonify({"error": "Unauthorized"}), 403

    data = request.get_json() or {}

    confirmed_data, field_errors = feature_schema.validate_attributes(data)
    if field_errors:
        first = next(iter(field_errors.values()))
        return jsonify({
            "error": first["message"],
            "error_code": "INVALID_DESIGN_ATTRIBUTES",
            "field_errors": field_errors,
        }), 400

    # Persist confirmed choices separately from raw AI model predictions
    design_image.confirmed_attributes = confirmed_data
    design_image.confirmed_at = datetime.now(timezone.utc)

    # Sync into detected_features using CAD-compatible (space-form) labels
    from app.logic.taxonomy_map import confirmed_to_cad_features
    cad_features = confirmed_to_cad_features(confirmed_data)
    updated_features = dict(design_image.detected_features or {})
    updated_features.update(cad_features)
    updated_features["source"] = "user_confirmed"  # darts/seams are rule-derived from garment_type
    design_image.detected_features = updated_features

    # Canonical design specification: confirmed values + provenance (ML vs user-corrected)
    # + rule-based derived features + model/checkpoint metadata + engine support.
    spec = feature_schema.build_design_spec(
        confirmed_data, getattr(design_image, "garment_attributes", None), cad_features)
    design_image.design_spec = spec
    design_image.save()

    return jsonify({
        "message": "Garment attributes confirmed successfully",
        "image_id": str(design_image.id),
        "confirmed_attributes": confirmed_data,
        "detected_features": updated_features,
        "confirmed_at": str(design_image.confirmed_at),
        "design_spec": spec,
        "engine_support": spec["support"],
        "status": (
            "confirmed — ready for measurements and pattern generation"
            if spec["support"]["supported"]
            else "confirmed — but the design contains features the pattern engine cannot draft yet"
        )
    }), 200


# ── GET ALL IMAGES FOR USER ───────────────────────────────────────────────────
@images_bp.route("/", methods=["GET"])
@jwt_required()
def get_all_images():
    current_user_id = get_jwt_identity()
    user = User.objects(id=current_user_id).first()

    if not user:
        return jsonify({"error": "User not found"}), 404

    images = DesignImage.objects(user_id=user).order_by("-uploaded_at")

    result = []
    for img in images:
        result.append({
            "image_id":          str(img.id),
            "filename":          img.file_path,
            "confidence_score":  img.confidence_score,
            "has_features":      bool(img.detected_features),
            "uploaded_at":       str(img.uploaded_at)
        })

    return jsonify({
        "total":  len(result),
        "images": result
    }), 200


# ── SERVE IMAGE FILE ──────────────────────────────────────────────────────────
@images_bp.route("/view/<filename>", methods=["GET"])
@jwt_required()
def view_image(filename):
    """Serves the actual image file so frontend can display it."""
    upload_folder = current_app.config["UPLOAD_FOLDER"]
    return send_from_directory(upload_folder, filename)


# ── DELETE IMAGE ──────────────────────────────────────────────────────────────
@images_bp.route("/<image_id>", methods=["DELETE"])
@jwt_required()
def delete_image(image_id):
    current_user_id = get_jwt_identity()

    image_id = image_id.strip("<>")
    try:
        design_image = DesignImage.objects(id=image_id).first()
    except Exception:
        return jsonify({"error": "Invalid or missing image_id"}), 400

    if not design_image:
        return jsonify({"error": "Image not found"}), 404

    if str(design_image.user_id.id) != current_user_id:
        return jsonify({"error": "Unauthorized"}), 403

    # Delete file from disk
    upload_folder = current_app.config["UPLOAD_FOLDER"]
    filepath = os.path.join(upload_folder, design_image.file_path)
    if os.path.exists(filepath):
        os.remove(filepath)

    # Delete record from MongoDB
    design_image.delete()

    return jsonify({
        "message": "Image deleted successfully"
    }), 200
