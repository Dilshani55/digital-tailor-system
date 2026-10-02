"""Build the part datasets from the Fashionpedia part annotations (neckline, collar and sleeve boxes).

    backend\\venv\\Scripts\\python backend\\training\\prepare_part_datasets.py                  # step 1
    backend\\venv\\Scripts\\python backend\\training\\prepare_part_datasets.py --add-detected   # step 2, after the part detector is trained

Why: a neckline or a sleeve is a small part of a garment photo. Fashionpedia marks every neckline, collar and sleeve
with its own box and its own style label, on every kind of garment. The garment-level datasets used only the
blouse / T-shirt records and so only a small share of these labels.

Output (local, git-ignored): backend/training/datasets/parts/
    detector/images|labels/train|val/   garment crops with the boxes of their parts: 0 neck, 1 sleeve  (YOLO format)
    detector/data.yaml
    neck/train|val/<class>/*.jpg        the neck area alone:   round-neck, v-neck, square-neck, collared-neck
    sleeve/train|val/<class>/*.jpg      one sleeve alone:      regular-sleeve, puff-sleeve, bell-sleeve
    summary.json                        counts, label rules, what was left out

Step 2 adds, to neck/ and sleeve/, the parts that the trained part detector itself finds in the garment-level
training and validation records of every dataset (files m_*.jpg). The classifiers then also learn from the kind of
crop they get in the app (the detector's box, not a hand-drawn one) and from shop photos, which Fashionpedia lacks.

Splits (by photo, never by crop):
    test        every Fashionpedia photo of the frozen test sets: NOT used here at all
    val         the Fashionpedia photos of the frozen validation set + 8 % of the remaining photos (by file-name hash)
    train       the other photos, minus any photo that is near-identical (dHash, Hamming <= 4) to a validation or
                test photo of any dataset
"""
import hashlib
import json
import os
import random
import re
import shutil
import sys
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor

import numpy as np
from PIL import Image

sys.path.insert(0, "backend")
sys.path.insert(0, "backend/training")
import common as C                                              # noqa: E402
from app.ai.preprocess import crop_box, load_rgb, square_pad     # noqa: E402

FP = f"{C.ROOT}/data/raw/fashionpedia"
ANNOTATIONS = f"{FP}/instances_attributes_train2020.json"
IMAGES = f"{FP}/images/train"
OUT = f"{C.ROOT}/datasets/parts"
SEED = 42
SIZE = 256                      # classifier crops (trained at 224)
DETECTOR_SIDE = 512             # longest side of a detector image (trained at 416)
NEAR = 4                        # dHash Hamming distance that counts as "the same photo"
VAL_SHARE = 8                   # % of the free photos that go to validation

# Fashionpedia ids
NECKLINE, COLLAR, SLEEVE = 33, 28, 31
GARMENTS = {0: "shirt, blouse", 1: "top, t-shirt, sweatshirt", 2: "sweater", 3: "cardigan", 4: "jacket", 5: "vest", 10: "dress"}
NECK_ATTR = {182: "round-neck", 181: "round-neck", 183: "v-neck", 191: "square-neck"}   # round (neck), crew (neck), v-neck, square (neckline)
FOLD_OVER_COLLAR = {163, 164, 168}       # shirt, polo, peter pan: a band folded around the neck
SET_IN, PUFF, BELL = 204, 209, 210
SLEEVE_NICKNAMES = set(range(204, 217))  # every sleeve style name of Fashionpedia

NECK_MARGIN, SLEEVE_MARGIN, GARMENT_MARGIN = 0.15, 0.10, 0.10
MIN_NECK_SIDE, MIN_NECK_LONG_SIDE, MAX_NECK_TALLNESS = 24, 48, 2.2     # taller than 2.2 x its width: the open front of a jacket
MIN_SLEEVE_SIDE, MIN_GARMENT_SIDE = 32, 96
TRAIN_CAP = {"neck": 3000, "sleeve": 3000}
TRAIN_FLOOR = {"neck": 1500, "sleeve": 1500}
VAL_CAP = {"neck": 150, "sleeve": 150}
DETECTOR_TRAIN = {0: 2500, 1: 2500, 10: 800, 4: 600, 2: 300, 3: 200, 5: 100}       # garment crops per category
DETECTOR_VAL = {0: 250, 1: 250, 10: 80, 4: 60, 2: 30, 3: 20, 5: 10}


