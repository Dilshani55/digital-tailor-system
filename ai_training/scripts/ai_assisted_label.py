#!/usr/bin/env python3
"""
ai_assisted_label.py

Zero-shot AI-assisted garment pseudo-labelling using CLIP (openai/clip-vit-base-patch32) (Milestone M8).

Target classes:
- blouse
- t-shirt
- crop-top
- reject (out-of-scope / bad quality / men's / non-target)

Rules:
- Aggregate prompt probabilities within each class
- Support batched inference & restart/resume
- Record all class scores, top-1 score, top-2 score, confidence, and margin
- Require top-1 confidence >= confidence_threshold (0.60)
- Require top-1/top-2 margin >= minimum_margin (0.10)
- Require agreement between at least two prompt formulations within top-1 class
- Direct crop-top evidence with CLIP disagreement MUST go to manual_review, not be silently rejected
- Ambiguous blouse/t-shirt candidate evidence must not be automatically accepted without passing thresholds
- Outputs: ai_labels_all.jsonl, accepted_pseudo_labels.jsonl, manual_review.jsonl, rejected.jsonl, labelling_summary.json
- Every record states: label_origin='ai_assisted_pseudo_label', human_verified=false
"""

import argparse
import json
import os
import sys
import numpy as np
import torch
from PIL import Image
try:
    from transformers import CLIPModel, CLIPProcessor
except ImportError:  # optional labelling-only dependency; the script reports it when actually run
    CLIPModel = CLIPProcessor = None


def parse_args():
    parser = argparse.ArgumentParser(description="AI-assisted garment pseudo-labelling with CLIP")
    parser.add_argument("--crop-manifest", required=True, help="Path to crop_manifest.jsonl")
    parser.add_argument("--config", required=True, help="Path to config/ai_assisted_labelling.json")
    parser.add_argument("--output-dir", required=True, help="Directory to output pseudo-label JSONL files and summary")
    parser.add_argument("--batch-size", type=int, default=32, help="Batch size for CLIP inference")
    return parser.parse_args()


def load_clip_model(model_name):
    print(f"Loading CLIP model '{model_name}' via Transformers...")
    try:
        if CLIPModel is None:
            raise RuntimeError("The 'transformers' package is required for CLIP labelling (pip install transformers).")
        model = CLIPModel.from_pretrained(model_name)
        processor = CLIPProcessor.from_pretrained(model_name)
        model.eval()
        print(f"Successfully loaded CLIP model '{model_name}'.")
        return model, processor
    except Exception as e:
        print(f"CRITICAL ERROR: Failed to load CLIP model '{model_name}': {e}")
        sys.exit(1)


def build_prompt_structure(prompt_templates, class_list):
    all_prompts = []
    prompt_to_class = []
    class_prompt_indices = {c: [] for c in class_list}

    for c in class_list:
        templates = prompt_templates.get(c, [])
        for t in templates:
            idx = len(all_prompts)
            all_prompts.append(t)
            prompt_to_class.append(c)
            class_prompt_indices[c].append(idx)

    return all_prompts, prompt_to_class, class_prompt_indices


