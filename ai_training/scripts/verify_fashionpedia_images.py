#!/usr/bin/env python3
"""
verify_fashionpedia_images.py

Verifies official extracted Fashionpedia images against annotation JSON metadata (Milestone M7).

Requirements:
- Resolve official image using file_name
- Verify existence and full PIL decoding (with EXIF transpose disabled)
- Compare decoded width and height against annotation width and height
- Record exact_match, missing_file, corrupt_file, width_mismatch, height_mismatch, aspect_ratio_mismatch
- Report exact matching percentage
- Report duplicate file_names and duplicate image IDs
- Report unmatched files found in extracted image directory
- Save JSON report under output-report
"""

import argparse
import json
import os
import sys
from PIL import Image


def parse_args():
    parser = argparse.ArgumentParser(description="Verify official extracted Fashionpedia images against annotations")
    parser.add_argument("--annotations", required=True, help="Path to instances_attributes_train2020.json or val2020.json")
    parser.add_argument("--images-root", required=True, help="Root directory of extracted images")
    parser.add_argument("--split", required=True, choices=["train", "val", "test"], help="Dataset split name")
    parser.add_argument("--output-report", required=True, help="Path to save output JSON verification report")
    return parser.parse_args()


def verify_image_file(image_path, expected_w, expected_h):
    """
    Verifies image decoding and compares decoded dimensions with expected dimensions.
    Returns (status, decoded_w, decoded_h, details_dict)
    """
    if not os.path.exists(image_path):
        return "missing_file", None, None, {"error": "File does not exist on disk"}

    try:
        # Open with EXIF transpose disabled for geometry comparison first
        with Image.open(image_path) as img:
            img.verify()

        with Image.open(image_path) as img:
            img.load()
            decoded_w, decoded_h = img.size

        if decoded_w <= 0 or decoded_h <= 0:
            return "corrupt_file", decoded_w, decoded_h, {"error": "Zero or negative decoded dimensions"}

        w_match = (decoded_w == expected_w)
        h_match = (decoded_h == expected_h)

        exp_ar = expected_w / max(expected_h, 1)
        dec_ar = decoded_w / max(decoded_h, 1)
        ar_match = (abs(exp_ar - dec_ar) < 0.001)

        if w_match and h_match:
            return "exact_match", decoded_w, decoded_h, {"width_match": True, "height_match": True}

        status_reasons = []
        if not w_match:
            status_reasons.append("width_mismatch")
        if not h_match:
            status_reasons.append("height_mismatch")
        if not ar_match:
            status_reasons.append("aspect_ratio_mismatch")

        primary_status = status_reasons[0] if status_reasons else "dimension_mismatch"

        return primary_status, decoded_w, decoded_h, {
            "width_match": w_match,
            "height_match": h_match,
            "aspect_ratio_match": ar_match,
            "expected_dimensions": [expected_w, expected_h],
            "decoded_dimensions": [decoded_w, decoded_h],
        }

    except Exception as e:
        return "corrupt_file", None, None, {"error": f"PIL decoding failure: {str(e)}"}


