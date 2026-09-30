"""Build trusted-label JSONL annotations from DeepFashion-MultiModal (DMM) for the 15-class heads.

Source  : https://github.com/yumingj/DeepFashion-MultiModal (images.zip, labels.zip, segm.zip from the authors'
          Google Drive). Licence: "available for non-commercial research purposes only" - kept local, git-ignored.
Output  : ai_training/datasets/deepfashion_multimodal/annotations/{train,val,test}.jsonl in the same record format
          as ai_training/datasets/deepfashion2_tops/annotations/*.jsonl.

Mapping (source label -> class; anything else is MASKED, never remapped to a look-alike):
  sleeve length   0 sleeveless -> sleeveless | 1 short -> short-sleeve | 3 long -> long-sleeve
                  2 medium, 4 not-long, 5 NA -> masked
  sleeve style    only when sleeve length is sleeveless: none (rule "none iff sleeveless"); otherwise masked
                  (DMM has no puff/bell/regular information)
  neckline        0 V -> v-neck | 1 square -> square-neck | 2 round -> round-neck | 4 lapel -> collared-neck
                  (ONLY with --lapel-as-collared: a seeded sample of 16
                  women's-top "lapel" front views was inspected on 1 Oct 2026 and all 16 showed a shirt/blouse collar;
                  sheet ai_training/runs_v2/label_checks/dmm_lapel_sample.jpg. 16 images cannot establish the mapping
                  and "lapel" can also mean a blazer lapel, so these labels carry provenance
                  candidate_dmm_lapel_needs_human_review and must NOT be treated as trusted until a person reviews them) | 3 standing, 5 suspenders, 6 NA
                  -> masked; masked on back views (view code 3), where the neckline is not visible
  garment type    shop category Blouses_Shirts -> blouse, Tees_Tanks / Graphic_Tees -> t-shirt;
                  if "upper clothing covering navel" == 0 (no) the record becomes crop-top (provenance
                  dmm_navel_uncovered). Other categories (dresses, jackets, sweaters, ...) are not used.
Scope   : WOMEN images of Blouses_Shirts, Tees_Tanks, Graphic_Tees only.
Splits  : by garment item id (all views of one item stay in one split): 70 / 15 / 15 via a stable hash.

    backend\\venv\\Scripts\\python ai_training\\scripts\\v2\\build_dmm_annotations.py [--lapel-as-collared]
Crops are added afterwards by crop_with_detector.py (same detector the app uses).
"""
import argparse
import hashlib
import json
import os
import re
from collections import Counter

ROOT = "ai_training/datasets/deepfashion_multimodal"
SHAPE = f"{ROOT}/raw/labels/labels/shape/shape_anno_all.txt"
IMAGES = f"{ROOT}/raw/images"
CATS = {"Blouses_Shirts": "blouse", "Tees_Tanks": "t-shirt", "Graphic_Tees": "t-shirt"}
SLEEVE = {0: "sleeveless", 1: "short-sleeve", 3: "long-sleeve"}
NECK = {0: "v-neck", 1: "square-neck", 2: "round-neck"}
NAME = re.compile(r"^(WOMEN|MEN)-([A-Za-z_]+)-(id_\d+)-(\d+)_(\d+)_([a-z]+)\.jpg$")


def split_of(item_id: str) -> str:
    h = int(hashlib.sha1(item_id.encode()).hexdigest(), 16) % 100
    return "train" if h < 70 else ("val" if h < 85 else "test")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lapel-as-collared", action="store_true")
    a = ap.parse_args()
    if a.lapel_as_collared:
        NECK[4] = "collared-neck"
    out = {"train": [], "val": [], "test": []}
    skipped = Counter()
    for line in open(SHAPE, encoding="utf-8"):
        parts = line.split()
        fname, v = parts[0], [int(x) for x in parts[1:]]
        m = NAME.match(fname)
        if not m:
            skipped["unparsed_name"] += 1
            continue
        gender, cat, item, _, view_code, view = m.groups()
        if gender != "WOMEN" or cat not in CATS:
            skipped["out_of_scope_category"] += 1
            continue
        img = f"{IMAGES}/{fname}"
        if not os.path.exists(img):
            skipped["image_missing"] += 1
            continue
        sl, neck, navel = v[0], v[9], v[11]
        labels = {"garment_type": CATS[cat], "neckline_type": None, "sleeve_length": SLEEVE.get(sl), "sleeve_style": None}
        prov = {"garment_type": "dmm_shop_category", "neckline_type": "missing/masked",
                "sleeve_length": "dmm_human_shape" if sl in SLEEVE else "missing/masked", "sleeve_style": "missing/masked"}
        if navel == 0:
            labels["garment_type"], prov["garment_type"] = "crop-top", "dmm_navel_uncovered"
        if labels["sleeve_length"] == "sleeveless":
            labels["sleeve_style"], prov["sleeve_style"] = "none", "derived_from_explicit_sleeveless"
        if neck in NECK and view_code != "3":
            labels["neckline_type"] = NECK[neck]
            prov["neckline_type"] = "candidate_dmm_lapel_needs_human_review" if neck == 4 else "dmm_human_shape"
        masks = {h: int(labels[h] is not None) for h in labels}
        sp = split_of(item)
        out[sp].append({
            "record_uid": f"dmm:{fname[:-4]}", "source_dataset": "deepfashion_multimodal",
            "source_image_uid": f"dmm:{fname[:-4]}", "group_id": f"dmm:{item}", "view": view,
            "split": sp, "crop_path": None, "full_image_path": img, "bbox": None,
            "labels": labels, "masks": masks, "provenance": prov,
        })
    os.makedirs(f"{ROOT}/annotations", exist_ok=True)
    summary = {"skipped": dict(skipped), "splits": {}}
    for sp, recs in out.items():
        with open(f"{ROOT}/annotations/{sp}.jsonl", "w", encoding="utf-8") as f:
            for r in recs:
                f.write(json.dumps(r) + "\n")
        summary["splits"][sp] = {"records": len(recs), "items": len({r["group_id"] for r in recs}),
                                 "per_head": {h: dict(Counter(r["labels"][h] for r in recs if r["masks"][h]))
                                              for h in ("garment_type", "neckline_type", "sleeve_length", "sleeve_style")}}
    summary["lapel_as_collared"] = a.lapel_as_collared
    json.dump(summary, open(f"{ROOT}/annotations/summary.json", "w"), indent=2)
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
