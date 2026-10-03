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
from app.logic.drafting import seam_allowance as sa

SEAM_TOL_CM = 0.05           # seams that are sewn together and built from the same numbers
SHOULDER_TOL_CM = 0.6        # the method raises the front neck point, so the front shoulder seam is a little longer
SIDE_DART_LEG_TOL_CM = 1.0   # the method's side dart points at the bust, not square to the seam
CAP_EASE_SOLVE_TOL_CM = 0.1  # constructed cap vs target
MAX_PIECE_DIM_CM = 200.0

REQUIRED_POINTS = {
    "front_bodice": ("CENTRE_NECK", "NECK_POINT", "SHOULDER_POINT", "UNDERARM", "HEM_SIDE", "HEM_CENTRE"),
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
    # a leg may end exactly ON an edge (waist edge, side seam): on the outline counts as inside
    inside = g.point_in_polygon(tuple(apex), poly) and all(
        g.point_in_polygon(tuple(q), poly) or g.point_on_polyline(tuple(q), poly, 1e-4) for q in (a, b))
    if "lower_apex" in dart:
        inside = inside and g.point_in_polygon(tuple(dart["lower_apex"]), poly)
    res.check(f"{prefix}: {dart['id']} inside outline", inside, "dart points lie inside the piece",
              f"{piece.name}: dart {dart['id']} lies outside the piece outline")
    la, lb = g.dist(apex, a), g.dist(apex, b)
    leg_tol = SIDE_DART_LEG_TOL_CM if dart["type"] == "side" else 0.01
    res.check(f"{prefix}: {dart['id']} symmetric", abs(la - lb) < leg_tol and dart["intake_cm"] > 0,
              f"legs {la:.2f} / {lb:.2f} cm, intake {dart['intake_cm']} cm",
              f"{piece.name}: dart {dart['id']} is asymmetric or has no intake")
    if dart["type"] in ("open", "side"):     # legs end on an edge of the piece (waist edge / side seam)
        on_edge = g.point_on_polyline(tuple(a), poly, 1e-4) and g.point_on_polyline(tuple(b), poly, 1e-4)
        res.check(f"{prefix}: {dart['id']} legs on edge", on_edge, "dart legs meet the edge of the piece",
                  f"{piece.name}: open dart legs do not meet the outline")


def _pair_checks(front, back, dv, res):
    """Seams that are sewn together, and the circumferences the two pieces add up to."""
    fs, bs = front.meta["shoulder_length_cm"], back.meta["shoulder_length_cm"]
    res.check("front/back shoulder seams", abs(fs - bs) <= SHOULDER_TOL_CM,
              f"front {fs:.2f} cm, back {bs:.2f} cm (difference {fs - bs:+.2f} cm, eased in)",
              f"Front/back shoulder seams differ too much ({fs:.2f} vs {bs:.2f} cm)")
    fl, bl = front.meta["side_seam_sewn_length_cm"], back.meta["side_seam_sewn_length_cm"]
    res.check("front/back side seams", abs(fl - bl) <= SEAM_TOL_CM,
              f"front {fl:.2f} cm (after the bust dart), back {bl:.2f} cm",
              f"Front/back side seams differ ({fl:.2f} vs {bl:.2f} cm)")
    bust = 2.0 * (front.meta["bust_width_cm"] + back.meta["bust_width_cm"])
    res.check("bust circumference", abs(bust - dv.garment_bust) <= 0.05,
              f"2 x (front {front.meta['bust_width_cm']:.2f} + back {back.meta['bust_width_cm']:.2f}) = {bust:.2f} cm "
              f"vs bust + ease {dv.garment_bust:.2f} cm",
              f"Front and back widths do not add up to the bust plus ease ({bust:.1f} vs {dv.garment_bust:.1f} cm)")
    waist = 2.0 * (front.meta["waist_finished_cm"] + back.meta["waist_finished_cm"])
    res.check("waist circumference", abs(waist - dv.garment_waist) <= 0.05,
              f"2 x (front {front.meta['waist_finished_cm']:.2f} + back {back.meta['waist_finished_cm']:.2f}) = {waist:.2f} cm "
              f"vs waist + ease {dv.garment_waist:.2f} cm",
              f"Waist widths (darts sewn) do not add up to the waist plus ease ({waist:.1f} vs {dv.garment_waist:.1f} cm)")
    fa, ba = front.meta["armhole_length_cm"], back.meta["armhole_length_cm"]
    if dv.darts:
        res.check("front armhole deeper than back", fa > ba,
                  f"front {fa:.2f} cm, back {ba:.2f} cm", "The front armhole is not longer than the back armhole")
        res.check("front wider than back", front.meta["bust_width_cm"] > back.meta["bust_width_cm"],
                  f"front {front.meta['bust_width_cm']:.2f} cm, back {back.meta['bust_width_cm']:.2f} cm",
                  "The front is not wider than the back")
    front_bp = front.points.get("BUST_POINT")
    if front_bp is not None:
        res.check("bust point inside front", g.point_in_polygon(tuple(front_bp), front.outline),
                  "bust point lies inside the front piece", "Bust point lies outside the front piece")
    elif dv.darts:
        res.check("bust point present", False, "missing", "The front of a darted block has no bust point")


def _flat_cap_ok(sleeve_piece, front, back, tol=0.05):
    """The cap from each underarm to its notch equals the bodice's notch distance (that part is sewn flat)."""
    front_cap, back_cap = sa.cap_paths_of(sleeve_piece)
    marks = {n["id"]: tuple(n["point"]) for n in sleeve_piece.notches}
    if "sleeve_front_1" not in marks or "sleeve_back_1" not in marks:
        return False, "notches missing"
    df, _ = g.length_to_point(front_cap, marks["sleeve_front_1"])
    arc_b, total_b = g.length_to_point(back_cap, marks["sleeve_back_1"])
    db = total_b - arc_b
    want_f, want_b = front.meta["armhole_notch_from_underarm_cm"], back.meta["armhole_notch_from_underarm_cm"]
    ok = abs(df - want_f) <= tol and abs(db - want_b) <= tol
    return ok, f"cap below the notches: front {df:.2f}/{want_f:.2f} cm, back {db:.2f}/{want_b:.2f} cm"


def _sleeve_checks(front, back, sleeve_piece, res, dv):
    total = front.meta["armhole_length_cm"] + back.meta["armhole_length_cm"]
    cap = sleeve_piece.meta["cap_length_cm"]
    ease = cap - total
    gathered = bool(sleeve_piece.meta.get("gathered_cap"))
    if gathered:
        # puff sleeve: the excess is gathered between the notches, so a larger (but bounded) excess is intended
        lo, hi = A["puff_gather_excess_range_cm"]
        res.check("puff cap gathering vs armhole", lo <= ease <= hi,
                  f"cap {cap:.2f} cm - armhole {total:.2f} cm = {ease:.2f} cm gathered (accepted {lo:g}..{hi:g})",
                  f"Puff sleeve cap ({cap:.1f} cm) gathers {ease:.1f} cm into the armhole ({total:.1f} cm); "
                  f"outside {lo:g}..{hi:g} cm")
    else:
        lo, hi = dv.cap_ease_min, dv.cap_ease_max
        res.check("sleeve cap vs armhole", lo - 1e-6 <= ease <= hi + 1e-6,
                  f"cap {cap:.2f} cm - armhole {total:.2f} cm = ease {ease:.2f} cm (accepted {lo:g}..{hi:g})",
                  f"Sleeve cap ({cap:.1f} cm) is not compatible with the armhole ({total:.1f} cm); ease {ease:.1f} cm")
    if sleeve_piece.notches:
        flat = _flat_cap_ok(sleeve_piece, front, back)
        res.check("sleeve notches meet the armhole notches", flat[0], flat[1],
                  "Sleeve notches are not at the bodice notches' distance from the underarm")
    return {"front_armhole_seam_cm": front.meta["armhole_length_cm"], "back_armhole_seam_cm": back.meta["armhole_length_cm"],
            "total_armhole_seam_cm": total, "sleeve_cap_seam_cm": cap, "cap_ease_cm": ease,
            "sleeve_cap_front_cm": sleeve_piece.meta["cap_front_length_cm"],
            "sleeve_cap_back_cm": sleeve_piece.meta["cap_back_length_cm"],
            "allowed_cap_ease_min_cm": lo, "allowed_cap_ease_max_cm": hi, "gathered": gathered}


def validate_base_block(base):
    res = _Result()
    for piece in base.pieces:
        validate_piece(piece, res)
    _pair_checks(base.front, base.back, base.dv, res)
    info = {}
    if base.sleeve is not None:                       # sleeveless designs have no sleeve block
        info = _sleeve_checks(base.front, base.back, base.sleeve, res, base.dv)
        if base.armhole.get("cap_fit") == "adjusted":
            res.check("sleeve cap solved to target",
                      abs(info["cap_ease_cm"] - base.dv.sleeve_cap_ease) <= CAP_EASE_SOLVE_TOL_CM,
                      f"ease {info['cap_ease_cm']:.3f} vs target {base.dv.sleeve_cap_ease:g}",
                      "Sleeve cap length does not match its target")
    out = res.dump()
    out["armhole_sleeve"] = {k: (round(v, 3) if isinstance(v, float) else v) for k, v in info.items()}
    out["scope"] = "geometry validation only; not a fit or sewing validation"
    return out


SA_TOL_CM = 0.05


def validate_construction(piece, res):
    """Seam-allowance geometry, notches, grainline, fold, quantity and labelling of one final piece."""
    p = piece.name
    cut, seam = piece.cut_outline, piece.seam_outline
    res.check(f"{p}: cutting line present", bool(cut) and bool(seam), "seam allowance geometry attached",
              f"{p}: no cutting-line geometry (seam allowance missing)")
    if not cut or not seam:
        return
    finite = g.all_finite(cut)
    res.check(f"{p}: cutting line finite", finite, "all coordinates finite", f"{p}: cutting line has non-finite coordinates")
    if not finite:
        return
    crossings = g.self_intersections(cut)
    res.check(f"{p}: cutting line simple", not crossings, "no self-intersection",
              f"{p}: seam allowance makes the cutting line self-intersect (edges {crossings[:3]})")
    res.check(f"{p}: cutting line encloses seam line",
              g.polygon_area(cut) > g.polygon_area(seam) and all(g.point_in_polygon(q, cut) for q in seam),
              f"cut {g.polygon_area(cut):.1f} cm2 > seam {g.polygon_area(seam):.1f} cm2",
              f"{p}: cutting line does not enclose the seam line")
    short_by, matched, checked = 0.0, 0, 0
    n = len(seam)
    for i in range(n):
        a, b = seam[i], seam[(i + 1) % n]
        if g.dist(a, b) < 0.3:
            continue          # tiny curve facets: corner mitres dominate
        mid = ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)
        want = piece.edge_offsets[i]
        got = sa.point_polyline_distance(mid, cut, piece.fold_line if piece.cut_on_fold else None)
        checked += 1
        short_by = max(short_by, want - got)
        matched += abs(got - want) <= SA_TOL_CM + 0.05 * want
    # never LESS than specified anywhere; and the offset really is applied along (nearly) the whole outline
    # (a tight concave curve, e.g. a neck point, is trimmed and may legitimately exceed the value locally)
    res.check(f"{p}: seam allowance width", short_by <= SA_TOL_CM and matched >= 0.85 * max(checked, 1),
              f"minimum shortfall {short_by:.3f} cm; {matched}/{checked} edges at the exact allowance",
              f"{p}: seam allowance is narrower than specified by {short_by:.2f} cm")
    res.check(f"{p}: allowance values", all(v >= 0 for v in piece.edge_offsets) and piece.seam_allowance_cm > 0,
              f"seam {piece.seam_allowance_cm} cm", f"{p}: invalid seam allowance")
    gr = piece.grain
    res.check(f"{p}: grainline", gr is not None and g.all_finite(list(gr)) and g.dist(gr[0], gr[1]) > 1.0,
              "grainline present", f"{p}: missing or degenerate grainline")
    res.check(f"{p}: fold line", (not piece.cut_on_fold) or (piece.fold_line is not None and g.dist(*piece.fold_line) > 1.0),
              "fold line present when cut on fold", f"{p}: cut-on-fold piece has no fold line")
    res.check(f"{p}: cut quantity", isinstance(piece.cut_count, int) and piece.cut_count >= 1,
              f"cut {piece.cut_count}", f"{p}: invalid cut quantity")
    res.check(f"{p}: label", bool(piece.name and piece.name.strip()), "named", "A pattern piece has no name")
    bad = [nt["id"] for nt in piece.notches if sa.point_polyline_distance(tuple(nt["point"]), seam) > 0.05]
    res.check(f"{p}: notches on seam line", not bad, f"{len(piece.notches)} notches",
              f"{p}: notches {bad} do not lie on the seam line")
    if piece.piece_type in ("front_bodice", "back_bodice", "sleeve"):
        need = {"front_bodice": 2, "back_bodice": 1, "sleeve": 4}[piece.piece_type]
        res.check(f"{p}: notches present", len(piece.notches) >= need, f"{len(piece.notches)} notches (need {need})",
                  f"{p}: balance notches are missing")


