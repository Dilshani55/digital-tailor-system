# ── Ease allowance rules (PROJECT ASSUMPTIONS — not verified against a published table) ──
# Positive = add room, Negative = reduce (for stretch fabrics)

EASE_RULES = {
    "woven": {
        "bust_cm":   10.0,
        "waist_cm":   8.0,
        "hip_cm":    10.0,
        "shoulder":   1.5,
        "back_neck":  0.5
    },
    "knit": {
        "bust_cm":   6.0,
        "waist_cm":  4.0,
        "hip_cm":    6.0,
        "shoulder":  1.0,
        "back_neck": 0.5
    },
    "stretch-knit": {
        "bust_cm":   -2.0,
        "waist_cm":  -2.0,
        "hip_cm":    -2.0,
        "shoulder":   0.5,
        "back_neck":  0.5
    }
}

# Fit preference adjusts circumferential ease (cm)
FIT_EASE_DELTA = {
    "close": -2.0,
    "standard": 0.0,
    "loose": 3.0,
}

# Neckline depth adjustments (cm dropped from base neck)
# Includes both CAD space-form and hyphen taxonomy aliases
NECKLINE_DEPTH = {
    "round neck":        2.0,
    "round-neck":        2.0,
    "v-neck":            8.0,
    "square neck":       4.0,
    "square-neck":       4.0,
    "scoop-neck":        5.0,
    "collar":            1.0,
    "high-neck":         1.0,
    "collared-neck":     1.0,
    "boat neck":         1.5,
    "boat-neck":         1.5,
    "halter neck":      10.0,
    "halter-neck":      10.0,
    "off-the-shoulder":  6.0,
    "off-shoulder":      6.0,
    "one-shoulder":      8.0,
    "sweetheart neck":   7.5,
    "sweetheart-neck":   7.5,
}

# Sleeve length standards (cm from shoulder point)
SLEEVE_LENGTH = {
    "sleeveless":             0.0,
    "cap sleeve":            10.0,
    "cap-length":            10.0,
    "short sleeve":          22.0,
    "short-sleeve":          22.0,
    "elbow sleeve":          32.0,
    "elbow-length":          32.0,
    "three-quarter sleeve":  45.0,
    "three-quarter-sleeve":  45.0,
    "long sleeve":           58.0,
    "long-sleeve":           58.0,
    "single sleeve":         22.0,
    "puff sleeve":           20.0,
    "bell sleeve":           56.0,
    "flared sleeve":         56.0,
    "bishop sleeve":         58.0,
    "balloon sleeve":        54.0,
    "lantern sleeve":        52.0,
    "leg-o'-mutton sleeve":  58.0,
    "cold shoulder sleeve":  54.0,
    "cape sleeve":           32.0,
    "butterfly sleeve":      26.0,
    "slit sleeve":           58.0,
    "batwing sleeve":        56.0,
    "kimono sleeve":         54.0,
    "petal sleeve":          14.0,
    "ruffle sleeve":         30.0,
    "tiered sleeve":         56.0,
}


def apply_ease(measurements, fabric_type, fit_preference="standard"):
    """
    Applies ease allowance to raw body measurements.

    Args:
        measurements (dict): raw body measurements in cm
        fabric_type  (str):  woven | knit | stretch-knit
        fit_preference (str): close | standard | loose

    Returns:
        dict: measurements with ease applied (extra keys preserved)
    """
    rules = EASE_RULES.get(fabric_type, EASE_RULES["woven"])
    fit_delta = FIT_EASE_DELTA.get(fit_preference or "standard", 0.0)

    eased = {
        "bust_cm":    measurements["bust_cm"]   + rules["bust_cm"] + fit_delta,
        "waist_cm":   measurements["waist_cm"]  + rules["waist_cm"] + fit_delta,
        "hip_cm":     measurements["hip_cm"]    + rules["hip_cm"] + fit_delta,
        "height_cm":  measurements["height_cm"],  # no ease on height
        "shoulder":   rules["shoulder"],
        "back_neck":  rules["back_neck"],
        "fit_preference": fit_preference or "standard",
        "fit_delta": fit_delta,
    }

    # Pass through locked drafting measurements unchanged (used directly by engine)
    for key in (
        "neck_cm", "shoulder_cm", "across_back_cm", "back_waist_length_cm",
        "armhole_depth_cm", "armhole_cm", "garment_length_cm",
        "bicep_cm", "sleeve_cm", "wrist_cm",
    ):
        if key in measurements and measurements[key] is not None:
            eased[key] = measurements[key]

    return eased


def get_neckline_depth(neckline_type):
    return NECKLINE_DEPTH.get(neckline_type, 2.0)


def get_sleeve_length(sleeve_type):
    return SLEEVE_LENGTH.get(sleeve_type, 22.0)
