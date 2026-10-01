"""Read-only audit of the training data as it is on this machine (Fashionpedia, DeepFashion2, DeepFashion-MultiModal).

It answers, from the manifests the trainer really reads (ai_training/data/manifests_m41):
  1. paths      - do the dataset folders and every image a manifest names exist?
  2. counts     - per head and class: train / val / test examples, split by how far the label can be trusted
                    trusted   : a person labelled this attribute (or "none" follows from an explicit sleeveless label)
                    proxy     : a shop category or a rule stands in for the label (not a human label of this head)
                    candidate : only a rule suggests the class; masked until a person reviews it
  3. mapping    - is every label inside its head's class list, are class indices and masks consistent, does the
                  DeepFashion2 / DMM source value really map to the stored label, do proxy garment types
                  contradict the drafting scope (for example a sleeveless "t-shirt")?
  4. leakage    - the same source photo or DMM garment item in two splits; byte-identical photos; near-identical
                  photos (dHash, Hamming <= 4) between training and each validation / test set.

Nothing is changed. Results: --out/dataset_audit.json and dataset_audit.md (the folder `evidence/` is git-ignored).

    backend\\venv\\Scripts\\python ai_training\\scripts\\v2\\audit_datasets.py --out evidence/ai_data_audit
    (add --no-near-duplicates to skip the slow image hashing)
"""
import argparse
import hashlib
import json
import os
import re
import sys
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor

sys.path.insert(0, ".")
from ai_training.training import labels15 as L  # noqa: E402

MANIFESTS = os.environ.get("AUDIT_MANIFESTS", "ai_training/data/manifests_m41")
CLASSES_FILE = "ai_training/config/classes_v2_15class.json"
SCOPE_FILE = "config/garment_scope.json"
DMM_ANNOTATIONS = "ai_training/datasets/deepfashion_multimodal/annotations"
DMM_SHAPE = "ai_training/datasets/deepfashion_multimodal/raw/labels/labels/shape/shape_anno_all.txt"
HASH_CACHE = "ai_training/data/audits/image_hashes.json"

DATASETS = {
    "fashionpedia": {"folder": "ai_training/data/raw/fashionpedia", "licence": "CC BY 4.0 (annotations); images under their original Flickr-style licences"},
    "deepfashion2": {"folder": "ai_training/datasets/archive/DeepFashion2", "licence": "non-commercial research only"},
    "deepfashion2 (prepared tops)": {"folder": "ai_training/datasets/deepfashion2_tops", "licence": "derived from DeepFashion2"},
    "deepfashion_multimodal": {"folder": "ai_training/datasets/deepfashion_multimodal", "licence": "non-commercial research only"},
}
FILES = {"train": "train.jsonl", "val": "val.jsonl", "test_all": "test.jsonl", "test_dmm": "test_dmm.jsonl", "bench60": "bench60.jsonl"}
TRUSTED = {"human_verified", "fashionpedia_direct", "df2_human_category", "dmm_human_shape", "derived_from_explicit_sleeveless"}
PROXY = {"dmm_shop_category", "dmm_navel_uncovered", "accepted_pseudo_label"}
CANDIDATE_DMM = "candidate_dmm_lapel_needs_human_review"
DF2_SLEEVE = {"short_sleeved_shirt": "short-sleeve", "long_sleeved_shirt": "long-sleeve", "vest": "sleeveless", "sling": "sleeveless"}
DMM_SLEEVE = {0: "sleeveless", 1: "short-sleeve", 3: "long-sleeve"}
DMM_NECK = {0: "v-neck", 1: "square-neck", 2: "round-neck"}
DMM_CATS = {"Blouses_Shirts": "blouse", "Tees_Tanks": "t-shirt", "Graphic_Tees": "t-shirt"}
DMM_NAME = re.compile(r"^dmm:(WOMEN|MEN)-([A-Za-z_]+)-(id_\d+)-(\d+)_(\d+)_([a-z]+)$")
NEAR = 4


def source_of(rec):
    return rec.get("source_dataset") or ("deepfashion2" if str(rec.get("record_uid", "")).startswith("df2:") else "fashionpedia")


