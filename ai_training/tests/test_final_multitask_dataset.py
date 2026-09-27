#!/usr/bin/env python3
"""
test_final_multitask_dataset.py

Unit tests for Milestone M9B final multi-task dataset construction and validation.
Uses synthetic test fixtures ONLY.
"""

import json
import os
import shutil
import tempfile
import unittest

from ai_training.scripts.build_final_multitask_dataset import (
    load_partition_image_path_map,
    process_spatial_record,
    resolve_partition_for_record,
)
from ai_training.scripts.validate_final_multitask_dataset import validate_dataset


class TestFinalMultiTaskDataset(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.labelling_dir = os.path.join(self.temp_dir, "labelling")
        self.human_dir = os.path.join(self.temp_dir, "human")
        self.processed_dir = os.path.join(self.temp_dir, "processed")
        self.output_dir = os.path.join(self.temp_dir, "output")
        self.images_dir = os.path.join(self.temp_dir, "images")

        os.makedirs(self.labelling_dir, exist_ok=True)
        os.makedirs(self.human_dir, exist_ok=True)
        os.makedirs(self.processed_dir, exist_ok=True)
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.images_dir, exist_ok=True)

        # Mock classes.json
        self.classes_path = os.path.join(self.temp_dir, "classes.json")
        self.classes_data = {
            "schema_version": "1.0.0",
            "model_family": "YOLOv8",
            "model_type": "single-multi-task-classifier",
            "number_of_models": 1,
            "class_counts": {
                "garment_type": 3,
                "neckline_type": 10,
                "sleeve_length": 6,
                "sleeve_style": 9
            },
            "total_label_count": 28,
            "outputs": {
                "garment_type": {
                    "class_count": 3,
                    "classes": ["blouse", "t-shirt", "crop-top"],
                    "class_to_idx": {"blouse": 0, "t-shirt": 1, "crop-top": 2},
                    "idx_to_class": {"0": "blouse", "1": "t-shirt", "2": "crop-top"}
                },
                "neckline_type": {
                    "class_count": 10,
                    "classes": ["round-neck", "v-neck", "square-neck", "scoop-neck", "boat-neck", "sweetheart-neck", "halter-neck", "high-neck", "collared-neck", "off-shoulder"],
                    "class_to_idx": {"round-neck": 0, "v-neck": 1, "square-neck": 2, "scoop-neck": 3, "boat-neck": 4, "sweetheart-neck": 5, "halter-neck": 6, "high-neck": 7, "collared-neck": 8, "off-shoulder": 9},
                    "idx_to_class": {"0": "round-neck", "1": "v-neck", "2": "square-neck", "3": "scoop-neck", "4": "boat-neck", "5": "sweetheart-neck", "6": "halter-neck", "7": "high-neck", "8": "collared-neck", "9": "off-shoulder"}
                },
                "sleeve_length": {
                    "class_count": 6,
                    "classes": ["sleeveless", "cap-length", "short-sleeve", "elbow-length", "three-quarter-sleeve", "long-sleeve"],
                    "class_to_idx": {"sleeveless": 0, "cap-length": 1, "short-sleeve": 2, "elbow-length": 3, "three-quarter-sleeve": 4, "long-sleeve": 5},
                    "idx_to_class": {"0": "sleeveless", "1": "cap-length", "2": "short-sleeve", "3": "elbow-length", "4": "three-quarter-sleeve", "5": "long-sleeve"}
                },
                "sleeve_style": {
                    "class_count": 9,
                    "classes": ["none", "regular-sleeve", "puff-sleeve", "bell-sleeve", "bishop-sleeve", "flutter-sleeve", "raglan-sleeve", "dolman-sleeve", "kimono-sleeve"],
                    "class_to_idx": {"none": 0, "regular-sleeve": 1, "puff-sleeve": 2, "bell-sleeve": 3, "bishop-sleeve": 4, "flutter-sleeve": 5, "raglan-sleeve": 6, "dolman-sleeve": 7, "kimono-sleeve": 8},
                    "idx_to_class": {"0": "none", "1": "regular-sleeve", "2": "puff-sleeve", "3": "bell-sleeve", "4": "bishop-sleeve", "5": "flutter-sleeve", "6": "raglan-sleeve", "7": "dolman-sleeve", "8": "kimono-sleeve"}
                }
            }
        }
        with open(self.classes_path, "w", encoding="utf-8") as f:
            json.dump(self.classes_data, f, indent=2)

        # Mock policy.json
        self.policy_path = os.path.join(self.temp_dir, "policy.json")
        self.policy_data = {
            "schema_version": "1.1.0",
            "readiness_verdict": "READY_FOR_PARTIAL_COVERAGE_BASELINE_ONLY",
            "allowed_garment_labels": ["blouse", "t-shirt", "crop-top"],
            "heads": ["garment_type", "neckline_type", "sleeve_length", "sleeve_style"],
            "provenance_priority": ["human_verified", "fashionpedia_direct", "accepted_pseudo_label", "missing/masked"],
            "sample_weights": {
                "human_verified": 1.0,
                "fashionpedia_direct": 1.0,
                "accepted_pseudo_label": 0.5,
                "missing/masked": 0.0
            },
            "minimum_gold_evaluation_count_warning_threshold": 50
        }
        with open(self.policy_path, "w", encoding="utf-8") as f:
            json.dump(self.policy_data, f, indent=2)

        self.class_to_idx = {h: self.classes_data["outputs"][h]["class_to_idx"] for h in self.policy_data["heads"]}

        # Dummy image file
        self.mock_fn = "test.jpg"
        self.mock_img = os.path.join(self.images_dir, self.mock_fn)
        with open(self.mock_img, "wb") as f:
            f.write(b"dummy image content")

        self.img_file_map = {("train2020", self.mock_fn): self.mock_img, ("val2020", self.mock_fn): self.mock_img}

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_partition_resolution_with_same_raw_ids(self):
        spatial_by_uid = {
            "fashionpedia:train2020:100": {"source_annotation_id": 100, "source_image_id": 50, "source_file_name": "train.jpg"},
            "fashionpedia:val2020:100": {"source_annotation_id": 100, "source_image_id": 50, "source_file_name": "val.jpg"}
        }

        rec_train = {"source_annotation_id": 100, "source_image_id": 50, "source_file_name": "train.jpg"}
        rec_val = {"source_annotation_id": 100, "source_image_id": 50, "source_file_name": "val.jpg"}

        self.assertEqual(resolve_partition_for_record(rec_train, spatial_by_uid), "train2020")
        self.assertEqual(resolve_partition_for_record(rec_val, spatial_by_uid), "val2020")

    def test_human_decision_applies_only_to_exact_partition(self):
        sp_train = {"source_partition": "train2020", "source_annotation_id": 100, "source_image_id": 50, "source_file_name": self.mock_fn, "bbox": [10, 10, 100, 100]}
        sp_val = {"source_partition": "val2020", "source_annotation_id": 100, "source_image_id": 50, "source_file_name": self.mock_fn, "bbox": [10, 10, 100, 100]}

        d_train = {"human_label": "blouse", "human_verified": True}
        decisions_by_uid = {"fashionpedia:train2020:100": d_train}

        res_train = process_spatial_record("fashionpedia:train2020:100", sp_train, {}, {}, decisions_by_uid, {}, self.img_file_map, self.policy_data, self.class_to_idx)
        res_val = process_spatial_record("fashionpedia:val2020:100", sp_val, {}, {}, decisions_by_uid, {}, self.img_file_map, self.policy_data, self.class_to_idx)

        self.assertEqual(res_train["labels"]["garment_type"], "blouse")
        self.assertEqual(res_train["provenance"]["garment_type"], "human_verified")

        # val2020 record MUST NOT receive train2020 decision!
        self.assertIsNone(res_val["labels"]["garment_type"])
        self.assertEqual(res_val["masks"]["garment_type"], 0)
        self.assertEqual(res_val["provenance"]["garment_type"], "missing/masked")

    def test_pseudo_label_applies_only_to_exact_partition(self):
        sp_train = {"source_partition": "train2020", "source_annotation_id": 200, "source_image_id": 60, "source_file_name": self.mock_fn, "bbox": [10, 10, 50, 50]}
        sp_val = {"source_partition": "val2020", "source_annotation_id": 200, "source_image_id": 60, "source_file_name": self.mock_fn, "bbox": [10, 10, 50, 50]}

        p_rec = {"decision": "accepted", "predicted_garment_type": "t-shirt", "top1_confidence": 0.85}
        pseudo_by_uid = {"fashionpedia:train2020:200": p_rec}

        res_train = process_spatial_record("fashionpedia:train2020:200", sp_train, {}, {}, {}, pseudo_by_uid, self.img_file_map, self.policy_data, self.class_to_idx)
        res_val = process_spatial_record("fashionpedia:val2020:200", sp_val, {}, {}, {}, pseudo_by_uid, self.img_file_map, self.policy_data, self.class_to_idx)

        self.assertEqual(res_train["labels"]["garment_type"], "t-shirt")
        self.assertIsNone(res_val["labels"]["garment_type"])

    def test_crop_metadata_applies_only_to_exact_partition(self):
        sp_train = {"source_partition": "train2020", "source_annotation_id": 300, "source_image_id": 70, "source_file_name": self.mock_fn, "bbox": [10, 10, 50, 50]}
        sp_val = {"source_partition": "val2020", "source_annotation_id": 300, "source_image_id": 70, "source_file_name": self.mock_fn, "bbox": [10, 10, 50, 50]}

        crop_rec = {"crop_path": "ai_training/data/crops/300_crop.jpg"}
        crops_by_uid = {"fashionpedia:train2020:300": crop_rec}

        res_train = process_spatial_record("fashionpedia:train2020:300", sp_train, crops_by_uid, {}, {}, {}, self.img_file_map, self.policy_data, self.class_to_idx)
        res_val = process_spatial_record("fashionpedia:val2020:300", sp_val, crops_by_uid, {}, {}, {}, self.img_file_map, self.policy_data, self.class_to_idx)

        self.assertEqual(res_train["crop_path"], "ai_training/data/crops/300_crop.jpg")
        self.assertIsNone(res_val["crop_path"])

    def test_strict_partition_image_path_map_no_fallback(self):
        train_dir = os.path.join(self.images_dir, "train")
        val_dir = os.path.join(self.images_dir, "val")
        os.makedirs(train_dir, exist_ok=True)
        os.makedirs(val_dir, exist_ok=True)

        with open(os.path.join(train_dir, "img1.jpg"), "wb") as f:
            f.write(b"train1")
        with open(os.path.join(val_dir, "img2.jpg"), "wb") as f:
            f.write(b"val2")

        img_map = load_partition_image_path_map(self.images_dir)

        self.assertIn(("train2020", "img1.jpg"), img_map)
        self.assertNotIn(("val2020", "img1.jpg"), img_map)  # NO fallback for train image

        self.assertIn(("val2020", "img2.jpg"), img_map)
        self.assertNotIn(("train2020", "img2.jpg"), img_map)  # NO fallback for val image!

    def test_duplicate_image_path_keys_raise_error(self):
        train_dir1 = os.path.join(self.images_dir, "train", "sub1")
        train_dir2 = os.path.join(self.images_dir, "train", "sub2")
        os.makedirs(train_dir1, exist_ok=True)
        os.makedirs(train_dir2, exist_ok=True)

        with open(os.path.join(train_dir1, "dup.jpg"), "wb") as f:
            f.write(b"dup1")
        with open(os.path.join(train_dir2, "dup.jpg"), "wb") as f:
            f.write(b"dup2")

    def test_direct_croptop_in_train_produces_mask_1(self):
        sp_train = {
            "source_partition": "train2020",
            "source_annotation_id": 400,
            "source_image_id": 80,
            "source_file_name": self.mock_fn,
            "bbox": [10, 10, 50, 50],
            "fashionpedia_attribute_ids": [8],
        }
        res_train = process_spatial_record("fashionpedia:train2020:400", sp_train, {}, {}, {}, {}, self.img_file_map, self.policy_data, self.class_to_idx)
        self.assertEqual(res_train["labels"]["garment_type"], "crop-top")
        self.assertEqual(res_train["masks"]["garment_type"], 1)
        self.assertEqual(res_train["provenance"]["garment_type"], "fashionpedia_direct")

    def test_direct_croptop_in_val_and_test_produces_mask_0_without_human_decision(self):
        sp_val = {
            "source_partition": "val2020",
            "source_annotation_id": 401,
            "source_image_id": 81,
            "source_file_name": self.mock_fn,
            "bbox": [10, 10, 50, 50],
            "fashionpedia_attribute_ids": [8],
        }
        res_val = process_spatial_record("fashionpedia:val2020:401", sp_val, {}, {}, {}, {}, self.img_file_map, self.policy_data, self.class_to_idx)
        self.assertIsNone(res_val["labels"]["garment_type"])
        self.assertEqual(res_val["masks"]["garment_type"], 0)
        self.assertEqual(res_val["provenance"]["garment_type"], "missing/masked")

    def test_human_verified_croptop_in_val_test_produces_mask_1(self):
        sp_val = {
            "source_partition": "val2020",
            "source_annotation_id": 402,
            "source_image_id": 82,
            "source_file_name": self.mock_fn,
            "bbox": [10, 10, 50, 50],
            "fashionpedia_attribute_ids": [8],
        }
        decisions_by_uid = {"fashionpedia:val2020:402": {"human_label": "crop-top", "human_verified": True}}
        res_val = process_spatial_record("fashionpedia:val2020:402", sp_val, {}, {}, decisions_by_uid, {}, self.img_file_map, self.policy_data, self.class_to_idx)
        self.assertEqual(res_val["labels"]["garment_type"], "crop-top")
        self.assertEqual(res_val["masks"]["garment_type"], 1)
        self.assertEqual(res_val["provenance"]["garment_type"], "human_verified")

    def test_val_record_with_masked_garment_type_but_direct_neckline_remains_usable(self):
        sp_val = {
            "source_partition": "val2020",
            "source_annotation_id": 403,
            "source_image_id": 83,
            "source_file_name": self.mock_fn,
            "bbox": [10, 10, 50, 50],
            "fashionpedia_attribute_ids": [8],
            "labels": {
                "neckline_type": {"status": "direct", "label": "v-neck"}
            }
        }
        res_val = process_spatial_record("fashionpedia:val2020:403", sp_val, {}, {}, {}, {}, self.img_file_map, self.policy_data, self.class_to_idx)
        self.assertEqual(res_val["masks"]["garment_type"], 0)
        self.assertEqual(res_val["masks"]["neckline_type"], 1)
        self.assertEqual(res_val["labels"]["neckline_type"], "v-neck")
        self.assertFalse(res_val["exclusion_reasons"])


if __name__ == "__main__":
    unittest.main()
