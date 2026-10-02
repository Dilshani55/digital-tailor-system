"""Finds the neck area and the sleeves inside a garment picture, so that the neckline and sleeve-design models look
at that part alone instead of at the whole garment (where a neckline is only a few pixels).

Model: YOLOv8n object detector, classes `neck` (neckline or collar) and `sleeve`, trained on Fashionpedia part boxes
inside garment crops (backend/training/prepare_part_datasets.py). File: backend/model/part_detector.pt.

`find_parts()` never raises: without the model, or when nothing is found with enough confidence, the part is
reported as not found and the caller treats that feature as "uncertain - please select".
"""
import os
import threading

from app.ai.preprocess import crop_box, square_pad

FILE = "part_detector.pt"
MIN_SCORE = 0.35                 # fixed before testing (the same cut-off as the garment detector), not tuned
MARGIN = {"neck": 0.15, "sleeve": 0.10}      # the margins of the training crops
MAX_SLEEVES = 2
IMAGE_SIZE = 384

_lock = threading.Lock()
_cache = {}                      # path -> (mtime, model)


def _load(path):
    key = os.path.getmtime(path)
    with _lock:
        entry = _cache.get(path)
        if not entry or entry[0] != key:
            from ultralytics import YOLO
            entry = (key, YOLO(path))
            _cache[path] = entry
        return entry[1]


def reset_parts():
    """Forget the loaded model (tests)."""
    with _lock:
        _cache.clear()


def available(model_dir):
    return os.path.isfile(os.path.join(model_dir, FILE))


def choose(detections):
    """From [{class, score, box_xyxy}]: the best neck box and up to two sleeve boxes at or above MIN_SCORE."""
    good = sorted((d for d in detections if d["score"] >= MIN_SCORE), key=lambda d: -d["score"])
    necks = [d["box_xyxy"] for d in good if d["class"] == "neck"]
    sleeves = [d["box_xyxy"] for d in good if d["class"] == "sleeve"]
    return {"neck": necks[0] if necks else None, "sleeves": sleeves[:MAX_SLEEVES]}


def find_parts(image, model_dir):
    """{"neck": box or None, "sleeves": [boxes]} in pixels of `image` (a prepared garment picture)."""
    path = os.path.join(model_dir, FILE)
    if not os.path.isfile(path):
        return {"neck": None, "sleeves": []}
    try:
        model = _load(path)
        with _lock:                                             # the Ultralytics predictor is not re-entrant
            result = model.predict(image, imgsz=IMAGE_SIZE, conf=0.10, device="cpu", verbose=False)[0]
        names = result.names
        detections = [{"class": names[int(b.cls)], "score": float(b.conf), "box_xyxy": [float(v) for v in b.xyxy[0].tolist()]}
                      for b in result.boxes]
    except Exception:                                           # corrupt file, incompatible library: no parts
        return {"neck": None, "sleeves": []}
    return choose(detections)


def part_pictures(image, model_dir):
    """{"neck": [picture] or [], "sleeve": [pictures]}: each part cropped with its training margin, padded square."""
    found = find_parts(image, model_dir)
    return {
        "neck": [square_pad(crop_box(image, found["neck"], margin=MARGIN["neck"]))] if found["neck"] else [],
        "sleeve": [square_pad(crop_box(image, b, margin=MARGIN["sleeve"])) for b in found["sleeves"]],
    }
