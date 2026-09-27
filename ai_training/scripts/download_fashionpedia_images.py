#!/usr/bin/env python3
"""
download_fashionpedia_images.py

Reusable downloader for official Fashionpedia CVDF image archives (Milestone M7).

Official Archive URLs:
1. https://s3.amazonaws.com/ifashionist-dataset/images/train2020.zip
2. https://s3.amazonaws.com/ifashionist-dataset/images/val_test2020.zip

Requirements:
- Download to temporary .part files
- Support HTTP Range resume when supported by server
- Robust retry loop for transient network timeouts
- Atomically rename .part to .zip after successful download
- Compute SHA-256 checksums
- Save metadata to ai_training/data/raw/fashionpedia/download_manifest.json
"""

import argparse
import datetime
import hashlib
import json
import os
import sys
import time
import urllib.request
import urllib.error

OFFICIAL_ARCHIVES = {
    "train2020": {
        "url": "https://s3.amazonaws.com/ifashionist-dataset/images/train2020.zip",
        "filename": "train2020.zip",
    },
    "val_test2020": {
        "url": "https://s3.amazonaws.com/ifashionist-dataset/images/val_test2020.zip",
        "filename": "val_test2020.zip",
    },
}


def parse_args():
    parser = argparse.ArgumentParser(description="Download official Fashionpedia image archives")
    parser.add_argument("--output-dir", required=True, help="Directory to save downloaded archives")
    parser.add_argument("--include-train", action="store_true", help="Download train2020.zip")
    parser.add_argument("--include-val-test", action="store_true", help="Download val_test2020.zip")
    parser.add_argument("--resume", action="store_true", default=True, help="Enable HTTP Range resume for partial downloads")
    parser.add_argument("--chunk-size", type=int, default=1048576, help="Chunk size in bytes for downloading (default 1MB)")
    parser.add_argument("--max-retries", type=int, default=10, help="Maximum retries for network timeouts")
    return parser.parse_args()


def compute_sha256(filepath, chunk_size=1048576):
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(chunk_size):
            h.update(chunk)
    return h.hexdigest()


def format_bytes(num_bytes):
    if num_bytes is None:
        return "Unknown"
    if num_bytes >= 1024**3:
        return f"{num_bytes / (1024**3):.2f} GB"
    if num_bytes >= 1024**2:
        return f"{num_bytes / (1024**2):.2f} MB"
    if num_bytes >= 1024:
        return f"{num_bytes / 1024:.2f} KB"
    return f"{num_bytes} B"


def fetch_head_metadata(url):
    headers = {"User-Agent": "DigitalTailorResearch/1.0"}
    req = urllib.request.Request(url, headers=headers, method="HEAD")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            content_length = resp.headers.get("Content-Length")
            total_size = int(content_length) if content_length and content_length.isdigit() else None
            accept_ranges = resp.headers.get("Accept-Ranges", "")
            etag = resp.headers.get("ETag", "").strip('"')
            last_modified = resp.headers.get("Last-Modified", "")
            return {
                "total_size": total_size,
                "supports_range": "bytes" in accept_ranges.lower(),
                "etag": etag,
                "last_modified": last_modified,
                "http_status": resp.status,
            }
    except Exception as e:
        print(f"Error fetching HEAD metadata for {url}: {e}")
        return None


def download_file_attempt(url, part_path, total_size, supports_range, allow_resume, chunk_size):
    """Single download session attempt with Range header if resuming."""
    initial_size = 0
    mode = "wb"
    request_headers = {"User-Agent": "DigitalTailorResearch/1.0"}

    if allow_resume and supports_range and os.path.exists(part_path):
        initial_size = os.path.getsize(part_path)
        if total_size and initial_size >= total_size:
            initial_size = 0
            mode = "wb"
        elif initial_size > 0:
            request_headers["Range"] = f"bytes={initial_size}-"
            mode = "ab"
            print(f"Resuming download from byte {initial_size} ({format_bytes(initial_size)})...")

    req = urllib.request.Request(url, headers=request_headers)
    start_time = time.time()
    downloaded_bytes = initial_size

    with urllib.request.urlopen(req, timeout=60) as resp:
        if resp.status == 200 and initial_size > 0 and mode == "ab":
            print("Server returned 200 OK (Range ignored). Resetting download from start...")
            initial_size = 0
            downloaded_bytes = 0
            mode = "wb"

        with open(part_path, mode) as out_f:
            last_print_time = start_time
            while True:
                chunk = resp.read(chunk_size)
                if not chunk:
                    break
                out_f.write(chunk)
                downloaded_bytes += len(chunk)

                now = time.time()
                if now - last_print_time >= 1.0 or (total_size and downloaded_bytes == total_size):
                    last_print_time = now
                    speed = (downloaded_bytes - initial_size) / max(now - start_time, 0.001)
                    pct_str = f"{(downloaded_bytes / total_size) * 100:.1f}%" if total_size else "N/A"
                    print(f"[{format_bytes(downloaded_bytes)} / {format_bytes(total_size)}] ({pct_str}) | Speed: {format_bytes(speed)}/s")

    return downloaded_bytes


