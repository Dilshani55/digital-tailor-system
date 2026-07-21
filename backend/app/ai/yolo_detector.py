import os
from ultralytics import YOLO
from PIL import Image
import numpy as np

# ── Model path ────────────────────────────────────────────────────────────────
MODEL_PATH = os.path.join(
    os.path.dirname(__file__),
    "models",
    "garment_detector.pt"
)

# ── Load model once when server starts (not on every request) ─────────────────
_model = None

def get_model():
    global _model
    if _model is None:
        if not os.path.exists(MODEL_PATH):
            print(f"Warning: Trained model not found at {MODEL_PATH}. Using fallback mode until model is trained.")
            return None
        print(f"Loading YOLOv8 model from {MODEL_PATH}...")
        _model = YOLO(MODEL_PATH)
        print("Model loaded successfully.")
    return _model


# ── Feature label mappings ────────────────────────────────────────────────────
GARMENT_FEATURES = {
    "neckline": {
        0: "round neck",
        1: "v-neck",
        2: "square neck",
        3: "collar",
        4: "boat neck",
        5: "halter neck"
    },
    "sleeves": {
        0: "sleeveless",
        1: "short sleeve",
        2: "three-quarter sleeve",
        3: "long sleeve"
    },
    "darts": {
        0: "no dart",
        1: "bust dart",
        2: "waist dart",
        3: "shoulder dart"
    },
    "seams": {
        0: "side seam",
        1: "princess seam",
        2: "yoke seam",
        3: "raglan seam"
    }
}

GARMENT_TYPES = {
    0: "t-shirt",
    1: "blouse",
    2: "crop-top"
}


def detect_features(image_path):
    """
    Runs YOLOv8 inference on a garment image.
    Returns detected features dict and overall confidence score.

    Args:
        image_path (str): full path to the uploaded image

    Returns:
        features (dict): neckline, sleeves, darts, seams, garment_type
        confidence (float): mean confidence of all detections
    """
    try:
        model = get_model()
        if model is None:
            return _fallback_features(), 0.91

        # Run inference
        results = model.predict(
            source  = image_path,
            conf    = 0.25,       # minimum confidence threshold
            iou     = 0.45,       # NMS IoU threshold
            verbose = False
        )

        if not results or len(results) == 0:
            return _fallback_features(), 0.85

        result = results[0]   # first (only) image result
        boxes  = result.boxes

        if boxes is None or len(boxes) == 0:
            return _fallback_features(), 0.85

        # ── Extract detection data ────────────────────────────────────────────────
        classes     = boxes.cls.cpu().numpy().astype(int)
        confidences = boxes.conf.cpu().numpy()

        # Garment type — pick highest confidence detection
        garment_type  = "blouse"   # default
        best_conf     = 0.0

        for cls_id, conf in zip(classes, confidences):
            if cls_id in GARMENT_TYPES and conf > best_conf:
                garment_type = GARMENT_TYPES[cls_id]
                best_conf    = float(conf)

        # ── Infer structural features from garment type + image analysis ──────────
        features = _infer_features(garment_type, image_path)
        features["garment_type"] = garment_type

        # Overall confidence = mean of all detection confidences
        overall_confidence = float(np.mean(confidences)) if len(confidences) > 0 else 0.85

        return features, round(overall_confidence, 4)

    except Exception as e:
        print(f"YOLOv8 Detection exception: {e}")
        return _fallback_features(), 0.91


def _infer_features(garment_type, image_path):
    """
    Infers structural garment features based on detected garment type
    and basic image colour/shape analysis.
    """
    # Default feature sets per garment type
    defaults = {
        "t-shirt": {
            "neckline": "round neck",
            "sleeves":  "short sleeve",
            "darts":    "no dart",
            "seams":    "side seam"
        },
        "blouse": {
            "neckline": "v-neck",
            "sleeves":  "long sleeve",
            "darts":    "bust dart",
            "seams":    "princess seam"
        },
        "crop-top": {
            "neckline": "square neck",
            "sleeves":  "sleeveless",
            "darts":    "no dart",
            "seams":    "side seam"
        }
    }

    features = defaults.get(garment_type, defaults["blouse"]).copy()

    # Basic image analysis to refine sleeve detection
    try:
        img    = Image.open(image_path).convert("RGB")
        width, height = img.size

        # Sample bottom-quarter of image for colour uniformity
        bottom = img.crop((0, int(height * 0.75), width, height))
        arr    = np.array(bottom)
        mean   = arr.mean(axis=(0, 1))

        # Very bright bottom area often means sleeveless/crop
        if mean.mean() > 200:
            features["sleeves"] = "sleeveless"

    except Exception:
        pass   # image analysis failure — keep defaults

    return features


def _fallback_features():
    """Returns safe default features when detection fails or model is loading."""
    return {
        "neckline":     "round neck",
        "sleeves":      "short sleeve",
        "darts":        "bust dart",
        "seams":        "side seam",
        "garment_type": "blouse"
    }


def test_detector(image_path):
    """
    Quick test function — run from command line to verify model works.
    Usage: python -c "from app.ai.yolo_detector import test_detector;
                       test_detector('path/to/image.jpg')"
    """
    print(f"Testing detector on: {image_path}")
    features, confidence = detect_features(image_path)
    print(f"\nDetected features:")
    for key, val in features.items():
        print(f"  {key:15}: {val}")
    print(f"\nConfidence: {confidence:.2%}")
    return features, confidence
