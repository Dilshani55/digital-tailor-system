#!/usr/bin/env python3
"""
audit_dataset.py - reproducible audit of the garment multi-task dataset (read-only).

Reports, from the manifests and image files that are actually on disk:
  * record counts per split, unique source images per split
  * class distribution per head and split, label provenance, human-verified / weak / pseudo labels
  * missing and corrupt image files (every unique source image is opened)
  * exact duplicates (SHA-256) and near-duplicates (64-bit dHash, Hamming <= --near) ACROSS splits,
    plus the locked real-product evaluation set against the training images
  * source-image-ID leakage across splits
  * taxonomy consistency: classes.json vs backend feature schema vs model heads vs frontend schema
  * SHA-256 of every manifest (dataset fingerprint)

Usage (from the repository root):
    PYTHONPATH=. python ai_training/scripts/audit_dataset.py --output ai_training/data/audits/dataset_audit.json
"""

import argparse
import collections
import hashlib
import json
import os
import re
import sys

import numpy as np
from PIL import Image

HEADS = ["garment_type", "neckline_type", "sleeve_length", "sleeve_style"]


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_jsonl(path):
    with open(path, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def dhash(path):
    with Image.open(path) as im:
        im = im.convert("L").resize((9, 8), Image.LANCZOS)
        px = np.asarray(im, dtype=np.int16)
    bits = (px[:, 1:] > px[:, :-1]).flatten()
    v = 0
    for b in bits:
        v = (v << 1) | int(b)
    return v


def check_image(path):
    """(ok, error) - fully decodes the file."""
    try:
        with Image.open(path) as im:
            im.verify()
        with Image.open(path) as im:
            im.load()
        return True, None
    except Exception as exc:                       # noqa: BLE001 - report any decode failure
        return False, f"{type(exc).__name__}: {exc}"


def near_pairs(hashes_a, hashes_b, max_dist):
    """All (i, j, dist) with Hamming distance <= max_dist between two uint64 arrays."""
    a = np.array(hashes_a, dtype=np.uint64)
    out = []
    for j, hb in enumerate(hashes_b):
        d = np.bitwise_count(a ^ np.uint64(hb))
        for i in np.flatnonzero(d <= max_dist):
            out.append((int(i), j, int(d[i])))
    return out


def taxonomy_report(classes_path):
    with open(classes_path, "r", encoding="utf-8") as f:
        classes = json.load(f)
    truth = {h: classes["outputs"][h]["classes"] for h in HEADS}
    report = {"classes_json": {h: len(v) for h, v in truth.items()}, "checks": {}}

    sys.path.insert(0, os.path.abspath("backend"))
    try:
        from app.logic.feature_schema import MODEL_TAXONOMY, UI_TAXONOMY
        # the deployed classifier's taxonomy is unchanged ...
        report["checks"]["backend_model_taxonomy"] = all(list(MODEL_TAXONOMY[h]) == truth[h] for h in HEADS)
        # ... and the user-selectable classes are an ordered subset of it (never a remapping)
        report["checks"]["ui_taxonomy_is_ordered_subset_of_model"] = all(
            [truth[h].index(v) for v in UI_TAXONOMY[h]] == sorted(truth[h].index(v) for v in UI_TAXONOMY[h]) for h in HEADS)
    except Exception as exc:                        # noqa: BLE001
        report["checks"]["backend_feature_schema"] = f"unavailable: {exc}"
    try:
        from app.ai.multitask_classifier import DEFAULT_HEAD_DIMS
        report["checks"]["model_head_dims"] = all(DEFAULT_HEAD_DIMS[h] == len(truth[h]) for h in HEADS)
    except Exception as exc:                        # noqa: BLE001
        report["checks"]["model_head_dims"] = f"unavailable: {exc}"
    # The frontend no longer has its own list: it imports config/garment_scope.json, which the backend loads too.
    js = os.path.join("frontend", "src", "utils", "designSchema.js")
    canon = os.path.join("config", "garment_scope.json")
    if os.path.exists(js) and os.path.exists(canon):
        text = open(js, encoding="utf-8").read()
        with open(canon, encoding="utf-8") as f:
            canon_tax = json.load(f)["taxonomy"]
        ok = "config/garment_scope.json" in text and not re.search(r"value: '[a-z-]+'", text)
        try:
            from app.logic.feature_schema import UI_TAXONOMY as _UI
            ok = ok and all([o["value"] for o in canon_tax[h]] == list(_UI[h]) for h in HEADS)
        except Exception:                                # noqa: BLE001
            ok = False
        report["checks"]["frontend_designSchema_matches_active_ui_taxonomy"] = ok
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="ai_training/data/final_multitask")
    ap.add_argument("--train", default="train.jsonl")
    ap.add_argument("--val", default="val.jsonl")
    ap.add_argument("--test", default="test.jsonl")
    ap.add_argument("--eval-manifest", default="ai_training/data/eval_real_product_set/eval_manifest.jsonl")
    ap.add_argument("--classes", default="ai_training/config/classes.json")
    ap.add_argument("--near", type=int, default=4, help="max Hamming distance counted as a near-duplicate")
    ap.add_argument("--output", default="ai_training/data/audits/dataset_audit.json")
    ap.add_argument("--skip-images", action="store_true", help="skip decoding / hashing (fast structural audit)")
    args = ap.parse_args()

    splits = {}
    for name, fn in (("train", args.train), ("val", args.val), ("test", args.test)):
        splits[name] = read_jsonl(os.path.join(args.data_dir, fn))

    audit = {"manifests": {}, "splits": {}, "leakage": {}, "images": {}, "taxonomy": taxonomy_report(args.classes)}
    for fn in (args.train, args.val, args.test, "excluded.jsonl"):
        p = os.path.join(args.data_dir, fn)
        if os.path.exists(p):
            audit["manifests"][fn] = sha256_file(p)

    for name, recs in splits.items():
        info = {"records": len(recs), "unique_source_images": len({r["source_image_uid"] for r in recs}),
                "human_verified_records": sum(1 for r in recs if r.get("human_verified")),
                "weak_label_records": sum(1 for r in recs if r.get("weak_label")), "heads": {}}
        for h in HEADS:
            counts = collections.Counter(r["labels"][h] for r in recs if r["masks"].get(h) == 1)
            prov = collections.Counter(r["provenance"][h] for r in recs if r["masks"].get(h) == 1)
            info["heads"][h] = {"supervised": sum(counts.values()), "classes": dict(sorted(counts.items())),
                                "provenance": dict(prov),
                                "classes_with_zero_samples": [c for c in json.load(open(args.classes))["outputs"][h]["classes"]
                                                              if counts.get(c, 0) == 0]}
        audit["splits"][name] = info

    # source image / annotation-id leakage across splits
    uid = {n: {r["source_image_uid"] for r in recs} for n, recs in splits.items()}
    rid = {n: {r["record_uid"] for r in recs} for n, recs in splits.items()}
    for a, b in (("train", "val"), ("train", "test"), ("val", "test")):
        audit["leakage"][f"source_image_uid_overlap_{a}_{b}"] = len(uid[a] & uid[b])
        audit["leakage"][f"record_uid_overlap_{a}_{b}"] = len(rid[a] & rid[b])

    if not args.skip_images:
        paths = {}
        for n, recs in splits.items():
            for r in recs:
                paths.setdefault(r["source_image_path"], set()).add(n)
        missing, corrupt = [], []
        hashes, sha = {}, {}
        for p, ns in paths.items():
            if not os.path.exists(p):
                missing.append(p)
                continue
            ok, err = check_image(p)
            if not ok:
                corrupt.append({"path": p, "error": err})
                continue
            hashes[p] = dhash(p)
            sha[p] = sha256_file(p)
        audit["images"] = {"unique_image_files": len(paths), "missing": len(missing), "corrupt": len(corrupt),
                           "missing_examples": missing[:5], "corrupt_examples": corrupt[:5]}

        # exact duplicates and near-duplicates across splits (per unique file)
        by_split = {n: [p for p in hashes if n in paths[p]] for n in splits}
        exact = collections.defaultdict(set)
        for p, s in sha.items():
            exact[s].add(p)
        audit["leakage"]["exact_duplicate_content_groups_total"] = sum(1 for v in exact.values() if len(v) > 1)
        cross = 0
        for v in exact.values():
            if len(v) > 1 and len({n for p in v for n in paths[p]}) > 1:
                cross += 1
        audit["leakage"]["exact_duplicate_groups_across_splits"] = cross
        for a, b in (("val", "train"), ("test", "train"), ("test", "val")):
            pa = [hashes[p] for p in by_split[a]]
            pb = [hashes[p] for p in by_split[b]]
            pairs = near_pairs(pb, pa, args.near)
            audit["leakage"][f"near_duplicate_pairs_{a}_vs_{b}_dhash<={args.near}"] = len(pairs)
            audit["leakage"][f"images_in_{a}_with_near_duplicate_in_{b}"] = len({j for _, j, _ in pairs})
            if b == "train":
                # exact file lists, so evaluations can exclude near-duplicated images ("clean" splits)
                audit["leakage"][f"{a}_images_with_near_duplicate_in_train_paths"] = sorted({by_split[a][j] for _, j, _ in pairs})

        # the locked real-product evaluation set against the training images
        if os.path.exists(args.eval_manifest):
            ev = read_jsonl(args.eval_manifest)
            ev_hash = []
            for e in ev:
                p = e["image_path"].replace("\\", "/")
                if os.path.exists(p):
                    ev_hash.append(dhash(p))
            train_hashes = [hashes[p] for p in by_split["train"]]
            pairs = near_pairs(train_hashes, ev_hash, args.near)
            min_d = []
            a = np.array(train_hashes, dtype=np.uint64)
            for h in ev_hash:
                min_d.append(int(np.bitwise_count(a ^ np.uint64(h)).min()))
            train_uids = uid["train"]
            audit["leakage"]["eval_set_images"] = len(ev)
            audit["leakage"]["eval_set_images_hashed"] = len(ev_hash)
            audit["leakage"]["eval_set_record_uids_in_train"] = sum(1 for e in ev if e["original_record_uid"] in rid["train"])
            audit["leakage"]["eval_set_near_duplicate_pairs_vs_train"] = len(pairs)
            audit["leakage"]["eval_set_min_dhash_distance_to_train"] = min(min_d) if min_d else None
            audit["leakage"]["eval_set_images_with_near_duplicate_in_train"] = len({j for _, j, _ in pairs})
            audit["leakage"]["eval_set_record_uids_in_test_split"] = sum(1 for e in ev if e["original_record_uid"] in rid["test"])

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(audit, f, indent=2)
    print(json.dumps({k: audit[k] for k in ("leakage", "images", "taxonomy")}, indent=2))
    for n, info in audit["splits"].items():
        print(f"{n}: {info['records']} records, {info['unique_source_images']} images, "
              f"human_verified={info['human_verified_records']}, weak={info['weak_label_records']}")
    print(f"\nAudit written to {args.output}")


if __name__ == "__main__":
    main()
