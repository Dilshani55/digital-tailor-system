#!/usr/bin/env python3
"""
build_final_multitask_dataset.py

Constructs the final multi-task dataset for Milestone M9B (Corrected for Composite Record UID Joins):
- Evaluates the complete Fashionpedia spatial parent manifest universe (33,862 train2020 + 817 val2020 = 34,679 parent records).
- Uses composite record UIDs (record_uid = fashionpedia:{source_partition}:{source_annotation_id}) for ALL artifacts.
- Key all lookup dictionaries by record_uid (crops_by_uid, queue_by_uid, decisions_by_uid, pseudo_by_uid).
- Key image path map by (source_partition, source_file_name).
- Asserts strict real-data human review invariants (700 decisions, 600 accepted class labels, 50 reject, 50 uncertain).
- Asserts exact human-gold manifest counts: Val (41/37/43 = 121), Test (42/42/45 = 129), Train (87/212/51 = 350), Total = 600.
"""

import argparse
import hashlib
import json
import os
import sys
from collections import Counter, defaultdict


def parse_args():
    parser = argparse.ArgumentParser(description="Build final multi-task dataset for Digital Tailor M9B/M10")
    parser.add_argument("--labelling-dir", default="ai_training/data/labelling_official", help="Directory with M8/M9 labelling outputs")
    parser.add_argument("--human-review-dir", default="ai_training/data/human_review", help="Directory with human decisions and queue")
    parser.add_argument("--processed-dir", default="ai_training/data/processed", help="Directory with spatial manifests")
    parser.add_argument("--raw-images-dir", default="ai_training/data/raw/fashionpedia/images", help="Directory with extracted raw images")
    parser.add_argument("--policy", default="ai_training/config/final_dataset_policy.json", help="Path to final_dataset_policy.json")
    parser.add_argument("--weak-policy", default="ai_training/config/weak_label_policy.json", help="Path to weak_label_policy.json")
    parser.add_argument("--classes", default="ai_training/config/classes.json", help="Path to classes.json")
    parser.add_argument("--output-dir", default="ai_training/data/final_multitask", help="Output directory for final dataset")
    return parser.parse_args()


