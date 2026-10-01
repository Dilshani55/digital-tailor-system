"""
DRAFTING-VALUES stage: validated measurements + ease -> the numbers the block is drawn from.

Pure arithmetic, no geometry. Every value is recorded with the formula that produced it and
its source status, so the whole stage can be unit-tested and explained.

`height_cm` is not used by any drafting equation. hip, bicep, sleeve and wrist are only present when the
confirmed design needs them (config/measurement_requirements.json); otherwise their values are None.
"""

import math
from dataclasses import dataclass
from typing import Optional

from app.logic.drafting.assumptions import A, DERIVED, ASSUMPTION
from app.logic.drafting.ease import EaseProfile, DraftingError


@dataclass(frozen=True)
class DraftingValues:
    # garment (eased) circumferences and quarter widths
    garment_bust: float
    garment_waist: float
    garment_hip: Optional[float]   # None when the design does not need the hip (hem above the waist)
    q_bust: float
    q_waist: float
    q_hip: Optional[float]
    # neck / shoulder
    neck_half_width: float
    back_neck_depth: float
    front_neck_depth: float
    shoulder_length: float
    shoulder_slope_deg: float
    across_back_half: float
    # vertical levels (y = 0 at the neck/shoulder-point level, y grows downwards)
    armhole_depth: float
    waist_y: float
    hip_y: float
    # waist shaping
    suppression: float            # q_bust - q_waist (per quarter), may be <= 0
    # sleeve (None for sleeveless designs; wrist only where a sleeve tapers to the wrist)
    sleeve_length: Optional[float]   # wanted sleeve length: shoulder tip to where the sleeve ends
    bicep_width: Optional[float]     # sleeve width at bicep line (bicep + ease)
    wrist_width: Optional[float]
    sleeve_cap_ease: float
    garment_length: float         # measured garment length (final hem level before design rule)


BODICE_KEYS = ("bust_cm", "waist_cm", "neck_cm", "shoulder_cm", "across_back_cm", "back_waist_length_cm",
               "armhole_depth_cm", "garment_length_cm")
OPTIONAL_KEYS = ("hip_cm", "bicep_cm", "sleeve_cm", "wrist_cm")


def compute_drafting_values(m, ease: EaseProfile):
    """m: validated engine measurements (dict, cm). Returns (DraftingValues, explanation list)."""
    def ok(v):
        return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and v > 0

    for key in BODICE_KEYS:
        if not ok(m.get(key)):
            raise DraftingError(f"Measurement '{key}' is missing or invalid.", code="MEASUREMENTS_INVALID",
                                field_errors={key: [{"code": "REQUIRED", "message": f"{key} is required."}]})
    for key in OPTIONAL_KEYS:
        if m.get(key) is not None and not ok(m.get(key)):
            raise DraftingError(f"Measurement '{key}' is invalid.", code="MEASUREMENTS_INVALID",
                                field_errors={key: [{"code": "NOT_POSITIVE", "message": "Must be a number greater than 0."}]})
    has = lambda key: m.get(key) is not None  # noqa: E731

    g_bust = m["bust_cm"] + ease.bust_cm
    g_waist = m["waist_cm"] + ease.waist_cm
    g_hip = m["hip_cm"] + ease.hip_cm if has("hip_cm") else None
    q_bust, q_waist = g_bust / 4.0, g_waist / 4.0
    q_hip = g_hip / 4.0 if g_hip is not None else None

    nw = m["neck_cm"] / 6.0
    back_depth = A["back_neck_depth_cm"]
    front_depth = nw + A["front_neck_extra_depth_cm"]
    ab_half = m["across_back_cm"] / 2.0
    waist_y = back_depth + m["back_waist_length_cm"]

    dv = DraftingValues(
        garment_bust=g_bust, garment_waist=g_waist, garment_hip=g_hip,
        q_bust=q_bust, q_waist=q_waist, q_hip=q_hip,
        neck_half_width=nw, back_neck_depth=back_depth, front_neck_depth=front_depth,
        shoulder_length=m["shoulder_cm"], shoulder_slope_deg=A["shoulder_slope_deg"],
        across_back_half=ab_half,
        armhole_depth=m["armhole_depth_cm"], waist_y=waist_y, hip_y=waist_y + A["hip_depth_below_waist_cm"],
        suppression=q_bust - q_waist,
        sleeve_length=m["sleeve_cm"] if has("sleeve_cm") else None,
        bicep_width=m["bicep_cm"] + ease.bicep_cm if has("bicep_cm") else None,
        wrist_width=m["wrist_cm"] + ease.wrist_cm if has("wrist_cm") else None,
        sleeve_cap_ease=ease.sleeve_cap_cm,
        garment_length=m["garment_length_cm"],
    )
    _check_feasible(dv, m)
    return dv, explain(dv, m, ease)


