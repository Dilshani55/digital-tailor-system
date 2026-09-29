"""
EASE stage:  BODY MEASUREMENT + EASE = GARMENT (drafting) DIMENSION.

Ease values are PROJECT ASSUMPTIONS (see assumptions.py / ease_rules.py); they are not taken
from a verified published table. Every applied ease is returned so the engine can explain it.

Only positive-ease woven and knit bodice blocks are drafted. Stretch-knit (negative ease)
drafting is not implemented and is rejected rather than approximated.
"""

from dataclasses import dataclass, asdict

from app.logic.ease_rules import EASE_RULES, FIT_EASE_DELTA
from app.logic.drafting.assumptions import A, ASSUMPTION

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
    fit_delta_cm: float
    bust_cm: float          # total circumference ease at bust  (incl. fit delta)
    waist_cm: float
    hip_cm: float
    bicep_cm: float         # sleeve circumference ease
    wrist_cm: float
    sleeve_cap_cm: float    # target extra length of sleeve cap over the armhole seam
    status: str = ASSUMPTION

    def to_dict(self):
        return asdict(self)


def ease_profile_for(block_id, fit_preference="standard"):
    """EaseProfile for a drafting block. Unknown block or fit -> DraftingError (never a default)."""
    if block_id not in (WOVEN_BLOCK, KNIT_BLOCK):
        raise DraftingError(f"No ease profile for block '{block_id}'.", code="UNSUPPORTED_BLOCK")
    fit = fit_preference or "standard"
    if fit not in FIT_EASE_DELTA:
        raise DraftingError(f"Unknown fit preference '{fit}'.", code="INVALID_FIT_PREFERENCE")
    base = EASE_RULES["woven" if block_id == WOVEN_BLOCK else "knit"]
    delta = FIT_EASE_DELTA[fit]
    sleeve = A["sleeve_ease_cm"][block_id]
    return EaseProfile(
        block_id=block_id, fit_preference=fit, fit_delta_cm=delta,
        bust_cm=base["bust_cm"] + delta, waist_cm=base["waist_cm"] + delta, hip_cm=base["hip_cm"] + delta,
        bicep_cm=sleeve["bicep"], wrist_cm=sleeve["wrist"], sleeve_cap_cm=sleeve["cap"],
    )
