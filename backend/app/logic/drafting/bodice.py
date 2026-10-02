"""
Bodice geometry: the BACK and the FRONT half pattern (centre line = x 0, cut on the fold), drafted separately
as the drafting method does (assumptions.py). They are NOT the same shape:

                         back                                   front
  width at underarm      (bust + ease) / 4 - 1/2 in             (bust + ease) / 4 + 1/2 in
  neck point             1/12 bust from the centre, on the      1/4 in nearer the centre, raised 3/8 in for a
                         top line                               bust above 31 in
  neck depth             1 in (design value)                    1/12 bust + 1/4 in (or the entered depth)
  shoulder tip           half shoulder-to-shoulder, 1 in down   1/4 in nearer the centre, 1 in down
  armhole                straight for a third, then a quarter   hollowed 1/2 in and 3/8 in inside that line at one
                         curve to the underarm                  and two thirds, then out to the underarm (longer)
  waist                  waist / 4 - 1/4 in + ease, 1 in dart   waist / 4 + 1/4 in + ease, 1 1/2 in dart under the
                         in the middle of the waist edge        bust point
  length                 to the waist line                      1 in longer; a side-seam dart takes it up

A knit block (T-shirt) uses the same lines without the bust shaping: equal widths, no darts, no raise.

Piece coordinates: cm, x to the right from the centre line, y DOWN. For the back y = 0 is the top construction
line. The front is moved down by its neck raise so that its highest point is at y = 0 (meta["top_line_y_cm"]).
Darts are internal lines only; they are never part of the cutting outline.
"""

import math

from app.logic.drafting import geometry as g
from app.logic.drafting.assumptions import A
from app.logic.drafting.ease import DraftingError
from app.logic.drafting.pieces import Piece

MIN_DART_LENGTH_CM = 4.0


def side_nodes(dv, side):
    """Side-seam reference nodes of one piece in top-line coordinates: underarm, waist, hip (hip may be None)."""
    ext = dv.front_extra if side == "front" else 0.0
    width = dv.front_width if side == "front" else dv.back_width
    waist_x = dv.front_waist_x if side == "front" else dv.back_waist_x
    u = (width, dv.armhole_depth)
    w = (waist_x, dv.waist_y + ext)
    h = None
    if dv.hip_quarter is not None and dv.hip_y is not None:
        # the two pieces share the hip so that waist-to-hip runs out by the same amount on both: the front and
        # back side seams then have the same length, and front + back = half the hip (assumptions: hip_quarter_split)
        delta = (dv.front_waist_x - dv.back_waist_x) / 2.0
        h = (dv.hip_quarter + (delta if side == "front" else -delta), dv.hip_y + ext)
    return u, w, h


def _x_at(u, w, h, y):
    if y <= w[1]:
        return u[0] + (w[0] - u[0]) * (y - u[1]) / (w[1] - u[1])
    if h is None:
        return w[0]
    if y <= h[1]:
        return w[0] + (h[0] - w[0]) * (y - w[1]) / (h[1] - w[1])
    return h[0]


def underarm_to_waist_seam(dv, side):
    """Length of the side seam from the underarm to the waist, as drawn (before the side-seam dart is sewn)."""
    u, w, _ = side_nodes(dv, side)
    return g.dist(u, w)


def side_dart_intake(dv):
    """What the front side seam is longer than the back one (the source: about 1 in); the side-seam dart takes it."""
    if not dv.darts or dv.front_extra <= 0:
        return 0.0
    return underarm_to_waist_seam(dv, "front") - underarm_to_waist_seam(dv, "back")