def photo_of(rec):
    """The whole photo a record comes from (what the app would receive)."""
    for key in ("full_image_path", "source_image_path", "crop_path"):
        p = rec.get(key)
        if p:
            return p.replace("\\", "/")
    return None


def photo_identity(rec):
    """One id per source photo. DeepFashion2 numbers its train and validation folders separately, so the bare
    id ("df2:023609") names two different photos; the folder is taken from the path."""
    uid = rec.get("source_image_uid")
    if source_of(rec) == "deepfashion2":
        p = photo_of(rec) or ""
        folder = "train" if "/train/" in p else "val" if "/val/" in p else "test" if "/test/" in p else "?"
        return f"{uid}@{folder}"
    return uid


def tier(provenance):
    return "trusted" if provenance in TRUSTED else "proxy" if provenance in PROXY else "other"


# ── image hashes (cached; computed in parallel) ───────────────────────────────
def _hash_one(path):
    try:
        from PIL import Image, ImageOps
        with open(path, "rb") as f:
            sha = hashlib.sha256(f.read()).hexdigest()
        with Image.open(path) as im:
            g = ImageOps.exif_transpose(im).convert("L").resize((9, 8), Image.Resampling.LANCZOS)
        px = list(g.getdata())
        v = 0
        for r in range(8):
            for c in range(8):
                v = (v << 1) | (px[r * 9 + c] > px[r * 9 + c + 1])
        st = os.stat(path)
        return path, {"sha256": sha, "dhash": v, "size": st.st_size, "mtime": int(st.st_mtime)}
    except Exception as exc:                                     # unreadable image: reported, not hidden
        return path, {"error": f"{type(exc).__name__}: {exc}"}


def image_hashes(paths, workers):
    cache = {}
    if os.path.exists(HASH_CACHE):
        cache = json.load(open(HASH_CACHE, encoding="utf-8"))
    todo = []
    for p in paths:
        c = cache.get(p)
        if c and "error" not in c and os.path.exists(p):
            st = os.stat(p)
            if c.get("size") == st.st_size and c.get("mtime") == int(st.st_mtime):
                continue
        if os.path.exists(p):
            todo.append(p)
    if todo:
        print(f"hashing {len(todo)} images ({len(paths) - len(todo)} cached) ...", flush=True)
        with ProcessPoolExecutor(max_workers=workers) as pool:
            for i, (p, h) in enumerate(pool.map(_hash_one, todo, chunksize=64), 1):
                cache[p] = h
                if i % 5000 == 0:
                    print(f"  {i}/{len(todo)}", flush=True)
        os.makedirs(os.path.dirname(HASH_CACHE), exist_ok=True)
        json.dump(cache, open(HASH_CACHE, "w", encoding="utf-8"))
    return cache


def near_duplicates(test_hashes, train_hashes):
    """For each test dHash: index of a training dHash within Hamming distance NEAR, or -1."""
    import numpy as np
    train = np.array(train_hashes, dtype=np.uint64)
    out = []
    counter = np.bitwise_count if hasattr(np, "bitwise_count") else None
    for h in test_hashes:
        x = np.bitwise_xor(train, np.uint64(h))
        if counter is not None:
            d = counter(x)
        else:
            d = np.unpackbits(x.view(np.uint8).reshape(-1, 8), axis=1).sum(axis=1)
        j = int(d.argmin())
        out.append(j if int(d[j]) <= NEAR else -1)
    return out


