from flask import Blueprint, request, jsonify

measurements_bp = Blueprint('measurements', __name__)

@measurements_bp.route('/', methods=['POST'])
def save_measurements():
    data = request.get_json() or {}
    return jsonify({"message": "Measurements saved", "measurements": data}), 200
