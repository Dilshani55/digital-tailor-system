#!/usr/bin/env python3
"""
select_labelling_candidates.py

Selects a deterministic, balanced candidate subset from Fashionpedia spatial manifest
and raw metadata for AI-assisted garment labelling (Milestone AI-6B).

Target classes:
- blouse (Fashionpedia Cat 0 shirt, blouse without Attr 8 crop)
- t-shirt (Fashionpedia Cat 1 top, t-shirt, sweatshirt with Attr 0 classic / Attr 4 ringer, without Attr 8 crop)
- crop-top (Fashionpedia Cat 0 or 1 with exact Attr 8 crop)

Excludes jackets, pants, dresses, coats, jumpsuits, and other out-of-scope categories.
Preserves existing project splits (train/val/test).
Outputs candidate_queue.jsonl and candidate_summary.json.
"""

import argparse
import json
import os
import sys
from collections import defaultdict, Counter


def parse_args():
    parser = argparse.ArgumentParser(description="Select candidate subset for AI-assisted labelling")
    parser.add_argument("--spatial-manifest", required=True, help="Path to all_instances_spatial.jsonl")
    parser.add_argument("--annotations", required=True, help="Path to raw instances_attributes_train2020.json")
    parser.add_argument("--classes", required=True, help="Path to config/classes.json")
    parser.add_argument("--config", required=True, help="Path to config/ai_assisted_labelling.json")
    parser.add_argument("--output-dir", required=True, help="Directory to output candidate queue and summary")
    return parser.parse_args()