# ── the audit ─────────────────────────────────────────────────────────────────
def audit(with_hashes=True, workers=4):
    classes = L.load_classes(CLASSES_FILE)
    scope = json.load(open(SCOPE_FILE, encoding="utf-8"))["scope"]
    sets = {name: L.load_jsonl(f"{MANIFESTS}/{f}") for name, f in FILES.items()}
    report = {"manifests": MANIFESTS, "sets": {n: len(r) for n, r in sets.items()}}

    # 1. paths
    paths = {}
    for name, d in DATASETS.items():
        ok = os.path.isdir(d["folder"])
        paths[name] = {"folder": d["folder"], "exists": ok, "licence": d["licence"]}
    missing = Counter()
    by_source = {n: Counter(source_of(r) for r in recs) for n, recs in sets.items()}
    for n, recs in sets.items():
        for r in recs:
            for key in ("crop_path", "full_image_path", "source_image_path"):
                p = r.get(key)
                if p and not os.path.exists(p.replace("\\", "/")):
                    missing[f"{n}: {source_of(r)} {key}"] += 1
    report["paths"] = {"datasets": paths, "records_by_source": {n: dict(c) for n, c in by_source.items()},
                       "manifest_files_missing_on_disk": dict(missing)}

    # 2. counts per head / class / tier
    counts = {h: {c: defaultdict(lambda: Counter()) for c in classes[h]} for h in L.HEADS}
    for n, recs in sets.items():
        for r in recs:
            for h in L.HEADS:
                if r["masks"].get(h) == 1 and r["labels"].get(h) in counts[h]:
                    counts[h][r["labels"][h]][n][f"{tier(r['provenance'][h])}:{source_of(r)}"] += 1
    table = {}
    for h in L.HEADS:
        table[h] = {}
        for c in classes[h]:
            row = {}
            for n in FILES:
                cell = counts[h][c][n]
                row[n] = {"trusted": sum(v for k, v in cell.items() if k.startswith("trusted:")),
                          "proxy": sum(v for k, v in cell.items() if k.startswith("proxy:")),
                          "by_tier_and_source": dict(cell)}
            table[h][c] = row
    report["counts"] = table

    # candidates that are masked today (need a person)
    candidates = Counter()
    for n in ("train", "val", "test_all"):
        for r in sets[n]:
            for w in r.get("weak_label_details") or []:
                candidates[f"{w['head']}={w['label']} [fashionpedia rule: {w.get('evidence')}] {n}"] += 1
    for split in ("train", "val", "test"):
        f = f"{DMM_ANNOTATIONS}/{split}.jsonl"
        if os.path.exists(f):
            for r in L.load_jsonl(f):
                if r["provenance"].get("neckline_type") == CANDIDATE_DMM:
                    candidates[f"neckline_type=collared-neck [dmm lapel] {split}"] += 1
    report["masked_candidates_needing_review"] = dict(sorted(candidates.items()))

    # 3. mapping / consistency
    problems = Counter()
    examples = defaultdict(list)

    def flag(kind, rec):
        problems[kind] += 1
        if len(examples[kind]) < 5:
            examples[kind].append(rec["record_uid"])

    dmm_raw = {}
    if os.path.exists(DMM_SHAPE):
        for line in open(DMM_SHAPE, encoding="utf-8"):
            parts = line.split()
            dmm_raw["dmm:" + parts[0][:-4]] = [int(x) for x in parts[1:]]
    cross = Counter()
    notes = Counter()
    seen_uid = {}
    for n, recs in sets.items():
        for r in recs:
            if n in ("train", "val") and r.get("split") != n:
                flag("record split field differs from its file", r)
            if n in ("train", "val", "test_all", "test_dmm"):
                where = "test" if n.startswith("test") else n
                if r["record_uid"] in seen_uid and seen_uid[r["record_uid"]] != where:
                    flag("same record in two splits", r)
                seen_uid[r["record_uid"]] = where
            for h in L.HEADS:
                lab, mask = r["labels"].get(h), r["masks"].get(h)
                if (mask == 1) != (lab is not None):
                    flag("mask and label disagree", r)
                if lab is not None and lab not in classes[h]:
                    flag("label outside the head's class list", r)
                idx = (r.get("class_indices") or {}).get(h)
                if lab is not None and idx is not None and classes[h][idx] != lab:
                    flag("class index does not match the label", r)
                if mask == 1 and r["provenance"].get(h) in (L.MASKED_PROVENANCE, L.REMOVED_PROVENANCE, CANDIDATE_DMM):
                    flag("a masked / candidate provenance is used as a label", r)
            sl, st = r["labels"].get("sleeve_length"), r["labels"].get("sleeve_style")
            if st == "none" and sl != "sleeveless":
                flag("sleeve style 'none' without sleeve length 'sleeveless'", r)
            if sl == "sleeveless" and st not in (None, "none"):
                flag("sleeveless with a sleeve style other than 'none'", r)
            src = source_of(r)
            if src == "deepfashion2" and r.get("df2_category"):
                if DF2_SLEEVE.get(r["df2_category"]) != sl:
                    flag("DeepFashion2 category does not map to the stored sleeve length", r)
            if src == "deepfashion_multimodal" and dmm_raw:
                raw = dmm_raw.get(r["record_uid"])
                m = DMM_NAME.match(r["record_uid"])
                if raw is None or not m:
                    flag("DMM record not found in the source label file", r)
                else:
                    if sl != DMM_SLEEVE.get(raw[0]):
                        flag("DMM sleeve value does not map to the stored sleeve length", r)
                    neck = r["labels"].get("neckline_type")
                    want = DMM_NECK.get(raw[9]) if m.group(5) != "3" else None
                    if neck != want and r["provenance"].get("neckline_type") != "human_verified":   # a person's review overrides the source value
                        flag("DMM neckline value does not map to the stored neckline", r)
                    garment = "crop-top" if raw[11] == 0 else DMM_CATS.get(m.group(2))
                    deliberately_masked = bool((r.get("masked_reason") or {}).get("garment_type"))
                    if r["labels"].get("garment_type") != garment and not deliberately_masked:
                        flag("DMM category / navel value does not map to the stored garment type", r)
            g = r["labels"].get("garment_type")
            if g and sl:
                cross[f"{g} + {sl} [{tier(r['provenance']['garment_type'])}:{src}]"] += 1
                if g == "t-shirt" and sl == "sleeveless" and r["provenance"]["garment_type"] in PROXY:
                    flag("tank top labelled t-shirt (tee shop category + sleeveless human label)", r)
                elif sl not in scope[g]["sleeves"]:
                    # a real garment (a sleeveless blouse, a long-sleeved crop top) that the engine cannot draft:
                    # the label is not wrong, so this is information, not a problem
                    notes[f"{g} + {sl} is outside the drafting scope ({r['provenance']['garment_type']})"] += 1
    report["mapping"] = {"problems": dict(sorted(problems.items())), "examples": dict(examples),
                         "outside_drafting_scope_but_correctly_labelled": dict(sorted(notes.items())),
                         "garment_type_by_sleeve_length": dict(sorted(cross.items()))}

    # 4. leakage
    leak = {}
    train_uids = {photo_identity(r) for r in sets["train"]}
    train_groups = {r.get("group_id") for r in sets["train"] if r.get("group_id")}
    for n in ("val", "test_all", "test_dmm", "bench60"):
        leak[n] = {
            "same_source_photo_as_training": sum(1 for r in sets[n] if photo_identity(r) in train_uids),
            "same_dmm_garment_item_as_training": sum(1 for r in sets[n] if r.get("group_id") and r["group_id"] in train_groups),
        }
    val_uids = {photo_identity(r) for r in sets["val"]}
    val_groups = {r.get("group_id") for r in sets["val"] if r.get("group_id")}
    for n in ("test_all", "test_dmm", "bench60"):
        leak[n]["same_source_photo_as_validation"] = sum(1 for r in sets[n] if photo_identity(r) in val_uids)
        leak[n]["same_dmm_garment_item_as_validation"] = sum(1 for r in sets[n] if r.get("group_id") and r["group_id"] in val_groups)
    bench_uids = {photo_identity(r) for r in sets["bench60"]}
    leak["bench60"]["records_also_in_test_all"] = sum(1 for r in sets["test_all"] if photo_identity(r) in bench_uids)
    ids = Counter()
    for n in ("train", "val", "test_all"):
        for uid in {r.get("source_image_uid") for r in sets[n] if source_of(r) == "deepfashion2"}:
            ids[uid] += 1
    leak["deepfashion2_ids_reused_for_different_photos"] = sum(1 for v in ids.values() if v > 1)

    if with_hashes:
        photos = {n: [photo_of(r) for r in recs] for n, recs in sets.items()}
        hashes = image_hashes(sorted({p for ps in photos.values() for p in ps if p}), workers)
        unreadable = {p: h["error"] for p, h in hashes.items() if "error" in h}
        train_ok = [(p, hashes[p]) for p in dict.fromkeys(photos["train"]) if p in hashes and "error" not in hashes[p]]
        train_sha = {h["sha256"] for _, h in train_ok}
        train_dh = [h["dhash"] for _, h in train_ok]
        for n in ("val", "test_all", "test_dmm", "bench60"):
            uniq = [p for p in dict.fromkeys(photos[n]) if p in hashes and "error" not in hashes[p]]
            hit = near_duplicates([hashes[p]["dhash"] for p in uniq], train_dh)
            pairs = [(p, train_ok[j][0]) for p, j in zip(uniq, hit) if j >= 0]
            by_pair = Counter()
            for a, b in pairs:
                by_pair[f"{_src(a)} ~ train {_src(b)}"] += 1
            if n != "val":                                        # thresholds are chosen on validation: it must not see test photos
                val_ok = [p for p in dict.fromkeys(photos["val"]) if p in hashes and "error" not in hashes[p]]
                vhit = near_duplicates([hashes[p]["dhash"] for p in uniq], [hashes[p]["dhash"] for p in val_ok])
                leak[n][f"near_identical_to_a_validation_photo_dhash_le_{NEAR}"] = sum(1 for j in vhit if j >= 0)
            leak[n].update({
                "photos": len(uniq),
                "byte_identical_to_a_training_photo": sum(1 for p in uniq if hashes[p]["sha256"] in train_sha),
                f"near_identical_to_a_training_photo_dhash_le_{NEAR}": len(pairs),
                "near_identical_by_source": dict(by_pair),
                "near_identical_examples": pairs[:5],
            })
        leak["unreadable_images"] = unreadable
    report["leakage"] = leak
    return report


