from flask import Blueprint, request, jsonify

patterns_bp = Blueprint('patterns', __name__)

@patterns_bp.route('/generate', methods=['POST'])
def generate_pattern():
    data = request.get_json() or {}
    return jsonify({"message": "Pattern generated successfully", "pattern_data": data}), 200
