#!/usr/bin/env python3
"""
evaluate_m40.py - independent evaluation of a 3/5/3/4 candidate and the deployed M13 on the SAME held-out images.

* Every model runs through the production preprocessing (EXIF-corrected, 224x224) and loader.
* Evaluation sets: test (DeepFashion2 test + Fashionpedia test), each alone, and the locked 60-image benchmark;
  each is scored on garment CROPS and on WHOLE photos (what a user uploads).
* Only trusted labels are scored. A head with no label on a record is skipped for that record.
* M13 predicts more classes than the 15 selectable ones. A prediction outside the 15 is NEVER remapped: it counts
  as wrong (the pipeline would ask the user to choose), and the count of such predictions is reported.
* Majority-class baseline = always answer the most frequent class of the TRAINING split.
* Uncertainty thresholds are chosen on the VALIDATION split only (whole-photo mode): per head the smallest score
  threshold at which the accepted validation predictions are >= 90 % correct (coverage >= 20 %); otherwise null
  (the head is always reported as uncertain). They are then applied, unchanged, to the test sets.

  PYTHONPATH=. python ai_training/scripts/evaluate_m40.py --candidate <best.pt> --out <dir>
"""

import argparse
import hashlib
import json
import os
import sys

import numpy as np
import torch

sys.path.insert(0, os.path.abspath("."))
sys.path.insert(0, os.path.abspath("backend"))
from backend.app.ai.multitask_classifier import get_multitask_classifier, preprocess_image_crop   # noqa: E402

HEADS = ["garment_type", "neckline_type", "sleeve_length", "sleeve_style"]
ACTIVE = {
    "garment_type": ["blouse", "t-shirt", "crop-top"],
    "neckline_type": ["round-neck", "v-neck", "square-neck", "collared-neck", "off-shoulder"],
    "sleeve_length": ["sleeveless", "short-sleeve", "long-sleeve"],
    "sleeve_style": ["none", "regular-sleeve", "puff-sleeve", "bell-sleeve"],
}
M13 = "backend/app/ai/models/garment_multitask_yolov8_best.pt"
MAN = "ai_training/data/manifests_m40"
SETS = {"test_all": "test.jsonl", "test_df2": "test_df2.jsonl", "test_fp": "test_fp.jsonl", "bench60": "bench60.jsonl"}
TARGET, MIN_COVERAGE = 0.90, 0.20


def load(path):
    return [json.loads(x) for x in open(path, encoding="utf-8") if x.strip()]


def image_for(rec, mode):
    p = lambda x: x.replace("\\", "/") if x else None
    if mode == "full":
        for k in ("full_image_path", "source_image_path"):
            if rec.get(k) and os.path.exists(p(rec[k])):
                return p(rec[k]), None
    if rec.get("crop_path") and os.path.exists(p(rec["crop_path"])):
        return p(rec["crop_path"]), None
    b = rec.get("bbox")
    box = [b[0], b[1], b[0] + b[2], b[1] + b[3]] if b and len(b) == 4 else None
    return p(rec["source_image_path"]), box


