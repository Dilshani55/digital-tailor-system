#!/usr/bin/env python3
"""
build_label_queue_15class.py - human-review labelling queue for the FUTURE 15-class model.

For every (head, class) whose TRUSTED count misses the target (from counts.json written by
build_15class_manifests.py) it lists real annotated Fashionpedia garments that a person could confirm.
Nothing here is a label: every row carries only a HINT (why it is a candidate) and an empty decision.
A reviewer must look at the image and write one active class (or reject / uncertain).

Candidate evidence (hints, all from the original annotations):
  collared-neck    parent has an attached collar part (category 28)          [candidate_mapping]
  regular-sleeve   sleeve part with attribute 204 'set-in sleeve'             [candidate_mapping]
  blouse/t-shirt   garment-category mapping of the annotation                  [candidate_mapping]
  sleeveless       upper garment (shirt/blouse, top/t-shirt) with NO attached sleeve part
                   -> the absence of a sleeve annotation is only a reason to LOOK, never a label
  (sleeve_style 'none' is not queued: it is derived automatically from an accepted human 'sleeveless')
  square-neck, off-shoulder, puff-sleeve, bell-sleeve: every annotated example is already used, so
                   the pool is exhausted and new images/annotations from another source are required.

Leakage control: a candidate keeps the split of its source image (train/val/test as in the existing
manifests); candidates whose image is already in the trusted manifest for that class are skipped;
val/test acceptances are checked for near-duplicates of train images when the manifests are rebuilt.

  PYTHONPATH=. python ai_training/scripts/build_label_queue_15class.py
Outputs (ai_training/data/label_queue_15class/): queue.jsonl, queue.csv, queue_summary.json
Reviewed decisions go in decisions.jsonl:
  {"queue_id": "...", "decision": "<active class | reject | uncertain>", "reviewer_id": "...", "reviewed_at": "..."}
then:  build_15class_manifests.py --queue queue.jsonl --decisions decisions.jsonl --near-duplicate-check
"""

import argparse
import csv
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from ai_training.training import labels15 as L   # noqa: E402

UPPER_CATEGORIES = {0, 1}          # shirt/blouse, top/t-shirt/sweatshirt (the project's garments)
PARENT_FILES = [
    "ai_training/data/processed/fashionpedia_train_spatial_manifest/all_instances_spatial.jsonl",
    "ai_training/data/processed/fashionpedia_spatial_manifest/all_instances_spatial.jsonl",
]
IMAGE_DIRS = ["ai_training/data/raw/fashionpedia/images/train", "ai_training/data/raw/fashionpedia/images/test"]


def image_path(file_name):
    for d in IMAGE_DIRS:
        p = f"{d}/{file_name}"
        if os.path.exists(p):
            return p
    return f"{IMAGE_DIRS[0]}/{file_name}"


def candidate_hint(parent, head, cls):
    """Reason string if this annotation is a candidate for (head, cls), else None."""
    labels = parent.get("labels") or {}
    parts = parent.get("attached_parts") or []
    if head == "neckline_type" and cls == "collared-neck":
        ok = (labels.get("neckline_type") or {}).get("label") == "collared-neck" and any(p.get("part_type") == "collar" for p in parts)
        return "fashionpedia_collar_part_present" if ok else None
    if head == "sleeve_style" and cls == "regular-sleeve":
        ok = (labels.get("sleeve_style") or {}).get("label") == "regular-sleeve"
        return "fashionpedia_set_in_sleeve_attribute_204" if ok else None
    if head == "garment_type" and cls in ("blouse", "t-shirt"):
        ok = (labels.get("garment_type") or {}).get("label") == cls
        return "fashionpedia_garment_category_mapping" if ok else None
    if head == "sleeve_length" and cls == "sleeveless":
        ok = parent.get("fashionpedia_category_id") in UPPER_CATEGORIES and not any(p.get("part_type") == "sleeve" for p in parts)
        return "no_sleeve_part_annotated_(look_only)" if ok else None
    return None


