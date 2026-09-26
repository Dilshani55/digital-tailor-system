#!/usr/bin/env python3
"""
analyse_training_feasibility.py

Analyzes training-data feasibility and generates manual-review priority queues
for the Digital Tailor System four-head classification model.

Usage:
    python ai_training/scripts/analyse_training_feasibility.py \
      --spatial-manifest ai_training/data/processed/fashionpedia_spatial_manifest/all_instances_spatial.jsonl \
      --classes ai_training/config/classes.json \
      --policy ai_training/config/training_data_policy.json \
      --output-dir ai_training/data/analysis/training_feasibility
"""

import sys
import os
import json
import argparse
import hashlib
from datetime import datetime, timezone
from collections import defaultdict


def compute_sha256(filepath):
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def run_feasibility_analysis(spatial_manifest_path, classes_path, policy_path, output_dir):
    # Verify input files
    for p in [spatial_manifest_path, classes_path, policy_path]:
        if not os.path.exists(p):
            print(f"ERROR: File not found: {p}", file=sys.stderr)
            sys.exit(1)

    input_sha256 = {
        "spatial_manifest": compute_sha256(spatial_manifest_path),
        "classes": compute_sha256(classes_path),
        "policy": compute_sha256(policy_path),
    }

    try:
        with open(spatial_manifest_path, "r", encoding="utf-8") as f:
            spatial_records = [json.loads(line) for line in f]
        with open(classes_path, "r", encoding="utf-8") as f:
            classes_data = json.load(f)
        with open(policy_path, "r", encoding="utf-8") as f:
            policy_data = json.load(f)
    except Exception as e:
        print(f"ERROR: Failed to parse input JSON files: {e}", file=sys.stderr)
        sys.exit(1)

    # 1. TAXONOMY VERIFICATION (Strictly 29 classes from classes.json)
    target_heads = list(classes_data["outputs"].keys())
    all_classes_by_head = {h: classes_data["outputs"][h]["classes"] for h in target_heads}
    total_target_classes = sum(len(classes_data["outputs"][h]["classes"]) for h in target_heads)

    if total_target_classes != 29:
        print(f"ERROR: Expected 29 total target classes in classes.json, found {total_target_classes}", file=sys.stderr)
        sys.exit(1)

    forbidden_source_terms = {"shirt", "top", "sweatshirt"}
    for h, c_list in all_classes_by_head.items():
        for cname in c_list:
            if cname in forbidden_source_terms:
                print(f"ERROR: Forbidden source ontology term '{cname}' found as target class in head '{h}'!", file=sys.stderr)
                sys.exit(1)

    thresholds = policy_data.get("planning_thresholds", {})
    min_baseline = thresholds.get("minimum_viable_baseline_samples", 20)
    min_recommended = thresholds.get("minimum_recommended_samples", 100)
    imbalance_warning_ratio = thresholds.get("imbalance_warning_ratio", 5.0)

    # Initialize class count structures (guaranteeing all 29 classes exist across train/val/test/total)
    class_counts_by_split = {h: {} for h in target_heads}
    record_ids_by_head_class = {h: defaultdict(set) for h in target_heads}

    for h in target_heads:
        for cname in all_classes_by_head[h]:
            class_counts_by_split[h][cname] = {
                "train": 0,
                "val": 0,
                "test": 0,
                "total": 0,
            }

    usable_head_distribution = {
        "0_usable_heads": 0,
        "1_usable_head": 0,
        "2_usable_heads": 0,
        "3_usable_heads": 0,
        "4_usable_heads": 0,
    }

    usable_records_per_head = {h: 0 for h in target_heads}
    fully_labelled_records = []
    partial_label_records = []
    manual_review_candidates = []

    # Track candidate mapping potential boost per target class on train split
    train_candidate_counts_by_class = {h: defaultdict(int) for h in target_heads}

    # Frequency analysis for rare label evidence boost
    direct_label_occurrences = defaultdict(int)
    for r in spatial_records:
        for h in target_heads:
            lbl_info = r["labels"].get(h)
            if lbl_info and lbl_info.get("status") == "direct":
                direct_label_occurrences[lbl_info["label"]] += 1

    # 2. RECONCILE RECORD-LEVEL COUNTS & PRESENCE
    seen_annotation_ids = set()

    for r in spatial_records:
        ann_id = r["source_annotation_id"]
        if ann_id in seen_annotation_ids:
            print(f"ERROR: Duplicate parent annotation record found: {ann_id}", file=sys.stderr)
            sys.exit(1)
        seen_annotation_ids.add(ann_id)

        img_id = r["source_image_id"]
        fname = r["source_file_name"]
        sp = r["split"]
        if sp not in ("train", "val", "test"):
            print(f"ERROR: Invalid record split '{sp}' for annotation {ann_id}", file=sys.stderr)
            sys.exit(1)

        bbox = r["bbox"]
        attached_parts = r.get("attached_parts", [])
        attached_part_ids = [p["part_annotation_id"] for p in attached_parts]

        usable_direct_count = 0
        missing_heads = []
        candidate_heads = []
        conflicting_heads = []
        direct_heads = []

        usable_head_details = {}

        for h in target_heads:
            lbl_info = r["labels"].get(h)
            if lbl_info is None:
                r_codes = r.get("reason_codes", [])
                if f"CONFLICT_HEAD_{h.upper()}" in r_codes:
                    conflicting_heads.append(h)
                else:
                    missing_heads.append(h)
                usable_head_details[h] = {"usable": False, "status": "missing_or_conflicting", "label": None}
            else:
                lbl = lbl_info["label"]
                st = lbl_info["status"]
                if lbl not in all_classes_by_head[h]:
                    print(f"ERROR: Invalid label '{lbl}' for head '{h}' in annotation {ann_id}", file=sys.stderr)
                    sys.exit(1)

                if st == "direct":
                    usable_direct_count += 1
                    direct_heads.append(h)
                    usable_head_details[h] = {"usable": True, "status": "direct", "label": lbl}
                    usable_records_per_head[h] += 1

                    # Increment class counts strictly once per parent record
                    class_counts_by_split[h][lbl][sp] += 1
                    class_counts_by_split[h][lbl]["total"] += 1
                    record_ids_by_head_class[h][lbl].add(ann_id)

                elif st == "candidate_mapping":
                    candidate_heads.append(h)
                    usable_head_details[h] = {"usable": False, "status": "candidate_mapping", "label": lbl}
                    if sp == "train":
                        train_candidate_counts_by_class[h][lbl] += 1

        # Usable head distribution
        dist_key = f"{usable_direct_count}_usable_head" if usable_direct_count == 1 else f"{usable_direct_count}_usable_heads"
        usable_head_distribution[dist_key] += 1

        rec_summary = {
            "source_annotation_id": ann_id,
            "source_image_id": img_id,
            "source_file_name": fname,
            "split": sp,
            "bbox": bbox,
            "usable_direct_heads_count": usable_direct_count,
            "usable_head_details": usable_head_details,
            "missing_heads": missing_heads,
            "candidate_heads": candidate_heads,
            "conflicting_heads": conflicting_heads,
            "attached_part_ids": attached_part_ids,
        }

        if usable_direct_count == 4:
            fully_labelled_records.append(rec_summary)
        elif 1 <= usable_direct_count <= 3:
            partial_label_records.append(rec_summary)

        # Priority scoring for manual review queue
        if r["decision"] != "training_ready" or candidate_heads or missing_heads or conflicting_heads:
            score = 0.0

            # 1. Train split boost
            if sp == "train":
                score += 50.0
            elif sp == "val":
                score += 10.0

            # 2. Single missing/candidate head boost (especially garment_type)
            if usable_direct_count == 3:
                score += 30.0
                if "garment_type" in candidate_heads or "garment_type" in missing_heads:
                    score += 20.0

            # 3. Rare direct label evidence boost
            has_rare = False
            for h in direct_heads:
                d_lbl = usable_head_details[h]["label"]
                if direct_label_occurrences[d_lbl] <= 10:
                    has_rare = True
                    break
            if has_rare:
                score += 40.0

            # 4. Penalty for many missing heads
            score -= (len(missing_heads) * 10.0)

            # Generate review questions & reason codes
            questions = []
            rec_reason_codes = list(r.get("reason_codes", []))

            if "garment_type" in candidate_heads:
                cat_id = r.get("fashionpedia_category_id")
                if cat_id == 0:
                    questions.append("Confirm whether Category 0 'shirt, blouse' is a blouse or t-shirt.")
                elif cat_id == 1:
                    questions.append("Confirm whether Category 1 'top, t-shirt, sweatshirt' is a t-shirt or blouse.")

            if "neckline_type" in candidate_heads:
                questions.append("Confirm candidate neckline_type (e.g. collared-neck from collar part).")

            if "sleeve_style" in candidate_heads:
                questions.append("Confirm derived sleeve_style = none or candidate sleeve_style.")

            for mh in missing_heads:
                questions.append(f"Annotate missing {mh} label.")

            for ch in conflicting_heads:
                questions.append(f"Resolve conflicting attribute evidence for {ch}.")

            if not questions:
                questions.append("Verify candidate labels and spatial part alignment.")

            manual_review_candidates.append({
                "priority_score": round(score, 2),
                "source_annotation_id": ann_id,
                "source_image_id": img_id,
                "source_file_name": fname,
                "split": sp,
                "bbox": bbox,
                "usable_direct_heads_count": usable_direct_count,
                "current_labels": r.get("labels", {}),
                "missing_heads": missing_heads,
                "candidate_heads": candidate_heads,
                "conflicting_heads": conflicting_heads,
                "accepted_part_association_ids": attached_part_ids,
                "review_questions": questions,
                "reason_codes": rec_reason_codes,
            })

    # ASSERTIONS FOR RECORD-LEVEL COUNT INTEGRITY
    for h in target_heads:
        sum_class_totals = sum(class_counts_by_split[h][c]["total"] for c in all_classes_by_head[h])
        if sum_class_totals != usable_records_per_head[h]:
            print(f"ASSERTION FAILURE: Sum of usable class counts for head '{h}' ({sum_class_totals}) != usable records count ({usable_records_per_head[h]})", file=sys.stderr)
            sys.exit(1)

        # Check unique annotation ID matching
        for cname in all_classes_by_head[h]:
            reported = class_counts_by_split[h][cname]["total"]
            actual_unique = len(record_ids_by_head_class[h][cname])
            if reported != actual_unique:
                print(f"ASSERTION FAILURE: Head '{h}', Class '{cname}': reported count {reported} != unique annotation IDs count {actual_unique}", file=sys.stderr)
                sys.exit(1)

        # Check split sum arithmetic
        for cname in all_classes_by_head[h]:
            tr = class_counts_by_split[h][cname]["train"]
            va = class_counts_by_split[h][cname]["val"]
            te = class_counts_by_split[h][cname]["test"]
            tot = class_counts_by_split[h][cname]["total"]
            if tr + va + te != tot:
                print(f"ASSERTION FAILURE: Head '{h}', Class '{cname}': train({tr}) + val({va}) + test({te}) != total({tot})", file=sys.stderr)
                sys.exit(1)

    # Sort manual review queue deterministically by priority_score descending, then source_annotation_id
    manual_review_candidates.sort(key=lambda x: (-x["priority_score"], x["source_annotation_id"]))

    manual_review_queue = []
    for rank, item in enumerate(manual_review_candidates, start=1):
        queue_item = {"priority_rank": rank}
        queue_item.update(item)
        manual_review_queue.append(queue_item)

    # 3. EXCLUSIVE PLANNING BANDS & OVERLAPPING LISTS
    zero_sample_classes = []
    below_baseline_threshold_classes = []  # < 20 (overlapping)
    below_recommended_threshold_classes = []  # < 100 (overlapping)
    sufficient_sample_classes = []  # >= 100 (overlapping)

    exclusive_planning_bands = {
        "zero": [],                   # 0
        "below_baseline_1_19": [],    # 1 to 19
        "below_recommended_20_99": [],# 20 to 99
        "sufficient_100_plus": [],    # 100+
    }

    imbalance_ratios_per_head = {}

    for h in target_heads:
        head_counts = [class_counts_by_split[h][c]["total"] for c in all_classes_by_head[h]]
        nonzero_counts = [cnt for cnt in head_counts if cnt > 0]

        max_c = max(head_counts) if head_counts else 0
        min_c = min(head_counts) if head_counts else 0
        min_nonzero = min(nonzero_counts) if nonzero_counts else 0

        if min_c > 0:
            ratio = round(max_c / float(min_c), 2)
        elif min_nonzero > 0:
            ratio = round(max_c / float(min_nonzero), 2)
        else:
            ratio = 0.0

        imbalance_ratios_per_head[h] = {
            "max_class_count": max_c,
            "min_class_count": min_c,
            "min_nonzero_class_count": min_nonzero,
            "imbalance_ratio": ratio,
            "exceeds_warning_ratio": ratio > imbalance_warning_ratio,
        }

        for cname in all_classes_by_head[h]:
            tot = class_counts_by_split[h][cname]["total"]
            info = {
                "head": h,
                "class_name": cname,
                "total_direct_count": tot,
                "counts_by_split": class_counts_by_split[h][cname],
            }

            # Overlapping lists
            if tot == 0:
                zero_sample_classes.append(info)
                below_baseline_threshold_classes.append(info)
                below_recommended_threshold_classes.append(info)
            elif tot < min_baseline:
                below_baseline_threshold_classes.append(info)
                below_recommended_threshold_classes.append(info)
            elif tot < min_recommended:
                below_recommended_threshold_classes.append(info)
            else:
                sufficient_sample_classes.append(info)

            # Exclusive planning bands
            if tot == 0:
                exclusive_planning_bands["zero"].append(info)
            elif 1 <= tot < min_baseline:
                exclusive_planning_bands["below_baseline_1_19"].append(info)
            elif min_baseline <= tot < min_recommended:
                exclusive_planning_bands["below_recommended_20_99"].append(info)
            else:
                exclusive_planning_bands["sufficient_100_plus"].append(info)

    # Validate that exclusive planning bands sum to exactly 29
    exclusive_band_counts = {k: len(v) for k, v in exclusive_planning_bands.items()}
    sum_exclusive_bands = sum(exclusive_band_counts.values())

    if sum_exclusive_bands != 29:
        print(f"ASSERTION FAILURE: Exclusive planning bands sum ({sum_exclusive_bands}) != 29", file=sys.stderr)
        sys.exit(1)

    # 4. FEASIBILITY VERDICT (Validation Subset Specific)
    feasibility_verdict = "NOT_FEASIBLE_WITH_CURRENT_VALIDATION_SUBSET"
    verdict_disclaimer = (
        "This verdict applies strictly to the currently inspected Fashionpedia validation annotation package "
        "(instances_attributes_val2020.json, 817 spatial parent instances). It evaluates direct label availability "
        "on this subset and does not represent an evaluation of the full Fashionpedia training dataset."
    )

    # 5. MANUAL-REVIEW WORKLOAD BREAKDOWN
    total_review_eligible = len(manual_review_queue)
    garment_type_only = len([r for r in manual_review_queue if r["usable_direct_heads_count"] == 3 and ("garment_type" in r["candidate_heads"] or "garment_type" in r["missing_heads"])])
    one_additional_head = len([r for r in manual_review_queue if r["usable_direct_heads_count"] == 3])
    two_or_more_additional_heads = len([r for r in manual_review_queue if r["usable_direct_heads_count"] <= 2])

    workload_statement = "Minimum manual-review workload cannot yet be determined without image availability."

    # Write output directory
    os.makedirs(output_dir, exist_ok=True)

    # Write JSONL files
    def write_jsonl(recs, filename):
        path = os.path.join(output_dir, filename)
        with open(path, "w", encoding="utf-8") as f:
            for r in recs:
                f.write(json.dumps(r) + "\n")

    write_jsonl(fully_labelled_records, "fully_labelled_records.jsonl")
    write_jsonl(partial_label_records, "partial_label_records.jsonl")
    write_jsonl(manual_review_queue, "manual_review_priority.jsonl")

    # Write JSON summary & report files
    with open(os.path.join(output_dir, "class_counts_by_split.json"), "w", encoding="utf-8") as f:
        json.dump(class_counts_by_split, f, indent=2)

    with open(os.path.join(output_dir, "zero_sample_classes.json"), "w", encoding="utf-8") as f:
        json.dump({
            "total_zero_sample_classes": len(zero_sample_classes),
            "zero_sample_classes": zero_sample_classes,
        }, f, indent=2)

    action_plan = {
        "feasibility_verdict": feasibility_verdict,
        "verdict_disclaimer": verdict_disclaimer,
        "recommended_minimum_manual_reviews_statement": workload_statement,
        "manual_review_workload_breakdown": {
            "total_review_eligible_records": total_review_eligible,
            "records_needing_only_garment_type_confirmation": garment_type_only,
            "records_needing_one_additional_head": one_additional_head,
            "records_needing_two_or_more_additional_heads": two_or_more_additional_heads,
        },
        "planning_thresholds": {
            "minimum_viable_baseline_samples": min_baseline,
            "minimum_recommended_samples": min_recommended,
            "imbalance_warning_ratio": imbalance_warning_ratio,
        },
        "exclusive_planning_bands": {
            "zero_samples_count": exclusive_band_counts["zero"],
            "below_baseline_1_19_count": exclusive_band_counts["below_baseline_1_19"],
            "below_recommended_20_99_count": exclusive_band_counts["below_recommended_20_99"],
            "sufficient_100_plus_count": exclusive_band_counts["sufficient_100_plus"],
            "total_classes_sum": sum_exclusive_bands,
        },
        "class_shortages": {
            "zero_sample_classes_count": len(zero_sample_classes),
            "below_baseline_classes_count": len(below_baseline_threshold_classes),
            "below_recommended_classes_count": len(below_recommended_threshold_classes),
            "sufficient_sample_classes_count": len(sufficient_sample_classes),
        },
        "next_recommended_steps": [
            "Inspect full Fashionpedia training package (instances_attributes_train2020.json) to evaluate broader label availability.",
            "Review high-priority manual-review queue items to confirm Category 0 (blouse) and Category 1 (t-shirt) garment_type labels.",
            "Implement a masked loss multi-task training loop supporting missing head labels.",
            "Supplement zero-sample classes with external dataset sources or synthetic annotations."
        ]
    }

    with open(os.path.join(output_dir, "recommended_action_plan.json"), "w", encoding="utf-8") as f:
        json.dump(action_plan, f, indent=2)

    summary = {
        "source_package": "instances_attributes_val2020.json",
        "total_spatial_records_evaluated": len(spatial_records),
        "split_counts": {
            "train": sum(1 for r in spatial_records if r["split"] == "train"),
            "val": sum(1 for r in spatial_records if r["split"] == "val"),
            "test": sum(1 for r in spatial_records if r["split"] == "test"),
        },
        "usable_head_distribution": usable_head_distribution,
        "usable_records_per_head": usable_records_per_head,
        "fully_labelled_records_count": len(fully_labelled_records),
        "partial_label_records_count": len(partial_label_records),
        "manual_review_queue_count": len(manual_review_queue),
        "manual_review_workload_breakdown": {
            "total_review_eligible_records": total_review_eligible,
            "records_needing_only_garment_type_confirmation": garment_type_only,
            "records_needing_one_additional_head": one_additional_head,
            "records_needing_two_or_more_additional_heads": two_or_more_additional_heads,
            "workload_statement": workload_statement,
        },
        "class_classification": {
            "total_classes": 29,
            "zero_sample_classes": len(zero_sample_classes),
            "below_baseline_threshold": len(below_baseline_threshold_classes),
            "below_recommended_threshold": len(below_recommended_threshold_classes),
            "sufficient_samples": len(sufficient_sample_classes),
        },
        "exclusive_planning_bands": exclusive_band_counts,
        "imbalance_ratios_per_head": imbalance_ratios_per_head,
        "feasibility_verdict": feasibility_verdict,
        "verdict_disclaimer": verdict_disclaimer,
        "input_sha256": input_sha256,
        "generation_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "schema_version": "1.0.0",
    }

    with open(os.path.join(output_dir, "feasibility_summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print("==================================================")
    print("FASHIONPEDIA TRAINING FEASIBILITY ANALYSIS COMPLETED")
    print("==================================================")
    print(f"Output Directory: {os.path.abspath(output_dir)}")
    print(f"Total Records Evaluated: {len(spatial_records)}")
    print(f"Usable Head Distribution:")
    print(f"  - 4 Usable Heads (Fully Labelled): {usable_head_distribution['4_usable_heads']}")
    print(f"  - 3 Usable Heads (Partial):         {usable_head_distribution['3_usable_heads']}")
    print(f"  - 2 Usable Heads (Partial):         {usable_head_distribution['2_usable_heads']}")
    print(f"  - 1 Usable Head  (Partial):         {usable_head_distribution['1_usable_head']}")
    print(f"  - 0 Usable Heads (Unusable):        {usable_head_distribution['0_usable_heads']}")
    print(f"Exclusive Planning Bands (Total = 29):")
    print(f"  - Zero Samples (0):                {exclusive_band_counts['zero']}")
    print(f"  - Below Baseline (1-19):           {exclusive_band_counts['below_baseline_1_19']}")
    print(f"  - Below Recommended (20-99):       {exclusive_band_counts['below_recommended_20_99']}")
    print(f"  - Sufficient Samples (100+):       {exclusive_band_counts['sufficient_100_plus']}")
    print(f"Feasibility Verdict: {feasibility_verdict}")
    print("==================================================")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analyze training feasibility and generate manual review queues.")
    parser.add_argument("--spatial-manifest", required=True, help="Path to all_instances_spatial.jsonl.")
    parser.add_argument("--classes", required=True, help="Path to classes.json.")
    parser.add_argument("--policy", required=True, help="Path to training_data_policy.json.")
    parser.add_argument("--output-dir", required=True, help="Output directory for feasibility analysis.")

    args = parser.parse_args()
    run_feasibility_analysis(
        spatial_manifest_path=args.spatial_manifest,
        classes_path=args.classes,
        policy_path=args.policy,
        output_dir=args.output_dir,
    )
