#!/usr/bin/env python3
"""
test_fashionpedia_manifest.py

Unit tests for build_fashionpedia_manifest.py and validate_fashionpedia_manifest.py
using synthetic fixtures.
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


class TestFashionpediaManifest(unittest.TestCase):
    def setUp(self):
        self.fixtures_dir = os.path.abspath("ai_training/tests/fixtures")
        self.mini_json = os.path.join(self.fixtures_dir, "fashionpedia_mini.json")
        self.classes_json = os.path.abspath("ai_training/config/classes.json")
        self.mapping_json = os.path.abspath("ai_training/config/fashionpedia_mapping.json")
        self.pipeline_config_json = os.path.abspath("ai_training/config/dataset_pipeline.json")

        self.test_output_dir = os.path.abspath("ai_training/tests/tmp_manifest_output")
        if os.path.exists(self.test_output_dir):
            shutil.rmtree(self.test_output_dir)

    def tearDown(self):
        if os.path.exists(self.test_output_dir):
            shutil.rmtree(self.test_output_dir)

    def test_build_and_validate_mini_manifest(self):
        # Run manifest build
        build_manifest(
            annotations_path=self.mini_json,
            classes_path=self.classes_json,
            mapping_path=self.mapping_json,
            pipeline_config_path=self.pipeline_config_json,
            output_dir=self.test_output_dir,
        )

        # Check output files exist
        self.assertTrue(os.path.exists(os.path.join(self.test_output_dir, "all_instances.jsonl")))
        self.assertTrue(os.path.exists(os.path.join(self.test_output_dir, "training_ready.jsonl")))
        self.assertTrue(os.path.exists(os.path.join(self.test_output_dir, "manual_review.jsonl")))
        self.assertTrue(os.path.exists(os.path.join(self.test_output_dir, "rejected.jsonl")))
        self.assertTrue(os.path.exists(os.path.join(self.test_output_dir, "summary.json")))

        # Read output records
        with open(os.path.join(self.test_output_dir, "all_instances.jsonl"), "r", encoding="utf-8") as f:
            all_records = [json.loads(line) for line in f]

        rec_by_id = {r["source_annotation_id"]: r for r in all_records}

        # 1. Relevant instance count check (Category 6 'pants' ignored -> 8 upper garment instances)
        self.assertEqual(len(all_records), 8)
        self.assertNotIn(7, rec_by_id)  # Instance 7 (pants) excluded

        # 2. Instance 1: Training ready (crop-top + v-neck + short-sleeve + puff-sleeve, all direct)
        r1 = rec_by_id[1]
        self.assertEqual(r1["decision"], "training_ready")
        self.assertEqual(r1["labels"]["garment_type"]["label"], "crop-top")
        self.assertEqual(r1["labels"]["garment_type"]["status"], "direct")
        self.assertEqual(r1["labels"]["neckline_type"]["label"], "v-neck")

        # 3. Crop-top precedence test: Instance 1 Category 0 'shirt, blouse' overridden to crop-top via Attr 8
        self.assertEqual(r1["fashionpedia_category_id"], 0)
        self.assertEqual(r1["labels"]["garment_type"]["label"], "crop-top")

        # 4. Instance 2: Sleeveless (Attr 156) deriving sleeve_style = none
        r2 = rec_by_id[2]
        self.assertEqual(r2["labels"]["sleeve_length"]["label"], "sleeveless")
        self.assertEqual(r2["labels"]["sleeve_style"]["label"], "none")
        self.assertEqual(r2["labels"]["sleeve_style"]["status"], "candidate_mapping")

        # 5. Split isolation test: Instance 1 and Instance 2 share image_id 1001 -> identical split
        self.assertEqual(r1["source_image_id"], 1001)
        self.assertEqual(r2["source_image_id"], 1001)
        self.assertEqual(r1["split"], r2["split"])

        # 6. Instance 3: Candidate mapping blouse (Cat 0) -> manual_review
        r3 = rec_by_id[3]
        self.assertEqual(r3["decision"], "manual_review")
        self.assertIn("MANUAL_REVIEW_CANDIDATE_MAPPING", r3["reason_codes"])

        # 7. Instance 4: Invalid zero bbox -> rejected
        r4 = rec_by_id[4]
        self.assertEqual(r4["decision"], "rejected")
        self.assertIn("INVALID_BBOX", r4["reason_codes"])

        # 8. Instance 5: Conflicting neckline attributes (182 round + 183 v-neck) -> manual_review
        r5 = rec_by_id[5]
        self.assertEqual(r5["decision"], "manual_review")
        self.assertIn("CONFLICT_HEAD_NECKLINE_TYPE", r5["reason_codes"])

        # 9. Instance 6: Missing neckline head -> manual_review
        r6 = rec_by_id[6]
        self.assertEqual(r6["decision"], "manual_review")
        self.assertIn("MISSING_HEAD_NECKLINE_TYPE", r6["reason_codes"])

        # 10. Instance 8: Unknown attribute ID 9999 handled gracefully
        r8 = rec_by_id[8]
        self.assertIn(9999, r8["fashionpedia_attribute_ids"])
        self.assertIn("unknown_9999", r8["fashionpedia_attribute_names"])

        # 11. Regression test: Instance 9 (Jacket Category 4 with Attr 8) MUST NOT become crop-top
        r9 = rec_by_id[9]
        self.assertEqual(r9["fashionpedia_category_id"], 4)
        self.assertIsNone(r9["labels"]["garment_type"])  # garment_type is None, not crop-top

        # Run validate_manifest on the output directory
        validate_manifest(self.test_output_dir, self.classes_json)


if __name__ == "__main__":
    unittest.main()
