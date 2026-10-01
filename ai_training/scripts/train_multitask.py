#!/usr/bin/env python3
"""
train_multitask.py

Full Staged Training Script for Milestone M12 Single YOLOv8 Multi-Task Model.
- Stage A (Head Warm-up): 3 epochs, shared backbone frozen, head LR = 0.001.
- Stage B (Partial Fine-Tuning): 12 epochs, unfreezes final backbone stage (layer 8 + projection) keeping early layers (0-7) frozen. Differential LRs: backbone LR = 0.0001, head LR = 0.0005.
- Capped train-split class weights (cap = 5.0) and provenance sample weights.
- Early stopping patience = 4 epochs monitored on supported validation mean macro-F1 score.
- Saves stage_a_best.pt, best.pt, last.pt, training_history.csv/json, class_weights.json, environment_info.json, m12_summary.json.
- Supports resuming training from last.pt with --resume.
"""

import argparse
import copy
import csv
import json
import math
import os
import platform
import random
import shutil
import sys
import time
import torch
import torch.optim as optim
from torch.utils.data import DataLoader

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from ai_training.datasets.multitask_dataset_v2 import MultiTaskDatasetV2
from ai_training.datasets.multitask_dataset import MultiTaskDataset, HEADS
from ai_training.models.multitask_yolov8 import YOLOv8MultiTaskClassifier
from ai_training.training.masked_loss import MaskedMultiTaskLoss, compute_capped_class_weights
from ai_training.training.metrics import MultiTaskMetricsTracker


def parse_args():
    parser = argparse.ArgumentParser(description="Full Staged Training for Single YOLOv8 Multi-Task Model (Milestone M12)")
    parser.add_argument("--config", default="ai_training/config/m12_training_config.json", help="Path to m12_training_config.json")
    parser.add_argument("--classes", default="ai_training/config/classes.json", help="Path to classes.json")
    parser.add_argument("--train-manifest", default="ai_training/data/final_multitask/train.jsonl", help="Path to train.jsonl")
    parser.add_argument("--val-manifest", default="ai_training/data/final_multitask/val.jsonl", help="Path to val.jsonl")
    parser.add_argument("--output-dir", default="ai_training/data/training_runs/m12_full", help="Directory to store full training outputs")
    parser.add_argument("--smoke-test", action="store_true", default=False, help="Perform 1-epoch smoke run")
    parser.add_argument("--focal-gamma", type=float, default=0.0, help="Focal-loss gamma (0 = class-weighted cross-entropy)")
    parser.add_argument("--resume", action="store_true", default=False, help="Resume training from last.pt checkpoint")
    return parser.parse_args()


def _sha256(path):
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


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


def record_environment_info(output_log_dir, pretrained_path):
    """Records preflight environment details and system specs."""
    import psutil
    import ultralytics

    env_info = {
        "python_version": platform.python_version(),
        "pytorch_version": torch.__version__,
        "ultralytics_version": ultralytics.__version__,
        "platform_system": platform.system(),
        "platform_processor": platform.processor() or platform.machine(),
        "cpu_count": os.cpu_count(),
        "ram_gb": round(psutil.virtual_memory().total / (1024 ** 3), 2),
        "free_disk_space_gb": round(shutil.disk_usage(".").free / (1024 ** 3), 2),
        "pretrained_weights_path": pretrained_path,
        "pretrained_weights_exists": os.path.exists(pretrained_path),
        "cuda_available": torch.cuda.is_available(),
    }

    os.makedirs(output_log_dir, exist_ok=True)
    info_path = os.path.join(output_log_dir, "environment_info.json")
    with open(info_path, "w", encoding="utf-8") as f:
        json.dump(env_info, f, indent=2)
    print(f"Preflight environment info recorded to {info_path}.")
    return env_info


