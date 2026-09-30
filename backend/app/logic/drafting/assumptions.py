"""
Registry of every non-measured constant used by the drafting engine.

SOURCE STATUS (research honesty):
  derived_geometry   follows from geometry/definitions given the measurements
  project_assumption a value chosen by this project. NOT taken from, or verified against,
                     Aldrich or any other published drafting table (no such source text is
                     available in this repository). Must be validated by fitting trials.

Nothing in this engine is labelled "Aldrich" because none of its equations can be traced to
the book from the material in this project.
"""

DERIVED = "derived_geometry"
ASSUMPTION = "project_assumption"

ASSUMPTIONS = {
    "neck_half_width": dict(
        status=DERIVED, value="neck_cm / 6",
        note="Neck base modelled as a circle: radius = circumference / 2*pi ~= neck/6.28, rounded to /6."),
    "back_neck_depth_cm": dict(
        status=ASSUMPTION, value=2.0,
        note="Vertical drop of the centre-back neck point below the neck/shoulder point."),
    "front_neck_extra_depth_cm": dict(
        status=ASSUMPTION, value=1.0,
        note="Base round front neck depth = neck_half_width + 1.0 cm."),
    "shoulder_slope_deg": dict(
        status=ASSUMPTION, value=18.0,
        note="Shoulder line drops at this angle below horizontal; used for front and back so the "
             "two shoulder seams have the same measured length."),
    "shoulder_length": dict(
        status=DERIVED, value="measured shoulder_cm",
        note="Shoulder seam length equals the measurement; no ease added."),
    "armhole_depth": dict(
        status=DERIVED, value="measured armhole_depth_cm",
        note="Measured vertically from the neck/shoulder-point level (y = 0) to the underarm level."),
    "waist_level_y": dict(
        status=DERIVED, value="back_neck_depth + back_waist_length_cm",
        note="Waist line measured down the spine from the nape (centre-back neck point)."),
    "hip_depth_below_waist_cm": dict(
        status=ASSUMPTION, value=20.0,
        note="Waist-to-hip distance; no such measurement is collected. Used only to shape the side "
             "seam of garments that extend below the waist."),
    "side_seam_suppression_share_with_darts": dict(
        status=ASSUMPTION, value=0.5,
        note="Share of (bust - waist) suppression taken at the side seam; the rest goes into the "
             "dart. Without darts the side seam takes all of it."),
    "max_dart_intake_cm": dict(
        status=ASSUMPTION, value=5.0,
        note="Upper limit for one dart's intake; any excess moves to the side seam."),
    "bust_point_x_share": dict(
        status=ASSUMPTION, value=0.42,
        note="Bust point x = 0.42 * quarter bust (no bust-point measurement is collected)."),
    "bust_point_below_underarm_cm": dict(
        status=ASSUMPTION, value=3.0, note="Bust point y = armhole_depth + 3.0 cm."),
    "front_dart_apex_below_bust_point_cm": dict(
        status=ASSUMPTION, value=2.5, note="Front dart stops this far below the bust point."),
    "back_dart_apex_share": dict(
        status=ASSUMPTION, value=0.6,
        note="Back dart length = 0.6 * (waist - armhole depth); centred on the waist edge."),
    "fish_dart_lower_share": dict(
        status=ASSUMPTION, value=0.5,
        note="For garments longer than the waist the dart is a closed fish dart whose lower half "
             "is 0.5 * the upper half (limited by the hem)."),
    "front_armhole_hollow_cm": dict(
        status=ASSUMPTION, value=1.0,
        note="Front armhole control point sits 1.0 cm nearer the centre than the across-back line; "
             "back control point sits on half the measured across-back width."),
    "curve_kappa": dict(
        status=DERIVED, value=0.5523,
        note="Cubic-Bezier constant for an elliptical quadrant."),
    "v_neck_extra_depth_cm": dict(
        status=ASSUMPTION, value=3.0, note="V-neck centre-front depth = base front neck depth + 3.0 cm."),
    "square_neck_depth": dict(
        status=ASSUMPTION, value="same as base front neck depth",
        note="Square neck keeps the base neck width and depth; only the shape changes."),
    "crop_min_hem_below_underarm_cm": dict(
        status=ASSUMPTION, value=6.0, note="Crop hem must be at least 6 cm below the underarm level."),
    "crop_max_hem_above_waist_cm": dict(
        status=ASSUMPTION, value=2.0,
        note="Crop-top hem must be at least 2 cm above the waist line; regular length must reach the waist."),
    "sleeve_length_fraction": dict(
        status=ASSUMPTION,
        value={"short-sleeve": 0.40, "elbow-length": 0.58, "three-quarter-sleeve": 0.75, "long-sleeve": 1.00},
        note="Design sleeve length = fraction of the measured full-arm sleeve_cm (shoulder tip to wrist)."),
    "sleeve_ease_cm": dict(
        status=ASSUMPTION, value={"woven_bodice": dict(bicep=5.0, wrist=4.0, cap=2.0),
                                  "knit_bodice": dict(bicep=3.0, wrist=2.0, cap=1.0)},
        note="Added to bicep / wrist circumference; cap = target sleeve-cap ease over the armhole seam length."),
    "sleeve_cap_ease_tolerance_cm": dict(
        status=ASSUMPTION, value=(0.0, 5.0),
        note="Accepted range of (sleeve cap seam - total armhole seam)."),
    "puff_spread_fraction": dict(
        status=ASSUMPTION, value=0.5,
        note="Puff sleeve: the plain sleeve is spread to 1.5 x its eased bicep width (slash-and-spread)."),
    "puff_crown_rise_cm": dict(
        status=ASSUMPTION, value=2.5,
        note="Puff sleeve: crown raised by 2.5 cm so the gathered cap stands up; underarm-to-hem length kept."),
    "puff_gather_excess_range_cm": dict(
        status=ASSUMPTION, value=(4.0, 30.0),
        note="Accepted (puff cap seam - total armhole seam), gathered between the front and back notches."),
    "puff_band_height_cm": dict(
        status=ASSUMPTION, value=2.5,
        note="Short puff sleeve: finished band height; the band strip is cut double (folded) and its length is "
             "the eased bicep width."),
    "bell_flare_fraction": dict(
        status=ASSUMPTION, value={"short-sleeve": 0.6, "long-sleeve": 0.9},
        note="Bell sleeve: hem width = eased bicep width x (1 + fraction); the cap stays the fitted, solved cap."),
    "facing_width_cm": dict(status=ASSUMPTION, value=4.0, note="Armhole facing strip width."),
    "neckband_stretch_factor": dict(
        status=ASSUMPTION, value=0.85, note="Knit neckband length = 0.85 * neckline seam length."),
    "neckband_height_cm": dict(status=ASSUMPTION, value=3.0, note="Neckband strip height."),
}

A = {k: v["value"] for k, v in ASSUMPTIONS.items()}


def assumptions_payload():
    return {k: dict(v) for k, v in ASSUMPTIONS.items()}
