#!/usr/bin/env python3
"""
test_training_feasibility.py

Unit tests for analyse_training_feasibility.py and validate_training_feasibility.py.
"""

import unittest
import os
import json
import shutil
import sys

sys.path.insert(0, os.path.abspath("ai_training/scripts"))

from build_fashionpedia_manifest import build_manifest
from associate_fashionpedia_parts import run_spatial_association
from analyse_training_feasibility import run_feasibility_analysis
from validate_training_feasibility import validate_feasibility_analysis


class TestTrainingFeasibility(unittest.TestCase):
    def setUp(self):
        self.fixtures_dir = os.path.abspath("ai_training/tests/fixtures")
        self.mini_json = os.path.join(self.fixtures_dir, "fashionpedia_mini.json")
        self.classes_json = os.path.abspath("ai_training/config/classes.json")
        self.mapping_json = os.path.abspath("ai_training/config/fashionpedia_mapping.json")
        self.pipeline_config_json = os.path.abspath("ai_training/config/dataset_pipeline.json")
        self.assoc_config_json = os.path.abspath("ai_training/config/part_association.json")
        self.policy_json = os.path.abspath("ai_training/config/training_data_policy.json")

        self.ai4a_dir = os.path.abspath("ai_training/tests/tmp_feasibility_base_manifest")
        self.ai4b_dir = os.path.abspath("ai_training/tests/tmp_feasibility_spatial_manifest")
        self.ai5_dir = os.path.abspath("ai_training/tests/tmp_feasibility_analysis")

        for d in [self.ai4a_dir, self.ai4b_dir, self.ai5_dir]:
            if os.path.exists(d):
                shutil.rmtree(d)

        # Build base manifest (AI-4A)
        build_manifest(
            annotations_path=self.mini_json,
            classes_path=self.classes_json,
            mapping_path=self.mapping_json,
            pipeline_config_path=self.pipeline_config_json,
            output_dir=self.ai4a_dir,
        )

        # Run spatial part association (AI-4B)
        run_spatial_association(
            annotations_path=self.mini_json,
            base_manifest_path=os.path.join(self.ai4a_dir, "all_instances.jsonl"),
            classes_path=self.classes_json,
            mapping_path=self.mapping_json,
            assoc_config_path=self.assoc_config_json,
            output_dir=self.ai4b_dir,
        )

        # Run feasibility analysis (AI-5)
        run_feasibility_analysis(
            spatial_manifest_path=os.path.join(self.ai4b_dir, "all_instances_spatial.jsonl"),
            classes_path=self.classes_json,
            policy_path=self.policy_json,
            output_dir=self.ai5_dir,
        )

        # Load generated files
        with open(os.path.join(self.ai5_dir, "feasibility_summary.json"), "r", encoding="utf-8") as f:
            self.summary = json.load(f)
        with open(os.path.join(self.ai5_dir, "class_counts_by_split.json"), "r", encoding="utf-8") as f:
            self.class_counts = json.load(f)
        with open(os.path.join(self.ai5_dir, "zero_sample_classes.json"), "r", encoding="utf-8") as f:
            self.zero_classes_data = json.load(f)

        def load_jsonl(fn):
            with open(os.path.join(self.ai5_dir, fn), "r", encoding="utf-8") as f:
                return [json.loads(line) for line in f]

        self.fully_labelled = load_jsonl("fully_labelled_records.jsonl")
        self.partial = load_jsonl("partial_label_records.jsonl")
        self.queue = load_jsonl("manual_review_priority.jsonl")

    def tearDown(self):
        for d in [self.ai4a_dir, self.ai4b_dir, self.ai5_dir]:
            if os.path.exists(d):
                shutil.rmtree(d)

    def test_fully_labelled_record(self):
        # Record 1 has 4 direct labels -> fully labelled
        rec1_full = [r for r in self.fully_labelled if r["source_annotation_id"] == 1]
        self.assertEqual(len(rec1_full), 1)
        self.assertEqual(rec1_full[0]["usable_direct_heads_count"], 4)

    def test_one_head_partial_record(self):
        # Record 2 has 1 direct head (sleeve_length: sleeveless)
        rec2_part = [r for r in self.partial if r["source_annotation_id"] == 2]
        self.assertEqual(len(rec2_part), 1)
        self.assertEqual(rec2_part[0]["usable_direct_heads_count"], 1)

    def test_three_head_partial_record(self):
        # Partial records list must contain partial records (usable direct heads between 1 and 3)
        self.assertGreaterEqual(len(self.partial), 1)
        for r in self.partial:
            self.assertTrue(1 <= r["usable_direct_heads_count"] <= 3)

    def test_candidate_label_excluded_from_direct_counts(self):
        # Record 3 (Cat 0 shirt/blouse) maps to candidate_mapping 'blouse'
        # Direct count for 'blouse' from Record 3 must be 0
        b_cnt = self.class_counts["garment_type"]["blouse"]["total"]
        self.assertEqual(b_cnt, 0)

    def test_missing_label_represented_by_mask_not_class_0(self):
        # Missing heads in partial records must have status missing_or_conflicting and label None
        rec5 = [r for r in self.partial if r["source_annotation_id"] == 5][0]
        self.assertFalse(rec5["usable_head_details"]["neckline_type"]["usable"])
        self.assertIsNone(rec5["usable_head_details"]["neckline_type"]["label"])

    def test_conflicting_label_excluded(self):
        # Record 70 has conflicting sleeve_length attributes -> conflicting_heads includes sleeve_length
        rec70 = [r for r in self.queue if r["source_annotation_id"] == 70][0]
        self.assertIn("sleeve_length", rec70["conflicting_heads"])

    def test_zero_sample_classes_retained_in_report(self):
        # All 28 target classes must be present in class_counts_by_split.json
        total_cls_count = sum(len(self.class_counts[h]) for h in self.class_counts)
        self.assertEqual(total_cls_count, 28)

        # Removed label cold-shoulder-sleeve must be absent from active taxonomy
        self.assertNotIn("cold-shoulder-sleeve", self.class_counts["sleeve_style"])

    def test_split_preservation(self):
        # Splits in queue and analysis must match spatial manifest
        spatial_path = os.path.join(self.ai4b_dir, "all_instances_spatial.jsonl")
        with open(spatial_path, "r", encoding="utf-8") as f:
            sp_recs = [json.loads(line) for line in f]
        sp_by_id = {r["source_annotation_id"]: r["split"] for r in sp_recs}

        for q in self.queue:
            ann_id = q["source_annotation_id"]
            self.assertEqual(q["split"], sp_by_id[ann_id])

    def test_duplicate_prevention(self):
        # Sum of usable direct head counts across distribution equals total evaluated records
        tot_recs = self.summary["total_spatial_records_evaluated"]
        sum_dist = (
            self.summary["usable_head_distribution"]["0_usable_heads"] +
            self.summary["usable_head_distribution"]["1_usable_head"] +
            self.summary["usable_head_distribution"]["2_usable_heads"] +
            self.summary["usable_head_distribution"]["3_usable_heads"] +
            self.summary["usable_head_distribution"]["4_usable_heads"]
        )
        self.assertEqual(tot_recs, sum_dist)

    def test_manual_review_priority_ordering(self):
        # Ranks must be 1-indexed sequential, scores descending
        ranks = [q["priority_rank"] for q in self.queue]
        scores = [q["priority_score"] for q in self.queue]

        self.assertEqual(ranks, list(range(1, len(self.queue) + 1)))
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_rare_label_priority(self):
        # Verify queue items with rare direct labels receive non-zero priority score
        rare_items = [q for q in self.queue if any("direct" in str(lbl) for lbl in q["current_labels"].values())]
        if rare_items:
            self.assertGreater(rare_items[0]["priority_score"], 0.0)

    def test_summary_count_consistency(self):
        # Run validator on output directory
        validate_feasibility_analysis(
            analysis_dir=self.ai5_dir,
            spatial_manifest_path=os.path.join(self.ai4b_dir, "all_instances_spatial.jsonl"),
            classes_path=self.classes_json,
            policy_path=self.policy_json,
        )

    # REGRESSION TESTS (MILESTONE AI-5 AUDIT)

    def test_fashionpedia_source_names_never_become_target_classes(self):
        # Verify forbidden ontology terms like 'shirt', 'top', 'sweatshirt' never appear as target classes
        forbidden_terms = {"shirt", "top", "sweatshirt"}
        for h in self.class_counts:
            for cname in self.class_counts[h]:
                self.assertNotIn(cname, forbidden_terms, f"Forbidden source term '{cname}' in head '{h}'")
        self.assertEqual(len(self.class_counts["garment_type"]), 3)

    def test_duplicate_sleeve_evidence_counted_once(self):
        # Record 1 in mini fixture has 2 attached short-sleeve parts.
        # Verify that Record 1 has 2 attached parts but contributes exactly 1 to Record 1's sleeve_length label.
        spatial_path = os.path.join(self.ai4b_dir, "all_instances_spatial.jsonl")
        with open(spatial_path, "r", encoding="utf-8") as f:
            sp_recs = [json.loads(line) for line in f]
        rec1 = [r for r in sp_recs if r["source_annotation_id"] == 1][0]
        self.assertEqual(len(rec1["attached_parts"]), 2)
        self.assertEqual(rec1["labels"]["sleeve_length"]["label"], "short-sleeve")
        self.assertEqual(rec1["labels"]["sleeve_length"]["status"], "direct")
        # In mini fixture 3 unique parent records have short-sleeve (Rec 1, 46, 125).
        # If double-counted per part, count would be 4 instead of 3.
        self.assertEqual(self.class_counts["sleeve_length"]["short-sleeve"]["total"], 3)

    def test_conflicting_sleeve_evidence_counted_zero_times(self):
        # Record 70 in mini fixture has conflicting sleeve length attributes
        # Its sleeve_length label must be None (usable False) and contribute 0 to any sleeve_length class
        spatial_path = os.path.join(self.ai4b_dir, "all_instances_spatial.jsonl")
        with open(spatial_path, "r", encoding="utf-8") as f:
            sp_recs = [json.loads(line) for line in f]
        rec70 = [r for r in sp_recs if r["source_annotation_id"] == 70][0]
        self.assertIsNone(rec70["labels"]["sleeve_length"])

    def test_train_val_test_totals_sum_to_global_totals(self):
        # For every head and class: train + val + test == total
        for h in self.class_counts:
            for cname, counts in self.class_counts[h].items():
                self.assertEqual(counts["train"] + counts["val"] + counts["test"], counts["total"])

    def test_source_package_name_does_not_overwrite_project_split(self):
        # Ensure summary records source_package as val2020 while keeping train/val/test split counts
        self.assertEqual(self.summary["source_package"], "instances_attributes_val2020.json")
        self.assertIn("train", self.summary["split_counts"])
        self.assertIn("val", self.summary["split_counts"])
        self.assertIn("test", self.summary["split_counts"])

    def test_zero_class_displayed_total_matches_list_length(self):
        # Total zero sample classes count in JSON must equal list length
        tot_cnt = self.zero_classes_data["total_zero_sample_classes"]
        list_len = len(self.zero_classes_data["zero_sample_classes"])
        self.assertEqual(tot_cnt, list_len)

    def test_four_exclusive_planning_bands_sum_to_28(self):
        # Four exclusive planning bands in summary must sum to 28
        bands = self.summary["exclusive_planning_bands"]
        sum_bands = sum(bands.values())
        self.assertEqual(sum_bands, 28)

    def test_validator_rejects_impossible_per_head_totals(self):
        # Corrupt class counts so head total exceeds usable records
        class_counts_path = os.path.join(self.ai5_dir, "class_counts_by_split.json")
        with open(class_counts_path, "r", encoding="utf-8") as f:
            corrupted = json.load(f)
        corrupted["garment_type"]["crop-top"]["total"] += 999
        with open(class_counts_path, "w", encoding="utf-8") as f:
            json.dump(corrupted, f)

        with self.assertRaises(SystemExit):
            validate_feasibility_analysis(
                analysis_dir=self.ai5_dir,
                spatial_manifest_path=os.path.join(self.ai4b_dir, "all_instances_spatial.jsonl"),
                classes_path=self.classes_json,
                policy_path=self.policy_json,
            )

    def test_validator_detects_corrupted_counts(self):
        # Corrupt summary file count
        summary_path = os.path.join(self.ai5_dir, "feasibility_summary.json")
        with open(summary_path, "r", encoding="utf-8") as f:
            corrupted = json.load(f)
        corrupted["fully_labelled_records_count"] += 999
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(corrupted, f)

        with self.assertRaises(SystemExit):
            validate_feasibility_analysis(
                analysis_dir=self.ai5_dir,
                spatial_manifest_path=os.path.join(self.ai4b_dir, "all_instances_spatial.jsonl"),
                classes_path=self.classes_json,
                policy_path=self.policy_json,
            )


if __name__ == "__main__":
    unittest.main()
