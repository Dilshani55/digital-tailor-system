#!/usr/bin/env python3
"""
evaluate_multitask.py

Evaluation and Single-Image Crop Inference Script for Digital Tailor AI (Milestone M11).
- Loads saved checkpoint (.pt file) and verifies mandatory metadata.
- Re-instantiates single YOLOv8MultiTaskClassifier model and reloads weights.
- Evaluates dataset manifest (val.jsonl / test.jsonl) computing per-head metrics.
- Runs single real-image garment crop inference, outputting four head predictions, confidence scores, and tensor shapes.
"""

import argparse
import json
import os
import sys
import torch
import torch.nn.functional as F
from PIL import Image
from torchvision import transforms

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from ai_training.datasets.multitask_dataset import MultiTaskDataset, get_default_transforms, HEADS
from ai_training.models.multitask_yolov8 import YOLOv8MultiTaskClassifier
from ai_training.training.metrics import MultiTaskMetricsTracker


def parse_args():
    parser = argparse.ArgumentParser(description="Evaluate multi-task model and run single-image crop inference")
    parser.add_argument("--checkpoint", default="ai_training/data/training_runs/run_smoke/checkpoints/best.pt", help="Path to checkpoint .pt file")
    parser.add_argument("--manifest", default="ai_training/data/final_multitask/val.jsonl", help="Path to evaluation JSONL manifest")
    parser.add_argument("--classes", default="ai_training/config/classes.json", help="Path to classes.json")
    parser.add_argument("--single-inference", action="store_true", default=True, help="Run single real-image crop inference")
    parser.add_argument("--output-dir", default="ai_training/data/training_runs/run_smoke/evaluation", help="Output directory for evaluation results")
    return parser.parse_args()


def load_and_verify_checkpoint(checkpoint_path: str, device: torch.device):
    """Loads checkpoint and verifies mandatory M11 metadata keys."""
    if not os.path.exists(checkpoint_path):
        raise FileNotFoundError(f"Error: Checkpoint file not found at {checkpoint_path}")

    ckpt = torch.load(checkpoint_path, map_location=device)

    required_keys = [
        "model_state_dict",
        "config",
        "class_to_idx",
        "idx_to_class",
        "head_dimensions",
        "pretrained_backbone_identifier",
        "random_seed",
    ]
    for key in required_keys:
        if key not in ckpt:
            raise KeyError(f"Error: Mandatory checkpoint key '{key}' missing from {checkpoint_path}")

    print(f"Loaded checkpoint from {checkpoint_path}: epoch={ckpt.get('epoch')}, backbone={ckpt.get('pretrained_backbone_identifier')}, seed={ckpt.get('random_seed')}.")

    config = ckpt["config"]
    head_dims = ckpt["head_dimensions"]
    class_to_idx = ckpt["class_to_idx"]
    idx_to_class = ckpt["idx_to_class"]
    pretrained_path = config.get("pretrained_path", "ai_training/data/training_runs/pretrained/yolov8n-cls.pt")

    model = YOLOv8MultiTaskClassifier(
        pretrained_path=pretrained_path,
        head_dims=head_dims,
        freeze_backbone=False,
    ).to(device)

    model.load_state_dict(ckpt["model_state_dict"])
    model.eval()

    return model, ckpt, config, class_to_idx, idx_to_class


def run_single_crop_inference(model, dataset, class_to_idx, idx_to_class, device):
    """Runs inference on a real garment crop from dataset."""
    print("\n--- Single Real-Image Garment Crop Inference Verification ---")

    # Find first record with a valid image
    target_record = dataset.records[0]
    image_tensor = dataset[0]["image"].unsqueeze(0).to(device)  # [1, 3, 224, 224]

    with torch.no_grad():
        logits_dict = model(image_tensor)

    print(f"Input Record UID: {target_record.get('record_uid')}")
    print(f"Input Image Tensor Shape: {image_tensor.shape}")
    print("Output Logits & Predictions Across All 4 Heads:")

    predictions = {}
    for head in HEADS:
        logits = logits_dict[head]  # [1, C_h]
        probs = F.softmax(logits, dim=-1)[0]
        pred_idx = torch.argmax(probs).item()
        confidence = probs[pred_idx].item()
        pred_class = idx_to_class[head][str(pred_idx)]

        predictions[head] = {
            "logits_shape": list(logits.shape),
            "predicted_index": pred_idx,
            "predicted_class": pred_class,
            "confidence": round(confidence, 4),
        }

        print(f"  Head '{head}': Shape={list(logits.shape)} -> Predicted Class='{pred_class}' (Index={pred_idx}, Conf={confidence:.4f})")

    return predictions


def main():
    args = parse_args()

    device = torch.device("cpu")
    model, ckpt, config, class_to_idx, idx_to_class = load_and_verify_checkpoint(args.checkpoint, device)

    eval_dataset = MultiTaskDataset(
        jsonl_path=args.manifest,
        class_to_idx=class_to_idx,
        is_train=False,
        max_records=128,
        coverage_aware_sample=False,
        image_size=config.get("image_size", 224),
    )

    metrics_tracker = MultiTaskMetricsTracker(class_to_idx, idx_to_class)

    with torch.no_grad():
        for i in range(len(eval_dataset)):
            item = eval_dataset[i]
            img = item["image"].unsqueeze(0).to(device)
            targets = {h: item["labels"][h].unsqueeze(0).to(device) for h in HEADS}
            masks = {h: item["masks"][h].unsqueeze(0).to(device) for h in HEADS}

            logits = model(img)
            metrics_tracker.update(logits, targets, masks)

    metrics_results = metrics_tracker.compute()

    os.makedirs(args.output_dir, exist_ok=True)
    metrics_path = os.path.join(args.output_dir, "eval_metrics.json")
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(metrics_results, f, indent=2)

    print(f"\nEvaluation completed over {len(eval_dataset)} records.")
    print(f"Wrote evaluation metrics to {metrics_path}.")

    single_pred_results = None
    if args.single_inference:
        single_pred_results = run_single_crop_inference(model, eval_dataset, class_to_idx, idx_to_class, device)
        single_path = os.path.join(args.output_dir, "single_inference.json")
        with open(single_path, "w", encoding="utf-8") as f:
            json.dump(single_pred_results, f, indent=2)
        print(f"Wrote single inference results to {single_path}.")


if __name__ == "__main__":
    main()
