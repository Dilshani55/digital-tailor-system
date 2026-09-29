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


def build_sleeve(dv, cap_height, hem_y, *, name="Sleeve", sleeve_kind="full"):
    """Sleeve piece with the given cap height and hem level (distance from the crown)."""
    w = dv.bicep_width
    if hem_y < cap_height + MIN_HEM_BELOW_UNDERARM:
        raise DraftingError(
            f"Sleeve length {hem_y:.1f} cm leaves less than {MIN_HEM_BELOW_UNDERARM:g} cm below the "
            f"sleeve cap ({cap_height:.1f} cm).", code="SLEEVE_TOO_SHORT_FOR_CAP",
            field_errors={"sleeve_cm": [{"code": "NOT_DRAFTABLE", "message":
                          "Sleeve length is too short for this armhole/sleeve cap."}]})
    total = dv.sleeve_length
    frac = (hem_y - cap_height) / (total - cap_height)
    hem_w = w + (dv.wrist_width - w) * frac
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
