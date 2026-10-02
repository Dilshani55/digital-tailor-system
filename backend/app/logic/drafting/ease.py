"""
EASE stage:  BODY MEASUREMENT + EASE = GARMENT (pattern) DIMENSION.

Ease is wearing room. It is a separate thing from the seam allowance (seam_allowance.py), which is added
outside the sewing line and does not change the size of the garment.

Woven values come from the drafting source (assumptions.py, "principles of drafting"); knit values are project
presets because the source does not cover knit fabric. Every applied ease is returned so the engine can show
"body + ease = pattern" for each dimension.

Stretch-knit (negative ease) drafting is not implemented and is rejected rather than approximated.
"""

from dataclasses import dataclass, asdict

from app.logic.drafting.assumptions import EASE_PRESETS, FIT_LABELS

WOVEN_BLOCK = "woven_bodice"
KNIT_BLOCK = "knit_bodice"


class DraftingError(Exception):
    """A design/measurement combination that cannot be drafted. Carries a structured payload."""

    def __init__(self, message, code="DRAFTING_FAILED", field_errors=None, **extra):
        super().__init__(message)
        self.message, self.code = message, code
        self.field_errors = field_errors or {}
        self.extra = extra

    def to_dict(self):
        return {"error": self.message, "error_code": self.code,
                "field_errors": self.field_errors, **self.extra}


@dataclass(frozen=True)
class EaseProfile:
    block_id: str
    fit_preference: str
    fit_label: str
    bust_cm: float              # added to the bust around (whole circumference)
    waist_cm: float             # added to the waist around (4 x the per-quarter ease)
    waist_quarter_cm: float     # per quarter pattern, as the source states it
    hip_cm: float
    upper_arm_cm: float         # least ease of the sleeve over the upper arm
    sleeve_end_cm: float        # added to the arm at the sleeve end
    sleeve_cap_cm: float        # target extra length of the sleeve cap over the armhole seam
    cap_ease_min_cm: float      # accepted range of (sleeve cap seam - armhole seam)
    cap_ease_max_cm: float
    status: str                 # "ease" (from the source) or "extension" (project preset)

    def to_dict(self):
        return asdict(self)


def ease_profile_for(block_id, fit_preference="standard"):
    """EaseProfile for a drafting block. Unknown block or fit -> DraftingError (never a default)."""
    if block_id not in EASE_PRESETS:
        raise DraftingError(f"No ease profile for block '{block_id}'.", code="UNSUPPORTED_BLOCK")
    fit = fit_preference or "standard"
    table = EASE_PRESETS[block_id]
    if fit not in FIT_LABELS:
        raise DraftingError(f"Unknown fit preference '{fit}'.", code="INVALID_FIT_PREFERENCE")
    e = table[fit]
    lo, hi = table["cap_ease_range"]
    return EaseProfile(
        block_id=block_id, fit_preference=fit, fit_label=FIT_LABELS[fit],
        bust_cm=e["bust"], waist_cm=4.0 * e["waist_quarter"], waist_quarter_cm=e["waist_quarter"], hip_cm=e["hip"],
        upper_arm_cm=e["upper_arm"], sleeve_end_cm=table["sleeve_end"], sleeve_cap_cm=table["cap_ease_target"],
        cap_ease_min_cm=lo, cap_ease_max_cm=hi, status=table["kind"],
    )
