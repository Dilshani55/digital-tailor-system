"""Build one image-folder dataset per model from the audited manifests.

    backend\\venv\\Scripts\\python backend\\training\\prepare_datasets.py

Output (local, git-ignored): backend/training/datasets/attributes/
    <task>/train|val|test/<class>/*.jpg     garment crops, padded to a square, 256 px
    <task>/eval.jsonl                        validation and test photos (whole photo + label) for the evaluation
                                             that uses the app's own garment detector
    summary.json                             counts per task / split / class / trust tier

Splits are the audited ones (no photo, garment item or near-identical photo is shared between training and
validation / test). Training classes are balanced: a large class is capped, a small class is repeated; validation
and test are never repeated or balanced - they keep the real examples.
"""
import json
import os
import random
import re
import shutil
import sys
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor

sys.path.insert(0, "backend")
sys.path.insert(0, "backend/training")
import common as C                                             # noqa: E402
from app.ai.preprocess import crop_box, load_rgb, square_pad    # noqa: E402

SIZE = 256
SEED = 42
# training images per class: cap for big classes, floor (by repetition) for small ones
TRAIN_CAP = {"garment": 3000, "neckline": 2500, "sleeve_length": 4000, "sleeve_design": 400}
TRAIN_FLOOR = {"garment": 3000, "neckline": 800, "sleeve_length": 4000, "sleeve_design": 300}
# validation images per class in the folder a model is selected on (kept close to balanced so that the selection
# is not decided by the biggest class)
VAL_CAP = {"garment": 600, "neckline": 100, "sleeve_length": 600, "sleeve_design": 60}
SETS = {"train": ["train.jsonl"], "val": ["val.jsonl"], "test": ["test.jsonl", "test_reviewed.jsonl"],
        "test_dmm": ["test_dmm.jsonl"], "bench60": ["bench60.jsonl"]}


def safe(uid):
    return re.sub(r"[^A-Za-z0-9_.-]", "_", uid)


def _write(job):
    src, box, dst = job
    try:
        if not os.path.exists(dst):
            square_pad(crop_box(load_rgb(src), box), SIZE).save(dst, "JPEG", quality=90)
        return None
    except Exception as exc:                                   # an unreadable image is reported, not hidden
        return f"{src}: {type(exc).__name__}: {exc}"


def main():
    rnd = random.Random(SEED)
    if os.path.isdir(C.OUT):
        shutil.rmtree(C.OUT)
    records = {s: [r for f in files for r in C.load_jsonl(f"{C.MANIFESTS}/{f}")] for s, files in SETS.items()}
    jobs, summary = [], {}
    for task, classes in C.TASKS.items():
        summary[task] = {}
        eval_rows = []
        for split, recs in records.items():
            by_class = defaultdict(list)
            for r in recs:
                lab = C.label_of(task, r)
                if lab:
                    by_class[lab[0]].append((r, lab[1]))
            folder = "test" if split == "test" else split
            counts = {}
            for cls in classes:
                items = sorted(by_class[cls], key=lambda x: x[0]["record_uid"])
                tiers = Counter(t for _, t in items)
                if split == "train":
                    # trusted labels first, then proxies, up to the cap; small classes are repeated up to the floor
                    rnd.shuffle(items)
                    items.sort(key=lambda x: x[1] != "trusted")
                    items = items[:TRAIN_CAP[task]]
                    repeat = max(1, -(-TRAIN_FLOOR[task] // max(1, len(items)))) if len(items) < TRAIN_FLOOR[task] else 1
                elif split == "val":
                    rnd.shuffle(items)
                    items.sort(key=lambda x: x[1] != "trusted")
                    items, repeat = items[:VAL_CAP[task]], 1
                else:
                    repeat = 1
                out_dir = f"{C.OUT}/{task}/{folder}/{cls}"
                if split in ("train", "val", "test"):
                    os.makedirs(out_dir, exist_ok=True)
                used = 0
                for r, tier in items:
                    src, box = C.garment_crop(r)
                    if not src or not os.path.exists(src):
                        continue
                    name = safe(r["record_uid"])
                    if split in ("train", "val", "test"):
                        for k in range(repeat):
                            jobs.append((src, box, f"{out_dir}/{name}{'' if k == 0 else f'_r{k}'}.jpg"))
                    if split != "train":
                        eval_rows.append({"task": task, "set": split, "label": cls, "tier": tier, "record_uid": r["record_uid"],
                                          "photo": C.whole_photo(r), "crop_source": src, "crop_box_xyxy": box})
                    used += 1
                counts[cls] = {"available": dict(tiers), "used": used, "repeated_x": repeat}
            summary[task][split] = counts
        os.makedirs(f"{C.OUT}/{task}", exist_ok=True)
        with open(f"{C.OUT}/{task}/eval.jsonl", "w", encoding="utf-8") as f:
            for row in eval_rows:
                f.write(json.dumps(row) + "\n")
    print(f"writing {len(jobs)} images ...", flush=True)
    errors = []
    with ProcessPoolExecutor(max_workers=6) as pool:
        for i, err in enumerate(pool.map(_write, jobs, chunksize=64), 1):
            if err:
                errors.append(err)
            if i % 5000 == 0:
                print(f"  {i}/{len(jobs)}", flush=True)
    json.dump({"seed": SEED, "image_size": SIZE, "tasks": summary, "unreadable": errors},
              open(f"{C.OUT}/summary.json", "w", encoding="utf-8"), indent=1)
    for task, splits in summary.items():
        print(task)
        for split, counts in splits.items():
            print("  ", split.ljust(9), {c: (v["used"], f"x{v['repeated_x']}") if v["repeated_x"] > 1 else v["used"] for c, v in counts.items()},
                  {c: v["available"] for c, v in counts.items()} if split in ("test", "bench60") else "")
    print("unreadable images:", len(errors))


if __name__ == "__main__":
    main()
