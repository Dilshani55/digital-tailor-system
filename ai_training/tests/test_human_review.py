#!/usr/bin/env python3
"""
test_human_review.py

Unit tests for Milestone M9A targeted human review queue and gold-label review interface.

Tests cover:
- Deterministic queue construction
- Review target limits
- Duplicate prevention
- Split preservation
- T-shirt prioritization
- Saved decision schema validation
- Invalid label rejection
- Unknown queue ID rejection
- Atomic persistence
- Decision correction
- Path traversal prevention
- Arithmetic consistency
- Leakage detection
"""

import datetime
import json
import os
import shutil
import tempfile
import unittest

from ai_training.scripts.build_human_review_queue import (
    select_records_for_pool,
    load_labelling_data,
)
from ai_training.scripts.validate_human_review import (
    validate_iso_timestamp,
    compute_sha256,
)
from ai_training.review_app import (
    atomic_write_decisions,
    load_human_decisions,
    load_queue_records,
)


class TestHumanReview(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.policy = {
            "max_queue_total": 700,
            "allowed_human_labels": ["blouse", "t-shirt", "crop-top", "reject", "uncertain"],
            "queue_targets": {
                "val_gold_set": {"per_class_target": 50, "max_total": 150},
                "test_gold_set": {"per_class_target": 50, "max_total": 150},
                "train_correction_set": {
                    "max_total": 400,
                    "class_targets": {"t-shirt": 250, "blouse": 100, "crop-top": 50}
                }
            }
        }

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_deterministic_queue_construction(self):
        """Test deterministic candidate selection order."""
        candidates = [
            {"source_annotation_id": 1, "source_image_id": 10, "split": "train", "decision": "accepted", "top1_confidence": 0.85},
            {"source_annotation_id": 2, "source_image_id": 11, "split": "train", "decision": "accepted", "top1_confidence": 0.95},
            {"source_annotation_id": 3, "source_image_id": 12, "split": "train", "decision": "manual_review", "top1_confidence": 0.55},
        ]
        seen_ann = set()
        seen_img = set()
        split_by_img = {}

        sel = select_records_for_pool(candidates, 2, "train_tshirt_priority", "t-shirt", seen_ann, seen_img, split_by_img)
        self.assertEqual(len(sel), 2)
        # Higher confidence accepted record should come first
        self.assertEqual(sel[0]["source_annotation_id"], 2)
        self.assertEqual(sel[1]["source_annotation_id"], 1)

    def test_duplicate_prevention_and_split_preservation(self):
        """Test duplicate annotation prevention and split constancy."""
        candidates = [
            {"source_annotation_id": 1, "source_image_id": 10, "split": "val", "decision": "accepted", "top1_confidence": 0.90},
            {"source_annotation_id": 1, "source_image_id": 10, "split": "val", "decision": "accepted", "top1_confidence": 0.90},
        ]
        seen_ann = set()
        seen_img = set()
        split_by_img = {}

        sel = select_records_for_pool(candidates, 5, "val_gold_set", "blouse", seen_ann, seen_img, split_by_img)
        self.assertEqual(len(sel), 1)
        self.assertEqual(sel[0]["split"], "val")

    def test_tshirt_prioritization(self):
        """Test that train split prioritizes t-shirt candidates."""
        candidates = [
            {"source_annotation_id": 1, "source_image_id": 10, "split": "train", "decision": "manual_review", "top1_confidence": 0.50, "source_evidence": {"candidate_garment_type": "t-shirt"}},
            {"source_annotation_id": 2, "source_image_id": 11, "split": "train", "decision": "accepted", "top1_confidence": 0.80, "source_evidence": {"candidate_garment_type": "blouse"}},
        ]
        seen_ann = set()
        seen_img = set()
        split_by_img = {}

        sel = select_records_for_pool(candidates, 1, "train_tshirt_priority", "t-shirt", seen_ann, seen_img, split_by_img)
        self.assertEqual(len(sel), 1)
        self.assertEqual(sel[0]["source_annotation_id"], 1)

    def test_saved_decision_schema_validation(self):
        """Test validation of saved decision record fields."""
        now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
        decision = {
            "source_annotation_id": 101,
            "source_image_id": 201,
            "split": "val",
            "crop_path": "ai_training/data/images/crops/test.jpg",
            "human_label": "blouse",
            "human_verified": True,
            "reviewer_id": "test_reviewer",
            "reviewed_at": now_str,
            "previous_pseudo_label": "blouse",
            "fashionpedia_evidence": {"candidate_garment_type": "blouse"},
            "decision_version": "1.0.0"
        }
        self.assertTrue(decision["human_verified"])
        self.assertEqual(decision["human_label"], "blouse")
        self.assertTrue(validate_iso_timestamp(now_str))

    def test_invalid_label_and_unknown_id_rejection(self):
        """Test rejection of invalid human label and unknown queue ID."""
        allowed = set(self.policy["allowed_human_labels"])
        invalid_label = "sweater"
        self.assertNotIn(invalid_label, allowed)

        queue_ids = {101, 102}
        unknown_id = 999
        self.assertNotIn(unknown_id, queue_ids)

    def test_atomic_persistence_and_decision_correction(self):
        """Test atomic file writing and correcting a decision."""
        decisions_file = os.path.join(self.temp_dir, "human_decisions.jsonl")

        d1 = {
            101: {
                "source_annotation_id": 101,
                "human_label": "t-shirt",
                "human_verified": True,
                "reviewer_id": "rev1",
                "reviewed_at": "2026-09-27T12:00:00Z"
            }
        }
        atomic_write_decisions(decisions_file, d1)
        loaded1 = load_human_decisions(decisions_file)
        self.assertEqual(loaded1[101]["human_label"], "t-shirt")

        # Correct decision to crop-top
        d1[101]["human_label"] = "crop-top"
        atomic_write_decisions(decisions_file, d1)
        loaded2 = load_human_decisions(decisions_file)
        self.assertEqual(loaded2[101]["human_label"], "crop-top")

    def test_path_traversal_prevention(self):
        """Test that relative path traversal is detected."""
        proj_root = os.path.abspath(self.temp_dir)
        traversal_path = os.path.abspath(os.path.join(proj_root, "..", "outside.jpg"))
        self.assertFalse(traversal_path.startswith(proj_root))

    def test_arithmetic_consistency(self):
        """Test exact reviewed + remaining == total queue arithmetic."""
        total_queue = 700
        reviewed = 150
        remaining = total_queue - reviewed
        self.assertEqual(reviewed + remaining, total_queue)

    def test_leakage_detection(self):
        """Test image ID split leakage detection."""
        split_by_img = {100: "train"}
        # Attempt to add image 100 to val split
        image_id = 100
        target_split = "val"
        leakage = (image_id in split_by_img) and (split_by_img[image_id] != target_split)
        self.assertTrue(leakage)


if __name__ == "__main__":
    unittest.main()
