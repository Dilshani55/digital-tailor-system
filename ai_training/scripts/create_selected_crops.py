#!/usr/bin/env python3
"""
create_selected_crops.py

Creates bounded garment crops from successfully downloaded Fashionpedia images (Milestone AI-6B).

Requirements:
- Use verified parent bbox
- Validate image dimensions and bbox coordinates
- Clip bbox safely to image bounds
- Add small configurable context margin (5%)
- Never stretch the crop
- Reject invalid or tiny crops
- Store crops under: ai_training/data/images/fashionpedia_selected/crops/
- Create crop_manifest.jsonl and crop_summary.json
- Preserve source image hash, annotation ID, bbox, split
"""

import argparse
import hashlib
import json
import os
import sys
from PIL import Image


def parse_args():
    parser = argparse.ArgumentParser(description="Create garment crops from downloaded images")
    parser.add_argument("--download-manifest", required=True, help="Path to download_manifest.jsonl")
    parser.add_argument("--queue", required=True, help="Path to candidate_queue.jsonl")
    parser.add_argument("--config", required=True, help="Path to config/ai_assisted_labelling.json")
    parser.add_argument("--output-dir", required=True, help="Directory to store crops")
    parser.add_argument("--manifest-dir", required=True, help="Directory to store crop manifest and summary")
    return parser.parse_args()


def compute_sha256(filepath):
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()


def compute_crop_coordinates(bbox, img_width, img_height, margin_percent):
    """
    Computes context-expanded, clipped crop coordinates from Fashionpedia bbox [x, y, w, h].
    Returns (crop_left, crop_top, crop_right, crop_bottom, expanded_bbox)
    """
    if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
        return None, "Invalid bbox format"

    x, y, w, h = [float(v) for v in bbox]
    if x < 0 or y < 0 or w <= 0 or h <= 0:
        return None, f"Negative or zero bbox dimensions: {bbox}"

    margin_x = w * margin_percent
    margin_y = h * margin_percent

    crop_left = max(0, int(round(x - margin_x)))
    crop_top = max(0, int(round(y - margin_y)))
    crop_right = min(img_width, int(round(x + w + margin_x)))
    crop_bottom = min(img_height, int(round(y + h + margin_y)))

    crop_w = crop_right - crop_left
    crop_h = crop_bottom - crop_top

    if crop_w <= 0 or crop_h <= 0:
        return None, f"Clipped crop has invalid size ({crop_w}x{crop_h})"

    return (crop_left, crop_top, crop_right, crop_bottom), None


def main():
    args = parse_args()

    with open(args.config, "r", encoding="utf-8") as f:
        config = json.load(f)

    crop_rules = config.get("crop_rules", {})
    margin_percent = crop_rules.get("margin_percent", 0.05)
    min_crop_size = crop_rules.get("min_crop_size", 32)

    os.makedirs(args.output_dir, exist_ok=True)
    os.makedirs(args.manifest_dir, exist_ok=True)

    # Load queue lookup for metadata
    queue_map = {}
    with open(args.queue, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rec = json.loads(line.strip())
                queue_map[rec["source_annotation_id"]] = rec

    print(f"Reading download manifest from {args.download_manifest}...")
    download_records = []
    with open(args.download_manifest, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                download_records.append(json.loads(line.strip()))

    print(f"Loaded {len(download_records)} download records.")

    crop_records = []
    status_counts = {"success": 0, "failed": 0, "rejected_tiny": 0, "missing_image": 0}

    for idx, d_rec in enumerate(download_records, 1):
        ann_id = d_rec["source_annotation_id"]
        img_id = d_rec["source_image_id"]
        d_status = d_rec.get("status")
        local_path = d_rec.get("local_path")

        if d_status != "success" or not local_path or not os.path.exists(local_path):
            status_counts["missing_image"] += 1
            crop_records.append({
                "source_image_id": img_id,
                "source_annotation_id": ann_id,
                "status": "missing_image",
                "error_message": f"Source image unavailable or download status={d_status}",
                "split": d_rec.get("split", "train"),
            })
            continue

        bbox = d_rec.get("bbox")
        cand_info = queue_map.get(ann_id, {})
        if not bbox:
            bbox = cand_info.get("bbox")

        # Load image and compute crop
        try:
            with Image.open(local_path) as img:
                img_w, img_h = img.size
                coords, err = compute_crop_coordinates(bbox, img_w, img_h, margin_percent)
                
                if coords is None:
                    status_counts["failed"] += 1
                    crop_records.append({
                        "source_image_id": img_id,
                        "source_annotation_id": ann_id,
                        "status": "failed",
                        "error_message": err,
                        "split": d_rec.get("split", "train"),
                    })
                    continue

                crop_left, crop_top, crop_right, crop_bottom = coords
                crop_w = crop_right - crop_left
                crop_h = crop_bottom - crop_top

                if crop_w < min_crop_size or crop_h < min_crop_size:
                    status_counts["rejected_tiny"] += 1
                    crop_records.append({
                        "source_image_id": img_id,
                        "source_annotation_id": ann_id,
                        "status": "rejected_tiny",
                        "error_message": f"Crop dimensions ({crop_w}x{crop_h}) below minimum target ({min_crop_size}x{min_crop_size})",
                        "split": d_rec.get("split", "train"),
                    })
                    continue

                # Perform crop
                cropped_img = img.crop((crop_left, crop_top, crop_right, crop_bottom))
                
                # Deterministic crop filename
                crop_filename = f"{img_id}_{ann_id}_crop.jpg"
                crop_path = os.path.join(args.output_dir, crop_filename)
                rel_crop_path = os.path.relpath(crop_path, start=os.getcwd()).replace("\\", "/")

                cropped_img.convert("RGB").save(crop_path, format="JPEG", quality=95)
                crop_sha256 = compute_sha256(crop_path)
                status_counts["success"] += 1

                crop_records.append({
                    "source_image_id": img_id,
                    "source_annotation_id": ann_id,
                    "crop_filename": crop_filename,
                    "crop_path": rel_crop_path,
                    "crop_sha256": crop_sha256,
                    "source_image_sha256": d_rec.get("sha256"),
                    "original_bbox": bbox,
                    "crop_bbox": [crop_left, crop_top, crop_w, crop_h],
                    "crop_dimensions": [crop_w, crop_h],
                    "original_image_dimensions": [img_w, img_h],
                    "candidate_garment_type": d_rec.get("candidate_garment_type"),
                    "candidate_garment_reason": d_rec.get("candidate_garment_reason"),
                    "split": d_rec.get("split", "train"),
                    "status": "success",
                })

        except Exception as e:
            status_counts["failed"] += 1
            crop_records.append({
                "source_image_id": img_id,
                "source_annotation_id": ann_id,
                "status": "failed",
                "error_message": f"Crop processing error: {str(e)}",
                "split": d_rec.get("split", "train"),
            })

    manifest_path = os.path.join(args.manifest_dir, "crop_manifest.jsonl")
    summary_path = os.path.join(args.manifest_dir, "crop_summary.json")

    print(f"Writing crop manifest ({len(crop_records)} records) to {manifest_path}...")
    with open(manifest_path, "w", encoding="utf-8") as f:
        for rec in crop_records:
            f.write(json.dumps(rec) + "\n")

    summary = {
        "total_downloads_processed": len(download_records),
        "status_counts": status_counts,
        "success_rate": status_counts["success"] / max(len(download_records), 1),
        "margin_percent": margin_percent,
        "min_crop_size": min_crop_size,
    }

    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"Wrote crop summary to {summary_path}.")
    print(f"Crop results: {status_counts}")


if __name__ == "__main__":
    main()
