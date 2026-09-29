"""
Bodice geometry builder (front / back half pattern, centre line = x 0, cut on the fold).

Used by BOTH the base block (round neck, hem at the waist) and the design-transformation layer
(design neckline, design hem). It draws whatever parameters it is given; it does not decide the
design. Coordinates: cm, x to the right from the centre line, y DOWN from the neck/shoulder-point
level.

Construction (equations; status in assumptions.py)
  NP  neck point            = (neck_half_width, 0)
  SP  shoulder point        = NP + shoulder_length * (cos t, sin t),   t = shoulder slope
  U   underarm point        = (q_bust, armhole_depth)                  side seam starts here
  armhole: one cubic Bezier SP -> U, control points
        P1 = (across-back line x, SP.y + k*(U.y - SP.y))      (vertical-ish leaving the shoulder)
        P2 = (U.x - k*(U.x - SP.x), U.y)                      (horizontal arriving at the underarm)
  side seam: polyline U -> W (waist) -> H (hip); x at the waist = q_bust - side share of the
        suppression, x at the hip = max(q_hip, x at waist)
  darts: internal lines only (never part of the cutting outline)
"""

import math

from app.logic.drafting import geometry as g
from app.logic.drafting.assumptions import A
from app.logic.drafting.ease import DraftingError
from app.logic.drafting.pieces import Piece

K = A["curve_kappa"]


def waist_allocation(dv, dart_allowed):
    """(side_take, dart_intake): how the per-quarter suppression is shared (side seam vs dart)."""
    s = dv.suppression
    if s <= 0:
        return s, 0.0       # waist wider than bust: side seam moves OUT by |s|
    if not dart_allowed:
        return s, 0.0
    dart = min((1.0 - A["side_seam_suppression_share_with_darts"]) * s, A["max_dart_intake_cm"])
    return s - dart, dart


def side_profile(dv, side_take):
    """Side-seam reference nodes and x(y)."""
    x_waist = dv.q_bust - side_take
    x_hip = max(dv.q_hip, x_waist)
    u = (dv.q_bust, dv.armhole_depth)
    w = (x_waist, dv.waist_y)
    h = (x_hip, dv.hip_y)

    def x_at(y):
        if y <= dv.waist_y:
            t = (y - u[1]) / (w[1] - u[1])
            return u[0] + (w[0] - u[0]) * t
        if y <= dv.hip_y:
            t = (y - w[1]) / (h[1] - w[1])
            return w[0] + (h[0] - w[0]) * t
        return x_hip

    return {"U": u, "W": w, "H": h, "x_at": x_at}


def _neck_segments(dv, side, neck):
    """Segments running from the centre-line neck point to the neck point NP."""
    nw = dv.neck_half_width
    if side == "back":
        d = dv.back_neck_depth
        return [g.quarter_ellipse("neckline", (0, d), (nw, 0), (nw, d), first_axis="horizontal")], (0.0, d)
    shape = (neck or {}).get("shape", "round")
    if shape == "round":
        d = dv.front_neck_depth
        return [g.quarter_ellipse("neckline", (0, d), (nw, 0), (nw, d), first_axis="horizontal")], (0.0, d)
    if shape == "square":
        d = neck.get("depth", dv.front_neck_depth)
        return [g.Line("neckline_bottom", (0, d), (nw, d)), g.Line("neckline_side", (nw, d), (nw, 0))], (0.0, d)
    if shape == "v":
        d = neck["depth"]
        return [g.Line("neckline", (0, d), (nw, 0))], (0.0, d)
    raise DraftingError(f"Unknown neckline shape '{shape}'.", code="UNSUPPORTED_NECKLINE")


