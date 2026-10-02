"""
Sleeve geometry (drafting method: assumptions.py).

The method drafts half a sleeve on folded paper: half width AB, cap height BE = AB / 2, and the cap as a curve
through points set off the diagonal A-E (crown to underarm) at its quarter points:

    back cap   1/2 in and 1/4 in OUTSIDE the diagonal at 1/4 and 1/2, 1/4 in INSIDE at 3/4
    front cap  1/2 in outside at 1/4, ON the diagonal at 1/2, 5/8 in inside at 3/4   (the front is hollowed more)

so the front and back halves of the cap are different curves. Here the whole sleeve is drawn open: the FRONT
half is on the left (x = 0 is the front underarm point), the BACK half on the right, the crown at y = 0.

Fit to the armhole. The bodice armhole seams are measured from the generated curves. The method's cap is kept when
(cap seam - armhole seam) lies inside the accepted cap-ease range; otherwise only the cap HEIGHT is changed until
the cap seam equals the armhole seam plus the target ease (project extension, reported in the result). A sleeve
whose width cannot be matched to the armhole at any height is an error, never a silent adjustment.
"""

from app.logic.drafting import geometry as g
from app.logic.drafting.assumptions import A
from app.logic.drafting.ease import DraftingError
from app.logic.drafting.pieces import Piece

MIN_CAP_HEIGHT = 1.0
MAX_CAP_HEIGHT = 40.0
MIN_HEM_BELOW_UNDERARM = 3.0
QUARTERS = (0.25, 0.5, 0.75)


def cap_paths(width, height):
    """(front segments: front underarm -> crown, back segments: crown -> back underarm)."""
    a = width / 2.0
    crown, back_end, front_end = (a, 0.0), (width, height), (0.0, height)
    length = (a * a + height * height) ** 0.5
    nx, ny = height / length, -a / length                       # outward normal of the back diagonal
    # The method's offsets belong to its own cap (height = half the half-width). A cap that had to be made
    # flatter to fit the armhole gets proportionally smaller offsets, so it keeps the same character.
    scale = min(1.0, height / (A["sleeve_cap_height_share"] * a))

    def through(offsets, mirror):
        pts = []
        for t, off in zip(QUARTERS, offsets):
            off = off * scale
            x = a + (back_end[0] - a) * t + nx * off
            y = height * t + ny * off
            pts.append((2.0 * a - x, y) if mirror else (x, y))
        return pts

    back_pts = [crown] + through(A["sleeve_cap_back_offsets_cm"], False) + [back_end]
    front_pts = [front_end] + list(reversed(through(A["sleeve_cap_front_offsets_cm"], True))) + [crown]
    front = g.spline_through("cap_front", front_pts, end_dir=(1.0, 0.0))
    back = g.spline_through("cap_back", back_pts, start_dir=(1.0, 0.0))
    return front, back


def cap_length(width, height):
    front, back = cap_paths(width, height)
    return g.path_length(front) + g.path_length(back)


def solve_cap_height(width, target_length):
    """Cap height so that the cap seam length equals target_length. Raises if infeasible."""
    minimum = cap_length(width, MIN_CAP_HEIGHT)
    if target_length < minimum:
        raise DraftingError(
            f"The sleeve is too wide for the armhole: even a nearly flat cap over a {width:.1f} cm sleeve is "
            f"{minimum:.1f} cm long but the armhole seam allows {target_length:.1f} cm.",
            code="SLEEVE_TOO_WIDE_FOR_ARMHOLE",
            field_errors={"bicep_cm": [{"code": "NOT_DRAFTABLE", "message":
                          "The sleeve (upper arm plus ease) is too wide for the bodice armhole. Check upper arm around "
                          "and bust around; if both are right, enter a larger armhole depth."}]})
    height = g.solve_monotone(lambda h: cap_length(width, h), MIN_CAP_HEIGHT, MAX_CAP_HEIGHT, target_length)
    if height is None:
        raise DraftingError(f"No sleeve-cap height reaches the required cap length {target_length:.1f} cm.",
                            code="SLEEVE_CAP_NOT_SOLVABLE")
    return height


def fit_cap(dv, armhole_total):
    """
    Cap height for the plain sleeve and how it was found:
    {"cap_height_cm", "method_cap_height_cm", "method_cap_seam_cm", "method_cap_ease_cm", "mode": "method" | "adjusted"}.
    """
    h0 = dv.sleeve_cap_height_method
    seam0 = cap_length(dv.sleeve_width, h0)
    ease0 = seam0 - armhole_total
    info = {"method_cap_height_cm": h0, "method_cap_seam_cm": seam0, "method_cap_ease_cm": ease0}
    if dv.cap_ease_min - 1e-9 <= ease0 <= dv.cap_ease_max + 1e-9:
        return {**info, "cap_height_cm": h0, "mode": "method"}
    return {**info, "cap_height_cm": solve_cap_height(dv.sleeve_width, armhole_total + dv.sleeve_cap_ease), "mode": "adjusted"}


