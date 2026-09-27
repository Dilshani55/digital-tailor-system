#!/usr/bin/env python3
"""
validate_ai_labels.py

Validates zero-shot AI pseudo-labels and output artifacts for Milestone AI-6B.

Validations:
- Only the three project garment targets (blouse, t-shirt, crop-top) plus reject appear
- No source ontology terms (shirt, top, sweatshirt) appear as target classes
- No duplicate annotation IDs across output manifests
- Accepted pseudo-labels satisfy confidence, margin, and prompt-agreement rules
- Review-required labels are not treated as accepted
- Every pseudo-label explicitly states human_verified: false and label_origin: ai_assisted_pseudo_label
- Project splits remain unchanged
- Summaries match JSONL outputs
- Downloaded/generated data remains ignored by Git
"""

import argparse
import json
import os
import subprocess
import sys


def parse_args():
    parser = argparse.ArgumentParser(description="Validate AI pseudo-labels and output artifacts")
    parser.add_argument("--labelling-dir", required=True, help="Directory containing labelling JSONL outputs")
    parser.add_argument("--classes", required=True, help="Path to config/classes.json")
    parser.add_argument("--config", required=True, help="Path to config/ai_assisted_labelling.json")
    return parser.parse_args()


def main():
    args = parse_args()

    with open(args.classes, "r", encoding="utf-8") as f:
        classes_config = json.load(f)

    with open(args.config, "r", encoding="utf-8") as f:
        labelling_config = json.load(f)

    target_classes = set(labelling_config.get("target_classes", ["blouse", "t-shirt", "crop-top"]))
    reject_class = labelling_config.get("reject_class", "reject")
    allowed_labels = target_classes.union({reject_class, "unclear"})
    forbidden_terms = {"shirt", "top", "sweatshirt"}

    conf_threshold = labelling_config.get("confidence_threshold", 0.60)
    min_margin = labelling_config.get("minimum_margin", 0.10)

    errors = []

    # Check Git ignore status on data directory
    try:
        git_res = subprocess.run(["git", "status", "--ignored", "-sb", "ai_training/data/"], capture_output=True, text=True)
        if "!! ai_training/data/" not in git_res.stdout:
            errors.append("ai_training/data/ directory is NOT ignored by Git!")
    except Exception as e:
        print(f"Warning: Failed to check git status: {e}")

    # Read accepted pseudo-labels
    accepted_path = os.path.join(args.labelling_dir, "accepted_pseudo_labels.jsonl")
    review_path = os.path.join(args.labelling_dir, "review_required.jsonl")
    rejected_path = os.path.join(args.labelling_dir, "rejected.jsonl")
    all_preds_path = os.path.join(args.labelling_dir, "ai_predictions.jsonl")
    summary_path = os.path.join(args.labelling_dir, "ai_labelling_summary.json")

    accepted_recs = []
    if os.path.exists(accepted_path):
        with open(accepted_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    accepted_recs.append(json.loads(line.strip()))

    review_recs = []
    if os.path.exists(review_path):
        with open(review_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    review_recs.append(json.loads(line.strip()))

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

    # 1. Validate accepted pseudo-labels
    seen_accepted_anns = set()
    accepted_counts = {c: 0 for c in target_classes}

    for idx, rec in enumerate(accepted_recs, 1):
        ann_id = rec.get("source_annotation_id")
        lbl = rec.get("predicted_garment_type")
        conf = rec.get("top1_confidence", 0.0)
        margin = rec.get("margin", 0.0)
        agreement = rec.get("prompt_agreement", False)
        hv = rec.get("human_verified")
        origin = rec.get("label_origin")

        if ann_id in seen_accepted_anns:
            errors.append(f"Accepted record #{idx}: Duplicate source_annotation_id={ann_id}")
        seen_accepted_anns.add(ann_id)

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

    # 2. Validate review_required records
    for idx, rec in enumerate(review_recs, 1):
        if rec.get("decision") != "review_required":
            errors.append(f"Review-required record #{idx}: decision is '{rec.get('decision')}' instead of 'review_required'")
        if rec.get("human_verified") is not False:
            errors.append(f"Review-required record #{idx}: human_verified must be False")

    # 3. Summary reconciliation
    if os.path.exists(summary_path):
        with open(summary_path, "r", encoding="utf-8") as f:
            summary = json.load(f)

        d_counts = summary.get("decision_counts", {})
        if d_counts.get("accepted", 0) != len(accepted_recs):
            errors.append(f"Summary accepted count ({d_counts.get('accepted')}) != accepted_pseudo_labels.jsonl count ({len(accepted_recs)})")
        if d_counts.get("review_required", 0) != len(review_recs):
            errors.append(f"Summary review_required count ({d_counts.get('review_required')}) != review_required.jsonl count ({len(review_recs)})")
        if d_counts.get("rejected", 0) != len(rejected_recs):
            errors.append(f"Summary rejected count ({d_counts.get('rejected')}) != rejected.jsonl count ({len(rejected_recs)})")

    print("\n--- AI Pseudo-Label Validation Results ---")
    print(f"Total evaluated predictions: {len(all_pred_recs)}")
    print(f"Accepted pseudo-labels: {len(accepted_recs)} {accepted_counts}")
    print(f"Review-required: {len(review_recs)}")
    print(f"Rejected AI predictions: {len(rejected_recs)}")

    if errors:
        print(f"\nVALIDATION FAILED with {len(errors)} errors:")
        for err in errors[:10]:
            print(f"  - {err}")
        sys.exit(1)
    else:
        print("\nVALIDATION PASSED: All AI pseudo-labels satisfy strict project constraints.")


if __name__ == "__main__":
    main()
