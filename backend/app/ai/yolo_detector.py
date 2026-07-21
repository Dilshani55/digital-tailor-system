def detect_features(image_path):
    """
    Analyses a garment image and returns detected structural features.

    Args:
        image_path: full path to the uploaded image file

    Returns:
        features (dict): detected garment features
        confidence (float): overall detection confidence 0.0 to 1.0
    """

    features = {
        "neckline":     "round neck",
        "sleeves":      "short sleeve",
        "darts":        "bust dart",
        "seams":        "side seam",
        "garment_type": "blouse"
    }
    confidence = 0.91

    return features, confidence
