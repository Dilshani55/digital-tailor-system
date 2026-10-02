"""The four garment models the app uses to SUGGEST a design from a photo (the user always confirms it).

    garment_type   blouse / t-shirt                              MobileNetV3-Large   backend/model/garment_mobilenetv3.pt
    neckline_type  round / v / square / collared                 YOLOv8n-cls         backend/model/neckline_yolov8.pt
    sleeve_length  sleeveless / short / long                     YOLOv8n-cls         backend/model/sleeve_length_yolov8.pt
    sleeve_style   regular / puff / bell (only with sleeves)     YOLOv8n-cls         backend/model/sleeve_design_yolov8.pt

Each model is an image classifier that looks at the garment area (found by the garment detector) padded to a
square. The neckline and the sleeve style can also have a PART model (neckline_part_yolov8.pt,
sleeve_design_part_yolov8.pt) that looks at the neck area / at each sleeve alone, found inside the garment area by
the part detector (app/ai/garment_parts.py). backend/model/inputs.json says which is used for a feature:
    "garment"           the garment model only                                              - the default
    "neck" / "sleeve"   the part model only; part not found -> "uncertain - please select"
    "garment+neck" / "garment+sleeve"
                        the average of both models; part not found -> the garment model alone
The choice is made on validation photos by backend/training/evaluate_models.py.
Training and evaluation: backend/training/.

A suggestion is filled in for the user only when the model's score is at or above that model's threshold in
backend/model/thresholds.json (chosen on validation photos so that accepted answers were at least 90 % correct).
No threshold (null) means the feature is always shown as "uncertain - please select".
Sleeve style is not predicted for a sleeveless garment: it is "none" by definition.
"""
import hashlib
import json
import os
import threading

from app.ai import garment_parts
from app.ai.preprocess import crop_box, load_rgb, square_pad

MODEL_DIR = os.environ.get("GARMENT_MODEL_DIR") or os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "model"))
HEADS = ["garment_type", "neckline_type", "sleeve_length", "sleeve_style"]
FILES = {
    "garment_type": "garment_mobilenetv3.pt",
    "neckline_type": "neckline_yolov8.pt",
    "sleeve_length": "sleeve_length_yolov8.pt",
    "sleeve_style": "sleeve_design_yolov8.pt",
}
ARCHITECTURE = {"garment_type": "MobileNetV3-Large", "neckline_type": "YOLOv8n-cls",
                "sleeve_length": "YOLOv8n-cls", "sleeve_style": "YOLOv8n-cls"}
THRESHOLDS_FILE = "thresholds.json"
INPUTS_FILE = "inputs.json"
PART_FILES = {"neckline_type": "neckline_part_yolov8.pt", "sleeve_style": "sleeve_design_part_yolov8.pt"}
PART_OF = {"neckline_type": "neck", "sleeve_style": "sleeve"}
MODEL_TYPE = "four image classifiers (MobileNetV3-Large garment type; YOLOv8n-cls neckline, sleeve length, sleeve style); not an object detector"
MODEL_VERSION = "garment-models-v1"
IMAGE_SIZE = 224

_lock = threading.Lock()
_cache = {}                     # head -> {"key": (path, mtime), "model": ..., "classes": [...], "sha256": ...}


class GarmentModelError(Exception):
    """A model file is missing or unusable, or the photo cannot be read."""


def model_dir():
    return os.environ.get("GARMENT_MODEL_DIR") or MODEL_DIR


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_mobilenet(path):
    import torch
    from torch import nn
    from torchvision.models import mobilenet_v3_large
    bundle = torch.load(path, map_location="cpu", weights_only=False)
    if bundle.get("architecture") != "mobilenet_v3_large" or not bundle.get("classes"):
        raise GarmentModelError("not a garment-type checkpoint")
    net = mobilenet_v3_large(weights=None)
    net.classifier[3] = nn.Linear(net.classifier[3].in_features, len(bundle["classes"]))
    net.load_state_dict(bundle["state_dict"])
    net.eval()
    return {"net": net, "mean": bundle["mean"], "std": bundle["std"]}, list(bundle["classes"])


def _load_yolo(path):
    from ultralytics import YOLO
    model = YOLO(path)
    if getattr(model, "task", None) != "classify":
        raise GarmentModelError("not a classification checkpoint")
    names = model.names
    return model, [names[i] for i in range(len(names))]