def _check_length(cap_height, hem_y):
    if hem_y < cap_height + MIN_HEM_BELOW_UNDERARM:
        raise DraftingError(
            f"Sleeve length {hem_y:.1f} cm leaves less than {MIN_HEM_BELOW_UNDERARM:g} cm below the "
            f"sleeve cap ({cap_height:.1f} cm).", code="SLEEVE_TOO_SHORT_FOR_CAP",
            field_errors={"sleeve_cm": [{"code": "NOT_DRAFTABLE", "message":
                          "Sleeve length is too short for this armhole/sleeve cap."}]})


def _need_end(dv):
    if dv.sleeve_end_width is None:
        raise DraftingError("This sleeve narrows to the arm at its end, so the sleeve-end measurement is needed.",
                            code="MEASUREMENTS_INCOMPLETE",
                            field_errors={"sleeve_end_cm": [{"code": "REQUIRED", "message":
                                          "Sleeve end around is required for this design."}]})
    return dv.sleeve_end_width


def _shift_x(seg, dx):
    return g.Cubic(seg.id, *[(x + dx, y) for x, y in seg.p])


def _dimensions(piece, extra=()):
    P, m = piece.points, piece.meta
    crown, ul, ur, hl, hr = P["CROWN"], P["UNDERARM_LEFT"], P["UNDERARM_RIGHT"], P["HEM_LEFT"], P["HEM_RIGHT"]
    out = []

    def dim(did, label, a, b, value=None, trace=None, kind="linear", place="auto"):
        out.append({"id": did, "label": label, "value_cm": round(g.dist(a, b) if value is None else value, 2),
                    "a": [round(a[0], 3), round(a[1], 3)], "b": [round(b[0], 3), round(b[1], 3)],
                    "kind": kind, "place": place, "trace": trace})

    hem_y = max(hl[1], hr[1])
    dim("sleeve_length", "Sleeve length", crown, (crown[0], hem_y), value=m["length_cm"], trace="sleeve_length", place="inside")
    dim("sleeve_width", "Sleeve width", ul, ur, trace="sleeve_width", place="on")
    dim("cap_height", "Cap height", (ur[0], 0.0), ur, value=m["cap_height_cm"], trace="sleeve_cap_height", place="right")
    dim("sleeve_end", "Sleeve end width", hl, hr, value=m["width_hem_cm"], trace="sleeve_end_width", place="below")
    front = [s for s in piece.segments if s.id.startswith("cap_front")]
    back = [s for s in piece.segments if s.id.startswith("cap_back")]
    fm, bm = g.point_at_length(front, g.path_length(front) / 2.0), g.point_at_length(back, g.path_length(back) / 2.0)
    dim("cap_front", "Front cap", fm, fm, value=m["cap_front_length_cm"], kind="curve", place="curve")
    dim("cap_back", "Back cap", bm, bm, value=m["cap_back_length_cm"], kind="curve", place="curve")
    return out + list(extra)


def _piece(name, width, cap_height, hem_segments, points, grain, meta, front, back):
    segments = front + back + hem_segments
    meta = {"cap_length_cm": g.path_length(front) + g.path_length(back),
            "cap_front_length_cm": g.path_length(front), "cap_back_length_cm": g.path_length(back),
            "cap_height_cm": cap_height, "width_bicep_cm": width, **meta}
    piece = Piece(name, "sleeve", segments, points, cut_count=2, cut_on_fold=False, grain=grain, meta=meta)
    piece.dimensions = _dimensions(piece)
    return piece


def build_sleeve(dv, cap_height, hem_y, *, name="Sleeve", sleeve_kind="full", taper_to_wrist=None):
    """
    Plain set-in sleeve: the cap over the sleeve width, the seams running straight to the width of the arm at the
    sleeve end (+ ease). `hem_y` is the sleeve length, measured from the crown. `taper_to_wrist` is accepted for
    older callers and ignored: short and long sleeves both follow the measured sleeve end.
    """
    w = dv.sleeve_width
    _check_length(cap_height, hem_y)
    hem_w = _need_end(dv)
    if hem_w > w + 1e-9:
        raise DraftingError(
            f"The sleeve end ({hem_w:.1f} cm with ease) is wider than the sleeve at the underarm ({w:.1f} cm).",
            code="MEASUREMENTS_NOT_DRAFTABLE",
            field_errors={"sleeve_end_cm": [{"code": "NOT_DRAFTABLE", "message":
                          "Sleeve end around is larger than the sleeve; check it and upper arm around."}]})
    x_l, x_r = (w - hem_w) / 2.0, (w + hem_w) / 2.0
    front, back = cap_paths(w, cap_height)
    hem = [g.Line("underarm_right", (w, cap_height), (x_r, hem_y)),
           g.Line("hem", (x_r, hem_y), (x_l, hem_y)),
           g.Line("underarm_left", (x_l, hem_y), (0.0, cap_height))]
    points = {"CROWN": (w / 2.0, 0.0), "UNDERARM_LEFT": (0.0, cap_height), "UNDERARM_RIGHT": (w, cap_height),
              "HEM_LEFT": (x_l, hem_y), "HEM_RIGHT": (x_r, hem_y)}
    return _piece(name, w, cap_height, hem, points, ((w / 2.0, cap_height), (w / 2.0, hem_y)),
                  {"width_hem_cm": hem_w, "length_cm": hem_y, "sleeve_kind": sleeve_kind}, front, back)


