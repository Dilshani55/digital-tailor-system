#!/usr/bin/env python3
"""
ai_assisted_label.py

Zero-shot AI-assisted garment pseudo-labelling using CLIP (openai/clip-vit-base-patch32) (Milestone AI-6B).

Target classes:
- blouse
- t-shirt
- crop-top
- reject (out-of-scope / bad quality / men's / non-target)

Rules:
- Aggregate prompts within each class
- Store all class scores, top-1 score, top-2 score, confidence, and margin
- Require top-1 confidence >= confidence_threshold (0.60)
- Require top-1/top-2 margin >= minimum_margin (0.10)
- Require agreement between at least two prompt formulations within class
- Low-confidence or disagreement result -> review_required
- Outputs: ai_predictions.jsonl, accepted_pseudo_labels.jsonl, review_required.jsonl, rejected.jsonl, ai_labelling_summary.json
- Every record states: label_origin='ai_assisted_pseudo_label', human_verified=false
"""

import argparse
import json
import os
import sys
import numpy as np
import torch
from PIL import Image
from transformers import CLIPModel, CLIPProcessor


def parse_args():
    parser = argparse.ArgumentParser(description="AI-assisted garment pseudo-labelling with CLIP")
    parser.add_argument("--crop-manifest", required=True, help="Path to crop_manifest.jsonl")
    parser.add_argument("--config", required=True, help="Path to config/ai_assisted_labelling.json")
    parser.add_argument("--output-dir", required=True, help="Directory to output pseudo-label JSONL files and summary")
    return parser.parse_args()


def load_clip_model(model_name):
    print(f"Loading CLIP model '{model_name}' via Transformers...")
    try:
        model = CLIPModel.from_pretrained(model_name)
        processor = CLIPProcessor.from_pretrained(model_name)
        model.eval()
        print(f"Successfully loaded CLIP model '{model_name}'.")
        return model, processor
    except Exception as e:
        print(f"CRITICAL ERROR: Failed to load CLIP model '{model_name}': {e}")
        sys.exit(1)


def evaluate_crop_with_clip(crop_image_path, model, processor, prompt_templates, class_list):
    """
    Evaluates a single crop image against natural language prompts using CLIP.
    Returns dict containing prompt scores, class scores, top-1, top-2, margin, and agreement status.
    """
    # Build flattened prompt list and mapping
    all_prompts = []
    prompt_to_class = []
    class_prompt_indices = {c: [] for c in class_list}

    for c in class_list:
        templates = prompt_templates.get(c, [])
        for t in templates:
            prompt_idx = len(all_prompts)
            all_prompts.append(t)
            prompt_to_class.append(c)
            class_prompt_indices[c].append(prompt_idx)

    # Load and preprocess crop image
    try:
        image = Image.open(crop_image_path).convert("RGB")
    except Exception as e:
        return None, f"Failed to open image: {e}"

    inputs = processor(text=all_prompts, images=image, return_tensors="pt", padding=True)

    with torch.no_grad():
        outputs = model(**inputs)
        logits_per_image = outputs.logits_per_image  # [1, num_prompts]
        probs = torch.softmax(logits_per_image, dim=-1).numpy()[0]

    # Map raw prompt probabilities
    prompt_scores = {all_prompts[i]: float(probs[i]) for i in range(len(all_prompts))}

    # Compute class-level aggregated scores (sum of prompt probabilities in class)
    class_scores = {}
    for c in class_list:
        indices = class_prompt_indices[c]
        class_scores[c] = float(sum(probs[i] for i in indices))

    # Rank classes
    sorted_classes = sorted(class_list, key=lambda c: class_scores[c], reverse=True)
    top1_cls = sorted_classes[0]
    top2_cls = sorted_classes[1]

    top1_score = class_scores[top1_cls]
    top2_score = class_scores[top2_cls]
    margin = top1_score - top2_score

    # Evaluate multi-prompt agreement inside top-1 class
    # Count how many prompts in top1_cls have probability greater than any prompt outside top1_cls
    max_non_top1_prompt_prob = 0.0
    for idx, p_cls in enumerate(prompt_to_class):
        if p_cls != top1_cls:
            max_non_top1_prompt_prob = max(max_non_top1_prompt_prob, float(probs[idx]))

    top1_prompt_indices = class_prompt_indices[top1_cls]
    agreed_prompts_count = sum(1 for idx in top1_prompt_indices if float(probs[idx]) >= max_non_top1_prompt_prob)
    
    # Agreement is true if at least 2 prompt formulations support top-1 class strongly
    prompt_agreement = (agreed_prompts_count >= 2) or (len(top1_prompt_indices) < 2 and agreed_prompts_count >= 1)

    return {
        "prompt_scores": prompt_scores,
        "class_scores": class_scores,
        "top1_label": top1_cls,
        "top1_confidence": top1_score,
        "top2_label": top2_cls,
        "top2_confidence": top2_score,
        "margin": margin,
        "prompt_agreement": prompt_agreement,
        "agreed_prompts_count": agreed_prompts_count,
    }, None