def _get(head, part=False):
    """The loaded model of a feature (`part=True`: its part model). Cached under the head name / "<head>:part"."""
    path = os.path.join(model_dir(), (PART_FILES if part else FILES)[head])
    name = f"{head}:part" if part else head
    if not os.path.isfile(path):
        raise GarmentModelError(f"model file for {name} is missing")
    key = (path, os.path.getmtime(path))
    with _lock:
        entry = _cache.get(name)
        if entry and entry["key"] == key:
            return entry
        try:
            model, classes = _load_mobilenet(path) if head == "garment_type" else _load_yolo(path)
        except GarmentModelError:
            raise
        except Exception as exc:                                     # corrupt file, incompatible library ...
            raise GarmentModelError(f"model for {name} could not be loaded: {exc}")
        entry = {"key": key, "model": model, "classes": classes, "sha256": _sha256(path)}
        _cache[name] = entry
        return entry


def reset_models():
    """Forget loaded models (tests)."""
    with _lock:
        _cache.clear()


def load_thresholds():
    """{head: float | None}. A missing file or entry means None: the head is never answered automatically."""
    out = {h: None for h in HEADS}
    path = os.path.join(model_dir(), THRESHOLDS_FILE)
    if os.path.isfile(path):
        try:
            data = json.load(open(path, encoding="utf-8"))
        except (OSError, ValueError):
            return out
        for h in HEADS:
            v = data.get(h)
            if isinstance(v, (int, float)) and not isinstance(v, bool) and 0.0 < v <= 1.0:
                out[h] = float(v)
    return out


def input_kinds(head):
    """The values inputs.json may hold for a feature."""
    part = PART_OF.get(head)
    return ("garment", part, f"garment+{part}") if part else ("garment",)


def load_inputs():
    """{head: kind}: which model(s) answer a feature (see the top of this file). Missing file or entry: "garment"."""
    out = {h: "garment" for h in HEADS}
    path = os.path.join(model_dir(), INPUTS_FILE)
    if os.path.isfile(path):
        try:
            data = json.load(open(path, encoding="utf-8"))
        except (OSError, ValueError):
            return out
        for h in HEADS:
            if data.get(h) in input_kinds(h):
                out[h] = data[h]
    return out


def models_status():
    """Which models can be used right now (each one is really loaded once). Never raises, exposes no paths."""
    models, hashes = {}, []
    for head in HEADS:
        try:
            entry = _get(head)
            models[head] = {"available": True, "architecture": ARCHITECTURE[head], "classes": entry["classes"],
                            "sha256": entry["sha256"]}
            hashes.append(entry["sha256"])
        except GarmentModelError as exc:
            models[head] = {"available": False, "architecture": ARCHITECTURE[head], "reason": str(exc)}
    available = [h for h in HEADS if models[h]["available"]]
    return {
        "available": bool(available),
        "complete": len(available) == len(HEADS),
        "model_type": MODEL_TYPE,
        "model_version": MODEL_VERSION,
        # one fingerprint for the set of loaded models (hash of their hashes)
        "checkpoint_sha256": hashlib.sha256("".join(hashes).encode()).hexdigest() if hashes else None,
        "models": models,
        "thresholds": load_thresholds(),
        "inputs": load_inputs(),
        "part_detector_available": garment_parts.available(model_dir()),
        "part_models_available": {h: os.path.isfile(os.path.join(model_dir(), f)) for h, f in PART_FILES.items()},
    }


def _probabilities(head, image, part=False):
    """[(class, probability)] for one prepared (square) image, in the model's class order."""
    import torch
    entry = _get(head, part)
    if head == "garment_type":
        from torchvision import transforms
        m = entry["model"]
        x = transforms.Compose([transforms.Resize((IMAGE_SIZE, IMAGE_SIZE)), transforms.ToTensor(),
                                transforms.Normalize(m["mean"], m["std"])])(image).unsqueeze(0)
        with torch.inference_mode():
            p = torch.softmax(m["net"](x), dim=1)[0].tolist()
    else:
        with _lock:                                                  # the Ultralytics predictor is not re-entrant
            result = entry["model"].predict(image, imgsz=IMAGE_SIZE, device="cpu", verbose=False)[0]
        p = result.probs.data.tolist()
    return list(zip(entry["classes"], [float(v) for v in p]))


def _mean(runs):
    """Average of several [(class, probability)] lists, matched by class name (the models order classes differently)."""
    classes = [c for c, _ in runs[0]]
    tables = [dict(r) for r in runs]
    return [(c, sum(t[c] for t in tables) / len(tables)) for c in classes]


