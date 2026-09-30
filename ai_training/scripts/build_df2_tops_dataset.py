#!/usr/bin/env python3
"""
build_df2_tops_dataset.py - clean SLEEVE-LENGTH dataset of tops from DeepFashion2 (local copy).

Only what DeepFashion2 really labels is used:
    category 1 short_sleeved_shirt -> sleeve_length = short-sleeve
    category 2 long_sleeved_shirt  -> sleeve_length = long-sleeve
    category 5 vest, 6 sling       -> sleeve_length = sleeveless   (and sleeve_style = none, derived from an
                                       explicit sleeveless category - never from a missing annotation)
DeepFashion2 has NO neckline, garment-type (blouse / t-shirt / crop top) or sleeve-design labels, so those
heads are masked (never invented) for every record built here.

Quality filters (all recorded): the top must be the ONLY top-category instance in its photo (layered outfits
are ambiguous), occlusion <= 2 ("slight"/"medium"), bounding box >= 100 px on both sides.
Splits: train <- official TRAIN; val and test <- official VALIDATION (a separate collection), split by a hash
of the image id. Near-duplicates (64-bit dHash, Hamming <= 4) between val/test and train are removed.

Outputs (ai_training/datasets/deepfashion2_tops/):
    images/{train,val,test}/<id>_<inst>_crop.jpg   bbox + 10 % margin (max side 320)
    images/{train,val,test}/<id>_<inst>_full.jpg   the whole photo (max side 480), EXIF-corrected
    annotations/{train,val,test}.jsonl, summary.json
"""

import argparse
import ast
import collections
import csv
import hashlib
import json
import os
import random
import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np
from PIL import Image, ImageOps

csv.field_size_limit(sys.maxsize)
SLEEVE = {1: "short-sleeve", 2: "long-sleeve", 5: "sleeveless", 6: "sleeveless"}
CAT_NAME = {1: "short_sleeved_shirt", 2: "long_sleeved_shirt", 5: "vest", 6: "sling"}
TOPS = {1, 2, 3, 4, 5, 6}                      # every top-like category (3, 4 = outwear) for the "only one top" rule


def read_instances(csv_path, root, sub):
    """{image_path: [(category_id, bbox, occlusion)]} for tops only."""
    per = collections.defaultdict(list)
    with open(csv_path, newline="", encoding="utf-8", errors="ignore") as f:
        for row in csv.DictReader(f):
            cid = int(row["category_id"])
            if cid not in TOPS:
                continue
            path = row["path"].replace("\\", "/").split("deepfashion2_original_images/")[-1]   # e.g. train/image/039350.jpg
            per[path].append((cid, ast.literal_eval(row["b_box"]), int(float(row.get("occlusion") or 0)),
                              int(row["img_width"]), int(row["img_height"])))
    return per


def candidates(per, sub):
    out = []
    for path, inst in per.items():
        if len(inst) != 1:                       # exactly one top in the photo
            continue
        cid, box, occ, w, h = inst[0]
        if cid not in SLEEVE or occ > 2:
            continue
        x1, y1, x2, y2 = box
        if (x2 - x1) < 100 or (y2 - y1) < 100:
            continue
        out.append({"path": path, "category_id": cid, "bbox": box, "occlusion": occ, "w": w, "h": h})
    return out


def _save(job):
    src, box, crop_out, full_out = job
    try:
        with Image.open(src) as im:
            im = ImageOps.exif_transpose(im).convert("RGB")
            w, h = im.size
            x1, y1, x2, y2 = box
            mx, my = 0.10 * (x2 - x1), 0.10 * (y2 - y1)
            c = im.crop((max(0, int(x1 - mx)), max(0, int(y1 - my)), min(w, int(x2 + mx)), min(h, int(y2 + my))))
            c.thumbnail((320, 320), Image.LANCZOS)
            c.save(crop_out, quality=90)
            f = im.copy()
            f.thumbnail((480, 480), Image.LANCZOS)
            f.save(full_out, quality=88)
        return True
    except Exception:                                # noqa: BLE001 - unreadable file is skipped and counted
        return False