def _neck_segments(dv, side, neck):
    """Segments from the centre-line neck point to the neck point NP (top-line coordinates)."""
    if side == "back":
        nw, d = dv.neck_half_back, dv.back_neck_depth
        return [g.quarter_ellipse("neckline", (0, d), (nw, 0), (nw, d), first_axis="horizontal")], (0.0, d), (nw, 0.0)
    nw, top = dv.neck_half_front, -dv.front_raise
    shape = (neck or {}).get("shape", "round")
    d = (neck or {}).get("depth", dv.front_neck_depth)
    if shape == "round":
        return [g.quarter_ellipse("neckline", (0, d), (nw, top), (nw, d), first_axis="horizontal")], (0.0, d), (nw, top)
    if shape == "square":
        return [g.Line("neckline_bottom", (0, d), (nw, d)), g.Line("neckline_side", (nw, d), (nw, top))], (0.0, d), (nw, top)
    if shape == "v":
        return [g.Line("neckline", (0, d), (nw, top))], (0.0, d), (nw, top)
    raise DraftingError(f"Unknown neckline shape '{shape}'.", code="UNSUPPORTED_NECKLINE")


def armhole_segments(dv, side):
    """The armhole from the shoulder tip to the underarm (top-line coordinates) and the notch position on it."""
    d, drop = dv.armhole_depth, dv.shoulder_drop
    if side == "back":
        k = (dv.shoulder_half, drop)
        x = (dv.shoulder_half, drop + (d - drop) * A["back_armscye_straight_share"])
        o = (dv.back_width, d)
        segs = [g.Line("armhole_1", k, x),
                g.quarter_ellipse("armhole_2", x, o, (dv.shoulder_half, d), first_axis="vertical")]
        return segs, k, o
    k = (dv.front_shoulder_x, drop)
    x2 = (dv.front_shoulder_x - A["front_armscye_hollow_upper_cm"], drop + (d - drop) / 3.0)
    y1 = (dv.front_shoulder_x - A["front_armscye_hollow_lower_cm"], drop + 2.0 * (d - drop) / 3.0)
    o = (dv.front_width, d)
    return g.spline_through("armhole", [k, x2, y1, o], end_dir=(1.0, 0.0)), k, o


def armhole_notch_distance(dv, side):
    """Seam distance of the balance notch from the UNDERARM, along the armhole (the method's Z / Y1)."""
    segs, _, _ = armhole_segments(dv, side)
    if side == "back":                                   # Z: midpoint of the curved part O-X
        return segs[1].length() / 2.0
    return segs[2].length()                              # Y1: the end of the last span


