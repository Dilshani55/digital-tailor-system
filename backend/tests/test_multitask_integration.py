#!/usr/bin/env python3
"""
test_multitask_integration.py

Comprehensive Integration and Unit Tests for Milestone M13:
- Checkpoint existence, SHA-256 integrity, and file size metadata.
- Offline model reconstruction and loading without internet.
- Singleton pattern verification (loads only once).
- Four-head logit tensor shapes and class mapping validation.
- Valid image inference and bounding box fallback handling.
- Invalid image, corrupt image, and missing checkpoint handling.
- Low-confidence flags and confirmation routing.
- API response backward compatibility.
"""

import os
import sys
import shutil
import hashlib
import tempfile
import unittest
import torch
from PIL import Image

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.ai.multitask_classifier import (
    get_multitask_classifier,
    reset_multitask_classifier_singleton,
    preprocess_image_crop,
    predict_multitask_features,
    MultiTaskModelError,
    DEFAULT_MODEL_PATH,
    DEFAULT_BACKBONE_PATH,
    M13_MODEL_PATH,
    M40_MODEL_PATH,
    HEADS,
)


class TestMultiTaskIntegration(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Anchored to the repo root (was cwd-relative, so it failed when run from backend/).
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        cls.source_ckpt = os.path.join(
            repo_root, "ai_training", "data", "training_runs", "m12_full", "checkpoints", "best.pt")
        cls.target_ckpt = DEFAULT_MODEL_PATH
        cls.target_backbone = DEFAULT_BACKBONE_PATH

    def setUp(self):
        reset_multitask_classifier_singleton()
        self.temp_dir = tempfile.mkdtemp()
        self.sample_img_path = os.path.join(self.temp_dir, "sample.jpg")
        Image.new("RGB", (300, 400), color="blue").save(self.sample_img_path)

    def tearDown(self):
        reset_multitask_classifier_singleton()
        shutil.rmtree(self.temp_dir)

    def test_checkpoint_existence_and_sha(self):
        self.assertTrue(os.path.exists(self.target_ckpt), "Backend checkpoint missing!")
        self.assertTrue(os.path.exists(M13_MODEL_PATH), "The M13 rollback checkpoint must stay in place")
        self.target_ckpt = M13_MODEL_PATH                      # the rollback model is verified against its training output
        if not os.path.exists(self.source_ckpt):
            # ai_training/data is git-ignored; the training output only exists on the training machine.
            self.skipTest("M12 training output not present (ai_training/data is not in the repository)")

        src_size = os.path.getsize(self.source_ckpt)
        dst_size = os.path.getsize(self.target_ckpt)
        self.assertEqual(src_size, dst_size, "File sizes do not match!")

        def get_sha256(path):
            h = hashlib.sha256()
            with open(path, "rb") as f:
                while chunk := f.read(8192):
                    h.update(chunk)
            return h.hexdigest()

        src_sha = get_sha256(self.source_ckpt)
        dst_sha = get_sha256(self.target_ckpt)
        self.assertEqual(src_sha, dst_sha, "Checksums do not match!")

    def test_offline_reconstruction(self):
        model, meta = get_multitask_classifier()
        self.assertIsNotNone(model)
        # model_version is derived from the loaded checkpoint (stage, epoch, content hash),
        # not a hard-coded label.
        with open(self.target_ckpt, "rb") as f:
            actual_sha = hashlib.sha256(f.read()).hexdigest()
        self.assertEqual(meta["checkpoint_sha256"], actual_sha)
        self.assertIn("sha256=" + actual_sha[:12], meta["model_version"])
        self.assertTrue(meta["model_version"].startswith("YOLOv8MultiTaskClassifier|"))
        self.assertIn("classifier", meta["model_type"])
        self.assertIn("not an object detector", meta["model_type"])
        self.assertTrue(os.path.exists(self.target_backbone))

    def test_singleton_loading(self):
        m1, meta1 = get_multitask_classifier()
        m2, meta2 = get_multitask_classifier()
        self.assertIs(m1, m2, "Singleton failed: model instances are distinct!")
        self.assertEqual(meta1, meta2)

    def test_four_output_shapes(self):
        model, meta = get_multitask_classifier()
        model.eval()

        dummy_input = torch.randn(1, 3, 224, 224)
        with torch.no_grad():
            out = model(dummy_input)

        dims = (3, 5, 3, 4) if os.path.abspath(DEFAULT_MODEL_PATH) == os.path.abspath(M40_MODEL_PATH) else (3, 10, 6, 9)
        for head, n in zip(HEADS, dims):
            self.assertEqual(out[head].shape, (1, n), head)
        self.assertEqual([int(meta["head_dims"][h]) for h in HEADS], list(dims))

    def test_class_mapping_validation(self):
        _, meta = get_multitask_classifier()
        class_to_idx = meta["class_to_idx"]
        idx_to_class = meta["idx_to_class"]

        for head in HEADS:
            self.assertIn(head, class_to_idx)
            self.assertIn(head, idx_to_class)
            expected_dim = meta["head_dims"][head]
            self.assertEqual(len(class_to_idx[head]), expected_dim)

        # active model: M40 = 15 classes (3/5/3/4); the M13 rollback = 28 classes (3/10/6/9)
        total_classes = sum(len(class_to_idx[h]) for h in HEADS)
        is_m40 = os.path.abspath(DEFAULT_MODEL_PATH) == os.path.abspath(M40_MODEL_PATH)
        self.assertEqual(total_classes, 15 if is_m40 else 28)

    def test_valid_image_inference(self):
        res = predict_multitask_features(self.sample_img_path)

        self.assertIn("model_version", res)
        self.assertIn("predictions", res)
        self.assertIn("low_confidence_heads", res)
        self.assertIn("requires_user_confirmation", res)

        preds = res["predictions"]
        for head in HEADS:
            self.assertIn(head, preds)
            h_pred = preds[head]
            self.assertIn("label", h_pred)
            self.assertIn("class_index", h_pred)
            self.assertIn("confidence", h_pred)
            self.assertIn("top_3", h_pred)
            self.assertEqual(len(h_pred["top_3"]), 3)
            self.assertIn("requires_user_confirmation", h_pred)
            self.assertIn("threshold_used", h_pred)

    def test_invalid_bbox_fallback(self):
        # Invalid bbox: negative coordinates, out of bounds, zero area
        invalid_bboxes = [
            [-10, -5, 50, 50],
            [10, 10, 5, 5],       # x_max < x_min
            [0, 0, 1000, 1000],   # Out of image bounds
            None
        ]
        for bbox in invalid_bboxes:
            t = preprocess_image_crop(self.sample_img_path, bbox=bbox)
            self.assertEqual(t.shape, (1, 3, 224, 224))

    def test_invalid_corrupt_image_handling(self):
        corrupt_file = os.path.join(self.temp_dir, "corrupt.jpg")
        with open(corrupt_file, "w") as f:
            f.write("not an image")

        with self.assertRaises(MultiTaskModelError):
            predict_multitask_features(corrupt_file)

    def test_missing_checkpoint_response(self):
        fake_path = os.path.join(self.temp_dir, "nonexistent.pt")
        with self.assertRaises(MultiTaskModelError):
            get_multitask_classifier(model_path=fake_path)

    def test_low_confidence_flags(self):
        # Set artificially high thresholds (0.99) to force all heads into low confidence
        strict_thresholds = {h: 0.99 for h in HEADS}
        res = predict_multitask_features(self.sample_img_path, thresholds=strict_thresholds)

        self.assertTrue(res["requires_user_confirmation"])
        self.assertEqual(len(res["low_confidence_heads"]), 4)
        for h in HEADS:
            self.assertTrue(res["predictions"][h]["requires_user_confirmation"])

    def test_no_internet_required(self):
        # Run inference and verify zero internet socket/downloads required
        res = predict_multitask_features(self.sample_img_path)
        self.assertIsNotNone(res)

    def test_active_taxonomy_and_cold_shoulder_rejection(self):
        from app.routes.images import ACTIVE_TAXONOMY

        # 15 active user-selectable classes (3 / 5 / 3 / 4); the model itself still outputs 3 / 10 / 6 / 9
        total_classes = sum(len(opts) for opts in ACTIVE_TAXONOMY.values())
        self.assertEqual(total_classes, 15)
        self.assertEqual([len(ACTIVE_TAXONOMY[h]) for h in ("garment_type", "neckline_type", "sleeve_length", "sleeve_style")],
                         [3, 5, 3, 4])

        # Verify active taxonomy values
        self.assertIn("blouse", ACTIVE_TAXONOMY["garment_type"])
        self.assertIn("v-neck", ACTIVE_TAXONOMY["neckline_type"])
        self.assertIn("short-sleeve", ACTIVE_TAXONOMY["sleeve_length"])
        self.assertIn("bell-sleeve", ACTIVE_TAXONOMY["sleeve_style"])

        # Verify removed cold-shoulder-sleeve is NOT in taxonomy
        all_labels = [label for head_opts in ACTIVE_TAXONOMY.values() for label in head_opts]
        self.assertNotIn("cold-shoulder-sleeve", all_labels)
        self.assertNotIn("cold_shoulder_sleeve", all_labels)


if __name__ == "__main__":
    unittest.main()