def dhash(path):
    with Image.open(path) as im:
        px = np.asarray(im.convert("L").resize((9, 8), Image.LANCZOS), dtype=np.int16)
    v = 0
    for b in (px[:, 1:] > px[:, :-1]).flatten():
        v = (v << 1) | int(b)
    return v


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="Dataset/archive/DeepFashion2")
    ap.add_argument("--out", default="ai_training/datasets/deepfashion2_tops")
    ap.add_argument("--train-per-class", type=int, default=3000)
    ap.add_argument("--val-per-class", type=int, default=400)
    ap.add_argument("--test-per-class", type=int, default=500)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    rnd = random.Random(args.seed)
    imgs = os.path.join(args.root, "deepfashion2_original_images")

    per_train = read_instances(os.path.join(args.root, "img_info_dataframes", "train.csv"), imgs, "train")
    per_val = read_instances(os.path.join(args.root, "img_info_dataframes", "validation.csv"), imgs, "validation")
    cand_train, cand_val = candidates(per_train, "train"), candidates(per_val, "validation")
    print("candidates after quality filters:", len(cand_train), "train,", len(cand_val), "validation")

    def pick(cands, n_per_class, sub_dir):
        by = collections.defaultdict(list)
        for c in cands:
            by[SLEEVE[c["category_id"]]].append(c)
        chosen = []
        for lab, lst in sorted(by.items()):
            rnd.shuffle(lst)
            if lab == "sleeveless":                # balance vest and sling
                v = [c for c in lst if c["category_id"] == 5][: n_per_class // 2]
                s = [c for c in lst if c["category_id"] == 6][: n_per_class - len(v)]
                lst = v + s
            chosen += [dict(c, label=lab, sub=sub_dir) for c in lst[:n_per_class]]
        return chosen

    val_pool, test_pool = [], []
    for c in cand_val:                             # deterministic image-level split of the official validation set
        h = int(hashlib.sha1(c["path"].encode()).hexdigest(), 16) % 2
        (val_pool if h == 0 else test_pool).append(c)
    sel = {"train": pick(cand_train, args.train_per_class, "train"),
           "val": pick(val_pool, args.val_per_class, "validation"),
           "test": pick(test_pool, args.test_per_class, "validation")}

    jobs, meta = [], []
    for split, items in sel.items():
        d = os.path.join(args.out, "images", split)
        os.makedirs(d, exist_ok=True)
        for c in items:
            stem = os.path.splitext(os.path.basename(c["path"]))[0]
            src = os.path.join(imgs, c["path"])
            crop, full = os.path.join(d, f"{stem}_crop.jpg"), os.path.join(d, f"{stem}_full.jpg")
            jobs.append((src, c["bbox"], crop, full))
            meta.append((split, c, src, crop, full))
    with ProcessPoolExecutor(max_workers=max(1, (os.cpu_count() or 4) - 2)) as ex:
        ok = list(ex.map(_save, jobs, chunksize=32))
    print("saved:", sum(ok), "failed:", len(ok) - sum(ok))

    kept = collections.defaultdict(list)
    for (split, c, src, crop, full), good in zip(meta, ok):
        if good:
            kept[split].append((c, crop, full))

    # near-duplicate removal between train and val/test (dHash <= 4)
    train_h = np.array([dhash(cr) for _, cr, _ in kept["train"]], dtype=np.uint64)
    dropped = collections.Counter()
    for split in ("val", "test"):
        clean = []
        for c, cr, fu in kept[split]:
            d = np.bitwise_count(train_h ^ np.uint64(dhash(cr)))
            if int(d.min()) <= 4:
                dropped[split] += 1
                for p in (cr, fu):
                    os.remove(p)
            else:
                clean.append((c, cr, fu))
        kept[split] = clean
    # test vs val as well (same photos must not be in both)
    val_h = np.array([dhash(cr) for _, cr, _ in kept["val"]], dtype=np.uint64)
    clean = []
    for c, cr, fu in kept["test"]:
        if int(np.bitwise_count(val_h ^ np.uint64(dhash(cr))).min()) <= 4:
            dropped["test_vs_val"] += 1
            for p in (cr, fu):
                os.remove(p)
        else:
            clean.append((c, cr, fu))
    kept["test"] = clean

    os.makedirs(os.path.join(args.out, "annotations"), exist_ok=True)
    summary = {"source": "DeepFashion2 (local copy Dataset/archive)", "quality_filters": "single top in photo, occlusion<=2, bbox>=100px",
               "near_duplicates_removed": dict(dropped), "seed": args.seed, "counts": {}}
    for split, items in kept.items():
        recs = []
        for c, cr, fu in items:
            lab = c["label"]
            stem = os.path.splitext(os.path.basename(c["path"]))[0]
            recs.append({
                "record_uid": f"df2:{split}:{stem}", "source_dataset": "deepfashion2", "source_image_uid": f"df2:{stem}",
                "split": split, "crop_path": cr.replace("\\", "/"), "full_image_path": fu.replace("\\", "/"), "bbox": None,
                "df2_category": CAT_NAME[c["category_id"]], "occlusion": c["occlusion"],
                "labels": {"garment_type": None, "neckline_type": None, "sleeve_length": lab,
                           "sleeve_style": "none" if lab == "sleeveless" else None},
                "masks": {"garment_type": 0, "neckline_type": 0, "sleeve_length": 1, "sleeve_style": 1 if lab == "sleeveless" else 0},
                "provenance": {"garment_type": "missing/masked", "neckline_type": "missing/masked", "sleeve_length": "df2_human_category",
                               "sleeve_style": "derived_from_explicit_sleeveless" if lab == "sleeveless" else "missing/masked"},
            })
        with open(os.path.join(args.out, "annotations", f"{split}.jsonl"), "w", encoding="utf-8") as f:
            for r in recs:
                f.write(json.dumps(r) + "\n")
        summary["counts"][split] = dict(collections.Counter(r["labels"]["sleeve_length"] for r in recs))
    json.dump(summary, open(os.path.join(args.out, "annotations", "summary.json"), "w"), indent=2)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