def _completeness(final, res):
    """The right set of pieces exists for the confirmed design and block."""
    types = [p.piece_type for p in final.pieces]
    attrs = final.attributes
    need = ["front_bodice", "back_bodice"]
    if attrs["sleeve_length"] == "sleeveless":
        need.append("armhole_facing")
    else:
        need.append("sleeve")
        if final.sleeve is not None and final.sleeve.meta.get("gathered_hem"):
            need.append("sleeve_band")
    if final.base.block.get("add_neckband"):
        need.append("neckband")
    missing = [t for t in need if t not in types]
    res.check("required pieces", not missing, f"pieces: {', '.join(types)}",
              f"Required pattern pieces are missing: {', '.join(missing)}")
    dv = final.dv
    if dv.darts and dv.front_dart > 1e-9:
        res.check("front waist dart present", any(d["id"] == "front_waist_dart" for d in final.front.darts),
                  "front waist dart present", "Woven bodice is missing its front waist dart")
    if dv.darts and dv.front_extra > 0:
        res.check("bust dart present", any(d["id"] == "front_side_dart" for d in final.front.darts),
                  "side-seam bust dart present", "Woven bodice is missing its side-seam bust dart")


def validate_final_pattern(final):
    """final: FinalPattern (transformations.py)."""
    res = _Result()
    for piece in final.pieces:
        validate_piece(piece, res)
        validate_construction(piece, res)
    _completeness(final, res)
    _pair_checks(final.front, final.back, final.dv, res)
    info = None
    if final.sleeve is not None:
        info = _sleeve_checks(final.front, final.back, final.sleeve, res, final.dv)
        res.check("sleeve hem below cap", final.sleeve.meta["length_cm"] > final.sleeve.meta["cap_height_cm"],
                  f"hem {final.sleeve.meta['length_cm']:.1f} cm, cap {final.sleeve.meta['cap_height_cm']:.1f} cm",
                  "Sleeve hem is not below the sleeve cap")
    res.check("transformations recorded", bool(final.transformations),
              f"{len(final.transformations)} recorded", "Final pattern carries no transformation record")
    out = res.dump()
    if info:
        out["armhole_sleeve"] = {k: (round(v, 3) if isinstance(v, float) else v) for k, v in info.items()}
    out["scope"] = "geometry validation only; not a fit or sewing validation"
    return out
