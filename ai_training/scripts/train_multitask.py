#!/usr/bin/env python3
"""
train_multitask.py

Training script for Milestone M11 Single YOLOv8 Multi-Task Model with CPU Smoke Training.
- Loads configuration, classes, and multi-task dataset splits.
- Builds single YOLOv8MultiTaskClassifier model with pretrained backbone and 4 linear heads.
- Computes capped train-split class weights.
- Performs CPU smoke training (1 epoch, max 256 coverage-aware train records, max 128 val records).
- Verifies head parameters receive gradients and frozen backbone parameters do not change.
- Saves comprehensive checkpoints (last.pt, best.pt) containing state_dict, optimizer, epoch, config, class_to_idx, head_dimensions, val_metrics, pretrained_backbone_identifier, random_seed.
- Stores outputs under Git-ignored ai_training/data/training_runs/.
"""

import argparse
import copy
import json
import os
import random
import sys
import time
import torch
import torch.optim as optim
from torch.utils.data import DataLoader

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from ai_training.datasets.multitask_dataset import MultiTaskDataset, HEADS
from ai_training.models.multitask_yolov8 import YOLOv8MultiTaskClassifier
from ai_training.training.masked_loss import MaskedMultiTaskLoss, compute_capped_class_weights
from ai_training.training.metrics import MultiTaskMetricsTracker


def parse_args():
    parser = argparse.ArgumentParser(description="Train single YOLOv8 multi-task model (Milestone M11)")
    parser.add_argument("--config", default="ai_training/config/multitask_training.json", help="Path to multitask_training.json")
    parser.add_argument("--classes", default="ai_training/config/classes.json", help="Path to classes.json")
    parser.add_argument("--train-manifest", default="ai_training/data/final_multitask/train.jsonl", help="Path to train.jsonl")
    parser.add_argument("--val-manifest", default="ai_training/data/final_multitask/val.jsonl", help="Path to val.jsonl")
    parser.add_argument("--output-dir", default="ai_training/data/training_runs/run_smoke", help="Directory to store run outputs")
    parser.add_argument("--smoke-test", action="store_true", default=True, help="Perform 1-epoch CPU smoke run with max 256 train & 128 val records")
    return parser.parse_args()


