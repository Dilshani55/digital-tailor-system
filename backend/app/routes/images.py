from flask import Blueprint, request, jsonify

images_bp = Blueprint('images', __name__)

@images_bp.route('/upload', methods=['POST'])
def upload_image():
    if 'image' not in request.files:
        return jsonify({"error": "No image file provided"}), 400
    file = request.files['image']
    return jsonify({"message": "Image uploaded successfully", "filename": file.filename}), 200
