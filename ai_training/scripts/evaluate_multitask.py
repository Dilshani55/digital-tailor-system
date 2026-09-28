#!/usr/bin/env python3
"""
evaluate_multitask.py

Evaluation and 3-Garment Crop Inference Script for Digital Tailor AI (Milestone M12).
- Loads saved checkpoint (.pt file) and verifies mandatory metadata.
- Re-instantiates single YOLOv8MultiTaskClassifier model and reloads weights.
- Evaluates dataset manifest (val.jsonl / test.jsonl) computing per-head metrics and confusion matrices.
- Computes overall supported-head mean macro-F1 score.
- Runs inference on 3 real garment crops (1 blouse, 1 t-shirt, 1 crop-top), outputting 4-head predictions, confidence scores, and tensor shapes.
"""

import argparse
import json
import os
import sys
import torch
import torch.nn.functional as F
from PIL import Image

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from ai_training.datasets.multitask_dataset import MultiTaskDataset, HEADS
from ai_training.models.multitask_yolov8 import YOLOv8MultiTaskClassifier
from ai_training.training.metrics import MultiTaskMetricsTracker


def parse_args():
    parser = argparse.ArgumentParser(description="Evaluate multi-task model and run 3-garment crop inference")
    parser.add_argument("--checkpoint", default="ai_training/data/training_runs/m12_full/checkpoints/best.pt", help="Path to checkpoint .pt file")
    parser.add_argument("--manifest", default="ai_training/data/final_multitask/test.jsonl", help="Path to evaluation JSONL manifest")
    parser.add_argument("--classes", default="ai_training/config/classes.json", help="Path to classes.json")
    parser.add_argument("--three-garment-inference", action="store_true", default=True, help="Run 3-garment (blouse, t-shirt, crop-top) crop inference")
    parser.add_argument("--output-dir", default="ai_training/data/training_runs/m12_full/logs", help="Output directory for evaluation results")
    return parser.parse_args()


def load_and_verify_checkpoint(checkpoint_path: str, device: torch.device):
    """Loads checkpoint and verifies mandatory M12 metadata keys."""
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


def run_three_garment_crop_inference(model, dataset, class_to_idx, idx_to_class, device):
    """Runs inference on 1 blouse, 1 t-shirt, and 1 crop-top image crop."""
    print("\n==================================================")
    print("THREE-GARMENT CROP INFERENCE VERIFICATION")
    print("==================================================")

    targets_to_find = ["blouse", "t-shirt", "crop-top"]
    found_indices = {}

    for idx, r in enumerate(dataset.records):
        g_lbl = r.get("labels", {}).get("garment_type")
        g_mask = r.get("masks", {}).get("garment_type", 0)
        if g_mask == 1 and g_lbl in targets_to_find and g_lbl not in found_indices:
            found_indices[g_lbl] = idx
        if len(found_indices) == 3:
            break

    three_garment_results = {}

    for garment_name in targets_to_find:
        idx = found_indices.get(garment_name)
        if idx is None:
            print(f"WARNING: Could not find a test record for garment '{garment_name}'!")
            continue

        record = dataset.records[idx]
        item = dataset[idx]
        image_tensor = item["image"].unsqueeze(0).to(device)  # [1, 3, 224, 224]

        with torch.no_grad():
            logits_dict = model(image_tensor)

        print(f"\n--- Target Garment: '{garment_name.upper()}' ---")
        print(f"Record UID: {record.get('record_uid')}")
        print(f"Input Image Tensor Shape: {image_tensor.shape}")

        garment_pred_info = {"record_uid": record.get("record_uid"), "tensor_shape": list(image_tensor.shape), "heads": {}}

        for head in HEADS:
            logits = logits_dict[head]  # [1, C_h]
            probs = F.softmax(logits, dim=-1)[0]
            pred_idx = torch.argmax(probs).item()
            confidence = probs[pred_idx].item()
            pred_class = idx_to_class[head][str(pred_idx)]

            garment_pred_info["heads"][head] = {
                "logits_shape": list(logits.shape),
                "predicted_index": pred_idx,
                "predicted_class": pred_class,
                "confidence": round(confidence, 4),
            }

            print(f"  Head '{head}': Shape={list(logits.shape)} -> Pred='{pred_class}' (Conf={confidence:.4f})")

        three_garment_results[garment_name] = garment_pred_info

    return three_garment_results


def main():
    args = parse_args()

    device = torch.device("cpu")
    model, ckpt, config, class_to_idx, idx_to_class = load_and_verify_checkpoint(args.checkpoint, device)

    eval_dataset = MultiTaskDataset(
        jsonl_path=args.manifest,
        class_to_idx=class_to_idx,
        is_train=False,
        max_records=None,  # Full split evaluation
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

    # Calculate mean macro-F1 across supported heads
    supported_f1s = [metrics_results[h]["macro_f1"] for h in HEADS if metrics_results[h]["evaluated_count"] > 0 and metrics_results[h]["macro_f1"] != "N/A"]
    overall_mean_macro_f1 = round(sum(supported_f1s) / len(supported_f1s), 4) if supported_f1s else 0.0

    eval_summary = {
        "manifest_path": args.manifest,
        "record_count": len(eval_dataset),
        "overall_supported_head_mean_macro_f1": overall_mean_macro_f1,
        "metrics_by_head": metrics_results,
    }

    os.makedirs(args.output_dir, exist_ok=True)
    is_test = "test" in args.manifest.lower()
    metrics_filename = "test_metrics_final.json" if is_test else "val_metrics_final.json"
    metrics_path = os.path.join(args.output_dir, metrics_filename)

    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(eval_summary, f, indent=2)

    # Save confusion matrices separately for inspection
    cm_data = {h: metrics_results[h]["confusion_matrix"] for h in HEADS}
    cm_path = os.path.join(args.output_dir, "confusion_matrices.json")
    with open(cm_path, "w", encoding="utf-8") as f:
        json.dump(cm_data, f, indent=2)

    print(f"\n==================================================")
    print(f"LOCKED EVALUATION COMPLETED ({'TEST' if is_test else 'VAL'} SPLIT: {len(eval_dataset)} RECORDS)")
    print(f"Overall Supported-Head Mean Macro-F1: {overall_mean_macro_f1:.4f}")
    print(f"==================================================")
    for h in HEADS:
        print(f"  [{h}] Evaluated: {metrics_results[h]['evaluated_count']} | Acc: {metrics_results[h]['accuracy']} | Macro-F1: {metrics_results[h]['macro_f1']}")

    if args.three_garment_inference:
        three_garment_results = run_three_garment_crop_inference(model, eval_dataset, class_to_idx, idx_to_class, device)
        single_path = os.path.join(args.output_dir, "sample_garment_predictions.json")
        with open(single_path, "w", encoding="utf-8") as f:
            json.dump(three_garment_results, f, indent=2)
        print(f"\nWrote 3-garment inference results to {single_path}.")


if __name__ == "__main__":
    main()
