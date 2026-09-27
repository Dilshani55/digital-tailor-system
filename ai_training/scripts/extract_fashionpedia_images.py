#!/usr/bin/env python3
"""
extract_fashionpedia_images.py

Validates and safely extracts official Fashionpedia ZIP archives (Milestone M7).

Requirements:
- Use zipfile testzip() to verify integrity before extraction
- Reject unsafe ZIP member paths (absolute paths, '..' traversal)
- Detect duplicate member paths
- Streamed extraction to avoid high memory usage
- Extract to ai_training/data/raw/fashionpedia/images/
- Preserve original file names and folder structures
"""

import argparse
import os
import sys
import zipfile


def parse_args():
    parser = argparse.ArgumentParser(description="Validate and extract official Fashionpedia ZIP archives")
    parser.add_argument("--archive", required=True, help="Path to ZIP archive file")
    parser.add_argument("--output-dir", required=True, help="Root directory for extracted images")
    parser.add_argument("--chunk-size", type=int, default=1048576, help="Streamed extraction chunk size in bytes")
    return parser.parse_args()


def validate_archive_paths(zip_file):
    """
    Checks for unsafe member names (absolute paths, '..' directory traversal) and duplicate member paths.
    Returns (is_safe, error_message, member_list)
    """
    seen_paths = set()
    duplicate_paths = []
    unsafe_paths = []
    valid_members = []

    for member in zip_file.infolist():
        name = member.filename

        # Check duplicate paths
        if name in seen_paths:
            duplicate_paths.append(name)
        seen_annotation_name = name
        seen_paths.add(name)

        # Check unsafe paths: absolute path or directory traversal
        norm_path = os.path.normpath(name)
        if norm_path.startswith("..") or os.path.isabs(norm_path) or "/../" in name or "\\..\\" in name:
            unsafe_paths.append(name)

        valid_members.append(member)

    if unsafe_paths:
        return False, f"ZIP contains {len(unsafe_paths)} unsafe path(s) (e.g. '{unsafe_paths[0]}')", []

    if duplicate_paths:
        print(f"Warning: ZIP contains {len(duplicate_paths)} duplicate member path(s).")

    return True, None, valid_members


def validate_zip_file(archive_path):
    """
    Runs zipfile.testzip() and path validation.
    Returns (is_valid, summary_dict)
    """
    print(f"\n==========================================")
    print(f"Validating ZIP archive: {archive_path}")
    print(f"==========================================")

    if not os.path.exists(archive_path):
        return False, {"error": f"Archive file does not exist: {archive_path}"}

    try:
        with zipfile.ZipFile(archive_path, "r") as zf:
            print("Testing ZIP integrity using testzip()...")
            bad_file = zf.testzip()
            if bad_file is not None:
                return False, {"error": f"Corrupted member in ZIP: {bad_file}"}
            print("testzip() passed: No corrupted files found.")

            is_safe, err_msg, members = validate_archive_paths(zf)
            if not is_safe:
                return False, {"error": err_msg}

            total_entries = len(members)
            image_entries = [m for m in members if not m.is_dir() and m.filename.lower().endswith((".jpg", ".jpeg", ".png"))]

            compressed_bytes = sum(m.compress_size for m in members)
            uncompressed_bytes = sum(m.file_size for m in members)

            print(f"Archive Summary:")
            print(f"  - Total entries: {total_entries}")
            print(f"  - Image entries: {len(image_entries)}")
            print(f"  - Compressed total: {compressed_bytes / (1024**3):.2f} GB ({compressed_bytes} bytes)")
            print(f"  - Uncompressed total: {uncompressed_bytes / (1024**3):.2f} GB ({uncompressed_bytes} bytes)")

            return True, {
                "archive_path": archive_path,
                "total_entries": total_entries,
                "image_entries": len(image_entries),
                "compressed_bytes": compressed_bytes,
                "uncompressed_bytes": uncompressed_bytes,
                "members": members,
            }

    except Exception as e:
        return False, {"error": f"Failed to open or test ZIP file: {str(e)}"}


def safe_extract_archive(archive_path, output_root, chunk_size=1048576):
    """
    Safely extracts archive_path into output_root using streamed I/O.
    """
    is_valid, summary = validate_zip_file(archive_path)
    if not is_valid:
        print(f"ERROR: Archive validation failed: {summary.get('error')}")
        return False, summary

    members = summary["members"]
    os.makedirs(output_root, exist_ok=True)

    extracted_count = 0
    skipped_count = 0

    print(f"\nExtracting archive into '{output_root}' using streamed I/O...")
    with zipfile.ZipFile(archive_path, "r") as zf:
        for idx, member in enumerate(members, 1):
            if member.is_dir():
                continue

            target_file_path = os.path.join(output_root, member.filename)
            target_dir = os.path.dirname(target_file_path)
            os.makedirs(target_dir, exist_ok=True)

            # Skip if file already exists with identical size
            if os.path.exists(target_file_path):
                if os.path.getsize(target_file_path) == member.file_size:
                    skipped_count += 1
                    continue

            # Streamed extraction
            with zf.open(member) as source, open(target_file_path, "wb") as target:
                while chunk := source.read(chunk_size):
                    target.write(chunk)
            extracted_count += 1

            if extracted_count % 1000 == 0:
                print(f"Extracted {extracted_count} / {len(members)} entries...")

    print(f"Extraction complete for {archive_path}: Extracted={extracted_count}, Skipped (existing)={skipped_count}")
    return True, {
        "archive_path": archive_path,
        "extracted_count": extracted_count,
        "skipped_count": skipped_count,
        "total_images": summary["image_entries"],
        "uncompressed_bytes": summary["uncompressed_bytes"],
    }


def main():
    args = parse_args()
    success, summary = safe_extract_archive(args.archive, args.output_dir, args.chunk_size)
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
