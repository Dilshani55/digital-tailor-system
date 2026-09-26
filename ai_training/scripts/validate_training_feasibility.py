#!/usr/bin/env python3
"""
validate_training_feasibility.py

Validates the accuracy, schema, class counts, split constancy, priority queue ranks,
and summary consistency of the training feasibility analysis produced by Milestone AI-5.

Usage:
    python ai_training/scripts/validate_training_feasibility.py \
      --analysis-dir ai_training/data/analysis/training_feasibility \
      --spatial-manifest ai_training/data/processed/fashionpedia_spatial_manifest/all_instances_spatial.jsonl \
      --classes ai_training/config/classes.json \
      --policy ai_training/config/training_data_policy.json
"""

import sys
import os
import json
import argparse


def validate_feasibility_analysis(analysis_dir, spatial_manifest_path, classes_path, policy_path):
    print("==================================================")
    print("FASHIONPEDIA TRAINING FEASIBILITY VALIDATION RUN")
    print("==================================================")
    print(f"Analysis Directory: {os.path.abspath(analysis_dir)}")

    summary_file = os.path.join(analysis_dir, "feasibility_summary.json")
    class_counts_file = os.path.join(analysis_dir, "class_counts_by_split.json")
    partial_file = os.path.join(analysis_dir, "partial_label_records.jsonl")
    fully_labelled_file = os.path.join(analysis_dir, "fully_labelled_records.jsonl")
    queue_file = os.path.join(analysis_dir, "manual_review_priority.jsonl")
    zero_classes_file = os.path.join(analysis_dir, "zero_sample_classes.json")
    action_plan_file = os.path.join(analysis_dir, "recommended_action_plan.json")

    for p in [summary_file, class_counts_file, partial_file, fully_labelled_file, queue_file, zero_classes_file, action_plan_file, spatial_manifest_path, classes_path, policy_path]:
        if not os.path.exists(p):
            print(f"VALIDATION FAILED: File not found: {p}", file=sys.stderr)
            sys.exit(1)

    # Load metadata and JSON files
    with open(classes_path, "r", encoding="utf-8") as f:
        classes_data = json.load(f)
    with open(summary_file, "r", encoding="utf-8") as f:
        summary_data = json.load(f)
    with open(class_counts_file, "r", encoding="utf-8") as f:
        class_counts_data = json.load(f)
    with open(zero_classes_file, "r", encoding="utf-8") as f:
        zero_classes_data = json.load(f)
    with open(action_plan_file, "r", encoding="utf-8") as f:
        action_plan_data = json.load(f)

    target_heads = list(classes_data["outputs"].keys())
    all_classes_by_head = {h: classes_data["outputs"][h]["classes"] for h in target_heads}
    total_taxonomy_count = sum(len(classes_data["outputs"][h]["classes"]) for h in target_heads)

    if total_taxonomy_count != 29:
        print(f"VALIDATION FAILED: Total target classes ({total_taxonomy_count}) != 29", file=sys.stderr)
        sys.exit(1)

    if len(all_classes_by_head.get("garment_type", [])) != 3:
        print(f"VALIDATION FAILED: garment_type classes count ({len(all_classes_by_head.get('garment_type', []))}) != 3", file=sys.stderr)
        sys.exit(1)

    forbidden_source_terms = {"shirt", "top", "sweatshirt"}
    for h, clist in all_classes_by_head.items():
        for cname in clist:
            if cname in forbidden_source_terms:
                print(f"VALIDATION FAILED: Forbidden term '{cname}' found in target taxonomy for head '{h}'", file=sys.stderr)
                sys.exit(1)

    # Load JSONL files
    def load_jsonl(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            return [json.loads(line) for line in f]

    spatial_recs = load_jsonl(spatial_manifest_path)
    partial_recs = load_jsonl(partial_file)
    fully_labelled_recs = load_jsonl(fully_labelled_file)
    queue_recs = load_jsonl(queue_file)

    spatial_by_id = {r["source_annotation_id"]: r for r in spatial_recs}

    print(f"Loaded {len(spatial_recs)} spatial manifest records")

    # 1. Check all 29 target classes are represented in class_counts_by_split.json
    total_found_classes = 0
    for h in target_heads:
        if h not in class_counts_data:
            print(f"VALIDATION FAILED: Head '{h}' missing in class_counts_by_split.json", file=sys.stderr)
            sys.exit(1)

        expected_head_classes = set(all_classes_by_head[h])
        found_head_classes = set(class_counts_data[h].keys())

        if expected_head_classes != found_head_classes:
            print(f"VALIDATION FAILED: Mismatch in classes for head '{h}': expected {expected_head_classes}, found {found_head_classes}", file=sys.stderr)
            sys.exit(1)

        total_found_classes += len(found_head_classes)

        # Check per-split mathematical sum
        for cname, counts in class_counts_data[h].items():
            if counts["train"] + counts["val"] + counts["test"] != counts["total"]:
                print(f"VALIDATION FAILED: Split sum mismatch for class '{cname}': {counts}", file=sys.stderr)
                sys.exit(1)

    if total_found_classes != 29:
        print(f"VALIDATION FAILED: Total classes in report ({total_found_classes}) != 29", file=sys.stderr)
        sys.exit(1)

    print("1. All 29 target classes represented & split counts sum to total: PASSED")

    # 2. Re-calculate direct class counts from spatial manifest & check usable caps
    recalc_counts = {h: {c: {"train": 0, "val": 0, "test": 0, "total": 0} for c in all_classes_by_head[h]} for h in target_heads}
    recalc_zero_classes = []
    usable_records_per_head_recalc = {h: 0 for h in target_heads}

    for r in spatial_recs:
        sp = r["split"]
        for h in target_heads:
            lbl_info = r["labels"].get(h)
            if lbl_info and lbl_info.get("status") == "direct":
                lbl = lbl_info["label"]
                if lbl not in recalc_counts[h]:
                    print(f"VALIDATION FAILED: Unknown direct label '{lbl}' for head '{h}'", file=sys.stderr)
                    sys.exit(1)
                recalc_counts[h][lbl][sp] += 1
                recalc_counts[h][lbl]["total"] += 1
                usable_records_per_head_recalc[h] += 1

    for h in target_heads:
        sum_head_class_totals = sum(class_counts_data[h][cname]["total"] for cname in all_classes_by_head[h])
        if sum_head_class_totals > usable_records_per_head_recalc[h]:
            print(f"VALIDATION FAILED: Head '{h}' class totals sum ({sum_head_class_totals}) exceeds usable record count ({usable_records_per_head_recalc[h]})", file=sys.stderr)
            sys.exit(1)

        for cname in all_classes_by_head[h]:
            rep_cnt = class_counts_data[h][cname]["total"]
            real_cnt = recalc_counts[h][cname]["total"]
            if rep_cnt != real_cnt:
                print(f"VALIDATION FAILED: Direct count mismatch for class '{cname}': reported {rep_cnt} vs real {real_cnt}", file=sys.stderr)
                sys.exit(1)
            if real_cnt == 0:
                recalc_zero_classes.append(cname)

    # Verify zero-sample classes list accuracy & length equality
    zero_classes_reported_list = zero_classes_data["zero_sample_classes"]
    if zero_classes_data["total_zero_sample_classes"] != len(zero_classes_reported_list):
        print(f"VALIDATION FAILED: Reported total zero classes count ({zero_classes_data['total_zero_sample_classes']}) != list length ({len(zero_classes_reported_list)})", file=sys.stderr)
        sys.exit(1)

    zero_classes_reported_names = [c["class_name"] for c in zero_classes_reported_list]
    if set(zero_classes_reported_names) != set(recalc_zero_classes):
        print(f"VALIDATION FAILED: Zero-sample classes mismatch: reported {set(zero_classes_reported_names)} vs real {set(recalc_zero_classes)}", file=sys.stderr)
        sys.exit(1)

    print("2. Class counts and zero-sample classes verified against manifest: PASSED")

    # 3. Verify exclusive planning bands sum to 29
    exclusive_bands = summary_data.get("exclusive_planning_bands", {})
    sum_bands = sum(exclusive_bands.values())
    if sum_bands != 29:
        print(f"VALIDATION FAILED: Exclusive planning bands sum ({sum_bands}) != 29", file=sys.stderr)
        sys.exit(1)

    # 4. Verify record partition (fully labelled vs partial label)
    for r in fully_labelled_recs:
        ann_id = r["source_annotation_id"]
        if ann_id not in spatial_by_id:
            print(f"VALIDATION FAILED: Fully labelled record {ann_id} not in spatial manifest", file=sys.stderr)
            sys.exit(1)
        if r["usable_direct_heads_count"] != 4:
            print(f"VALIDATION FAILED: Fully labelled record {ann_id} does not have exactly 4 usable heads", file=sys.stderr)
            sys.exit(1)

    for r in partial_recs:
        ann_id = r["source_annotation_id"]
        if ann_id not in spatial_by_id:
            print(f"VALIDATION FAILED: Partial record {ann_id} not in spatial manifest", file=sys.stderr)
            sys.exit(1)
        cnt = r["usable_direct_heads_count"]
        if not (1 <= cnt <= 3):
            print(f"VALIDATION FAILED: Partial record {ann_id} has invalid usable heads count: {cnt}", file=sys.stderr)
            sys.exit(1)

    print("3. Fully labelled (4 heads) and partial records (1-3 heads) validation: PASSED")

    # 5. Verify manual review priority queue: real records, sequential ranks, split invariance
    seen_ranks = set()
    for idx, r in enumerate(queue_recs, start=1):
        ann_id = r["source_annotation_id"]
        rank = r["priority_rank"]

        if ann_id not in spatial_by_id:
            print(f"VALIDATION FAILED: Queue item {ann_id} not in spatial manifest", file=sys.stderr)
            sys.exit(1)

        sp = r["split"]
        if sp != spatial_by_id[ann_id]["split"]:
            print(f"VALIDATION FAILED: Queue item {ann_id} split changed: {spatial_by_id[ann_id]['split']} -> {sp}", file=sys.stderr)
            sys.exit(1)

        if rank != idx:
            print(f"VALIDATION FAILED: Non-sequential priority rank {rank} (expected {idx})", file=sys.stderr)
            sys.exit(1)

        if rank in seen_ranks:
            print(f"VALIDATION FAILED: Duplicate priority rank {rank}", file=sys.stderr)
            sys.exit(1)
        seen_ranks.add(rank)

    print("4. Manual review queue ranks, sequence, and split constancy: PASSED")

    # 6. Verify feasibility verdict is validation-subset specific
    verdict = summary_data.get("feasibility_verdict")
    allowed_verdicts = {
        "NOT_FEASIBLE_WITH_CURRENT_VALIDATION_SUBSET",
        "READY_AFTER_TARGETED_MANUAL_REVIEW",
        "FULL_DATASET_INSPECTION_REQUIRED",
    }

    if verdict not in allowed_verdicts:
        print(f"VALIDATION FAILED: Feasibility verdict '{verdict}' overgeneralizes beyond validation subset!", file=sys.stderr)
        sys.exit(1)

    disclaimer = summary_data.get("verdict_disclaimer", "")
    if "validation annotation package" not in disclaimer and "instances_attributes_val2020.json" not in disclaimer:
        print("VALIDATION FAILED: Verdict disclaimer missing validation subset qualification!", file=sys.stderr)
        sys.exit(1)

    # 7. Verify summary metrics match JSONL file counts
    if summary_data["total_spatial_records_evaluated"] != len(spatial_recs):
        print("VALIDATION FAILED: Summary record count mismatch", file=sys.stderr)
        sys.exit(1)

    if summary_data["fully_labelled_records_count"] != len(fully_labelled_recs):
        print("VALIDATION FAILED: Summary fully_labelled count mismatch", file=sys.stderr)
        sys.exit(1)

    if summary_data["partial_label_records_count"] != len(partial_recs):
        print("VALIDATION FAILED: Summary partial_label count mismatch", file=sys.stderr)
        sys.exit(1)

    if summary_data["manual_review_queue_count"] != len(queue_recs):
        print("VALIDATION FAILED: Summary manual_review_queue count mismatch", file=sys.stderr)
        sys.exit(1)

    print("5. Summary totals & JSONL line counts match: PASSED")
    print("==================================================")
    print("ALL FEASIBILITY VALIDATIONS PASSED CLEANLY!")
    print("==================================================")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validate training feasibility analysis.")
    parser.add_argument("--analysis-dir", required=True, help="Path to feasibility analysis output directory.")
    parser.add_argument("--spatial-manifest", required=True, help="Path to all_instances_spatial.jsonl.")
    parser.add_argument("--classes", required=True, help="Path to classes.json.")
    parser.add_argument("--policy", required=True, help="Path to training_data_policy.json.")

    args = parser.parse_args()
    validate_feasibility_analysis(args.analysis_dir, args.spatial_manifest, args.classes, args.policy)
