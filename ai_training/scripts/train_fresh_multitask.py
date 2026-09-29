#!/usr/bin/env python3
"""
train_fresh_multitask.py

Fresh Multi-Task Model Training Script for Milestone M14D.
- Output directory: ai_training/data/training_runs/m14d_fresh/
- Starting model: ONLY generic ImageNet pretrained backbone (yolov8n-cls.pt)
- Custom heads: 4 newly and randomly initialized linear heads (Kaiming Normal init)
- NO inheritance or loading from any previous custom checkpoint.
- Parameters: Up to 50 epochs, early stopping patience = 8.
- Loss configurations:
    A. Weighted Cross-Entropy (--loss-type weighted_ce)
    B. Focal Loss (--loss-type focal_loss)
"""

import argparse
import json
import os
import sys
import time
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader

sys.path.insert(0, os.path.abspath("."))

from ai_training.datasets.multitask_dataset import MultiTaskDataset, HEADS
from ai_training.models.fresh_multitask_yolov8 import FreshYOLOv8MultiTaskClassifier, HEAD_DIMS
from ai_training.training.metrics import MultiTaskMetricsTracker

CLASSES_JSON = "ai_training/config/classes.json"
GENERIC_BACKBONE_PATH = "backend/app/ai/models/yolov8n-cls.pt"
TRAIN_M14D_FINAL = "ai_training/data/final_multitask/train_m14d_final.jsonl"
VAL_M14D_FINAL = "ai_training/data/final_multitask/val_m14d_final.jsonl"
OUTPUT_BASE_DIR = "ai_training/data/training_runs/m14d_fresh"

class FocalLoss(nn.Module):
    def __init__(self, alpha=None, gamma=2.0, reduction="mean"):
        super().__init__()
        self.alpha = alpha
        self.gamma = gamma
        self.reduction = reduction

    def forward(self, logits, targets):
        ce_loss = F.cross_entropy(logits, targets, reduction="none", weight=self.alpha)
        pt = torch.exp(-ce_loss)
        focal_loss = ((1 - pt) ** self.gamma) * ce_loss

        if self.reduction == "mean":
            return focal_loss.mean()
        elif self.reduction == "sum":
            return focal_loss.sum()
        return focal_loss

def calculate_class_weights(dataset, class_to_idx, max_weight=5.0):
    weights_by_head = {}
    for h in HEADS:
        counts = [0] * len(class_to_idx[h])
        for rec in dataset.records:
            m = rec.get("masks", {}).get(h, 0)
            lbl = rec.get("labels", {}).get(h)
            if m == 1 and lbl in class_to_idx[h]:
                counts[class_to_idx[h][lbl]] += 1
        
        total = sum(counts)
        num_classes = len(counts)
        weights = []
        for c in counts:
            if c > 0:
                w = total / (num_classes * c)
            else:
                w = 1.0
            weights.append(min(w, max_weight))
        weights_by_head[h] = torch.tensor(weights, dtype=torch.float32)
    return weights_by_head