def build(args):
    classes = L.load_classes(args.classes)
    targets = L.load_targets(args.targets)
    counts_doc = json.load(open(args.counts, encoding="utf-8"))
    report = counts_doc["readiness"]
    factor = targets["queue_oversampling_factor"]

    parents = []
    for p in PARENT_FILES:
        if os.path.exists(p):
            parents += L.load_jsonl(p)

    # annotations already carrying a trusted label for a head are not queued again
    used = {h: set() for h in L.HEADS}
    for split in L.SPLITS:
        for r in L.load_jsonl(os.path.join(args.manifest_dir, f"{split}.jsonl")):
            ann = r.get("source_annotation_id")
            for h in L.HEADS:
                if r["masks"].get(h) == 1 and r["trusted"].get(h):
                    used[h].add(ann)

    queue, summary = [], []
    for item in report["insufficient_classes"]:
        head, cls = item["head"], item["class"]
        if head == "sleeve_style" and cls == "none":
            summary.append({"head": head, "class": cls, "note": "derived automatically from accepted human 'sleeveless' labels",
                            "queued": 0, "missing": _missing(report, head, cls)})
            continue
        miss = _missing(report, head, cls)
        entry = {"head": head, "class": cls, "missing": miss, "queued": {}, "pool": {}}
        any_rule = False
        for split in L.SPLITS:
            need = miss[split]
            pool = [p for p in parents if p["split"] == split and p["source_annotation_id"] not in used[head]
                    and candidate_hint(p, head, cls)]
            entry["pool"][split] = len(pool)
            any_rule = any_rule or candidate_hint({"labels": {}, "attached_parts": []}, head, cls) is not None or bool(pool)
            n = min(L.quota(need, factor), len(pool)) if need else 0
            pool.sort(key=lambda p: L.stable_order(p["source_annotation_id"], args.seed))
            for k, p in enumerate(pool[:n]):
                queue.append({
                    "queue_id": f"q15-{head}-{cls}-{split}-{p['source_annotation_id']}",
                    "split": split, "target_head": head, "target_class": cls,
                    "source_image_id": p["source_image_id"], "source_annotation_id": p["source_annotation_id"],
                    "source_image_uid": f"fashionpedia:{p['split']}:{p['source_image_id']}",
                    "source_image_path": image_path(p["source_file_name"]), "bbox": p["bbox"],
                    "hint": candidate_hint(p, head, cls),
                    "hint_is_a_label": False,
                    "question": f"Is the {head.replace('_', ' ')} of this garment '{cls}'? Answer '{cls}', 'reject' or 'uncertain'.",
                    "decision": "", "reviewer_id": "", "reviewed_at": "",
                })
            entry["queued"][split] = n
            if need and len(pool) < need:
                entry.setdefault("exhausted", []).append(split)
        entry["note"] = ("pool smaller than the missing count in some split: more annotated images from another source are required"
                         if entry.get("exhausted") else "")
        summary.append(entry)
    return queue, summary


def _missing(report, head, cls):
    return {s: report["missing"][s][head].get(cls, 0) for s in L.SPLITS}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--classes", default="ai_training/config/classes_v2_15class.json")
    ap.add_argument("--targets", default="ai_training/config/label_targets_15class.json")
    ap.add_argument("--counts", default="ai_training/data/manifests_15class/counts.json")
    ap.add_argument("--manifest-dir", default="ai_training/data/manifests_15class")
    ap.add_argument("--output-dir", default="ai_training/data/label_queue_15class")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    queue, summary = build(args)
    os.makedirs(args.output_dir, exist_ok=True)
    with open(os.path.join(args.output_dir, "queue.jsonl"), "w", encoding="utf-8") as f:
        for q in queue:
            f.write(json.dumps(q) + "\n")
    with open(os.path.join(args.output_dir, "queue.csv"), "w", newline="", encoding="utf-8") as f:
        cols = ["queue_id", "split", "target_head", "target_class", "hint", "source_image_path", "bbox", "decision", "reviewer_id"]
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(queue)
    with open(os.path.join(args.output_dir, "queue_summary.json"), "w", encoding="utf-8") as f:
        json.dump({"rows": len(queue), "per_class": summary}, f, indent=2)

    print(f"queue rows: {len(queue)}  ->  {args.output_dir}")
    for e in summary:
        print(f"  {e['head']:14}{e['class']:16} missing={e['missing']} queued={e.get('queued')} pool={e.get('pool')} {e.get('note', '')}")


if __name__ == "__main__":
    main()
