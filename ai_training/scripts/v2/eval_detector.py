"""Independent test of the garment detector (never used for training or checkpoint selection).

Set A - DeepFashion2 validation images NOT in the detector's val split (seeded sample): ultralytics mAP plus the
        app-level question "is the box the app crops the right garment?" (IoU >= 0.5 with a ground-truth top box).
Set B - DeepFashion-MultiModal WOMEN tops photos (different source: plain-background shop photos) whose ground truth
        comes from the human parsing masks (label 1 = top, 2 = outer, 4 = dress): same app-level question.

    backend\\venv\\Scripts\\python ai_training\\scripts\\v2\\eval_detector.py --weights <best.pt> --out <dir>
"""
import argparse
import ast
import glob
import json
import os
import random
import sys

import numpy as np
import pandas as pd
from PIL import Image

sys.path.insert(0, "backend")
from app.ai import garment_detector as gd  # noqa: E402

DF2 = "Dataset/archive/DeepFashion2"
DET_VAL = "ai_training/datasets/deepfashion2_det/images/val"
DMM_SEGM = "ai_training/datasets/deepfashion_multimodal/raw/segm/segm"
DMM_IMG = "ai_training/datasets/deepfashion_multimodal/raw/images"
TOPS = {"short sleeve top", "long sleeve top", "vest", "sling"}
SEG = {1: "top", 2: "outerwear", 4: "dress"}


def iou(a, b):
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    u = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / u if u else 0.0


def score(cases, weights):
    """cases: [(image_path, gt_top_boxes, gt_main_class)] -> app-level metrics."""
    n = hit = found = cls_ok = 0
    rows = []
    for path, tops, main in cases:
        r = gd.detect_garment(path, model_path=weights)
        n += 1
        got = r["box_xyxy"] is not None
        found += got
        good = got and r["class"] == "top" and any(iou(r["box_xyxy"], t) >= 0.5 for t in tops)
        hit += good
        cls_ok += (r["class"] == main)
        rows.append({"image": path, "pred_class": r["class"], "score": r["score"], "box": r["box_xyxy"],
                     "gt_main_class": main, "correct_top_box": bool(good)})
    return {"n": n, "box_returned": round(found / n, 4), "correct_top_crop_iou50": round(hit / n, 4),
            "main_class_accuracy": round(cls_ok / n, 4)}, rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--weights", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--n", type=int, default=600)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    rnd = random.Random(2026)
    res = {"weights": os.path.abspath(a.weights), "min_score": gd.MIN_SCORE, "crop_margin_added_by_caller": gd.CROP_MARGIN}

    # ---- A: DF2 validation, images with exactly one garment that is a top (clear app-like question) ----
    d = pd.read_csv(f"{DF2}/img_info_dataframes/validation.csv", usecols=["path", "b_box", "category_name"])
    d["file"] = d.path.str.split("/").str[-1]
    used = set(os.listdir(DET_VAL))
    g = d[~d.file.isin(used)].groupby("file")
    single = [f for f, grp in g if len(grp) == 1 and grp.category_name.iloc[0] in TOPS]
    pick = rnd.sample(single, min(a.n, len(single)))
    cases = []
    for f in pick:
        row = g.get_group(f).iloc[0]
        cases.append((f"{DF2}/deepfashion2_original_images/validation/image/{f}", [list(ast.literal_eval(row.b_box))], "top"))
    res["A_df2_validation_single_top"], rows_a = score(cases, a.weights)

    # ---- B: DMM parsing masks (women's tops categories) ----
    segs = sorted(glob.glob(f"{DMM_SEGM}/WOMEN-*_segm.png"))
    segs = [s for s in segs if any(c in s for c in ("Blouses_Shirts", "Tees_Tanks", "Graphic_Tees"))]
    rnd.shuffle(segs)
    cases = []
    for s in segs:
        img = os.path.join(DMM_IMG, os.path.basename(s).replace("_segm.png", ".jpg"))
        if not os.path.exists(img):
            continue
        m = np.array(Image.open(s))
        boxes, areas = {}, {}
        for k, name in SEG.items():
            ys, xs = np.nonzero(m == k)
            if len(xs) > 200:
                boxes[name] = [float(xs.min()), float(ys.min()), float(xs.max()), float(ys.max())]
                areas[name] = len(xs)
        if "top" not in boxes or "outerwear" in boxes or "dress" in boxes:
            continue        # only unambiguous single-top photos
        cases.append((img, [boxes["top"]], "top"))
        if len(cases) >= a.n:
            break
    if cases:
        res["B_dmm_shop_photos_single_top"], rows_b = score(cases, a.weights)
    else:
        res["B_dmm_shop_photos_single_top"], rows_b = "not run: DMM images not available yet", []

    # ---- ultralytics box mAP on set A images (all garments of the 3 classes) ----
    json.dump(res, open(f"{a.out}/detector_independent_test.json", "w"), indent=2)
    pd.DataFrame(rows_a + rows_b).to_csv(f"{a.out}/detector_independent_test_rows.csv", index=False)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
