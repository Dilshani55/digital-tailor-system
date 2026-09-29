#!/usr/bin/env python3
"""
fresh_multitask_yolov8.py

Fresh YOLOv8 Multi-Task Classification Model for Milestone M14D.
- Loads ONLY the generic ImageNet pretrained classification backbone (yolov8n-cls.pt).
- Re-initializes all 4 custom linear classification heads from scratch using Kaiming Normal initialization:
    1. garment_type: 3 logits
    2. neckline_type: 10 logits
    3. sleeve_length: 6 logits
    4. sleeve_style: 9 logits
- DOES NOT load or inherit weights from any previous Digital Tailor custom checkpoint.
"""

import hashlib
import os
import torch
import torch.nn as nn
from ultralytics import YOLO

HEAD_DIMS = {
    "garment_type": 3,
    "neckline_type": 10,
    "sleeve_length": 6,
    "sleeve_style": 9,
}

class FreshYOLOv8MultiTaskClassifier(nn.Module):
    def __init__(
        self,
        generic_backbone_path: str = "backend/app/ai/models/yolov8n-cls.pt",
        head_dims: dict = None,
    ):
        super().__init__()
        if head_dims is None:
            head_dims = HEAD_DIMS

        self.generic_backbone_path = generic_backbone_path
        self.head_dims = head_dims

        # Fallback path check
        if not os.path.exists(generic_backbone_path):
            alt_path = "ai_training/data/training_runs/pretrained/yolov8n-cls.pt"
            if os.path.exists(alt_path):
                generic_backbone_path = alt_path
            else:
                raise FileNotFoundError(
                    f"Error: Pretrained generic backbone not found at {generic_backbone_path}"
                )

        print(f"[FreshYOLOv8MultiTaskClassifier] Loading GENERIC backbone from: {generic_backbone_path}")
        
        # Load generic YOLOv8 classification backbone
        yolo_wrapper = YOLO(generic_backbone_path)
        base_model = yolo_wrapper.model

        self.backbone = base_model.model[0:9]
        self.projection_conv = base_model.model[9].conv
        self.global_pool = base_model.model[9].pool
        self.dropout = base_model.model[9].drop
        self.embedding_dim = 1280

        # Construct and randomly initialize 4 fresh classification heads
        self.heads = nn.ModuleDict()
        for head_name, num_classes in head_dims.items():
            linear = nn.Linear(self.embedding_dim, num_classes)
            nn.init.kaiming_normal_(linear.weight, mode='fan_out', nonlinearity='relu')
            nn.init.zeros_(linear.bias)
            self.heads[head_name] = linear

        print("[FreshYOLOv8MultiTaskClassifier] All 4 custom heads initialized from scratch with Kaiming Normal!")

    def extract_features(self, x: torch.Tensor) -> torch.Tensor:
        feats = self.backbone(x)
        feats = self.projection_conv(feats)
        feats = self.global_pool(feats)
        feats = torch.flatten(feats, 1)
        feats = self.dropout(feats)
        return feats

    def forward(self, x: torch.Tensor) -> dict:
        feats = self.extract_features(x)
        return {
            head_name: head_module(feats)
            for head_name, head_module in self.heads.items()
        }

    def compute_head_checksums(self) -> dict:
        """Computes SHA-256 checksums of head weight matrices to prove fresh initialization."""
        checksums = {}
        for head_name, module in self.heads.items():
            w_bytes = module.weight.detach().cpu().numpy().tobytes()
            b_bytes = module.bias.detach().cpu().numpy().tobytes()
            h = hashlib.sha256(w_bytes + b_bytes).hexdigest()
            checksums[head_name] = h
        return checksums

if __name__ == "__main__":
    model = FreshYOLOv8MultiTaskClassifier()
    print("Head Weight Checksums (Fresh Random Init):", model.compute_head_checksums())
