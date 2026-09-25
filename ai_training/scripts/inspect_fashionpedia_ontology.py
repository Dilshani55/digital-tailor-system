#!/usr/bin/env python3
"""
inspect_fashionpedia_ontology.py

Inspects the official Fashionpedia annotation metadata JSON file.
Validates structure, extracts category and attribute taxonomies,
detects duplicate IDs/names, and prints exact names.

Usage:
    python ai_training/scripts/inspect_fashionpedia_ontology.py <path_to_json>
"""

import sys
import json
import os
from collections import Counter


def inspect_ontology(json_path):
    if not os.path.exists(json_path):
        print(f"ERROR: File not found at path: {json_path}", file=sys.stderr)
        sys.exit(1)

    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"ERROR: Malformed JSON or read error: {e}", file=sys.stderr)
        sys.exit(1)

    if not isinstance(data, dict):
        print("ERROR: Expected top-level JSON object (dict).", file=sys.stderr)
        sys.exit(1)

    missing_keys = [key for key in ["categories", "attributes"] if key not in data]
    if missing_keys:
        print(f"ERROR: Missing required keys in JSON: {missing_keys}", file=sys.stderr)
        sys.exit(1)

    categories = data.get("categories", [])
    attributes = data.get("attributes", [])

    if not isinstance(categories, list) or not isinstance(attributes, list):
        print("ERROR: 'categories' and 'attributes' must be lists.", file=sys.stderr)
        sys.exit(1)

    print("==================================================")
    print("FASHIONPEDIA ONTOLOGY INSPECTION SUMMARY")
    print("==================================================")
    print(f"Source JSON file: {os.path.abspath(json_path)}")
    print(f"Category Total: {len(categories)}")
    print(f"Attribute Total: {len(attributes)}")

    # Category analysis
    cat_ids = [c.get("id") for c in categories]
    cat_names = [c.get("name") for c in categories]
    
    cat_id_counts = Counter(cat_ids)
    cat_name_counts = Counter(cat_names)

    dup_cat_ids = [cid for cid, count in cat_id_counts.items() if count > 1]
    dup_cat_names = [name for name, count in cat_name_counts.items() if count > 1]

    print("\n--- CATEGORIES (27 expected) ---")
    if dup_cat_ids:
        print(f"WARNING: Duplicate category IDs found: {dup_cat_ids}")
    else:
        print("Category IDs unique: True")

    if dup_cat_names:
        print(f"WARNING: Duplicate category names found: {dup_cat_names}")
    else:
        print("Category names unique: True")

    for cat in sorted(categories, key=lambda x: x.get("id", 0)):
        cid = cat.get("id")
        cname = cat.get("name")
        csuper = cat.get("supercategory", "N/A")
        print(f"  [ID {cid:2d}] {cname} (supercategory: {csuper})")

    # Attribute analysis
    attr_ids = [a.get("id") for a in attributes]
    attr_names = [a.get("name") for a in attributes]
    attr_supercategories = [a.get("supercategory") for a in attributes if "supercategory" in a]

    attr_id_counts = Counter(attr_ids)
    attr_name_counts = Counter(attr_names)

    dup_attr_ids = [aid for aid, count in attr_id_counts.items() if count > 1]
    dup_attr_names = [name for name, count in attr_name_counts.items() if count > 1]

    print(f"\n--- ATTRIBUTES ({len(attributes)} total, 294 expected) ---")
    if dup_attr_ids:
        print(f"WARNING: Duplicate attribute IDs found: {dup_attr_ids}")
    else:
        print("Attribute IDs unique: True")

    if dup_attr_names:
        print(f"WARNING: Duplicate attribute names found: {dup_attr_names}")
    else:
        print("Attribute names unique: True")

    if attr_supercategories:
        super_counts = Counter(attr_supercategories)
        print("\nAttribute Groups (Supercategories):")
        for group, count in super_counts.most_common():
            print(f"  - {group}: {count} attributes")

    print("\nExact Attribute Listing:")
    for attr in sorted(attributes, key=lambda x: x.get("id", 0)):
        aid = attr.get("id")
        aname = attr.get("name")
        asuper = attr.get("supercategory", "N/A")
        print(f"  [ID {aid:3d}] {aname} (group: {asuper})")

    print("\n==================================================")
    print("ONTOLOGY INSPECTION COMPLETED SUCCESSFULLY")
    print("==================================================")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("ERROR: Missing command-line argument <path_to_json>.", file=sys.stderr)
        print("Usage: python ai_training/scripts/inspect_fashionpedia_ontology.py <path_to_json>")
        sys.exit(1)

    inspect_ontology(sys.argv[1])