def build_bodice(dv, side, *, neck=None, hem_y, block_allows_darts=None, name=None):
    """
    Return a Piece for the front or back half bodice. `hem_y` is the hem level below the top line as measured
    (garment length); the front is `dv.front_extra` longer. `block_allows_darts` is accepted for older callers and
    ignored: whether a block has darts is part of the drafting values.
    """
    if side not in ("front", "back"):
        raise ValueError("side must be 'front' or 'back'")
    front = side == "front"
    ext = dv.front_extra if front else 0.0
    shift = dv.front_raise if front else 0.0             # move the front down so its top is at y = 0
    hem = hem_y + ext
    u, w, h = side_nodes(dv, side)
    waist = w[1]

    if hem_y < dv.waist_y - 1e-9:
        raise DraftingError(
            f"Hem level ({hem_y:.1f} cm) is above the waist line ({dv.waist_y:.1f} cm).", code="HEM_ABOVE_WAIST",
            field_errors={"garment_length_cm": [{"code": "NOT_DRAFTABLE", "message":
                          "Garment length puts the hem above the waist."}]})
    below_waist = hem > waist + 1e-9
    if below_waist and h is None:
        missing = [k for k, v in (("hip_cm", dv.hip_quarter), ("waist_to_hip_cm", dv.hip_y)) if v is None]
        raise DraftingError(
            "The hem is below the waist, so the hip and the waist-to-hip measurements are needed to shape the side seam.",
            code="MEASUREMENTS_INCOMPLETE",
            field_errors={k: [{"code": "REQUIRED", "message": "Required for this design."}] for k in missing})

    arm, sp, _ = armhole_segments(dv, side)
    if u[0] - sp[0] <= 0.5 or u[1] - sp[1] <= 2.0:
        raise DraftingError("Armhole geometry is degenerate for these measurements.", code="MEASUREMENTS_NOT_DRAFTABLE")
    neck_segs, cl_neck, np_ = _neck_segments(dv, side, neck)

    nodes = [u]
    if below_waist:
        nodes.append(w)
        if hem > h[1] + 1e-9:
            nodes.append(h)
    hem_side = (_x_at(u, w, h, hem), hem)
    nodes.append(hem_side)
    side_segs = [g.Line(f"side_seam_{i + 1}", nodes[i], nodes[i + 1]) for i in range(len(nodes) - 1)]

    segments = neck_segs + [g.Line("shoulder", np_, sp)] + arm + side_segs + [
        g.Line("hem", hem_side, (0.0, hem)),
        g.Line("centre_line", (0.0, hem), cl_neck),
    ]
    points = {"CENTRE_NECK": cl_neck, "NECK_POINT": np_, "SHOULDER_POINT": sp, "UNDERARM": u,
              "HEM_SIDE": hem_side, "HEM_CENTRE": (0.0, hem), "WAIST_SIDE": w}
    if below_waist and h is not None and hem >= h[1] - 1e-9:
        points["HIP_SIDE"] = h
    if front and dv.bust_point is not None:
        points["BUST_POINT"] = dv.bust_point

    at_waist = not below_waist
    darts = []
    waist_dart = dv.front_dart if front else dv.back_dart
    if waist_dart > 1e-9:
        darts.append(_waist_dart(dv, side, waist_dart, w, hem, at_waist))
        points["DART_APEX"] = tuple(darts[0]["apex"])
    side_take = side_dart_intake(dv) if front else 0.0
    if side_take > 1e-9:
        darts.append(_side_dart(dv, u, w, side_take))

    # the front is moved down by its neck raise: every y of the piece is shifted by the same amount
    if shift:
        segments = [_shift_segment(s, shift) for s in segments]
        points = {k: (p[0], p[1] + shift) for k, p in points.items()}
        darts = [_shift_dart(d, shift) for d in darts]
    top = shift                                           # y of the top construction line in piece coordinates
    width = u[0]
    arm_final = [s for s in segments if s.id.startswith("armhole")]
    side_final = [s for s in segments if s.id.startswith("side_seam")]
    neck_final = [s for s in segments if s.id.startswith("neckline")]
    side_len = g.path_length(side_final)

    piece = Piece(
        name or ("Front Bodice" if front else "Back Bodice"),
        f"{side}_bodice", segments, points, cut_count=1, cut_on_fold=True,
        grain=((width * 0.5, top + dv.armhole_depth), (width * 0.5, top + hem - 1.0)),
        fold_line=((0.0, points["CENTRE_NECK"][1]), (0.0, top + hem)), darts=darts,
        meta={
            "armhole_length_cm": g.path_length(arm_final),
            "armhole_notch_from_underarm_cm": armhole_notch_distance(dv, side),
            "shoulder_length_cm": g.dist(points["NECK_POINT"], points["SHOULDER_POINT"]),
            "side_seam_length_cm": side_len,
            "side_seam_sewn_length_cm": side_len - side_take,
            "neckline_length_cm": g.path_length(neck_final),
            "top_line_y_cm": top, "hem_y_cm": top + hem, "waist_y_cm": top + waist,
            "armhole_depth_y_cm": top + dv.armhole_depth,
            "bust_width_cm": width,
            "waist_edge_cm": w[0], "waist_finished_cm": w[0] - waist_dart,
            "dart_intake_cm": waist_dart, "side_dart_intake_cm": side_take,
            "dart_mode": ("open" if at_waist else "fish") if waist_dart > 1e-9 else "none",
            "front_extra_length_cm": ext,
        },
    )
    piece.dimensions = _dimensions(dv, side, piece, neck, hem, w, h)
    return piece


def _shift_segment(seg, dy):
    pts = [(x, y + dy) for x, y in seg.p]
    return g.Line(seg.id, *pts) if seg.kind == "line" else g.Cubic(seg.id, *pts)


