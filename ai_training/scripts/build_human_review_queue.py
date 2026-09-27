#!/usr/bin/env python3
"""
build_human_review_queue.py

Builds a deterministic, duplicate-free targeted human review queue for Milestone M9A.

Queue Targets:
A. Gold validation set (val split): up to 50 per class (blouse, t-shirt, crop-top), max 150
B. Gold test set (test split): up to 50 per class (blouse, t-shirt, crop-top), max 150
C. Training correction set (train split):
   - t-shirt priority: up to 250 records
   - blouse audit: up to 100 records
   - crop-top audit: up to 50 records
   - max 400 records
Total queue maximum: 700 unique source_annotation_id records.

Candidate selection rules:
- Prefer CLIP accepted records, then manual_review records.
- For t-shirt shortage, prioritize records proposed as t-shirt by Fashionpedia evidence even when CLIP placed them in manual_review.
- Exclude confident out-of-scope rejected records.
- Zero duplicate source_annotation_id values.
- Zero image_id leakage across splits.
- Preserve existing train/val/test assignments.
- Record review_purpose and selection_reason on every record.
- Do not set human_verified=true or copy pseudo-label into human_label.
"""

import argparse
import json
import os
import sys
from collections import Counter, defaultdict


def parse_args():
    parser = argparse.ArgumentParser(description="Build targeted human review queue")
    parser.add_argument("--labelling-dir", required=True, help="Directory containing M8 official labelling outputs")
    parser.add_argument("--policy", required=True, help="Path to config/human_review_policy.json")
    parser.add_argument("--output-dir", required=True, help="Directory to store review queue and summary")
    return parser.parse_args()