def main():
    args = parse_args()

    with open(args.config, "r", encoding="utf-8") as f:
        config = json.load(f)

    model_name = config.get("model_name", "openai/clip-vit-base-patch32")
    target_classes = config.get("target_classes", ["blouse", "t-shirt", "crop-top"])
    reject_class = config.get("reject_class", "reject")
    all_classes = target_classes + [reject_class]

    prompt_templates = config.get("prompt_templates", {})
    conf_threshold = config.get("confidence_threshold", 0.60)
    min_margin = config.get("minimum_margin", 0.10)
    disclaimer = config.get("disclaimer", "AI-assisted pseudo-labels are unverified by human review.")

    model, processor = load_clip_model(model_name)

    print(f"Reading crop manifest from {args.crop_manifest}...")
    crop_records = []
    with open(args.crop_manifest, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                crop_records.append(json.loads(line.strip()))

    print(f"Loaded {len(crop_records)} crop manifest records.")

    all_predictions = []
    accepted_pseudo_labels = []
    review_required = []
    rejected = []

    confidences = []
    margins = []
    counts_by_decision = {"accepted": 0, "review_required": 0, "rejected": 0, "failed": 0}
    counts_by_accepted_class = {c: 0 for c in target_classes}

    for idx, c_rec in enumerate(crop_records, 1):
        status = c_rec.get("status")
        ann_id = c_rec.get("source_annotation_id")
        img_id = c_rec.get("source_image_id")
        crop_path = c_rec.get("crop_path")

        if status != "success" or not crop_path or not os.path.exists(crop_path):
            counts_by_decision["failed"] += 1
            pred_rec = {
                "source_image_id": img_id,
                "source_annotation_id": ann_id,
                "label_origin": "ai_assisted_pseudo_label",
                "model_name": model_name,
                "human_verified": False,
                "decision": "failed",
                "error_message": f"Crop status={status}",
                "split": c_rec.get("split", "train"),
            }
            all_predictions.append(pred_rec)
            continue

        res, err = evaluate_crop_with_clip(crop_path, model, processor, prompt_templates, all_classes)

        if res is None:
            counts_by_decision["failed"] += 1
            pred_rec = {
                "source_image_id": img_id,
                "source_annotation_id": ann_id,
                "label_origin": "ai_assisted_pseudo_label",
                "model_name": model_name,
                "human_verified": False,
                "decision": "failed",
                "error_message": err,
                "split": c_rec.get("split", "train"),
            }
            all_predictions.append(pred_rec)
            continue

        top1_cls = res["top1_label"]
        top1_conf = res["top1_confidence"]
        top2_cls = res["top2_label"]
        top2_conf = res["top2_confidence"]
        margin = res["margin"]
        agreement = res["prompt_agreement"]

        confidences.append(top1_conf)
        margins.append(margin)

        # Decision classification
        if top1_cls == reject_class:
            decision = "rejected"
            target_garment_type = reject_class
        elif top1_conf >= conf_threshold and margin >= min_margin and agreement:
            decision = "accepted"
            target_garment_type = top1_cls
        else:
            decision = "review_required"
            target_garment_type = top1_cls

        counts_by_decision[decision] += 1
        if decision == "accepted":
            counts_by_accepted_class[target_garment_type] += 1

        pred_record = {
            "source_image_id": img_id,
            "source_annotation_id": ann_id,
            "crop_path": crop_path,
            "label_origin": "ai_assisted_pseudo_label",
            "model_name": model_name,
            "human_verified": False,
            "decision": decision,
            "predicted_garment_type": target_garment_type,
            "top1_label": top1_cls,
            "top1_confidence": round(top1_conf, 4),
            "top2_label": top2_cls,
            "top2_confidence": round(top2_conf, 4),
            "margin": round(margin, 4),
            "prompt_agreement": agreement,
            "agreed_prompts_count": res["agreed_prompts_count"],
            "class_scores": {k: round(v, 4) for k, v in res["class_scores"].items()},
            "prompt_scores": {k: round(v, 4) for k, v in res["prompt_scores"].items()},
            "source_evidence": {
                "candidate_garment_type": c_rec.get("candidate_garment_type"),
                "candidate_garment_reason": c_rec.get("candidate_garment_reason"),
                "original_bbox": c_rec.get("original_bbox"),
            },
            "split": c_rec.get("split", "train"),
            "limitations": disclaimer,
        }

        all_predictions.append(pred_record)

        if decision == "accepted":
            accepted_pseudo_labels.append(pred_record)
        elif decision == "review_required":
            review_required.append(pred_record)
        elif decision == "rejected":
            rejected.append(pred_record)

    os.makedirs(args.output_dir, exist_ok=True)

    # Save outputs
    def write_jsonl(filename, records):
        p = os.path.join(args.output_dir, filename)
        with open(p, "w", encoding="utf-8") as f:
            for r in records:
                f.write(json.dumps(r) + "\n")
        print(f"Wrote {len(records)} records to {p}.")

    write_jsonl("ai_predictions.jsonl", all_predictions)
    write_jsonl("accepted_pseudo_labels.jsonl", accepted_pseudo_labels)
    write_jsonl("review_required.jsonl", review_required)
    write_jsonl("rejected.jsonl", rejected)

    # Summary
    summary = {
        "model_name": model_name,
        "total_crops_evaluated": len(crop_records),
        "confidence_threshold": conf_threshold,
        "minimum_margin": min_margin,
        "decision_counts": counts_by_decision,
        "accepted_counts_by_class": counts_by_accepted_class,
        "confidence_stats": {
            "mean": float(np.mean(confidences)) if confidences else 0.0,
            "min": float(np.min(confidences)) if confidences else 0.0,
            "max": float(np.max(confidences)) if confidences else 0.0,
            "median": float(np.median(confidences)) if confidences else 0.0,
        },
        "margin_stats": {
            "mean": float(np.mean(margins)) if margins else 0.0,
            "min": float(np.min(margins)) if margins else 0.0,
            "max": float(np.max(margins)) if margins else 0.0,
            "median": float(np.median(margins)) if margins else 0.0,
        },
        "disclaimer": disclaimer,
    }

    summary_path = os.path.join(args.output_dir, "ai_labelling_summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"Wrote AI labelling summary to {summary_path}.")
    print(f"AI Labelling completed: Accepted={counts_by_decision['accepted']}, Review Required={counts_by_decision['review_required']}, Rejected={counts_by_decision['rejected']}")


if __name__ == "__main__":
    main()
