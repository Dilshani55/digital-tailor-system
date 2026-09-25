#!/usr/bin/env python3
"""
build_fashionpedia_manifest.py

Parses Fashionpedia instance annotations and builds deterministic, auditable dataset manifests
for the Digital Tailor System four-head YOLOv8 model.

Usage:
    python ai_training/scripts/build_fashionpedia_manifest.py \
      --annotations ai_training/data/raw/fashionpedia/instances_attributes_val2020.json \
      --classes ai_training/config/classes.json \
      --mapping ai_training/config/fashionpedia_mapping.json \
      --pipeline-config ai_training/config/dataset_pipeline.json \
      --output-dir ai_training/data/processed/fashionpedia_manifest
"""

import sys
import os
import json
import argparse
import hashlib
from datetime import datetime, timezone


def compute_sha256(filepath):
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def assign_split(image_id, seed, ratios):
    key = f"{image_id}_{seed}".encode("utf-8")
    hash_hex = hashlib.sha256(key).hexdigest()
    # Normalize 32-bit uint hash value to [0.0, 1.0)
    val = int(hash_hex[:8], 16) / 4294967296.0

    train_r = ratios.get("train", 0.70)
    val_r = ratios.get("val", 0.15)

    if val < train_r:
        return "train"
    elif val < (train_r + val_r):
        return "val"
    else:
        return "test"


def validate_bbox(bbox, min_w, min_h):
    if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
        return False
    try:
        x, y, w, h = float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])
        if x < 0 or y < 0 or w < min_w or h < min_h:
            return False
        return True
    except (ValueError, TypeError):
        return False


