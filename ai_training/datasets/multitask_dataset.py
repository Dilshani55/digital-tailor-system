#!/usr/bin/env python3
"""
multitask_dataset.py

PyTorch Dataset for Multi-Task Training and Evaluation (Milestone M11).
- Reads train.jsonl, val.jsonl, and test.jsonl manifests.
- Loads raw source images and crops parent garment using bounding boxes [x, y, w, h].
- Validates image and bounding box geometry.
- Applies torchvision augmentations for training split; deterministic resize and ImageNet normalization for val/test.
- Returns image tensor, target labels, masks, per-head provenance sample weights, and metadata.
- Includes coverage-aware sampling helper to select up to 256 records covering all 28 classes for CPU smoke training.
"""

import json
import os
import torch
from torch.utils.data import Dataset
from PIL import Image, ImageFile
from torchvision import transforms

ImageFile.LOAD_TRUNCATED_IMAGES = True

DEFAULT_PROVENANCE_WEIGHTS = {
    "human_verified": 1.0,
    "fashionpedia_direct": 1.0,
    "fashionpedia_rule_derived": 0.8,
    "accepted_pseudo_label": 0.5,
    "missing/masked": 0.0,
}

HEADS = ["garment_type", "neckline_type", "sleeve_length", "sleeve_style"]


def get_default_transforms(image_size=224, is_train=True):
    """Returns default torchvision transforms for 224x224 input."""
    if is_train:
        return transforms.Compose([
            transforms.Resize((image_size, image_size)),
            transforms.RandomHorizontalFlip(p=0.5),
            transforms.ColorJitter(brightness=0.1, contrast=0.1),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=[0.485, 0.456, 0.406],
                std=[0.229, 0.224, 0.225]
            ),
        ])
    else:
        return transforms.Compose([
            transforms.Resize((image_size, image_size)),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=[0.485, 0.456, 0.406],
                std=[0.229, 0.224, 0.225]
            ),
        ])


def select_coverage_aware_subset(records, max_records=256, samples_per_class=5):
    """
    Selects up to max_records while ensuring coverage of all 28 target classes in the train split.
    """
    if len(records) <= max_records:
        return records

    class_records = {}
    for idx, r in enumerate(records):
        for h in HEADS:
            mask = r.get("masks", {}).get(h, 0)
            lbl = r.get("labels", {}).get(h)
            if mask == 1 and lbl:
                key = f"{h}:{lbl}"
                class_records.setdefault(key, []).append(idx)

    selected_indices = set()
    # First pass: collect up to samples_per_class per target class
    for key, idxs in class_records.items():
        for i in idxs[:samples_per_class]:
            selected_indices.add(i)
            if len(selected_indices) >= max_records:
                break
        if len(selected_indices) >= max_records:
            break

    # Second pass: fill up to max_records in original order
    for idx in range(len(records)):
        if len(selected_indices) >= max_records:
            break
        selected_indices.add(idx)

    sorted_indices = sorted(selected_indices)
    return [records[i] for i in sorted_indices]


class MultiTaskDataset(Dataset):
    def __init__(
        self,
        jsonl_path: str,
        class_to_idx: dict,
        is_train: bool = True,
        transform=None,
        max_records: int = None,
        coverage_aware_sample: bool = False,
        provenance_weights: dict = None,
        image_size: int = 224,
    ):
        super().__init__()
        self.jsonl_path = jsonl_path
        self.class_to_idx = class_to_idx
        self.is_train = is_train
        self.image_size = image_size
        self.provenance_weights = provenance_weights or DEFAULT_PROVENANCE_WEIGHTS

        if transform is None:
            self.transform = get_default_transforms(image_size, is_train)
        else:
            self.transform = transform

        if not os.path.exists(jsonl_path):
            raise FileNotFoundError(f"Error: JSONL file not found at {jsonl_path}")

        records = []
        with open(jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    records.append(json.loads(line.strip()))

        if max_records and max_records > 0:
            if coverage_aware_sample:
                records = select_coverage_aware_subset(records, max_records=max_records)
            else:
                records = records[:max_records]

        self.records = records

    def __len__(self):
        return len(self.records)

    def load_and_crop_image(self, record):
        """Loads and crops parent garment from official source image or crop file."""
        crop_p = record.get("crop_path")
        if crop_p and os.path.exists(crop_p):
            try:
                with Image.open(crop_p) as img:
                    return img.convert("RGB")
            except Exception:
                pass

        source_p = record.get("source_image_path")
        if not source_p or not os.path.exists(source_p):
            raise FileNotFoundError(
                f"Error: Source image path missing for record {record.get('record_uid')}: {source_p}"
            )

        with Image.open(source_p) as img:
            img = img.convert("RGB")
            w, h = img.size
            bbox = record.get("bbox")

            if bbox and isinstance(bbox, (list, tuple)) and len(bbox) == 4:
                try:
                    bx, by, bw, bh = [float(v) for v in bbox]
                    if bw > 0 and bh > 0 and bx < w and by < h:
                        left = max(0, int(round(bx)))
                        top = max(0, int(round(by)))
                        right = min(w, int(round(bx + bw)))
                        bottom = min(h, int(round(by + bh)))
                        if (right - left) >= 8 and (bottom - top) >= 8:
                            img = img.crop((left, top, right, bottom))
                except Exception:
                    pass
            return img

    def __getitem__(self, idx):
        record = self.records[idx]
        image = self.load_and_crop_image(record)
        image_tensor = self.transform(image)

        labels = {}
        masks = {}
        sample_weights = {}

        for head in HEADS:
            mask = record.get("masks", {}).get(head, 0)
            lbl = record.get("labels", {}).get(head)
            prov = record.get("provenance", {}).get(head, "missing/masked")

            if mask == 1 and lbl is not None and lbl in self.class_to_idx[head]:
                labels[head] = torch.tensor(self.class_to_idx[head][lbl], dtype=torch.long)
                masks[head] = torch.tensor(1.0, dtype=torch.float32)
                weight = self.provenance_weights.get(prov, 1.0)
                sample_weights[head] = torch.tensor(weight, dtype=torch.float32)
            else:
                labels[head] = torch.tensor(0, dtype=torch.long)
                masks[head] = torch.tensor(0.0, dtype=torch.float32)
                sample_weights[head] = torch.tensor(0.0, dtype=torch.float32)

        return {
            "image": image_tensor,
            "labels": labels,
            "masks": masks,
            "sample_weights": sample_weights,
            "record_uid": record.get("record_uid"),
            "split": record.get("split"),
        }