def main():
    args = parse_args()

    print(f"\n==========================================")
    print(f"Running Fashionpedia Image Verification ({args.split})")
    print(f"Annotations: {args.annotations}")
    print(f"Images Root: {args.images_root}")
    print(f"==========================================")

    if not os.path.exists(args.annotations):
        print(f"ERROR: Annotations file not found: {args.annotations}")
        sys.exit(1)

    print("Loading annotation JSON...")
    with open(args.annotations, "r", encoding="utf-8") as f:
        data = json.load(f)

    images_meta = data.get("images", [])
    print(f"Loaded {len(images_meta)} image records from annotation JSON.")

    # Check for duplicate image IDs and duplicate file names in annotation JSON
    seen_ids = set()
    duplicate_ids = []
    seen_filenames = set()
    duplicate_filenames = []

    for img in images_meta:
        img_id = img.get("id")
        file_name = img.get("file_name")

        if img_id in seen_ids:
            duplicate_ids.append(img_id)
        seen_ids.add(img_id)

        if file_name in seen_filenames:
            duplicate_filenames.append(file_name)
        seen_filenames.add(file_name)

    # Build disk file index under images_root
    print(f"Indexing extracted files under '{args.images_root}'...")
    disk_files = {}  # basename -> full_path
    for root, _, files in os.walk(args.images_root):
        for fname in files:
            if fname.lower().endswith((".jpg", ".jpeg", ".png")):
                full_p = os.path.join(root, fname)
                disk_files[fname] = full_p

    print(f"Found {len(disk_files)} image files on disk.")

    status_counts = {
        "exact_match": 0,
        "missing_file": 0,
        "corrupt_file": 0,
        "width_mismatch": 0,
        "height_mismatch": 0,
        "aspect_ratio_mismatch": 0,
    }

    matched_disk_filenames = set()
    verification_details = []

    for idx, img_rec in enumerate(images_meta, 1):
        img_id = img_rec.get("id")
        file_name = img_rec.get("file_name")
        expected_w = img_rec.get("width")
        expected_h = img_rec.get("height")

        # Resolve local disk file
        disk_path = disk_files.get(file_name)
        if not disk_path and file_name:
            # Also check direct split folder path
            split_folder = "train2020" if args.split == "train" else "val2020"
            direct_path = os.path.join(args.images_root, split_folder, file_name)
            if os.path.exists(direct_path):
                disk_path = direct_path

        if disk_path:
            matched_disk_filenames.add(file_name)

        status, dec_w, dec_h, details = verify_image_file(disk_path, expected_w, expected_h)
        if status in status_counts:
            status_counts[status] += 1
        else:
            status_counts[status] = status_counts.get(status, 0) + 1

        rec_detail = {
            "image_id": img_id,
            "file_name": file_name,
            "expected_width": expected_w,
            "expected_height": expected_h,
            "decoded_width": dec_w,
            "decoded_height": dec_h,
            "status": status,
            "details": details,
        }
        verification_details.append(rec_detail)

        if idx % 5000 == 0:
            print(f"Verified {idx} / {len(images_meta)} images...")

    # Identify unmatched files on disk
    unmatched_disk_files = [fname for fname in disk_files if fname not in matched_disk_filenames]

    total_images = len(images_meta)
    exact_match_pct = (status_counts["exact_match"] / max(total_images, 1)) * 100.0

    print(f"\n--- Fashionpedia Image Verification Summary ({args.split}) ---")
    print(f"Total Annotation Images: {total_images}")
    print(f"Exact Dimension Matches: {status_counts['exact_match']} ({exact_match_pct:.2f}%)")
    print(f"Missing Files:           {status_counts['missing_file']}")
    print(f"Corrupt Files:           {status_counts['corrupt_file']}")
    print(f"Width Mismatches:        {status_counts['width_mismatch']}")
    print(f"Height Mismatches:       {status_counts['height_mismatch']}")
    print(f"Aspect Ratio Mismatches: {status_counts['aspect_ratio_mismatch']}")
    print(f"Duplicate Image IDs:     {len(duplicate_ids)}")
    print(f"Duplicate File Names:   {len(duplicate_filenames)}")
    print(f"Unmatched Files on Disk: {len(unmatched_disk_files)}")

    os.makedirs(os.path.dirname(args.output_report), exist_ok=True)

    report_data = {
        "split": args.split,
        "annotations_file": args.annotations,
        "images_root": args.images_root,
        "total_annotation_images": total_images,
        "exact_match_percentage": round(exact_match_pct, 4),
        "status_counts": status_counts,
        "duplicate_image_ids_count": len(duplicate_ids),
        "duplicate_image_ids": duplicate_ids[:50],
        "duplicate_filenames_count": len(duplicate_filenames),
        "duplicate_filenames": duplicate_filenames[:50],
        "unmatched_disk_files_count": len(unmatched_disk_files),
        "unmatched_disk_files_sample": unmatched_disk_files[:50],
        "verification_details_sample": verification_details[:50],
    }

    with open(args.output_report, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2)

    print(f"Wrote verification report to '{args.output_report}'.")

    if status_counts["exact_match"] != total_images or status_counts["missing_file"] > 0 or status_counts["corrupt_file"] > 0:
        print(f"WARNING: Verification found non-matching or missing images.")
        sys.exit(1)
    else:
        print("VERIFICATION SUCCESSFUL: 100% exact dimension match with zero missing or corrupt files.")


if __name__ == "__main__":
    main()
