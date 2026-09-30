#!/usr/bin/env python3
"""
build_m40_manifests.py - training / validation / test manifests for the 3/5/3/4 model "M40".

Sources (all labels TRUSTED only; everything else is masked, never guessed):
  * Fashionpedia records already re-expressed for the 15 classes (ai_training/data/manifests_15class): heads whose
    provenance is not human_verified / fashionpedia_direct / derived_from_explicit_sleeveless are masked.
    (rule-derived collared-neck and regular-sleeve, CLIP pseudo-labels are therefore NOT used for training.)
  * DeepFashion2 tops (ai_training/datasets/deepfashion2_tops): sleeve_length from the human-annotated category,
    sleeve_style 'none' derived from an explicit sleeveless category.
Records that keep no trusted head are dropped. Splits stay as built (image-level, near-duplicate controlled).
Also writes: test_df2.jsonl, test_fp.jsonl and the 60-image locked benchmark in the same format.
"""

import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from ai_training.training import labels15 as L   # noqa: E402

CLASSES = L.load_classes("ai_training/config/classes_v2_15class.json")
TRUSTED = L.TRUSTED | {"df2_human_category"}


def mask_untrusted(rec):
    r = json.loads(json.dumps(rec))
    for h in L.HEADS:
        if r["masks"].get(h) == 1 and r["provenance"].get(h) not in TRUSTED:
            r["labels"][h], r["masks"][h], r["provenance"][h] = None, 0, L.MASKED_PROVENANCE
    r["class_indices"] = {h: (CLASSES[h].index(r["labels"][h]) if r["labels"][h] is not None else None) for h in L.HEADS}
    r["trusted"] = {h: bool(r["masks"][h] and r["provenance"][h] in TRUSTED) for h in L.HEADS}
    return r


def keep(rec):
    return any(rec["masks"].get(h) == 1 for h in L.HEADS)


def with_indices(rec):
    rec["class_indices"] = {h: (CLASSES[h].index(rec["labels"][h]) if rec["labels"][h] is not None else None) for h in L.HEADS}
    rec["trusted"] = {h: bool(rec["masks"][h] and rec["provenance"][h] in TRUSTED) for h in L.HEADS}
    return rec


def main():
    out = "ai_training/data/manifests_m40"
    os.makedirs(out, exist_ok=True)
    fp = {s: [mask_untrusted(r) for r in L.load_jsonl(f"ai_training/data/manifests_15class/{s}.jsonl")] for s in L.SPLITS}
    fp = {s: [r for r in rs if keep(r)] for s, rs in fp.items()}
    df2 = {s: [with_indices(r) for r in L.load_jsonl(f"ai_training/datasets/deepfashion2_tops/annotations/{s}.jsonl")] for s in L.SPLITS}

    def dump(name, recs):
        with open(os.path.join(out, name), "w", encoding="utf-8") as f:
            for r in recs:
                f.write(json.dumps(r) + "\n")

    for s in L.SPLITS:
        dump(f"{s}.jsonl", fp[s] + df2[s])
    dump("test_fp.jsonl", fp["test"])
    dump("test_df2.jsonl", df2["test"])

    # locked 60-image real-product benchmark in the 15-class format (labels outside the 15 classes are masked)
    bench = []
    for line in open("ai_training/data/eval_real_product_set/eval_manifest.jsonl", encoding="utf-8"):
        e = json.loads(line)
        r = {"record_uid": e["eval_id"], "split": "bench", "source_image_path": e["image_path"].replace("\\", "/"),
             "crop_path": None, "bbox": e["bbox"], "labels": e["labels"], "masks": e["masks"],
             "provenance": e["provenance"], "confidence": {}}
        bench.append(mask_untrusted(L.convert_record(r, CLASSES)))
    dump("bench60.jsonl", bench)

    counts = L.count_classes({s: fp[s] + df2[s] for s in L.SPLITS}, CLASSES)
    json.dump({"counts": counts, "records": {s: len(fp[s]) + len(df2[s]) for s in L.SPLITS},
               "manifest_sha256": {n: L.sha256_file(os.path.join(out, n)) for n in sorted(os.listdir(out)) if n.endswith(".jsonl")}},
              open(os.path.join(out, "counts.json"), "w"), indent=2)
    print(f"{'head':14}{'class':16}" + "".join(f"{s:>16}" for s in L.SPLITS))
    for h in L.HEADS:
        for c in CLASSES[h]:
            print(f"{h:14}{c:16}" + "".join(f"{counts[s][h][c]['trusted']:>16}" for s in L.SPLITS))
    print("records:", {s: len(fp[s]) + len(df2[s]) for s in L.SPLITS}, "| bench60:", len(bench))


if __name__ == "__main__":
    main()