def compute_supported_mean_macro_f1(val_metrics):
    """Computes mean macro-F1 across supported validation heads."""
    supported_f1s = []
    for h in HEADS:
        cnt = val_metrics[h].get("evaluated_count", 0)
        f1 = val_metrics[h].get("macro_f1")
        if cnt > 0 and isinstance(f1, (int, float)):
            supported_f1s.append(f1)
    return round(sum(supported_f1s) / len(supported_f1s), 4) if supported_f1s else 0.0


def save_checkpoint(
    path: str,
    model: torch.nn.Module,
    optimizer: optim.Optimizer,
    epoch: int,
    stage: str,
    config: dict,
    class_to_idx: dict,
    idx_to_class: dict,
    val_metrics: dict,
    selection_score: float,
):
    """Saves checkpoint with mandatory M12 metadata."""
    os.makedirs(os.path.dirname(path), exist_ok=True)

    head_dims = getattr(model, "head_dims", {h: len(class_to_idx[h]) for h in HEADS})
    pretrained_id = config.get("pretrained_backbone_identifier", "yolov8n-cls")
    seed = config.get("random_seed", 42)

    checkpoint = {
        "epoch": epoch,
        "stage": stage,
        "model_state_dict": model.state_dict(),
        "optimizer_state_dict": optimizer.state_dict(),
        "config": config,
        "class_to_idx": class_to_idx,
        "idx_to_class": idx_to_class,
        "head_dimensions": head_dims,
        "val_metrics": val_metrics,
        "selection_score": selection_score,
        "pretrained_backbone_identifier": pretrained_id,
        "random_seed": seed,
    }
    torch.save(checkpoint, path)
    print(f"Saved [{stage}] checkpoint to {path} (Epoch={epoch}, Score={selection_score:.4f}, Size={os.path.getsize(path)/(1024*1024):.2f} MB).")


