"""Evaluate an M42 candidate against M40 with the same code and the same test images, then apply the gate.

1. Thresholds: the candidate is run on the VALIDATION split with the app's detector crop; per head the smallest
   score threshold whose accepted validation predictions are >= 90 % correct with >= 20 % coverage is kept
   (evaluate_m40.choose_threshold), otherwise the head is "please select". A head is never answered automatically
   if one of its classes has fewer than the gate's minimum of trusted validation examples (the validation split
   could not reveal a failure on that class). The thresholds are written as a sidecar next to a COPY of the
   candidate in the output folder. Nothing is deployed.
2. Crop and whole-photo modes for candidate and M40 (evaluate_m40, imported read-only) - reported, not gated.
3. Detector-crop mode (what the app does) for candidate and M40 on test_all, test_fp, test_df2, bench60, test_dmm
   and test_reviewed (when reviewed test labels exist).
4. Gate: check_m42_gate.decide on the candidate's detector-crop test_all result -> gate.json.

    backend\\venv\\Scripts\\python ai_training\\scripts\\v2\\eval_m42.py --candidate <best.pt> --out <dir>
    (--limit N evaluates only the first N records of every set: a smoke test of the pipeline, not a result)
"""
import argparse
import json
import os
import shutil
import sys

import numpy as np
import torch

sys.path.insert(0, ".")
sys.path.insert(0, "backend")
from ai_training.scripts import evaluate_m40 as ev  # noqa: E402
from ai_training.scripts.v2 import check_m42_gate as gate_mod  # noqa: E402
from ai_training.scripts.v2 import eval_m40_detector_crop as dc  # noqa: E402
from backend.app.ai import garment_detector as gd  # noqa: E402
from backend.app.ai.multitask_classifier import get_multitask_classifier, preprocess_image_crop  # noqa: E402

M40 = "backend/app/ai/models/garment_multitask_m40_15class.pt"
DET = "backend/app/ai/models/garment_detector_v1.pt"
MANIFESTS = "ai_training/data/manifests_m42"
GATE = "ai_training/config/m42_acceptance.json"


def detector_crop_probs(classifier, records, detector):
    """Class probabilities per head for every record, with the crop the app would use."""
    from PIL import Image, ImageOps
    model, meta = get_multitask_classifier(model_path=classifier)
    names = {h: [meta["idx_to_class"][h][str(i)] for i in range(len(meta["idx_to_class"][h]))] for h in ev.HEADS}
    probs = {h: [] for h in ev.HEADS}
    with torch.inference_mode():
        for r in records:
            path, _ = ev.image_for(r, "full")
            d = gd.detect_garment(path, model_path=detector)
            box = None
            if d.get("box_xyxy"):
                with Image.open(path) as im:
                    w, h_ = ImageOps.exif_transpose(im).size
                box = gd.pad_box(d["box_xyxy"], w, h_)
            logits = model(preprocess_image_crop(path, bbox=box))
            for h in ev.HEADS:
                probs[h].append(torch.softmax(logits[h], dim=1).numpy()[0])
    return {h: np.array(v) for h, v in probs.items()}, names