def component_probabilities(head, image, parts=None, garment=True):
    """
    The answers a feature's models give for one prepared garment picture:
    {"garment": pairs or None, "part": pairs or None}. "part" is None when the part was not found (or the part
    model / part detector is missing); "garment" is None when the garment model file is missing.
    """
    out = {"garment": None, "part": None}
    if garment:
        try:
            out["garment"] = _probabilities(head, image)
        except GarmentModelError:
            pass
    if head in PART_FILES and os.path.isfile(os.path.join(model_dir(), PART_FILES[head])):
        if parts is None:
            parts = garment_parts.part_pictures(image, model_dir())
        pictures = parts[PART_OF[head]]
        if pictures:                                   # both sleeves: their scores are averaged
            out["part"] = _mean([_probabilities(head, picture, part=True) for picture in pictures])
    return out


def combine(kind, answers):
    """([(class, probability)], trusted) for an inputs.json kind. `trusted` False: must not be an automatic answer."""
    garment, part = answers["garment"], answers["part"]
    if kind == "garment":
        return garment, True
    if "+" in kind:                                    # both models; without the part, the garment model alone
        if garment is None:
            return part, part is not None
        return (_mean([garment, part]) if part else garment), True
    # the part model only: without the part, show the garment model's guess but never fill it in
    return (part, True) if part else (garment, False)


def head_probabilities(head, image, parts=None, kind=None):
    """
    ([(class, probability)], trusted) for one prepared garment picture, following inputs.json (or `kind`).
    Raises GarmentModelError when no model of the feature can answer.
    """
    kind = kind or load_inputs()[head]
    if kind == "garment":
        return _probabilities(head, image), True
    answers = component_probabilities(head, image, parts, garment="+" in kind)
    if answers["part"] is None and answers["garment"] is None:
        answers["garment"] = _probabilities(head, image)           # the part model cannot answer: the garment model's guess
    return combine(kind, answers)


def prepare(image_path, bbox=None):
    """The picture every model sees: the photo upright, cropped to `bbox` (already padded by the caller), square."""
    try:
        image = load_rgb(image_path)
    except Exception as exc:
        raise GarmentModelError(f"the photo could not be read: {exc}")
    return square_pad(crop_box(image, bbox, margin=0.0))


def _prediction(pairs, threshold, part_found=True):
    ranked = sorted(pairs, key=lambda cp: -cp[1])
    label, confidence = ranked[0][0], round(ranked[0][1], 4)
    uncertain = threshold is None or confidence < threshold or not part_found
    return {
        "label": label,
        "confidence": confidence,
        "top_3": [{"class_name": c, "confidence": round(p, 4)} for c, p in ranked[:3]],
        "requires_user_confirmation": uncertain,
        "uncertain": uncertain,              # "uncertain / please select": the UI must not pre-select this guess
        "threshold_used": threshold,
        "part_found": part_found,            # False: the neck / sleeve was not found, the guess is from the whole garment
    }


def predict_attributes(image_path, bbox=None, heads=None):
    """
    Suggestions for one photo, in the structure the rest of the app stores and shows:
    {"predictions": {head: {label, confidence, top_3, uncertain, ...}}, "low_confidence_heads": [...], ...}.
    A head whose model file is missing is left out (the user selects it). Raises GarmentModelError when no model
    can be used or the photo cannot be read.
    """
    image = prepare(image_path, bbox)
    thresholds = load_thresholds()
    inputs = load_inputs()
    parts = garment_parts.part_pictures(image, model_dir()) if any(inputs[h] != "garment" for h in (heads or HEADS)) else None
    # (one run of the part detector serves the neckline and the sleeve style)
    predictions, hashes, missing = {}, [], []
    for head in (heads or HEADS):
        if head == "sleeve_style" and (predictions.get("sleeve_length") or {}).get("label") == "sleeveless":
            base = predictions["sleeve_length"]
            predictions[head] = {
                "label": "none", "confidence": base["confidence"],
                "top_3": [{"class_name": "none", "confidence": base["confidence"]}],
                "requires_user_confirmation": base["uncertain"], "uncertain": base["uncertain"],
                "threshold_used": base["threshold_used"], "derived_from": "sleeve_length",
            }
            continue
        try:
            pairs, part_found = head_probabilities(head, image, parts)
        except GarmentModelError:
            missing.append(head)
            continue
        predictions[head] = _prediction(pairs, thresholds[head], part_found)
        hashes += [_cache[k]["sha256"] for k in (head, f"{head}:part") if k in _cache]
    if not predictions:
        raise GarmentModelError("no garment model is available")
    low = [h for h in HEADS if h in predictions and predictions[h]["uncertain"]]
    return {
        "model_version": MODEL_VERSION,
        "model_type": MODEL_TYPE,
        "checkpoint_sha256": hashlib.sha256("".join(hashes).encode()).hexdigest() if hashes else None,
        "predictions": predictions,
        "heads_without_a_model": missing,
        "low_confidence_heads": low,
        "requires_user_confirmation": True,           # the user always confirms the design
    }
