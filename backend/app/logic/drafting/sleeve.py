"""
Sleeve geometry.

The sleeve cap is two cubic Bezier quadrants (vertical tangent at the underarm points,
horizontal tangent at the crown). Its width is the eased bicep width. Its HEIGHT is not a
fixed fraction of anything: it is solved (bisection) so that

        cap seam length = total bodice armhole seam length + target cap ease

where the armhole lengths are measured from the generated bodice curves. If no cap height can
give that length (sleeve too wide for the armhole) drafting fails with a structured error.

Sleeve piece coordinates: crown at y = 0, underarm level at y = cap height, x from the left
underarm point.
"""

from app.logic.drafting import geometry as g
from app.logic.drafting.ease import DraftingError
from app.logic.drafting.pieces import Piece

MIN_CAP_HEIGHT = 0.5
MAX_CAP_HEIGHT = 40.0
MIN_HEM_BELOW_UNDERARM = 3.0


def cap_segments(width, height):
    """Left and right cap quadrants for a sleeve of `width` and cap height `height`."""
    a = width / 2.0
    left = g.quarter_ellipse("cap_left", (0.0, height), (a, 0.0), (0.0, 0.0), first_axis="vertical")
    right = g.quarter_ellipse("cap_right", (a, 0.0), (width, height), (width, 0.0), first_axis="horizontal")
    return left, right


def cap_length(width, height):
    left, right = cap_segments(width, height)
    return left.length() + right.length()


def solve_cap_height(width, target_length):
    """Cap height so that the cap seam length equals target_length. Raises if infeasible."""
    minimum = cap_length(width, MIN_CAP_HEIGHT)
    if target_length < minimum:
        raise DraftingError(
            f"The sleeve is too wide for the armhole: even a nearly flat cap over a {width:.1f} cm "
            f"sleeve is {minimum:.1f} cm long but the armhole seam allows {target_length:.1f} cm.",
            code="SLEEVE_TOO_WIDE_FOR_ARMHOLE",
            field_errors={"bicep_cm": [{"code": "NOT_DRAFTABLE", "message":
                          "Bicep (plus ease) is too large for the bodice armhole; check bicep, armhole depth and bust."}]})
    height = g.solve_monotone(lambda h: cap_length(width, h), MIN_CAP_HEIGHT, MAX_CAP_HEIGHT, target_length)
    if height is None:
        raise DraftingError(
            f"No sleeve-cap height reaches the required cap length {target_length:.1f} cm.",
            code="SLEEVE_CAP_NOT_SOLVABLE")
    return height


def _check_length(cap_height, hem_y):
    if hem_y < cap_height + MIN_HEM_BELOW_UNDERARM:
        raise DraftingError(
            f"Sleeve length {hem_y:.1f} cm leaves less than {MIN_HEM_BELOW_UNDERARM:g} cm below the "
            f"sleeve cap ({cap_height:.1f} cm).", code="SLEEVE_TOO_SHORT_FOR_CAP",
            field_errors={"sleeve_cm": [{"code": "NOT_DRAFTABLE", "message":
                          "Sleeve length is too short for this armhole/sleeve cap."}]})


def build_puff_sleeve(dv, cap_height, hem_y, *, spread, rise, gathered_hem, name="Sleeve", sleeve_kind="short"):
    """
    Puff sleeve = the solved plain sleeve, widened by `spread` (fraction of the eased bicep width) and with
    the crown raised by `rise` cm (slash-and-spread at the cap). The cap seam is therefore LONGER than the
    armhole; the excess is gathered between the front and back balance notches (the cap below the notches is
    sewn flat). The underarm-to-hem length of the plain sleeve is kept.
      gathered_hem=True  short puff: straight sides, the full width is gathered into a sleeve band
      gathered_hem=False long puff: fullness only at the cap, tapering to the eased wrist
    """
    _check_length(cap_height, hem_y)
    if not gathered_hem and dv.wrist_width is None:
        raise DraftingError("A long puff sleeve tapers to the wrist, so the wrist measurement is needed.",
                            code="MEASUREMENTS_INCOMPLETE",
                            field_errors={"wrist_cm": [{"code": "REQUIRED", "message": "Wrist is required for this design."}]})
    w = dv.bicep_width * (1.0 + spread)
    h = cap_height + rise
    hem = hem_y + rise
    hem_w = w if gathered_hem else dv.wrist_width
    x_l, x_r = (w - hem_w) / 2.0, (w + hem_w) / 2.0
    left, right = cap_segments(w, h)
    segments = [
        left, right,
        g.Line("underarm_right", (w, h), (x_r, hem)),
        g.Line("hem", (x_r, hem), (x_l, hem)),
        g.Line("underarm_left", (x_l, hem), (0.0, h)),
    ]
    points = {"CROWN": (w / 2.0, 0.0), "UNDERARM_LEFT": (0.0, h), "UNDERARM_RIGHT": (w, h),
              "HEM_LEFT": (x_l, hem), "HEM_RIGHT": (x_r, hem)}
    return Piece(
        name, "sleeve", segments, points, cut_count=2, cut_on_fold=False,
        grain=((w / 2.0, h), (w / 2.0, hem)),
        meta={"cap_length_cm": left.length() + right.length(), "cap_height_cm": h, "width_bicep_cm": w,
              "width_hem_cm": hem_w, "length_cm": hem, "sleeve_kind": sleeve_kind, "sleeve_style": "puff",
              "gathered_cap": True, "gathered_hem": gathered_hem, "spread_fraction": spread, "crown_rise_cm": rise,
              "plain_width_bicep_cm": dv.bicep_width},
    )


