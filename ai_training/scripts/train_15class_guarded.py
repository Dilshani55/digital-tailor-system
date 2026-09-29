#!/usr/bin/env python3
"""
train_15class_guarded.py - the ONLY sanctioned way to start 3/5/3/4 (15-class) training.

It refuses to start (exit code 2, nothing is launched) unless ALL of these hold:
  1. manifests_15class/counts.json says readiness == READY (every class meets the trusted-sample targets);
  2. the manifest files on disk still match the checksums recorded in counts.json;
  3. the class configuration is 3/5/3/4 and matches the checksum recorded in counts.json;
  4. no old checkpoint is passed in (there is no --init-checkpoint; a 3/10/6/9 or 3/9/6/9 checkpoint is
     never compatible).
After training it verifies that the produced checkpoint has head dimensions 3/5/3/4 (exit code 3 if not).
It never touches backend/app/ai/models (the production M13 model).

Show the exact command without running it:   ... --print-command
Normal use (only once READY):
  PYTHONPATH=. python ai_training/scripts/train_15class_guarded.py
"""

import argparse
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from ai_training.training import labels15 as L   # noqa: E402

PRODUCTION_DIR = os.path.normpath("backend/app/ai/models")
EXPECTED_DIMS = {"garment_type": 3, "neckline_type": 5, "sleeve_length": 3, "sleeve_style": 4}


def preflight(args):
    """Return (ok, problems, report). Pure checks - launches nothing."""
    problems = []
    counts_path = os.path.join(args.manifest_dir, "counts.json")
    if not os.path.exists(counts_path):
        return False, [f"{counts_path} not found - run build_15class_manifests.py first"], None
    doc = json.load(open(counts_path, encoding="utf-8"))
    report = doc.get("readiness", {})
    if report.get("verdict") != "READY":
        missing = ", ".join(f"{c['head']}={c['class']}" for c in report.get("insufficient_classes", []))
        problems.append(f"label requirements not met (NOT_READY): insufficient trusted evidence for {missing or 'unknown classes'}")
    for name, want in (doc.get("manifest_sha256") or {}).items():
        path = os.path.join(args.manifest_dir, name)
        if not os.path.exists(path) or L.sha256_file(path) != want:
            problems.append(f"manifest {name} is missing or changed since counts.json was written")
    try:
        L.load_classes(args.classes)
    except Exception as exc:                                                       # noqa: BLE001
        problems.append(f"class configuration invalid: {exc}")
    else:
        if L.sha256_file(args.classes) != doc.get("classes_config_sha256"):
            problems.append("class configuration changed since the manifests were built")
    if os.path.normpath(args.output_dir).startswith(PRODUCTION_DIR):
        problems.append("the output directory must not be inside the production model folder")
    return not problems, problems, report


def training_command(args):
    return [sys.executable, "ai_training/scripts/train_multitask.py",
            "--config", args.config, "--classes", args.classes,
            "--train-manifest", os.path.join(args.manifest_dir, "train.jsonl"),
            "--val-manifest", os.path.join(args.manifest_dir, "val.jsonl"),
            "--output-dir", args.output_dir]


def verify_checkpoint(path):
    import torch
    ckpt = torch.load(path, map_location="cpu", weights_only=False)
    dims = {h: int(v) for h, v in (ckpt.get("head_dimensions") or {}).items()}
    return dims == EXPECTED_DIMS, dims


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest-dir", default="ai_training/data/manifests_15class")
    ap.add_argument("--classes", default="ai_training/config/classes_v2_15class.json")
    ap.add_argument("--config", default="ai_training/config/m30_15class_config.json")
    ap.add_argument("--output-dir", default="ai_training/data/training_runs/m30_15class")
    ap.add_argument("--print-command", action="store_true")
    args = ap.parse_args()

    cmd = training_command(args)
    if args.print_command:
        print(" ".join(cmd))
        return 0

    ok, problems, report = preflight(args)
    if not ok:
        print("REFUSING TO TRAIN the 15-class model:")
        for p in problems:
            print("  - " + p)
        print("Nothing was started. See docs/FUTURE_15_CLASS_MODEL.md for the label requirements.")
        return 2

    print("Requirements satisfied. Running:", " ".join(cmd))
    rc = subprocess.call(cmd)
    if rc != 0:
        return rc
    best = os.path.join(args.output_dir, "checkpoints", "best.pt")
    good, dims = verify_checkpoint(best)
    print(f"checkpoint head dimensions: {dims}  ->  {'OK' if good else 'WRONG (expected 3/5/3/4)'}")
    return 0 if good else 3


if __name__ == "__main__":
    sys.exit(main())
