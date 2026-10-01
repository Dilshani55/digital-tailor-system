"""Review queue for the two classes that have NO trusted label today: collared-neck and regular-sleeve.

Every row is a photo a person must look at. The hint says why the photo is a candidate; it is never used as a
label. The reviewer chooses the real class of that head (or "other" / "unclear"), so each answer gives a trusted
label whatever it is. A photo keeps the split (train / val / test) it already has, so nothing crosses splits.

Candidates (seeded sample, seed 42):
  neckline  - Fashionpedia garments with an attached collar part (the existing 15-class queue)
            - DeepFashion-MultiModal FRONT views whose source neckline is "lapel" (masked in training until reviewed)
  sleeves   - Fashionpedia sleeves annotated "set-in sleeve" (a construction, not a style - hence the review)
            - DeepFashion2 short / long sleeved tops (human sleeve-length label, no style label)

    backend\\venv\\Scripts\\python ai_training\\scripts\\v2\\build_review_queue_m42.py
Output: ai_training/data/label_queue_m42/queue.jsonl + queue_summary.json   (local, git-ignored)
Review: backend\\venv\\Scripts\\python ai_training\\tools\\review_labels.py
"""
import json
import os
import random
import sys
from collections import Counter

sys.path.insert(0, ".")
from ai_training.training import labels15 as L  # noqa: E402

OUT = "ai_training/data/label_queue_m42"
MANIFESTS = "ai_training/data/manifests_m41"
FP_QUEUE = "ai_training/data/label_queue_15class/queue.jsonl"
SEED = 42

OPTIONS = {
    "neckline_type": ["collared-neck", "round-neck", "v-neck", "square-neck", "off-shoulder", "other", "unclear"],
    "sleeve_style": ["regular-sleeve", "puff-sleeve", "bell-sleeve", "none", "other", "unclear"],
}
QUESTION = {
    "neckline_type": "Which neckline does this garment have?",
    "sleeve_style": "Which sleeve style does this garment have?",
}
FP_HINT = {
    "neckline_type": "the source annotation has a collar part attached to this garment",
    "sleeve_style": "the source annotation calls the sleeve 'set-in' (how it is sewn in, not its style)",
}
# (source, head) -> how many photos per split
PLAN = {
    ("fashionpedia", "neckline_type"): {"train": 140, "val": 40, "test": 45},
    ("deepfashion_multimodal", "neckline_type"): {"train": 100, "val": 30, "test": 35},
    ("fashionpedia", "sleeve_style"): {"train": 140, "val": 40, "test": 45},
    ("deepfashion2", "sleeve_style"): {"train": 60, "val": 20, "test": 30},
}


def exists(path):
    return bool(path) and os.path.exists(path.replace("\\", "/"))


def row(queue_id, head, source, split, hint_class, hint, image_path, **extra):
    return dict(queue_id=queue_id, head=head, source=source, split=split, hint_class=hint_class, hint=hint,
                hint_is_a_label=False, image_path=image_path.replace("\\", "/"), options=OPTIONS[head],
                question=QUESTION[head], **extra)


def candidates():
    pools = {key: {"train": [], "val": [], "test": []} for key in PLAN}

    for q in L.load_jsonl(FP_QUEUE):
        head = {"collared-neck": "neckline_type", "regular-sleeve": "sleeve_style"}.get(q.get("target_class"))
        if head and exists(q.get("source_image_path")):
            pools[("fashionpedia", head)][q["split"]].append(row(
                f"m42-fp-{head}-{q['split']}-{q['source_annotation_id']}", head, "fashionpedia", q["split"], q["target_class"],
                FP_HINT[head], q["source_image_path"], bbox_xywh=q.get("bbox"),
                source_annotation_id=q["source_annotation_id"], source_image_uid=q.get("source_image_uid")))

    files = {"train": "train.jsonl", "val": "val.jsonl", "test": "test_dmm.jsonl"}
    for split, name in files.items():
        for r in L.load_jsonl(f"{MANIFESTS}/{name}"):
            # front views only: the neckline is not visible from the back or in a detail shot
            if (r.get("masked_candidate") or {}).get("neckline_type") == "collared-neck" and r.get("view") == "front"                     and exists(r.get("crop_path")):
                pools[("deepfashion_multimodal", "neckline_type")][split].append(row(
                    f"m42-dmm-neckline_type-{split}-{r['record_uid'][4:]}", "neckline_type", "deepfashion_multimodal", split,
                    "collared-neck", "source neckline value 'lapel' (may be a shirt collar or a jacket lapel)",
                    r["crop_path"], full_image_path=r.get("full_image_path"), record_uid=r["record_uid"]))

    files = {"train": "train.jsonl", "val": "val.jsonl", "test": "test.jsonl"}
    for split, name in files.items():
        for r in L.load_jsonl(f"{MANIFESTS}/{name}"):
            if str(r.get("record_uid", "")).startswith("df2:") and r["labels"].get("sleeve_length") in ("short-sleeve", "long-sleeve") \
                    and exists(r.get("crop_path")):
                pools[("deepfashion2", "sleeve_style")][split].append(row(
                    f"m42-df2-sleeve_style-{split}-{r['record_uid'].split(':')[-1]}", "sleeve_style", "deepfashion2", split,
                    "regular-sleeve", f"human sleeve-length label '{r['labels']['sleeve_length']}', no style label",
                    r["crop_path"], full_image_path=r.get("full_image_path"), record_uid=r["record_uid"]))
    return pools


def build(seed=SEED):
    pools = candidates()
    rnd = random.Random(seed)
    queue, summary = [], {}
    for key, per_split in PLAN.items():
        for split, wanted in per_split.items():
            pool = sorted(pools[key][split], key=lambda q: q["queue_id"])
            rnd.shuffle(pool)
            picked = pool[:wanted]
            queue.extend(picked)
            summary[f"{key[0]} / {key[1]} / {split}"] = {"wanted": wanted, "available": len(pool), "queued": len(picked)}
    # neckline first, then sleeves; inside a head the sources and splits are mixed so the reviewer cannot guess a pattern
    by_head = {h: [q for q in queue if q["head"] == h] for h in OPTIONS}
    ordered = []
    for h, rows in by_head.items():
        rnd.shuffle(rows)
        ordered.extend(rows)
    for i, q in enumerate(ordered, 1):
        q["position"] = i
    return ordered, summary


def main():
    queue, summary = build()
    os.makedirs(OUT, exist_ok=True)
    with open(f"{OUT}/queue.jsonl", "w", encoding="utf-8") as f:
        for q in queue:
            f.write(json.dumps(q) + "\n")
    report = {"seed": SEED, "rows": len(queue), "by_head": dict(Counter(q["head"] for q in queue)),
              "by_split": dict(Counter(q["split"] for q in queue)), "plan": summary}
    json.dump(report, open(f"{OUT}/queue_summary.json", "w"), indent=2)
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
