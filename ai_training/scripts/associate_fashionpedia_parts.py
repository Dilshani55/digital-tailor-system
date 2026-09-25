#!/usr/bin/env python3
"""
associate_fashionpedia_parts.py

Performs evidence-preserving spatial association of Fashionpedia garment-part annotations
(sleeve = 31, neckline = 33, collar = 28) to parent upper-garment instances (category 0 or 1).

Usage:
    python ai_training/scripts/associate_fashionpedia_parts.py \
      --annotations ai_training/data/raw/fashionpedia/instances_attributes_val2020.json \
      --base-manifest ai_training/data/processed/fashionpedia_manifest/all_instances.jsonl \
      --classes ai_training/config/classes.json \
      --mapping ai_training/config/fashionpedia_mapping.json \
      --association-config ai_training/config/part_association.json \
      --output-dir ai_training/data/processed/fashionpedia_spatial_manifest
"""

import sys
import os
import json
import math
import argparse
import hashlib
from datetime import datetime, timezone
from collections import defaultdict


def compute_sha256(filepath):
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def validate_bbox(bbox):
    if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
        return False
    try:
        x, y, w, h = float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])
        if x < 0 or y < 0 or w <= 0 or h <= 0:
            return False
        return True
    except (ValueError, TypeError):
        return False


def calculate_spatial_metrics(part_bbox, parent_bbox, weights, min_part_coverage, require_centre_inside):
    """
    Calculates spatial overlap and distance metrics between a part bbox and a parent bbox.
    Returns (score, metrics, passes_thresholds)
    """
    if not validate_bbox(part_bbox) or not validate_bbox(parent_bbox):
        return 0.0, {}, False

    px, py, pw, ph = [float(v) for v in part_bbox]
    gx, gy, gw, gh = [float(v) for v in parent_bbox]

    part_area = pw * ph
    parent_area = gw * gh

    # Intersection box
    ix1 = max(px, gx)
    iy1 = max(py, gy)
    ix2 = min(px + pw, gx + gw)
    iy2 = min(py + ph, gy + gh)

    iw = max(0.0, ix2 - ix1)
    ih = max(0.0, iy2 - iy1)
    intersection_area = iw * ih

    part_coverage = intersection_area / part_area if part_area > 0 else 0.0
    parent_coverage = intersection_area / parent_area if parent_area > 0 else 0.0

    # Part centre point
    pcx = px + pw / 2.0
    pcy = py + ph / 2.0

    part_centre_inside = (gx <= pcx <= gx + gw) and (gy <= pcy <= gy + gh)

    # Parent centre point & diagonal distance
    gcx = gx + gw / 2.0
    gcy = gy + gh / 2.0
    center_dist = math.sqrt((pcx - gcx) ** 2 + (pcy - gcy) ** 2)
    parent_diag = math.sqrt(gw ** 2 + gh ** 2)
    norm_centre_dist = min(1.0, center_dist / parent_diag) if parent_diag > 0 else 1.0

    metrics = {
        "intersection_area": round(intersection_area, 4),
        "part_area": round(part_area, 4),
        "parent_area": round(parent_area, 4),
        "part_coverage": round(part_coverage, 4),
        "parent_coverage": round(parent_coverage, 4),
        "part_centre_inside": part_centre_inside,
        "normalized_centre_distance": round(norm_centre_dist, 4),
    }

    # Threshold checks
    if part_coverage < min_part_coverage:
        return 0.0, metrics, False
    if require_centre_inside and not part_centre_inside:
        return 0.0, metrics, False

    # Calculate weighted score
    w_pcov = weights.get("part_coverage", 0.60)
    w_cdist = weights.get("centre_distance", 0.30)
    w_gcov = weights.get("parent_coverage", 0.10)

    score = (w_pcov * part_coverage) + (w_cdist * (1.0 - norm_centre_dist)) + (w_gcov * parent_coverage)
    score = round(score, 4)

    return score, metrics, True


