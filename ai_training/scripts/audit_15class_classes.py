"""
Per-class audit of the 15-class (3/5/3/4) taxonomy.

For every head/class: raw labelled count, trusted train/val/test counts (from the 15-class manifests,
after masking and near-duplicate exclusion), locked-benchmark count, label provenance in the training
split, and an upper bound of what explicit Fashionpedia evidence exists at all for tops/blouses.

Reads (all local, not in Git):
  ai_training/data/manifests_15class/{counts.json,train.jsonl}   (build_15class_manifests.py)
  ai_training/data/eval_real_product_set/eval_manifest.jsonl       (locked 60-image benchmark)
  ai_training/data/raw/fashionpedia/instances_attributes_{train,val}2020.json  (optional)
Writes ai_training/data/audits/class_audit_15.json and prints a Markdown table.

    $env:PYTHONPATH="."; backend\\venv\\Scripts\\python ai_training\\scripts\\audit_15class_classes.py
"""
import collections
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATA = os.path.join(ROOT, "ai_training", "data")
MANIFESTS = os.path.join(DATA, "manifests_15class")
BENCH = os.path.join(DATA, "eval_real_product_set", "eval_manifest.jsonl")
RAW = os.path.join(DATA, "raw", "fashionpedia")
OUT = os.path.join(DATA, "audits", "class_audit_15.json")

# Explicit Fashionpedia part attributes that directly name a class (fashionpedia_mapping.json, status "direct").
DIRECT_PART_ATTRIBUTES = {("sleeve_length", "sleeveless"): 156, ("sleeve_style", "puff-sleeve"): 209,
                          ("sleeve_style", "bell-sleeve"): 210, ("neckline_type", "square-neck"): 191,
                          ("neckline_type", "off-shoulder"): 202}
TOPS = {"shirt, blouse", "top, t-shirt, sweatshirt"}
OTHER_UPPER = {"dress", "jumpsuit", "jacket", "coat", "cardigan", "vest", "sweater", "cape"}

RISKS = {
    ("garment_type", "blouse"): "Fashionpedia merges blouses with button-down shirts; only 87 trusted (human-verified) train labels.",
    ("neckline_type", "collared-neck"): "Only a candidate rule (a collar part is present); no trusted label in any split; not in the benchmark.",
    ("neckline_type", "square-neck"): "Explicit attribute exists, but the pool of tops/blouses is exhausted; not in the benchmark.",
    ("neckline_type", "off-shoulder"): "Pool of tops/blouses exhausted.",
    ("sleeve_length", "sleeveless"): "Very rare on tops in Fashionpedia (upper bound ~61 images); not in the benchmark.",
    ("sleeve_style", "none"): "Only derivable from an explicit sleeveless label, so limited like sleeveless; not in the benchmark.",
    ("sleeve_style", "regular-sleeve"): "Only a candidate rule ('set-in sleeve' is a construction, not a style); no trusted label; not in the benchmark.",
    ("sleeve_style", "puff-sleeve"): "Pool of tops/blouses exhausted.",
    ("sleeve_style", "bell-sleeve"): "Pool of tops/blouses exhausted; below targets in every split.",
}


def _jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def raw_upper_bounds():
    """Images in which the attribute occurs together with a top/blouse and no other upper garment."""
    out = collections.Counter()
    for split in ("train2020", "val2020"):
        path = os.path.join(RAW, f"instances_attributes_{split}.json")
        if not os.path.exists(path):
            return None
        d = json.load(open(path, encoding="utf-8"))
        cats = {c["id"]: c["name"] for c in d["categories"]}
        imgs = collections.defaultdict(lambda: [0, 0, set()])
        for a in d["annotations"]:
            c = cats[a["category_id"]]
            im = imgs[a["image_id"]]
            im[0] += c in TOPS
            im[1] += c in OTHER_UPPER
            im[2].update(a.get("attribute_ids", []))
        for key, aid in DIRECT_PART_ATTRIBUTES.items():
            out[key] += sum(1 for tops, other, attrs in imgs.values() if tops and not other and aid in attrs)
    return out