def load_classes_config(classes_path):
    with open(classes_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    heads = ["garment_type", "neckline_type", "sleeve_length", "sleeve_style"]
    class_to_idx = {}
    idx_to_class = {}
    for h in heads:
        class_to_idx[h] = data["outputs"][h]["class_to_idx"]
        idx_to_class[h] = data["outputs"][h]["idx_to_class"]

    return data, heads, class_to_idx, idx_to_class


def load_spatial_manifests(processed_dir):
    train_path = os.path.join(processed_dir, "fashionpedia_train_spatial_manifest", "all_instances_spatial.jsonl")
    val_path = os.path.join(processed_dir, "fashionpedia_spatial_manifest", "all_instances_spatial.jsonl")

    train_records = []
    if os.path.exists(train_path):
        with open(train_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    rec = json.loads(line.strip())
                    rec["source_partition"] = "train2020"
                    train_records.append(rec)

    val_records = []
    if os.path.exists(val_path):
        with open(val_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    rec = json.loads(line.strip())
                    rec["source_partition"] = "val2020"
                    val_records.append(rec)

    total_physical = len(train_records) + len(val_records)
    print(f"Loaded spatial manifests: train2020={len(train_records)}, val2020={len(val_records)}, total={total_physical}.")

    if len(train_records) != 33862 or len(val_records) != 817:
        print(f"WARNING: Expected 33862 train2020 and 817 val2020 records. Got {len(train_records)} and {len(val_records)}.")

    if total_physical != 34679:
        raise ValueError(f"Error: Expected exactly 34679 physical parent records, got {total_physical}")

    # Build composite dictionary to prevent annotation ID collision
    spatial_by_uid = {}
    for rec in train_records + val_records:
        part = rec["source_partition"]
        ann_id = rec["source_annotation_id"]
        record_uid = f"fashionpedia:{part}:{ann_id}"
        if record_uid in spatial_by_uid:
            raise ValueError(f"Error: Duplicate composite record_uid {record_uid} detected!")
        spatial_by_uid[record_uid] = rec

    if len(spatial_by_uid) != 34679:
        raise ValueError(f"Error: Composite spatial record count ({len(spatial_by_uid)}) does not match expected 34679.")

    print(f"Composite spatial dictionary verified: {len(spatial_by_uid)} unique record_uids.")
    return spatial_by_uid, len(train_records), len(val_records)


def resolve_partition_for_record(rec, spatial_by_uid):
    ann_id = rec.get("source_annotation_id")
    part = rec.get("source_partition")
    if part in ("train2020", "val2020"):
        return part

    # Check source_image_path or metadata if present
    img_p = rec.get("source_image_path") or ""
    if "train2020" in img_p or "/train/" in img_p or "\\train\\" in img_p:
        if f"fashionpedia:train2020:{ann_id}" in spatial_by_uid:
            return "train2020"
    if "val2020" in img_p or "/val/" in img_p or "\\val\\" in img_p:
        if f"fashionpedia:val2020:{ann_id}" in spatial_by_uid:
            return "val2020"

    in_train = f"fashionpedia:train2020:{ann_id}" in spatial_by_uid
    in_val = f"fashionpedia:val2020:{ann_id}" in spatial_by_uid

    if in_train and not in_val:
        return "train2020"
    if in_val and not in_train:
        return "val2020"

    if in_train and in_val:
        # Match using img_id and file_name
        img_id = rec.get("source_image_id")
        fn = rec.get("source_file_name")
        sp_t = spatial_by_uid[f"fashionpedia:train2020:{ann_id}"]
        sp_v = spatial_by_uid[f"fashionpedia:val2020:{ann_id}"]
        if sp_t.get("source_image_id") == img_id and (not fn or sp_t.get("source_file_name") == fn):
            return "train2020"
        if sp_v.get("source_image_id") == img_id and (not fn or sp_v.get("source_file_name") == fn):
            return "val2020"

    raise ValueError(f"Error: Could not uniquely resolve source_partition for record {ann_id}")


def load_review_queue_by_uid(human_review_dir, spatial_by_uid):
    queue_path = os.path.join(human_review_dir, "review_queue.jsonl")
    queue_by_uid = {}

    if os.path.exists(queue_path):
        with open(queue_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    rec = json.loads(line.strip())
                    part = resolve_partition_for_record(rec, spatial_by_uid)
                    ann_id = rec["source_annotation_id"]
                    uid = f"fashionpedia:{part}:{ann_id}"
                    if uid in queue_by_uid:
                        raise ValueError(f"Error: Duplicate review queue record_uid {uid}")
                    rec["source_partition"] = part
                    queue_by_uid[uid] = rec

    print(f"Loaded review queue: {len(queue_by_uid)} records keyed by record_uid.")
    if len(queue_by_uid) != 700:
        raise ValueError(f"Error: Expected 700 review queue records, got {len(queue_by_uid)}")
    return queue_by_uid


def load_and_verify_human_decisions_by_uid(human_review_dir, queue_by_uid, spatial_by_uid):
    decisions_path = os.path.join(human_review_dir, "human_decisions.jsonl")
    decisions_by_uid = {}

    if os.path.exists(decisions_path):
        with open(decisions_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    rec = json.loads(line.strip())
                    part = resolve_partition_for_record(rec, spatial_by_uid)
                    ann_id = rec["source_annotation_id"]
                    uid = f"fashionpedia:{part}:{ann_id}"
                    rec["source_partition"] = part
                    # Latest decision wins for the exact record_uid
                    decisions_by_uid[uid] = rec

    print(f"Loaded human decisions: {len(decisions_by_uid)} unique decisions keyed by record_uid.")
    if len(decisions_by_uid) != 700:
        raise ValueError(f"Error: Expected 700 human decision records, got {len(decisions_by_uid)}")

    # Strict Arithmetic Assertions
    label_counts = Counter()
    purpose_counts = Counter()
    split_counts = Counter()
    purpose_label_counts = defaultdict(Counter)

    for uid, dec in decisions_by_uid.items():
        q_item = queue_by_uid.get(uid, {})
        purpose = q_item.get("review_purpose", dec.get("review_purpose", "unknown"))
        split = q_item.get("split", dec.get("split", "train"))
        h_label = dec.get("human_label")

        purpose_counts[purpose] += 1
        split_counts[split] += 1
        label_counts[h_label] += 1
        purpose_label_counts[purpose][h_label] += 1

    total_decisions = len(decisions_by_uid)
    if total_decisions != 700 or sum(purpose_counts.values()) != 700 or sum(split_counts.values()) != 700 or sum(label_counts.values()) != 700:
        raise ValueError("Error: Human decision arithmetic sums must equal 700 exactly.")

    if label_counts.get("reject", 0) != 50:
        raise ValueError(f"Error: Total human reject count must be 50, got {label_counts.get('reject')}")
    if label_counts.get("uncertain", 0) != 50:
        raise ValueError(f"Error: Total human uncertain count must be 50, got {label_counts.get('uncertain')}")

    accepted_human_total = label_counts.get("blouse", 0) + label_counts.get("t-shirt", 0) + label_counts.get("crop-top", 0)
    if accepted_human_total != 600:
        raise ValueError(f"Error: Total human accepted class labels must be 600, got {accepted_human_total}")

    if label_counts.get("blouse") != 170 or label_counts.get("t-shirt") != 291 or label_counts.get("crop-top") != 139:
        raise ValueError(f"Error: Human class totals mismatch. Expected 170 blouse, 291 t-shirt, 139 crop-top. Got {label_counts}")

    print(f"Human decisions invariants verified: total=700, accepted=600, reject=50, uncertain=50.")

    human_stats = {
        "total_human_decisions": total_decisions,
        "accepted_human_class_labels": accepted_human_total,
        "reject_count": label_counts.get("reject", 0),
        "uncertain_count": label_counts.get("uncertain", 0),
        "label_totals": dict(sorted(label_counts.items())),
        "purpose_totals": dict(sorted(purpose_counts.items())),
        "split_totals": dict(sorted(split_counts.items())),
        "purpose_label_breakdown": {k: dict(v) for k, v in purpose_label_counts.items()},
    }
    return decisions_by_uid, human_stats


def load_pseudo_labels_by_uid(labelling_dir, spatial_by_uid):
    pseudo_by_uid = {}
    accepted_path = os.path.join(labelling_dir, "accepted_pseudo_labels.jsonl")
    all_labels_path = os.path.join(labelling_dir, "ai_labels_all.jsonl")

    target_path = accepted_path if os.path.exists(accepted_path) else all_labels_path
    if os.path.exists(target_path):
        with open(target_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    rec = json.loads(line.strip())
                    part = resolve_partition_for_record(rec, spatial_by_uid)
                    ann_id = rec["source_annotation_id"]
                    uid = f"fashionpedia:{part}:{ann_id}"
                    if uid in pseudo_by_uid:
                        raise ValueError(f"Error: Pseudo label record_uid {uid} applied to multiple records!")
                    rec["source_partition"] = part
                    pseudo_by_uid[uid] = rec
    print(f"Loaded pseudo labels: {len(pseudo_by_uid)} records keyed by record_uid.")
    return pseudo_by_uid


def load_crop_manifest_by_uid(labelling_dir, spatial_by_uid):
    crops_by_uid = {}
    crop_path = os.path.join(labelling_dir, "expanded_crop_manifest.jsonl")
    if not os.path.exists(crop_path):
        crop_path = os.path.join(labelling_dir, "crop_manifest.jsonl")

    if os.path.exists(crop_path):
        with open(crop_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    rec = json.loads(line.strip())
                    part = resolve_partition_for_record(rec, spatial_by_uid)
                    ann_id = rec["source_annotation_id"]
                    uid = f"fashionpedia:{part}:{ann_id}"
                    if uid in crops_by_uid:
                        raise ValueError(f"Error: Crop manifest record_uid {uid} attached to multiple records!")
                    rec["source_partition"] = part
                    crops_by_uid[uid] = rec
    print(f"Loaded crop manifest: {len(crops_by_uid)} records keyed by record_uid.")
    if len(crops_by_uid) != 3000:
        raise ValueError(f"Error: Expected 3000 crop records, got {len(crops_by_uid)}")
    return crops_by_uid


def load_partition_image_path_map(raw_images_dir):
    image_path_map = {}
    duplicate_keys = []
    if os.path.exists(raw_images_dir):
        for root, dirs, files in os.walk(raw_images_dir):
            for f in files:
                if f.endswith(".jpg") or f.endswith(".png") or f.endswith(".jpeg"):
                    rel_path = os.path.relpath(os.path.join(root, f), raw_images_dir)
                    p_dir = os.path.normpath(rel_path).split(os.sep)[0]
                    if "train" in p_dir:
                        key = ("train2020", f)
                    elif "test" in p_dir or "val" in p_dir:
                        key = ("val2020", f)
                    else:
                        continue

                    full_path = os.path.join(root, f)
                    if key in image_path_map:
                        duplicate_keys.append((key, full_path, image_path_map[key]))
                    else:
                        image_path_map[key] = full_path

    if duplicate_keys:
        raise ValueError(f"Error: Duplicate partition image path keys detected: {duplicate_keys[:5]}")

    print(f"Indexed partition-aware image paths: {len(image_path_map)} entries.")
    return image_path_map



def compute_file_sha256(filepath):
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()


def process_spatial_record(record_uid, spatial_rec, crops_by_uid, queue_by_uid, decisions_by_uid, pseudo_by_uid, image_path_map, policy, weak_policy, class_to_idx, weak_class_counts):
    part = spatial_rec["source_partition"]
    ann_id = spatial_rec["source_annotation_id"]
    img_id = spatial_rec["source_image_id"]
    fn = spatial_rec.get("source_file_name")

    source_image_uid = f"fashionpedia:{part}:{img_id}"

    crop_rec = crops_by_uid.get(record_uid, {})
    q_rec = queue_by_uid.get(record_uid, {})
    d_rec = decisions_by_uid.get(record_uid, {})
    p_rec = pseudo_by_uid.get(record_uid, {})

    split = crop_rec.get("split") or q_rec.get("split") or spatial_rec.get("split") or spatial_rec.get("source_split") or ("train" if part == "train2020" else "val")
    crop_path = crop_rec.get("crop_path")
    source_img_path = image_path_map.get((part, fn)) or crop_rec.get("source_image_path")

    bbox = spatial_rec.get("bbox") or crop_rec.get("bbox")
    exclusion_reasons = []

    if not source_img_path or not os.path.exists(source_img_path):
        exclusion_reasons.append("source_image_missing")

    # Head 1: garment_type
    g_label, g_idx, g_mask, g_prov, g_conf, g_weight, g_hv = None, None, 0, "missing/masked", None, 0.0, False

    if d_rec:
        h_lbl = d_rec.get("human_label")
        if h_lbl in ("blouse", "t-shirt", "crop-top"):
            g_label = h_lbl
            g_idx = class_to_idx["garment_type"][h_lbl]
            g_mask = 1
            g_prov = "human_verified"
            g_conf = 1.0
            g_weight = policy["sample_weights"].get("human_verified", 1.0)
            g_hv = True
        elif h_lbl == "reject":
            exclusion_reasons.append("human_reject")
        elif h_lbl == "uncertain":
            exclusion_reasons.append("human_uncertain")
    else:
        # Permit direct crop-top and pseudo-labels ONLY in train split
        if split == "train":
            attrs = spatial_rec.get("fashionpedia_attribute_ids", [])
            if 8 in attrs:
                g_label = "crop-top"
                g_idx = class_to_idx["garment_type"]["crop-top"]
                g_mask = 1
                g_prov = "fashionpedia_direct"
                g_conf = 1.0
                g_weight = policy["sample_weights"].get("fashionpedia_direct", 1.0)
            elif p_rec and p_rec.get("decision") == "accepted":
                top1 = p_rec.get("predicted_garment_type") or p_rec.get("top1_label")
                if top1 in ("blouse", "t-shirt", "crop-top"):
                    g_label = top1
                    g_idx = class_to_idx["garment_type"][top1]
                    g_mask = 1
                    g_prov = "accepted_pseudo_label"
                    g_conf = p_rec.get("top1_confidence")
                    g_weight = policy["sample_weights"].get("accepted_pseudo_label", 0.5)

    head_labels = {"garment_type": g_label}
    head_indices = {"garment_type": g_idx}
    head_masks = {"garment_type": g_mask}
    head_prov = {"garment_type": g_prov}
    head_conf = {"garment_type": g_conf}

    # Heads 2, 3, 4: neckline_type, sleeve_length, sleeve_style
    sp_labels = spatial_rec.get("labels", {})
    for h in ["neckline_type", "sleeve_length", "sleeve_style"]:
        h_info = sp_labels.get(h)
        if h_info and isinstance(h_info, dict) and h_info.get("status") == "direct":
            lbl = h_info.get("label")
            if lbl in class_to_idx[h]:
                head_labels[h] = lbl
                head_indices[h] = class_to_idx[h][lbl]
                head_masks[h] = 1
                head_prov[h] = "fashionpedia_direct"
                head_conf[h] = 1.0
            else:
                head_labels[h] = None
                head_indices[h] = None
                head_masks[h] = 0
                head_prov[h] = "missing/masked"
                head_conf[h] = None
        else:
            head_labels[h] = None
            head_indices[h] = None
            head_masks[h] = 0
            head_prov[h] = "missing/masked"
            head_conf[h] = None

    # M10 Automatic Training-Label Completion (Train Split Only)
    weak_label_details = []
    if split == "train" and weak_policy and weak_policy.get("enabled", True):
        attached_parts = spatial_rec.get("attached_parts", [])
        parent_attrs = set(spatial_rec.get("fashionpedia_attribute_ids", []))
        part_attrs = set(aid for p in attached_parts for aid in p.get("part_attribute_ids", []))
        all_attrs = parent_attrs | part_attrs

        collar_parts = [p for p in attached_parts if p.get("part_type") == "collar" or p.get("part_category_id") == 28]
        sleeve_parts = [p for p in attached_parts if p.get("part_type") == "sleeve" or p.get("part_category_id") == 31]

        caps = weak_policy.get("class_balancing_caps", {})

        # Rule 1: collared-neck (neckline_type)
        if head_masks["neckline_type"] == 0:
            if weak_class_counts.get("collared-neck", 0) < caps.get("collared-neck", 500):
                if collar_parts:
                    conflicting_necklines = all_attrs & {182, 183, 187, 189, 190, 191, 194, 197, 202}
                    if not conflicting_necklines:
                        head_labels["neckline_type"] = "collared-neck"
                        head_indices["neckline_type"] = class_to_idx["neckline_type"]["collared-neck"]
                        head_masks["neckline_type"] = 1
                        head_prov["neckline_type"] = "fashionpedia_rule_derived"
                        head_conf["neckline_type"] = weak_policy.get("confidence", 0.85)
                        weak_class_counts["collared-neck"] = weak_class_counts.get("collared-neck", 0) + 1
                        weak_label_details.append({
                            "head": "neckline_type",
                            "label": "collared-neck",
                            "rule": "collared-neck",
                            "evidence": "category_28_collar_part"
                        })

        # Rule 2: cap-length (sleeve_length)
        if head_masks["sleeve_length"] == 0:
            if weak_class_counts.get("cap-length", 0) < caps.get("cap-length", 500):
                if 207 in all_attrs:
                    conflicting_lengths = all_attrs & {156, 158, 159, 160}
                    if not conflicting_lengths:
                        head_labels["sleeve_length"] = "cap-length"
                        head_indices["sleeve_length"] = class_to_idx["sleeve_length"]["cap-length"]
                        head_masks["sleeve_length"] = 1
                        head_prov["sleeve_length"] = "fashionpedia_rule_derived"
                        head_conf["sleeve_length"] = weak_policy.get("confidence", 0.85)
                        weak_class_counts["cap-length"] = weak_class_counts.get("cap-length", 0) + 1
                        weak_label_details.append({
                            "head": "sleeve_length",
                            "label": "cap-length",
                            "rule": "cap-length",
                            "evidence": "attribute_207_cap_sleeve"
                        })

        # Rule 3: sleeve_style:none (sleeve_style)
        if head_masks["sleeve_style"] == 0:
            if weak_class_counts.get("none", 0) < caps.get("none", 500):
                is_sleeveless = (head_masks["sleeve_length"] == 1 and
                                 head_labels["sleeve_length"] == "sleeveless" and
                                 head_prov["sleeve_length"] in ("fashionpedia_direct", "human_verified"))
                if is_sleeveless:
                    head_labels["sleeve_style"] = "none"
                    head_indices["sleeve_style"] = class_to_idx["sleeve_style"]["none"]
                    head_masks["sleeve_style"] = 1
                    head_prov["sleeve_style"] = "fashionpedia_rule_derived"
                    head_conf["sleeve_style"] = weak_policy.get("confidence", 0.85)
                    weak_class_counts["none"] = weak_class_counts.get("none", 0) + 1
                    weak_label_details.append({
                        "head": "sleeve_style",
                        "label": "none",
                        "rule": "none",
                        "evidence": "derived_from_sleeveless_length"
                    })

        # Rule 4: regular-sleeve (sleeve_style)
        if head_masks["sleeve_style"] == 0:
            if weak_class_counts.get("regular-sleeve", 0) < caps.get("regular-sleeve", 500):
                if 204 in all_attrs:
                    special_styles = all_attrs & {206, 209, 210, 211, 213, 214, 216}
                    if not special_styles:
                        head_labels["sleeve_style"] = "regular-sleeve"
                        head_indices["sleeve_style"] = class_to_idx["sleeve_style"]["regular-sleeve"]
                        head_masks["sleeve_style"] = 1
                        head_prov["sleeve_style"] = "fashionpedia_rule_derived"
                        head_conf["sleeve_style"] = weak_policy.get("confidence", 0.85)
                        weak_class_counts["regular-sleeve"] = weak_class_counts.get("regular-sleeve", 0) + 1
                        weak_label_details.append({
                            "head": "sleeve_style",
                            "label": "regular-sleeve",
                            "rule": "regular-sleeve",
                            "evidence": "attribute_204_set_in_sleeve"
                        })

        # Rule 5: flutter-sleeve (sleeve_style)
        if head_masks["sleeve_style"] == 0:
            if weak_class_counts.get("flutter-sleeve", 0) < caps.get("flutter-sleeve", 500):
                if 211 in all_attrs:
                    other_styles = (all_attrs & {206, 209, 210, 213, 214, 216})
                    if not other_styles:
                        head_labels["sleeve_style"] = "flutter-sleeve"
                        head_indices["sleeve_style"] = class_to_idx["sleeve_style"]["flutter-sleeve"]
                        head_masks["sleeve_style"] = 1
                        head_prov["sleeve_style"] = "fashionpedia_rule_derived"
                        head_conf["sleeve_style"] = weak_policy.get("confidence", 0.85)
                        weak_class_counts["flutter-sleeve"] = weak_class_counts.get("flutter-sleeve", 0) + 1
                        weak_label_details.append({
                            "head": "sleeve_style",
                            "label": "flutter-sleeve",
                            "rule": "flutter-sleeve",
                            "evidence": "attribute_211_circular_flounce"
                        })

    total_masks = sum(head_masks.values())
    if total_masks == 0 and not exclusion_reasons:
        exclusion_reasons.append("no_permitted_labels_across_all_heads")

    sample_weight = 0.0
    if total_masks > 0:
        if "human_verified" in head_prov.values() or "fashionpedia_direct" in head_prov.values():
            sample_weight = 1.0
        elif "fashionpedia_rule_derived" in head_prov.values():
            sample_weight = policy["sample_weights"].get("fashionpedia_rule_derived", 0.8)
        elif "accepted_pseudo_label" in head_prov.values():
            sample_weight = policy["sample_weights"].get("accepted_pseudo_label", 0.5)

    attached_parts = spatial_rec.get("attached_parts", [])

    return {
        "record_uid": record_uid,
        "source_dataset": "fashionpedia",
        "source_partition": part,
        "source_annotation_id": ann_id,
        "source_image_id": img_id,
        "source_image_uid": source_image_uid,
        "source_image_path": source_img_path,
        "crop_path": crop_path,
        "bbox": bbox,
        "split": split,
        "labels": head_labels,
        "class_indices": head_indices,
        "masks": head_masks,
        "provenance": head_prov,
        "confidence": head_conf,
        "sample_weight": sample_weight,
        "human_verified": g_hv,
        "weak_label": any(p == "fashionpedia_rule_derived" for p in head_prov.values()),
        "weak_label_details": weak_label_details,
        "exclusion_reasons": exclusion_reasons,
        "attached_parts": attached_parts,
    }


def main():
    args = parse_args()

    with open(args.policy, "r", encoding="utf-8") as f:
        policy = json.load(f)

    weak_policy = None
    if args.weak_policy and os.path.exists(args.weak_policy):
        with open(args.weak_policy, "r", encoding="utf-8") as f:
            weak_policy = json.load(f)

    classes_data, heads, class_to_idx, idx_to_class = load_classes_config(args.classes)

    spatial_by_uid, train2020_count, val2020_count = load_spatial_manifests(args.processed_dir)

    queue_by_uid = load_review_queue_by_uid(args.human_review_dir, spatial_by_uid)
    decisions_by_uid, human_stats = load_and_verify_human_decisions_by_uid(args.human_review_dir, queue_by_uid, spatial_by_uid)
    pseudo_by_uid = load_pseudo_labels_by_uid(args.labelling_dir, spatial_by_uid)
    crops_by_uid = load_crop_manifest_by_uid(args.labelling_dir, spatial_by_uid)
    image_path_map = load_partition_image_path_map(args.raw_images_dir)

    # Process all 34,679 spatial parent records by record_uid in deterministic order
    weak_class_counts = Counter()
    all_processed = []
    for record_uid in sorted(spatial_by_uid.keys()):
        sp_rec = spatial_by_uid[record_uid]
        proc = process_spatial_record(
            record_uid, sp_rec, crops_by_uid, queue_by_uid, decisions_by_uid,
            pseudo_by_uid, image_path_map, policy, weak_policy, class_to_idx, weak_class_counts
        )
        all_processed.append(proc)

    if len(all_processed) != 34679:
        raise ValueError(f"Error: Processed records count ({len(all_processed)}) does not match expected 34679.")

    usable_records = [r for r in all_processed if not r["exclusion_reasons"]]
    excluded_records = [r for r in all_processed if r["exclusion_reasons"]]

    if len(usable_records) + len(excluded_records) != 34679:
        raise ValueError("Error: Usable + Excluded counts do not sum to total physical records (34679).")

    # Partition by split
    train_records = [r for r in usable_records if r["split"] == "train"]
    val_records = [r for r in usable_records if r["split"] == "val"]
    test_records = [r for r in usable_records if r["split"] == "test"]

    # Assert exact human gold garment counts in final manifests
    val_gold = Counter(r["labels"]["garment_type"] for r in val_records if r["provenance"]["garment_type"] == "human_verified")
    test_gold = Counter(r["labels"]["garment_type"] for r in test_records if r["provenance"]["garment_type"] == "human_verified")
    train_gold = Counter(r["labels"]["garment_type"] for r in train_records if r["provenance"]["garment_type"] == "human_verified")

    if dict(val_gold) != {"blouse": 41, "crop-top": 43, "t-shirt": 37}:
        raise ValueError(f"Error: Val human gold garment counts mismatch. Expected {{'blouse': 41, 'crop-top': 43, 't-shirt': 37}}, got {dict(val_gold)}")
    if dict(test_gold) != {"blouse": 42, "crop-top": 45, "t-shirt": 42}:
        raise ValueError(f"Error: Test human gold garment counts mismatch. Expected {{'blouse': 42, 'crop-top': 45, 't-shirt': 42}}, got {dict(test_gold)}")
    if dict(train_gold) != {"blouse": 87, "crop-top": 51, "t-shirt": 212}:
        raise ValueError(f"Error: Train human gold garment counts mismatch. Expected {{'blouse': 87, 'crop-top': 51, 't-shirt': 212}}, got {dict(train_gold)}")

    total_human_verified_usable = sum(val_gold.values()) + sum(test_gold.values()) + sum(train_gold.values())
    if total_human_verified_usable != 600:
        raise ValueError(f"Error: Total human_verified usable records in final manifests must equal 600, got {total_human_verified_usable}")

    print("Final human gold garment counts verified against review decisions: Val (121), Test (129), Train (350), Total = 600.")

    os.makedirs(args.output_dir, exist_ok=True)
    train_path = os.path.join(args.output_dir, "train.jsonl")
    val_path = os.path.join(args.output_dir, "val.jsonl")
    test_path = os.path.join(args.output_dir, "test.jsonl")
    excluded_path = os.path.join(args.output_dir, "excluded.jsonl")
    summary_path = os.path.join(args.output_dir, "coverage_summary.json")
    checksums_path = os.path.join(args.output_dir, "manifest_checksums.json")
    gold_topup_path = os.path.join(args.output_dir, "gold_topup_requirements.json")

    def write_jsonl(path, recs):
        with open(path, "w", encoding="utf-8") as f:
            for r in recs:
                f.write(json.dumps(r) + "\n")

    write_jsonl(train_path, train_records)
    write_jsonl(val_path, val_records)
    write_jsonl(test_path, test_records)
    write_jsonl(excluded_path, excluded_records)

    print(f"Wrote final JSONL files: train={len(train_records)}, val={len(val_records)}, test={len(test_records)}, excluded={len(excluded_records)}.")

    # 4-head 28-label Coverage Audit
    coverage_by_label = {}
    for h in heads:
        for c in classes_data["outputs"][h]["classes"]:
            key = f"{h}:{c}"
            coverage_by_label[key] = {
                "head": h,
                "class": c,
                "usable_count": 0,
                "masked_count": 0,
                "human_verified_count": 0,
                "direct_evidence_count": 0,
                "rule_derived_count": 0,
                "pseudo_label_count": 0,
                "by_split": {"train": 0, "val": 0, "test": 0},
            }

    for r in usable_records:
        split = r["split"]
        for h in heads:
            mask = r["masks"][h]
            lbl = r["labels"][h]
            prov = r["provenance"][h]
            if mask == 1 and lbl:
                key = f"{h}:{lbl}"
                coverage_by_label[key]["usable_count"] += 1
                coverage_by_label[key]["by_split"][split] += 1
                if prov == "human_verified":
                    coverage_by_label[key]["human_verified_count"] += 1
                elif prov == "fashionpedia_direct":
                    coverage_by_label[key]["direct_evidence_count"] += 1
                elif prov == "fashionpedia_rule_derived":
                    coverage_by_label[key]["rule_derived_count"] += 1
                elif prov == "accepted_pseudo_label":
                    coverage_by_label[key]["pseudo_label_count"] += 1
            else:
                for c in classes_data["outputs"][h]["classes"]:
                    coverage_by_label[f"{h}:{c}"]["masked_count"] += 1

    # Assert coverage arithmetic identities and gold counts
    for key, cov_info in coverage_by_label.items():
        if cov_info["usable_count"] != sum(cov_info["by_split"].values()):
            raise ValueError(f"Error: Usable count for {key} does not equal sum of split counts.")
        if cov_info["usable_count"] != cov_info["human_verified_count"] + cov_info["direct_evidence_count"] + cov_info["rule_derived_count"] + cov_info["pseudo_label_count"]:
            raise ValueError(f"Error: Usable count for {key} does not equal sum of provenance counts.")

    blouse_cov = coverage_by_label["garment_type:blouse"]
    if blouse_cov["by_split"]["val"] != 41 or blouse_cov["by_split"]["test"] != 42 or blouse_cov["by_split"]["train"] != 278:
        raise ValueError(f"Error: Blouse split counts mismatch! Expected val=41, test=42, train=278, got {blouse_cov['by_split']}")
    if blouse_cov["human_verified_count"] != 170 or blouse_cov["pseudo_label_count"] != 191:
        raise ValueError(f"Error: Blouse provenance counts mismatch! Got {blouse_cov}")

    tshirt_cov = coverage_by_label["garment_type:t-shirt"]
    if tshirt_cov["by_split"]["val"] != 37 or tshirt_cov["by_split"]["test"] != 42 or tshirt_cov["by_split"]["train"] != 212:
        raise ValueError(f"Error: T-shirt split counts mismatch! Expected val=37, test=42, train=212, got {tshirt_cov['by_split']}")
    if tshirt_cov["human_verified_count"] != 291 or tshirt_cov["pseudo_label_count"] != 0:
        raise ValueError(f"Error: T-shirt provenance counts mismatch! Got {tshirt_cov}")

    croptop_cov = coverage_by_label["garment_type:crop-top"]
    if croptop_cov["by_split"]["val"] != 43 or croptop_cov["by_split"]["test"] != 45 or croptop_cov["by_split"]["train"] != 820:
        raise ValueError(f"Error: Crop-top split counts mismatch! Expected val=43, test=45, train=820, got {croptop_cov['by_split']}")
    if croptop_cov["human_verified_count"] != 139 or croptop_cov["direct_evidence_count"] != 764 or croptop_cov["pseudo_label_count"] != 5:
        raise ValueError(f"Error: Crop-top provenance counts mismatch! Got {croptop_cov}")

    # Assert zero direct and zero pseudo garment labels in val and test
    val_garment_active = sum(1 for r in val_records if r["masks"]["garment_type"] == 1)
    test_garment_active = sum(1 for r in test_records if r["masks"]["garment_type"] == 1)
    if val_garment_active != 121:
        raise ValueError(f"Error: Val active garment_type masks must equal 121 (human gold only), got {val_garment_active}")
    if test_garment_active != 129:
        raise ValueError(f"Error: Test active garment_type masks must equal 129 (human gold only), got {test_garment_active}")

    zero_sample_classes = [k for k, v in coverage_by_label.items() if v["usable_count"] == 0]

    rare_classes = [k for k, v in coverage_by_label.items() if 0 < v["usable_count"] < 20]
    unsupported_classes = []

    # Supervised heads count per record (1, 2, 3, 4)
    supervised_heads_dist = Counter(sum(r["masks"].values()) for r in usable_records)

    # Gold insufficiency warning check
    min_gold_target = policy.get("minimum_gold_evaluation_count_warning_threshold", 50)
    val_deficits = {c: max(0, min_gold_target - val_gold.get(c, 0)) for c in ["blouse", "t-shirt", "crop-top"]}
    test_deficits = {c: max(0, min_gold_target - test_gold.get(c, 0)) for c in ["blouse", "t-shirt", "crop-top"]}
    total_additional_needed = sum(val_deficits.values()) + sum(test_deficits.values())

    gold_topup_required = total_additional_needed > 0
    if gold_topup_required:
        gold_topup_data = {
            "warning": "GOLD_SET_INSUFFICIENCY_WARNING",
            "minimum_required_per_class": min_gold_target,
            "val_deficits": val_deficits,
            "test_deficits": test_deficits,
            "total_additional_gold_samples_needed": total_additional_needed,
            "note": "Do not silently replace missing gold labels with pseudo-labels."
        }
        with open(gold_topup_path, "w", encoding="utf-8") as f:
            json.dump(gold_topup_data, f, indent=2)

    primary_exclusion_counts = Counter(r["exclusion_reasons"][0] for r in excluded_records)
    readiness_verdict = policy.get("readiness_verdict", "READY_FOR_PARTIAL_COVERAGE_BASELINE_ONLY")

    summary = {
        "readiness_verdict": readiness_verdict,
        "input_source_manifest_counts": {
            "train2020": train2020_count,
            "val2020": val2020_count,
            "total_physical_parent_records": len(all_processed),
        },
        "total_usable_records": len(usable_records),
        "total_excluded_records": len(excluded_records),
        "split_counts": {
            "train": len(train_records),
            "val": len(val_records),
            "test": len(test_records),
        },
        "primary_exclusion_counts": dict(primary_exclusion_counts),
        "supervised_heads_distribution": {str(k): v for k, v in sorted(supervised_heads_dist.items())},
        "human_decision_statistics": human_stats,
        "val_gold_garment_counts": dict(val_gold),
        "test_gold_garment_counts": dict(test_gold),
        "train_gold_garment_counts": dict(train_gold),
        "gold_topup_required": gold_topup_required,
        "zero_sample_classes": zero_sample_classes,
        "rare_classes": rare_classes,
        "unsupported_classes": unsupported_classes,
        "coverage_by_label": coverage_by_label,
    }

    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"Wrote coverage summary to {summary_path}.")

    # Manifest Checksums
    checksums = {
        "train.jsonl": compute_file_sha256(train_path),
        "val.jsonl": compute_file_sha256(val_path),
        "test.jsonl": compute_file_sha256(test_path),
        "excluded.jsonl": compute_file_sha256(excluded_path),
        "coverage_summary.json": compute_file_sha256(summary_path),
    }
    if os.path.exists(gold_topup_path):
        checksums["gold_topup_requirements.json"] = compute_file_sha256(gold_topup_path)

    with open(checksums_path, "w", encoding="utf-8") as f:
        json.dump(checksums, f, indent=2)
    print(f"Wrote manifest checksums to {checksums_path}.")


if __name__ == "__main__":
    main()