def _shift_dart(dart, dy):
    out = dict(dart)
    for key in ("apex", "leg_a", "leg_b", "lower_apex"):
        if key in out:
            out[key] = [out[key][0], round(out[key][1] + dy, 4)]
    return out


def _waist_dart(dv, side, intake, w, hem, at_waist):
    """Waist dart (internal lines). `open` in a waist-length block, `fish` when the garment continues below."""
    y_w = w[1]
    if side == "front":
        if dv.bust_point is None:
            raise DraftingError("The front waist dart points at the bust, so shoulder to bust point is needed.",
                                code="MEASUREMENTS_INCOMPLETE",
                                field_errors={"shoulder_to_bust_cm": [{"code": "REQUIRED", "message": "Required for this design."}]})
        xc = dv.bust_point[0]
        apex_y = dv.bust_point[1] + A["front_dart_below_bust_point_cm"]
    else:
        xc = w[0] / 2.0                                                    # N: midpoint of the waist edge
        apex_y = dv.armhole_depth + A["back_dart_short_of_underarm_cm"]    # NP = underarm-to-waist - 1 in
    if y_w - apex_y < MIN_DART_LENGTH_CM:
        field = "shoulder_to_bust_cm" if side == "front" else "back_waist_length_cm"
        raise DraftingError(
            f"The {side} waist dart would be shorter than {MIN_DART_LENGTH_CM:g} cm: the waist is too close to the "
            + ("bust point." if side == "front" else "underarm."), code="MEASUREMENTS_NOT_DRAFTABLE",
            field_errors={field: [{"code": "NOT_DRAFTABLE", "message": "Too close to the waist for a dart."}]})
    left, right = (xc - intake / 2.0, y_w), (xc + intake / 2.0, y_w)
    if left[0] <= 0.5 or right[0] >= w[0] - 0.5:
        raise DraftingError("The waist dart does not fit between the centre line and the side seam.",
                            code="MEASUREMENTS_NOT_DRAFTABLE")
    dart = {
        "id": f"{side}_waist_dart", "type": "open" if at_waist else "fish", "intake_cm": round(intake, 3),
        "apex": [round(xc, 4), round(apex_y, 4)],
        "leg_a": [round(left[0], 4), round(left[1], 4)], "leg_b": [round(right[0], 4), round(right[1], 4)],
        "length_cm": round(y_w - apex_y, 3),
    }
    if not at_waist:
        lower = min(A["fish_dart_lower_share"] * (y_w - apex_y), hem - y_w - 2.0)
        if lower > 0.5:
            dart["lower_apex"] = [round(xc, 4), round(y_w + lower, 4)]
        else:
            dart["type"] = "open_inside"                       # hem too close to the waist for a lower half
    return dart


def _side_dart(dv, u, w, intake):
    """Side-seam (bust) dart of the front: on the side seam below the bust level, pointing at the bust point."""
    tx, ty = dv.bust_point
    seam = g.dist(u, w)
    ux_dir = ((w[0] - u[0]) / seam, (w[1] - u[1]) / seam)
    want_y = ty + A["side_dart_below_bust_level_cm"]
    lo, hi = u[1] + intake / 2.0 * ux_dir[1] + 1.0, w[1] - intake / 2.0 * ux_dir[1] - 1.0
    if hi <= lo:
        raise DraftingError("The side seam between the underarm and the waist is too short for the bust dart.",
                            code="MEASUREMENTS_NOT_DRAFTABLE")
    uy = min(max(want_y, lo), hi)
    t = (uy - u[1]) / (w[1] - u[1])
    centre = (u[0] + (w[0] - u[0]) * t, uy)
    upper = (centre[0] - ux_dir[0] * intake / 2.0, centre[1] - ux_dir[1] * intake / 2.0)
    lower = (centre[0] + ux_dir[0] * intake / 2.0, centre[1] + ux_dir[1] * intake / 2.0)
    to_centre = g.dist((tx, ty), centre)
    back_off = min(A["side_dart_point_from_bust_point_cm"], 0.6 * to_centre)
    apex = (tx + (centre[0] - tx) * back_off / to_centre, ty + (centre[1] - ty) * back_off / to_centre)
    return {
        "id": "front_side_dart", "type": "side", "intake_cm": round(intake, 3),
        "apex": [round(apex[0], 4), round(apex[1], 4)],
        "leg_a": [round(upper[0], 4), round(upper[1], 4)], "leg_b": [round(lower[0], 4), round(lower[1], 4)],
        "length_cm": round(g.dist(apex, centre), 3),
    }


