#!/usr/bin/env python3
"""
multitask_yolov8.py

Single YOLOv8 Multi-Task Classification Model Architecture for Digital Tailor AI (Milestone M11).
- Reuses pretrained YOLOv8 classification backbone (layers 0-8) and 1280-dim projection layer (Classify.conv).
- Global pooling and dropout produce a 1280-dimensional shared feature embedding.
- Connects shared embedding to four task-specific linear classification heads:
  1. garment_type: 3 logits
  2. neckline_type: 10 logits
  3. sleeve_length: 6 logits
  4. sleeve_style: 9 logits
- Supports freezing shared backbone/projection weights for CPU smoke training.
"""

import os
import torch
import torch.nn as nn
from ultralytics import YOLO


DEFAULT_HEAD_DIMS = {
    "garment_type": 3,
    "neckline_type": 10,
    "sleeve_length": 6,
    "sleeve_style": 9,
}


class YOLOv8MultiTaskClassifier(nn.Module):
    def __init__(
        self,
        pretrained_path: str = "ai_training/data/training_runs/pretrained/yolov8n-cls.pt",
        head_dims: dict = None,
        freeze_backbone: bool = False,
    ):
        super().__init__()
        if head_dims is None:
            head_dims = DEFAULT_HEAD_DIMS

        self.pretrained_path = pretrained_path
        self.head_dims = head_dims

        if not os.path.exists(pretrained_path):
            raise FileNotFoundError(
                f"Error: Pretrained weights file not found at {pretrained_path}"
            )

        # Load pretrained classification model
        yolo_wrapper = YOLO(pretrained_path)
        base_model = yolo_wrapper.model

        # Extract shared feature backbone and 1280-dim projection components
        self.backbone = base_model.model[0:9]
        self.projection_conv = base_model.model[9].conv
        self.global_pool = base_model.model[9].pool
        self.dropout = base_model.model[9].drop

        self.embedding_dim = 1280

        # Construct four linear classification heads
        self.heads = nn.ModuleDict({
            head_name: nn.Linear(self.embedding_dim, num_classes)
            for head_name, num_classes in head_dims.items()
        })

        if freeze_backbone:
            self.freeze_backbone_weights()

    def freeze_backbone_weights(self):
        """Freezes shared backbone and projection layers."""
        for param in self.backbone.parameters():
            param.requires_grad = False
        for param in self.projection_conv.parameters():
            param.requires_grad = False

    def unfreeze_backbone_weights(self):
        """Unfreezes shared backbone and projection layers."""
        for param in self.backbone.parameters():
            param.requires_grad = True
        for param in self.projection_conv.parameters():
            param.requires_grad = True

    def extract_features(self, x: torch.Tensor) -> torch.Tensor:
        """Extracts 1280-dimensional shared feature embedding."""
        feats = self.backbone(x)
        feats = self.projection_conv(feats)
        feats = self.global_pool(feats)
        feats = torch.flatten(feats, 1)
        feats = self.dropout(feats)
        return feats

    def forward(self, x: torch.Tensor) -> dict:
        """
        Forward pass returning dictionary of task logits:
        {
            "garment_type": Tensor[B, 3],
            "neckline_type": Tensor[B, 10],
            "sleeve_length": Tensor[B, 6],
            "sleeve_style": Tensor[B, 9]
        }
        """
        feats = self.extract_features(x)
        return {
            head_name: head_module(feats)
            for head_name, head_module in self.heads.items()
        }

    def get_param_count(self) -> dict:
        """Returns parameter counts."""
        total_params = sum(p.numel() for p in self.parameters())
        trainable_params = sum(p.numel() for p in self.parameters() if p.requires_grad)
        frozen_params = total_params - trainable_params
        return {
            "total_params": total_params,
            "trainable_params": trainable_params,
            "frozen_params": frozen_params,
        }
