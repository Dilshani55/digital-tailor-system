"""
DRAFTING-VALUES stage: validated measurements + ease -> the numbers the block is drawn from.

Pure arithmetic, no geometry. Every value is recorded with the formula that produced it (with the customer's own
numbers in it) and where the rule comes from, so each pattern dimension can be traced back to a measurement, a
rule of the drafting method, a design value, the ease, or a project extension ("Why this size?").

Divisions and what they stand for
    / 4   a QUARTER of a body circumference: each bodice piece is half a front or half a back
    / 2   HALF: the centre line to the shoulder tip (shoulder to shoulder / 2), half the neckline width,
          half the sleeve width from the centre line of the sleeve to its seam
    / 12  the method's neck width from the bust (assumptions.py)

Coordinates of the levels: y = 0 is the top construction line of the block (the back neck point lies on it),
y grows downwards. All lengths in cm.
"""

import math
from dataclasses import dataclass
from typing import Optional, Tuple

from app.logic.drafting.assumptions import A, IN, CONSTANTS
from app.logic.drafting.ease import EaseProfile, DraftingError, KNIT_BLOCK


@dataclass(frozen=True)
class DraftingValues:
    block_id: str
    darts: bool                           # woven block: waist darts, side-seam dart, extra front length
    # garment (eased) circumferences
    garment_bust: float
    garment_waist: float
    garment_hip: Optional[float]
    # widths of the half pieces at the underarm (centre line to side seam)
    back_width: float
    front_width: float
    # neck / shoulder
    neck_half_back: float
    neck_half_front: float
    back_neck_depth: float
    front_neck_depth: float
    front_raise: float                    # front neck point above the top line
    shoulder_half: float                  # centre back to the shoulder tip
    front_shoulder_x: float               # centre front to the front shoulder tip
    shoulder_drop: float
    # levels
    armhole_depth: float
    waist_y: float
    hip_y: Optional[float]
    # waist edge of each half piece (finished quarter + dart) and the darts
    back_waist_quarter: float
    front_waist_quarter: float
    back_dart: float
    front_dart: float
    hip_quarter: Optional[float]
    front_extra: float                    # extra front length below the bust (taken up by the side-seam dart)
    bust_point: Optional[Tuple[float, float]]   # (from centre front, below the top line)
    garment_length: float
    # sleeve (None for sleeveless designs)
    sleeve_length: Optional[float]
    sleeve_width: Optional[float]         # whole sleeve at the underarm line
    sleeve_width_method: Optional[float]  # what the method gives from the bust
    sleeve_cap_height_method: Optional[float]
    sleeve_end_width: Optional[float]     # whole sleeve at its hem (regular sleeve)
    sleeve_cap_ease: float
    cap_ease_min: float
    cap_ease_max: float

    # earlier names, still read by a few callers
    @property
    def back_waist_x(self):
        return self.back_waist_quarter + self.back_dart

    @property
    def front_waist_x(self):
        return self.front_waist_quarter + self.front_dart


BODICE_KEYS = ("bust_cm", "waist_cm", "shoulder_width_cm", "back_waist_length_cm", "garment_length_cm")
OPTIONAL_KEYS = ("hip_cm", "waist_to_hip_cm", "shoulder_to_bust_cm", "bust_point_distance_cm", "bicep_cm", "sleeve_cm",
                 "sleeve_end_cm", "neck_width_cm", "front_neck_depth_cm", "back_neck_depth_cm", "armhole_depth_cm")


