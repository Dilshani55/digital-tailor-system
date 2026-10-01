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

# Genuine evaluation results written by backend/training/evaluate_models.py. The file is local (git-ignored),
# so it may be absent on another machine.
EVALUATION_FILE = os.environ.get(
    "MODEL_EVALUATION_FILE", os.path.join(_BACKEND_DIR, "training", "runs", "evaluation.json"))
MODEL_DIR = os.environ.get("GARMENT_MODEL_DIR") or os.path.join(_BACKEND_DIR, "model")


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


def load_model_evaluation(evaluation_file=None, model_dir=None):
    """
    Test-set results of the four garment models (the app's detector crop), read from the evaluation file.
    Returns {"available": False, "reason": ...} if the file is missing or unreadable - never a substitute.
    """
    path = evaluation_file or EVALUATION_FILE
    model_dir = model_dir or MODEL_DIR
    if not os.path.exists(path):
        return {"available": False, "reason": "Evaluation file not found (training results are not part of the repository).",
                "source": os.path.basename(path)}
    try:
        with open(path, "r", encoding="utf-8") as f:
            results = json.load(f)["results"]
    except (OSError, ValueError, KeyError) as exc:
        return {"available": False, "reason": f"Evaluation file unreadable: {exc}", "source": os.path.basename(path)}

    per_head, matches = {}, []
    for r in results:
        test = ((r.get("sets") or {}).get("test") or {}).get("detector_crop") or {}
        auto = test.get("auto_answer") or {}
        # only claim the numbers describe the model in use if the files are identical
        sha = _file_sha256(os.path.join(model_dir, r.get("model_file") or ""))
        same = (sha == r.get("model_sha256")) if sha and r.get("model_sha256") else None
        matches.append(same)
        per_head[r.get("head")] = {
            "architecture": r.get("architecture"),
            "evaluated_count": test.get("n"),
            "accuracy": _num(test.get("accuracy")),
            "macro_f1": _num(test.get("macro_f1")),
            "majority_class_accuracy": _num(test.get("majority_class_accuracy")),
            "answered_automatically": {"threshold": _num(auto.get("threshold")), "coverage": _num(auto.get("coverage")),
                                       "accuracy_when_answered": _num(auto.get("accuracy_when_answered"))},
            "evaluates_model_in_use": same,
        }
    return {
        "available": True,
        "source": os.path.basename(path),
        "split": "held-out test photos, garment-detector crop (what the app does)",
        "per_head": per_head,
        "evaluates_deployed_checkpoint": None if any(m is None for m in matches) or not matches else all(matches),
        "note": "Image classification results per model; not object-detection mAP.",
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


def summarize_fabric_comparisons(rows):
    """
    Descriptive summary of traditional-vs-system fabric estimates.

    rows: iterable of dicts with the stored values
        {"traditional_m", "system_m", "source", "pattern_id"}.
    difference = traditional - system (positive: the system recommends buying LESS cloth).

    Returns None when there is no entry. Only descriptive statistics are given: with the small
    samples a prototype study collects, no significance or "fabric saving" claim follows from it.
    """
    rows = [r for r in rows if r.get("traditional_m") and r.get("system_m") is not None]
    if not rows:
        return None
    diffs = sorted(r["traditional_m"] - r["system_m"] for r in rows)
    rel = [100.0 * (r["traditional_m"] - r["system_m"]) / r["traditional_m"] for r in rows]
    n = len(diffs)
    mean = sum(diffs) / n
    median = diffs[n // 2] if n % 2 else (diffs[n // 2 - 1] + diffs[n // 2]) / 2
    sd = (sum((d - mean) ** 2 for d in diffs) / (n - 1)) ** 0.5 if n > 1 else None
    by_source = {}
    for r in rows:
        by_source[r["source"]] = by_source.get(r["source"], 0) + 1
    return {
        "n": n,
        "patterns": len({r["pattern_id"] for r in rows}),
        "mean_difference_m": round(mean, 3),
        "median_difference_m": round(median, 3),
        "sd_difference_m": None if sd is None else round(sd, 3),
        "mean_relative_difference_percent": round(sum(rel) / n, 1),
        "system_lower_count": sum(1 for d in diffs if d > 0),
        "system_higher_count": sum(1 for d in diffs if d < 0),
        "equal_count": sum(1 for d in diffs if d == 0),
        "by_source": by_source,
        "definition": "difference = traditional estimate - system recommended purchase, same fabric width",
        "note": "Descriptive only. Whether the system amount is actually sufficient has not been verified by cutting.",
    }
