#!/usr/bin/env python3
"""
test_fashionpedia_manifest.py

Unit tests for build_fashionpedia_manifest.py, associate_fashionpedia_parts.py,
validate_fashionpedia_manifest.py, and validate_fashionpedia_spatial_manifest.py.
"""

import unittest
import os
import json
import shutil
import sys

# Ensure scripts directory is in path
sys.path.insert(0, os.path.abspath("ai_training/scripts"))

from build_fashionpedia_manifest import build_manifest
from validate_fashionpedia_manifest import validate_manifest
from associate_fashionpedia_parts import run_spatial_association
from validate_fashionpedia_spatial_manifest import validate_spatial_manifest


class TestFashionpediaManifest(unittest.TestCase):
    def setUp(self):
        self.fixtures_dir = os.path.abspath("ai_training/tests/fixtures")
        self.mini_json = os.path.join(self.fixtures_dir, "fashionpedia_mini.json")
        self.classes_json = os.path.abspath("ai_training/config/classes.json")
        self.mapping_json = os.path.abspath("ai_training/config/fashionpedia_mapping.json")
        self.pipeline_config_json = os.path.abspath("ai_training/config/dataset_pipeline.json")
        self.assoc_config_json = os.path.abspath("ai_training/config/part_association.json")

        self.ai4a_output_dir = os.path.abspath("ai_training/tests/tmp_manifest_output")
        self.ai4b_output_dir = os.path.abspath("ai_training/tests/tmp_spatial_manifest_output")

        for d in [self.ai4a_output_dir, self.ai4b_output_dir]:
            if os.path.exists(d):
                shutil.rmtree(d)

        # Build AI-4A base manifest
        build_manifest(
            annotations_path=self.mini_json,
            classes_path=self.classes_json,
            mapping_path=self.mapping_json,
            pipeline_config_path=self.pipeline_config_json,
            output_dir=self.ai4a_output_dir,
        )

        # Run AI-4B spatial association
        run_spatial_association(
            annotations_path=self.mini_json,
            base_manifest_path=os.path.join(self.ai4a_output_dir, "all_instances.jsonl"),
            classes_path=self.classes_json,
            mapping_path=self.mapping_json,
            assoc_config_path=self.assoc_config_json,
            output_dir=self.ai4b_output_dir,
        )

        # Load AI-4B output records
        with open(os.path.join(self.ai4b_output_dir, "all_instances_spatial.jsonl"), "r", encoding="utf-8") as f:
            self.spatial_records = [json.loads(line) for line in f]
        self.spatial_rec_by_id = {r["source_annotation_id"]: r for r in self.spatial_records}

        with open(os.path.join(self.ai4b_output_dir, "accepted_associations.jsonl"), "r", encoding="utf-8") as f:
            self.accepted_assocs = [json.loads(line) for line in f]

        with open(os.path.join(self.ai4b_output_dir, "ambiguous_associations.jsonl"), "r", encoding="utf-8") as f:
            self.ambig_assocs = [json.loads(line) for line in f]

        with open(os.path.join(self.ai4b_output_dir, "unassociated_parts.jsonl"), "r", encoding="utf-8") as f:
            self.unassoc_parts = [json.loads(line) for line in f]

    def tearDown(self):
        for d in [self.ai4a_output_dir, self.ai4b_output_dir]:
            if os.path.exists(d):
                shutil.rmtree(d)

    def test_ai4a_build_and_validate_mini_manifest(self):
        validate_manifest(self.ai4a_output_dir, self.classes_json)
        validate_spatial_manifest(
            manifest_dir=self.ai4b_output_dir,
            base_manifest_path=os.path.join(self.ai4a_output_dir, "all_instances.jsonl"),
            classes_path=self.classes_json,
            association_config=self.assoc_config_json,
        )

    def test_one_sleeve_clearly_contained_by_one_garment(self):
        # Part 10 (sleeve) inside Parent 1
        assoc10 = [a for a in self.accepted_assocs if a["part_annotation_id"] == 10]
        self.assertEqual(len(assoc10), 1)
        self.assertEqual(assoc10[0]["parent_annotation_id"], 1)
        self.assertGreaterEqual(assoc10[0]["geometry_metrics"]["part_coverage"], 0.80)
        self.assertTrue(assoc10[0]["geometry_metrics"]["part_centre_inside"])

        p1 = self.spatial_rec_by_id[1]
        self.assertEqual(p1["labels"]["sleeve_length"]["label"], "short-sleeve")
        self.assertEqual(p1["labels"]["sleeve_length"]["status"], "direct")

    def test_one_neckline_clearly_contained_by_one_garment(self):
        # Part 11 (neckline) inside Parent 1
        assoc11 = [a for a in self.accepted_assocs if a["part_annotation_id"] == 11]
        self.assertEqual(len(assoc11), 1)
        self.assertEqual(assoc11[0]["parent_annotation_id"], 1)

        p1 = self.spatial_rec_by_id[1]
        self.assertEqual(p1["labels"]["neckline_type"]["label"], "v-neck")
        self.assertEqual(p1["labels"]["neckline_type"]["status"], "direct")

    def test_collar_candidate_mapping(self):
        # Part 20 (collar) inside Parent 3
        assoc20 = [a for a in self.accepted_assocs if a["part_annotation_id"] == 20]
        self.assertEqual(len(assoc20), 1)
        self.assertEqual(assoc20[0]["parent_annotation_id"], 3)

        p3 = self.spatial_rec_by_id[3]
        self.assertEqual(p3["labels"]["neckline_type"]["label"], "collared-neck")
        self.assertEqual(p3["labels"]["neckline_type"]["status"], "candidate_mapping")
        self.assertEqual(p3["decision"], "manual_review")

    def test_two_sleeve_parts_belonging_to_one_garment(self):
        # Parts 30 and 31 (left and right sleeves) inside Parent 5
        assoc_p5 = [a for a in self.accepted_assocs if a["parent_annotation_id"] == 5]
        self.assertEqual(len(assoc_p5), 2)
        part_ids = set(a["part_annotation_id"] for a in assoc_p5)
        self.assertEqual(part_ids, {30, 31})

        p5 = self.spatial_rec_by_id[5]
        self.assertEqual(p5["attached_parts_count"], 2)
        self.assertEqual(p5["labels"]["sleeve_length"]["label"], "short-sleeve")

    def test_part_outside_all_garments(self):
        # Part 40 (far outside Parent 8)
        unassoc40 = [u for u in self.unassoc_parts if u["part_annotation_id"] == 40]
        self.assertEqual(len(unassoc40), 1)
        self.assertEqual(unassoc40[0]["reason"], "NO_PARENT_MET_SPATIAL_THRESHOLDS")

    def test_part_overlapping_two_garments_ambiguously(self):
        # Part 52 overlaps Parent 50 and Parent 51 heavily -> ambiguous
        ambig52 = [a for a in self.ambig_assocs if a["part_annotation_id"] == 52]
        self.assertEqual(len(ambig52), 1)
        self.assertIn(ambig52[0]["top_parent_annotation_id"], [50, 51])
        self.assertIn(ambig52[0]["second_parent_annotation_id"], [50, 51])
        self.assertLess(ambig52[0]["score_margin"], 0.15)

    def test_two_garments_with_one_clear_spatial_winner(self):
        # Part 62 inside Parent 60, far from Parent 61 -> Parent 60 is winner
        assoc62 = [a for a in self.accepted_assocs if a["part_annotation_id"] == 62]
        self.assertEqual(len(assoc62), 1)
        self.assertEqual(assoc62[0]["parent_annotation_id"], 60)

    def test_conflicting_sleeve_length_attributes(self):
        # Part 71 (short-sleeve) and Part 72 (wrist-length) both attached to Parent 70
        p70 = self.spatial_rec_by_id[70]
        self.assertEqual(p70["decision"], "manual_review")
        self.assertIn("CONFLICT_HEAD_SLEEVE_LENGTH", p70["reason_codes"])
        self.assertIsNone(p70["labels"]["sleeve_length"])

    def test_invalid_part_bbox(self):
        # Part 81 (zero bbox) -> unassociated with INVALID_PART_BBOX
        unassoc81 = [u for u in self.unassoc_parts if u["part_annotation_id"] == 81]
        self.assertEqual(len(unassoc81), 1)
        self.assertEqual(unassoc81[0]["reason"], "INVALID_PART_BBOX")

    def test_no_duplicate_part_assignment(self):
        assigned_part_ids = [a["part_annotation_id"] for a in self.accepted_assocs]
        self.assertEqual(len(assigned_part_ids), len(set(assigned_part_ids)))

    def test_crop_top_with_complete_four_head_direct_evidence(self):
        # Parent 1: Cat 0 + Attr 8 crop-top, Sleeve Part 10 (short-sleeve, puff-sleeve), Neckline Part 11 (v-neck)
        # All 4 heads receive valid direct labels -> training_ready!
        p1 = self.spatial_rec_by_id[1]
        self.assertEqual(p1["decision"], "training_ready")
        self.assertEqual(p1["labels"]["garment_type"]["label"], "crop-top")
        self.assertEqual(p1["labels"]["garment_type"]["status"], "direct")
        self.assertEqual(p1["labels"]["neckline_type"]["label"], "v-neck")
        self.assertEqual(p1["labels"]["neckline_type"]["status"], "direct")
        self.assertEqual(p1["labels"]["sleeve_length"]["label"], "short-sleeve")
        self.assertEqual(p1["labels"]["sleeve_length"]["status"], "direct")
        self.assertEqual(p1["labels"]["sleeve_style"]["label"], "puff-sleeve")
        self.assertEqual(p1["labels"]["sleeve_style"]["status"], "direct")

    def test_source_split_unchanged_after_association(self):
        with open(os.path.join(self.ai4a_output_dir, "all_instances.jsonl"), "r", encoding="utf-8") as f:
            base_recs = [json.loads(line) for line in f]
        base_by_id = {r["source_annotation_id"]: r for r in base_recs}

        for p_id, p_rec in self.spatial_rec_by_id.items():
            self.assertEqual(p_rec["split"], base_by_id[p_id]["split"])


if __name__ == "__main__":
    unittest.main()
