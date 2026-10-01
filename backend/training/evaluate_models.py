"""Test the trained models exactly as the app uses them, choose the confidence thresholds, and write the report.

    backend\\venv\\Scripts\\python backend\\training\\evaluate_models.py            # all four
    backend\\venv\\Scripts\\python backend\\training\\evaluate_models.py neckline   # one task

For every task the photos in datasets/attributes/<task>/eval.jsonl (never trained on) are run through the production
inference code (app/ai/garment_models.py) in three ways, reported separately:

    detector crop   whole photo -> garment detector -> box + 10 % -> model      (what the app does)
    dataset crop    the dataset's own garment box -> model                       (best case)
    whole photo     the photo as uploaded, no crop -> model                      (when the detector finds nothing)

Thresholds: chosen on the VALIDATION photos with the detector crop - the smallest score at which the accepted
validation answers are >= 90 % correct with >= 20 % coverage; none if that cannot be reached, or if a class has
fewer than 15 validation photos (validation could not reveal a failure on it). They are written to
backend/model/thresholds.json and then applied, unchanged, to the test photos.

Output: backend/training/runs/evaluation.json and evaluation.md (also printed).
"""
import json
import os
import sys

import numpy as np

sys.path.insert(0, "backend")
sys.path.insert(0, "backend/training")
import common as C  # noqa: E402
from app.ai import garment_detector as gd  # noqa: E402
from app.ai import garment_models as gm  # noqa: E402
from app.ai.preprocess import crop_box, load_rgb, square_pad  # noqa: E402

TASK_HEAD = {"garment": "garment_type", "neckline": "neckline_type", "sleeve_length": "sleeve_length", "sleeve_design": "sleeve_style"}
TARGET, MIN_COVERAGE, MIN_VAL_PER_CLASS = 0.90, 0.20, 15
MODES = ("detector_crop", "dataset_crop", "whole_photo")
DETECTOR_CACHE = f"{C.ROOT}/runs/detector_boxes.json"
OUT = f"{C.ROOT}/runs"


def metrics(y_true, y_pred, classes):
    n = len(y_true)
    per, f1s = {}, []
    for c in classes:
        tp = sum(1 for a, b in zip(y_true, y_pred) if a == c and b == c)
        support = sum(1 for a in y_true if a == c)
        predicted = sum(1 for b in y_pred if b == c)
        p = tp / predicted if predicted else 0.0
        r = tp / support if support else None
        f = (2 * p * r / (p + r)) if (r is not None and p + r > 0) else (0.0 if support else None)
        per[c] = {"support": support, "precision": round(p, 4), "recall": None if r is None else round(r, 4),
                  "f1": None if f is None else round(f, 4)}
        if support:
            f1s.append(f)
    matrix = [[sum(1 for a, b in zip(y_true, y_pred) if a == t and b == p) for p in classes] for t in classes]
    majority = max((sum(1 for a in y_true if a == c) for c in classes), default=0)
    return {"n": n, "accuracy": round(sum(a == b for a, b in zip(y_true, y_pred)) / n, 4) if n else None,
            "macro_f1": round(float(np.mean(f1s)), 4) if f1s else None,
            "majority_class_accuracy": round(majority / n, 4) if n else None,
            "per_class": per, "confusion_matrix": {"rows_true_cols_predicted": classes, "matrix": matrix},
            "classes_without_examples": [c for c in classes if per[c]["support"] == 0]}


def choose_threshold(conf, correct):
    """Smallest threshold whose accepted predictions are >= TARGET correct with coverage >= MIN_COVERAGE, else None."""
    order = np.argsort(-conf)
    c = correct[order]
    running = np.cumsum(c) / (np.arange(len(c)) + 1)
    best = None
    for k in range(len(c)):
        if (k + 1) / len(c) >= MIN_COVERAGE and running[k] >= TARGET:
            best = float(conf[order][k])
    return best


def answered(conf, correct, threshold):
    if threshold is None:
        return {"threshold": None, "coverage": 0.0, "accuracy_when_answered": None}
    keep = conf >= threshold
    return {"threshold": round(threshold, 4), "coverage": round(float(keep.mean()), 4),
            "accuracy_when_answered": round(float(correct[keep].mean()), 4) if keep.any() else None}


def detector_box(photo, cache):
    if photo not in cache:
        d = gd.detect_garment(photo)
        box = None
        if d.get("box_xyxy"):
            image = load_rgb(photo)
            box = [round(v, 1) for v in gd.pad_box(d["box_xyxy"], image.width, image.height)]
        cache[photo] = {"box": box, "class": d.get("class")}
    return cache[photo]["box"]


def picture(row, mode, cache):
    if mode == "detector_crop":
        return gm.prepare(row["photo"], detector_box(row["photo"], cache))
    if mode == "whole_photo":
        return gm.prepare(row["photo"], None)
    return square_pad(crop_box(load_rgb(row["crop_source"]), row["crop_box_xyxy"]))


