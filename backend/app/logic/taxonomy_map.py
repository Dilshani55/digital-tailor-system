"""
Map M14 hyphen taxonomy (AI confirm) → CAD / ease_rules space-form labels.
"""

NECKLINE_TO_CAD = {
    "round-neck": "round neck",
    "v-neck": "v-neck",
    "square-neck": "square neck",
    "scoop-neck": "round neck",
    "boat-neck": "boat neck",
    "sweetheart-neck": "sweetheart neck",
    "halter-neck": "halter neck",
    "high-neck": "collar",
    "collared-neck": "collar",
    "off-shoulder": "off-the-shoulder",
}

SLEEVE_LENGTH_TO_CAD = {
    "sleeveless": "sleeveless",
    "cap-length": "cap sleeve",
    "short-sleeve": "short sleeve",
    "elbow-length": "elbow sleeve",
    "three-quarter-sleeve": "three-quarter sleeve",
    "long-sleeve": "long sleeve",
}

SLEEVE_STYLE_TO_CAD = {
    "none": "none",
    "regular-sleeve": "regular sleeve",
    "puff-sleeve": "puff sleeve",
    "bell-sleeve": "bell sleeve",
    "bishop-sleeve": "bishop sleeve",
    "flutter-sleeve": "butterfly sleeve",
    "raglan-sleeve": "regular sleeve",
    "dolman-sleeve": "batwing sleeve",
    "kimono-sleeve": "kimono sleeve",
}


def _space_or_passthrough(value):
    if not value or not isinstance(value, str):
        return value
    return value.replace("-", " ") if "-" in value else value


def confirmed_to_cad_features(confirmed):
    """
    Convert confirmed_attributes (hyphen taxonomy) into detected_features
    keys expected by ParametricEngine / ease_rules.
    """
    confirmed = confirmed or {}
    garment_type = confirmed.get("garment_type", "blouse")
    neckline = confirmed.get("neckline_type", "round-neck")
    sleeve_length = confirmed.get("sleeve_length", "short-sleeve")
    sleeve_style = confirmed.get("sleeve_style", "regular-sleeve")

    cad_neckline = NECKLINE_TO_CAD.get(neckline, _space_or_passthrough(neckline))
    cad_sleeves = SLEEVE_LENGTH_TO_CAD.get(sleeve_length, _space_or_passthrough(sleeve_length))
    cad_style = SLEEVE_STYLE_TO_CAD.get(sleeve_style, _space_or_passthrough(sleeve_style))

    # Woven blouses typically need bust darts; knits / T-shirts do not.
    if garment_type == "blouse":
        darts = "bust dart"
        seams = "side seam"
    elif garment_type == "t-shirt":
        darts = "no dart"
        seams = "side seam"
    else:  # crop-top
        darts = "no dart"
        seams = "side seam"

    return {
        "garment_type": garment_type,
        "neckline": cad_neckline,
        "sleeves": cad_sleeves,
        "sleeve_style": cad_style,
        "sleeve_length_taxonomy": sleeve_length,
        "neckline_taxonomy": neckline,
        "darts": darts,
        "seams": seams,
    }