def _ok(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and v > 0


def method_armhole_depth(bust):
    """EO = 1/4 bust - 1 in (1/2 in for a bust under 30 in)."""
    less = A["armhole_depth_less_small_bust_cm"] if bust < A["small_bust_limit_cm"] else A["armhole_depth_less_cm"]
    return bust / 4.0 - less, less


def compute_drafting_values(m, ease: EaseProfile):
    """m: validated engine measurements (dict, cm). Returns (DraftingValues, trace rows)."""
    for key in BODICE_KEYS:
        if not _ok(m.get(key)):
            raise DraftingError(f"Measurement '{key}' is missing or invalid.", code="MEASUREMENTS_INVALID",
                                field_errors={key: [{"code": "REQUIRED", "message": f"{key} is required."}]})
    for key in OPTIONAL_KEYS:
        if m.get(key) is not None and not _ok(m.get(key)):
            raise DraftingError(f"Measurement '{key}' is invalid.", code="MEASUREMENTS_INVALID",
                                field_errors={key: [{"code": "NOT_POSITIVE", "message": "Must be a number greater than 0."}]})
    has = lambda key: m.get(key) is not None  # noqa: E731
    knit = ease.block_id == KNIT_BLOCK
    darts = not knit
    bust, waist = m["bust_cm"], m["waist_cm"]

    if darts and not has("shoulder_to_bust_cm"):
        raise DraftingError("A woven blouse has bust darts, so the shoulder-to-bust-point measurement is needed.",
                            code="MEASUREMENTS_INCOMPLETE",
                            field_errors={"shoulder_to_bust_cm": [{"code": "REQUIRED", "message":
                                          "Shoulder to bust point is required for this design."}]})

    # widths
    g_bust = bust + ease.bust_cm
    balance = 0.0 if knit else A["front_back_balance_cm"]
    back_w, front_w = g_bust / 4.0 - balance, g_bust / 4.0 + balance

    # neck and shoulder
    neck_back = m["neck_width_cm"] / 2.0 if has("neck_width_cm") else bust * A["neck_width_bust_fraction"]
    neck_front = neck_back - A["front_neck_narrower_cm"]
    back_depth = m["back_neck_depth_cm"] if has("back_neck_depth_cm") else A["back_neck_depth_cm"]
    front_depth = m["front_neck_depth_cm"] if has("front_neck_depth_cm") else \
        bust * A["neck_width_bust_fraction"] + A["front_neck_depth_extra_cm"]
    raise_ = A["front_neck_raise_cm"] if (not knit and bust > A["front_neck_raise_min_bust_cm"]) else 0.0
    sh_half = m["shoulder_width_cm"] / 2.0
    front_sx = sh_half - A["front_shoulder_tip_in_cm"]
    drop = A["shoulder_drop_cm"]

    # levels
    depth_method, depth_less = method_armhole_depth(bust)
    depth = m["armhole_depth_cm"] if has("armhole_depth_cm") else depth_method
    waist_y = m["back_waist_length_cm"] + A["waist_line_extra_cm"]
    hip_y = waist_y + m["waist_to_hip_cm"] if has("waist_to_hip_cm") else None

    # waist
    shift = 0.0 if knit else A["waist_front_back_shift_cm"]
    back_q = waist / 4.0 - shift + ease.waist_quarter_cm
    front_q = waist / 4.0 + shift + ease.waist_quarter_cm
    back_dart = min(A["back_dart_width_cm"], max(0.0, back_w - back_q)) if darts else 0.0
    front_dart = min(A["front_dart_width_cm"], max(0.0, front_w - front_q)) if darts else 0.0
    g_hip = m["hip_cm"] + ease.hip_cm if has("hip_cm") else None
    hip_q = g_hip / 4.0 if g_hip is not None else None

    # bust point and the extra front length
    bust_point = None
    if has("shoulder_to_bust_cm"):
        half = m["bust_point_distance_cm"] / 2.0 if has("bust_point_distance_cm") else \
            bust * A["bust_point_half_distance_bust_fraction"]
        bust_point = (half, m["shoulder_to_bust_cm"] + A["shoulder_to_bust_ease_cm"])
    front_extra = A["front_length_extra_cm"] if darts else 0.0

    # sleeve
    sleeve_len = m["sleeve_cm"] if has("sleeve_cm") else None
    sleeve_w = sleeve_w_method = cap_h = end_w = None
    if has("bicep_cm"):
        sleeve_w_method = 2.0 * (depth_method - A["sleeve_half_width_less_than_armhole_depth_cm"])
        sleeve_w = max(sleeve_w_method, m["bicep_cm"] + ease.upper_arm_cm)
        cap_h = A["sleeve_cap_height_share"] * sleeve_w / 2.0
        if has("sleeve_end_cm"):
            end_w = m["sleeve_end_cm"] + ease.sleeve_end_cm

    dv = DraftingValues(
        block_id=ease.block_id, darts=darts,
        garment_bust=g_bust, garment_waist=waist + ease.waist_cm, garment_hip=g_hip,
        back_width=back_w, front_width=front_w,
        neck_half_back=neck_back, neck_half_front=neck_front, back_neck_depth=back_depth,
        front_neck_depth=front_depth, front_raise=raise_,
        shoulder_half=sh_half, front_shoulder_x=front_sx, shoulder_drop=drop,
        armhole_depth=depth, waist_y=waist_y, hip_y=hip_y,
        back_waist_quarter=back_q, front_waist_quarter=front_q, back_dart=back_dart, front_dart=front_dart,
        hip_quarter=hip_q, front_extra=front_extra, bust_point=bust_point,
        garment_length=m["garment_length_cm"],
        sleeve_length=sleeve_len, sleeve_width=sleeve_w, sleeve_width_method=sleeve_w_method,
        sleeve_cap_height_method=cap_h, sleeve_end_width=end_w,
        sleeve_cap_ease=ease.sleeve_cap_cm, cap_ease_min=ease.cap_ease_min_cm, cap_ease_max=ease.cap_ease_max_cm,
    )
    _check_feasible(dv, m)
    return dv, explain(dv, m, ease, depth_less)


def _check_feasible(dv, m):
    """Combinations that would give negative / degenerate geometry are rejected, not adjusted."""
    problems = {}

    def bad(key, message):
        problems.setdefault(key, message)

    if dv.shoulder_half <= dv.neck_half_back + 2.0:
        bad("shoulder_width_cm",
            f"Shoulder to shoulder ({2 * dv.shoulder_half:g} cm) leaves no shoulder seam beside the neckline "
            f"({2 * dv.neck_half_back:.1f} cm wide).")
    if dv.shoulder_half >= dv.back_width - 0.5:
        bad("shoulder_width_cm",
            f"Half of shoulder to shoulder ({dv.shoulder_half:.1f} cm) must be smaller than the back width of the "
            f"pattern at the underarm ({dv.back_width:.1f} cm) - please check shoulder to shoulder and bust.")
    if dv.armhole_depth <= dv.shoulder_drop + 6.0:
        bad("armhole_depth_cm", f"Armhole depth ({dv.armhole_depth:.1f} cm) is too small for an armhole.")
    if dv.armhole_depth >= dv.waist_y - 3.0:
        bad("back_waist_length_cm",
            f"The underarm level ({dv.armhole_depth:.1f} cm below the shoulder line) must be at least 3 cm above the "
            f"waist level ({dv.waist_y:.1f} cm) - please check back neck to waist.")
    if dv.neck_half_front <= 1.0:
        bad("neck_width_cm", "The neckline is too narrow.")
    if dv.front_neck_depth >= dv.armhole_depth + (dv.waist_y - dv.armhole_depth) * 0.75:
        bad("front_neck_depth_cm", f"Front neck depth ({dv.front_neck_depth:.1f} cm) reaches almost to the waist.")
    if dv.back_neck_depth >= dv.armhole_depth:
        bad("back_neck_depth_cm", f"Back neck depth ({dv.back_neck_depth:.1f} cm) is below the underarm level.")
    if dv.darts and dv.bust_point is not None:
        bx, by = dv.bust_point
        if bx >= dv.front_width - 2.0:
            bad("bust_point_distance_cm", "The bust point lies outside the front pattern - please check between bust points.")
        if by >= dv.waist_y - 4.0:
            bad("shoulder_to_bust_cm",
                f"Shoulder to bust point ({m['shoulder_to_bust_cm']:g} cm) puts the bust point at the waist "
                f"({dv.waist_y:.1f} cm) - please check it and back neck to waist.")
        if by <= dv.shoulder_drop + 4.0:
            bad("shoulder_to_bust_cm", f"Shoulder to bust point ({m['shoulder_to_bust_cm']:g} cm) is too short.")
    if dv.hip_y is not None and dv.hip_y <= dv.waist_y + 3.0:
        bad("waist_to_hip_cm", "Waist to hip is too short.")
    if problems:
        raise DraftingError(
            "The measurements cannot be drafted into a valid block: " + " ".join(problems.values()),
            code="MEASUREMENTS_NOT_DRAFTABLE",
            field_errors={k: [{"code": "NOT_DRAFTABLE", "message": v}] for k, v in problems.items()})


def _f(v):
    return f"{v:.2f}".rstrip("0").rstrip(".")


def explain(dv, m, ease, depth_less):
    """
    "Why this size?": every drafting value with the calculation that produced it, in the customer's own numbers.
    source: measurement | method | figure | design | ease | extension  (see assumptions.py).
    """
    rows = []

    def row(rid, label, value, formula, source, piece="bodice"):
        rows.append({"id": rid, "name": rid, "label": label, "value_cm": round(value, 3), "formula": formula,
                     "source": source, "status": source, "piece": piece})

    kind = lambda key: CONSTANTS[key]["kind"]  # noqa: E731
    bust, waist = m["bust_cm"], m["waist_cm"]
    knit = not dv.darts
    bal = 0.0 if knit else A["front_back_balance_cm"]

    row("garment_bust", "Bust of the garment", dv.garment_bust,
        f"bust {_f(bust)} + ease {_f(ease.bust_cm)} ({ease.fit_label})", "ease")
    row("back_bust_width", "Back width at the bust line", dv.back_width,
        f"({_f(bust)} + {_f(ease.bust_cm)}) / 4" + ("" if knit else f" - {_f(bal)} (front/back balance)"),
        "extension" if knit else "method", "back")
    row("front_bust_width", "Front width at the bust line", dv.front_width,
        f"({_f(bust)} + {_f(ease.bust_cm)}) / 4" + ("" if knit else f" + {_f(bal)} (front/back balance)"),
        "extension" if knit else "method", "front")
    if m.get("neck_width_cm") is not None:
        row("back_neck_width", "Back neck width (centre to neck point)", dv.neck_half_back,
            f"neckline width {_f(m['neck_width_cm'])} / 2", "design", "back")
    else:
        row("back_neck_width", "Back neck width (centre to neck point)", dv.neck_half_back,
            f"bust {_f(bust)} / 12", "method", "back")
    row("front_neck_width", "Front neck width (centre to neck point)", dv.neck_half_front,
        f"back neck width {_f(dv.neck_half_back)} - {_f(A['front_neck_narrower_cm'])}", "method", "front")
    row("back_neck_depth", "Back neck depth", dv.back_neck_depth,
        "entered" if m.get("back_neck_depth_cm") is not None else "standard value (1 in)", "design", "back")
    row("front_neck_depth", "Front neck depth", dv.front_neck_depth,
        "entered" if m.get("front_neck_depth_cm") is not None else
        f"bust {_f(bust)} / 12 + {_f(A['front_neck_depth_extra_cm'])}",
        "design" if m.get("front_neck_depth_cm") is not None else "method", "front")
    if dv.front_raise:
        row("front_neck_raise", "Front neck point raised", dv.front_raise,
            f"bust above {_f(A['front_neck_raise_min_bust_cm'])} cm (31 in)", "method", "front")
    row("shoulder_tip_back", "Centre back to shoulder tip", dv.shoulder_half,
        f"shoulder to shoulder {_f(m['shoulder_width_cm'])} / 2", "measurement", "back")
    row("shoulder_tip_front", "Centre front to shoulder tip", dv.front_shoulder_x,
        f"{_f(dv.shoulder_half)} - {_f(A['front_shoulder_tip_in_cm'])}", "method", "front")
    row("shoulder_drop", "Shoulder drop", dv.shoulder_drop, "standard value (1 in)", kind("shoulder_drop_cm"))
    if m.get("armhole_depth_cm") is not None:
        row("armhole_depth", "Armhole depth", dv.armhole_depth, "entered", "design")
    else:
        row("armhole_depth", "Armhole depth", dv.armhole_depth, f"bust {_f(bust)} / 4 - {_f(depth_less)}", "method")
    row("waist_level", "Waist level below the shoulder line", dv.waist_y,
        f"back neck to waist {_f(m['back_waist_length_cm'])} + {_f(A['waist_line_extra_cm'])}", "method")
    shift = 0.0 if knit else A["waist_front_back_shift_cm"]
    row("back_waist_width", "Back waist width (finished)", dv.back_waist_quarter,
        f"waist {_f(waist)} / 4" + ("" if knit else f" - {_f(shift)}") + f" + ease {_f(ease.waist_quarter_cm)}",
        "extension" if knit else "method", "back")
    row("front_waist_width", "Front waist width (finished)", dv.front_waist_quarter,
        f"waist {_f(waist)} / 4" + ("" if knit else f" + {_f(shift)}") + f" + ease {_f(ease.waist_quarter_cm)}",
        "extension" if knit else "method", "front")
    if dv.darts:
        for side, got, full in (("back", dv.back_dart, A["back_dart_width_cm"]), ("front", dv.front_dart, A["front_dart_width_cm"])):
            row(f"{side}_waist_dart", f"{side.capitalize()} waist dart width", got,
                f"method {_f(full)}" + ("" if abs(got - full) < 1e-9 else
                                        " reduced: the waist edge would be wider than the block"),
                "method" if abs(got - full) < 1e-9 else "extension", side)
        row("front_length_extra", "Extra front length (side-seam dart)", dv.front_extra,
            "front hem line 1 in below the waist line", "figure", "front")
    if dv.bust_point is not None:
        row("bust_point_from_centre", "Bust point from the centre front", dv.bust_point[0],
            f"between bust points {_f(m['bust_point_distance_cm'])} / 2" if m.get("bust_point_distance_cm") is not None
            else f"bust {_f(bust)} / 10", "measurement" if m.get("bust_point_distance_cm") is not None else "method", "front")
        row("bust_point_level", "Bust point below the shoulder line", dv.bust_point[1],
            f"shoulder to bust point {_f(m['shoulder_to_bust_cm'])} + {_f(A['shoulder_to_bust_ease_cm'])}", "method", "front")
    if dv.garment_hip is not None:
        row("garment_hip", "Hip of the garment", dv.garment_hip,
            f"hip {_f(m['hip_cm'])} + ease {_f(ease.hip_cm)} ({ease.fit_label})", "ease")
        delta = (dv.front_waist_x - dv.back_waist_x) / 2.0
        row("hip_width", "Hip width, front + back", 2.0 * dv.hip_quarter,
            f"({_f(m['hip_cm'])} + {_f(ease.hip_cm)}) / 2; front {_f(dv.hip_quarter + delta)}, back "
            f"{_f(dv.hip_quarter - delta)} (the front keeps its extra waist width so both side seams are equally long)",
            "extension")
    if dv.hip_y is not None:
        row("hip_level", "Hip level below the shoulder line", dv.hip_y,
            f"waist level {_f(dv.waist_y)} + waist to hip {_f(m['waist_to_hip_cm'])}", "measurement")
    row("garment_length", "Garment length", dv.garment_length, "entered", "measurement")
    if dv.sleeve_width is not None:
        need = m["bicep_cm"] + ease.upper_arm_cm
        if dv.sleeve_width > dv.sleeve_width_method + 1e-9:
            row("sleeve_width", "Sleeve width at the underarm", dv.sleeve_width,
                f"upper arm {_f(m['bicep_cm'])} + ease {_f(ease.upper_arm_cm)} (the method's "
                f"{_f(dv.sleeve_width_method)} from the bust is narrower than the arm needs)", "extension", "sleeve")
        else:
            row("sleeve_width", "Sleeve width at the underarm", dv.sleeve_width,
                f"2 x (bust {_f(bust)} / 4 - {_f(depth_less + A['sleeve_half_width_less_than_armhole_depth_cm'])}); "
                f"upper arm {_f(m['bicep_cm'])} + ease {_f(ease.upper_arm_cm)} = {_f(need)} fits inside", "method", "sleeve")
        row("sleeve_cap_height_method", "Sleeve cap height (method)", dv.sleeve_cap_height_method,
            f"sleeve width {_f(dv.sleeve_width)} / 2 / 2", "method", "sleeve")
    if dv.sleeve_length is not None:
        row("sleeve_length", "Sleeve length", dv.sleeve_length, "entered", "measurement", "sleeve")
    if dv.sleeve_end_width is not None:
        row("sleeve_end_width", "Sleeve width at its end", dv.sleeve_end_width,
            f"sleeve end around {_f(m['sleeve_end_cm'])} + ease {_f(ease.sleeve_end_cm)}", "extension", "sleeve")
    return rows


__all__ = ["DraftingValues", "compute_drafting_values", "method_armhole_depth", "explain", "IN"]
