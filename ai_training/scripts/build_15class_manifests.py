#!/usr/bin/env python3
"""
build_15class_manifests.py - manifests and an exact readiness report for the FUTURE 3/5/3/4 model.

Nothing here touches production: it reads the existing trustworthy manifests, re-expresses them for the
15 active classes (removed classes masked per head, never remapped), optionally adds HUMAN-VERIFIED
labels from a reviewed queue, prints the retained sample count of every one of the 15 classes and states
whether the label targets in config/label_targets_15class.json are met.

  PYTHONPATH=. python ai_training/scripts/build_15class_manifests.py
  PYTHONPATH=. python ai_training/scripts/build_15class_manifests.py --queue Q.jsonl --decisions D.jsonl --near-duplicate-check

Leakage control
  * splits are the existing source-image-level splits (an image never appears in two splits);
  * val/test records whose image has a near-duplicate (dHash <= 4) in train are excluded (audit lists);
  * new human-labelled val/test images are hashed and checked against the train images (--near-duplicate-check).

Exit code: 0 = report written; 2 = NOT_READY and --require-ready was given.
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from ai_training.training import labels15 as L   # noqa: E402


def _norm(p):
    return (p or "").replace("\\", "/")


def build(args):
    classes = L.load_classes(args.classes)
    targets = L.load_targets(args.targets)

    audit = {}
    if args.audit and os.path.exists(args.audit):
        audit = json.load(open(args.audit, encoding="utf-8")).get("leakage", {})
    near = {
        "val": {_norm(p) for p in audit.get("val_images_with_near_duplicate_in_train_paths", [])},
        "test": {_norm(p) for p in audit.get("test_images_with_near_duplicate_in_train_paths", [])},
    }

    by_split, excluded_near = {}, {"val": 0, "test": 0}
    for split in L.SPLITS:
        recs = L.load_jsonl(os.path.join(args.data_dir, f"{split}.jsonl"))
        kept = []
        for r in recs:
            if split in near and _norm(r.get("source_image_path")) in near[split]:
                excluded_near[split] += 1
                continue
            kept.append(L.convert_record(r, classes))
        by_split[split] = kept

    human = {"decisions": 0, "accepted": 0, "problems": [], "added": 0, "dropped_near_duplicate": 0}
    if args.queue and args.decisions:
        queue = L.load_jsonl(args.queue)
        decisions = L.load_jsonl(args.decisions)
        accepted, problems = L.validate_decisions(queue, decisions, classes)
        human.update(decisions=len(decisions), accepted=len(accepted), problems=problems)
        new = [L.record_from_decision(a, classes) for a in accepted]
        if args.near_duplicate_check:
            new, dropped = _drop_near_duplicates(new, by_split["train"], args)
            human["dropped_near_duplicate"] = dropped
        # 'none' is derived only from an accepted, explicit human 'sleeveless' on the same annotation
        derived = []
        for r in new:
            if r["labels"]["sleeve_length"] == "sleeveless":
                d = dict(r)
                d["record_uid"] = r["record_uid"].rsplit(":", 1)[0] + ":sleeve_style"
                d["labels"], d["masks"], d["provenance"] = dict(r["labels"]), dict(r["masks"]), dict(r["provenance"])
                d["labels"]["sleeve_style"], d["masks"]["sleeve_style"] = "none", 1
                d["provenance"]["sleeve_style"] = "human_verified"
                d["labels"]["sleeve_length"], d["masks"]["sleeve_length"] = None, 0
                d["provenance"]["sleeve_length"] = L.MASKED_PROVENANCE
                d["trusted"] = dict(r["trusted"], sleeve_style=True, sleeve_length=False)
                d["class_indices"] = dict(r["class_indices"], sleeve_style=classes["sleeve_style"].index("none"), sleeve_length=None)
                d["derived_from"] = r["record_uid"]
                derived.append(d)
        for r in new + derived:
            by_split[r["split"]].append(r)
        human["added"] = len(new) + len(derived)

    counts = L.count_classes(by_split, classes)
    report = L.readiness(counts, targets, classes)
    return classes, targets, by_split, counts, report, excluded_near, human


def _drop_near_duplicates(new, train_records, args):
    """Hash new val/test images and drop those with a near-twin among the train images."""
    from ai_training.scripts import audit_dataset as A
    cache = {}
    if os.path.exists(args.hash_cache):
        cache = json.load(open(args.hash_cache))
    for r in train_records:
        p = r["source_image_path"]
        if p not in cache and os.path.exists(p.replace("\\", "/")):
            cache[p] = A.dhash(p.replace("\\", "/"))
    os.makedirs(os.path.dirname(args.hash_cache), exist_ok=True)
    json.dump(cache, open(args.hash_cache, "w"))
    train_hashes = list(cache.values())
    kept, dropped = [], 0
    for r in new:
        if r["split"] == "train":
            kept.append(r)
            continue
        p = r["source_image_path"].replace("\\", "/")
        if os.path.exists(p) and A.near_pairs(train_hashes, [A.dhash(p)], 4):
            dropped += 1
        else:
            kept.append(r)
    return kept, dropped


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="ai_training/data/final_multitask")
    ap.add_argument("--classes", default="ai_training/config/classes_v2_15class.json")
    ap.add_argument("--targets", default="ai_training/config/label_targets_15class.json")
    ap.add_argument("--audit", default="ai_training/data/audits/dataset_audit.json")
    ap.add_argument("--queue", default=None)
    ap.add_argument("--decisions", default=None)
    ap.add_argument("--near-duplicate-check", action="store_true")
    ap.add_argument("--hash-cache", default="ai_training/data/audits/train_dhash_cache.json")
    ap.add_argument("--output-dir", default="ai_training/data/manifests_15class")
    ap.add_argument("--require-ready", action="store_true")
    args = ap.parse_args()

    classes, targets, by_split, counts, report, excl, human = build(args)
    os.makedirs(args.output_dir, exist_ok=True)
    sums = {}
    for split, recs in by_split.items():
        path = os.path.join(args.output_dir, f"{split}.jsonl")
        with open(path, "w", encoding="utf-8") as f:
            for r in recs:
                f.write(json.dumps(r) + "\n")
        sums[f"{split}.jsonl"] = L.sha256_file(path)
    out = {"taxonomy": "15class-v2", "classes": classes, "records": {s: len(v) for s, v in by_split.items()},
           "excluded_near_duplicates": excl, "human_labels": human, "counts": counts, "readiness": report,
           "manifest_sha256": sums, "classes_config_sha256": L.sha256_file(args.classes)}
    with open(os.path.join(args.output_dir, "counts.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)

    print(L.format_table(counts, report, classes))
    print(f"\nrecords: {out['records']}  (near-duplicates excluded from evaluation splits: {excl})")
    if human["decisions"]:
        print(f"human decisions: {human['decisions']} read, {human['accepted']} accepted, {human['added']} records added, "
              f"{len(human['problems'])} problems")
    print(f"\nVERDICT: {report['verdict']}")
    if report["verdict"] != "READY":
        print("Insufficient trustworthy evidence for: " + ", ".join(f"{c['head']}={c['class']}" for c in report["insufficient_classes"]))
        print("Do NOT train the 15-class model. See docs/FUTURE_15_CLASS_MODEL.md.")
    print(f"\nWritten to {args.output_dir}")
    return 2 if (args.require_ready and report["verdict"] != "READY") else 0


if __name__ == "__main__":
    sys.exit(main())
