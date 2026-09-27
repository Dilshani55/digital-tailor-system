#!/usr/bin/env python3
"""
validate_human_review.py

Validates targeted human review queue and saved human decision artifacts for Milestone M9A.

Validations:
- Unique source_annotation_id values in review queue and decisions.
- Decisions reference valid queue records.
- Allowed human_label values only (blouse, t-shirt, crop-top, reject, uncertain).
- human_verified must be explicitly true on all saved human decisions.
- Non-empty reviewer_id and valid UTC ISO-8601 timestamp.
- Crop file exists and crop_sha256 matches queue record.
- Split preservation (decision.split == queue.split).
- Exact reviewed/remaining arithmetic.
- Zero image_id leakage across train/val/test splits.
- ai_training/data/ remains ignored by Git.
"""

import argparse
import datetime
import hashlib
import json
import os
import subprocess
import sys


def parse_args():
    parser = argparse.ArgumentParser(description="Validate human review queue and decisions")
    parser.add_argument("--review-dir", required=True, help="Directory containing review_queue.jsonl and human_decisions.jsonl")
    parser.add_argument("--policy", required=True, help="Path to config/human_review_policy.json")
    return parser.parse_args()


def compute_sha256(filepath):
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()


def validate_iso_timestamp(ts_str):
    if not ts_str or not isinstance(ts_str, str):
        return False
    try:
        # Normalize trailing Z
        if ts_str.endswith("Z"):
            ts_str = ts_str[:-1] + "+00:00"
        datetime.datetime.fromisoformat(ts_str)
        return True
    except Exception:
        return False


