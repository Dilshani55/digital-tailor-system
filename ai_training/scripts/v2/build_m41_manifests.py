"""M41 manifests = the unchanged M40 manifests + DeepFashion-MultiModal (DMM) records with detector crops.

* M40 train / val records are copied as they are; M40 test files (test, test_df2, test_fp, bench60) are copied
  byte-identical (verified by sha256) so M41 and M40 are compared on exactly the same images.
* DMM records (ai_training/datasets/deepfashion_multimodal/annotations, cropped by crop_with_detector.py):
    - `candidate_dmm_lapel_needs_human_review` (collared-neck) is MASKED entirely - not trusted until reviewed;
    - garment type from `dmm_shop_category` / `dmm_navel_uncovered` is kept but down-weighted in the config
      (proxies, not human garment-type labels);
    - no detector box -> crop_path = the whole photo (what the app would classify).
* Leakage control (dHash, Hamming <= 4, whole photo): DMM train/val records whose photo near-duplicates ANY photo
  in the M40 test files are dropped; DMM test records with a near-duplicate in DMM train are dropped.
  DMM test is written separately as test_dmm.jsonl (never merged into test_all).

    backend\\venv\\Scripts\\python ai_training\\scripts\\v2\\build_m41_manifests.py
"""
import hashlib
import json
import os
import shutil
import sys
from collections import Counter

from PIL import Image, ImageOps

sys.path.insert(0, ".")
from ai_training.training import labels15 as L  # noqa: E402

M40 = "ai_training/data/manifests_m40"
OUT = "ai_training/data/manifests_m41"
DMM = "ai_training/datasets/deepfashion_multimodal/annotations"
CLASSES = L.load_classes("ai_training/config/classes_v2_15class.json")
TESTS = ["test.jsonl", "test_df2.jsonl", "test_fp.jsonl", "bench60.jsonl"]
CANDIDATE = "candidate_dmm_lapel_needs_human_review"
PROXY = {"dmm_shop_category", "dmm_navel_uncovered"}


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def dhash(path, size=8):
    with Image.open(path) as im:
        g = ImageOps.exif_transpose(im).convert("L").resize((size + 1, size), Image.Resampling.LANCZOS)
    px = list(g.getdata())
    v = 0
    for r in range(size):
        for c in range(size):
            v = (v << 1) | (px[r * (size + 1) + c] > px[r * (size + 1) + c + 1])
    return v


def photo(rec):
    for k in ("full_image_path", "source_image_path"):
        p = rec.get(k)
        if p and os.path.exists(p.replace("\\", "/")):
            return p.replace("\\", "/")
    return None


def near(h, pool, t=4):
    return any(bin(h ^ q).count("1") <= t for q in pool)


def prepare(rec):
    r = json.loads(json.dumps(rec))
    for h in L.HEADS:
        if r["provenance"].get(h) == CANDIDATE:
            r["masked_candidate"] = {h: r["labels"][h]}
            r["labels"][h], r["masks"][h], r["provenance"][h] = None, 0, L.MASKED_PROVENANCE
    if not r.get("crop_path"):
        r["crop_path"] = r["full_image_path"]          # whole photo, exactly what the app would classify
    r["class_indices"] = {h: (CLASSES[h].index(r["labels"][h]) if r["labels"][h] is not None else None) for h in L.HEADS}
    r["trusted"] = {h: bool(r["masks"][h] and r["provenance"][h] not in PROXY | {L.MASKED_PROVENANCE}) for h in L.HEADS}
    return r


def main():
    os.makedirs(OUT, exist_ok=True)
    report = {"copied_identical": {}, "dropped": Counter()}
    for t in TESTS:
        shutil.copyfile(f"{M40}/{t}", f"{OUT}/{t}")
        assert sha(f"{M40}/{t}") == sha(f"{OUT}/{t}")
        report["copied_identical"][t] = sha(f"{OUT}/{t}")[:16]

    test_hashes = []
    for t in TESTS:
        for r in L.load_jsonl(f"{M40}/{t}"):
            p = photo(r)
            if p:
                test_hashes.append(dhash(p))
    print("test photos hashed:", len(test_hashes), flush=True)

    dmm = {s: [prepare(r) for r in L.load_jsonl(f"{DMM}/{s}.jsonl")] for s in L.SPLITS}
    kept = {}
    train_h = []
    for s in ("train", "val"):
        kept[s] = []
        for r in dmm[s]:
            h = dhash(r["full_image_path"])
            if near(h, test_hashes):
                report["dropped"][f"dmm_{s}_near_duplicate_of_m40_test"] += 1
                continue
            if s == "train":
                train_h.append(h)
            kept[s].append(r)
        print(s, "kept", len(kept[s]), flush=True)
    kept["test"] = []
    for r in dmm["test"]:
        h = dhash(r["full_image_path"])
        if near(h, train_h):
            report["dropped"]["dmm_test_near_duplicate_of_dmm_train"] += 1
            continue
        kept["test"].append(r)
    keep = lambda r: any(r["masks"].get(h) == 1 for h in L.HEADS)  # noqa: E731

    def dump(name, recs):
        with open(f"{OUT}/{name}", "w", encoding="utf-8") as f:
            for r in recs:
                f.write(json.dumps(r) + "\n")

    for s in ("train", "val"):
        dump(f"{s}.jsonl", L.load_jsonl(f"{M40}/{s}.jsonl") + [r for r in kept[s] if keep(r)])
    dump("test_dmm.jsonl", [r for r in kept["test"] if keep(r)])

    counts = {}
    for name in ("train.jsonl", "val.jsonl", "test_dmm.jsonl"):
        recs = L.load_jsonl(f"{OUT}/{name}")
        counts[name] = {"records": len(recs), "by_source": dict(Counter(r.get("source_dataset", "fashionpedia") for r in recs)),
                        "per_head": {h: dict(Counter(f"{r['labels'][h]} [{r['provenance'][h]}]" for r in recs if r["masks"].get(h) == 1))
                                     for h in L.HEADS}}
    report["dropped"] = dict(report["dropped"])
    json.dump({"report": report, "counts": counts}, open(f"{OUT}/counts.json", "w"), indent=2)
    print(json.dumps(report, indent=1))
    for n, c in counts.items():
        print(n, c["records"], c["by_source"])


if __name__ == "__main__":
    main()
