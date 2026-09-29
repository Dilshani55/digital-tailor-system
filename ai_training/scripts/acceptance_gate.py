#!/usr/bin/env python3
"""
acceptance_gate.py - decides whether a candidate checkpoint may replace the deployed model.

Both checkpoints are loaded and run through the PRODUCTION inference code
(backend/app/ai/multitask_classifier.py) and scored on

    A. the locked 60-image real-product benchmark (never trained on), and
    B. the CLEAN test split: test records whose image has no near-duplicate (dHash <= 4) in the
       training images (list produced by scripts/audit_dataset.py).

Gate (all must hold for PASS):
    1. candidate loads in the production code; head dimensions equal classes.json
    2. inference smoke test on real images returns valid 4-head probability distributions
    3. mean macro-F1 over the four heads is HIGHER than the deployed model on the locked benchmark
    4. ... and not lower on the clean test split
    5. garment_type (critical: it selects the woven/knit block) macro-F1 drops by no more than 0.03,
       every other head by no more than 0.05, on the locked benchmark
    6. no train/eval leakage: no locked-benchmark record is in the training manifest and the
       smallest dHash distance to a training image is > 4
    7. evidence + SHA-256 checksums are written

Result: PASS / FAIL / AMBIGUOUS (locked benchmark improves but the clean test split disagrees, or
the improvement is below 0.01). AMBIGUOUS needs a human decision; nothing is deployed automatically.

Usage (repository root):
  PYTHONPATH=. python ai_training/scripts/acceptance_gate.py --candidate <best.pt> --output <gate.json>
"""

import argparse
import hashlib
import json
import os
import sys

import numpy as np
import torch
import torch.nn.functional as F

sys.path.insert(0, os.path.abspath("."))
sys.path.insert(0, os.path.abspath("backend"))

from backend.app.ai.multitask_classifier import get_multitask_classifier, preprocess_image_crop  # noqa: E402
from ai_training.training.metrics import MultiTaskMetricsTracker  # noqa: E402

HEADS = ["garment_type", "neckline_type", "sleeve_length", "sleeve_style"]
DEPLOYED = "backend/app/ai/models/garment_multitask_yolov8_best.pt"
MIN_IMPROVEMENT = 0.01
MAX_REGRESSION = {"garment_type": 0.03, "neckline_type": 0.05, "sleeve_length": 0.05, "sleeve_style": 0.05}


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_jsonl(path):
    with open(path, "r", encoding="utf-8") as f:
        return [json.loads(x) for x in f if x.strip()]


def _path(p):
    return p.replace("\\", "/") if p else p


def score(model_path, records, image_key, bbox_xywh=True):
    model, meta = get_multitask_classifier(model_path=model_path)
    c2i, i2c = meta["class_to_idx"], meta["idx_to_class"]
    tracker = MultiTaskMetricsTracker(c2i, i2c)
    with torch.no_grad():
        for rec in records:
            bbox = rec.get("bbox")
            crop = [bbox[0], bbox[1], bbox[0] + bbox[2], bbox[1] + bbox[3]] if (bbox and len(bbox) == 4 and bbox_xywh) else None
            x = preprocess_image_crop(_path(rec[image_key]), bbox=crop)
            logits = model(x)
            targets, masks = {}, {}
            for h in HEADS:
                lbl = rec["labels"].get(h)
                if rec["masks"].get(h) == 1 and lbl in c2i[h]:
                    targets[h] = torch.tensor([c2i[h][lbl]])
                    masks[h] = torch.tensor([1.0])
                else:
                    targets[h] = torch.tensor([0])
                    masks[h] = torch.tensor([0.0])
            tracker.update(logits, targets, masks)
    res = tracker.compute()
    return {h: {"accuracy": res[h]["accuracy"], "macro_f1": res[h]["macro_f1"], "evaluated": res[h]["evaluated_count"]}
            for h in HEADS}, res


def mean_f1(scores):
    vals = [scores[h]["macro_f1"] for h in HEADS if scores[h]["evaluated"]]
    return sum(vals) / len(vals)