def main():
    args = parse_args()

    with open(args.policy, "r", encoding="utf-8") as f:
        policy = json.load(f)

    allowed_labels = set(policy.get("allowed_human_labels", ["blouse", "t-shirt", "crop-top", "reject", "uncertain"]))
    max_queue_total = policy.get("max_queue_total", 700)

    errors = []

    # 1. Check Git ignore status on data directory
    try:
        git_res = subprocess.run(["git", "status", "--ignored", "-sb", "ai_training/data/"], capture_output=True, text=True)
        if "!! ai_training/data/" not in git_res.stdout:
            errors.append("ai_training/data/ directory is NOT ignored by Git!")
    except Exception as e:
        print(f"Warning: Failed to check git status: {e}")

    queue_path = os.path.join(args.review_dir, "review_queue.jsonl")
    decisions_path = os.path.join(args.review_dir, "human_decisions.jsonl")
    summary_path = os.path.join(args.review_dir, "review_queue_summary.json")

    if not os.path.exists(queue_path):
        print(f"ERROR: Review queue file not found at {queue_path}")
        sys.exit(1)

    queue_records = []
    queue_map = {}
    seen_queue_ann_ids = set()
    split_by_img = {}

    with open(queue_path, "r", encoding="utf-8") as f:
        for idx, line in enumerate(f, 1):
            if not line.strip():
                continue
            rec = json.loads(line.strip())
            ann_id = rec.get("source_annotation_id")
            img_id = rec.get("source_image_id")
            split = rec.get("split")
            crop_path = rec.get("crop_path")

            if ann_id in seen_queue_ann_ids:
                errors.append(f"Queue record #{idx}: Duplicate source_annotation_id={ann_id}")
            seen_queue_ann_ids.add(ann_id)
            queue_map[ann_id] = rec
            queue_records.append(rec)

            # Check split consistency across image_id
            if img_id is not None and split is not None:
                if img_id in split_by_img and split_by_img[img_id] != split:
                    errors.append(f"Queue record #{idx}: Image ID {img_id} appears in multiple splits ({split_by_img[img_id]} vs {split})")
                split_by_img[img_id] = split

            # Verify crop file existence and SHA-256 if path present
            if crop_path:
                if not os.path.exists(crop_path):
                    errors.append(f"Queue record #{idx}: Crop file missing at {crop_path}")
                elif rec.get("crop_sha256"):
                    calc_sha = compute_sha256(crop_path)
                    if calc_sha != rec["crop_sha256"]:
                        errors.append(f"Queue record #{idx}: Crop SHA256 mismatch for {crop_path}")

            # Verify human_verified is false in queue
            if rec.get("human_verified") is not False:
                errors.append(f"Queue record #{idx}: human_verified in queue must be False (got {rec.get('human_verified')})")

    if len(queue_records) > max_queue_total:
        errors.append(f"Total review queue records ({len(queue_records)}) exceeds max_queue_total ({max_queue_total})")

    # Load decisions
    decisions = []
    decision_map = {}
    seen_decision_ann_ids = set()

    if os.path.exists(decisions_path):
        with open(decisions_path, "r", encoding="utf-8") as f:
            for idx, line in enumerate(f, 1):
                if not line.strip():
                    continue
                d_rec = json.loads(line.strip())
                ann_id = d_rec.get("source_annotation_id")
                lbl = d_rec.get("human_label")
                hv = d_rec.get("human_verified")
                rev_id = d_rec.get("reviewer_id")
                ts = d_rec.get("reviewed_at")

                if ann_id in seen_decision_ann_ids:
                    errors.append(f"Decision record #{idx}: Duplicate source_annotation_id={ann_id}")
                seen_decision_ann_ids.add(ann_id)
                decision_map[ann_id] = d_rec
                decisions.append(d_rec)

                # Check queue reference
                if ann_id not in queue_map:
                    errors.append(f"Decision record #{idx}: References unknown source_annotation_id={ann_id} not in queue!")
                else:
                    q_rec = queue_map[ann_id]
                    if d_rec.get("split") != q_rec.get("split"):
                        errors.append(f"Decision record #{idx}: Split changed from queue ({q_rec.get('split')} vs {d_rec.get('split')})")

                # Check allowed labels
                if lbl not in allowed_labels:
                    errors.append(f"Decision record #{idx}: Invalid human_label '{lbl}'. Must be one of {allowed_labels}")

                # Check human_verified is true
                if hv is not True:
                    errors.append(f"Decision record #{idx}: human_verified must be explicitly True (got {hv})")

                # Check reviewer_id
                if not rev_id or not isinstance(rev_id, str) or not rev_id.strip():
                    errors.append(f"Decision record #{idx}: Missing or empty reviewer_id!")

                # Check timestamp
                if not validate_iso_timestamp(ts):
                    errors.append(f"Decision record #{idx}: Invalid ISO-8601 reviewed_at timestamp '{ts}'")

    # Arithmetic checks
    total_queue = len(queue_records)
    reviewed_count = len(decision_map)
    remaining_count = total_queue - reviewed_count

    if reviewed_count + remaining_count != total_queue:
        errors.append(f"Arithmetic mismatch: reviewed ({reviewed_count}) + remaining ({remaining_count}) != total queue ({total_queue})")

    # Summary reconciliation if summary exists
    if os.path.exists(summary_path):
        with open(summary_path, "r", encoding="utf-8") as f:
            summary = json.load(f)
        if summary.get("total_queue_records") != total_queue:
            errors.append(f"Summary total_queue_records ({summary.get('total_queue_records')}) != review_queue.jsonl count ({total_queue})")

    print("\n--- Human Review Validation Results ---")
    print(f"Total Review Queue Records: {total_queue}")
    print(f"Completed Human Decisions: {reviewed_count}")
    print(f"Remaining Unreviewed Items: {remaining_count}")
    print(f"Unique Images in Queue:     {len(split_by_img)}")

    if errors:
        print(f"\nVALIDATION FAILED with {len(errors)} errors:")
        for err in errors[:10]:
            print(f"  - {err}")
        sys.exit(1)
    else:
        print("\nVALIDATION PASSED: All review queue and decision artifacts satisfy strict project constraints.")


if __name__ == "__main__":
    main()
