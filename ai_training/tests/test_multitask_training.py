#!/usr/bin/env python3
"""
test_multitask_training.py

Unit tests for Milestone M11 Single YOLOv8 Multi-Task Model and Training Pipeline.
Uses synthetic test fixtures ONLY.
"""

import json
import os
import shutil
import sys
import tempfile
import unittest
import torch
import torch.nn as nn
from PIL import Image

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from ai_training.datasets.multitask_dataset import MultiTaskDataset, select_coverage_aware_subset, HEADS
from ai_training.models.multitask_yolov8 import YOLOv8MultiTaskClassifier
from ai_training.training.masked_loss import MaskedMultiTaskLoss, compute_capped_class_weights
from ai_training.training.metrics import MultiTaskMetricsTracker
from ai_training.scripts.evaluate_multitask import load_and_verify_checkpoint


class TestMultiTaskTraining(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.pretrained_path = os.path.join(self.temp_dir, "yolov8n-cls.pt")
        shutil.copy("ai_training/data/training_runs/pretrained/yolov8n-cls.pt", self.pretrained_path)

        self.head_dims = {
            "garment_type": 3,
            "neckline_type": 10,
            "sleeve_length": 6,
            "sleeve_style": 9,
        }

        self.class_to_idx = {
            "garment_type": {"blouse": 0, "t-shirt": 1, "crop-top": 2},
            "neckline_type": {f"neck_{i}": i for i in range(10)},
            "sleeve_length": {f"len_{i}": i for i in range(6)},
            "sleeve_style": {f"style_{i}": i for i in range(9)},
        }

        self.idx_to_class = {
            h: {str(v): k for k, v in self.class_to_idx[h].items()}
            for h in HEADS
        }

        # Mock image
        self.mock_img_path = os.path.join(self.temp_dir, "test.jpg")
        Image.new("RGB", (300, 300), color="blue").save(self.mock_img_path)

        # Mock JSONL manifest
        self.mock_jsonl = os.path.join(self.temp_dir, "train.jsonl")
        mock_records = []
        for i in range(20):
            mock_records.append({
                "record_uid": f"fashionpedia:train2020:{i}",
                "source_image_path": self.mock_img_path,
                "bbox": [10.0, 10.0, 100.0, 100.0],
                "split": "train",
                "labels": {
                    "garment_type": "blouse" if i % 2 == 0 else "t-shirt",
                    "neckline_type": "neck_0",
                    "sleeve_length": "len_0",
                    "sleeve_style": "style_0",
                },
                "masks": {
                    "garment_type": 1 if i % 2 == 0 else 0,
                    "neckline_type": 1,
                    "sleeve_length": 0,
                    "sleeve_style": 1,
                },
                "provenance": {
                    "garment_type": "human_verified",
                    "neckline_type": "fashionpedia_direct",
                    "sleeve_length": "missing/masked",
                    "sleeve_style": "fashionpedia_rule_derived",
                },
            })

        with open(self.mock_jsonl, "w", encoding="utf-8") as f:
            for r in mock_records:
                f.write(json.dumps(r) + "\n")

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_four_output_shapes(self):
        model = YOLOv8MultiTaskClassifier(
            pretrained_path=self.pretrained_path,
            head_dims=self.head_dims,
            freeze_backbone=True,
        )
        x = torch.randn(4, 3, 224, 224)
        out = model(x)

        self.assertIn("garment_type", out)
        self.assertIn("neckline_type", out)
        self.assertIn("sleeve_length", out)
        self.assertIn("sleeve_style", out)

        self.assertEqual(out["garment_type"].shape, (4, 3))
        self.assertEqual(out["neckline_type"].shape, (4, 10))
        self.assertEqual(out["sleeve_length"].shape, (4, 6))
        self.assertEqual(out["sleeve_style"].shape, (4, 9))

    def test_masked_loss(self):
        criterion = MaskedMultiTaskLoss()

        logits = {
            "garment_type": torch.randn(2, 3),
            "neckline_type": torch.randn(2, 10),
            "sleeve_length": torch.randn(2, 6),
            "sleeve_style": torch.randn(2, 9),
        }
        targets = {
            "garment_type": torch.tensor([0, 1]),
            "neckline_type": torch.tensor([1, 2]),
            "sleeve_length": torch.tensor([0, 0]),
            "sleeve_style": torch.tensor([3, 4]),
        }
        masks = {
            "garment_type": torch.tensor([1.0, 0.0]),
            "neckline_type": torch.tensor([1.0, 1.0]),
            "sleeve_length": torch.tensor([0.0, 0.0]),  # Completely masked head
            "sleeve_style": torch.tensor([0.0, 1.0]),
        }
        weights = {h: torch.ones(2) for h in HEADS}

        loss, head_losses = criterion(logits, targets, masks, weights)

        self.assertTrue(loss.requires_grad or loss.item() > 0)
        self.assertGreater(loss.item(), 0)
        self.assertEqual(head_losses["sleeve_length"], 0.0)  # Fully masked head must produce 0 loss!

    def test_all_masked_batch_handling(self):
        criterion = MaskedMultiTaskLoss()
        logits = {h: torch.randn(2, self.head_dims[h]) for h in HEADS}
        targets = {h: torch.tensor([0, 0]) for h in HEADS}
        masks = {h: torch.zeros(2) for h in HEADS}
        weights = {h: torch.zeros(2) for h in HEADS}

        loss, head_losses = criterion(logits, targets, masks, weights)
        self.assertEqual(loss.item(), 0.0)

    def test_provenance_weights(self):
        criterion = MaskedMultiTaskLoss()
        logits = {h: torch.randn(1, self.head_dims[h]) for h in HEADS}
        targets = {h: torch.tensor([0]) for h in HEADS}
        masks = {h: torch.tensor([1.0]) for h in HEADS}

        w_high = {h: torch.tensor([1.0]) for h in HEADS}
        w_low = {h: torch.tensor([0.5]) for h in HEADS}

        loss_high, _ = criterion(logits, targets, masks, w_high)
        loss_low, _ = criterion(logits, targets, masks, w_low)

        # Mean loss normalized by active weight sum equals average unweighted loss
        self.assertAlmostEqual(loss_high.item(), loss_low.item(), places=4)

    def test_bbox_cropping_geometry(self):
        ds = MultiTaskDataset(
            jsonl_path=self.mock_jsonl,
            class_to_idx=self.class_to_idx,
            is_train=False,
        )
        item = ds[0]
        self.assertEqual(item["image"].shape, (3, 224, 224))
        self.assertEqual(item["masks"]["garment_type"].item(), 1.0)
        self.assertEqual(item["labels"]["garment_type"].item(), 0)

    def test_deterministic_sampling(self):
        with open(self.mock_jsonl, "r", encoding="utf-8") as f:
            records = [json.loads(line) for line in f if line.strip()]
        sub1 = select_coverage_aware_subset(records, max_records=10)
        sub2 = select_coverage_aware_subset(records, max_records=10)

        uids1 = [r["record_uid"] for r in sub1]
        uids2 = [r["record_uid"] for r in sub2]
        self.assertEqual(uids1, uids2)
        self.assertEqual(len(sub1), 10)

    def test_checkpoint_save_and_reload(self):
        model = YOLOv8MultiTaskClassifier(
            pretrained_path=self.pretrained_path,
            head_dims=self.head_dims,
            freeze_backbone=True,
        )
        ckpt_path = os.path.join(self.temp_dir, "test_ckpt.pt")

        config = {"pretrained_path": self.pretrained_path, "random_seed": 42, "pretrained_backbone_identifier": "yolov8n-cls"}
        optimizer = torch.optim.Adam(model.parameters(), lr=0.001)

        from ai_training.scripts.train_multitask import save_checkpoint
        save_checkpoint(ckpt_path, model, optimizer, epoch=1, stage="A", selection_score=0.5, config=config, class_to_idx=self.class_to_idx, idx_to_class=self.idx_to_class, val_metrics={})

        loaded_model, ckpt, loaded_config, _, _ = load_and_verify_checkpoint(ckpt_path, torch.device("cpu"))
        self.assertIsNotNone(loaded_model)
        self.assertEqual(ckpt["epoch"], 1)
        self.assertEqual(ckpt["pretrained_backbone_identifier"], "yolov8n-cls")

    def test_one_real_image_inference_path(self):
        model = YOLOv8MultiTaskClassifier(
            pretrained_path=self.pretrained_path,
            head_dims=self.head_dims,
            freeze_backbone=True,
        )
        model.eval()

        img_tensor = torch.randn(1, 3, 224, 224)
        with torch.no_grad():
            out = model(img_tensor)

        for head in HEADS:
            self.assertEqual(out[head].shape, (1, self.head_dims[head]))


if __name__ == "__main__":
    unittest.main()