def download_file(url, target_zip_path, allow_resume=True, chunk_size=1048576, max_retries=10):
    part_path = target_zip_path + ".part"
    head_meta = fetch_head_metadata(url)
    if not head_meta:
        return False, {"error": "Failed to query remote metadata via HTTP HEAD"}

    total_size = head_meta["total_size"]
    supports_range = head_meta["supports_range"]

    # Check if target .zip already exists and matches expected size
    if os.path.exists(target_zip_path):
        existing_size = os.path.getsize(target_zip_path)
        if total_size is not None and existing_size == total_size:
            print(f"Archive '{target_zip_path}' already fully downloaded ({format_bytes(existing_size)}). Validating SHA-256...")
            sha256_checksum = compute_sha256(target_zip_path)
            return True, {
                "url": url,
                "file_path": os.path.relpath(target_zip_path, start=os.getcwd()).replace("\\", "/"),
                "file_size": existing_size,
                "etag": head_meta["etag"],
                "last_modified": head_meta["last_modified"],
                "sha256": sha256_checksum,
                "download_timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "skipped_existing": True,
            }

    for attempt in range(1, max_retries + 1):
        try:
            print(f"\nDownload attempt {attempt}/{max_retries} for {url}...")
            download_file_attempt(url, part_path, total_size, supports_range, allow_resume, chunk_size)

            final_part_size = os.path.getsize(part_path)
            if total_size is not None and final_part_size == total_size:
                print(f"Download complete ({format_bytes(final_part_size)}). Atomically renaming .part -> .zip...")
                os.replace(part_path, target_zip_path)
                print(f"Computing SHA-256 checksum for '{target_zip_path}'...")
                sha256_checksum = compute_sha256(target_zip_path)

                return True, {
                    "url": url,
                    "file_path": os.path.relpath(target_zip_path, start=os.getcwd()).replace("\\", "/"),
                    "file_size": final_part_size,
                    "etag": head_meta["etag"],
                    "last_modified": head_meta["last_modified"],
                    "sha256": sha256_checksum,
                    "download_timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    "skipped_existing": False,
                }
        except Exception as e:
            print(f"Attempt {attempt}/{max_retries} interrupted: {e}")
            if attempt < max_retries:
                time.sleep(3.0)

    return False, {"error": f"Exhausted {max_retries} download attempts"}


def main():
    args = parse_args()

    if not args.include_train and not args.include_val_test:
        print("ERROR: Must specify at least one of --include-train or --include-val-test")
        sys.exit(1)

    os.makedirs(args.output_dir, exist_ok=True)
    manifest_dir = os.path.dirname(args.output_dir)
    manifest_path = os.path.join(manifest_dir, "download_manifest.json")

    manifest_data = {}
    if os.path.exists(manifest_path):
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest_data = json.load(f)
        except Exception:
            manifest_data = {}

    targets = []
    if args.include_train:
        targets.append("train2020")
    if args.include_val_test:
        targets.append("val_test2020")

    success_all = True

    for name in targets:
        info = OFFICIAL_ARCHIVES[name]
        url = info["url"]
        target_path = os.path.join(args.output_dir, info["filename"])

        print(f"\n==========================================")
        print(f"Processing official archive: {name}")
        print(f"URL: {url}")
        print(f"Target: {target_path}")
        print(f"==========================================")

        success, meta = download_file(
            url=url,
            target_zip_path=target_path,
            allow_resume=args.resume,
            chunk_size=args.chunk_size,
            max_retries=args.max_retries,
        )

        if success:
            manifest_data[name] = meta
            print(f"Successfully processed {name}. SHA-256: {meta.get('sha256')}")
        else:
            print(f"FAILED to download {name}: {meta.get('error')}")
            success_all = False
            break

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2)

    print(f"\nUpdated download manifest at {manifest_path}.")

    if not success_all:
        sys.exit(1)


if __name__ == "__main__":
    main()