def smoke(model_path, images):
    model, meta = get_multitask_classifier(model_path=model_path)
    dims = {h: len(meta["class_to_idx"][h]) for h in HEADS}
    ok = True
    with torch.no_grad():
        for p in images:
            logits = model(preprocess_image_crop(p))
            for h in HEADS:
                pr = F.softmax(logits[h][0], dim=0)
                ok = ok and pr.numel() == dims[h] and abs(float(pr.sum()) - 1.0) < 1e-4 and bool(torch.isfinite(pr).all())
    return ok, dims


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidate", required=True)
    ap.add_argument("--baseline", default=DEPLOYED)
    ap.add_argument("--eval-manifest", default="ai_training/data/eval_real_product_set/eval_manifest.jsonl")
    ap.add_argument("--test-manifest", default="ai_training/data/final_multitask/test.jsonl")
    ap.add_argument("--train-manifest", default="ai_training/data/final_multitask/train.jsonl")
    ap.add_argument("--audit", default="ai_training/data/audits/dataset_audit.json")
    ap.add_argument("--classes", default="ai_training/config/classes.json")
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    classes = json.load(open(args.classes))
    want_dims = {h: len(classes["outputs"][h]["classes"]) for h in HEADS}
    evalrecs = read_jsonl(args.eval_manifest)
    test = read_jsonl(args.test_manifest)
    audit = json.load(open(args.audit))
    near_paths = {_path(p) for p in audit["leakage"].get("test_images_with_near_duplicate_in_train_paths", [])}
    clean_test = [r for r in test if _path(r["source_image_path"]) not in near_paths]

    gate = {"candidate": args.candidate, "baseline": args.baseline,
            "candidate_sha256": sha256(args.candidate), "baseline_sha256": sha256(args.baseline),
            "eval_manifest_sha256": sha256(args.eval_manifest), "checks": {}}

    # 1 + 2  load in production code, dimensions, smoke
    try:
        smoke_ok, dims = smoke(args.candidate, [_path(r["image_path"]) for r in evalrecs[:6]])
        gate["checks"]["loads_in_production_code"] = True
        gate["checks"]["head_dimensions_match_taxonomy"] = dims == want_dims
        gate["checks"]["inference_smoke_test"] = bool(smoke_ok)
    except Exception as exc:                                    # noqa: BLE001
        gate["checks"]["loads_in_production_code"] = f"FAILED: {exc}"
        gate["result"] = "FAIL"
        json.dump(gate, open(args.output, "w"), indent=2)
        print(json.dumps(gate, indent=2))
        return 1

    # scores
    cand_lock, cand_lock_full = score(args.candidate, evalrecs, "image_path")
    base_lock, base_lock_full = score(args.baseline, evalrecs, "image_path")
    cand_test, _ = score(args.candidate, clean_test, "source_image_path")
    base_test, _ = score(args.baseline, clean_test, "source_image_path")
    gate["locked_benchmark"] = {"records": len(evalrecs), "candidate": cand_lock, "baseline": base_lock,
                                "candidate_mean_macro_f1": mean_f1(cand_lock), "baseline_mean_macro_f1": mean_f1(base_lock)}
    gate["clean_test_split"] = {"records": len(clean_test), "excluded_near_duplicates": len(test) - len(clean_test),
                                "candidate": cand_test, "baseline": base_test,
                                "candidate_mean_macro_f1": mean_f1(cand_test), "baseline_mean_macro_f1": mean_f1(base_test)}

    d_lock = mean_f1(cand_lock) - mean_f1(base_lock)
    d_test = mean_f1(cand_test) - mean_f1(base_test)
    reg = {h: cand_lock[h]["macro_f1"] - base_lock[h]["macro_f1"] for h in HEADS}
    gate["checks"]["locked_mean_macro_f1_delta"] = round(d_lock, 4)
    gate["checks"]["clean_test_mean_macro_f1_delta"] = round(d_test, 4)
    gate["checks"]["per_head_locked_delta"] = {h: round(v, 4) for h, v in reg.items()}
    gate["checks"]["no_critical_regression"] = all(reg[h] >= -MAX_REGRESSION[h] for h in HEADS)

    train_uids = {r["record_uid"] for r in read_jsonl(args.train_manifest)}
    gate["checks"]["no_eval_record_in_training_manifest"] = not any(e["original_record_uid"] in train_uids for e in evalrecs)
    gate["checks"]["eval_min_dhash_distance_to_train"] = audit["leakage"].get("eval_set_min_dhash_distance_to_train")
    gate["checks"]["no_eval_near_duplicate_of_training"] = audit["leakage"].get("eval_set_near_duplicate_pairs_vs_train") == 0

    hard = [gate["checks"]["head_dimensions_match_taxonomy"], gate["checks"]["inference_smoke_test"],
            gate["checks"]["no_critical_regression"], gate["checks"]["no_eval_record_in_training_manifest"],
            gate["checks"]["no_eval_near_duplicate_of_training"]]
    if not all(hard) or d_lock <= 0:
        gate["result"] = "FAIL"
    elif d_test < 0 or d_lock < MIN_IMPROVEMENT:
        gate["result"] = "AMBIGUOUS"
    else:
        gate["result"] = "PASS"
    gate["note"] = ("The locked benchmark has only 60 images (23-54 labelled per head); differences of a few points are "
                    "within sampling noise, which is why the clean test split must agree.")
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    json.dump(gate, open(args.output, "w"), indent=2)
    print(json.dumps({k: gate[k] for k in ("checks", "result")}, indent=2))
    print("locked  mean macro-F1  baseline %.4f  candidate %.4f" % (mean_f1(base_lock), mean_f1(cand_lock)))
    print("clean   mean macro-F1  baseline %.4f  candidate %.4f  (n=%d)" % (mean_f1(base_test), mean_f1(cand_test), len(clean_test)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