def build_bodice(dv, side, *, neck=None, hem_y, block_allows_darts, name=None):
    """Return a Piece for the front or back half bodice."""
    if side not in ("front", "back"):
        raise ValueError("side must be 'front' or 'back'")
    if hem_y <= dv.armhole_depth + 1.0:
        raise DraftingError(
            f"Hem level ({hem_y:.1f} cm) is not below the underarm level ({dv.armhole_depth:.1f} cm).",
            code="HEM_ABOVE_UNDERARM",
            field_errors={"garment_length_cm": [{"code": "NOT_DRAFTABLE", "message":
                          "Garment length puts the hem at or above the underarm level."}]})

    at_waist = abs(hem_y - dv.waist_y) < 1e-6
    dart_allowed = block_allows_darts and (at_waist or hem_y >= dv.waist_y + 3.0)
    side_take, dart_intake = waist_allocation(dv, dart_allowed)
    prof = side_profile(dv, side_take)

    nw = dv.neck_half_width
    theta = math.radians(dv.shoulder_slope_deg)
    np_ = (nw, 0.0)
    sp = (nw + dv.shoulder_length * math.cos(theta), dv.shoulder_length * math.sin(theta))
    u = prof["U"]
    dx, dy = u[0] - sp[0], u[1] - sp[1]
    if dx <= 0.5 or dy <= 2.0:
        raise DraftingError("Armhole geometry is degenerate for these measurements.",
                            code="MEASUREMENTS_NOT_DRAFTABLE")
    across = dv.across_back_half - (A["front_armhole_hollow_cm"] if side == "front" else 0.0)
    armhole = g.Cubic("armhole", sp, (across, sp[1] + K * dy), (u[0] - K * dx, u[1]), u)

    neck_segs, cl_neck = _neck_segments(dv, side, neck)

    # side seam polyline down to the hem
    nodes = [prof["U"]]
    if hem_y > dv.waist_y + 1e-9:
        nodes.append(prof["W"])
    if hem_y > dv.hip_y + 1e-9:
        nodes.append(prof["H"])
    hem_side = (prof["x_at"](hem_y), hem_y)
    nodes.append(hem_side)
    side_segs = [g.Line(f"side_seam_{i + 1}", nodes[i], nodes[i + 1]) for i in range(len(nodes) - 1)]

    segments = neck_segs + [g.Line("shoulder", np_, sp), armhole] + side_segs + [
        g.Line("hem", hem_side, (0.0, hem_y)),
        g.Line("centre_line", (0.0, hem_y), cl_neck),
    ]

    points = {
        "CENTRE_NECK": cl_neck, "NECK_POINT": np_, "SHOULDER_POINT": sp, "UNDERARM": u,
        "HEM_SIDE": hem_side, "HEM_CENTRE": (0.0, hem_y),
    }
    if hem_y >= dv.waist_y - 1e-9:
        points["WAIST_SIDE"] = prof["W"]

    darts = []
    if dart_intake > 0:
        darts.append(_dart(dv, side, dart_intake, prof, hem_y, at_waist))
        points["DART_APEX"] = tuple(darts[0]["apex"])
    if side == "front":
        points["BUST_POINT"] = (A["bust_point_x_share"] * dv.q_bust, dv.armhole_depth + A["bust_point_below_underarm_cm"])

    piece = Piece(
        name or ("Front Bodice" if side == "front" else "Back Bodice"),
        f"{side}_bodice", segments, points, cut_count=1, cut_on_fold=True,
        grain=((dv.q_bust * 0.5, dv.armhole_depth), (dv.q_bust * 0.5, hem_y - 1.0)),
        fold_line=((0.0, cl_neck[1]), (0.0, hem_y)), darts=darts,
        meta={
            "armhole_length_cm": armhole.length(),
            "shoulder_length_cm": g.dist(np_, sp),
            "side_seam_length_cm": sum(s.length() for s in side_segs),
            "neckline_length_cm": sum(s.length() for s in neck_segs),
            "hem_y_cm": hem_y, "waist_y_cm": dv.waist_y,
            "side_seam_x_at_waist_cm": prof["W"][0],
            "dart_intake_cm": dart_intake, "side_seam_suppression_cm": side_take,
            "dart_mode": ("open" if at_waist else "fish") if dart_intake > 0 else "none",
        },
    )
    return piece


def _dart(dv, side, intake, prof, hem_y, at_waist):
    """Internal dart lines (waist dart). `open` in a waist-length block, `fish` when the garment continues."""
    y_w = dv.waist_y
    if side == "front":
        xc = A["bust_point_x_share"] * dv.q_bust
        apex_y = dv.armhole_depth + A["bust_point_below_underarm_cm"] + A["front_dart_apex_below_bust_point_cm"]
    else:
        xc = prof["W"][0] * 0.5
        apex_y = y_w - A["back_dart_apex_share"] * (y_w - dv.armhole_depth)
    if y_w - apex_y < 4.0:
        raise DraftingError("Waist is too close to the underarm for a dart; check armhole depth / back waist length.",
                            code="MEASUREMENTS_NOT_DRAFTABLE")
    left, right = (xc - intake / 2.0, y_w), (xc + intake / 2.0, y_w)
    if left[0] <= 0.5 or right[0] >= prof["W"][0] - 0.5:
        raise DraftingError("Dart does not fit between the centre line and the side seam.",
                            code="MEASUREMENTS_NOT_DRAFTABLE")
    dart = {
        "id": f"{side}_waist_dart", "type": "open" if at_waist else "fish",
        "intake_cm": round(intake, 3),
        "apex": [round(xc, 4), round(apex_y, 4)],
        "leg_a": [round(left[0], 4), round(left[1], 4)],
        "leg_b": [round(right[0], 4), round(right[1], 4)],
        "length_cm": round(y_w - apex_y, 3),
    }
    if not at_waist:
        lower = min(A["fish_dart_lower_share"] * (y_w - apex_y), hem_y - y_w - 2.0)
        dart["lower_apex"] = [round(xc, 4), round(y_w + lower, 4)]
    return dart