def sha8(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def predict(model_path, records, mode, cache_file):
    """{head: array[n, classes]} probabilities plus the model's class names per head. Cached on disk."""
    model, meta = get_multitask_classifier(model_path=model_path)
    names = {h: [meta["idx_to_class"][h][str(i)] for i in range(len(meta["idx_to_class"][h]))] for h in HEADS}
    if os.path.exists(cache_file):
        z = np.load(cache_file)
        return {h: z[h] for h in HEADS}, names
    out = {h: [] for h in HEADS}
    with torch.inference_mode():
        for i in range(0, len(records), 32):
            xs = []
            for r in records[i:i + 32]:
                path, box = image_for(r, mode)
                xs.append(preprocess_image_crop(path, bbox=box))
            logits = model(torch.cat(xs, 0))
            for h in HEADS:
                out[h].append(torch.softmax(logits[h], dim=1).numpy())
    arr = {h: np.concatenate(out[h], 0) for h in HEADS}
    os.makedirs(os.path.dirname(cache_file), exist_ok=True)
    np.savez_compressed(cache_file, **arr)
    return arr, names


def metrics(y_true, y_pred, classes):
    """y_* are class-name strings; y_pred may hold names outside `classes` (counted wrong)."""
    n = len(y_true)
    acc = float(np.mean([a == b for a, b in zip(y_true, y_pred)])) if n else None
    per, ps, rs, fs = {}, [], [], []
    for c in classes:
        tp = sum(1 for a, b in zip(y_true, y_pred) if a == c and b == c)
        sup = sum(1 for a in y_true if a == c)
        pred = sum(1 for b in y_pred if b == c)
        p = tp / pred if pred else 0.0
        r = tp / sup if sup else None
        f = (2 * p * r / (p + r)) if (r is not None and (p + r) > 0) else (0.0 if sup else None)
        per[c] = {"support": sup, "precision": round(p, 4), "recall": None if r is None else round(r, 4),
                  "f1": None if f is None else round(f, 4)}
        if sup:
            ps.append(p), rs.append(r), fs.append(f)
    labels = list(classes) + ["<outside 15 classes>"]
    cm = [[0] * len(labels) for _ in classes]
    for a, b in zip(y_true, y_pred):
        if a in classes:
            cm[classes.index(a)][classes.index(b) if b in classes else len(classes)] += 1
    return {"n": n, "accuracy": None if acc is None else round(acc, 4),
            "macro_precision": round(float(np.mean(ps)), 4) if ps else None,
            "macro_recall": round(float(np.mean(rs)), 4) if rs else None,
            "macro_f1": round(float(np.mean(fs)), 4) if fs else None,
            "per_class": per, "confusion_matrix": {"rows_true": list(classes), "cols_pred": labels, "matrix": cm},
            "classes_without_test_data": [c for c in classes if per[c]["support"] == 0]}


def labels_of(records, head):
    idx = [i for i, r in enumerate(records) if r["masks"].get(head) == 1 and r["labels"].get(head) in ACTIVE[head]]
    return idx, [records[i]["labels"][head] for i in idx]


def choose_threshold(conf, correct):
    """Smallest threshold whose accepted predictions are >= TARGET correct with coverage >= MIN_COVERAGE, else None."""
    order = np.argsort(-conf)
    best = None
    c = correct[order]
    cum = np.cumsum(c) / (np.arange(len(c)) + 1)
    for k in range(len(c)):
        if (k + 1) / len(c) >= MIN_COVERAGE and cum[k] >= TARGET:
            best = float(conf[order][k])
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidate", required=True)
    ap.add_argument("--baseline", default=M13)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    cache = os.path.join(args.out, "cache")

    records = {k: load(os.path.join(MAN, v)) for k, v in SETS.items()}
    val = load(os.path.join(MAN, "val.jsonl"))
    train = load(os.path.join(MAN, "train.jsonl"))
    result = {"candidate": args.candidate, "candidate_sha256": sha8(args.candidate), "baseline": args.baseline,
              "baseline_sha256": sha8(args.baseline), "sets": {k: len(v) for k, v in records.items()}, "eval": {}}

    majority = {}
    for h in HEADS:
        _, tr = labels_of(train, h)
        majority[h] = max(ACTIVE[h], key=tr.count) if tr else None
    result["majority_class_from_train"] = majority

    def run(model_path, tag):
        res = {}
        for setname, recs in list(records.items()) + [("val", val)]:
            for mode in ("crop", "full"):
                if setname == "val" and mode == "crop":
                    continue
                cf = os.path.join(cache, f"{tag}_{setname}_{mode}.npz")
                probs, names = predict(model_path, recs, mode, cf)
                res[(setname, mode)] = (probs, names)
        return res

    cand = run(args.candidate, "cand_" + result["candidate_sha256"][:10])
    base = run(args.baseline, "base_" + result["baseline_sha256"][:10])

    def score(pred_bundle, setname, mode, recs):
        probs, names = pred_bundle[(setname, mode)]
        out = {}
        for h in HEADS:
            idx, y = labels_of(recs, h)
            if not idx:
                out[h] = {"n": 0}
                continue
            top = probs[h][idx].argmax(1)
            y_pred = [names[h][t] for t in top]
            m = metrics(y, y_pred, ACTIVE[h])
            m["predictions_outside_the_15_classes"] = int(sum(1 for b in y_pred if b not in ACTIVE[h]))
            m["majority_baseline_accuracy"] = round(float(np.mean([a == majority[h] for a in y])), 4)
            out[h] = m
        return out

    for setname, recs in records.items():
        result["eval"][setname] = {}
        for mode in ("crop", "full"):
            result["eval"][setname][mode] = {"candidate": score(cand, setname, mode, recs), "m13": score(base, setname, mode, recs)}

    # thresholds: validation, whole-photo mode, candidate only
    probs, names = cand[("val", "full")]
    thr, val_report = {}, {}
    for h in HEADS:
        idx, y = labels_of(val, h)
        if not idx:
            thr[h] = None
            continue
        p = probs[h][idx]
        conf = p.max(1)
        correct = np.array([names[h][t] == a for t, a in zip(p.argmax(1), y)], dtype=float)
        thr[h] = choose_threshold(conf, correct)
        val_report[h] = {"n": len(idx), "val_accuracy_all": round(float(correct.mean()), 4), "threshold": thr[h]}
    result["thresholds_chosen_on_validation"] = thr
    result["validation_summary"] = val_report

    # selective prediction on the test sets with the frozen thresholds
    result["selective_test"] = {}
    for setname in ("test_all", "test_df2", "test_fp", "bench60"):
        for mode in ("crop", "full"):
            probs, names = cand[(setname, mode)]
            recs = records[setname]
            sel = {}
            for h in HEADS:
                idx, y = labels_of(recs, h)
                if not idx:
                    continue
                p = probs[h][idx]
                conf = p.max(1)
                ok = np.array([names[h][t] == a for t, a in zip(p.argmax(1), y)])
                accepted = conf >= thr[h] if thr[h] is not None else np.zeros(len(conf), bool)
                sel[h] = {"n": len(idx), "coverage": round(float(accepted.mean()), 4),
                          "accuracy_when_answering": round(float(ok[accepted].mean()), 4) if accepted.any() else None}
            result["selective_test"][f"{setname}/{mode}"] = sel

    json.dump(thr, open(os.path.join(args.out, "thresholds.json"), "w"), indent=2)
    json.dump(result, open(os.path.join(args.out, "evaluation.json"), "w"), indent=2)

    print(f"{'set/mode':22}{'head':15}{'n':>6}{'cand acc':>10}{'cand F1':>9}{'M13 acc':>9}{'M13 F1':>8}{'majority':>10}")
    for s, modes in result["eval"].items():
        for m, both in modes.items():
            for h in HEADS:
                c, b = both["candidate"][h], both["m13"][h]
                if c.get("n"):
                    print(f"{s + '/' + m:22}{h:15}{c['n']:>6}{c['accuracy']:>10}{str(c['macro_f1']):>9}{b['accuracy']:>9}{str(b['macro_f1']):>8}{c['majority_baseline_accuracy']:>10}")
    print("thresholds (validation):", thr)


if __name__ == "__main__":
    main()