def _src(path):
    return "dmm" if "deepfashion_multimodal" in path else "df2" if "deepfashion2" in path else "fashionpedia"


def markdown(report):
    out = ["# Dataset audit", "", f"Manifests: `{report['manifests']}`. Records: " +
           ", ".join(f"{n} {v}" for n, v in report["sets"].items()) + ".", "",
           "## Per head and class (trusted labels / proxy labels)", "",
           "| Head | Class | Train | Val | Test (test_all) | Test (test_dmm) | Benchmark |", "|---|---|---:|---:|---:|---:|---:|"]
    for h, classes in report["counts"].items():
        for c, row in classes.items():
            cells = []
            for n in FILES:
                t, p = row[n]["trusted"], row[n]["proxy"]
                cells.append(f"{t}" + (f" (+{p} proxy)" if p else ""))
            out.append(f"| {h} | {c} | " + " | ".join(cells) + " |")
    out += ["", "## Masked candidates that need a person", ""]
    out += [f"* {k}: {v}" for k, v in report["masked_candidates_needing_review"].items()] or ["* none"]
    out += ["", "## Mapping and consistency problems", ""]
    out += [f"* {k}: {v}" for k, v in report["mapping"]["problems"].items()] or ["* none found"]
    out += ["", "Correct labels of garments the engine cannot draft (information only):", ""]
    out += [f"* {k}: {v}" for k, v in report["mapping"]["outside_drafting_scope_but_correctly_labelled"].items()] or ["* none"]
    out += ["", "## Leakage checks", ""]
    for n, d in report["leakage"].items():
        if n == "unreadable_images":
            out.append(f"* unreadable images: {len(d)}")
            continue
        if not isinstance(d, dict):
            out.append(f"* {n}: {d}")
            continue
        out.append(f"* **{n}**: " + "; ".join(f"{k} = {v}" for k, v in d.items() if not k.endswith("examples")))
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="evidence/ai_data_audit")
    ap.add_argument("--no-near-duplicates", action="store_true")
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    report = audit(with_hashes=not a.no_near_duplicates, workers=a.workers)
    os.makedirs(a.out, exist_ok=True)
    json.dump(report, open(f"{a.out}/dataset_audit.json", "w", encoding="utf-8"), indent=2)
    md = markdown(report)
    open(f"{a.out}/dataset_audit.md", "w", encoding="utf-8").write(md)
    print(md)


if __name__ == "__main__":
    main()
