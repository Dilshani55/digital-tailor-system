"""Shared realistic fixtures for drafting-engine tests (cm)."""

# Three realistic adult-woman measurement profiles (typical small / medium / large builds).
# sleeve_cm / sleeve_end_cm are a LONG sleeve (it ends at the wrist).
PROFILES = {
    "medium": dict(bust_cm=88, waist_cm=70, hip_cm=94, shoulder_width_cm=37, back_waist_length_cm=40,
                   shoulder_to_bust_cm=25, waist_to_hip_cm=20, garment_length_cm=65, bicep_cm=28, sleeve_cm=55,
                   sleeve_end_cm=16),
    "small": dict(bust_cm=80, waist_cm=62, hip_cm=88, shoulder_width_cm=35, back_waist_length_cm=37.5,
                  shoulder_to_bust_cm=23, waist_to_hip_cm=19, garment_length_cm=60, bicep_cm=25, sleeve_cm=52,
                  sleeve_end_cm=14.5),
    "large": dict(bust_cm=104, waist_cm=88, hip_cm=112, shoulder_width_cm=41, back_waist_length_cm=42,
                  shoulder_to_bust_cm=28, waist_to_hip_cm=21, garment_length_cm=70, bicep_cm=33, sleeve_cm=58,
                  sleeve_end_cm=17),
}

# A SHORT sleeve of each profile: wanted length (shoulder tip to hem) and the arm measured where it ends.
SHORT_SLEEVE_CM = {"small": 22, "medium": 24, "large": 26}
SHORT_SLEEVE_END_CM = {"small": 24, "medium": 27, "large": 32}

# The drafting source's own sample (inches): bust 34, waist 26, hip 36, back width 14, shoulder to bust 9,
# bust points 6 1/2, back waist length 14 (its block is 14 1/2 long), sleeve length 7.
IN = 2.54
SOURCE_SAMPLE = dict(bust_cm=34 * IN, waist_cm=26 * IN, hip_cm=36 * IN, shoulder_width_cm=14 * IN,
                     back_waist_length_cm=14 * IN, shoulder_to_bust_cm=9 * IN, bust_point_distance_cm=6.5 * IN,
                     waist_to_hip_cm=20.0, garment_length_cm=14.5 * IN, bicep_cm=27.0, sleeve_cm=7 * IN,
                     sleeve_end_cm=27.0)


def measurements(profile="medium", fabric_type="woven", fit_preference="standard", **over):
    m = dict(PROFILES[profile], fabric_type=fabric_type, fit_preference=fit_preference)
    m.update(over)
    return m


def short_sleeve(profile="medium", **over):
    """Measurements of a profile with its SHORT sleeve (length and arm at the sleeve end)."""
    return measurements(profile, sleeve_cm=SHORT_SLEEVE_CM[profile], sleeve_end_cm=SHORT_SLEEVE_END_CM[profile], **over)


def design(garment_type="blouse", neckline="round-neck", length="short-sleeve", style="regular-sleeve"):
    return {"garment_type": garment_type, "neckline_type": neckline, "sleeve_length": length, "sleeve_style": style}
