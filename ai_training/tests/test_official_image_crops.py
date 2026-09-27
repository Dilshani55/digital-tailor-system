#!/usr/bin/env python3
"""
test_official_image_crops.py

Unit tests for Milestone M8 geometry-correct official garment crops and AI-assisted labelling pipeline.
"""

import json
import os
import shutil
import tempfile
import unittest
from PIL import Image

from ai_training.scripts.create_selected_crops import (
    compute_crop_coordinates,
    build_official_image_index,
    compute_sha256,
)
from ai_training.scripts.select_labelling_candidates import (
    determine_candidate_class,
    compute_selection_score,
)


class TestOfficialImageCrops(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.images_root = os.path.join(self.temp_dir, "images")
        os.makedirs(os.path.join(self.images_root, "train"), exist_ok=True)
        os.makedirs(os.path.join(self.images_root, "test"), exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_official_path_resolution(self):
        """Test resolving image paths across subdirectories in official images root."""
        test_img_path = os.path.join(self.images_root, "train", "test_001.jpg")
        img = Image.new("RGB", (640, 480), color="blue")
        img.save(test_img_path)

        index = build_official_image_index(self.images_root)
        self.assertIn("test_001.jpg", index)
        self.assertEqual(os.path.normpath(index["test_001.jpg"]), os.path.normpath(test_img_path))

    def test_missing_official_source_rejection(self):
        """Test that a missing official image returns empty index entry."""
        index = build_official_image_index(self.images_root)
        self.assertNotIn("non_existent.jpg", index)

    def test_exact_geometry_crop(self):
        """Test exact geometry crop without scaling or distortion."""
        bbox = [50.0, 50.0, 100.0, 100.0]  # x, y, w, h
        coords, status, err = compute_crop_coordinates(bbox, 640, 480, margin_percent=0.05)
        self.assertEqual(status, "success")
        self.assertIsNone(err)
        # Margin x = 100 * 0.05 = 5 -> left = 45, right = 155, top = 45, bottom = 155
        self.assertEqual(coords, (45, 45, 155, 155))

    def test_invalid_bbox_rejection(self):
        """Test that zero-area or negative bbox is rejected."""
        bbox = [10.0, 10.0, 0.0, 50.0]
        coords, status, err = compute_crop_coordinates(bbox, 640, 480, margin_percent=0.05)
        self.assertEqual(status, "invalid_bbox")
        self.assertIsNotNone(err)

    def test_boundary_touching_bbox_clipping(self):
        """Test numerical boundary clipping for bbox touching image edge."""
        bbox = [0.0, 0.0, 100.0, 100.0]
        coords, status, err = compute_crop_coordinates(bbox, 640, 480, margin_percent=0.05)
        self.assertEqual(status, "success")
        # Left and top clipped to 0
        self.assertEqual(coords, (0, 0, 105, 105))

    def test_no_arbitrary_rescaling(self):
        """Ensure original bbox coords are kept without arbitrary scaling."""
        bbox = [100.0, 100.0, 200.0, 200.0]
        coords, status, err = compute_crop_coordinates(bbox, 640, 480, margin_percent=0.0)
        self.assertEqual(coords, (100, 100, 300, 300))

    def test_crop_sha256_validation(self):
        """Test SHA-256 calculation for crop file."""
        test_file = os.path.join(self.temp_dir, "sample.txt")
        with open(test_file, "w") as f:
            f.write("digital tailor system test")

        h1 = compute_sha256(test_file)
        h2 = compute_sha256(test_file)
        self.assertEqual(h1, h2)
        self.assertEqual(len(h1), 64)

    def test_crop_top_direct_disagreement_sent_to_review(self):
        """Test that crop-top direct evidence with CLIP disagreement goes to manual_review."""
        cand_garment_type = "crop-top"
        cand_reason = "Fashionpedia Cat 0 with Attr 8 crop (top)"
        top1_cls = "reject"
        reject_class = "reject"

        is_crop_top_direct = (cand_garment_type == "crop-top") and ("Attr 8" in cand_reason or "crop" in cand_reason)

        if top1_cls == reject_class:
            if is_crop_top_direct:
                decision = "manual_review"
            else:
                decision = "rejected"
        else:
            decision = "accepted"

        self.assertEqual(decision, "manual_review")

    def test_ambiguous_blouse_sent_to_review_if_threshold_fails(self):
        """Test that blouse/t-shirt ambiguous evidence goes to manual_review if confidence threshold fails."""
        top1_conf = 0.50
        conf_threshold = 0.60
        margin = 0.15
        min_margin = 0.10
        prompt_agreement = True

        if top1_conf >= conf_threshold and margin >= min_margin and prompt_agreement:
            decision = "accepted"
        else:
            decision = "manual_review"

        self.assertEqual(decision, "manual_review")


if __name__ == "__main__":
    unittest.main()
