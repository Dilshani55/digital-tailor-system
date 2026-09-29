#!/usr/bin/env python3
"""
evaluate_phase2.py

Evaluates multi-task YOLOv8 model checkpoint on the locked 60-image real-product evaluation benchmark.
Computes per-head accuracy, macro-F1, per-class metrics, confusion matrices, and failure logs.
"""

import argparse
import json
import os
import sys
import torch
import torch.nn.functional as F

sys.path.insert(0, os.path.abspath("."))
sys.path.insert(0, os.path.abspath("backend"))

from backend.app.ai.multitask_classifier import get_multitask_classifier, preprocess_image_crop
from ai_training.training.metrics import MultiTaskMetricsTracker

DEFAULT_MODEL_PATH = "backend/app/ai/models/garment_multitask_yolov8_best.pt"
EVAL_MANIFEST = "ai_training/data/eval_real_product_set/eval_manifest.jsonl"
HEADS = ["garment_type", "neckline_type", "sleeve_length", "sleeve_style"]


def resolve_manifest_path(path):
    """Resolve manifests created on Windows when evaluation runs on any OS."""
    if os.path.exists(path):
        return path
    normalized = os.path.normpath(path.replace("\\", os.sep).replace("/", os.sep))
    if os.path.exists(normalized):
        return normalized
    return path

def evaluate_locked_set(model_path=None, manifest_path=None):
    model_path = model_path or DEFAULT_MODEL_PATH
    manifest_path = manifest_path or EVAL_MANIFEST

    print("==================================================")
    print("PHASE 2: LOCKED REAL-PRODUCT EVALUATION BENCHMARK")
    print(f"Model Checkpoint: {model_path}")
    print("==================================================")
    
    model, meta = get_multitask_classifier(model_path=model_path)
    class_to_idx = meta["class_to_idx"]
    idx_to_class = meta["idx_to_class"]
    
    records = []
    with open(manifest_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line.strip()))
                
    print(f"Loaded {len(records)} locked evaluation records.")
    
    metrics_tracker = MultiTaskMetricsTracker(class_to_idx, idx_to_class)
    failures = {h: [] for h in HEADS}
    
    with torch.no_grad():
        for rec in records:
            img_path = resolve_manifest_path(rec["image_path"])
            bbox = rec.get("bbox")
            
            if bbox and isinstance(bbox, (list, tuple)) and len(bbox) == 4:
                bx, by, bw, bh = bbox
                crop_bbox = [bx, by, bx + bw, by + bh]
            else:
                crop_bbox = None
                
            input_tensor = preprocess_image_crop(img_path, bbox=crop_bbox)
            logits_dict = model(input_tensor)
            
            targets = {}
            masks = {}
            
            for h in HEADS:
                mask_val = rec["masks"].get(h, 0)
                lbl_val = rec["labels"].get(h)
                
                if mask_val == 1 and lbl_val and lbl_val in class_to_idx[h]:
                    targets[h] = torch.tensor([class_to_idx[h][lbl_val]], dtype=torch.long)
                    masks[h] = torch.tensor([1.0], dtype=torch.float32)
                    
                    probs = F.softmax(logits_dict[h][0], dim=0)
                    pred_idx = torch.argmax(probs).item()
                    true_idx = class_to_idx[h][lbl_val]
                    
                    if pred_idx != true_idx:
                        pred_class = idx_to_class[h][str(pred_idx)]
                        failures[h].append({
                            "eval_id": rec["eval_id"],
                            "image": rec["image_filename"],
                            "true_label": lbl_val,
                            "predicted_label": pred_class,
                            "confidence": round(probs[pred_idx].item(), 4),
                            "true_class_confidence": round(probs[true_idx].item(), 4),
                        })
                else:
                    targets[h] = torch.tensor([0], dtype=torch.long)
                    masks[h] = torch.tensor([0.0], dtype=torch.float32)
                    
            metrics_tracker.update(logits_dict, targets, masks)
            
    results = metrics_tracker.compute()
    
    print("\n--------------------------------------------------")
    print("SUMMARY PERFORMANCE METRICS ON 60-IMAGE REAL-PRODUCT SET")
    print("--------------------------------------------------")
    for h in HEADS:
        h_res = results[h]
        print(f"\nHead: '{h.upper()}' (Evaluated: {h_res['evaluated_count']}/60)")
        print(f"  Accuracy: {h_res['accuracy'] * 100:.2f}%")
        print(f"  Macro-F1: {h_res['macro_f1']:.4f}")

    return results, failures

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Evaluate a multi-task checkpoint on the locked 60-image benchmark."
    )
    parser.add_argument("checkpoint", nargs="?", default=DEFAULT_MODEL_PATH)
    parser.add_argument("--manifest", default=EVAL_MANIFEST)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    results, failures = evaluate_locked_set(
        model_path=args.checkpoint,
        manifest_path=args.manifest,
    )
    output_path = args.output or os.path.join(
        os.path.dirname(EVAL_MANIFEST), "latest_eval_results.json"
    )
    output = {
        "model_checkpoint": args.checkpoint,
        "evaluation_manifest": args.manifest,
        "results": results,
        "failures": failures,
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)
    print(f"\nSaved evaluation results to: {output_path}")