def sleeveless_recovery_candidates(used_uids):
    """
    Tops/blouses with an EXPLICIT 'sleeveless' attribute (156) where the image holds exactly one top and no
    other upper garment, so the part belongs to that top without guessing. Records already in the manifests
    are skipped. Output rows carry provenance for a later, reviewed manifest rebuild (nothing is added here).
    """
    out = []
    for split in ("train2020", "val2020"):
        path = os.path.join(RAW, f"instances_attributes_{split}.json")
        if not os.path.exists(path):
            return []
        d = json.load(open(path, encoding="utf-8"))
        cats = {c["id"]: c["name"] for c in d["categories"]}
        files = {i["id"]: i["file_name"] for i in d["images"]}
        per = collections.defaultdict(lambda: {"tops": [], "other": 0, "sleeveless_parts": []})
        for a in d["annotations"]:
            c = cats[a["category_id"]]
            im = per[a["image_id"]]
            if c in TOPS:
                im["tops"].append(a)
            elif c in OTHER_UPPER:
                im["other"] += 1
            if 156 in a.get("attribute_ids", []):
                im["sleeveless_parts"].append(a["id"])
        for iid, im in per.items():
            if len(im["tops"]) != 1 or im["other"] or not im["sleeveless_parts"]:
                continue
            top = im["tops"][0]
            uid = f"fashionpedia:{split}:{top['id']}"
            if uid in used_uids:
                continue
            out.append({"source_record_uid": uid, "image_file": files[iid], "garment_category": cats[top["category_id"]],
                        "garment_bbox": top["bbox"], "evidence_annotation_ids": im["sleeveless_parts"],
                        "labels": {"sleeve_length": "sleeveless", "sleeve_style": "none"},
                        "provenance": {"sleeve_length": "fashionpedia_direct",
                                       "sleeve_style": "derived_from_explicit_sleeveless"},
                        "note": "single top, no other upper garment; split must follow the source image and a "
                                "near-duplicate check must pass before use"})
    return out


def main():
    counts = json.load(open(os.path.join(MANIFESTS, "counts.json"), encoding="utf-8"))
    classes = counts["classes"]
    c = counts["counts"]

    prov = collections.defaultdict(collections.Counter)
    for rec in _jsonl(os.path.join(MANIFESTS, "train.jsonl")):
        for head, label in (rec.get("labels") or {}).items():
            if label and (rec.get("masks") or {}).get(head, 1):
                prov[(head, label)][(rec.get("provenance") or {}).get(head, "unknown")] += 1

    bench = collections.Counter()
    for rec in _jsonl(BENCH):
        for head, label in rec["labels"].items():
            if label and rec.get("masks", {}).get(head, 1):
                bench[(head, label)] += 1

    used = set()
    for split in ("train", "val", "test"):
        for rec in _jsonl(os.path.join(MANIFESTS, f"{split}.jsonl")):
            for key in ("source_record_uid", "original_record_uid", "record_uid", "uid"):
                if rec.get(key):
                    used.add(rec[key])
    recovery = sleeveless_recovery_candidates(used)
    if recovery:
        with open(os.path.join(DATA, "audits", "sleeveless_recovery_candidates.jsonl"), "w", encoding="utf-8") as f:
            for row in recovery:
                f.write(json.dumps(row) + "\n")

    upper = raw_upper_bounds()
    rows = []
    for head, values in classes.items():
        for cls in values:
            tr, va, te = c["train"][head][cls], c["val"][head][cls], c["test"][head][cls]
            rows.append({
                "head": head, "class": cls,
                "raw_count": tr["total"] + va["total"] + te["total"],
                "trusted_train": tr["trusted"], "val": va["trusted"], "test": te["trusted"],
                "locked_benchmark": bench.get((head, cls), 0),
                "train_provenance": dict(prov.get((head, cls), {})),
                "raw_fashionpedia_upper_bound": (upper or {}).get((head, cls)) if (head, cls) in DIRECT_PART_ATTRIBUTES else None,
                "known_risks": RISKS.get((head, cls), ""),
            })

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    result = {"verdict": counts["readiness"]["verdict"], "targets": counts["readiness"]["targets"],
              "manifest_sha256": counts["manifest_sha256"], "rows": rows}
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    print("| Head | Class | Raw count | Trusted train | Val | Test | Locked benchmark | Train label provenance | Raw Fashionpedia upper bound | Known risks |")
    print("|---|---|---:|---:|---:|---:|---:|---|---:|---|")
    for r in rows:
        pv = ", ".join(f"{k} {v}" for k, v in sorted(r["train_provenance"].items())) or "—"
        ub = "" if r["raw_fashionpedia_upper_bound"] is None else r["raw_fashionpedia_upper_bound"]
        print(f"| {r['head']} | {r['class']} | {r['raw_count']} | {r['trusted_train']} | {r['val']} | {r['test']} | "
              f"{r['locked_benchmark']} | {pv} | {ub} | {r['known_risks']} |")
    print(f"\nVERDICT: {result['verdict']}  (targets per class: {result['targets']})")
    print(f"Explicit sleeveless evidence not yet in the manifests (unambiguous single tops): {len(recovery)} "
          f"-> ai_training/data/audits/sleeveless_recovery_candidates.jsonl")
    return 0


if __name__ == "__main__":
    sys.exit(main())