def xyxy(b):
    return [b[0], b[1], b[0] + b[2], b[1] + b[3]]


def centre_in(inner, outer):
    cx, cy = (inner[0] + inner[2]) / 2, (inner[1] + inner[3]) / 2
    return outer[0] <= cx <= outer[2] and outer[1] <= cy <= outer[3]


def iou(a, b):
    w = min(a[2], b[2]) - max(a[0], b[0])
    h = min(a[3], b[3]) - max(a[1], b[1])
    if w <= 0 or h <= 0:
        return 0.0
    inter = w * h
    return inter / ((a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter)


def neck_regions(annotations):
    """Neckline and collar boxes of one photo, merged when they are the same neck. -> [(box, class or None)]"""
    parts = [(xyxy(a["bbox"]), a) for a in annotations if a["category_id"] in (NECKLINE, COLLAR)]
    group = list(range(len(parts)))

    def find(i):
        while group[i] != i:
            i = group[i]
        return i
    for i in range(len(parts)):
        for j in range(i + 1, len(parts)):
            a, b = parts[i][0], parts[j][0]
            if iou(a, b) >= 0.15 or centre_in(a, b) or centre_in(b, a):
                group[find(j)] = find(i)
    merged = defaultdict(list)
    for i, p in enumerate(parts):
        merged[find(i)].append(p)
    out = []
    for members in merged.values():
        box = [min(m[0][0] for m in members), min(m[0][1] for m in members), max(m[0][2] for m in members), max(m[0][3] for m in members)]
        collars = [m[1] for m in members if m[1]["category_id"] == COLLAR]
        necklines = [m[1] for m in members if m[1]["category_id"] == NECKLINE]
        label = None
        if collars:
            # a fold-over collar decides; any other collar (mandarin, banded, bow ...) is not one of the classes
            if all(set(c["attribute_ids"]) & FOLD_OVER_COLLAR for c in collars):
                label = "collared-neck"
        elif len(necklines) == 1:
            names = {NECK_ATTR[a] for a in necklines[0]["attribute_ids"] if a in NECK_ATTR}
            if len(names) == 1:
                label = names.pop()
        out.append((box, label))
    return out


def sleeve_label(a):
    names = set(a["attribute_ids"]) & SLEEVE_NICKNAMES
    if names == {PUFF}:
        return "puff-sleeve"
    if names == {BELL}:
        return "bell-sleeve"
    if names == {SET_IN}:
        return "regular-sleeve"
    return None                       # raglan, dolman, kimono, bishop, cap, two styles at once ...: not a class


def dhash(path):
    try:
        with Image.open(path) as im:
            im.draft("L", (64, 64))
            g = np.asarray(im.convert("L").resize((9, 8), Image.Resampling.BILINEAR), dtype=np.int16)
        return path, int(np.packbits((g[:, 1:] > g[:, :-1]).flatten()).view(">u8")[0])
    except Exception:                                           # unreadable: reported by the caller
        return path, None


def _crop(job):
    src, box, margin, dst, size, long_side = job
    try:
        image = crop_box(load_rgb(src), box, margin=margin)
        if size:
            image = square_pad(image, size)
        elif max(image.size) > long_side:
            k = long_side / max(image.size)
            image = image.resize((max(1, round(image.width * k)), max(1, round(image.height * k))), Image.Resampling.BILINEAR)
        image.save(dst, "JPEG", quality=90)
        return None
    except Exception as exc:
        return f"{src}: {type(exc).__name__}: {exc}"


def held_out():
    """Fashionpedia file names of the frozen validation / test photos, and every validation / test whole photo."""
    names = {"val": set(), "test": set()}
    photos = []
    for split, files in (("val", ["val.jsonl"]), ("test", ["test.jsonl", "test_reviewed.jsonl", "test_dmm.jsonl", "bench60.jsonl"])):
        for f in files:
            for r in C.load_jsonl(f"{C.MANIFESTS}/{f}"):
                p = C.whole_photo(r)
                if p:
                    photos.append(p)
                if r.get("source_dataset") == "fashionpedia" and r.get("source_image_path"):
                    names[split].add(os.path.basename(r["source_image_path"].replace("\\", "/")))
    return names, sorted(set(photos))


def main():
    rnd = random.Random(SEED)
    data = json.load(open(ANNOTATIONS, encoding="utf-8"))
    images = {im["id"]: im for im in data["images"]}
    by_image = defaultdict(list)
    for a in data["annotations"]:
        by_image[a["image_id"]].append(a)
    held, held_photos = held_out()

    # ── split by photo ──
    split = {}
    for i, im in images.items():
        name = im["file_name"]
        if name in held["test"]:
            split[i] = "test"
        elif name in held["val"] or int(hashlib.md5(name.encode()).hexdigest(), 16) % 100 < VAL_SHARE:
            split[i] = "val"
        else:
            split[i] = "train"

    # ── near-identical photos: nothing in train may look like a validation / test photo ──
    own = {i: f"{IMAGES}/{images[i]['file_name']}" for i in images}
    todo = sorted(set(own.values()) | set(held_photos))
    print(f"hashing {len(todo)} photos ...", flush=True)
    with ProcessPoolExecutor(max_workers=8) as pool:
        hashes = dict(pool.map(dhash, todo, chunksize=128))
    unreadable = [p for p, h in hashes.items() if h is None]
    pop = np.array([bin(v).count("1") for v in range(256)], dtype=np.uint8)

    def near(candidates, reference):
        ref = np.array([hashes[p] for p in reference if hashes.get(p) is not None], dtype=">u8")
        hit = set()
        for i in candidates:
            h = hashes.get(own[i])
            if h is None:
                hit.add(i)
                continue
            x = np.bitwise_xor(ref, np.uint64(h)).view(np.uint8).reshape(-1, 8)
            if int(pop[x].sum(1).min()) <= NEAR:
                hit.add(i)
        return hit

    test_reference = [p for p in held_photos] + [own[i] for i in images if split[i] == "test"]
    val_ids = [i for i in images if split[i] == "val"]
    drop_val = near([i for i in val_ids if images[i]["file_name"] not in held["val"]], test_reference)
    for i in drop_val:
        split[i] = "dropped"
    train_ids = [i for i in images if split[i] == "train"]
    drop_train = near(train_ids, test_reference + [own[i] for i in images if split[i] == "val"])
    for i in drop_train:
        split[i] = "dropped"
    print("photos:", dict(Counter(split.values())), flush=True)

    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    jobs = []
    summary = {"seed": SEED, "source": ANNOTATIONS, "photos": dict(Counter(split.values())),
               "dropped_near_identical": {"train": len(drop_train), "val": len(drop_val), "hamming": NEAR},
               "unreadable_photos": len(unreadable)}

    # ── classifier crops ──
    parts = {"neck": defaultdict(list), "sleeve": defaultdict(list)}        # (split, class) -> [(image id, box, uid)]
    left_out = Counter()
    for i, annotations in by_image.items():
        if split[i] not in ("train", "val"):
            continue
        for k, (box, label) in enumerate(neck_regions(annotations)):
            w, h = box[2] - box[0], box[3] - box[1]
            if min(w, h) < MIN_NECK_SIDE or max(w, h) < MIN_NECK_LONG_SIDE:
                left_out["neck: too small"] += 1
            elif h > MAX_NECK_TALLNESS * w:
                left_out["neck: tall open front (jacket)"] += 1
            elif label is None:
                left_out["neck: another neckline or collar type"] += 1
            else:
                parts["neck"][(split[i], label)].append((i, box, f"{i}_n{k}"))
        for a in annotations:
            if a["category_id"] != SLEEVE:
                continue
            box, label = xyxy(a["bbox"]), sleeve_label(a)
            if min(box[2] - box[0], box[3] - box[1]) < MIN_SLEEVE_SIDE:
                left_out["sleeve: too small"] += 1
            elif label is None:
                left_out["sleeve: another sleeve style"] += 1
            else:
                parts["sleeve"][(split[i], label)].append((i, box, f"{i}_s{a['id']}"))
    classes = {"neck": C.TASKS["neckline"], "sleeve": C.TASKS["sleeve_design"]}
    margin = {"neck": NECK_MARGIN, "sleeve": SLEEVE_MARGIN}
    summary["classifier_crops"] = {}
    for task in ("neck", "sleeve"):
        summary["classifier_crops"][task] = {}
        for sp in ("train", "val"):
            counts = {}
            for cls in classes[task]:
                items = sorted(parts[task][(sp, cls)], key=lambda x: x[2])
                rnd.shuffle(items)
                available = len(items)
                if sp == "train":
                    items = items[:TRAIN_CAP[task]]
                    repeat = -(-TRAIN_FLOOR[task] // max(1, len(items))) if len(items) < TRAIN_FLOOR[task] else 1
                else:
                    items, repeat = items[:VAL_CAP[task]], 1
                folder = f"{OUT}/{task}/{sp}/{cls}"
                os.makedirs(folder, exist_ok=True)
                for i, box, uid in items:
                    for k in range(repeat):
                        jobs.append((own[i], box, margin[task], f"{folder}/{uid}{'' if k == 0 else f'_r{k}'}.jpg", SIZE, None))
                counts[cls] = {"available": available, "used": len(items), "repeated_x": repeat}
            summary["classifier_crops"][task][sp] = counts
    summary["left_out"] = dict(left_out)

    # ── detector: garment crops with their part boxes ──
    garments = defaultdict(list)                                  # (split, category) -> [(image id, annotation)]
    for i, annotations in by_image.items():
        if split[i] in ("train", "val"):
            for a in annotations:
                if a["category_id"] in GARMENTS and min(a["bbox"][2], a["bbox"][3]) >= MIN_GARMENT_SIDE:
                    garments[(split[i], a["category_id"])].append((i, a))
    summary["detector"] = {"classes": ["neck", "sleeve"], "garment_crops": {}, "boxes": {}}
    for sp, quota in (("train", DETECTOR_TRAIN), ("val", DETECTOR_VAL)):
        os.makedirs(f"{OUT}/detector/images/{sp}", exist_ok=True)
        os.makedirs(f"{OUT}/detector/labels/{sp}", exist_ok=True)
        boxes = Counter()
        for category, n in quota.items():
            items = sorted(garments[(sp, category)], key=lambda x: x[1]["id"])
            rnd.shuffle(items)
            for i, a in items[:n]:
                W, H = images[i]["width"], images[i]["height"]
                g = xyxy(a["bbox"])
                mx, my = GARMENT_MARGIN * (g[2] - g[0]), GARMENT_MARGIN * (g[3] - g[1])
                crop = [max(0, int(g[0] - mx)), max(0, int(g[1] - my)), min(W, int(g[2] + mx)), min(H, int(g[3] + my))]
                cw, ch = crop[2] - crop[0], crop[3] - crop[1]
                found = [(0, b) for b, _ in neck_regions(by_image[i])] + \
                        [(1, xyxy(s["bbox"])) for s in by_image[i] if s["category_id"] == SLEEVE]
                lines = []
                for cls, b in found:
                    if not centre_in(b, crop):
                        continue
                    x1, y1, x2, y2 = max(b[0], crop[0]), max(b[1], crop[1]), min(b[2], crop[2]), min(b[3], crop[3])
                    if x2 - x1 < 4 or y2 - y1 < 4:
                        continue
                    lines.append(f"{cls} {((x1 + x2) / 2 - crop[0]) / cw:.6f} {((y1 + y2) / 2 - crop[1]) / ch:.6f} {(x2 - x1) / cw:.6f} {(y2 - y1) / ch:.6f}")
                    boxes[["neck", "sleeve"][cls]] += 1
                name = f"{i}_{a['id']}"
                with open(f"{OUT}/detector/labels/{sp}/{name}.txt", "w") as f:
                    f.write("\n".join(lines))
                # the crop box is already padded: margin 0 here
                jobs.append((own[i], crop, 0.0, f"{OUT}/detector/images/{sp}/{name}.jpg", None, DETECTOR_SIDE))
            summary["detector"]["garment_crops"].setdefault(sp, {})[GARMENTS[category]] = min(n, len(items))
        summary["detector"]["boxes"][sp] = dict(boxes)
    with open(f"{OUT}/detector/data.yaml", "w") as f:
        f.write(f"path: {os.path.abspath(OUT + '/detector').replace(os.sep, '/')}\ntrain: images/train\nval: images/val\nnames:\n  0: neck\n  1: sleeve\n")

    print(f"writing {len(jobs)} images ...", flush=True)
    errors = []
    with ProcessPoolExecutor(max_workers=8) as pool:
        for n, err in enumerate(pool.map(_crop, jobs, chunksize=64), 1):
            if err:
                errors.append(err)
            if n % 5000 == 0:
                print(f"  {n}/{len(jobs)}", flush=True)
    summary["unreadable_crops"] = errors
    json.dump(summary, open(f"{OUT}/summary.json", "w", encoding="utf-8"), indent=1)
    print(json.dumps({k: v for k, v in summary.items() if k != "unreadable_crops"}, indent=1))
    print("unreadable crops:", len(errors))


DETECTED_TRAIN_CAP = {"neckline": 2500, "sleeve_design": 3000}       # garment records per class given to the detector


def add_detected():
    """Step 2: part crops found by the part detector in the garment-level train / validation records."""
    from app.ai import garment_parts
    model_dir = next(d for d in (f"{C.ROOT}/runs/candidate_model", C.MODEL_DIR) if garment_parts.available(d))
    rnd = random.Random(SEED)
    summary = json.load(open(f"{OUT}/summary.json", encoding="utf-8"))
    folder = {"neckline": "neck", "sleeve_design": "sleeve"}
    kind = {"neckline": "neck", "sleeve_design": "sleeve"}
    report = {"part_detector": f"{model_dir}/{garment_parts.FILE}", "tasks": {}}
    for task in ("neckline", "sleeve_design"):
        report["tasks"][task] = {}
        for sp, manifest in (("train", "train.jsonl"), ("val", "val.jsonl")):
            by_class = defaultdict(list)
            for r in C.load_jsonl(f"{C.MANIFESTS}/{manifest}"):
                lab = C.label_of(task, r)
                if not lab:
                    continue
                name = os.path.basename((r.get("source_image_path") or "").replace("\\", "/"))
                if sp == "train" and r.get("source_dataset") == "fashionpedia" and int(hashlib.md5(name.encode()).hexdigest(), 16) % 100 < VAL_SHARE:
                    continue                                   # this photo is a validation photo of the part datasets
                by_class[lab[0]].append(r)
            counts = {}
            for cls, records in by_class.items():
                records.sort(key=lambda r: r["record_uid"])
                rnd.shuffle(records)
                records = records[:DETECTED_TRAIN_CAP[task] if sp == "train" else VAL_CAP[folder[task]]]
                repeat = summary["classifier_crops"][folder[task]]["train"][cls]["repeated_x"] if sp == "train" else 1
                out_dir = f"{OUT}/{folder[task]}/{sp}/{cls}"
                os.makedirs(out_dir, exist_ok=True)
                found = crops = 0
                for r in records:
                    src, box = C.garment_crop(r)
                    if not src or not os.path.exists(src):
                        continue
                    try:
                        picture = square_pad(crop_box(load_rgb(src), box))
                    except Exception:
                        continue
                    pictures = garment_parts.part_pictures(picture, model_dir)[kind[task]]
                    found += bool(pictures)
                    for k, part in enumerate(pictures):
                        uid = re.sub(r"[^A-Za-z0-9_.-]", "_", r["record_uid"])
                        part = part.resize((SIZE, SIZE), Image.Resampling.BILINEAR)
                        for j in range(repeat):
                            part.save(f"{out_dir}/m_{uid}_{k}{'' if j == 0 else f'_r{j}'}.jpg", "JPEG", quality=90)
                        crops += 1
                counts[cls] = {"records": len(records), "part_found": found, "crops": crops, "repeated_x": repeat}
                print(task, sp, cls, counts[cls], flush=True)
            report["tasks"][task][sp] = counts
    summary["detected_crops"] = report
    json.dump(summary, open(f"{OUT}/summary.json", "w", encoding="utf-8"), indent=1)


if __name__ == "__main__":
    add_detected() if "--add-detected" in sys.argv else main()
