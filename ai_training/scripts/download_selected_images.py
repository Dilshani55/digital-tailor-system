#!/usr/bin/env python3
"""
download_selected_images.py

Downloads selected candidate images from Fashionpedia original URLs (Milestone AI-6B).

Requirements:
- Download only records from candidate_queue.jsonl
- Store images under: ai_training/data/images/fashionpedia_selected/original/
- Deterministic filenames based on source image ID
- Validate HTTP response and image decoding with PIL
- Reject HTML/error responses
- Apply timeouts and limited retries
- Never overwrite a valid existing image
- Compute SHA-256 for each downloaded image
- Record success/failed/unavailable/invalid status
- Never download more than configured max_download_target
- Create download_manifest.jsonl and download_summary.json
"""

import argparse
import hashlib
import json
import os
import sys
import time
import urllib.request
import urllib.error
from PIL import Image


def parse_args():
    parser = argparse.ArgumentParser(description="Download candidate images from Fashionpedia original URLs")
    parser.add_argument("--queue", required=True, help="Path to candidate_queue.jsonl")
    parser.add_argument("--config", required=True, help="Path to config/ai_assisted_labelling.json")
    parser.add_argument("--output-dir", required=True, help="Directory to store downloaded images")
    parser.add_argument("--manifest-dir", required=True, help="Directory to store download manifest and summary")
    return parser.parse_args()


def compute_sha256(filepath):
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()


def validate_image_file(filepath):
    try:
        with Image.open(filepath) as img:
            img.verify()
        with Image.open(filepath) as img:
            img.load()
            w, h = img.size
            if w <= 0 or h <= 0:
                return False, "Zero or negative dimensions"
            return True, None
    except Exception as e:
        return False, str(e)


def download_image(url, target_path, timeout, max_retries):
    """
    Downloads image with timeouts and limited retries.
    Returns (status, http_code, sha256_hash, error_msg)
    """
    if not url or not isinstance(url, str) or not url.startswith("http"):
        return "unavailable", None, None, "Missing or invalid URL format"

    headers = {
        "User-Agent": "DigitalTailorResearch/1.0 (Educational/Research Garment Analysis)"
    }
    req = urllib.request.Request(url, headers=headers)

    for attempt in range(1 + max_retries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                http_code = response.getcode()
                content_type = response.headers.get("Content-Type", "")
                
                # Check for HTML responses (error pages)
                if "html" in content_type.lower():
                    return "failed", http_code, None, f"Server returned HTML response ({content_type})"

                content = response.read()

                # Save temporarily to target path
                with open(target_path, "wb") as f:
                    f.write(content)

                # Validate image content
                valid, img_err = validate_image_file(target_path)
                if not valid:
                    if os.path.exists(target_path):
                        os.remove(target_path)
                    return "invalid", http_code, None, f"Downloaded content is not a valid image: {img_err}"

                sha256_hash = compute_sha256(target_path)
                return "success", http_code, sha256_hash, None

        except urllib.error.HTTPError as e:
            http_code = e.code
            if attempt == max_retries:
                return "failed", http_code, None, f"HTTPError {e.code}: {e.reason}"
            time.sleep(1.0)
        except urllib.error.URLError as e:
            if attempt == max_retries:
                return "failed", None, None, f"URLError: {e.reason}"
            time.sleep(1.0)
        except Exception as e:
            if attempt == max_retries:
                return "failed", None, None, f"Download error: {str(e)}"
            time.sleep(1.0)

    return "failed", None, None, "Exhausted retries"


def main():
    args = parse_args()

    with open(args.config, "r", encoding="utf-8") as f:
        config = json.load(f)

    max_downloads = config.get("max_download_target", 450)
    retry_rules = config.get("retry_timeout_rules", {})
    timeout = retry_rules.get("timeout_seconds", 10)
    max_retries = retry_rules.get("max_retries", 2)

    os.makedirs(args.output_dir, exist_ok=True)
    os.makedirs(args.manifest_dir, exist_ok=True)

    print(f"Reading candidate queue from {args.queue}...")
    candidates = []
    with open(args.queue, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                candidates.append(json.loads(line.strip()))

    print(f"Loaded {len(candidates)} candidate queue records.")

    manifest_records = []
    status_counts = {"success": 0, "failed": 0, "unavailable": 0, "invalid": 0, "skipped_existing": 0}
    
    downloaded_count = 0

    for idx, cand in enumerate(candidates, 1):
        if downloaded_count >= max_downloads:
            print(f"Reached maximum download target ({max_downloads}). Stopping downloads.")
            break

        img_id = cand["source_image_id"]
        ann_id = cand["source_annotation_id"]
        url = cand.get("original_url")
        file_name = cand.get("file_name") or f"{img_id}.jpg"
        
        # Deterministic local filename
        local_filename = f"{img_id}_{file_name}" if not file_name.startswith(str(img_id)) else file_name
        local_path = os.path.join(args.output_dir, local_filename)
        rel_local_path = os.path.relpath(local_path, start=os.getcwd()).replace("\\", "/")

        sha256_hash = None
        http_code = None
        error_msg = None
        status = "pending"

        # Check if file already exists and is valid
        if os.path.exists(local_path):
            valid, img_err = validate_image_file(local_path)
            if valid:
                status = "success"
                http_code = 200
                sha256_hash = compute_sha256(local_path)
                status_counts["skipped_existing"] += 1
                status_counts["success"] += 1
                downloaded_count += 1
            else:
                # Remove invalid existing file and re-download
                os.remove(local_path)

        if status == "pending":
            print(f"[{idx}/{len(candidates)}] Downloading image_id={img_id} from {url}...")
            status, http_code, sha256_hash, error_msg = download_image(url, local_path, timeout, max_retries)
            status_counts[status] += 1
            if status == "success":
                downloaded_count += 1

        manifest_record = {
            "source_image_id": img_id,
            "source_annotation_id": ann_id,
            "file_name": file_name,
            "original_url": url,
            "local_path": rel_local_path,
            "status": status,
            "http_status": http_code,
            "sha256": sha256_hash,
            "error_message": error_msg,
            "candidate_garment_type": cand.get("candidate_garment_type"),
            "candidate_garment_reason": cand.get("candidate_garment_reason"),
            "split": cand.get("split", "train"),
            "bbox": cand.get("bbox"),
            "disclaimer": "Original image downloaded from Fashionpedia candidate pool for research screening."
        }
        manifest_records.append(manifest_record)

    manifest_path = os.path.join(args.manifest_dir, "download_manifest.jsonl")
    summary_path = os.path.join(args.manifest_dir, "download_summary.json")

    print(f"Writing download manifest to {manifest_path}...")
    with open(manifest_path, "w", encoding="utf-8") as f:
        for rec in manifest_records:
            f.write(json.dumps(rec) + "\n")

    summary = {
        "total_queued": len(candidates),
        "total_processed": len(manifest_records),
        "max_download_target": max_downloads,
        "status_counts": status_counts,
        "success_rate": status_counts["success"] / max(len(manifest_records), 1),
    }

    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"Wrote download summary to {summary_path}.")
    print(f"Download results: {status_counts}")


if __name__ == "__main__":
    main()
