#!/usr/bin/env python3
"""
validate_fashionpedia_mapping.py

Validates fashionpedia_mapping.json against classes.json and the official
Fashionpedia metadata JSON file. Calculates status totals dynamically.

Usage:
    python ai_training/scripts/validate_fashionpedia_mapping.py <classes.json> <fashionpedia_mapping.json> <fashionpedia_meta.json>
"""

import sys
import json
import os


def validate_mapping(classes_path, mapping_path, meta_path):
    for path in [classes_path, mapping_path, meta_path]:
        if not os.path.exists(path):
            print(f"ERROR: Required file not found at: {path}", file=sys.stderr)
            sys.exit(1)

    try:
        with open(classes_path, "r", encoding="utf-8") as f:
            classes_data = json.load(f)
        with open(mapping_path, "r", encoding="utf-8") as f:
            mapping_data = json.load(f)
        with open(meta_path, "r", encoding="utf-8") as f:
            meta_data = json.load(f)
    except Exception as e:
        print(f"ERROR: Failed to load JSON files: {e}", file=sys.stderr)
        sys.exit(1)

    valid_categories = {c["id"]: c["name"] for c in meta_data.get("categories", [])}
    valid_attributes = {a["id"]: a["name"] for a in meta_data.get("attributes", [])}

    print("==================================================")
    print("FASHIONPEDIA MAPPING VALIDATION RUN")
    print("==================================================")

    # 1. Four output heads match classes.json
    expected_heads = list(classes_data.get("outputs", {}).keys())
    mapping_outputs = mapping_data.get("outputs", {})
    mapping_heads = list(mapping_outputs.keys())

    if expected_heads != mapping_heads:
        print(f"ERROR: Output heads mismatch. Expected: {expected_heads}, Got: {mapping_heads}", file=sys.stderr)
        sys.exit(1)
    print("1. Four output heads match classes.json: PASSED")

    # 2. Check labels completeness & uniqueness head by head
    allowed_statuses = {"direct", "candidate_mapping", "unsupported"}
    allowed_logics = {"single", "any", "all", "derived", None}

    mapped_labels_all = []
    status_counts = {"direct": 0, "candidate_mapping": 0, "unsupported": 0}

    for head_name, expected_info in classes_data["outputs"].items():
        expected_head_labels = expected_info["classes"]
        mapping_head_items = mapping_outputs.get(head_name, [])

        if not isinstance(mapping_head_items, list):
            print(f"ERROR: Head '{head_name}' in mapping must be a list.", file=sys.stderr)
            sys.exit(1)

        actual_head_labels = [item.get("target_label") for item in mapping_head_items]

        if actual_head_labels != expected_head_labels:
            print(f"ERROR: Label mismatch under head '{head_name}'. Expected: {expected_head_labels}, Got: {actual_head_labels}", file=sys.stderr)
            sys.exit(1)

        for item in mapping_head_items:
            lbl = item.get("target_label")
            status = item.get("status")
            logic = item.get("mapping_logic")
            evidence = item.get("source_evidence")
            rule = item.get("mapping_rule")

            mapped_labels_all.append(lbl)

            if status not in allowed_statuses:
                print(f"ERROR: Invalid status '{status}' for label '{lbl}'. Allowed: {allowed_statuses}", file=sys.stderr)
                sys.exit(1)

            if logic not in allowed_logics:
                print(f"ERROR: Invalid mapping_logic '{logic}' for label '{lbl}'. Allowed: {allowed_logics}", file=sys.stderr)
                sys.exit(1)

            if not isinstance(evidence, list):
                print(f"ERROR: source_evidence for label '{lbl}' must be an array (list).", file=sys.stderr)
                sys.exit(1)

            # Tally counts dynamically
            status_counts[status] += 1

            if status == "direct":
                if len(evidence) == 0:
                    print(f"ERROR: Direct mapping '{lbl}' must contain at least one source_evidence entry.", file=sys.stderr)
                    sys.exit(1)

            elif status == "candidate_mapping":
                if len(evidence) == 0 and (not rule or len(rule.strip()) == 0):
                    print(f"ERROR: Candidate mapping '{lbl}' must contain evidence or an explicit derived mapping rule.", file=sys.stderr)
                    sys.exit(1)

            elif status == "unsupported":
                if len(evidence) != 0:
                    print(f"ERROR: Unsupported mapping '{lbl}' must have an empty source_evidence array.", file=sys.stderr)
                    sys.exit(1)

            # Validate each evidence entry against metadata
            for ev in evidence:
                stype = ev.get("source_type")
                sid = ev.get("source_id")
                sname = ev.get("source_name")

                if stype not in ["category", "attribute"]:
                    print(f"ERROR: Invalid source_type '{stype}' in evidence for label '{lbl}'.", file=sys.stderr)
                    sys.exit(1)

                if stype == "category":
                    if sid not in valid_categories:
                        print(f"ERROR: Unknown Category ID {sid} for label '{lbl}'.", file=sys.stderr)
                        sys.exit(1)
                    if valid_categories[sid] != sname:
                        print(f"ERROR: Category ID {sid} name mismatch for label '{lbl}'. Expected '{valid_categories[sid]}', got '{sname}'.", file=sys.stderr)
                        sys.exit(1)

                elif stype == "attribute":
                    if sid not in valid_attributes:
                        print(f"ERROR: Unknown Attribute ID {sid} for label '{lbl}'.", file=sys.stderr)
                        sys.exit(1)
                    if valid_attributes[sid] != sname:
                        print(f"ERROR: Attribute ID {sid} name mismatch for label '{lbl}'. Expected '{valid_attributes[sid]}', got '{sname}'.", file=sys.stderr)
                        sys.exit(1)

    print("2. Target labels completeness & model head alignment: PASSED")
    print("3. Metadata ID, name, and evidence constraints validation: PASSED")

    # 3. Dynamic status totals computation
    total_calculated = sum(status_counts.values())
    print("\nCalculated Status Totals:")
    print(f"   - Direct Mappings: {status_counts['direct']}")
    print(f"   - Candidate Mappings: {status_counts['candidate_mapping']}")
    print(f"   - Unsupported Targets: {status_counts['unsupported']}")
    print(f"   - Total Evaluated Labels: {total_calculated}")

    if total_calculated != 29:
        print(f"ERROR: Total evaluated labels sum ({total_calculated}) does not equal 29.", file=sys.stderr)
        sys.exit(1)

    print("\n4. Dynamic totals sum equals 29: PASSED")
    print("==================================================")
    print("ALL MAPPING VALIDATIONS PASSED CLEANLY!")
    print("==================================================")


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("ERROR: Missing CLI arguments.", file=sys.stderr)
        print("Usage: python ai_training/scripts/validate_fashionpedia_mapping.py <classes.json> <fashionpedia_mapping.json> <fashionpedia_meta.json>")
        sys.exit(1)

    validate_mapping(sys.argv[1], sys.argv[2], sys.argv[3])
