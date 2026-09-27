#!/usr/bin/env python3
"""
create_selected_crops.py

Generates geometry-correct garment crops directly from official extracted Fashionpedia images (Milestone M8).

Requirements:
- Open official image WITHOUT EXIF transpose
- Require exact decoded width/height equality with annotation metadata
- Use original Fashionpedia bbox directly
- Reject invalid, zero-area, or out-of-bounds boxes with explicit reason codes
- Permit only numerical boundary clipping for valid bbox touching image edge
- Never rescale official-image bbox
- Never use original_url or Flickr images as fallback
- Record complete provenance on every crop
"""

import argparse
import hashlib
import json
import os
import sys
from PIL import Image


def parse_args():
    parser = argparse.ArgumentParser(description="Create official geometry-correct garment crops")
    parser.add_argument("--queue", required=True, help="Path to candidate queue JSONL")
    parser.add_argument("--annotations", nargs="+", required=True, help="Path(s) to raw instances_attributes_train2020.json / val2020.json")
    parser.add_argument("--official-images-root", default="ai_training/data/raw/fashionpedia/images", help="Root directory of extracted official images")
    parser.add_argument("--config", required=True, help="Path to config/ai_assisted_labelling.json")
    parser.add_argument("--output-dir", required=True, help="Directory to store crops")
    parser.add_argument("--manifest-dir", required=True, help="Directory to store crop manifest and summary")
    parser.add_argument("--manifest-prefix", default="", help="Prefix for output manifest and summary filenames")
    return parser.parse_args()


def compute_sha256(filepath):
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()