def evaluate(task, cache):
    head, classes = TASK_HEAD[task], C.TASKS[task]
    rows = [r for r in C.load_jsonl(f"{C.OUT}/{task}/eval.jsonl") if r["photo"] and os.path.exists(r["photo"])]
    probs = {m: [] for m in MODES}
    for i, row in enumerate(rows, 1):
        for mode in MODES:
            pairs = dict(gm._probabilities(head, picture(row, mode, cache)))
            probs[mode].append([pairs[c] for c in classes])
        if i % 500 == 0:
            print(f"  {task}: {i}/{len(rows)}", flush=True)
            json.dump(cache, open(DETECTOR_CACHE, "w"))
    probs = {m: np.array(v) for m, v in probs.items()}
    labels = np.array([classes.index(r["label"]) for r in rows])

    def subset(set_name, tier=None):
        return np.array([i for i, r in enumerate(rows) if r["set"] == set_name and (tier is None or r["tier"] == tier)], dtype=int)

    # threshold from validation, detector crop
    val = subset("val")
    support = {c: int((labels[val] == k).sum()) for k, c in enumerate(classes)}
    thin = [c for c, n in support.items() if n < MIN_VAL_PER_CLASS]
    p = probs["detector_crop"][val]
    threshold = None if thin or not len(val) else choose_threshold(p.max(1), p.argmax(1) == labels[val])
    reason = (f"classes with fewer than {MIN_VAL_PER_CLASS} validation photos: {thin}" if thin else
              None if threshold is not None else "no threshold reaches 90 % accepted accuracy at 20 % coverage on validation")

    result = {"task": task, "head": head, "classes": classes, "model_file": C.WEIGHTS[task],
              "model_sha256": gm._get(head)["sha256"], "architecture": gm.ARCHITECTURE[head],
              "threshold": {"value": threshold, "validation_support": support, "why_none": reason}, "sets": {}}
    groups = [("val", "val", None), ("test", "test", "trusted"), ("test_dmm", "test_dmm", None), ("bench60", "bench60", "trusted")]
    if task == "garment":
        groups.insert(2, ("test_proxy_labels", "test", "proxy"))
    for name, set_name, tier in groups:
        idx = subset(set_name, tier)
        if not len(idx):
            continue
        entry = {"n": int(len(idx)), "label_tier": tier or ("mixed" if task == "garment" else "trusted")}
        y = [classes[k] for k in labels[idx]]
        for mode in MODES:
            pm = probs[mode][idx]
            m = metrics(y, [classes[k] for k in pm.argmax(1)], classes)
            m["auto_answer"] = answered(pm.max(1), pm.argmax(1) == labels[idx], threshold)
            entry[mode] = m
        result["sets"][name] = entry
    return result


def markdown(results):
    out = ["# Garment models - evaluation", "",
           "Accuracy / macro-F1 on photos never used for training. \"Detector crop\" is what the app does.", "",
           "| Model | Set | n | Majority class | Detector crop | Dataset crop | Whole photo | Answered automatically (detector crop) |",
           "|---|---|---:|---:|---|---|---|---|"]
    for r in results:
        for name, e in r["sets"].items():
            a = e["detector_crop"]["auto_answer"]
            auto = "never (please select)" if a["threshold"] is None else \
                f"{a['accuracy_when_answered']:.1%} correct on {a['coverage']:.1%} of photos (score >= {a['threshold']})"
            cells = " | ".join(f"{e[m]['accuracy']:.3f} / {e[m]['macro_f1']:.3f}" for m in MODES)
            out.append(f"| {r['task']} | {name} | {e['n']} | {e['detector_crop']['majority_class_accuracy']:.3f} | {cells} | {auto} |")
    out += ["", "## Per class (test set, detector crop)", "", "| Model | Class | Test photos | Precision | Recall | F1 |", "|---|---|---:|---:|---:|---:|"]
    for r in results:
        test = r["sets"].get("test")
        if not test:
            continue
        for c, v in test["detector_crop"]["per_class"].items():
            out.append(f"| {r['task']} | {c} | {v['support']} | {v['precision']} | {v['recall']} | {v['f1']} |")
    out += ["", "## Thresholds (from validation)", ""]
    for r in results:
        t = r["threshold"]
        out.append(f"* {r['task']}: {t['value'] if t['value'] is not None else 'none'}" + (f" - {t['why_none']}" if t["why_none"] else "")
                   + f" (validation photos per class: {t['validation_support']})")
    return "\n".join(out) + "\n"


def main():
    tasks = sys.argv[1:] or list(C.TASKS)
    os.makedirs(OUT, exist_ok=True)
    cache = json.load(open(DETECTOR_CACHE)) if os.path.exists(DETECTOR_CACHE) else {}
    path = f"{OUT}/evaluation.json"
    done = {r["task"]: r for r in json.load(open(path))["results"]} if os.path.exists(path) else {}
    for task in tasks:
        print(f"evaluating {task} ...", flush=True)
        done[task] = evaluate(task, cache)
        json.dump(cache, open(DETECTOR_CACHE, "w"))
    results = [done[t] for t in C.TASKS if t in done]
    json.dump({"detector": {"file": "garment_detector.pt", "min_score": gd.MIN_SCORE, "crop_margin": gd.CROP_MARGIN},
               "threshold_rule": {"target_accuracy": TARGET, "min_coverage": MIN_COVERAGE, "min_validation_photos_per_class": MIN_VAL_PER_CLASS},
               "results": results}, open(path, "w", encoding="utf-8"), indent=1)
    thresholds = {TASK_HEAD[r["task"]]: r["threshold"]["value"] for r in results}
    thresholds["_note"] = ("Score at or above which a suggestion is filled in automatically; null = always 'please select'. "
                           "Chosen on validation photos with the garment detector's crop (backend/training/evaluate_models.py).")
    json.dump(thresholds, open(f"{C.MODEL_DIR}/thresholds.json", "w", encoding="utf-8"), indent=2)
    md = markdown(results)
    open(f"{OUT}/evaluation.md", "w", encoding="utf-8").write(md)
    print(md)


if __name__ == "__main__":
    main()
