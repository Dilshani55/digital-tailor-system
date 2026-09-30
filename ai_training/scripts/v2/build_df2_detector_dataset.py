"""Build a YOLO detection dataset (top / outerwear / dress) from the local DeepFashion2 copy.

Source: Dataset/archive/DeepFashion2 (Kaggle mirror "deepfashion2-original-with-dataframes", named in the approved
proposal). Licence: DeepFashion2 is for non-commercial research only - images are hard-linked (not copied or
redistributed) into ai_training/datasets/deepfashion2_det/, which is git-ignored.

Splits: train <- a sample of DF2 *train*; val <- a sample of DF2 *validation* (official, disjoint image sets).
DF2 validation images that deepfashion2_tops uses as classifier val/test are excluded from the detector val set.

    backend\\venv\\Scripts\\python ai_training\\scripts\\v2\\build_df2_detector_dataset.py --train 9000 --val 1200
"""
import argparse
import ast
import json
import os
import random

import pandas as pd

SRC = "Dataset/archive/DeepFashion2"
OUT = "ai_training/datasets/deepfashion2_det"
CLASSES = ["top", "outerwear", "dress"]
CAT = {
    "short sleeve top": 0, "long sleeve top": 0, "vest": 0, "sling": 0,
    "short sleeve outwear": 1, "long sleeve outwear": 1,
    "short sleeve dress": 2, "long sleeve dress": 2, "vest dress": 2, "sling dress": 2,
}


def load(split):
    d = pd.read_csv(f"{SRC}/img_info_dataframes/{split}.csv",
                    usecols=["path", "b_box", "category_name", "viewpoint", "occlusion", "img_height", "img_width"])
    d["file"] = d["path"].str.split("/").str[-1]
    return d


def classifier_eval_ids():
    """DF2 image ids used as classifier val/test by deepfashion2_tops - never used by the detector (independence)."""
    ids = set()
    for sp in ("val", "test"):
        p = f"ai_training/datasets/deepfashion2_tops/annotations/{sp}.jsonl"
        if os.path.exists(p):
            for line in open(p, encoding="utf-8"):
                ids.add(json.loads(line)["source_image_uid"].split(":")[-1] + ".jpg")
    return ids


def build(split_src, split_dst, n, rnd, exclude=frozenset()):
    d = load(split_src)
    d = d[d.category_name.isin(CAT) & ~d.file.isin(exclude)]
    by_img = d.groupby("file")
    files = list(by_img.groups)
    # oversample images that contain a no-wear (product) view so shop-style photos are represented
    prod = set(d[d.viewpoint == 1].file)
    rnd.shuffle(files)
    files.sort(key=lambda f: 0 if f in prod else 1)
    chosen = files[: n // 3] + rnd.sample(files[n // 3:], n - n // 3)
    img_dir = f"{OUT}/images/{split_dst}"
    lbl_dir = f"{OUT}/labels/{split_dst}"
    os.makedirs(img_dir, exist_ok=True)
    os.makedirs(lbl_dir, exist_ok=True)
    counts = [0, 0, 0]
    for f in chosen:
        src = f"{SRC}/deepfashion2_original_images/{split_src}/image/{f}"
        dst = f"{img_dir}/{f}"
        if not os.path.exists(dst):
            try:
                os.link(src, dst)
            except OSError:
                import shutil
                shutil.copy2(src, dst)
        lines = []
        for _, r in by_img.get_group(f).iterrows():
            x1, y1, x2, y2 = ast.literal_eval(r.b_box)
            W, H = float(r.img_width), float(r.img_height)
            c = CAT[r.category_name]
            counts[c] += 1
            lines.append(f"{c} {(x1 + x2) / 2 / W:.6f} {(y1 + y2) / 2 / H:.6f} {(x2 - x1) / W:.6f} {(y2 - y1) / H:.6f}")
        with open(f"{lbl_dir}/{os.path.splitext(f)[0]}.txt", "w") as fh:
            fh.write("\n".join(lines) + "\n")
    return {"images": len(chosen), "boxes_per_class": dict(zip(CLASSES, counts)),
            "product_view_images": sum(1 for f in chosen if f in prod)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--train", type=int, default=9000)
    ap.add_argument("--val", type=int, default=1200)
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    rnd = random.Random(a.seed)
    global EXCL
    EXCL = classifier_eval_ids()
    stats = {"train": build("train", "train", a.train, rnd), "val": build("validation", "val", a.val, rnd, exclude=EXCL)}
    stats["val"]["excluded_classifier_eval_images"] = len(EXCL)
    with open(f"{OUT}/data.yaml", "w") as f:
        f.write(f"path: {os.path.abspath(OUT)}\ntrain: images/train\nval: images/val\nnames:\n")
        for i, c in enumerate(CLASSES):
            f.write(f"  {i}: {c}\n")
    json.dump(stats, open(f"{OUT}/build_stats.json", "w"), indent=2)
    print(json.dumps(stats, indent=1))


if __name__ == "__main__":
    main()
