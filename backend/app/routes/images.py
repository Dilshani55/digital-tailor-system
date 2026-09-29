import os
from flask import Blueprint, request, jsonify, current_app, send_from_directory
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models.design_image import DesignImage
from app.models.user import User
from app.utils.helpers import allowed_file, save_image, get_image_dimensions

images_bp = Blueprint("images", __name__)


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

    filename = save_image(file, upload_folder)
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

    # 4. Locked workflow: M13 multi-task classifier is the primary AI path
    #    (garment type, neckline, sleeve length, sleeve style only — no CAD drafting).
    garment_attributes = {}
    try:
        from app.ai.multitask_classifier import predict_multitask_features
        garment_attributes = predict_multitask_features(filepath)
    except Exception as e:
        if hasattr(current_app, "logger"):
            current_app.logger.warning(f"Multi-task classification failed: {e}")
        return jsonify({
            "error": "AI garment analysis failed. Check that the multi-task model checkpoint is available."
        }), 500

    # Optional legacy detector — used only for auxiliary CAD hints (darts/seams)
    # until the user confirms attributes. Does not drive the review UI.
    legacy_features = {}
    legacy_confidence = 0.0
    try:
        from app.ai.yolo_detector import detect_features
        legacy_features, legacy_confidence = detect_features(filepath)
    except Exception:
        legacy_features = {}
        legacy_confidence = 0.0

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

    # Provisional CAD features from legacy detector only — overwritten on confirm.
    features = legacy_features or {
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
    design_image.confirmed_at = None
    design_image.confidence_score = pred_confidence or legacy_confidence
    design_image.save()

    return jsonify({
        "message": "Image analysed successfully",
        "image_id": str(design_image.id),
        "detected_features": features,
        "garment_attributes": garment_attributes,
        "confidence_score": design_image.confidence_score,
        "requires_user_confirmation": requires_confirmation,
        "requires_user_verification": requires_confirmation,  # alias for older clients
        "confirmed_attributes": {},
        "status": "analysis complete — confirm garment features before pattern generation"
    }), 200


from datetime import datetime, timezone

ACTIVE_TAXONOMY = {
    "garment_type": ["blouse", "t-shirt", "crop-top"],
    "neckline_type": [
        "round-neck", "v-neck", "square-neck", "scoop-neck", "boat-neck",
        "sweetheart-neck", "halter-neck", "high-neck", "collared-neck", "off-shoulder"
    ],
    "sleeve_length": [
        "sleeveless", "cap-length", "short-sleeve", "elbow-length",
        "three-quarter-sleeve", "long-sleeve"
    ],
    "sleeve_style": [
        "none", "regular-sleeve", "puff-sleeve", "bell-sleeve", "bishop-sleeve",
        "flutter-sleeve", "raglan-sleeve", "dolman-sleeve", "kimono-sleeve"
    ]
}


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

    required_heads = ["garment_type", "neckline_type", "sleeve_length", "sleeve_style"]
    confirmed_data = {}

    for head in required_heads:
        val = data.get(head)
        if not val or not isinstance(val, str):
            return jsonify({"error": f"Missing or invalid attribute '{head}'"}), 400

        val = val.strip()
        if val not in ACTIVE_TAXONOMY[head]:
            return jsonify({
                "error": f"Invalid attribute value '{val}' for '{head}'. Must be one of the active 28-class taxonomy values."
            }), 400

        confirmed_data[head] = val

    # Persist confirmed choices separately from raw AI model predictions
    design_image.confirmed_attributes = confirmed_data
    design_image.confirmed_at = datetime.now(timezone.utc)

    # Sync into detected_features using CAD-compatible (space-form) labels
    from app.logic.taxonomy_map import confirmed_to_cad_features
    cad_features = confirmed_to_cad_features(confirmed_data)
    updated_features = dict(design_image.detected_features or {})
    updated_features.update(cad_features)
    design_image.detected_features = updated_features
    design_image.save()

    return jsonify({
        "message": "Garment attributes confirmed successfully",
        "image_id": str(design_image.id),
        "confirmed_attributes": confirmed_data,
        "detected_features": updated_features,
        "confirmed_at": str(design_image.confirmed_at),
        "status": "confirmed — ready for measurements and pattern generation"
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