def write_history_csv(csv_path, history):
    """Writes training history to CSV file."""
    if not history:
        return
    fieldnames = ["stage", "epoch", "train_loss", "val_loss", "supported_mean_val_macro_f1"]
    for h in HEADS:
        fieldnames.append(f"{h}_train_loss")
        fieldnames.append(f"{h}_val_acc")
        fieldnames.append(f"{h}_val_f1")

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for rec in history:
            row = {
                "stage": rec["stage"],
                "epoch": rec["epoch"],
                "train_loss": rec["train_loss"],
                "val_loss": rec["val_loss"],
                "supported_mean_val_macro_f1": rec["supported_mean_val_macro_f1"],
            }
            for h in HEADS:
                row[f"{h}_train_loss"] = rec["train_head_losses"].get(h, 0.0)
                row[f"{h}_val_acc"] = rec["val_metrics"].get(h, {}).get("accuracy", 0.0)
                row[f"{h}_val_f1"] = rec["val_metrics"].get(h, {}).get("macro_f1", 0.0)
            writer.writerow(row)


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

    pretrained_path = config.get("pretrained_path", "ai_training/data/training_runs/pretrained/yolov8n-cls.pt")
    record_environment_info(log_dir, pretrained_path)

    is_smoke = args.smoke_test
    max_train = config.get("smoke_train_records", 256) if is_smoke else None
    max_val = config.get("smoke_val_records", 128) if is_smoke else None

    stage_a_epochs = 1 if is_smoke else config.get("stage_a_epochs", 3)
    stage_b_epochs = 0 if is_smoke else config.get("stage_b_epochs", 12)
    total_max_epochs = stage_a_epochs + stage_b_epochs

    print(f"\n==================================================")
    print(f"DIGITAL TAILOR M12 FULL STAGED TRAINING")
    print(f"==================================================")
    print(f"Stage A (Warm-up) Epochs: {stage_a_epochs} | Head LR: {config.get('stage_a_head_lr', 0.001)}")
    print(f"Stage B (Fine-tuning) Epochs: {stage_b_epochs} | Backbone LR: {config.get('stage_b_backbone_lr', 0.0001)} | Head LR: {config.get('stage_b_head_lr', 0.0005)}")
    print(f"Batch Size: {config.get('batch_size', 16)} | Image Size: {config.get('image_size', 224)}")

    # Datasets
    _Cls = MultiTaskDatasetV2 if config.get("full_image_prob") is not None else MultiTaskDataset
    _extra_train = {"full_image_prob": config["full_image_prob"]} if _Cls is MultiTaskDatasetV2 else {}
    train_dataset = _Cls(
        jsonl_path=args.train_manifest,
        class_to_idx=class_to_idx,
        is_train=True,
        max_records=max_train,
        coverage_aware_sample=is_smoke,
        provenance_weights=config.get("provenance_weights"),
        image_size=config.get("image_size", 224),
        augmentation=config.get("augmentation", "basic"),
        **_extra_train,
    )

    val_dataset = _Cls(
        jsonl_path=args.val_manifest,
        class_to_idx=class_to_idx,
        is_train=False,
        max_records=max_val,
        coverage_aware_sample=False,
        provenance_weights=config.get("provenance_weights"),
        image_size=config.get("image_size", 224),
    )

    # Class Weights
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

    batch_size = config.get("batch_size", 16)
    num_workers = config.get("num_workers", 0)

    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True, num_workers=num_workers)
    val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False, num_workers=num_workers)

    device = torch.device("cuda" if torch.cuda.is_available() and config.get("device") != "cpu" else "cpu")
    print(f"Execution Device: {device}")

    # Build Model
    model = YOLOv8MultiTaskClassifier(
        pretrained_path=pretrained_path,
        head_dims=head_dims,
        freeze_backbone=True,
    ).to(device)

    criterion = MaskedMultiTaskLoss(class_weights=class_weights_dict, focal_gamma=args.focal_gamma)
    metrics_tracker = MultiTaskMetricsTracker(class_to_idx, idx_to_class)

    history = []
    best_stage_a_score = -1.0
    best_overall_score = -1.0
    patience = config.get("early_stopping_patience", 4)
    patience_counter = 0

    start_time = time.time()

    # Stage A: Head Warm-up
    print(f"\n--- Entering Stage A: Head Warm-up (Epochs 1..{stage_a_epochs}) ---")
    model.freeze_backbone_weights()

    head_params = [p for p in model.heads.parameters() if p.requires_grad]
    optimizer = optim.AdamW(head_params, lr=config.get("stage_a_head_lr", 0.001), weight_decay=config.get("weight_decay", 0.0001))

    for epoch in range(1, stage_a_epochs + 1):
        model.train()
        train_loss = 0.0
        head_train_losses = {h: 0.0 for h in HEADS}
        num_batches = 0

        for batch in train_loader:
            images = batch["image"].to(device)
            targets = {h: batch["labels"][h].to(device) for h in HEADS}
            masks = {h: batch["masks"][h].to(device) for h in HEADS}
            sample_weights = {h: batch["sample_weights"][h].to(device) for h in HEADS}

            optimizer.zero_grad()
            logits_dict = model(images)
            loss, head_losses = criterion(logits_dict, targets, masks, sample_weights)

            if math.isnan(loss.item()) or math.isinf(loss.item()):
                raise ValueError(f"CRITICAL ERROR: Stage A Loss became NaN or Inf at epoch {epoch}!")

            if loss.requires_grad and loss.item() > 0:
                loss.backward()
                optimizer.step()

            train_loss += loss.item()
            for h in HEADS:
                head_train_losses[h] += head_losses.get(h, 0.0)
            num_batches += 1

        avg_train_loss = train_loss / max(1, num_batches)
        avg_head_train_losses = {h: round(head_train_losses[h] / max(1, num_batches), 4) for h in HEADS}

        # Validation
        model.eval()
        val_loss = 0.0
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
                val_batches += 1
                metrics_tracker.update(logits_dict, targets, masks)

        avg_val_loss = val_loss / max(1, val_batches)
        val_metrics = metrics_tracker.compute()
        mean_macro_f1 = compute_supported_mean_macro_f1(val_metrics)

        print(f"Stage A - Epoch {epoch}/{stage_a_epochs} - Train Loss: {avg_train_loss:.4f}, Val Loss: {avg_val_loss:.4f}, Val Mean Macro-F1: {mean_macro_f1:.4f}")

        rec = {
            "stage": "Stage_A",
            "epoch": epoch,
            "train_loss": round(avg_train_loss, 4),
            "val_loss": round(avg_val_loss, 4),
            "supported_mean_val_macro_f1": mean_macro_f1,
            "train_head_losses": avg_head_train_losses,
            "val_metrics": val_metrics,
        }
        history.append(rec)

        last_ckpt = os.path.join(ckpt_dir, "last.pt")
        save_checkpoint(last_ckpt, model, optimizer, epoch, "Stage_A", config, class_to_idx, idx_to_class, val_metrics, mean_macro_f1)

        if mean_macro_f1 > best_stage_a_score:
            best_stage_a_score = mean_macro_f1
            best_overall_score = mean_macro_f1
            stage_a_best_ckpt = os.path.join(ckpt_dir, "stage_a_best.pt")
            save_checkpoint(stage_a_best_ckpt, model, optimizer, epoch, "Stage_A", config, class_to_idx, idx_to_class, val_metrics, mean_macro_f1)
            best_ckpt = os.path.join(ckpt_dir, "best.pt")
            save_checkpoint(best_ckpt, model, optimizer, epoch, "Stage_A", config, class_to_idx, idx_to_class, val_metrics, mean_macro_f1)

    # Stage B: Partial Fine-Tuning
    if stage_b_epochs > 0:
        print(f"\n--- Entering Stage B: Partial Fine-Tuning (Epochs {stage_a_epochs + 1}..{total_max_epochs}) ---")
        stage_a_best_ckpt = os.path.join(ckpt_dir, "stage_a_best.pt")
        if os.path.exists(stage_a_best_ckpt):
            ckpt = torch.load(stage_a_best_ckpt, map_location=device)
            model.load_state_dict(ckpt["model_state_dict"])
            print(f"Loaded best Stage A model state from {stage_a_best_ckpt}.")

        model.unfreeze_partial_backbone(config.get("stage_b_unfreeze_from", 8))
        param_info = model.get_param_count()
        print(f"Stage B Parameters: Total={param_info['total_params']:,}, Trainable={param_info['trainable_params']:,}, Frozen={param_info['frozen_params']:,}")

        param_groups = model.get_parameter_groups(
            backbone_lr=config.get("stage_b_backbone_lr", 0.0001),
            head_lr=config.get("stage_b_head_lr", 0.0005),
            weight_decay=config.get("weight_decay", 0.0001),
        )
        optimizer = optim.AdamW(param_groups)

        for epoch_offset in range(1, stage_b_epochs + 1):
            epoch = stage_a_epochs + epoch_offset
            model.train()
            train_loss = 0.0
            head_train_losses = {h: 0.0 for h in HEADS}
            num_batches = 0

            for batch in train_loader:
                images = batch["image"].to(device)
                targets = {h: batch["labels"][h].to(device) for h in HEADS}
                masks = {h: batch["masks"][h].to(device) for h in HEADS}
                sample_weights = {h: batch["sample_weights"][h].to(device) for h in HEADS}

                optimizer.zero_grad()
                logits_dict = model(images)
                loss, head_losses = criterion(logits_dict, targets, masks, sample_weights)

                if math.isnan(loss.item()) or math.isinf(loss.item()):
                    raise ValueError(f"CRITICAL ERROR: Stage B Loss became NaN or Inf at epoch {epoch}!")

                if loss.requires_grad and loss.item() > 0:
                    loss.backward()
                    optimizer.step()

                train_loss += loss.item()
                for h in HEADS:
                    head_train_losses[h] += head_losses.get(h, 0.0)
                num_batches += 1

            avg_train_loss = train_loss / max(1, num_batches)
            avg_head_train_losses = {h: round(head_train_losses[h] / max(1, num_batches), 4) for h in HEADS}

            # Validation
            model.eval()
            val_loss = 0.0
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
                    val_batches += 1
                    metrics_tracker.update(logits_dict, targets, masks)

            avg_val_loss = val_loss / max(1, val_batches)
            val_metrics = metrics_tracker.compute()
            mean_macro_f1 = compute_supported_mean_macro_f1(val_metrics)

            print(f"Stage B - Epoch {epoch}/{total_max_epochs} - Train Loss: {avg_train_loss:.4f}, Val Loss: {avg_val_loss:.4f}, Val Mean Macro-F1: {mean_macro_f1:.4f}")

            rec = {
                "stage": "Stage_B",
                "epoch": epoch,
                "train_loss": round(avg_train_loss, 4),
                "val_loss": round(avg_val_loss, 4),
                "supported_mean_val_macro_f1": mean_macro_f1,
                "train_head_losses": avg_head_train_losses,
                "val_metrics": val_metrics,
            }
            history.append(rec)

            last_ckpt = os.path.join(ckpt_dir, "last.pt")
            save_checkpoint(last_ckpt, model, optimizer, epoch, "Stage_B", config, class_to_idx, idx_to_class, val_metrics, mean_macro_f1)

            if mean_macro_f1 > best_overall_score:
                best_overall_score = mean_macro_f1
                patience_counter = 0
                best_ckpt = os.path.join(ckpt_dir, "best.pt")
                save_checkpoint(best_ckpt, model, optimizer, epoch, "Stage_B", config, class_to_idx, idx_to_class, val_metrics, mean_macro_f1)
                best_val_metrics = val_metrics
                with open(os.path.join(log_dir, "val_metrics_best.json"), "w", encoding="utf-8") as f:
                    json.dump({"epoch": epoch, "selection_score": mean_macro_f1, "val_metrics": val_metrics}, f, indent=2)
            else:
                patience_counter += 1
                print(f"Patience counter: {patience_counter}/{patience}")
                if patience_counter >= patience:
                    print(f"Early stopping triggered at Stage B epoch {epoch} (no improvement for {patience} epochs).")
                    break

    elapsed = time.time() - start_time

    # Save history
    write_history_csv(os.path.join(log_dir, "training_history.csv"), history)
    with open(os.path.join(log_dir, "training_history.json"), "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2)

    # Save M12 Summary
    m12_summary = {
        "model_architecture": "YOLOv8MultiTaskClassifier",
        "pretrained_backbone": pretrained_path,
        "pretrained_backbone_identifier": config.get("pretrained_backbone_identifier", "yolov8n-cls"),
        "random_seed": seed,
        "loss": "focal" if args.focal_gamma > 0 else "class_weighted_cross_entropy",
        "focal_gamma": args.focal_gamma,
        "augmentation": config.get("augmentation", "basic"),
        "config_path": args.config,
        "train_manifest_sha256": _sha256(args.train_manifest),
        "val_manifest_sha256": _sha256(args.val_manifest),
        "device": str(device),
        "total_duration_seconds": round(elapsed, 2),
        "stage_a_epochs_completed": min(stage_a_epochs, len([r for r in history if r["stage"] == "Stage_A"])),
        "stage_b_epochs_completed": len([r for r in history if r["stage"] == "Stage_B"]),
        "total_epochs_completed": len(history),
        "best_selection_score_val_macro_f1": best_overall_score,
        "train_record_count": len(train_dataset),
        "val_record_count": len(val_dataset),
        "checkpoints": {
            "stage_a_best": os.path.join(ckpt_dir, "stage_a_best.pt"),
            "best": os.path.join(ckpt_dir, "best.pt"),
            "last": os.path.join(ckpt_dir, "last.pt"),
        },
    }

    with open(os.path.join(log_dir, "m12_summary.json"), "w", encoding="utf-8") as f:
        json.dump(m12_summary, f, indent=2)

    print(f"\n==================================================")
    print(f"M12 FULL STAGED TRAINING COMPLETED in {elapsed:.2f}s")
    print(f"Best Validation Mean Macro-F1: {best_overall_score:.4f}")
    print(f"==================================================")


if __name__ == "__main__":
    run_training()