def build_bell_sleeve(dv, cap_height, hem_y, *, flare, name="Sleeve", sleeve_kind="short"):
    """
    Bell sleeve = the solved plain sleeve cap (fitted, normal cap ease) flaring from the underarm to a hem
    `flare` x the eased bicep width wider. The hem is a cubic curve that meets both underarm seams at a
    right angle, so the flared sides join into a smooth hem after sewing.
    """
    _check_length(cap_height, hem_y)
    w = dv.bicep_width
    hem_w = w * (1.0 + flare)
    dx = (hem_w - w) / 2.0                                    # shift so the flared hem starts at x = 0
    x_l, x_r = 0.0, hem_w
    slope = dx / (hem_y - cap_height)                         # outward run per cm of seam drop
    k = hem_w / 3.0
    a, b = cap_segments(w, cap_height)
    left = g.Cubic(a.id, *[(x + dx, y) for x, y in a.p])
    right = g.Cubic(b.id, *[(x + dx, y) for x, y in b.p])
    segments = [
        left, right,
        g.Line("underarm_right", (dx + w, cap_height), (x_r, hem_y)),
        # perpendicular to the seam at both ends: tangent (-1, slope) at the right, (-1, -slope) at the left
        g.Cubic("hem", (x_r, hem_y), (x_r - k, hem_y + slope * k), (x_l + k, hem_y + slope * k), (x_l, hem_y)),
        g.Line("underarm_left", (x_l, hem_y), (dx, cap_height)),
    ]
    cx = dx + w / 2.0
    points = {"CROWN": (cx, 0.0), "UNDERARM_LEFT": (dx, cap_height), "UNDERARM_RIGHT": (dx + w, cap_height),
              "HEM_LEFT": (x_l, hem_y), "HEM_RIGHT": (x_r, hem_y), "HEM_CENTRE": (cx, hem_y + 0.75 * slope * k)}
    return Piece(
        name, "sleeve", segments, points, cut_count=2, cut_on_fold=False,
        grain=((cx, cap_height), (cx, hem_y)),
        meta={"cap_length_cm": left.length() + right.length(), "cap_height_cm": cap_height, "width_bicep_cm": w,
              "width_hem_cm": hem_w, "length_cm": hem_y, "sleeve_kind": sleeve_kind, "sleeve_style": "bell",
              "flare_fraction": flare},
    )


def build_sleeve(dv, cap_height, hem_y, *, name="Sleeve", sleeve_kind="full", taper_to_wrist=False):
    """
    Plain sleeve with the given cap height and hem level (distance from the crown = the wanted sleeve length).
    taper_to_wrist=True (long sleeve): the underarm seams run straight from the eased bicep width to the eased
    wrist width at the hem. Otherwise (short sleeve) the sleeve keeps the eased bicep width down to the hem
    (straight sleeve, project assumption) - no wrist measurement is needed.
    """
    w = dv.bicep_width
    if hem_y < cap_height + MIN_HEM_BELOW_UNDERARM:
        raise DraftingError(
            f"Sleeve length {hem_y:.1f} cm leaves less than {MIN_HEM_BELOW_UNDERARM:g} cm below the "
            f"sleeve cap ({cap_height:.1f} cm).", code="SLEEVE_TOO_SHORT_FOR_CAP",
            field_errors={"sleeve_cm": [{"code": "NOT_DRAFTABLE", "message":
                          "Sleeve length is too short for this armhole/sleeve cap."}]})
    if taper_to_wrist:
        if dv.wrist_width is None:
            raise DraftingError("A long sleeve tapers to the wrist, so the wrist measurement is needed.",
                                code="MEASUREMENTS_INCOMPLETE",
                                field_errors={"wrist_cm": [{"code": "REQUIRED", "message": "Wrist is required for this design."}]})
        hem_w = dv.wrist_width
    else:
        hem_w = w
    x_l, x_r = (w - hem_w) / 2.0, (w + hem_w) / 2.0
    left, right = cap_segments(w, cap_height)
    segments = [
        left, right,
        g.Line("underarm_right", (w, cap_height), (x_r, hem_y)),
        g.Line("hem", (x_r, hem_y), (x_l, hem_y)),
        g.Line("underarm_left", (x_l, hem_y), (0.0, cap_height)),
    ]
    points = {"CROWN": (w / 2.0, 0.0), "UNDERARM_LEFT": (0.0, cap_height), "UNDERARM_RIGHT": (w, cap_height),
              "HEM_LEFT": (x_l, hem_y), "HEM_RIGHT": (x_r, hem_y)}
    return Piece(
        name, "sleeve", segments, points, cut_count=2, cut_on_fold=False,
        grain=((w / 2.0, cap_height), (w / 2.0, hem_y)),
        meta={"cap_length_cm": left.length() + right.length(), "cap_height_cm": cap_height,
              "width_bicep_cm": w, "width_hem_cm": hem_w, "length_cm": hem_y, "sleeve_kind": sleeve_kind},
    )
