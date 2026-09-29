"""
Geometry validation for generated blocks / patterns.

These are GEOMETRY checks (finite, closed, simple polygon, consistent seams, sleeve-cap vs armhole).
They are not a fit or sewing validation. A failure stops generation — it is never downgraded to a
warning and never converted into a "successful" pattern.

Result shape (kept compatible with the earlier validator):
    {"passed": bool, "errors": [str], "warnings": [str], "checks": {name: {"ok": bool, "detail": str}}}
"""

import math

from app.logic.drafting import geometry as g
from app.logic.drafting.assumptions import A

SEAM_TOL_CM = 0.05           # front/back seam-length agreement (they are built from the same numbers)
CAP_EASE_SOLVE_TOL_CM = 0.1  # constructed cap vs target
MAX_PIECE_DIM_CM = 200.0

REQUIRED_POINTS = {
    "front_bodice": ("CENTRE_NECK", "NECK_POINT", "SHOULDER_POINT", "UNDERARM", "HEM_SIDE", "HEM_CENTRE", "BUST_POINT"),
    "back_bodice": ("CENTRE_NECK", "NECK_POINT", "SHOULDER_POINT", "UNDERARM", "HEM_SIDE", "HEM_CENTRE"),
    "sleeve": ("CROWN", "UNDERARM_LEFT", "UNDERARM_RIGHT", "HEM_LEFT", "HEM_RIGHT"),
}


class _Result:
    def __init__(self):
        self.errors, self.warnings, self.checks = [], [], {}

    def check(self, name, ok, detail, error=None):
        self.checks[name] = {"ok": bool(ok), "detail": detail}
        if not ok:
            self.errors.append(error or f"{name}: {detail}")

    def dump(self):
        return {"passed": not self.errors, "errors": self.errors, "warnings": self.warnings, "checks": self.checks}


def validate_piece(piece, res=None, prefix=None):
    """Structural checks for one Piece. Returns the _Result used."""
    res = res or _Result()
    p = prefix or piece.name
    pts = piece.outline

    ctrl = [q for s in piece.segments for q in s.p] + list(piece.points.values())
    res.check(f"{p}: finite", g.all_finite(ctrl) and g.all_finite(pts), "all coordinates finite",
              f"{piece.name}: contains non-finite coordinates")
    if not (g.all_finite(ctrl) and g.all_finite(pts)):
        return res

    res.check(f"{p}: connected", g.path_is_connected(piece.segments), "segments join end-to-start",
              f"{piece.name}: outline segments are not connected")
    closed = g.dist(piece.segments[-1].end, piece.segments[0].start) <= 1e-6
    res.check(f"{p}: closed", closed, "outline returns to its start point", f"{piece.name}: outline is not closed")

    crossings = g.self_intersections(pts)
    res.check(f"{p}: simple outline", not crossings,
              "no self-intersection" if not crossings else f"self-intersecting edges {crossings[:3]}",
              f"{piece.name}: outline self-intersects (edges {crossings[:3]})")

    area = g.polygon_area(pts)
    min_x, min_y, max_x, max_y = g.bbox(pts)
    w, h = max_x - min_x, max_y - min_y
    res.check(f"{p}: positive size", area > 1.0 and w > 0.5 and h > 0.5,
              f"area {area:.1f} cm2, {w:.1f} x {h:.1f} cm", f"{piece.name}: degenerate size ({w:.1f} x {h:.1f} cm)")
    res.check(f"{p}: plausible size", w <= MAX_PIECE_DIM_CM and h <= MAX_PIECE_DIM_CM,
              f"{w:.1f} x {h:.1f} cm", f"{piece.name}: implausible size ({w:.0f} x {h:.0f} cm)")
    res.check(f"{p}: no negative geometry", min_x >= -1e-6 and min_y >= -1e-6,
              f"min x {min_x:.3f}, min y {min_y:.3f}", f"{piece.name}: geometry extends into negative coordinates")

    required = REQUIRED_POINTS.get(piece.piece_type)
    if required:
        missing = [k for k in required if k not in piece.points]
        res.check(f"{p}: required points", not missing, "all present" if not missing else f"missing {missing}",
                  f"{piece.name}: missing required points {missing}")

    for dart in piece.darts:
        _check_dart(piece, dart, pts, res, p)
    return res


def _check_dart(piece, dart, poly, res, prefix):
    apex, a, b = dart["apex"], dart["leg_a"], dart["leg_b"]
    inside = all(g.point_in_polygon(tuple(q), poly) for q in (apex, a, b))
    if "lower_apex" in dart:
        inside = inside and g.point_in_polygon(tuple(dart["lower_apex"]), poly)
    res.check(f"{prefix}: {dart['id']} inside outline", inside, "dart points lie inside the piece",
              f"{piece.name}: dart {dart['id']} lies outside the piece outline")
    la, lb = g.dist(apex, a), g.dist(apex, b)
    res.check(f"{prefix}: {dart['id']} symmetric", abs(la - lb) < 0.01 and dart["intake_cm"] > 0,
              f"legs {la:.2f} / {lb:.2f} cm, intake {dart['intake_cm']} cm",
              f"{piece.name}: dart {dart['id']} is asymmetric or has no intake")
    if dart["type"] == "open":     # legs end on the bottom edge of the piece
        on_edge = g.point_on_polyline(tuple(a), poly, 1e-5) and g.point_on_polyline(tuple(b), poly, 1e-5)
        res.check(f"{prefix}: {dart['id']} legs on edge", on_edge, "open dart legs meet the waist edge",
                  f"{piece.name}: open dart legs do not meet the outline")


