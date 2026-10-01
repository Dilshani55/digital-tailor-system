"""
garment_detector.py

Finds the garment in an uploaded photo so the classifier sees a garment crop (what it was trained on) instead of
the whole scene. Model: YOLOv8n object detector fine-tuned on DeepFashion2 boxes with three classes
(top / outerwear / dress); independent test: docs/AI_MODELS.md.

`detect_garment()` never raises. When the model is missing or nothing is found with enough confidence it returns
`box_xyxy=None` and the caller analyses the full image. Box coordinates refer to the EXIF-rotated image (the
same orientation the classifier uses), in pixels, as a TIGHT [x1, y1, x2, y2]; the caller adds CROP_MARGIN
(see pad_box) exactly as the classifier's training crops did.
"""

import hashlib
import os
import threading

from PIL import Image, ImageOps

DEFAULT_DETECTOR_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "model", "garment_detector.pt"))
MIN_SCORE = 0.35          # fixed before testing (not tuned); independent test: docs/AI_MODELS.md
CROP_MARGIN = 0.10        # margin the CALLER adds before classifying (same as the classifier training crops)
SUPPORTED_CLASS = "top"

_model = None
_model_key = None
_model_sha = None
_lock = threading.Lock()


def detector_path() -> str:
    return os.environ.get("GARMENT_DETECTOR_PATH") or DEFAULT_DETECTOR_PATH


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _load(path: str):
    """Loads the YOLO detector once (cached per path)."""
    global _model, _model_key, _model_sha
    with _lock:
        if _model is None or _model_key != path:
            from ultralytics import YOLO
            _model = YOLO(path)
            _model_key = path
            _model_sha = _sha256(path)
    return _model, _model_sha


def reset_detector():
    """Clears the cached model (tests)."""
    global _model, _model_key, _model_sha
    with _lock:
        _model = _model_key = _model_sha = None


def _unavailable(reason: str, sha=None) -> dict:
    return {"available": False, "box_xyxy": None, "class": None, "score": None,
            "model_sha256": sha, "detections": [], "reason": reason}


def choose(detections: list, width: int, height: int) -> dict:
    """
    Picks the detection to crop from `detections` ([{class, score, box_xyxy}]).
    The most confident detection at or above MIN_SCORE decides the garment class; its tight box is clipped to
    the image. Returns {box_xyxy, class, score} (all None when nothing qualifies).
    """
    good = [d for d in detections if d["score"] >= MIN_SCORE]
    if not good:
        return {"box_xyxy": None, "class": None, "score": None}
    best = max(good, key=lambda d: d["score"])
    x1, y1, x2, y2 = best["box_xyxy"]
    box = [max(0.0, x1), max(0.0, y1), min(float(width), x2), min(float(height), y2)]
    return {"box_xyxy": [round(v, 1) for v in box], "class": best["class"], "score": round(float(best["score"]), 4)}


def pad_box(box, width: int, height: int, margin: float = CROP_MARGIN) -> list:
    """Adds `margin` of the box size on every side, clipped to the image (the classifier's crop convention)."""
    x1, y1, x2, y2 = box
    px, py = (x2 - x1) * margin, (y2 - y1) * margin
    return [max(0.0, x1 - px), max(0.0, y1 - py), min(float(width), x2 + px), min(float(height), y2 + py)]


def detect_garment(image_path: str, model_path: str = None) -> dict:
    """
    Returns {"available", "box_xyxy", "class", "score", "model_sha256", "detections", "reason"}.
    `available` is False only when the detector itself cannot run; "nothing found" is available=True, box None.
    """
    path = os.path.abspath(model_path or detector_path())
    if not os.path.exists(path):
        return _unavailable(f"Garment detector not found at {path}")
    try:
        model, sha = _load(path)
    except Exception as e:  # noqa: BLE001 - incompatible/corrupt file: report, never crash the upload
        return _unavailable(f"Garment detector could not be loaded: {e}")
    try:
        with Image.open(image_path) as im:
            img = ImageOps.exif_transpose(im).convert("RGB")
        W, H = img.size
        res = model.predict(img, imgsz=512, conf=0.10, device="cpu", verbose=False)[0]
        names = res.names
        dets = []
        for b in res.boxes:
            dets.append({"class": names[int(b.cls)], "score": float(b.conf),
                         "box_xyxy": [float(v) for v in b.xyxy[0].tolist()]})
        dets.sort(key=lambda d: -d["score"])
    except Exception as e:  # noqa: BLE001
        return _unavailable(f"Garment detection failed: {e}", sha)
    picked = choose(dets, W, H)
    return {"available": True, **picked, "model_sha256": sha,
            "detections": [{**d, "score": round(d["score"], 4), "box_xyxy": [round(v, 1) for v in d["box_xyxy"]]}
                           for d in dets[:5]],
            "reason": None if picked["box_xyxy"] else "No garment found with enough confidence; full image used."}
