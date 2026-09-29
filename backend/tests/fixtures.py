"""Shared realistic fixtures for drafting-engine tests (cm)."""

# Three realistic adult-woman measurement profiles (typical small / medium / large builds).
PROFILES = {
    "medium": dict(bust_cm=88, waist_cm=70, hip_cm=94, height_cm=162, neck_cm=36, shoulder_cm=12, across_back_cm=34,
                   back_waist_length_cm=40, armhole_depth_cm=20, garment_length_cm=65, bicep_cm=28, sleeve_cm=55,
                   wrist_cm=16),
    "small": dict(bust_cm=80, waist_cm=62, hip_cm=88, height_cm=155, neck_cm=33, shoulder_cm=11.5, across_back_cm=32,
                  back_waist_length_cm=37.5, armhole_depth_cm=18.5, garment_length_cm=60, bicep_cm=25, sleeve_cm=52,
                  wrist_cm=14.5),
    "large": dict(bust_cm=104, waist_cm=88, hip_cm=112, height_cm=170, neck_cm=39, shoulder_cm=13, across_back_cm=38,
                  back_waist_length_cm=42, armhole_depth_cm=22, garment_length_cm=70, bicep_cm=33, sleeve_cm=58,
                  wrist_cm=17),
}


def measurements(profile="medium", fabric_type="woven", fit_preference="standard", **over):
    m = dict(PROFILES[profile], fabric_type=fabric_type, fit_preference=fit_preference)
    m.update(over)
    return m


def design(garment_type="blouse", neckline="round-neck", length="short-sleeve", style="regular-sleeve"):
    return {"garment_type": garment_type, "neckline_type": neckline, "sleeve_length": length, "sleeve_style": style}
