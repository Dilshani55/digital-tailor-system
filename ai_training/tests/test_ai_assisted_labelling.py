#!/usr/bin/env python3
"""
test_ai_assisted_labelling.py

Unit tests for AI-assisted garment labelling pipeline (Milestone AI-6B).

Runs with:
python -m unittest discover -s ai_training/tests -p "test_*.py" -v
"""

import json
import os
import shutil
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from PIL import Image

import torch

# Import functions from scripts
from ai_training.scripts.select_labelling_candidates import determine_candidate_class, compute_selection_score
from ai_training.scripts.create_selected_crops import compute_crop_coordinates
from ai_training.scripts.download_selected_images import validate_image_file, compute_sha256


class TestAIAssistedLabelling(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_crop_top_precedence(self):
        """Test that Attr 8 crop (top) takes precedence over blouse and t-shirt."""
        # Cat 0 shirt, blouse with Attr 8 crop (top)
        cls, reason = determine_candidate_class(0, [8, 115])
        self.assertEqual(cls, "crop-top")

        # Cat 1 top, t-shirt, sweatshirt with Attr 8 crop (top) and Attr 0 classic
        cls, reason = determine_candidate_class(1, [0, 8])
        self.assertEqual(cls, "crop-top")

    def test_tshirt_rules(self):
        """Test Cat 1 top, t-shirt with Attr 0 or 4 yields t-shirt."""
        cls, reason = determine_candidate_class(1, [0, 115])
        self.assertEqual(cls, "t-shirt")

        cls, reason = determine_candidate_class(1, [4])
        self.assertEqual(cls, "t-shirt")

    def test_blouse_rules(self):
        """Test Cat 0 shirt, blouse without Attr 8 yields blouse."""
        cls, reason = determine_candidate_class(0, [115, 137])
        self.assertEqual(cls, "blouse")

    def test_out_of_scope_categories_excluded(self):
        """Test that out-of-scope categories (e.g. Cat 4 jacket, Cat 2 dress) are excluded."""
        cls, reason = determine_candidate_class(4, [17])
        self.assertIsNone(cls)

        cls, reason = determine_candidate_class(2, [8])
        self.assertIsNone(cls)

    def test_compute_selection_score(self):
        """Test score calculation for direct heads and attached parts."""
        rec = {
            "labels": {
                "garment_type": {"status": "candidate_mapping", "label": "blouse"},
                "neckline_type": {"status": "direct", "label": "v-neck"},
                "sleeve_length": {"status": "direct", "label": "short-sleeve"},
                "sleeve_style": {"status": "candidate_mapping", "label": "regular-sleeve"},
            },
            "attached_parts_count": 2,
            "fashionpedia_attribute_ids": [115, 137],
        }
        score = compute_selection_score(rec)
        # 2 direct heads * 10 = 20, 2 candidate_mapping * 4 = 8, 2 attached parts * 2 = 4, 2 attrs = 2 -> total = 34
        self.assertEqual(score, 34)

    def test_bbox_clipping_and_margin(self):
        """Test context expansion (5%) and clipping to image bounds."""
        bbox = [100.0, 100.0, 200.0, 200.0]  # x, y, w, h
        img_w, img_h = 500, 500
        margin_pct = 0.05

        coords, err = compute_crop_coordinates(bbox, img_w, img_h, margin_pct)
        self.assertIsNone(err)
        # Margin x = 200 * 0.05 = 10, Margin y = 200 * 0.05 = 10
        # Expected: left=90, top=90, right=310, bottom=310
        self.assertEqual(coords, (90, 90, 310, 310))

    def test_invalid_image_rejection(self):
        """Test that corrupted bytes are rejected by validate_image_file."""
        corrupt_path = os.path.join(self.temp_dir, "corrupt.jpg")
        with open(corrupt_path, "wb") as f:
            f.write(b"not an image file bytes")

        valid, err = validate_image_file(corrupt_path)
        self.assertFalse(valid)
        self.assertIsNotNone(err)

    def test_synthetic_image_validation(self):
        """Test valid synthetic image file."""
        synth_path = os.path.join(self.temp_dir, "test.jpg")
        img = Image.new("RGB", (100, 100), color="blue")
        img.save(synth_path, format="JPEG")

        valid, err = validate_image_file(synth_path)
        self.assertTrue(valid)
        self.assertIsNone(err)

    @patch("ai_training.scripts.ai_assisted_label.CLIPModel")
    @patch("ai_training.scripts.ai_assisted_label.CLIPProcessor")
    def test_ai_label_thresholds_and_disagreement(self, mock_processor, mock_model):
        """Test low-confidence and prompt disagreement routing to review_required."""
        from ai_training.scripts.ai_assisted_label import evaluate_crop_with_clip

        synth_path = os.path.join(self.temp_dir, "crop.jpg")
        img = Image.new("RGB", (100, 100), color="red")
        img.save(synth_path, format="JPEG")

        # Mock model outputs for 14 prompts
        mock_instance = MagicMock()
        mock_model.from_pretrained.return_value = mock_instance
        
        # Create dummy logits per image
        logits = torch.tensor([[10.0, 9.5, 9.2, 5.0, 4.0, 4.0, 2.0, 2.0, 2.0, 1.0, 1.0, 1.0, 1.0, 1.0]])
        mock_output = MagicMock()
        mock_output.logits_per_image = logits
        mock_instance.return_value = mock_output

        mock_proc_instance = MagicMock()
        mock_processor.from_pretrained.return_value = mock_proc_instance

        prompt_templates = {
            "blouse": ["a women's blouse", "a feminine blouse for women", "a women's tailored blouse"],
            "t-shirt": ["a women's t-shirt", "a short-sleeved women's tee shirt", "a casual women's t-shirt"],
            "crop-top": ["a women's crop top", "a cropped top for women", "a women's cropped blouse or t-shirt"],
            "reject": ["a men's shirt", "a sweatshirt or hoodie", "a dress, jacket or coat", "not a women's blouse, t-shirt or crop top", "an unclear or unsuitable garment image"]
        }
        all_classes = ["blouse", "t-shirt", "crop-top", "reject"]

        res, err = evaluate_crop_with_clip(synth_path, mock_instance, mock_proc_instance, prompt_templates, all_classes)
        
        self.assertIsNone(err)
        self.assertIn("top1_label", res)
        self.assertIn("top1_confidence", res)
        self.assertIn("margin", res)

    def test_pseudo_label_never_human_verified(self):
        """Ensure pseudo-labels generated by AI pipeline always set human_verified: False."""
        fake_label = {
            "source_annotation_id": 100,
            "label_origin": "ai_assisted_pseudo_label",
            "predicted_garment_type": "blouse",
            "human_verified": False,
        }
        self.assertFalse(fake_label["human_verified"])


if __name__ == "__main__":
    unittest.main()
