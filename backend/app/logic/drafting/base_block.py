"""
BASE BLOCK stage:
    ValidatedMeasurements -> EaseProfile -> DraftingValues -> BaseBlock -> validate_base_block()

The base block is the waist-length bodice of the drafting method (front and back drafted separately, round
neck, hem at the waist line) plus, when the design has sleeves, the sleeve cap fitted to the two armholes. It
is NOT a garment pattern; design transformations are applied afterwards (transformations.py). Prototype,
mathematically generated, geometry-validated only.
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
        return [p for p in (self.front, self.back, self.sleeve) if p is not None]

    def to_dict(self):
        return {
            "stage": "base_block",
            "description": "Waist-length bodice of the drafting method (front and back) and, for designs with "
                           "sleeves, the sleeve fitted to the armholes - before design transformations.",
            "block": {"block_id": self.block["block_id"], "block_label": self.block["block_label"]},
            "ease": self.ease.to_dict(),
            "drafting_values": self.explanation,
            "assumptions": assumptions_payload(),
            "armhole": {k: (round(v, 3) if isinstance(v, float) else v) for k, v in self.armhole.items()},
            "pieces": [p.to_dict() for p in self.pieces],
        }


def _f(v):
    return f"{v:.2f}".rstrip("0").rstrip(".")


def draft_base_block(measurements, block, fit_preference="standard"):
    """Draft the base block. Raises DraftingError for measurement sets that cannot be drafted."""
    if measurements.get("fabric_type") == "stretch-knit":
        raise DraftingError(
            "Stretch-knit (negative-ease) drafting is not implemented. Choose woven or knit.",
            code="UNSUPPORTED_FABRIC_TYPE",
            field_errors={"fabric_type": [{"code": "UNSUPPORTED", "message": "stretch-knit is not drafted yet."}]})
    ease = ease_profile_for(block["block_id"], fit_preference)
    dv, explanation = compute_drafting_values(measurements, ease)

    front = bodice.build_bodice(dv, "front", neck={"shape": "round"}, hem_y=dv.waist_y)
    back = bodice.build_bodice(dv, "back", hem_y=dv.waist_y)

    front_len = front.meta["armhole_length_cm"]
    back_len = back.meta["armhole_length_cm"]
    total = front_len + back_len
    armhole = {"front_armhole_seam_cm": front_len, "back_armhole_seam_cm": back_len, "total_armhole_seam_cm": total}

    def row(rid, label, value, formula, source, piece):
        explanation.append({"id": rid, "name": rid, "label": label, "value_cm": round(value, 3), "formula": formula,
                            "source": source, "status": source, "piece": piece})

    row("front_armhole_curve", "Front armhole curve", front_len, "measured along the drafted curve", "method", "front")
    row("back_armhole_curve", "Back armhole curve", back_len, "measured along the drafted curve", "method", "back")
    row("total_armhole", "Total armhole", total, f"front {_f(front_len)} + back {_f(back_len)}", "method", "bodice")

    sleeve_piece = None
    if dv.sleeve_width is not None and dv.sleeve_length is not None:      # the design has sleeves
        fit = sleeve.fit_cap(dv, total)
        cap_h = fit["cap_height_cm"]
        cap_seam = sleeve.cap_length(dv.sleeve_width, cap_h)
        if dv.sleeve_end_width is not None and dv.sleeve_end_width <= dv.sleeve_width + 1e-9:
            sleeve_piece = sleeve.build_sleeve(dv, cap_h, dv.sleeve_length, name="Sleeve Block", sleeve_kind="block")
        armhole.update({
            "target_cap_ease_cm": dv.sleeve_cap_ease,
            "allowed_cap_ease_min_cm": dv.cap_ease_min, "allowed_cap_ease_max_cm": dv.cap_ease_max,
            "sleeve_cap_seam_cm": cap_seam, "cap_ease_cm": cap_seam - total, "cap_height_cm": cap_h,
            "method_cap_height_cm": fit["method_cap_height_cm"], "method_cap_seam_cm": fit["method_cap_seam_cm"],
            "method_cap_ease_cm": fit["method_cap_ease_cm"], "cap_fit": fit["mode"],
        })
        if fit["mode"] == "method":
            row("sleeve_cap_height", "Sleeve cap height", cap_h,
                f"method value kept: cap seam {_f(cap_seam)} - armhole {_f(total)} = {_f(cap_seam - total)} ease "
                f"(accepted {_f(dv.cap_ease_min)} to {_f(dv.cap_ease_max)})", "method", "sleeve")
        else:
            row("sleeve_cap_height", "Sleeve cap height", cap_h,
                f"changed from the method's {_f(fit['method_cap_height_cm'])} (ease would be "
                f"{_f(fit['method_cap_ease_cm'])}) so that cap seam = armhole {_f(total)} + {_f(dv.sleeve_cap_ease)} ease",
                "extension", "sleeve")
        row("sleeve_cap_seam", "Sleeve cap seam", cap_seam, "measured along the drafted cap", "method", "sleeve")
    base = BaseBlock(measurements, block, ease, dv, explanation, front, back, sleeve_piece, armhole)
    result = validate_base_block(base)
    base.validation = result
    if not result["passed"]:
        raise DraftingError("Base block failed geometry validation: " + "; ".join(result["errors"]),
                            code="BASE_BLOCK_INVALID", validation=result)
    return base