def load_raw_image_metadata(annotations_path):
    print(f"Loading raw annotations metadata from {annotations_path}...")
    with open(annotations_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    image_meta = {}
    for img in data.get("images", []):
        img_id = img.get("id")
        if img_id is not None:
            image_meta[img_id] = {
                "file_name": img.get("file_name"),
                "original_url": img.get("original_url"),
                "width": img.get("width"),
                "height": img.get("height"),
            }
    print(f"Loaded metadata for {len(image_meta)} raw images.")
    return image_meta


def compute_selection_score(record):
    """
    Computes a deterministic selection score prioritizing:
    - Direct head statuses
    - Direct/attached neckline & sleeve parts
    - Usable multi-head information
    """
    score = 0
    labels = record.get("labels", {})
    for head, head_data in labels.items():
        if isinstance(head_data, dict):
            status = head_data.get("status")
            if status == "direct":
                score += 10
            elif status == "candidate_mapping":
                score += 4
            elif head_data.get("label") is not None:
                score += 2

    # Bonus for attached parts count
    attached_count = record.get("attached_parts_count", 0)
    score += min(attached_count * 2, 6)

    # Bonus for non-empty attribute information
    attrs = record.get("fashionpedia_attribute_ids", [])
    score += min(len(attrs), 5)

    return score


def determine_candidate_class(cat_id, attrs):
    """
    Determines proposed garment class and reason based on category and attribute rules.
    Crop-top (Attr 8) has precedence over blouse and t-shirt.
    """
    attrs_set = set(attrs)
    # Crop-top precedence rule
    if cat_id in (0, 1) and 8 in attrs_set:
        return "crop-top", f"Fashionpedia Cat {cat_id} with Attr 8 crop (top)"
    
    # T-shirt rule: Cat 1 with Attr 0 (classic) or Attr 4 (ringer)
    if cat_id == 1 and (0 in attrs_set or 4 in attrs_set):
        return "t-shirt", f"Fashionpedia Cat 1 with Attr {sorted(attrs_set.intersection({0, 4}))} t-shirt"

    # Blouse rule: Cat 0 shirt, blouse
    if cat_id == 0:
        return "blouse", "Fashionpedia Cat 0 shirt, blouse"

    return None, None


def main():
    args = parse_args()

    # Load configs
    with open(args.classes, "r", encoding="utf-8") as f:
        classes_config = json.load(f)

    with open(args.config, "r", encoding="utf-8") as f:
        labelling_config = json.load(f)

    target_classes = labelling_config.get("target_classes", ["blouse", "t-shirt", "crop-top"])
    per_class_target = labelling_config.get("per_class_candidate_target", 150)
    max_download_target = labelling_config.get("max_download_target", 450)

    # Load raw image metadata for original_url lookup
    image_meta = load_raw_image_metadata(args.annotations)

    print(f"Reading spatial manifest from {args.spatial_manifest}...")
    candidates_by_class = defaultdict(list)
    seen_annotation_ids = set()

    with open(args.spatial_manifest, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)

            ann_id = rec.get("source_annotation_id")
            if ann_id in seen_annotation_ids:
                continue

            cat_id = rec.get("fashionpedia_category_id")
            attrs = rec.get("fashionpedia_attribute_ids", [])

            candidate_cls, reason = determine_candidate_class(cat_id, attrs)
            if candidate_cls is None or candidate_cls not in target_classes:
                continue

            img_id = rec.get("source_image_id")
            raw_meta = image_meta.get(img_id, {})
            original_url = raw_meta.get("original_url") or rec.get("source_url")
            file_name = raw_meta.get("file_name") or rec.get("source_file_name")

            score = compute_selection_score(rec)

            candidate_record = {
                "source_image_id": img_id,
                "source_annotation_id": ann_id,
                "file_name": file_name,
                "original_url": original_url,
                "bbox": rec.get("bbox"),
                "fashionpedia_category_id": cat_id,
                "fashionpedia_category_name": rec.get("fashionpedia_category_name"),
                "fashionpedia_attribute_ids": attrs,
                "fashionpedia_attribute_names": rec.get("fashionpedia_attribute_names", []),
                "labels": rec.get("labels", {}),
                "candidate_garment_type": candidate_cls,
                "candidate_garment_reason": reason,
                "split": rec.get("split", "train"),
                "selection_score": score,
            }

            candidates_by_class[candidate_cls].append(candidate_record)
            seen_annotation_ids.add(ann_id)

    print(f"Candidate pools collected:")
    for cls in target_classes:
        print(f"  - {cls}: {len(candidates_by_class[cls])} records")

    # Deterministic selection per class with image diversity heuristic
    final_queue = []
    selected_image_ids = set()

    for cls in target_classes:
        pool = candidates_by_class[cls]
        # Sort by score descending, then image_id ascending, then annotation_id ascending
        pool.sort(key=lambda x: (-x["selection_score"], x["source_image_id"], x["source_annotation_id"]))

        # First pass: select records with unique images
        selected_for_cls = []
        remaining_in_pool = []

        for item in pool:
            img_id = item["source_image_id"]
            if img_id not in selected_image_ids and len(selected_for_cls) < per_class_target:
                selected_for_cls.append(item)
                selected_image_ids.add(img_id)
            else:
                remaining_in_pool.append(item)

        # Second pass if target not reached: select remaining top scoring items
        if len(selected_for_cls) < per_class_target:
            for item in remaining_in_pool:
                if len(selected_for_cls) >= per_class_target:
                    break
                selected_for_cls.append(item)
                selected_image_ids.add(item["source_image_id"])

        print(f"Selected {len(selected_for_cls)} candidates for class '{cls}'.")
        final_queue.extend(selected_for_cls)

    # Re-sort final queue deterministically by candidate class order, then selection score
    class_order = {cls: i for i, cls in enumerate(target_classes)}
    final_queue.sort(key=lambda x: (class_order[x["candidate_garment_type"]], -x["selection_score"], x["source_image_id"], x["source_annotation_id"]))

    # Assign selection rank
    for rank, item in enumerate(final_queue, 1):
        item["selection_rank"] = rank

    # Enforce maximum target limit
    if len(final_queue) > max_download_target:
        final_queue = final_queue[:max_download_target]

    os.makedirs(args.output_dir, exist_ok=True)
    queue_path = os.path.join(args.output_dir, "candidate_queue.jsonl")
    summary_path = os.path.join(args.output_dir, "candidate_summary.json")

    print(f"Writing candidate queue ({len(final_queue)} records) to {queue_path}...")
    with open(queue_path, "w", encoding="utf-8") as f:
        for item in final_queue:
            f.write(json.dumps(item) + "\n")

    # Compute summary statistics
    counts_by_class = Counter()
    counts_by_split = Counter()
    counts_by_class_and_split = defaultdict(Counter)
    unique_images = set()

    for item in final_queue:
        c_cls = item["candidate_garment_type"]
        split = item["split"]
        counts_by_class[c_cls] += 1
        counts_by_split[split] += 1
        counts_by_class_and_split[c_cls][split] += 1
        unique_images.add(item["source_image_id"])

    summary = {
        "total_candidates": len(final_queue),
        "unique_images_count": len(unique_images),
        "target_classes": target_classes,
        "per_class_candidate_target": per_class_target,
        "max_download_target": max_download_target,
        "counts_by_class": dict(counts_by_class),
        "counts_by_split": dict(counts_by_split),
        "counts_by_class_and_split": {k: dict(v) for k, v in counts_by_class_and_split.items()},
    }

    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"Wrote candidate summary to {summary_path}.")
    print("Candidate selection completed successfully.")


if __name__ == "__main__":
    main()