def load_labelling_data(labelling_dir):
    all_labels_path = os.path.join(labelling_dir, "ai_labels_all.jsonl")
    crop_manifest_path = os.path.join(labelling_dir, "expanded_crop_manifest.jsonl")
    if not os.path.exists(crop_manifest_path):
        crop_manifest_path = os.path.join(labelling_dir, "crop_manifest.jsonl")

    crop_map = {}
    if os.path.exists(crop_manifest_path):
        with open(crop_manifest_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    rec = json.loads(line.strip())
                    crop_map[rec["source_annotation_id"]] = rec

    records = []
    if os.path.exists(all_labels_path):
        with open(all_labels_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    rec = json.loads(line.strip())
                    ann_id = rec.get("source_annotation_id")
                    crop_info = crop_map.get(ann_id, {})
                    rec["crop_sha256"] = rec.get("crop_sha256") or crop_info.get("crop_sha256")
                    records.append(rec)
    print(f"Loaded {len(records)} AI labelling records.")
    return records, crop_map


def select_records_for_pool(candidate_records, target_count, purpose, proposed_class, seen_ann_ids, seen_img_ids, split_by_img):
    selected = []

    # Sort candidates deterministically:
    # 1. Decision priority: accepted > manual_review
    # 2. Fashionpedia candidate garment type match
    # 3. Top-1 confidence descending
    # 4. Source image ID ascending
    # 5. Source annotation ID ascending
    def sort_key(r):
        ev = r.get("source_evidence", {})
        cand_match = 0 if ev.get("candidate_garment_type") == proposed_class else 1
        decision_rank = 0 if r.get("decision") == "accepted" else 1
        conf = r.get("top1_confidence", 0.0)
        return (cand_match, decision_rank, -conf, r.get("source_image_id", 0), r.get("source_annotation_id", 0))

    sorted_candidates = sorted(candidate_records, key=sort_key)

    for r in sorted_candidates:
        if len(selected) >= target_count:
            break
        ann_id = r["source_annotation_id"]
        img_id = r["source_image_id"]
        split = r.get("split", "train")

        if ann_id in seen_ann_ids:
            continue

        # Check split leakage per image ID
        if img_id in split_by_img and split_by_img[img_id] != split:
            continue

        # Build queue item
        item = {
            "source_annotation_id": ann_id,
            "source_image_id": img_id,
            "split": split,
            "crop_path": r.get("crop_path"),
            "crop_sha256": r.get("crop_sha256"),
            "proposed_class": proposed_class,
            "review_purpose": purpose,
            "selection_reason": f"Selected for {purpose} ({proposed_class} proposed via {r.get('decision')})",
            "previous_pseudo_label": r.get("predicted_garment_type") or r.get("top1_label"),
            "top1_confidence": r.get("top1_confidence"),
            "margin": r.get("margin"),
            "prompt_agreement": r.get("prompt_agreement"),
            "decision": r.get("decision"),
            "fashionpedia_evidence": r.get("source_evidence", {}),
            "human_label": None,
            "human_verified": False,
        }

        selected.append(item)
        seen_ann_ids.add(ann_id)
        seen_img_ids.add(img_id)
        split_by_img[img_id] = split

    return selected


def main():
    args = parse_args()

    with open(args.policy, "r", encoding="utf-8") as f:
        policy = json.load(f)

    max_queue_total = policy.get("max_queue_total", 700)
    queue_targets = policy.get("queue_targets", {})

    records, crop_map = load_labelling_data(args.labelling_dir)

    # Filter out failed records and out-of-scope rejected records
    usable_records = [r for r in records if r.get("decision") in ("accepted", "manual_review")]
    print(f"Total usable candidates (accepted + manual_review): {len(usable_records)}")

    # Index candidates by split and proposed class
    records_by_split_and_class = defaultdict(lambda: defaultdict(list))
    for r in usable_records:
        split = r.get("split", "train")
        # Proposed class considers top1_label or candidate_garment_type
        top1 = r.get("predicted_garment_type") or r.get("top1_label")
        ev_class = r.get("source_evidence", {}).get("candidate_garment_type")

        # Add to top1 class pool
        if top1 in ("blouse", "t-shirt", "crop-top"):
            records_by_split_and_class[split][top1].append(r)

        # If Fashionpedia evidence proposed t-shirt/blouse/crop-top but CLIP put it in manual_review, also include in ev_class pool
        if ev_class in ("blouse", "t-shirt", "crop-top") and ev_class != top1:
            records_by_split_and_class[split][ev_class].append(r)

    seen_ann_ids = set()
    seen_img_ids = set()
    split_by_img = {}
    queue_records = []

    # Section A: Val Gold Set (max 150, 50 per class)
    val_targets = queue_targets.get("val_gold_set", {})
    val_per_class = val_targets.get("per_class_target", 50)
    for c in ["blouse", "t-shirt", "crop-top"]:
        pool = records_by_split_and_class["val"][c]
        sel = select_records_for_pool(pool, val_per_class, "val_gold_set", c, seen_ann_ids, seen_img_ids, split_by_img)
        queue_records.extend(sel)
        print(f"Selected {len(sel)} records for val_gold_set ({c}).")

    # Section B: Test Gold Set (max 150, 50 per class)
    test_targets = queue_targets.get("test_gold_set", {})
    test_per_class = test_targets.get("per_class_target", 50)
    for c in ["blouse", "t-shirt", "crop-top"]:
        pool = records_by_split_and_class["test"][c]
        sel = select_records_for_pool(pool, test_per_class, "test_gold_set", c, seen_ann_ids, seen_img_ids, split_by_img)
        queue_records.extend(sel)
        print(f"Selected {len(sel)} records for test_gold_set ({c}).")

    # Section C: Train Correction Set (t-shirt priority 250, blouse 100, crop-top 50)
    train_targets = queue_targets.get("train_correction_set", {}).get("class_targets", {})

    # 1. T-shirt Priority (up to 250)
    tshirt_target = train_targets.get("t-shirt", 250)
    pool_tshirt = records_by_split_and_class["train"]["t-shirt"]
    sel_tshirt = select_records_for_pool(pool_tshirt, tshirt_target, "train_tshirt_priority", "t-shirt", seen_ann_ids, seen_img_ids, split_by_img)
    queue_records.extend(sel_tshirt)
    print(f"Selected {len(sel_tshirt)} records for train_tshirt_priority.")

    # 2. Blouse Audit (up to 100)
    blouse_target = train_targets.get("blouse", 100)
    pool_blouse = records_by_split_and_class["train"]["blouse"]
    sel_blouse = select_records_for_pool(pool_blouse, blouse_target, "train_blouse_audit", "blouse", seen_ann_ids, seen_img_ids, split_by_img)
    queue_records.extend(sel_blouse)
    print(f"Selected {len(sel_blouse)} records for train_blouse_audit.")

    # 3. Crop-top Audit (up to 50)
    croptop_target = train_targets.get("crop-top", 50)
    pool_croptop = records_by_split_and_class["train"]["crop-top"]
    sel_croptop = select_records_for_pool(pool_croptop, croptop_target, "train_croptop_audit", "crop-top", seen_ann_ids, seen_img_ids, split_by_img)
    queue_records.extend(sel_croptop)
    print(f"Selected {len(sel_croptop)} records for train_croptop_audit.")

    # Assign queue rank
    for rank, item in enumerate(queue_records, 1):
        item["queue_rank"] = rank

    if len(queue_records) > max_queue_total:
        print(f"Trimming queue from {len(queue_records)} to max_queue_total={max_queue_total}...")
        queue_records = queue_records[:max_queue_total]

    os.makedirs(args.output_dir, exist_ok=True)
    queue_path = os.path.join(args.output_dir, "review_queue.jsonl")
    summary_path = os.path.join(args.output_dir, "review_queue_summary.json")
    decisions_path = os.path.join(args.output_dir, "human_decisions.jsonl")

    # Write review_queue.jsonl
    print(f"Writing review queue ({len(queue_records)} records) to {queue_path}...")
    with open(queue_path, "w", encoding="utf-8") as f:
        for item in queue_records:
            f.write(json.dumps(item) + "\n")

    # Create empty human_decisions.jsonl if it doesn't exist
    if not os.path.exists(decisions_path):
        print(f"Creating empty human decisions file at {decisions_path}...")
        with open(decisions_path, "w", encoding="utf-8") as f:
            pass
    else:
        print(f"Preserving existing human decisions file at {decisions_path}.")

    # Summary statistics
    counts_by_purpose = Counter()
    counts_by_split = Counter()
    counts_by_proposed_class = Counter()
    counts_by_purpose_and_class = defaultdict(Counter)

    for item in queue_records:
        purp = item["review_purpose"]
        split = item["split"]
        p_cls = item["proposed_class"]
        counts_by_purpose[purp] += 1
        counts_by_split[split] += 1
        counts_by_proposed_class[p_cls] += 1
        counts_by_purpose_and_class[purp][p_cls] += 1

    summary = {
        "total_queue_records": len(queue_records),
        "unique_annotation_ids_count": len(seen_ann_ids),
        "unique_image_ids_count": len(seen_img_ids),
        "max_queue_total": max_queue_total,
        "counts_by_purpose": dict(counts_by_purpose),
        "counts_by_split": dict(counts_by_split),
        "counts_by_proposed_class": dict(counts_by_proposed_class),
        "counts_by_purpose_and_class": {k: dict(v) for k, v in counts_by_purpose_and_class.items()},
    }

    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"Wrote queue summary to {summary_path}.")
    print(f"Build complete: {len(queue_records)} total review queue records.")


if __name__ == "__main__":
    main()