def _check_feasible(dv, m):
    """Combinations that would give negative / degenerate geometry are rejected, not adjusted."""
    problems = {}
    if dv.armhole_depth >= dv.waist_y - 2.0:
        problems["armhole_depth_cm"] = (
            f"Armhole depth ({dv.armhole_depth:g} cm) must be at least 2 cm above the waist level "
            f"({dv.waist_y:.1f} cm below the shoulder-point level).")
    shoulder_tip_x = dv.neck_half_width + dv.shoulder_length * math.cos(math.radians(dv.shoulder_slope_deg))
    if shoulder_tip_x >= dv.q_bust - 1.0:
        problems["shoulder_cm"] = (
            f"Neck + shoulder ({shoulder_tip_x:.1f} cm from centre) does not fit inside the quarter "
            f"bust width ({dv.q_bust:.1f} cm).")
    if dv.across_back_half >= dv.q_bust - 1.0:
        problems["across_back_cm"] = (
            f"Half across-back width ({dv.across_back_half:.1f} cm) must be smaller than the quarter "
            f"bust width ({dv.q_bust:.1f} cm) — the garment would be narrower than the body.")
    if dv.bicep_width is not None and dv.wrist_width is not None and dv.bicep_width <= dv.wrist_width:
        problems["bicep_cm"] = "Sleeve width at the bicep must exceed the wrist width."
    if problems:
        raise DraftingError(
            "The measurements cannot be drafted into a valid block: " + " ".join(problems.values()),
            code="MEASUREMENTS_NOT_DRAFTABLE",
            field_errors={k: [{"code": "NOT_DRAFTABLE", "message": v}] for k, v in problems.items()})


def explain(dv, m, ease):
    """Human/thesis-readable list of every drafting value: name, value, formula, status."""
    def row(name, value, formula, status):
        return {"name": name, "value_cm": round(value, 3), "formula": formula, "status": status}

    rows = [
        row("garment_bust", dv.garment_bust, f"bust {m['bust_cm']:g} + ease {ease.bust_cm:g}", ASSUMPTION),
        row("garment_waist", dv.garment_waist, f"waist {m['waist_cm']:g} + ease {ease.waist_cm:g}", ASSUMPTION),
    ]
    if dv.garment_hip is not None:
        rows.append(row("garment_hip", dv.garment_hip, f"hip {m['hip_cm']:g} + ease {ease.hip_cm:g}", ASSUMPTION))
    rows += [
        row("q_bust", dv.q_bust, "garment_bust / 4", DERIVED),
        row("q_waist", dv.q_waist, "garment_waist / 4", DERIVED),
    ]
    if dv.q_hip is not None:
        rows.append(row("q_hip", dv.q_hip, "garment_hip / 4", DERIVED))
    rows += [
        row("neck_half_width", dv.neck_half_width, "neck / 6", DERIVED),
        row("back_neck_depth", dv.back_neck_depth, "assumption", ASSUMPTION),
        row("front_neck_depth", dv.front_neck_depth, "neck_half_width + 1.0", ASSUMPTION),
        row("shoulder_length", dv.shoulder_length, "measured shoulder", DERIVED),
        row("across_back_half", dv.across_back_half, "across_back / 2", DERIVED),
        row("armhole_depth", dv.armhole_depth, "measured, from neck/shoulder-point level", DERIVED),
        row("waist_y", dv.waist_y, "back_neck_depth + back_waist_length", DERIVED),
        row("hip_y", dv.hip_y, "waist_y + 20.0", ASSUMPTION),
        row("suppression_per_quarter", dv.suppression, "q_bust - q_waist", DERIVED),
    ]
    if dv.sleeve_length is not None:
        rows.append(row("sleeve_length", dv.sleeve_length, "measured: shoulder tip to where the sleeve ends", DERIVED))
    if dv.bicep_width is not None:
        rows.append(row("sleeve_width_bicep", dv.bicep_width, f"bicep {m['bicep_cm']:g} + ease {ease.bicep_cm:g}", ASSUMPTION))
        rows.append(row("sleeve_cap_ease_target", dv.sleeve_cap_ease, "assumption", ASSUMPTION))
    if dv.wrist_width is not None:
        rows.append(row("sleeve_width_wrist", dv.wrist_width, f"wrist {m['wrist_cm']:g} + ease {ease.wrist_cm:g}", ASSUMPTION))
    return rows
