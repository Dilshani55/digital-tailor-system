from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from app.logic.fabric_recommendation import (
    recommend_fabrics,
    get_all_fabrics,
    get_fabric_by_id,
    validate_fabric_id
)

fabric_bp = Blueprint("fabric", __name__)


@fabric_bp.route("/recommend", methods=["POST"])
@jwt_required(optional=True)
def get_recommendations():
    """
    Returns ranked fabric recommendations based on garment features.
    
    Request payload format (JSON):
    {
        "garment_type": "crop-top",   # optional (defaults to 'blouse')
        "neckline": "off-the-shoulder",# optional
        "sleeves": "short sleeve",   # optional
        "darts": "bust dart",        # optional
        "seams": "side seam"         # optional
    }
    """
    data = request.get_json() or {}
    
    garment_type = data.get("garment_type", "blouse")
    neckline = data.get("neckline")
    sleeves = data.get("sleeves")
    darts = data.get("darts")
    seams = data.get("seams")

    try:
        recommendations = recommend_fabrics(
            garment_type=garment_type,
            neckline=neckline,
            sleeves=sleeves,
            darts=darts,
            seams=seams
        )
        return jsonify({
            "message": "Fabric recommendations generated successfully",
            "garment_features_analyzed": {
                "garment_type": garment_type,
                "neckline": neckline,
                "sleeves": sleeves,
                "darts": darts,
                "seams": seams
            },
            "recommendations": recommendations,
            "total_materials": len(recommendations),
            "recommendation_method": "Explainable Rule-Based Fabric Optimization Engine (AI-Assisted)"
        }), 200

    except Exception as e:
        return jsonify({
            "error": f"Failed to generate fabric recommendations: {str(e)}"
        }), 500


@fabric_bp.route("/catalog", methods=["GET"])
def get_catalog():
    """Returns the full fabric catalog/knowledge base."""
    fabrics = get_all_fabrics()
    return jsonify({
        "total": len(fabrics),
        "fabrics": fabrics
    }), 200


@fabric_bp.route("/<fabric_id>", methods=["GET"])
def get_fabric_details(fabric_id):
    """Retrieves a single fabric definition by ID."""
    fabric = get_fabric_by_id(fabric_id)
    if not fabric:
        return jsonify({"error": f"Fabric with ID '{fabric_id}' not found"}), 404
    return jsonify(fabric), 200
