"""Evaluate the deployed M40 classifier on the M40 test sets with the crop the APP would use:
whole photo -> garment detector -> tight box + 10 % margin (gd.pad_box) -> classifier; full image when no box.

Nothing here tunes anything: M40's thresholds (chosen on validation by evaluate_m40.py) are read from the frozen
sidecar file, the detector's MIN_SCORE is fixed in garment_detector.py, and the test sets are the M40 test
manifests (never used for training or selection). Metrics code is imported read-only from evaluate_m40.py so the
numbers are comparable with its 'crop' and 'full' modes.

    backend\\venv\\Scripts\\python ai_training\\scripts\\v2\\eval_m40_detector_crop.py --detector <best.pt> --out <dir>
"""
import argparse
import json
import os
import sys

import numpy as np
import torch

sys.path.insert(0, ".")
from ai_training.scripts import evaluate_m40 as ev  # noqa: E402
from backend.app.ai import garment_detector as gd  # noqa: E402
from backend.app.ai.multitask_classifier import get_multitask_classifier, preprocess_image_crop  # noqa: E402

M40 = "backend/app/ai/models/garment_multitask_m40_15class.pt"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--detector", required=True)
    ap.add_argument("--classifier", default=M40)
    ap.add_argument("--out", required=True)
    ap.add_argument("--sets", default=",".join(ev.SETS), help="comma list of M40 test sets")
    ap.add_argument("--limit", type=int, default=0, help="smoke test only: first N records per set")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    model, meta = get_multitask_classifier(model_path=a.classifier)
    names = {h: [meta["idx_to_class"][h][str(i)] for i in range(len(meta["idx_to_class"][h]))] for h in ev.HEADS}
    thr_path = os.path.splitext(a.classifier)[0] + ".thresholds.json"
    thresholds = json.load(open(thr_path, encoding="utf-8"))
    result = {"classifier": a.classifier, "classifier_sha256": meta["checkpoint_sha256"], "detector": a.detector,
              "detector_min_score": gd.MIN_SCORE, "crop_margin": gd.CROP_MARGIN, "thresholds_used": thresholds, "sets": {}}
    for set_name, fname in ev.SETS.items():
        if set_name not in a.sets.split(","):
            continue
        recs = ev.load(os.path.join(ev.MAN, fname))
        if a.limit:
            recs = recs[:a.limit]
            result["SMOKE_TEST_LIMIT"] = a.limit
        probs = {h: [] for h in ev.HEADS}
        det_stats = {"box": 0, "no_box": 0, "unavailable": 0, "class": {}}
        with torch.inference_mode():
            for r in recs:
                path, _ = ev.image_for(r, "full")
                d = gd.detect_garment(path, model_path=a.detector)
                box = None
                if not d["available"]:
                    det_stats["unavailable"] += 1
                elif d["box_xyxy"] is None:
                    det_stats["no_box"] += 1
                else:
                    det_stats["box"] += 1
                    det_stats["class"][d["class"]] = det_stats["class"].get(d["class"], 0) + 1
                    from PIL import Image, ImageOps
                    with Image.open(path) as im:
                        W, H = ImageOps.exif_transpose(im).size
                    box = gd.pad_box(d["box_xyxy"], W, H)
                logits = model(preprocess_image_crop(path, bbox=box))
                for h in ev.HEADS:
                    probs[h].append(torch.softmax(logits[h], dim=1).numpy()[0])
        heads = {}
        for h in ev.HEADS:
            idx, y = ev.labels_of(recs, h)
            if not idx:
                continue
            P = np.array(probs[h])[idx]
            pred = [names[h][int(k)] for k in P.argmax(1)]
            m = ev.metrics(y, pred, list(ev.ACTIVE[h]))
            conf = P.max(1)
            t = thresholds.get(h)
            if t is None:
                m["answered"] = {"threshold": None, "coverage": 0.0, "accuracy_when_answered": None,
                                 "note": "head always shown as uncertain (no validation threshold reached the target)"}
            else:
                ans = conf >= t
                correct = np.array([a_ == b_ for a_, b_ in zip(y, pred)])
                m["answered"] = {"threshold": t, "coverage": round(float(ans.mean()), 4),
                                 "accuracy_when_answered": round(float(correct[ans].mean()), 4) if ans.any() else None}
            heads[h] = m
        result["sets"][set_name] = {"n_records": len(recs), "detector": det_stats, "heads": heads}
        print(set_name, det_stats, {h: (v["n"], v["accuracy"], v["macro_f1"], v["answered"]) for h, v in heads.items()}, flush=True)
    json.dump(result, open(os.path.join(a.out, "m40_detector_crop_eval.json"), "w"), indent=2)


if __name__ == "__main__":
    main()
