from flask import Blueprint, request, jsonify

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    return jsonify({"message": "Auth login placeholder", "data": data}), 200

@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json() or {}
    return jsonify({"message": "Auth register placeholder", "data": data}), 201