def load_raw_image_metadata(annotations_paths):
    if isinstance(annotations_paths, str):
        annotations_paths = [annotations_paths]
    image_meta = {}
    for ann_path in annotations_paths:
        print(f"Loading raw annotations metadata from {ann_path}...")
        with open(ann_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for img in data.get("images", []):
            img_id = img.get("id")
            if img_id is not None:
                image_meta[img_id] = {
                    "file_name": img.get("file_name"),
                    "width": img.get("width"),
                    "height": img.get("height"),
                }
    print(f"Loaded metadata for {len(image_meta)} raw images.")
    return image_meta


def build_official_image_index(official_root):
    print(f"Building official image index from {official_root}...")
    index = {}
    if not os.path.exists(official_root):
        print(f"WARNING: Official images root '{official_root}' does not exist!")
        return index
    for root_dir, _, files in os.walk(official_root):
        for file in files:
            if file.lower().endswith((".jpg", ".jpeg", ".png")):
                index[file] = os.path.join(root_dir, file)
    print(f"Indexed {len(index)} official images.")
    return index


def compute_crop_coordinates(bbox, img_width, img_height, margin_percent):
    """
    Computes context-expanded, clipped crop coordinates from Fashionpedia bbox [x, y, w, h].
    Returns ((crop_left, crop_top, crop_right, crop_bottom), status_code, error_message)
    """
    if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
        return None, "invalid_bbox", f"Invalid bbox format: {bbox}"

    try:
        x, y, w, h = [float(v) for v in bbox]
    except (ValueError, TypeError):
        return None, "invalid_bbox", f"Non-numeric bbox values: {bbox}"

    if w <= 0 or h <= 0 or x < 0 or y < 0:
        return None, "invalid_bbox", f"Negative or zero bbox dimensions: {bbox}"

    if x >= img_width or y >= img_height or (x + w) <= 0 or (y + h) <= 0:
        return None, "out_of_bounds_bbox", f"Bbox completely outside image bounds ({img_width}x{img_height}): {bbox}"

    margin_x = w * margin_percent
    margin_y = h * margin_percent

    crop_left = max(0, int(round(x - margin_x)))
    crop_top = max(0, int(round(y - margin_y)))
    crop_right = min(img_width, int(round(x + w + margin_x)))
    crop_bottom = min(img_height, int(round(y + h + margin_y)))

    crop_w = crop_right - crop_left
    crop_h = crop_bottom - crop_top

    if crop_w <= 0 or crop_h <= 0:
        return None, "invalid_bbox", f"Clipped crop has invalid size ({crop_w}x{crop_h})"

    return (crop_left, crop_top, crop_right, crop_bottom), "success", None


def main():
    args = parse_args()

    with open(args.config, "r", encoding="utf-8") as f:
        config = json.load(f)

    crop_rules = config.get("crop_rules", {})
    margin_percent = crop_rules.get("margin_percent", 0.05)
    min_crop_size = crop_rules.get("min_crop_size", 32)

    os.makedirs(args.output_dir, exist_ok=True)
    os.makedirs(args.manifest_dir, exist_ok=True)

    image_meta = load_raw_image_metadata(args.annotations)
    official_index = build_official_image_index(args.official_images_root)

    print(f"Reading candidate queue from {args.queue}...")
    candidates = []
    with open(args.queue, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                candidates.append(json.loads(line.strip()))

    print(f"Loaded {len(candidates)} candidate queue records.")

    crop_records = []
    status_counts = {
        "success": 0,
        "missing_official_source": 0,
        "dimension_mismatch": 0,
        "invalid_bbox": 0,
        "out_of_bounds_bbox": 0,
        "rejected_tiny": 0,
        "duplicate_crop": 0,
        "decode_failure": 0,
    }

    seen_crop_hashes = set()
    seen_annotation_ids = set()

    for idx, cand in enumerate(candidates, 1):
        ann_id = cand["source_annotation_id"]
        img_id = cand["source_image_id"]
        file_name = cand.get("file_name")
        split = cand.get("split", "train")
        bbox = cand.get("bbox")
        c_cls = cand.get("candidate_garment_type")
        c_reason = cand.get("candidate_garment_reason")
        rank = cand.get("selection_rank", idx)

        # Duplicate annotation check
        if ann_id in seen_annotation_ids:
            status_counts["duplicate_crop"] += 1
            crop_records.append({
                "source_dataset": "fashionpedia",
                "source_split": split,
                "source_image_id": img_id,
                "source_annotation_id": ann_id,
                "source_file_name": file_name,
                "source_image_path": None,
                "annotation_width": cand.get("annotation_width"),
                "annotation_height": cand.get("annotation_height"),
                "decoded_width": None,
                "decoded_height": None,
                "original_bbox": bbox,
                "crop_bbox": None,
                "crop_path": None,
                "geometry_status": "duplicate_crop",
                "status": "duplicate_crop",
                "crop_sha256": None,
                "candidate_garment_type": c_cls,
                "candidate_garment_reason": c_reason,
                "selection_rank": rank,
                "error_message": f"Duplicate source_annotation_id={ann_id}",
            })
            continue

        seen_annotation_ids.add(ann_id)

        # Resolve raw metadata if not in candidate
        raw_info = image_meta.get(img_id, {})
        ann_w = cand.get("annotation_width") or raw_info.get("width")
        ann_h = cand.get("annotation_height") or raw_info.get("height")
        if not file_name:
            file_name = raw_info.get("file_name")

        # 1. Resolve official source image path
        source_image_path = official_index.get(file_name)
        if not source_image_path or not os.path.exists(source_image_path):
            status_counts["missing_official_source"] += 1
            crop_records.append({
                "source_dataset": "fashionpedia",
                "source_split": split,
                "source_image_id": img_id,
                "source_annotation_id": ann_id,
                "source_file_name": file_name,
                "source_image_path": None,
                "annotation_width": ann_w,
                "annotation_height": ann_h,
                "decoded_width": None,
                "decoded_height": None,
                "original_bbox": bbox,
                "crop_bbox": None,
                "crop_path": None,
                "geometry_status": "missing_official_source",
                "status": "missing_official_source",
                "crop_sha256": None,
                "candidate_garment_type": c_cls,
                "candidate_garment_reason": c_reason,
                "selection_rank": rank,
                "error_message": f"Official image '{file_name}' not found in official images root",
            })
            continue

        # Normalized rel path for recording
        rel_source_image_path = os.path.relpath(source_image_path, start=os.getcwd()).replace("\\", "/")

        # 2. Decode image WITHOUT EXIF transpose & check dimensions
        try:
            with Image.open(source_image_path) as img:
                decoded_w, decoded_h = img.size

                # 3. Check exact decoded dimension equality with annotation width/height
                if ann_w is not None and ann_h is not None:
                    if decoded_w != ann_w or decoded_h != ann_h:
                        status_counts["dimension_mismatch"] += 1
                        crop_records.append({
                            "source_dataset": "fashionpedia",
                            "source_split": split,
                            "source_image_id": img_id,
                            "source_annotation_id": ann_id,
                            "source_file_name": file_name,
                            "source_image_path": rel_source_image_path,
                            "annotation_width": ann_w,
                            "annotation_height": ann_h,
                            "decoded_width": decoded_w,
                            "decoded_height": decoded_h,
                            "original_bbox": bbox,
                            "crop_bbox": None,
                            "crop_path": None,
                            "geometry_status": "dimension_mismatch",
                            "status": "dimension_mismatch",
                            "crop_sha256": None,
                            "candidate_garment_type": c_cls,
                            "candidate_garment_reason": c_reason,
                            "selection_rank": rank,
                            "error_message": f"Decoded image dimensions ({decoded_w}x{decoded_h}) != annotation dimensions ({ann_w}x{ann_h})",
                        })
                        continue

                # 4. Compute crop coordinates
                coords, status_code, err_msg = compute_crop_coordinates(bbox, decoded_w, decoded_h, margin_percent)
                if coords is None:
                    status_counts[status_code] += 1
                    crop_records.append({
                        "source_dataset": "fashionpedia",
                        "source_split": split,
                        "source_image_id": img_id,
                        "source_annotation_id": ann_id,
                        "source_file_name": file_name,
                        "source_image_path": rel_source_image_path,
                        "annotation_width": ann_w,
                        "annotation_height": ann_h,
                        "decoded_width": decoded_w,
                        "decoded_height": decoded_h,
                        "original_bbox": bbox,
                        "crop_bbox": None,
                        "crop_path": None,
                        "geometry_status": status_code,
                        "status": status_code,
                        "crop_sha256": None,
                        "candidate_garment_type": c_cls,
                        "candidate_garment_reason": c_reason,
                        "selection_rank": rank,
                        "error_message": err_msg,
                    })
                    continue

                crop_left, crop_top, crop_right, crop_bottom = coords
                crop_w = crop_right - crop_left
                crop_h = crop_bottom - crop_top

                # 5. Check minimum crop size
                if crop_w < min_crop_size or crop_h < min_crop_size:
                    status_counts["rejected_tiny"] += 1
                    crop_records.append({
                        "source_dataset": "fashionpedia",
                        "source_split": split,
                        "source_image_id": img_id,
                        "source_annotation_id": ann_id,
                        "source_file_name": file_name,
                        "source_image_path": rel_source_image_path,
                        "annotation_width": ann_w,
                        "annotation_height": ann_h,
                        "decoded_width": decoded_w,
                        "decoded_height": decoded_h,
                        "original_bbox": bbox,
                        "crop_bbox": [crop_left, crop_top, crop_w, crop_h],
                        "crop_path": None,
                        "geometry_status": "rejected_tiny",
                        "status": "rejected_tiny",
                        "crop_sha256": None,
                        "candidate_garment_type": c_cls,
                        "candidate_garment_reason": c_reason,
                        "selection_rank": rank,
                        "error_message": f"Crop size ({crop_w}x{crop_h}) below minimum ({min_crop_size}x{min_crop_size})",
                    })
                    continue

                # 6. Execute crop & save
                cropped_img = img.crop((crop_left, crop_top, crop_right, crop_bottom))
                crop_filename = f"{img_id}_{ann_id}_crop.jpg"
                crop_path = os.path.join(args.output_dir, crop_filename)
                rel_crop_path = os.path.relpath(crop_path, start=os.getcwd()).replace("\\", "/")

                cropped_img.convert("RGB").save(crop_path, format="JPEG", quality=95)
                crop_sha256 = compute_sha256(crop_path)

                if crop_sha256 in seen_crop_hashes:
                    status_counts["duplicate_crop"] += 1
                    crop_records.append({
                        "source_dataset": "fashionpedia",
                        "source_split": split,
                        "source_image_id": img_id,
                        "source_annotation_id": ann_id,
                        "source_file_name": file_name,
                        "source_image_path": rel_source_image_path,
                        "annotation_width": ann_w,
                        "annotation_height": ann_h,
                        "decoded_width": decoded_w,
                        "decoded_height": decoded_h,
                        "original_bbox": bbox,
                        "crop_bbox": [crop_left, crop_top, crop_w, crop_h],
                        "crop_path": rel_crop_path,
                        "geometry_status": "duplicate_crop",
                        "status": "duplicate_crop",
                        "crop_sha256": crop_sha256,
                        "candidate_garment_type": c_cls,
                        "candidate_garment_reason": c_reason,
                        "selection_rank": rank,
                        "error_message": "Duplicate crop SHA-256 hash detected",
                    })
                    continue

                seen_crop_hashes.add(crop_sha256)
                status_counts["success"] += 1

                crop_records.append({
                    "source_dataset": "fashionpedia",
                    "source_split": split,
                    "source_image_id": img_id,
                    "source_annotation_id": ann_id,
                    "source_file_name": file_name,
                    "source_image_path": rel_source_image_path,
                    "annotation_width": ann_w,
                    "annotation_height": ann_h,
                    "decoded_width": decoded_w,
                    "decoded_height": decoded_h,
                    "original_bbox": bbox,
                    "crop_bbox": [crop_left, crop_top, crop_w, crop_h],
                    "crop_path": rel_crop_path,
                    "geometry_status": "success",
                    "status": "success",
                    "crop_sha256": crop_sha256,
                    "candidate_garment_type": c_cls,
                    "candidate_garment_reason": c_reason,
                    "selection_rank": rank,
                    "error_message": None,
                })

        except Exception as e:
            status_counts["decode_failure"] += 1
            crop_records.append({
                "source_dataset": "fashionpedia",
                "source_split": split,
                "source_image_id": img_id,
                "source_annotation_id": ann_id,
                "source_file_name": file_name,
                "source_image_path": rel_source_image_path if 'rel_source_image_path' in locals() else None,
                "annotation_width": ann_w,
                "annotation_height": ann_h,
                "decoded_width": None,
                "decoded_height": None,
                "original_bbox": bbox,
                "crop_bbox": None,
                "crop_path": None,
                "geometry_status": "decode_failure",
                "status": "decode_failure",
                "crop_sha256": None,
                "candidate_garment_type": c_cls,
                "candidate_garment_reason": c_reason,
                "selection_rank": rank,
                "error_message": f"Decode/Crop failure: {str(e)}",
            })

    prefix = args.manifest_prefix
    manifest_name = f"{prefix}crop_manifest.jsonl" if prefix else "crop_manifest.jsonl"
    summary_name = f"{prefix}crop_summary.json" if prefix else "crop_summary.json"

    manifest_path = os.path.join(args.manifest_dir, manifest_name)
    summary_path = os.path.join(args.manifest_dir, summary_name)

    print(f"Writing crop manifest ({len(crop_records)} records) to {manifest_path}...")
    with open(manifest_path, "w", encoding="utf-8") as f:
        for rec in crop_records:
            f.write(json.dumps(rec) + "\n")

    summary = {
        "total_candidates_processed": len(candidates),
        "status_counts": status_counts,
        "success_rate": status_counts["success"] / max(len(candidates), 1),
        "margin_percent": margin_percent,
        "min_crop_size": min_crop_size,
    }

    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"Wrote crop summary to {summary_path}.")
    print(f"Official crop summary results: {status_counts}")


if __name__ == "__main__":
    main()