def train_fresh_experiment(exp_name, loss_type="focal_loss", max_epochs=50, patience=8, batch_size=16, lr=1e-4, seed=42):
    torch.manual_seed(seed)
    print(f"\n==================================================")
    print(f"MILESTONE M14D FRESH TRAINING EXPERIMENT: {exp_name}")
    print(f"Loss Type: {loss_type} | Max Epochs: {max_epochs} | Patience: {patience}")
    print(f"Manifests: {TRAIN_M14D_FINAL} | {VAL_M14D_FINAL}")
    print(f"==================================================")

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using compute device: {device}")

    with open(CLASSES_JSON, "r", encoding="utf-8") as f:
        classes_config = json.load(f)["outputs"]
        
    class_to_idx = {h: classes_config[h]["class_to_idx"] for h in HEADS}
    idx_to_class = {h: classes_config[h]["idx_to_class"] for h in HEADS}

    train_dataset = MultiTaskDataset(jsonl_path=TRAIN_M14D_FINAL, class_to_idx=class_to_idx, is_train=True, image_size=224)
    val_dataset = MultiTaskDataset(jsonl_path=VAL_M14D_FINAL, class_to_idx=class_to_idx, is_train=False, image_size=224)

    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True, drop_last=False)
    val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False)

    class_weights = calculate_class_weights(train_dataset, class_to_idx)
    for h in HEADS:
        class_weights[h] = class_weights[h].to(device)

    # Initialize BRAND NEW model starting ONLY from generic yolov8n-cls.pt
    model = FreshYOLOv8MultiTaskClassifier(generic_backbone_path=GENERIC_BACKBONE_PATH, head_dims=HEAD_DIMS)
    model.to(device)

    # Print weight checksums to verify zero custom weight inheritance
    init_checksums = model.compute_head_checksums()
    print("\nPROOF OF FRESH RANDOM HEAD INITIALIZATION:")
    for h_name, checksum in init_checksums.items():
        print(f"  - Head '{h_name}': SHA-256 = {checksum}")

    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)

    best_val_macro_f1 = -1.0
    best_epoch = 0
    patience_counter = 0
    exp_dir = os.path.join(OUTPUT_BASE_DIR, exp_name)
    os.makedirs(exp_dir, exist_ok=True)
    best_ckpt_path = os.path.join(exp_dir, "best.pt")

    history = []

    for epoch in range(1, max_epochs + 1):
        model.train()
        train_loss = 0.0

        for batch in train_loader:
            imgs = batch["image"].to(device)
            targets = {h: batch["labels"][h].to(device) for h in HEADS}
            masks = {h: batch["masks"][h].to(device) for h in HEADS}
            weights = {h: batch["sample_weights"][h].to(device) for h in HEADS}

            optimizer.zero_grad()
            logits_dict = model(imgs)
            total_loss = 0.0

            for h in HEADS:
                m = masks[h]
                if m.sum() > 0:
                    if loss_type == "focal_loss":
                        criterion = FocalLoss(alpha=class_weights[h], gamma=2.0, reduction="none")
                        h_loss = criterion(logits_dict[h], targets[h])
                    else:
                        h_loss = F.cross_entropy(logits_dict[h], targets[h], reduction="none", weight=class_weights[h])
                    
                    masked_loss = (h_loss * m * weights[h]).sum() / (m.sum() + 1e-6)
                    total_loss += masked_loss

            total_loss.backward()
            optimizer.step()
            train_loss += total_loss.item()

        # Validation phase
        model.eval()
        metrics_tracker = MultiTaskMetricsTracker(class_to_idx, idx_to_class)
        with torch.no_grad():
            for batch in val_loader:
                imgs = batch["image"].to(device)
                targets = {h: batch["labels"][h].to(device) for h in HEADS}
                masks = {h: batch["masks"][h].to(device) for h in HEADS}
                logits_dict = model(imgs)
                metrics_tracker.update(logits_dict, targets, masks)

        val_results = metrics_tracker.compute()
        val_f1s = [val_results[h]["macro_f1"] for h in HEADS if val_results[h]["evaluated_count"] > 0]
        mean_val_f1 = sum(val_f1s) / len(val_f1s) if val_f1s else 0.0

        avg_train_loss = train_loss / len(train_loader)
        print(f"Epoch {epoch:02d}/{max_epochs:02d} | Train Loss: {avg_train_loss:.4f} | Val Mean Macro-F1: {mean_val_f1:.4f}")

        epoch_entry = {
            "epoch": epoch,
            "train_loss": round(avg_train_loss, 4),
            "val_mean_macro_f1": round(mean_val_f1, 4),
            "head_metrics": {
                h: {
                    "accuracy": val_results[h]["accuracy"],
                    "macro_f1": val_results[h]["macro_f1"],
                    "per_class": val_results[h]["per_class"],
                    "confusion_matrix": val_results[h]["confusion_matrix"]
                }
                for h in HEADS
            }
        }
        history.append(epoch_entry)

        if mean_val_f1 > best_val_macro_f1:
            best_val_macro_f1 = mean_val_f1
            best_epoch = epoch
            patience_counter = 0
            save_dict = {
                "model_state_dict": model.state_dict(),
                "class_to_idx": class_to_idx,
                "idx_to_class": idx_to_class,
                "head_dimensions": HEAD_DIMS,
                "epoch": epoch,
                "val_macro_f1": mean_val_f1,
                "loss_type": loss_type,
                "initial_head_checksums": init_checksums,
                "generic_backbone": GENERIC_BACKBONE_PATH,
            }
            torch.save(save_dict, best_ckpt_path)
            print(f"  --> Saved new best checkpoint (Val F1: {mean_val_f1:.4f}) to {best_ckpt_path}")
        else:
            patience_counter += 1
            if patience_counter >= patience:
                print(f"\nEarly stopping triggered after {patience} epochs without validation improvement!")
                break

    with open(os.path.join(exp_dir, "training_history.json"), "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2)

    print(f"\n==================================================")
    print(f"EXPERIMENT {exp_name} COMPLETED.")
    print(f"Total Epochs Completed: {len(history)} | Best Epoch: {best_epoch}")
    print(f"Best Val Mean Macro-F1: {best_val_macro_f1:.4f}")
    print(f"==================================================")
    return best_ckpt_path, best_val_macro_f1

def main():
    parser = argparse.ArgumentParser(description="Train Fresh YOLOv8 Multi-Task Model for Milestone M14D")
    parser.add_argument("--loss-type", choices=["weighted_ce", "focal_loss"], default="focal_loss", help="Loss function variant")
    parser.add_argument("--exp-name", default="exp_b_focal", help="Experiment name directory")
    parser.add_argument("--epochs", type=int, default=50, help="Maximum training epochs")
    parser.add_argument("--patience", type=int, default=8, help="Early stopping patience")
    parser.add_argument("--lr", type=float, default=1e-4, help="Learning rate")
    args = parser.parse_args()

    train_fresh_experiment(
        exp_name=args.exp_name,
        loss_type=args.loss_type,
        max_epochs=args.epochs,
        patience=args.patience,
        lr=args.lr,
    )

if __name__ == "__main__":
    main()