def validation_thresholds(classifier, val_records, detector, min_per_class):
    probs, names = detector_crop_probs(classifier, val_records, detector)
    out, detail = {}, {}
    for h in ev.HEADS:
        idx, y = ev.labels_of(val_records, h)
        support = {c: y.count(c) for c in ev.ACTIVE[h]}
        thin = sorted(c for c, n in support.items() if n < min_per_class)
        if not idx or thin:
            out[h] = None
            detail[h] = {"threshold": None, "validation_support": support,
                         "reason": f"classes with fewer than {min_per_class} trusted validation examples: {thin}" if thin else "no validation labels"}
            continue
        p = probs[h][idx]
        pred = [names[h][int(k)] for k in p.argmax(1)]
        correct = np.array([a == b for a, b in zip(y, pred)])
        t = ev.choose_threshold(p.max(1), correct)
        out[h] = t
        detail[h] = {"threshold": t, "validation_support": support, "validation_accuracy": round(float(correct.mean()), 4),
                     "reason": None if t is not None else "no threshold reaches 90 % accepted accuracy at 20 % coverage on validation"}
    return out, detail


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidate", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--manifests", default=MANIFESTS)
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    gate = json.load(open(GATE, encoding="utf-8"))
    min_per_class = gate["required"]["auto_answer"]["min_validation_examples_per_class"]

    ev.MAN = a.manifests
    sets = dict(ev.SETS, test_dmm="test_dmm.jsonl")
    if os.path.exists(f"{a.manifests}/test_reviewed.jsonl") and os.path.getsize(f"{a.manifests}/test_reviewed.jsonl") > 0:
        sets["test_reviewed"] = "test_reviewed.jsonl"
    ev.SETS = sets

    # 1. thresholds from validation, detector crop
    staged = os.path.join(a.out, "m42_candidate.pt")
    shutil.copyfile(a.candidate, staged)
    val = ev.load(f"{a.manifests}/val.jsonl")
    if a.limit:
        val = val[:a.limit]
    thresholds, detail = validation_thresholds(staged, val, DET, min_per_class)
    sidecar = dict(thresholds, _note="chosen on the M42 validation split with the app's detector crop; candidate only, not deployed",
                   _detail=detail)
    json.dump(sidecar, open(os.path.splitext(staged)[0] + ".thresholds.json", "w"), indent=2)
    print("validation thresholds:", thresholds, flush=True)

    # 2. crop and whole-photo modes (reported, not gated)
    if not a.limit:
        sys.argv = ["evaluate_m40", "--candidate", staged, "--baseline", M40, "--out", os.path.join(a.out, "crop_and_full")]
        ev.main()

    # 3. detector crop, candidate and M40
    for tag, clf in (("m42", staged), ("m40", M40)):
        sys.argv = ["eval_m40_detector_crop", "--detector", DET, "--classifier", clf, "--out", os.path.join(a.out, f"detector_crop_{tag}")]
        if a.limit:
            sys.argv += ["--limit", str(a.limit)]
        dc.main()

    # 4. gate
    result = json.load(open(os.path.join(a.out, "detector_crop_m42", "m40_detector_crop_eval.json"), encoding="utf-8"))
    frozen = all(ev.sha8(f"{a.manifests}/{f}") == ev.sha8(f"ai_training/data/manifests_m40/{f}")
                 for f in ("test.jsonl", "test_df2.jsonl", "test_fp.jsonl", "bench60.jsonl"))
    dropped = json.load(open(f"{a.manifests}/counts.json", encoding="utf-8"))["report"].get("dropped") if os.path.exists(f"{a.manifests}/counts.json") else None
    integrity = bool(frozen and dropped is not None and not a.limit)
    decision = gate_mod.decide(gate, result["sets"]["test_all"]["heads"], (result["sets"].get("test_reviewed") or {}).get("heads"), integrity)
    decision.update(candidate={"checkpoint": a.candidate, "sha256": result["classifier_sha256"], "thresholds": thresholds},
                    integrity={"test_files_identical_to_m40": frozen, "near_duplicates_removed_by_manifest_builder": dropped,
                               "smoke_test_limit": a.limit or None})
    json.dump(decision, open(os.path.join(a.out, "gate.json"), "w"), indent=2)
    print("\nGATE:", decision["decision"], "-", decision["action"])
    for i in decision["items"]:
        print(("  ok   " if i["passed"] else "  FAIL ") + f"{i['item']}: {i['measured']} (target {i['target']})")
    if a.limit:
        print(f"\nSMOKE TEST ONLY (first {a.limit} records per set): these numbers are not a result.")


if __name__ == "__main__":
    main()