def build_manifest(annotations_path, classes_path, mapping_path, pipeline_config_path, output_dir):
    # Verify input files
    for p in [annotations_path, classes_path, mapping_path, pipeline_config_path]:
        if not os.path.exists(p):
            print(f"ERROR: File not found: {p}", file=sys.stderr)
            sys.exit(1)

    # Compute checksums
    input_sha256 = {
        "annotations": compute_sha256(annotations_path),
        "classes": compute_sha256(classes_path),
        "mapping": compute_sha256(mapping_path),
        "pipeline_config": compute_sha256(pipeline_config_path),
    }

    # Load JSON files
    try:
        with open(annotations_path, "r", encoding="utf-8") as f:
            ann_data = json.load(f)
        with open(classes_path, "r", encoding="utf-8") as f:
            classes_data = json.load(f)
        with open(mapping_path, "r", encoding="utf-8") as f:
            mapping_data = json.load(f)
        with open(pipeline_config_path, "r", encoding="utf-8") as f:
            pipeline_config = json.load(f)
    except Exception as e:
        print(f"ERROR: Failed to parse input JSON files: {e}", file=sys.stderr)
        sys.exit(1)

    # Pipeline config parameters
    seed = pipeline_config.get("random_seed", 42)
    split_ratios = pipeline_config.get("split_ratios", {"train": 0.70, "val": 0.15, "test": 0.15})
    accepted_cat_ids = set(pipeline_config.get("accepted_category_ids", [0, 1, 2, 3, 4, 5]))
    min_dims = pipeline_config.get("minimum_crop_dimensions", {"min_width": 10, "min_height": 10})
    min_w = min_dims.get("min_width", 10.0)
    min_h = min_dims.get("min_height", 10.0)

    # Index metadata
    images_dict = {img["id"]: img for img in ann_data.get("images", [])}
    categories_dict = {c["id"]: c["name"] for c in ann_data.get("categories", [])}
    attributes_dict = {a["id"]: a["name"] for a in ann_data.get("attributes", [])}

    # Build mapping lookups per head
    head_mappings = mapping_data.get("outputs", {})

    all_records = []
    reason_code_counts = {}
    target_label_counts_per_head = {h: {} for h in classes_data["outputs"]}
    missing_head_counts = {h: 0 for h in classes_data["outputs"]}
    conflict_counts = {h: 0 for h in classes_data["outputs"]}
    image_splits = {}

    relevant_instances_count = 0

    for ann in ann_data.get("annotations", []):
        cat_id = ann.get("category_id")
        if cat_id not in accepted_cat_ids:
            continue

        relevant_instances_count += 1

        ann_id = ann.get("id")
        img_id = ann.get("image_id")
        bbox = ann.get("bbox")
        attr_ids = ann.get("attribute_ids", [])
        attr_ids_set = set(attr_ids)

        img_info = images_dict.get(img_id, {})
        file_name = img_info.get("file_name", f"{img_id:09d}.jpg")
        source_url = img_info.get("coco_url") or img_info.get("url")

        # Assign split deterministically at image_id level
        if img_id not in image_splits:
            image_splits[img_id] = assign_split(img_id, seed, split_ratios)
        split = image_splits[img_id]

        cat_name = categories_dict.get(cat_id, "unknown")
        attr_names = [attributes_dict.get(aid, f"unknown_{aid}") for aid in attr_ids]

        reason_codes = []
        labels_by_head = {}

        # Check bbox validity
        bbox_valid = validate_bbox(bbox, min_w, min_h)
        if not bbox_valid:
            reason_codes.append("INVALID_BBOX")

        # Evaluate each head
        head_has_missing = False
        head_has_conflict = False

        for head_name in classes_data["outputs"]:
            head_items = head_mappings.get(head_name, [])
            matched_candidates = []

            # Head evaluation rules
            if head_name == "garment_type":
                # Crop top precedence rule: Attribute ID 8 'crop (top)' on eligible top categories (0 or 1)
                if 8 in attr_ids_set and cat_id in (0, 1):
                    matched_candidates.append({"label": "crop-top", "status": "direct", "source": "attribute_8"})
                else:
                    if cat_id == 0:
                        matched_candidates.append({"label": "blouse", "status": "candidate_mapping", "source": "category_0"})
                    elif cat_id == 1:
                        matched_candidates.append({"label": "t-shirt", "status": "candidate_mapping", "source": "category_1"})

            elif head_name == "neckline_type":
                for item in head_items:
                    target_lbl = item["target_label"]
                    st = item["status"]
                    for ev in item.get("source_evidence", []):
                        stype = ev.get("source_type")
                        sid = ev.get("source_id")
                        if stype == "attribute" and sid in attr_ids_set:
                            matched_candidates.append({"label": target_lbl, "status": st, "source": f"attribute_{sid}"})
                            break
                        elif stype == "category" and sid == cat_id:
                            matched_candidates.append({"label": target_lbl, "status": st, "source": f"category_{sid}"})
                            break

            elif head_name == "sleeve_length":
                for item in head_items:
                    target_lbl = item["target_label"]
                    st = item["status"]
                    for ev in item.get("source_evidence", []):
                        stype = ev.get("source_type")
                        sid = ev.get("source_id")
                        if stype == "attribute" and sid in attr_ids_set:
                            matched_candidates.append({"label": target_lbl, "status": st, "source": f"attribute_{sid}"})
                            break

            elif head_name == "sleeve_style":
                # Derived rule: sleeve_style = none if sleeveless (Attr 156) is present
                if 156 in attr_ids_set:
                    matched_candidates.append({"label": "none", "status": "candidate_mapping", "source": "derived_sleeveless"})
                
                for item in head_items:
                    target_lbl = item["target_label"]
                    if target_lbl == "none":
                        continue
                    st = item["status"]
                    for ev in item.get("source_evidence", []):
                        stype = ev.get("source_type")
                        sid = ev.get("source_id")
                        if stype == "attribute" and sid in attr_ids_set:
                            matched_candidates.append({"label": target_lbl, "status": st, "source": f"attribute_{sid}"})
                            break

            # Process candidates for head
            if len(matched_candidates) == 0:
                missing_head_counts[head_name] += 1
                head_has_missing = True
                reason_codes.append(f"MISSING_HEAD_{head_name.upper()}")
                labels_by_head[head_name] = None
            elif len(matched_candidates) > 1:
                # Deduplicate if same label matched multiple evidence sources
                unique_labels = {c["label"]: c for c in matched_candidates}
                if len(unique_labels) == 1:
                    lbl_info = list(unique_labels.values())[0]
                    labels_by_head[head_name] = {"label": lbl_info["label"], "status": lbl_info["status"]}
                    lbl = lbl_info["label"]
                    target_label_counts_per_head[head_name][lbl] = target_label_counts_per_head[head_name].get(lbl, 0) + 1
                else:
                    conflict_counts[head_name] += 1
                    head_has_conflict = True
                    reason_codes.append(f"CONFLICT_HEAD_{head_name.upper()}")
                    labels_by_head[head_name] = None
            else:
                lbl_info = matched_candidates[0]
                labels_by_head[head_name] = {"label": lbl_info["label"], "status": lbl_info["status"]}
                lbl = lbl_info["label"]
                target_label_counts_per_head[head_name][lbl] = target_label_counts_per_head[head_name].get(lbl, 0) + 1

        # Determine decision
        if not bbox_valid:
            decision = "rejected"
        elif head_has_conflict or head_has_missing:
            decision = "manual_review"
        else:
            # Check if all assigned labels are 'direct'
            statuses = [labels_by_head[h]["status"] for h in classes_data["outputs"]]
            if all(st == "direct" for st in statuses):
                decision = "training_ready"
                reason_codes.append("TRAINING_READY_DIRECT_LABELS")
            else:
                decision = "manual_review"
                reason_codes.append("MANUAL_REVIEW_CANDIDATE_MAPPING")

        for rcode in reason_codes:
            reason_code_counts[rcode] = reason_code_counts.get(rcode, 0) + 1

        record = {
            "source_dataset": "Fashionpedia",
            "source_image_id": img_id,
            "source_annotation_id": ann_id,
            "source_file_name": file_name,
            "source_url": source_url,
            "bbox": bbox,
            "fashionpedia_category_id": cat_id,
            "fashionpedia_category_name": cat_name,
            "fashionpedia_attribute_ids": attr_ids,
            "fashionpedia_attribute_names": attr_names,
            "split": split,
            "decision": decision,
            "reason_codes": reason_codes,
            "labels": labels_by_head,
        }
        all_records.append(record)

    # Deterministic sorting by source_annotation_id
    all_records.sort(key=lambda x: x["source_annotation_id"])

    training_ready_records = [r for r in all_records if r["decision"] == "training_ready"]
    manual_review_records = [r for r in all_records if r["decision"] == "manual_review"]
    rejected_records = [r for r in all_records if r["decision"] == "rejected"]

    # Compute split counts
    split_counts = {"train": 0, "val": 0, "test": 0}
    for r in all_records:
        split_counts[r["split"]] += 1

    # Source-image leakage check
    image_to_splits = {}
    for r in all_records:
        img_id = r["source_image_id"]
        sp = r["split"]
        if img_id not in image_to_splits:
            image_to_splits[img_id] = set()
        image_to_splits[img_id].add(sp)

    cross_split_images = [img_id for img_id, splits in image_to_splits.items() if len(splits) > 1]
    leakage_passed = len(cross_split_images) == 0

    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)

    # Write JSONL files
    def write_jsonl(records, filename):
        filepath = os.path.join(output_dir, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            for r in records:
                f.write(json.dumps(r) + "\n")

    write_jsonl(all_records, "all_instances.jsonl")
    write_jsonl(training_ready_records, "training_ready.jsonl")
    write_jsonl(manual_review_records, "manual_review.jsonl")
    write_jsonl(rejected_records, "rejected.jsonl")

    # Build summary.json
    summary = {
        "total_source_images": len(ann_data.get("images", [])),
        "total_source_annotations": len(ann_data.get("annotations", [])),
        "relevant_upper_garment_instances": relevant_instances_count,
        "decision_counts": {
            "training_ready": len(training_ready_records),
            "manual_review": len(manual_review_records),
            "rejected": len(rejected_records),
        },
        "reason_code_counts": reason_code_counts,
        "split_counts": split_counts,
        "target_label_counts_per_head": target_label_counts_per_head,
        "missing_head_counts": missing_head_counts,
        "conflict_counts": conflict_counts,
        "source_image_leakage_check": {
            "passed": leakage_passed,
            "cross_split_image_count": len(cross_split_images),
        },
        "input_sha256": input_sha256,
        "generation_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "pipeline_schema_version": pipeline_config.get("manifest_schema_version", "1.0.0"),
    }

    summary_filepath = os.path.join(output_dir, "summary.json")
    with open(summary_filepath, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print("==================================================")
    print("FASHIONPEDIA MANIFEST BUILD COMPLETED")
    print("==================================================")
    print(f"Output Directory: {os.path.abspath(output_dir)}")
    print(f"Total Relevant Upper-Garment Instances: {relevant_instances_count}")
    print(f"  - Training Ready: {len(training_ready_records)}")
    print(f"  - Manual Review:  {len(manual_review_records)}")
    print(f"  - Rejected:       {len(rejected_records)}")
    print(f"Leakage Check Passed: {leakage_passed}")
    print("==================================================")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build Fashionpedia dataset manifest.")
    parser.add_argument("--annotations", required=True, help="Path to Fashionpedia annotation JSON.")
    parser.add_argument("--classes", required=True, help="Path to classes.json.")
    parser.add_argument("--mapping", required=True, help="Path to fashionpedia_mapping.json.")
    parser.add_argument("--pipeline-config", required=True, help="Path to dataset_pipeline.json.")
    parser.add_argument("--output-dir", required=True, help="Output directory for manifests.")

    args = parser.parse_args()
    build_manifest(args.annotations, args.classes, args.mapping, args.pipeline_config, args.output_dir)
