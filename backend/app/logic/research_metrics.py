"""
Research-metric helpers.

Research-integrity rule: every number returned by the research API must be
either (a) measured from stored data, or (b) read from a genuine evaluation
artefact on disk. When neither is available the value is None ("not measured").
Nothing here supplies a substitute default.
"""

import hashlib
import json
import os
from functools import lru_cache

HEADS = ("garment_type", "neckline_type", "sleeve_length", "sleeve_style")

_BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_REPO_ROOT = os.path.abspath(os.path.join(_BACKEND_DIR, ".."))

# Genuine evaluation artefacts written by ai_training/scripts/train_multitask.py.
# ai_training/data is git-ignored, so the files may be absent on another machine.
EVAL_LOG_DIR = os.environ.get(
    "MODEL_EVAL_LOG_DIR",
    os.path.join(_REPO_ROOT, "ai_training", "data", "training_runs", "m12_full", "logs"),
)
EVAL_CHECKPOINT = os.environ.get(
    "MODEL_EVAL_CHECKPOINT",
    os.path.join(_REPO_ROOT, "ai_training", "data", "training_runs", "m12_full",
                 "checkpoints", "best.pt"),
)
DEPLOYED_CHECKPOINT = os.path.join(
    _BACKEND_DIR, "app", "ai", "models", "garment_multitask_yolov8_best.pt"
)


@lru_cache(maxsize=8)
def _sha256(path, mtime):  # mtime is part of the cache key
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _file_sha256(path):
    try:
        return _sha256(path, os.path.getmtime(path))
    except OSError:
        return None


def _num(value):
    """Return a float for real numbers, None for 'N/A' / missing / non-numeric."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def load_model_evaluation(log_dir=None, eval_checkpoint=None, deployed_checkpoint=None):
    """
    Load the held-out TEST-split metrics of the trained multi-task classifier from
    test_metrics_final.json. Returns {"available": False, "reason": ...} if the
    file is missing or unreadable — never a substitute.
    """
    log_dir = log_dir or EVAL_LOG_DIR
    eval_checkpoint = eval_checkpoint or EVAL_CHECKPOINT
    deployed_checkpoint = deployed_checkpoint or DEPLOYED_CHECKPOINT
    path = os.path.join(log_dir, "test_metrics_final.json")

    if not os.path.exists(path):
        return {
            "available": False,
            "reason": "Evaluation file not found (ai_training/data is not part of the repository).",
            "source": path,
        }
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        by_head = raw["metrics_by_head"]
    except (OSError, ValueError, KeyError) as exc:
        return {"available": False, "reason": f"Evaluation file unreadable: {exc}", "source": path}

    per_head = {}
    for head in HEADS:
        m = by_head.get(head)
        if not m:
            continue
        per_head[head] = {
            "evaluated_count": m.get("evaluated_count"),
            "accuracy": _num(m.get("accuracy")),
            "macro_precision": _num(m.get("macro_precision")),
            "macro_recall": _num(m.get("macro_recall")),
            "macro_f1": _num(m.get("macro_f1")),
        }

    # Only claim the numbers describe the deployed model if the files are identical.
    eval_sha = _file_sha256(eval_checkpoint)
    deployed_sha = _file_sha256(deployed_checkpoint)
    if eval_sha and deployed_sha:
        matches = eval_sha == deployed_sha
    else:
        matches = None  # cannot be verified

    return {
        "available": True,
        "source": path,
        "split": "held-out test split",
        "test_record_count": raw.get("record_count"),
        "overall_supported_head_mean_macro_f1": _num(raw.get("overall_supported_head_mean_macro_f1")),
        "per_head": per_head,
        "evaluates_deployed_checkpoint": matches,
        "note": "Image-level multi-task classification metrics; not object-detection mAP.",
    }


def compute_feature_corrections(predictions, confirmed):
    """
    Compare the classifier's stored top-1 predictions with the user-confirmed
    attributes. Returns (corrections, rate_percent).

    corrections = {head: {"predicted": str, "confirmed": str}} for changed heads only.
    rate_percent = changed heads / compared heads * 100, or None if nothing to compare.
    """
    predictions = predictions or {}
    confirmed = confirmed or {}
    compared = 0
    corrections = {}
    for head in HEADS:
        pred = (predictions.get(head) or {}).get("label")
        conf = confirmed.get(head)
        if not pred or not conf:
            continue
        compared += 1
        if pred != conf:
            corrections[head] = {"predicted": pred, "confirmed": conf}
    if compared == 0:
        return {}, None
    return corrections, round(len(corrections) / compared * 100.0, 1)


def mean_or_none(values):
    """Mean of the real (non-None) values; None when there are none."""
    vals = [v for v in values if v is not None]
    if not vals:
        return None
    return sum(vals) / len(vals)