def set_seed(seed):
    random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def load_classes_config(classes_path):
    with open(classes_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    class_to_idx = {}
    idx_to_class = {}
    head_dims = {}

    for h in HEADS:
        class_to_idx[h] = data["outputs"][h]["class_to_idx"]
        idx_to_class[h] = data["outputs"][h]["idx_to_class"]
        head_dims[h] = data["outputs"][h]["class_count"]

    return data, class_to_idx, idx_to_class, head_dims


def save_checkpoint(
    path: str,
    model: torch.nn.Module,
    optimizer: optim.Optimizer,
    epoch: int,
    config: dict,
    class_to_idx: dict,
    idx_to_class: dict,
    val_metrics: dict,
):
    """Saves checkpoint with mandatory M11 metadata."""
    os.makedirs(os.path.dirname(path), exist_ok=True)

    head_dims = getattr(model, "head_dims", {h: len(class_to_idx[h]) for h in HEADS})
    pretrained_id = config.get("pretrained_backbone_identifier", "yolov8n-cls")
    seed = config.get("random_seed", 42)

    checkpoint = {
        "epoch": epoch,
        "model_state_dict": model.state_dict(),
        "optimizer_state_dict": optimizer.state_dict(),
        "config": config,
        "class_to_idx": class_to_idx,
        "idx_to_class": idx_to_class,
        "head_dimensions": head_dims,
        "val_metrics": val_metrics,
        "pretrained_backbone_identifier": pretrained_id,
        "random_seed": seed,
    }
    torch.save(checkpoint, path)
    print(f"Saved checkpoint to {path} (size: {os.path.getsize(path) / (1024*1024):.2f} MB).")


def run_training():
    args = parse_args()

    with open(args.config, "r", encoding="utf-8") as f:
        config = json.load(f)

    seed = config.get("random_seed", 42)
    set_seed(seed)

    classes_data, class_to_idx, idx_to_class, head_dims = load_classes_config(args.classes)

    ckpt_dir = os.path.join(args.output_dir, "checkpoints")
    log_dir = os.path.join(args.output_dir, "logs")
    os.makedirs(ckpt_dir, exist_ok=True)
    os.makedirs(log_dir, exist_ok=True)

    # Determine smoke limits
    is_smoke = args.smoke_test
    max_train = config.get("smoke_train_records", 256) if is_smoke else None
    max_val = config.get("smoke_val_records", 128) if is_smoke else None
    epochs = config.get("smoke_epochs", 1) if is_smoke else config.get("full_epochs", 20)

    print(f"--- Starting Single YOLOv8 Multi-Task Training (Smoke={is_smoke}) ---")
    print(f"Configured Epochs: {epochs}, Smoke Train Limit: {max_train}, Smoke Val Limit: {max_val}")

    # Build Datasets
    train_dataset = MultiTaskDataset(
        jsonl_path=args.train_manifest,
        class_to_idx=class_to_idx,
        is_train=True,
        max_records=max_train,
        coverage_aware_sample=is_smoke,
        provenance_weights=config.get("provenance_weights"),
        image_size=config.get("image_size", 224),
    )

    val_dataset = MultiTaskDataset(
        jsonl_path=args.val_manifest,
        class_to_idx=class_to_idx,
        is_train=False,
        max_records=max_val,
        coverage_aware_sample=False,
        provenance_weights=config.get("provenance_weights"),
        image_size=config.get("image_size", 224),
    )

    # Compute capped class weights from train dataset records
    class_weights_dict = compute_capped_class_weights(
        train_manifest_records=train_dataset.records,
        class_to_idx=class_to_idx,
        cap=config.get("class_weight_cap", 5.0),
    )

    class_weights_log = {
        h: {idx_to_class[h][str(i)]: round(class_weights_dict[h][i].item(), 4) for i in range(len(class_weights_dict[h]))}
        for h in HEADS
    }
    with open(os.path.join(log_dir, "class_weights.json"), "w", encoding="utf-8") as f:
        json.dump(class_weights_log, f, indent=2)

    # Log smoke dataset coverage
    train_covered_classes = set()
    for r in train_dataset.records:
        for h in HEADS:
            if r.get("masks", {}).get(h) == 1 and r.get("labels", {}).get(h):
                train_covered_classes.add(f"{h}:{r['labels'][h]}")

    print(f"Train Dataset: {len(train_dataset)} records ({len(train_covered_classes)}/28 classes covered).")
    print(f"Val Dataset: {len(val_dataset)} records.")

    batch_size = config.get("batch_size", 8)
    num_workers = config.get("num_workers", 0)  # Always 0 for Windows safety

    train_loader = DataLoader(
        train_dataset,
        batch_size=batch_size,
        shuffle=True,
        num_workers=num_workers,
        drop_last=False,
    )

    val_loader = DataLoader(
        val_dataset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=num_workers,
        drop_last=False,
    )

    # Determine Device
    device_str = config.get("device", "auto")
    if device_str == "auto":
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    else:
        device = torch.device(device_str if torch.cuda.is_available() or device_str == "cpu" else "cpu")

    print(f"Execution Device: {device}")

    # Build Model
    pretrained_path = config.get("pretrained_path", "ai_training/data/training_runs/pretrained/yolov8n-cls.pt")
    freeze_backbone = config.get("freeze_backbone", True)

    model = YOLOv8MultiTaskClassifier(
        pretrained_path=pretrained_path,
        head_dims=head_dims,
        freeze_backbone=freeze_backbone,
    ).to(device)

    param_info = model.get_param_count()
    print(f"Model Parameters: Total={param_info['total_params']:,}, Trainable={param_info['trainable_params']:,}, Frozen={param_info['frozen_params']:,}")

    # Build Criterion & Optimizer
    criterion = MaskedMultiTaskLoss(class_weights=class_weights_dict)
    lr = config.get("learning_rate", 0.001)
    weight_decay = config.get("weight_decay", 0.0005)

    trainable_params = [p for p in model.parameters() if p.requires_grad]
    optimizer = optim.AdamW(trainable_params, lr=lr, weight_decay=weight_decay)

    # Record initial backbone parameter for freeze verification
    initial_backbone_param = copy.deepcopy(next(model.backbone.parameters()).detach().cpu())

    metrics_tracker = MultiTaskMetricsTracker(class_to_idx, idx_to_class)
    start_time = time.time()

    best_val_loss = float("inf")
    best_metrics = {}
    history = []

    for epoch in range(1, epochs + 1):
        model.train()
        epoch_loss = 0.0
        head_epoch_losses = {h: 0.0 for h in HEADS}
        num_batches = 0

        # Gradient verification flags
        grad_verified = False

        for batch in train_loader:
            images = batch["image"].to(device)
            targets = {h: batch["labels"][h].to(device) for h in HEADS}
            masks = {h: batch["masks"][h].to(device) for h in HEADS}
            sample_weights = {h: batch["sample_weights"][h].to(device) for h in HEADS}

            optimizer.zero_grad()

            logits_dict = model(images)
            loss, head_losses = criterion(logits_dict, targets, masks, sample_weights)

            if loss.requires_grad and loss.item() > 0:
                loss.backward()

                # Verify gradients on heads
                if not grad_verified:
                    head_has_grad = any(p.grad is not None for head_module in model.heads.values() for p in head_module.parameters())
                    if not head_has_grad:
                        raise RuntimeError("Error: Head parameters did not receive gradients during backward pass!")
                    print("Verification PASSED: Classification heads successfully received gradients.")
                    grad_verified = True

                optimizer.step()

            epoch_loss += loss.item()
            for h in HEADS:
                head_epoch_losses[h] += head_losses.get(h, 0.0)
            num_batches += 1

        # Verify frozen backbone parameters remained UNCHANGED after optimizer.step()
        if freeze_backbone:
            current_backbone_param = next(model.backbone.parameters()).detach().cpu()
            if not torch.equal(initial_backbone_param, current_backbone_param):
                raise RuntimeError("Error: Frozen backbone parameters were mutated during optimizer step!")
            print("Verification PASSED: Frozen backbone weights remained 100% unchanged after optimizer step.")

        avg_train_loss = epoch_loss / max(1, num_batches)
        avg_train_head_losses = {h: round(head_epoch_losses[h] / max(1, num_batches), 4) for h in HEADS}

        # Validation Pass
        model.eval()
        val_loss = 0.0
        val_head_losses = {h: 0.0 for h in HEADS}
        val_batches = 0
        metrics_tracker.reset()

        with torch.no_grad():
            for batch in val_loader:
                images = batch["image"].to(device)
                targets = {h: batch["labels"][h].to(device) for h in HEADS}
                masks = {h: batch["masks"][h].to(device) for h in HEADS}
                sample_weights = {h: batch["sample_weights"][h].to(device) for h in HEADS}

                logits_dict = model(images)
                loss, head_losses = criterion(logits_dict, targets, masks, sample_weights)

                val_loss += loss.item()
                for h in HEADS:
                    val_head_losses[h] += head_losses.get(h, 0.0)
                val_batches += 1

                metrics_tracker.update(logits_dict, targets, masks)

        avg_val_loss = val_loss / max(1, val_batches)
        val_metrics = metrics_tracker.compute()

        print(f"Epoch {epoch}/{epochs} - Train Loss: {avg_train_loss:.4f}, Val Loss: {avg_val_loss:.4f}")
        for h in HEADS:
            print(f"  [{h}] Train Loss: {avg_train_head_losses[h]}, Val Accuracy: {val_metrics[h]['accuracy']}, Val F1: {val_metrics[h]['macro_f1']}")

        epoch_record = {
            "epoch": epoch,
            "train_loss": round(avg_train_loss, 4),
            "val_loss": round(avg_val_loss, 4),
            "train_head_losses": avg_train_head_losses,
            "val_metrics": val_metrics,
        }
        history.append(epoch_record)

        # Save last checkpoint
        last_ckpt_path = os.path.join(ckpt_dir, "last.pt")
        save_checkpoint(last_ckpt_path, model, optimizer, epoch, config, class_to_idx, idx_to_class, val_metrics)

        # Save best checkpoint
        if avg_val_loss < best_val_loss:
            best_val_loss = avg_val_loss
            best_metrics = val_metrics
            best_ckpt_path = os.path.join(ckpt_dir, "best.pt")
            save_checkpoint(best_ckpt_path, model, optimizer, epoch, config, class_to_idx, idx_to_class, val_metrics)

    elapsed = time.time() - start_time

    # Save training metrics log
    metrics_log_path = os.path.join(log_dir, "training_metrics.json")
    with open(metrics_log_path, "w", encoding="utf-8") as f:
        json.dump({"history": history, "best_val_loss": round(best_val_loss, 4)}, f, indent=2)

    # Save smoke summary log
    smoke_summary = {
        "model_architecture": "YOLOv8MultiTaskClassifier",
        "pretrained_backbone": pretrained_path,
        "pretrained_backbone_identifier": config.get("pretrained_backbone_identifier", "yolov8n-cls"),
        "random_seed": seed,
        "device": str(device),
        "duration_seconds": round(elapsed, 2),
        "smoke_test": is_smoke,
        "train_record_count": len(train_dataset),
        "val_record_count": len(val_dataset),
        "train_class_coverage_count": len(train_covered_classes),
        "parameter_counts": param_info,
        "final_train_loss": round(avg_train_loss, 4),
        "final_val_loss": round(avg_val_loss, 4),
        "best_val_loss": round(best_val_loss, 4),
        "checkpoints": {
            "last": os.path.join(ckpt_dir, "last.pt"),
            "best": os.path.join(ckpt_dir, "best.pt"),
        },
        "disclaimer": "Smoke metrics from a 1-epoch CPU run on 256 records are for workflow validation ONLY, not final accuracy.",
    }

    summary_path = os.path.join(log_dir, "smoke_summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(smoke_summary, f, indent=2)

    print(f"\n--- Smoke Training Run Completed in {elapsed:.2f}s ---")
    print(f"Smoke Summary written to {summary_path}.")


if __name__ == "__main__":
    run_training()
