"""Evaluate M41 against M40 with the SAME code and the SAME test images.

1. evaluate_m40.main() (imported read-only) with MAN -> manifests_m41 (whose test files are byte-identical copies of
   the M40 ones) plus the extra set test_dmm: candidate = M41, baseline = M40, garment-crop and whole-photo modes,
   majority baseline, per-class results, thresholds chosen on validation (whole-photo mode, the M40 rule).
2. eval_m40_detector_crop.main() for M41 and for M40: the detector-crop mode the app uses. M41's thresholds from
   step 1 are written as a sidecar next to a COPY of the M41 checkpoint in the run folder (nothing deployed).

    backend\\venv\\Scripts\\python ai_training\\scripts\\v2\\eval_m41.py --m41 <best.pt> --out <dir>
"""
import argparse
import json
import os
import shutil
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "backend")
from ai_training.scripts import evaluate_m40 as ev  # noqa: E402
from ai_training.scripts.v2 import eval_m40_detector_crop as dc  # noqa: E402

M40 = "backend/app/ai/models/garment_multitask_m40_15class.pt"
DET = "backend/app/ai/models/garment_detector_v1.pt"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--m41", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    ev.MAN = "ai_training/data/manifests_m41"
    ev.SETS = dict(ev.SETS, test_dmm="test_dmm.jsonl")

    sys.argv = ["evaluate_m40", "--candidate", a.m41, "--baseline", M40, "--out", os.path.join(a.out, "crop_and_full")]
    ev.main()

    staged = os.path.join(a.out, "m41_candidate.pt")
    shutil.copyfile(a.m41, staged)
    thr = json.load(open(os.path.join(a.out, "crop_and_full", "thresholds.json")))
    thr["_note"] = "chosen on the M41 validation split (whole-photo mode), same rule as M40; candidate only, not deployed"
    json.dump(thr, open(os.path.splitext(staged)[0] + ".thresholds.json", "w"), indent=2)

    for tag, clf in (("m41", staged), ("m40", M40)):
        sys.argv = ["eval_m40_detector_crop", "--detector", DET, "--classifier", clf, "--out", os.path.join(a.out, f"detector_crop_{tag}")]
        dc.main()


if __name__ == "__main__":
    main()
