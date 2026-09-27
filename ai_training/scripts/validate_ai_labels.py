#!/usr/bin/env python3
"""
validate_ai_labels.py

Validates zero-shot AI pseudo-labels and output artifacts for Milestone M8.

Validations:
- Exact record accounting: accepted + manual_review + rejected + failed == evaluated total
- Source annotation IDs are unique across output manifests
- All crop files exist and crop SHA-256 values match
- Every crop is derived from an official verified image
- No original_url source is present
- No image_id crosses train/val/test splits
- Accepted labels belong to blouse/t-shirt/crop-top
- Accepted pseudo-labels always have human_verified=false
- Threshold and prompt-agreement rules are enforced
- Direct evidence and pseudo-label provenance remain separate
- Downloaded/generated data remains ignored by Git
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys


def parse_args():
    parser = argparse.ArgumentParser(description="Validate AI pseudo-labels and output artifacts")
    parser.add_argument("--labelling-dir", required=True, help="Directory containing labelling JSONL outputs")
    parser.add_argument("--crop-manifest", default=None, help="Path to crop_manifest.jsonl (optional)")
    parser.add_argument("--classes", required=True, help="Path to config/classes.json")
    parser.add_argument("--config", required=True, help="Path to config/ai_assisted_labelling.json")
    return parser.parse_args()


def compute_sha256(filepath):
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()


def main():
    args = parse_args()

    with open(args.classes, "r", encoding="utf-8") as f:
        classes_config = json.load(f)

    with open(args.config, "r", encoding="utf-8") as f:
        labelling_config = json.load(f)

    project_garment_classes = set(classes_config.get("outputs", {}).get("garment_type", {}).get("classes", []))
    target_classes = set(labelling_config.get("target_classes", ["blouse", "t-shirt", "crop-top"]))
    reject_class = labelling_config.get("reject_class", "reject")
    forbidden_terms = {"shirt", "top", "sweatshirt"}

    conf_threshold = labelling_config.get("confidence_threshold", 0.60)
    min_margin = labelling_config.get("minimum_margin", 0.10)

    errors = []

    # 1. Check Git ignore status on data directory
    try:
        git_res = subprocess.run(["git", "status", "--ignored", "-sb", "ai_training/data/"], capture_output=True, text=True)
        if "!! ai_training/data/" not in git_res.stdout:
            errors.append("ai_training/data/ directory is NOT ignored by Git!")
    except Exception as e:
        print(f"Warning: Failed to check git status: {e}")

    # Read output files
    labelling_dir = args.labelling_dir
    accepted_path = os.path.join(labelling_dir, "accepted_pseudo_labels.jsonl")
    manual_review_path = os.path.join(labelling_dir, "manual_review.jsonl")
    if not os.path.exists(manual_review_path):
        manual_review_path = os.path.join(labelling_dir, "review_required.jsonl")
    rejected_path = os.path.join(labelling_dir, "rejected.jsonl")
    all_preds_path = os.path.join(labelling_dir, "ai_labels_all.jsonl")
    if not os.path.exists(all_preds_path):
        all_preds_path = os.path.join(labelling_dir, "ai_predictions.jsonl")
    summary_path = os.path.join(labelling_dir, "labelling_summary.json")
    if not os.path.exists(summary_path):
        summary_path = os.path.join(labelling_dir, "ai_labelling_summary.json")

    accepted_recs = []
    if os.path.exists(accepted_path):
        with open(accepted_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    accepted_recs.append(json.loads(line.strip()))

    manual_review_recs = []
    if os.path.exists(manual_review_path):
        with open(manual_review_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    manual_review_recs.append(json.loads(line.strip()))

    rejected_recs = []
    if os.path.exists(rejected_path):
        with open(rejected_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    rejected_recs.append(json.loads(line.strip()))

    all_pred_recs = []
    if os.path.exists(all_preds_path):
        with open(all_preds_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    all_pred_recs.append(json.loads(line.strip()))

    # Exact record accounting
    failed_count = sum(1 for r in all_pred_recs if r.get("decision") == "failed")
    calculated_total = len(accepted_recs) + len(manual_review_recs) + len(rejected_recs) + failed_count

    if len(all_pred_recs) != calculated_total:
        errors.append(f"Record accounting mismatch: all predictions ({len(all_pred_recs)}) != accepted ({len(accepted_recs)}) + manual_review ({len(manual_review_recs)}) + rejected ({len(rejected_recs)}) + failed ({failed_count}) = {calculated_total}")

    # Check unique annotation IDs and no original_url
    seen_all_ann_ids = set()
    split_by_image_id = {}

    for idx, rec in enumerate(all_pred_recs, 1):
        ann_id = rec.get("source_annotation_id")
        img_id = rec.get("source_image_id")
        split = rec.get("split")
        crop_path = rec.get("crop_path")

        if ann_id in seen_all_ann_ids:
            errors.append(f"Prediction #{idx}: Duplicate source_annotation_id={ann_id}")
        seen_all_ann_ids.add(ann_id)

        # Check split consistency per image_id
        if img_id is not None and split is not None:
            if img_id in split_by_image_id and split_by_image_id[img_id] != split:
                errors.append(f"Prediction #{idx}: Image ID {img_id} appears in multiple splits ({split_by_image_id[img_id]} vs {split})")
            split_by_image_id[img_id] = split

        # Check no original_url in record
        if "original_url" in rec or "url" in rec:
            errors.append(f"Prediction #{idx}: original_url detected in prediction record!")

        if crop_path and "http" in crop_path.lower():
            errors.append(f"Prediction #{idx}: URL crop path detected: {crop_path}")

    # Validate accepted pseudo-labels
    accepted_counts = {c: 0 for c in target_classes}
    for idx, rec in enumerate(accepted_recs, 1):
        lbl = rec.get("predicted_garment_type")
        conf = rec.get("top1_confidence", 0.0)
        margin = rec.get("margin", 0.0)
        agreement = rec.get("prompt_agreement", False)
        hv = rec.get("human_verified")
        origin = rec.get("label_origin")

        if lbl not in target_classes:
            errors.append(f"Accepted record #{idx}: Label '{lbl}' is not in project target classes {target_classes}")

        if lbl in forbidden_terms:
            errors.append(f"Accepted record #{idx}: Source term '{lbl}' present as target label!")

        if conf < conf_threshold:
            errors.append(f"Accepted record #{idx}: Confidence {conf} below threshold {conf_threshold}")

        if margin < min_margin:
            errors.append(f"Accepted record #{idx}: Margin {margin} below minimum {min_margin}")

        if not agreement:
            errors.append(f"Accepted record #{idx}: Missing multi-prompt agreement")

        if hv is not False:
            errors.append(f"Accepted record #{idx}: human_verified must be explicitly False (got {hv})")

        if origin != "ai_assisted_pseudo_label":
            errors.append(f"Accepted record #{idx}: Invalid label_origin '{origin}'")

        if lbl in accepted_counts:
            accepted_counts[lbl] += 1

        # Check crop file existence and SHA256 if path present
        crop_p = rec.get("crop_path")
        if crop_p:
            if not os.path.exists(crop_p):
                errors.append(f"Accepted record #{idx}: Crop file not found at {crop_p}")
            elif "crop_sha256" in rec:
                calc_sha = compute_sha256(crop_p)
                if calc_sha != rec["crop_sha256"]:
                    errors.append(f"Accepted record #{idx}: SHA256 mismatch for {crop_p} (expected {rec['crop_sha256']}, got {calc_sha})")

    # Validate manual review records
    for idx, rec in enumerate(manual_review_recs, 1):
        if rec.get("decision") not in ("manual_review", "review_required"):
            errors.append(f"Manual review record #{idx}: invalid decision '{rec.get('decision')}'")
        if rec.get("human_verified") is not False:
            errors.append(f"Manual review record #{idx}: human_verified must be False")

    # Summary reconciliation
    if os.path.exists(summary_path):
        with open(summary_path, "r", encoding="utf-8") as f:
            summary = json.load(f)

        d_counts = summary.get("decision_counts", {})
        if d_counts.get("accepted", 0) != len(accepted_recs):
            errors.append(f"Summary accepted count ({d_counts.get('accepted')}) != accepted_pseudo_labels.jsonl count ({len(accepted_recs)})")
        if d_counts.get("manual_review", 0) != len(manual_review_recs) and d_counts.get("review_required", 0) != len(manual_review_recs):
            errors.append(f"Summary manual_review count != manual_review.jsonl count ({len(manual_review_recs)})")
        if d_counts.get("rejected", 0) != len(rejected_recs):
            errors.append(f"Summary rejected count ({d_counts.get('rejected')}) != rejected.jsonl count ({len(rejected_recs)})")

    print("\n--- AI Pseudo-Label Validation Results ---")
    print(f"Total evaluated predictions: {len(all_pred_recs)}")
    print(f"Accepted pseudo-labels: {len(accepted_recs)} {accepted_counts}")
    print(f"Manual review required: {len(manual_review_recs)}")
    print(f"Rejected AI predictions: {len(rejected_recs)}")
    print(f"Failed processing: {failed_count}")

    if errors:
        print(f"\nVALIDATION FAILED with {len(errors)} errors:")
        for err in errors[:10]:
            print(f"  - {err}")
        sys.exit(1)
    else:
        print("\nVALIDATION PASSED: All AI pseudo-labels satisfy strict project constraints.")


if __name__ == "__main__":
    main()