def _pair_checks(front, back, dv, res):
    fs, bs = front.meta["shoulder_length_cm"], back.meta["shoulder_length_cm"]
    res.check("front/back shoulder seams", abs(fs - bs) <= SEAM_TOL_CM,
              f"front {fs:.2f} cm, back {bs:.2f} cm", f"Front/back shoulder seams differ ({fs:.2f} vs {bs:.2f} cm)")
    if front.meta["hem_y_cm"] == back.meta["hem_y_cm"]:
        fl, bl = front.meta["side_seam_length_cm"], back.meta["side_seam_length_cm"]
        res.check("front/back side seams", abs(fl - bl) <= SEAM_TOL_CM,
                  f"front {fl:.2f} cm, back {bl:.2f} cm", f"Front/back side seams differ ({fl:.2f} vs {bl:.2f} cm)")
    fx, bx = front.meta["side_seam_x_at_waist_cm"], back.meta["side_seam_x_at_waist_cm"]
    res.check("front/back waist alignment", abs(fx - bx) <= SEAM_TOL_CM,
              f"{fx:.2f} vs {bx:.2f} cm", "Front and back side seams meet the waist at different widths")
    # Circumference accounting: 4 * (waist edge - dart intake) must equal the eased waist.
    for piece in (front, back):
        if piece.meta["hem_y_cm"] >= dv.waist_y - 1e-6:      # a waist edge exists in this piece
            net = 4.0 * (piece.meta["side_seam_x_at_waist_cm"] - piece.meta["dart_intake_cm"])
            res.check(f"{piece.name}: waist circumference", abs(net - dv.garment_waist) <= 0.05,
                      f"{net:.2f} cm vs eased waist {dv.garment_waist:.2f} cm",
                      f"{piece.name}: waist width does not add up to the eased waist ({net:.1f} vs {dv.garment_waist:.1f} cm)")
    front_bp = front.points.get("BUST_POINT")
    if front_bp is not None:
        res.check("bust point inside front", g.point_in_polygon(tuple(front_bp), front.outline),
                  "bust point lies inside the front piece", "Bust point lies outside the front piece")


def _sleeve_checks(front, back, sleeve_piece, res):
    total = front.meta["armhole_length_cm"] + back.meta["armhole_length_cm"]
    cap = sleeve_piece.meta["cap_length_cm"]
    ease = cap - total
    lo, hi = A["sleeve_cap_ease_tolerance_cm"]
    res.check("sleeve cap vs armhole", lo <= ease <= hi,
              f"cap {cap:.2f} cm - armhole {total:.2f} cm = ease {ease:.2f} cm (accepted {lo:g}..{hi:g})",
              f"Sleeve cap ({cap:.1f} cm) is not compatible with the armhole ({total:.1f} cm); ease {ease:.1f} cm")
    return {"front_armhole_seam_cm": front.meta["armhole_length_cm"], "back_armhole_seam_cm": back.meta["armhole_length_cm"],
            "total_armhole_seam_cm": total, "sleeve_cap_seam_cm": cap, "cap_ease_cm": ease}


def validate_base_block(base):
    res = _Result()
    for piece in base.pieces:
        validate_piece(piece, res)
    _pair_checks(base.front, base.back, base.dv, res)
    info = _sleeve_checks(base.front, base.back, base.sleeve, res)
    res.check("sleeve cap solved to target",
              abs(info["cap_ease_cm"] - base.dv.sleeve_cap_ease) <= CAP_EASE_SOLVE_TOL_CM,
              f"ease {info['cap_ease_cm']:.3f} vs target {base.dv.sleeve_cap_ease:g}",
              "Sleeve cap length does not match its target")
    out = res.dump()
    out["armhole_sleeve"] = {k: round(v, 3) for k, v in info.items()}
    out["scope"] = "geometry validation only; not a fit or sewing validation"
    return out


def validate_final_pattern(final):
    """final: FinalPattern (transformations.py)."""
    res = _Result()
    for piece in final.pieces:
        validate_piece(piece, res)
    _pair_checks(final.front, final.back, final.dv, res)
    info = None
    if final.sleeve is not None:
        info = _sleeve_checks(final.front, final.back, final.sleeve, res)
        res.check("sleeve hem below cap", final.sleeve.meta["length_cm"] > final.sleeve.meta["cap_height_cm"],
                  f"hem {final.sleeve.meta['length_cm']:.1f} cm, cap {final.sleeve.meta['cap_height_cm']:.1f} cm",
                  "Sleeve hem is not below the sleeve cap")
    res.check("transformations recorded", bool(final.transformations),
              f"{len(final.transformations)} recorded", "Final pattern carries no transformation record")
    out = res.dump()
    if info:
        out["armhole_sleeve"] = {k: round(v, 3) for k, v in info.items()}
    out["scope"] = "geometry validation only; not a fit or sewing validation"
    return out