def build_puff_sleeve(dv, cap_height, hem_y, *, spread, rise, gathered_hem, name="Sleeve", sleeve_kind="short"):
    """
    Puff sleeve = the fitted plain sleeve, widened by `spread` (fraction of its width) and with the crown raised
    by `rise` cm (slash-and-spread at the cap). The cap seam is therefore LONGER than the armhole; the excess is
    gathered between the front and back balance notches (the cap below the notches is sewn flat). The
    underarm-to-hem length of the plain sleeve is kept.
      gathered_hem=True  short puff: straight sides, the full width is gathered into a sleeve band
      gathered_hem=False long puff: fullness only at the cap, narrowing to the sleeve end
    """
    _check_length(cap_height, hem_y)
    w = dv.sleeve_width * (1.0 + spread)
    h = cap_height + rise
    hem = hem_y + rise
    hem_w = w if gathered_hem else _need_end(dv)
    x_l, x_r = (w - hem_w) / 2.0, (w + hem_w) / 2.0
    front, back = cap_paths(w, h)
    lines = [g.Line("underarm_right", (w, h), (x_r, hem)),
             g.Line("hem", (x_r, hem), (x_l, hem)),
             g.Line("underarm_left", (x_l, hem), (0.0, h))]
    points = {"CROWN": (w / 2.0, 0.0), "UNDERARM_LEFT": (0.0, h), "UNDERARM_RIGHT": (w, h),
              "HEM_LEFT": (x_l, hem), "HEM_RIGHT": (x_r, hem)}
    return _piece(name, w, h, lines, points, ((w / 2.0, h), (w / 2.0, hem)),
                  {"width_hem_cm": hem_w, "length_cm": hem, "sleeve_kind": sleeve_kind, "sleeve_style": "puff",
                   "gathered_cap": True, "gathered_hem": gathered_hem, "spread_fraction": spread, "crown_rise_cm": rise,
                   "plain_width_bicep_cm": dv.sleeve_width}, front, back)


def build_bell_sleeve(dv, cap_height, hem_y, *, flare, name="Sleeve", sleeve_kind="short"):
    """
    Bell sleeve = the fitted plain cap, flaring from the underarm to a hem `flare` x the sleeve width wider. The
    hem is a cubic curve that meets both underarm seams at a right angle, so the flared sides join into a smooth
    hem after sewing.
    """
    _check_length(cap_height, hem_y)
    w = dv.sleeve_width
    hem_w = w * (1.0 + flare)
    dx = (hem_w - w) / 2.0                                    # shift so the flared hem starts at x = 0
    x_l, x_r = 0.0, hem_w
    slope = dx / (hem_y - cap_height)                         # outward run per cm of seam drop
    k = hem_w / 3.0
    f0, b0 = cap_paths(w, cap_height)
    front, back = [_shift_x(s, dx) for s in f0], [_shift_x(s, dx) for s in b0]
    lines = [
        g.Line("underarm_right", (dx + w, cap_height), (x_r, hem_y)),
        # perpendicular to the seam at both ends: tangent (-1, slope) at the right, (-1, -slope) at the left
        g.Cubic("hem", (x_r, hem_y), (x_r - k, hem_y + slope * k), (x_l + k, hem_y + slope * k), (x_l, hem_y)),
        g.Line("underarm_left", (x_l, hem_y), (dx, cap_height)),
    ]
    cx = dx + w / 2.0
    points = {"CROWN": (cx, 0.0), "UNDERARM_LEFT": (dx, cap_height), "UNDERARM_RIGHT": (dx + w, cap_height),
              "HEM_LEFT": (x_l, hem_y), "HEM_RIGHT": (x_r, hem_y), "HEM_CENTRE": (cx, hem_y + 0.75 * slope * k)}
    return _piece(name, w, cap_height, lines, points, ((cx, cap_height), (cx, hem_y)),
                  {"width_hem_cm": hem_w, "length_cm": hem_y, "sleeve_kind": sleeve_kind, "sleeve_style": "bell",
                   "flare_fraction": flare}, front, back)