def process_batch(crop_records, model, processor, all_prompts, prompt_to_class, class_prompt_indices, class_list, config):
    conf_threshold = config.get("confidence_threshold", 0.60)
    min_margin = config.get("minimum_margin", 0.10)
    reject_class = config.get("reject_class", "reject")
    disclaimer = config.get("disclaimer", "AI-assisted pseudo-labels are unverified by human review.")

    images = []
    valid_records = []
    results = []

    for c_rec in crop_records:
        status = c_rec.get("status") or c_rec.get("geometry_status")
        crop_path = c_rec.get("crop_path")

        if status != "success" or not crop_path or not os.path.exists(crop_path):
            results.append({
                "source_image_id": c_rec.get("source_image_id"),
                "source_annotation_id": c_rec.get("source_annotation_id"),
                "crop_path": crop_path,
                "label_origin": "ai_assisted_pseudo_label",
                "model_name": config.get("model_name", "openai/clip-vit-base-patch32"),
                "human_verified": False,
                "decision": "failed",
                "predicted_garment_type": None,
                "error_message": f"Crop status={status}",
                "split": c_rec.get("split") or c_rec.get("source_split", "train"),
            })
            continue

        try:
            img = Image.open(crop_path).convert("RGB")
            images.append(img)
            valid_records.append(c_rec)
        except Exception as e:
            results.append({
                "source_image_id": c_rec.get("source_image_id"),
                "source_annotation_id": c_rec.get("source_annotation_id"),
                "crop_path": crop_path,
                "label_origin": "ai_assisted_pseudo_label",
                "model_name": config.get("model_name", "openai/clip-vit-base-patch32"),
                "human_verified": False,
                "decision": "failed",
                "predicted_garment_type": None,
                "error_message": f"Failed to open crop image: {e}",
                "split": c_rec.get("split") or c_rec.get("source_split", "train"),
            })

    if not images:
        return results

    inputs = processor(text=all_prompts, images=images, return_tensors="pt", padding=True)
    with torch.no_grad():
        outputs = model(**inputs)
        logits_per_image = outputs.logits_per_image  # [batch_size, num_prompts]
        probs_batch = torch.softmax(logits_per_image, dim=-1).cpu().numpy()

    for idx, c_rec in enumerate(valid_records):
        probs = probs_batch[idx]
        prompt_scores = {all_prompts[i]: float(probs[i]) for i in range(len(all_prompts))}

        # Class aggregated scores
        class_scores = {}
        for c in class_list:
            indices = class_prompt_indices[c]
            class_scores[c] = float(sum(probs[i] for i in indices))

        sorted_classes = sorted(class_list, key=lambda c: class_scores[c], reverse=True)
        top1_cls = sorted_classes[0]
        top2_cls = sorted_classes[1]
        top1_score = class_scores[top1_cls]
        top2_score = class_scores[top2_cls]
        margin = top1_score - top2_score

        # Multi-prompt agreement inside top-1 class
        max_non_top1_prompt_prob = max((float(probs[i]) for i, p_cls in enumerate(prompt_to_class) if p_cls != top1_cls), default=0.0)
        top1_indices = class_prompt_indices[top1_cls]
        agreed_prompts_count = sum(1 for i in top1_indices if float(probs[i]) >= max_non_top1_prompt_prob)
        prompt_agreement = (agreed_prompts_count >= 2) or (len(top1_indices) < 2 and agreed_prompts_count >= 1)

        # Check Fashionpedia direct evidence
        cand_garment_type = c_rec.get("candidate_garment_type")
        cand_reason = c_rec.get("candidate_garment_reason") or ""
        is_crop_top_direct = (cand_garment_type == "crop-top") and ("Attr 8" in cand_reason or "crop" in cand_reason)

        # Decision classification
        if top1_cls == reject_class:
            if is_crop_top_direct:
                decision = "manual_review"
                target_garment_type = "crop-top"
            else:
                decision = "rejected"
                target_garment_type = reject_class
        elif is_crop_top_direct and top1_cls != "crop-top":
            # Crop-top direct evidence disagreeing with CLIP top-1 prediction -> manual_review
            decision = "manual_review"
            target_garment_type = top1_cls
        elif top1_score >= conf_threshold and margin >= min_margin and prompt_agreement:
            decision = "accepted"
            target_garment_type = top1_cls
        else:
            decision = "manual_review"
            target_garment_type = top1_cls

        results.append({
            "source_image_id": c_rec.get("source_image_id"),
            "source_annotation_id": c_rec.get("source_annotation_id"),
            "crop_path": c_rec.get("crop_path"),
            "crop_sha256": c_rec.get("crop_sha256"),
            "label_origin": "ai_assisted_pseudo_label",
            "model_name": config.get("model_name", "openai/clip-vit-base-patch32"),
            "human_verified": False,
            "decision": decision,
            "predicted_garment_type": target_garment_type,
            "top1_label": top1_cls,
            "top1_confidence": round(top1_score, 4),
            "top2_label": top2_cls,
            "top2_confidence": round(top2_score, 4),
            "margin": round(margin, 4),
            "prompt_agreement": prompt_agreement,
            "agreed_prompts_count": agreed_prompts_count,
            "class_scores": {k: round(v, 4) for k, v in class_scores.items()},
            "prompt_scores": {k: round(v, 4) for k, v in prompt_scores.items()},
            "source_evidence": {
                "candidate_garment_type": cand_garment_type,
                "candidate_garment_reason": cand_reason,
                "original_bbox": c_rec.get("original_bbox"),
            },
            "split": c_rec.get("split") or c_rec.get("source_split", "train"),
            "limitations": disclaimer,
        })

    return results


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
    all_prompts, prompt_to_class, class_prompt_indices = build_prompt_structure(prompt_templates, all_classes)

    print(f"Reading crop manifest from {args.crop_manifest}...")
    crop_records = []
    with open(args.crop_manifest, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                crop_records.append(json.loads(line.strip()))

    print(f"Loaded {len(crop_records)} crop manifest records.")

    # Check for restart/resume output
    os.makedirs(args.output_dir, exist_ok=True)
    all_preds_path = os.path.join(args.output_dir, "ai_labels_all.jsonl")
    existing_preds = {}
    if os.path.exists(all_preds_path):
        print(f"Found existing predictions at {all_preds_path}, checking for resume...")
        with open(all_preds_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    rec = json.loads(line.strip())
                    existing_preds[rec["source_annotation_id"]] = rec
        print(f"Resuming: {len(existing_preds)} items already evaluated.")

    batch_size = args.batch_size
    num_crops = len(crop_records)

    for i in range(0, num_crops, batch_size):
        batch_records = crop_records[i:i + batch_size]
        unprocessed = [r for r in batch_records if r["source_annotation_id"] not in existing_preds]

        if unprocessed:
            batch_results = process_batch(unprocessed, model, processor, all_prompts, prompt_to_class, class_prompt_indices, all_classes, config)
            for r in batch_results:
                existing_preds[r["source_annotation_id"]] = r

        if (i + batch_size) % (batch_size * 5) == 0 or (i + batch_size) >= num_crops:
            print(f"Evaluated {min(i + batch_size, num_crops)} / {num_crops} crops...")

    all_predictions_list = list(existing_preds.values())
    accepted_pseudo_labels = [r for r in all_predictions_list if r.get("decision") == "accepted"]
    manual_review = [r for r in all_predictions_list if r.get("decision") == "manual_review"]
    rejected = [r for r in all_predictions_list if r.get("decision") == "rejected"]
    failed = [r for r in all_predictions_list if r.get("decision") == "failed"]

    confidences = [r["top1_confidence"] for r in all_predictions_list if "top1_confidence" in r]
    margins = [r["margin"] for r in all_predictions_list if "margin" in r]

    counts_by_decision = {
        "accepted": len(accepted_pseudo_labels),
        "manual_review": len(manual_review),
        "rejected": len(rejected),
        "failed": len(failed),
    }

    counts_by_accepted_class = {c: sum(1 for r in accepted_pseudo_labels if r.get("predicted_garment_type") == c) for c in target_classes}

    def write_jsonl(filename, records):
        p = os.path.join(args.output_dir, filename)
        with open(p, "w", encoding="utf-8") as f:
            for r in records:
                f.write(json.dumps(r) + "\n")
        print(f"Wrote {len(records)} records to {p}.")

    write_jsonl("ai_labels_all.jsonl", all_predictions_list)
    write_jsonl("accepted_pseudo_labels.jsonl", accepted_pseudo_labels)
    write_jsonl("manual_review.jsonl", manual_review)
    write_jsonl("review_required.jsonl", manual_review)
    write_jsonl("rejected.jsonl", rejected)

    summary = {
        "model_name": model_name,
        "total_crops_evaluated": len(all_predictions_list),
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

    summary_path = os.path.join(args.output_dir, "labelling_summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    legacy_summary_path = os.path.join(args.output_dir, "ai_labelling_summary.json")
    with open(legacy_summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"Wrote AI labelling summary to {summary_path}.")
    print(f"AI Labelling completed: Accepted={counts_by_decision['accepted']}, Manual Review={counts_by_decision['manual_review']}, Rejected={counts_by_decision['rejected']}, Failed={counts_by_decision['failed']}")


if __name__ == "__main__":
    main()