def _dimensions(dv, side, piece, neck, hem, w, h):
    """
    Dimension annotations of the block: what is drawn next to the piece in the preview and the PDF. Each has the
    two points it spans (piece coordinates), its value and the id of the "Why this size?" row that explains it.
    """
    front = side == "front"
    top = piece.meta["top_line_y_cm"]
    P = piece.points
    np_, sp, ua, cn = P["NECK_POINT"], P["SHOULDER_POINT"], P["UNDERARM"], P["CENTRE_NECK"]
    out = []

    def dim(did, label, a, b, value=None, trace=None, kind="linear", place="auto"):
        out.append({"id": did, "label": label, "value_cm": round(g.dist(a, b) if value is None else value, 2),
                    "a": [round(a[0], 3), round(a[1], 3)], "b": [round(b[0], 3), round(b[1], 3)],
                    "kind": kind, "place": place, "trace": trace})

    dim("neck_width", "Neck width", (0.0, np_[1]), np_, trace=f"{side}_neck_width", place="above")
    dim("neck_depth", "Front neck depth" if front else "Back neck depth", (0.0, top), cn,
        value=cn[1] - top, trace=f"{side}_neck_depth", place="centre")
    dim("shoulder", "Shoulder", np_, sp, trace=None, place="along")
    dim("shoulder_drop", "Shoulder drop", (sp[0], top), sp, trace="shoulder_drop", place="right")
    dim("armhole_depth", "Armhole depth", (ua[0], top), ua, trace="armhole_depth", place="right")
    arm = [s for s in piece.segments if s.id.startswith("armhole")]
    mid = g.point_at_length(arm, g.path_length(arm) / 2.0)
    dim("armhole_curve", "Armhole curve", mid, mid, value=piece.meta["armhole_length_cm"], kind="curve", place="curve")
    dim("bust_width", "Bust width", (0.0, ua[1]), ua, trace=f"{side}_bust_width", place="on")
    wy = P["WAIST_SIDE"][1]
    if piece.meta["hem_y_cm"] >= wy - 1e-9:
        dim("waist_width", "Waist width", (0.0, wy), P["WAIST_SIDE"], trace=f"{side}_waist_width", place="on")
        dim("shoulder_to_waist", "Shoulder line to waist", (0.0, top), (0.0, wy), value=wy - top,
            trace="waist_level", place="centre")
    if "HIP_SIDE" in P:
        hp = P["HIP_SIDE"]
        dim("hip_width", "Hip width", (0.0, hp[1]), hp, trace="hip_width", place="on")
        dim("waist_to_hip", "Waist to hip", (hp[0], wy), hp, value=hp[1] - wy, trace="hip_level", place="right")
    dim("garment_length", "Garment length", (np_[0], top), (np_[0], piece.meta["hem_y_cm"]),
        value=piece.meta["hem_y_cm"] - top, trace="garment_length", place="inside")
    for d in piece.darts:
        label = {"front_waist_dart": "Waist dart", "back_waist_dart": "Waist dart", "front_side_dart": "Bust dart"}[d["id"]]
        dim(d["id"], label, tuple(d["leg_a"]), tuple(d["leg_b"]), value=d["intake_cm"],
            trace=f"{side}_waist_dart" if "waist" in d["id"] else "front_length_extra", place="dart")
    return out


__all__ = ["build_bodice", "armhole_segments", "armhole_notch_distance", "side_nodes", "side_dart_intake",
           "underarm_to_waist_seam", "math"]