def run_spatial_association(annotations_path, base_manifest_path, classes_path, mapping_path, assoc_config_path, output_dir):
    # Verify inputs
    for p in [annotations_path, base_manifest_path, classes_path, mapping_path, assoc_config_path]:
        if not os.path.exists(p):
            print(f"ERROR: File not found: {p}", file=sys.stderr)
            sys.exit(1)

    input_sha256 = {
        "annotations": compute_sha256(annotations_path),
        "base_manifest": compute_sha256(base_manifest_path),
        "classes": compute_sha256(classes_path),
        "mapping": compute_sha256(mapping_path),
        "association_config": compute_sha256(assoc_config_path),
    }

    try:
        with open(annotations_path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)
        with open(base_manifest_path, "r", encoding="utf-8") as f:
            base_records = [json.loads(line) for line in f]
        with open(classes_path, "r", encoding="utf-8") as f:
            classes_data = json.load(f)
        with open(mapping_path, "r", encoding="utf-8") as f:
            mapping_data = json.load(f)
        with open(assoc_config_path, "r", encoding="utf-8") as f:
            assoc_config = json.load(f)
    except Exception as e:
        print(f"ERROR: Failed to load JSON files: {e}", file=sys.stderr)
        sys.exit(1)

    # Config parameters
    eligible_parents = set(assoc_config.get("eligible_parent_category_ids", [0, 1]))
    part_cat_ids = assoc_config.get("part_category_ids", {"collar": 28, "sleeve": 31, "neckline": 33})
    inv_part_cat_ids = {v: k for k, v in part_cat_ids.items()}

    min_part_cov = assoc_config.get("minimum_part_coverage", 0.80)
    min_score_margin = assoc_config.get("minimum_score_margin", 0.15)
    req_centre_inside = assoc_config.get("centre_inside_parent", True)
    weights = assoc_config.get("scoring_weights", {"part_coverage": 0.60, "centre_distance": 0.30, "parent_coverage": 0.10})

    # Metadata lookups
    categories_dict = {c["id"]: c["name"] for c in raw_data.get("categories", [])}
    attributes_dict = {a["id"]: a["name"] for a in raw_data.get("attributes", [])}
    head_mappings = mapping_data.get("outputs", {})

    # Group base parent records by image_id
    image_to_parents = defaultdict(list)
    parent_by_ann_id = {}
    for r in base_records:
        img_id = r["source_image_id"]
        cat_id = r["fashionpedia_category_id"]
        if cat_id in eligible_parents:
            image_to_parents[img_id].append(r)
            parent_by_ann_id[r["source_annotation_id"]] = r

    # Extract part annotations from raw JSON
    raw_parts = [ann for ann in raw_data.get("annotations", []) if ann.get("category_id") in inv_part_cat_ids]

    part_counts_by_type = {"sleeve": 0, "neckline": 0, "collar": 0, "total": len(raw_parts)}
    for p in raw_parts:
        ptype = inv_part_cat_ids.get(p.get("category_id"), "unknown")
        if ptype in part_counts_by_type:
            part_counts_by_type[ptype] += 1

    accepted_associations = []
    ambiguous_associations = []
    unassociated_parts = []

    # Track attached child parts per parent instance: parent_ann_id -> list of attached part info
    parent_attached_parts = defaultdict(list)

    # Process each part annotation
    for part in raw_parts:
        part_ann_id = part.get("id")
        part_img_id = part.get("image_id")
        part_cat_id = part.get("category_id")
        part_bbox = part.get("bbox")
        part_attr_ids = part.get("attribute_ids", [])
        part_type = inv_part_cat_ids.get(part_cat_id, "unknown")
        part_cat_name = categories_dict.get(part_cat_id, part_type)
        part_attr_names = [attributes_dict.get(aid, f"unknown_{aid}") for aid in part_attr_ids]

        part_record_base = {
            "part_annotation_id": part_ann_id,
            "source_image_id": part_img_id,
            "part_category_id": part_cat_id,
            "part_category_name": part_cat_name,
            "part_type": part_type,
            "part_bbox": part_bbox,
            "part_attribute_ids": part_attr_ids,
            "part_attribute_names": part_attr_names,
        }

        cand_parents = image_to_parents.get(part_img_id, [])

        if not validate_bbox(part_bbox):
            unassoc_entry = dict(part_record_base)
            unassoc_entry["reason"] = "INVALID_PART_BBOX"
            unassociated_parts.append(unassoc_entry)
            continue

        if not cand_parents:
            unassoc_entry = dict(part_record_base)
            unassoc_entry["reason"] = "NO_ELIGIBLE_PARENT_IN_IMAGE"
            unassociated_parts.append(unassoc_entry)
            continue

        # Evaluate candidate parents
        scored_candidates = []
        for parent in cand_parents:
            parent_ann_id = parent["source_annotation_id"]
            parent_bbox = parent["bbox"]

            score, metrics, passes = calculate_spatial_metrics(
                part_bbox=part_bbox,
                parent_bbox=parent_bbox,
                weights=weights,
                min_part_coverage=min_part_cov,
                require_centre_inside=req_centre_inside,
            )

            if passes and score > 0.0:
                scored_candidates.append({
                    "parent_annotation_id": parent_ann_id,
                    "parent_category_id": parent["fashionpedia_category_id"],
                    "parent_category_name": parent["fashionpedia_category_name"],
                    "score": score,
                    "metrics": metrics,
                })

        # Sort candidates descending by score
        scored_candidates.sort(key=lambda x: x["score"], reverse=True)

        if len(scored_candidates) == 0:
            unassoc_entry = dict(part_record_base)
            unassoc_entry["reason"] = "NO_PARENT_MET_SPATIAL_THRESHOLDS"
            unassociated_parts.append(unassoc_entry)
        elif len(scored_candidates) == 1:
            winner = scored_candidates[0]
            assoc_entry = dict(part_record_base)
            assoc_entry.update({
                "parent_annotation_id": winner["parent_annotation_id"],
                "parent_category_id": winner["parent_category_id"],
                "association_score": winner["score"],
                "winning_margin": round(winner["score"], 4),
                "geometry_metrics": winner["metrics"],
                "association_method": "spatial_geometry_v1.0",
            })
            accepted_associations.append(assoc_entry)

            # Link to parent instance
            parent_attached_parts[winner["parent_annotation_id"]].append(assoc_entry)
        else:
            top = scored_candidates[0]
            second = scored_candidates[1]
            margin = top["score"] - second["score"]

            if margin >= min_score_margin:
                assoc_entry = dict(part_record_base)
                assoc_entry.update({
                    "parent_annotation_id": top["parent_annotation_id"],
                    "parent_category_id": top["parent_category_id"],
                    "association_score": top["score"],
                    "winning_margin": round(margin, 4),
                    "geometry_metrics": top["metrics"],
                    "association_method": "spatial_geometry_v1.0",
                })
                accepted_associations.append(assoc_entry)
                parent_attached_parts[top["parent_annotation_id"]].append(assoc_entry)
            else:
                ambig_entry = dict(part_record_base)
                ambig_entry.update({
                    "competing_candidates_count": len(scored_candidates),
                    "top_parent_annotation_id": top["parent_annotation_id"],
                    "top_score": top["score"],
                    "second_parent_annotation_id": second["parent_annotation_id"],
                    "second_score": second["score"],
                    "score_margin": round(margin, 4),
                    "required_margin": min_score_margin,
                    "reason": "SCORE_MARGIN_BELOW_THRESHOLD",
                })
                ambiguous_associations.append(ambig_entry)

    # Now evaluate updated heads for each base parent instance
    updated_records = []
    reason_code_counts = {}
    target_label_counts_per_head = {h: {} for h in classes_data["outputs"]}
    missing_head_counts = {h: 0 for h in classes_data["outputs"]}
    conflict_counts = {h: 0 for h in classes_data["outputs"]}

    decision_counts_before = {"training_ready": 0, "manual_review": 0, "rejected": 0}
    decision_counts_after = {"training_ready": 0, "manual_review": 0, "rejected": 0}

    for base_rec in base_records:
        decision_counts_before[base_rec["decision"]] += 1

        ann_id = base_rec["source_annotation_id"]
        cat_id = base_rec["fashionpedia_category_id"]
        img_id = base_rec["source_image_id"]
        bbox = base_rec["bbox"]
        parent_attr_ids = base_rec.get("fashionpedia_attribute_ids", [])

        attached_parts = parent_attached_parts.get(ann_id, [])

        # Gather all attribute IDs and their origin (parent vs attached parts)
        all_eval_attr_sources = []
        for aid in parent_attr_ids:
            all_eval_attr_sources.append({"source_type": "parent", "source_id": aid, "part_type": None})

        for p_info in attached_parts:
            ptype = p_info["part_type"]
            for aid in p_info["part_attribute_ids"]:
                all_eval_attr_sources.append({"source_type": f"part_{ptype}", "source_id": aid, "part_type": ptype, "part_ann_id": p_info["part_annotation_id"]})

        attr_ids_set = set(item["source_id"] for item in all_eval_attr_sources)

        reason_codes = []
        labels_by_head = {}

        # Validate bbox
        bbox_valid = validate_bbox(bbox) and (float(bbox[2]) >= 10.0 and float(bbox[3]) >= 10.0)
        if not bbox_valid:
            reason_codes.append("INVALID_BBOX")

        head_has_missing = False
        head_has_conflict = False

        for head_name in classes_data["outputs"]:
            head_items = head_mappings.get(head_name, [])
            matched_candidates = []

            if head_name == "garment_type":
                # Crop top precedence rule: Attribute ID 8 'crop (top)' on eligible top categories (0 or 1)
                if 8 in attr_ids_set and cat_id in (0, 1):
                    matched_candidates.append({"label": "crop-top", "status": "direct", "source": "attribute_8"})
                else:
                    if cat_id == 0:
                        matched_candidates.append({"label": "blouse", "status": "candidate_mapping", "source": "category_0"})
                    elif cat_id == 1:
                        matched_candidates.append({"label": "t-shirt", "status": "candidate_mapping", "source": "category_1"})

            elif head_name == "neckline_type":
                for item in head_items:
                    target_lbl = item["target_label"]
                    st = item["status"]
                    for ev in item.get("source_evidence", []):
                        stype = ev.get("source_type")
                        sid = ev.get("source_id")
                        if stype == "attribute" and sid in attr_ids_set:
                            matched_candidates.append({"label": target_lbl, "status": st, "source": f"attribute_{sid}"})
                            break

            elif head_name == "sleeve_length":
                for item in head_items:
                    target_lbl = item["target_label"]
                    st = item["status"]
                    for ev in item.get("source_evidence", []):
                        stype = ev.get("source_type")
                        sid = ev.get("source_id")
                        if stype == "attribute" and sid in attr_ids_set:
                            matched_candidates.append({"label": target_lbl, "status": st, "source": f"attribute_{sid}"})
                            break

            elif head_name == "sleeve_style":
                # Derived rule: sleeve_style = none if sleeveless (Attr 156) is present
                if 156 in attr_ids_set:
                    matched_candidates.append({"label": "none", "status": "candidate_mapping", "source": "derived_sleeveless"})

                for item in head_items:
                    target_lbl = item["target_label"]
                    if target_lbl == "none":
                        continue
                    st = item["status"]
                    for ev in item.get("source_evidence", []):
                        stype = ev.get("source_type")
                        sid = ev.get("source_id")
                        if stype == "attribute" and sid in attr_ids_set:
                            matched_candidates.append({"label": target_lbl, "status": st, "source": f"attribute_{sid}"})
                            break

            # Deduplicate matching candidates per head
            if len(matched_candidates) == 0:
                missing_head_counts[head_name] += 1
                head_has_missing = True
                reason_codes.append(f"MISSING_HEAD_{head_name.upper()}")
                labels_by_head[head_name] = None
            elif len(matched_candidates) > 1:
                unique_labels = {c["label"]: c for c in matched_candidates}
                if len(unique_labels) == 1:
                    lbl_info = list(unique_labels.values())[0]
                    labels_by_head[head_name] = {"label": lbl_info["label"], "status": lbl_info["status"]}
                    lbl = lbl_info["label"]
                    target_label_counts_per_head[head_name][lbl] = target_label_counts_per_head[head_name].get(lbl, 0) + 1
                else:
                    conflict_counts[head_name] += 1
                    head_has_conflict = True
                    reason_codes.append(f"CONFLICT_HEAD_{head_name.upper()}")
                    labels_by_head[head_name] = None
            else:
                lbl_info = matched_candidates[0]
                labels_by_head[head_name] = {"label": lbl_info["label"], "status": lbl_info["status"]}
                lbl = lbl_info["label"]
                target_label_counts_per_head[head_name][lbl] = target_label_counts_per_head[head_name].get(lbl, 0) + 1

        # Determine decision after spatial association
        if not bbox_valid:
            decision = "rejected"
        elif head_has_conflict or head_has_missing:
            decision = "manual_review"
        else:
            statuses = [labels_by_head[h]["status"] for h in classes_data["outputs"]]
            if all(st == "direct" for st in statuses):
                decision = "training_ready"
                reason_codes.append("TRAINING_READY_DIRECT_LABELS")
            else:
                decision = "manual_review"
                reason_codes.append("MANUAL_REVIEW_CANDIDATE_MAPPING")

        if len(attached_parts) > 0:
            reason_codes.append(f"ATTACHED_PARTS_COUNT_{len(attached_parts)}")

        decision_counts_after[decision] += 1

        for rcode in reason_codes:
            reason_code_counts[rcode] = reason_code_counts.get(rcode, 0) + 1

        rec = dict(base_rec)
        rec.update({
            "decision": decision,
            "reason_codes": reason_codes,
            "labels": labels_by_head,
            "attached_parts_count": len(attached_parts),
            "attached_parts": attached_parts,
        })
        updated_records.append(rec)

    # Sort records deterministically
    updated_records.sort(key=lambda x: x["source_annotation_id"])
    accepted_associations.sort(key=lambda x: (x["source_image_id"], x["part_annotation_id"]))
    ambiguous_associations.sort(key=lambda x: (x["source_image_id"], x["part_annotation_id"]))
    unassociated_parts.sort(key=lambda x: (x["source_image_id"], x["part_annotation_id"]))

    training_ready_spatial = [r for r in updated_records if r["decision"] == "training_ready"]
    manual_review_spatial = [r for r in updated_records if r["decision"] == "manual_review"]
    rejected_spatial = [r for r in updated_records if r["decision"] == "rejected"]

    # Compute split counts
    split_counts = {"train": 0, "val": 0, "test": 0}
    for r in updated_records:
        split_counts[r["split"]] += 1

    # Source image leakage check
    img_to_splits = defaultdict(set)
    for r in updated_records:
        img_to_splits[r["source_image_id"]].add(r["split"])
    cross_split_imgs = [img_id for img_id, splits in img_to_splits.items() if len(splits) > 1]
    leakage_passed = len(cross_split_imgs) == 0

    # Counts by part type for summary
    accepted_counts_by_type = {"sleeve": 0, "neckline": 0, "collar": 0, "total": len(accepted_associations)}
    for a in accepted_associations:
        ptype = a["part_type"]
        if ptype in accepted_counts_by_type:
            accepted_counts_by_type[ptype] += 1

    ambig_counts_by_type = {"sleeve": 0, "neckline": 0, "collar": 0, "total": len(ambiguous_associations)}
    for a in ambiguous_associations:
        ptype = a["part_type"]
        if ptype in ambig_counts_by_type:
            ambig_counts_by_type[ptype] += 1

    unassoc_counts_by_type = {"sleeve": 0, "neckline": 0, "collar": 0, "total": len(unassociated_parts)}
    for a in unassociated_parts:
        ptype = a["part_type"]
        if ptype in unassoc_counts_by_type:
            unassoc_counts_by_type[ptype] += 1

    # Write output JSONL files
    os.makedirs(output_dir, exist_ok=True)

    def write_jsonl(recs, filename):
        path = os.path.join(output_dir, filename)
        with open(path, "w", encoding="utf-8") as f:
            for r in recs:
                f.write(json.dumps(r) + "\n")

    write_jsonl(updated_records, "all_instances_spatial.jsonl")
    write_jsonl(training_ready_spatial, "training_ready_spatial.jsonl")
    write_jsonl(manual_review_spatial, "manual_review_spatial.jsonl")
    write_jsonl(rejected_spatial, "rejected_spatial.jsonl")
    write_jsonl(accepted_associations, "accepted_associations.jsonl")
    write_jsonl(ambiguous_associations, "ambiguous_associations.jsonl")
    write_jsonl(unassociated_parts, "unassociated_parts.jsonl")

    # Build spatial_summary.json
    summary = {
        "base_instance_count": len(base_records),
        "total_part_count": part_counts_by_type["total"],
        "part_counts_by_type": part_counts_by_type,
        "accepted_association_counts": accepted_counts_by_type,
        "ambiguous_association_counts": ambig_counts_by_type,
        "unassociated_part_counts": unassoc_counts_by_type,
        "decision_counts_before": decision_counts_before,
        "decision_counts_after": decision_counts_after,
        "reason_code_counts": reason_code_counts,
        "target_label_counts_per_head": target_label_counts_per_head,
        "missing_head_counts": missing_head_counts,
        "conflict_counts": conflict_counts,
        "split_counts": split_counts,
        "source_image_leakage_check": {
            "passed": leakage_passed,
            "cross_split_image_count": len(cross_split_imgs),
        },
        "association_threshold_config": {
            "minimum_part_coverage": min_part_cov,
            "minimum_score_margin": min_score_margin,
            "centre_inside_parent": req_centre_inside,
            "scoring_weights": weights,
        },
        "input_sha256": input_sha256,
        "algorithm_version": "1.0.0",
        "generation_timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }

    with open(os.path.join(output_dir, "spatial_summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print("==================================================")
    print("FASHIONPEDIA SPATIAL PART ASSOCIATION COMPLETED")
    print("==================================================")
    print(f"Output Directory: {os.path.abspath(output_dir)}")
    print(f"Base Instances Evaluated: {len(base_records)}")
    print(f"Total Part Annotations:  {part_counts_by_type['total']}")
    print(f"  - Accepted Associations:  {accepted_counts_by_type['total']} (Sleeve: {accepted_counts_by_type['sleeve']}, Neckline: {accepted_counts_by_type['neckline']}, Collar: {accepted_counts_by_type['collar']})")
    print(f"  - Ambiguous Associations: {ambig_counts_by_type['total']} (Sleeve: {ambig_counts_by_type['sleeve']}, Neckline: {ambig_counts_by_type['neckline']}, Collar: {ambig_counts_by_type['collar']})")
    print(f"  - Unassociated Parts:     {unassoc_counts_by_type['total']} (Sleeve: {unassoc_counts_by_type['sleeve']}, Neckline: {unassoc_counts_by_type['neckline']}, Collar: {unassoc_counts_by_type['collar']})")
    print("Decisions After Association:")
    print(f"  - Training Ready: {len(training_ready_spatial)}")
    print(f"  - Manual Review:  {len(manual_review_spatial)}")
    print(f"  - Rejected:       {len(rejected_spatial)}")
    print(f"Leakage Check Passed: {leakage_passed}")
    print("==================================================")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Associate Fashionpedia garment-part annotations to upper garments.")
    parser.add_argument("--annotations", required=True, help="Path to raw Fashionpedia annotation JSON.")
    parser.add_argument("--base-manifest", required=True, help="Path to base manifest all_instances.jsonl.")
    parser.add_argument("--classes", required=True, help="Path to classes.json.")
    parser.add_argument("--mapping", required=True, help="Path to fashionpedia_mapping.json.")
    parser.add_argument("--association-config", required=True, help="Path to part_association.json.")
    parser.add_argument("--output-dir", required=True, help="Output directory for spatial manifest.")

    args = parser.parse_args()
    run_spatial_association(
        annotations_path=args.annotations,
        base_manifest_path=args.base_manifest,
        classes_path=args.classes,
        mapping_path=args.mapping,
        assoc_config_path=args.association_config,
        output_dir=args.output_dir,
    )
