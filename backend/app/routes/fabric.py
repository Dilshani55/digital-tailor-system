from flask import Blueprint, request, jsonify, current_app
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
    data = request.get_json(silent=True) or {}

    # Design-aware mode: the user-confirmed design (+ fit) -> compatible fabrics, 2-4 recommended.
    if isinstance(data.get("confirmed_attributes"), dict):
        from app.logic import feature_schema as fs
        from app.logic.fabric_selection import recommend_for_design
        clean, errors = fs.validate_attributes(data["confirmed_attributes"])
        if errors:
            first = next(iter(errors.values()))
            return jsonify({"error": first["message"], "error_code": "INVALID_DESIGN_ATTRIBUTES",
                            "field_errors": errors}), 400
        result = recommend_for_design(clean, data.get("fit_preference", "standard"))
        recommended = [f for f in result["fabrics"] if f["recommended"]]
        return jsonify({
            "message": "Fabric recommendations generated successfully",
            **result,
            "recommendations": result["fabrics"],          # compatible fabrics first, recommended ones on top
            "total_materials": len(result["fabrics"]),
            "total_recommended": len(recommended),
            "recommendation_method": result["method"],
        }), 200

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
            "recommendation_method": "Explainable rule-based fabric ranking (deterministic rules, not machine-learned)"
        }), 200

    except Exception:
        current_app.logger.exception("Fabric recommendation failed")
        return jsonify({
            "error": "Fabric recommendations could not be generated. Please try again.",
            "error_code": "RECOMMENDATION_FAILED",
        }), 500


@fabric_bp.route("/catalog", methods=["GET"])
def get_catalog():
    """Returns the full fabric catalog/knowledge base."""
    # construction (woven / knit) and the GSM range are included so a fabric can be chosen before a design is confirmed
    from app.logic.fabric_selection import TRAITS, _gsm
    fabrics = [dict(f, construction=TRAITS[f["id"]][0], gsm_range=_gsm(f)) for f in get_all_fabrics()]
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
