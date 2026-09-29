"""
BASE BLOCK stage:
    ValidatedMeasurements -> EaseProfile -> DraftingValues -> BaseBlock -> validate_base_block()

The base block is a fitted waist-length bodice (round neck, hem at the waist line) plus a
full-length plain sleeve. It is NOT a garment pattern; design transformations are applied
afterwards (transformations.py). Prototype, mathematically generated, geometry-validated only.
"""

from app.logic.drafting import bodice, sleeve
from app.logic.drafting.assumptions import assumptions_payload
from app.logic.drafting.drafting_values import compute_drafting_values
from app.logic.drafting.ease import ease_profile_for, DraftingError
from app.logic.drafting.validation import validate_base_block


class BaseBlock:
    def __init__(self, measurements, block, ease, dv, explanation, front, back, sleeve_piece, armhole):
        self.measurements = measurements
        self.block = block
        self.ease = ease
        self.dv = dv
        self.explanation = explanation
        self.front, self.back, self.sleeve = front, back, sleeve_piece
        self.armhole = armhole          # seam-length bookkeeping for the sleeve cap

    @property
    def pieces(self):
        return [self.front, self.back, self.sleeve]

    def to_dict(self):
        return {
            "stage": "base_block",
            "description": "Fitted waist-length bodice + full-length plain sleeve, before design transformations.",
            "block": {"block_id": self.block["block_id"], "block_label": self.block["block_label"]},
            "ease": self.ease.to_dict(),
            "drafting_values": self.explanation,
            "assumptions": assumptions_payload(),
            "armhole": {k: round(v, 3) for k, v in self.armhole.items()},
            "pieces": [p.to_dict() for p in self.pieces],
        }


def draft_base_block(measurements, block, fit_preference="standard"):
    """Draft the base block. Raises DraftingError for measurement sets that cannot be drafted."""
    if measurements.get("fabric_type") == "stretch-knit":
        raise DraftingError(
            "Stretch-knit (negative-ease) drafting is not implemented. Choose woven or knit.",
            code="UNSUPPORTED_FABRIC_TYPE",
            field_errors={"fabric_type": [{"code": "UNSUPPORTED", "message": "stretch-knit is not drafted yet."}]})
    ease = ease_profile_for(block["block_id"], fit_preference)
    dv, explanation = compute_drafting_values(measurements, ease)
    allow_darts = bool(block.get("allow_darts"))

    front = bodice.build_bodice(dv, "front", neck={"shape": "round"}, hem_y=dv.waist_y, block_allows_darts=allow_darts)
    back = bodice.build_bodice(dv, "back", hem_y=dv.waist_y, block_allows_darts=allow_darts)

    front_len = front.meta["armhole_length_cm"]
    back_len = back.meta["armhole_length_cm"]
    total = front_len + back_len
    target = total + dv.sleeve_cap_ease
    cap_h = sleeve.solve_cap_height(dv.bicep_width, target)
    sleeve_piece = sleeve.build_sleeve(dv, cap_h, dv.sleeve_length, name="Sleeve Block", sleeve_kind="full")

    armhole = {
        "front_armhole_seam_cm": front_len, "back_armhole_seam_cm": back_len,
        "total_armhole_seam_cm": total, "target_cap_ease_cm": dv.sleeve_cap_ease,
        "sleeve_cap_seam_cm": sleeve_piece.meta["cap_length_cm"],
        "cap_ease_cm": sleeve_piece.meta["cap_length_cm"] - total,
        "cap_height_cm": cap_h,
    }
    base = BaseBlock(measurements, block, ease, dv, explanation, front, back, sleeve_piece, armhole)
    result = validate_base_block(base)
    base.validation = result
    if not result["passed"]:
        raise DraftingError("Base block failed geometry validation: " + "; ".join(result["errors"]),
                            code="BASE_BLOCK_INVALID", validation=result)
    return base
