from flask import Blueprint, request, jsonify

export_bp = Blueprint('export', __name__)

@export_bp.route('/pdf', methods=['POST'])
def export_pdf():
    data = request.get_json() or {}
    return jsonify({"message": "PDF export initiated", "export_id": "pdf_12345"}), 200
