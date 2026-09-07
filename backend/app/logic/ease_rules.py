# ── Ease allowance rules based on Winifred Aldrich standards ──────────────────
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

# Neckline depth adjustments (cm dropped from base neck)
NECKLINE_DEPTH = {
    "round neck":        2.0,
    "v-neck":            8.0,
    "square neck":       4.0,
    "collar":            1.0,
    "boat neck":         1.5,
    "halter neck":      10.0,
    "off-the-shoulder":  6.0,
    "one-shoulder":      8.0,
    "sweetheart neck":   7.5
}

# Sleeve length standards (cm from shoulder point)
SLEEVE_LENGTH = {
    "sleeveless":             0.0,
    "cap sleeve":            10.0,
    "short sleeve":          22.0,
    "elbow sleeve":          32.0,
    "three-quarter sleeve":  45.0,
    "long sleeve":           58.0,
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
    "tiered sleeve":         56.0
}


def apply_ease(measurements, fabric_type):
    """
    Applies ease allowance to raw body measurements.

    Args:
        measurements (dict): raw body measurements in cm
        fabric_type  (str):  woven | knit | stretch-knit

    Returns:
        dict: measurements with ease applied
    """
    rules = EASE_RULES.get(fabric_type, EASE_RULES["woven"])

    eased = {
        "bust_cm":    measurements["bust_cm"]   + rules["bust_cm"],
        "waist_cm":   measurements["waist_cm"]  + rules["waist_cm"],
        "hip_cm":     measurements["hip_cm"]    + rules["hip_cm"],
        "height_cm":  measurements["height_cm"],  # no ease on height
        "shoulder":   rules["shoulder"],
        "back_neck":  rules["back_neck"]
    }

    return eased


def get_neckline_depth(neckline_type):
    return NECKLINE_DEPTH.get(neckline_type, 2.0)


def get_sleeve_length(sleeve_type):
    return SLEEVE_LENGTH.get(sleeve_type, 22.0)
