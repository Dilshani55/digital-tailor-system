from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required
from app.logic.fabric_recommendation import get_all_fabrics, get_fabric_by_id
from app.logic.fabric_selection import TRAITS, _gsm, recommend_for_design
from app.logic import feature_schema as fs

fabric_bp = Blueprint("fabric", __name__)


@fabric_bp.route("/recommend", methods=["POST"])
@jwt_required(optional=True)
def get_recommendations():
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not isinstance(data.get("confirmed_attributes"), dict):
        return jsonify({"error": "Confirm the supported design before requesting fabric recommendations.",
                        "error_code": "CONFIRMED_DESIGN_REQUIRED"}), 400
    clean, errors = fs.validate_attributes(data["confirmed_attributes"])
    if errors:
        return jsonify({"error": next(iter(errors.values()))["message"],
                        "error_code": "INVALID_DESIGN_ATTRIBUTES", "field_errors": errors}), 400
    fit = data.get("fit_preference", "standard")
    if fit not in ("close", "standard", "loose"):
        return jsonify({"error": "Choose close, standard or loose fit.", "error_code": "INVALID_FIT"}), 400
    result = recommend_for_design(clean, fit, data_path=current_app.config["FABRIC_RESEARCH_DATA_PATH"],
                                  user_preferences=data.get("user_preferences"))
    if result["ranking_status"] == "invalid_preferences":
        return jsonify({**result, "error": result["ranking_message"], "error_code": "INVALID_FABRIC_PREFERENCES"}), 422
    return jsonify({**result, "recommendations": result["fabrics"],
                    "total_materials": len(result["fabrics"]),
                    "total_recommended": len(result["recommended_ids"]),
                    "recommendation_method": result["method"]}), 200


@fabric_bp.route("/catalog", methods=["GET"])
def get_catalog():
    fabrics = [dict(f, construction=TRAITS[f["id"]][0], gsm_range=_gsm(f),
                    properties_basis="Generic catalogue descriptions; not measured sample data.")
               for f in get_all_fabrics()]
    return jsonify({"total": len(fabrics), "fabrics": fabrics}), 200


@fabric_bp.route("/<fabric_id>", methods=["GET"])
def get_fabric_details(fabric_id):
    fabric = get_fabric_by_id(fabric_id)
    if not fabric:
        return jsonify({"error": f"Fabric with ID '{fabric_id}' not found"}), 404
    return jsonify(fabric), 200
