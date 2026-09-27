#!/usr/bin/env python3
"""
validate_candidate_selection.py

Validates the candidate queue generated for AI-assisted garment labelling (Milestone AI-6B).

Validations:
- Exactly the three project target classes (blouse, t-shirt, crop-top) appear
- No source ontology terms (shirt, top, sweatshirt) appear as target classes
- No duplicate source annotation IDs
- Maximum download target limit respected (<= 450)
- Candidate garment rules (Crop-top precedence with Attr 8, T-shirt Cat 1 Attr 0/4, Blouse Cat 0)
- Split preservation (train, val, test)
"""

import argparse
import json
import os
import sys


def parse_args():
    parser = argparse.ArgumentParser(description="Validate candidate queue")
    parser.add_argument("--queue", required=True, help="Path to candidate_queue.jsonl")
    parser.add_argument("--classes", required=True, help="Path to config/classes.json")
    parser.add_argument("--config", required=True, help="Path to config/ai_assisted_labelling.json")
    return parser.parse_args()


def main():
    args = parse_args()

    with open(args.classes, "r", encoding="utf-8") as f:
        classes_config = json.load(f)
    
    with open(args.config, "r", encoding="utf-8") as f:
        labelling_config = json.load(f)

    project_garment_classes = set(classes_config.get("outputs", {}).get("garment_type", {}).get("classes", []))
    allowed_target_classes = set(labelling_config.get("target_classes", ["blouse", "t-shirt", "crop-top"]))
    max_download_target = labelling_config.get("max_download_target", 450)
    forbidden_source_terms = {"shirt", "top", "sweatshirt"}

    if allowed_target_classes != project_garment_classes:
        print(f"ERROR: Configured target classes {allowed_target_classes} do not match project taxonomy {project_garment_classes}!")
        sys.exit(1)

    print(f"Validating candidate queue at {args.queue}...")
    
    seen_annotation_ids = set()
    errors = []
    class_counts = {c: 0 for c in allowed_target_classes}
    split_counts = {}

    total_records = 0

    with open(args.queue, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            if not line.strip():
                continue
            total_records += 1
            rec = json.loads(line.strip())

            ann_id = rec.get("source_annotation_id")
            cand_cls = rec.get("candidate_garment_type")
            cat_id = rec.get("fashionpedia_category_id")
            attrs = set(rec.get("fashionpedia_attribute_ids", []))
            split = rec.get("split")

            # 1. Duplicate check
            if ann_id in seen_annotation_ids:
                errors.append(f"Line {line_num}: Duplicate source_annotation_id={ann_id}")
            seen_annotation_ids.add(ann_id)

            # 2. Class check
            if cand_cls not in allowed_target_classes:
                errors.append(f"Line {line_num}: Invalid candidate class '{cand_cls}'. Must be one of {allowed_target_classes}")

            if cand_cls in forbidden_source_terms:
                errors.append(f"Line {line_num}: Source ontology term '{cand_cls}' present as target class!")

            # 3. Rule checks
            if cand_cls == "crop-top":
                if 8 not in attrs or cat_id not in (0, 1):
                    errors.append(f"Line {line_num}: Crop-top record missing Attr 8 or valid Cat 0/1 (cat={cat_id}, attrs={attrs})")
            elif cand_cls == "t-shirt":
                if cat_id != 1 or (0 not in attrs and 4 not in attrs):
                    errors.append(f"Line {line_num}: T-shirt record invalid for Cat 1 Attr 0/4 (cat={cat_id}, attrs={attrs})")
            elif cand_cls == "blouse":
                if cat_id != 0 or 8 in attrs:
                    errors.append(f"Line {line_num}: Blouse record invalid for Cat 0 without Attr 8 (cat={cat_id}, attrs={attrs})")

            # 4. Split check
            if split not in ("train", "val", "test"):
                errors.append(f"Line {line_num}: Invalid split '{split}'")

            if cand_cls in class_counts:
                class_counts[cand_cls] += 1
            split_counts[split] = split_counts.get(split, 0) + 1

    # 5. Quantity checks
    if total_records > max_download_target:
        errors.append(f"Candidate queue count ({total_records}) exceeds max_download_target ({max_download_target})")

    print("\n--- Candidate Selection Validation Results ---")
    print(f"Total candidate records: {total_records}")
    print(f"Counts by proposed class: {class_counts}")
    print(f"Counts by split: {split_counts}")

    if errors:
        print(f"\nVALIDATION FAILED with {len(errors)} errors:")
        for err in errors[:10]:
            print(f"  - {err}")
        sys.exit(1)
    else:
        print("\nVALIDATION PASSED: All candidate queue records satisfy project constraints.")


if __name__ == "__main__":
    main()
