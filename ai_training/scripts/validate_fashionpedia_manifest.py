#!/usr/bin/env python3
"""
validate_fashionpedia_manifest.py

Validates generated Fashionpedia dataset manifests for integrity, schema compliance,
decision consistency, and zero cross-split data leakage.

Usage:
    python ai_training/scripts/validate_fashionpedia_manifest.py \
      --manifest-dir ai_training/data/processed/fashionpedia_manifest \
      --classes ai_training/config/classes.json
"""

import sys
import os
import json
import argparse


def load_jsonl(filepath):
    records = []
    if not os.path.exists(filepath):
        print(f"ERROR: JSONL file not found: {filepath}", file=sys.stderr)
        sys.exit(1)

    with open(filepath, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line_str = line.strip()
            if not line_str:
                continue
            try:
                records.append(json.loads(line_str))
            except Exception as e:
                print(f"ERROR: Malformed JSONL at {filepath}:{line_num}: {e}", file=sys.stderr)
                sys.exit(1)
    return records


def validate_manifest(manifest_dir, classes_path):
    if not os.path.exists(manifest_dir):
        print(f"ERROR: Manifest directory not found: {manifest_dir}", file=sys.stderr)
        sys.exit(1)

    if not os.path.exists(classes_path):
        print(f"ERROR: Classes file not found: {classes_path}", file=sys.stderr)
        sys.exit(1)

    try:
        with open(classes_path, "r", encoding="utf-8") as f:
            classes_data = json.load(f)
    except Exception as e:
        print(f"ERROR: Failed to load classes.json: {e}", file=sys.stderr)
        sys.exit(1)

    expected_heads = list(classes_data["outputs"].keys())
    valid_labels_per_head = {h: set(info["classes"]) for h, info in classes_data["outputs"].items()}

    summary_path = os.path.join(manifest_dir, "summary.json")
    if not os.path.exists(summary_path):
        print(f"ERROR: summary.json not found in {manifest_dir}", file=sys.stderr)
        sys.exit(1)

    try:
        with open(summary_path, "r", encoding="utf-8") as f:
            summary = json.load(f)
    except Exception as e:
        print(f"ERROR: Failed to parse summary.json: {e}", file=sys.stderr)
        sys.exit(1)

    print("==================================================")
    print("FASHIONPEDIA MANIFEST VALIDATION RUN")
    print("==================================================")
    print(f"Manifest Directory: {os.path.abspath(manifest_dir)}")

    # Load JSONL records
    all_records = load_jsonl(os.path.join(manifest_dir, "all_instances.jsonl"))
    tr_records = load_jsonl(os.path.join(manifest_dir, "training_ready.jsonl"))
    mr_records = load_jsonl(os.path.join(manifest_dir, "manual_review.jsonl"))
    rej_records = load_jsonl(os.path.join(manifest_dir, "rejected.jsonl"))

    print(f"Loaded {len(all_records)} total instance records from all_instances.jsonl")

    # 1. Check unique source_annotation_ids
    ann_ids = [r.get("source_annotation_id") for r in all_records]
    if len(ann_ids) != len(set(ann_ids)):
        print("ERROR: Duplicate source_annotation_id found in all_instances.jsonl", file=sys.stderr)
        sys.exit(1)
    print("1. Unique source_annotation_ids check: PASSED")

    # 2. Decision files consistency check
    if len(tr_records) + len(mr_records) + len(rej_records) != len(all_records):
        print("ERROR: Sum of decision file records does not equal total all_instances records.", file=sys.stderr)
        sys.exit(1)

    tr_ids = {r["source_annotation_id"] for r in tr_records}
    mr_ids = {r["source_annotation_id"] for r in mr_records}
    rej_ids = {r["source_annotation_id"] for r in rej_records}

    if (tr_ids & mr_ids) or (tr_ids & rej_ids) or (mr_ids & rej_ids):
        print("ERROR: Overlapping annotation IDs found across decision JSONL files.", file=sys.stderr)
        sys.exit(1)

    if (tr_ids | mr_ids | rej_ids) != set(ann_ids):
        print("ERROR: Decision JSONL files IDs set does not equal all_instances IDs set.", file=sys.stderr)
        sys.exit(1)
    print("2. Decision JSONL files partition consistency: PASSED")

    # 3. Validate individual record structure and rules
    allowed_decisions = {"training_ready", "manual_review", "rejected"}
    allowed_splits = {"train", "val", "test"}

    image_to_splits = {}

    for r in all_records:
        dec = r.get("decision")
        sp = r.get("split")
        bbox = r.get("bbox")
        img_id = r.get("source_image_id")
        labels = r.get("labels", {})

        if dec not in allowed_decisions:
            print(f"ERROR: Invalid decision '{dec}' in record {r.get('source_annotation_id')}", file=sys.stderr)
            sys.exit(1)

        if sp not in allowed_splits:
            print(f"ERROR: Invalid split '{sp}' in record {r.get('source_annotation_id')}", file=sys.stderr)
            sys.exit(1)

        # Track image split assignment for leakage check
        if img_id not in image_to_splits:
            image_to_splits[img_id] = set()
        image_to_splits[img_id].add(sp)

        # Validate bbox
        if dec != "rejected":
            if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
                print(f"ERROR: Invalid bbox format in record {r.get('source_annotation_id')}", file=sys.stderr)
                sys.exit(1)
            x, y, w, h = bbox
            if w <= 0 or h <= 0:
                print(f"ERROR: Non-positive bbox dimensions in valid record {r.get('source_annotation_id')}", file=sys.stderr)
                sys.exit(1)

        # Validate training_ready records
        if dec == "training_ready":
            for h in expected_heads:
                head_lbl_info = labels.get(h)
                if not head_lbl_info or not isinstance(head_lbl_info, dict):
                    print(f"ERROR: Head '{h}' missing or invalid in training_ready record {r.get('source_annotation_id')}", file=sys.stderr)
                    sys.exit(1)

                lbl = head_lbl_info.get("label")
                status = head_lbl_info.get("status")

                if lbl not in valid_labels_per_head[h]:
                    print(f"ERROR: Unknown target label '{lbl}' for head '{h}' in record {r.get('source_annotation_id')}", file=sys.stderr)
                    sys.exit(1)

                if status != "direct":
                    print(f"ERROR: Non-direct status '{status}' in training_ready record {r.get('source_annotation_id')}", file=sys.stderr)
                    sys.exit(1)

    print("3. Individual record schema and training_ready rules: PASSED")

    # 4. Zero data-leakage check across splits
    leakage_found = False
    for img_id, splits in image_to_splits.items():
        if len(splits) > 1:
            print(f"ERROR: Data leakage detected! Image ID {img_id} appears in multiple splits: {splits}", file=sys.stderr)
            leakage_found = True

    if leakage_found:
        sys.exit(1)

    print("4. Source image split isolation (zero data-leakage): PASSED")

    # 5. Verify summary.json totals
    dec_counts = summary.get("decision_counts", {})
    if (dec_counts.get("training_ready") != len(tr_records) or
        dec_counts.get("manual_review") != len(mr_records) or
        dec_counts.get("rejected") != len(rej_records)):
        print("ERROR: summary.json decision_counts do not match actual record counts.", file=sys.stderr)
        sys.exit(1)

    if summary.get("relevant_upper_garment_instances") != len(all_records):
        print("ERROR: summary.json relevant_upper_garment_instances does not match all_instances record count.", file=sys.stderr)
        sys.exit(1)

    if not summary.get("source_image_leakage_check", {}).get("passed"):
        print("ERROR: summary.json source_image_leakage_check reports failure.", file=sys.stderr)
        sys.exit(1)

    print("5. summary.json totals & leakage check match actual data: PASSED")
    print("==================================================")
    print("ALL MANIFEST VALIDATIONS PASSED CLEANLY!")
    print("==================================================")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validate Fashionpedia dataset manifest.")
    parser.add_argument("--manifest-dir", required=True, help="Path to manifest directory.")
    parser.add_argument("--classes", required=True, help="Path to classes.json.")

    args = parser.parse_args()
    validate_manifest(args.manifest_dir, args.classes)
