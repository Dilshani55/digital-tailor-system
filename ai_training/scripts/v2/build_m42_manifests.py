"""M42 manifests = the M41 manifests with the audit's fixes and the human-reviewed labels.

1. The M40 test files (test, test_df2, test_fp, bench60) are copied byte-identical (sha256 checked), so M42 is
   compared with M40 on exactly the same images.
2. Mapping fix: a DeepFashion-MultiModal record whose shop category is a tee but whose human sleeve label is
   "sleeveless" is a tank top, not a T-shirt (class definition: T-shirt = knit tee with sleeves). Its garment
   type is MASKED (not relabelled). The same rule is applied to train, val and test_dmm.
3. Reviewed labels (decisions.jsonl from tools/review_labels.py): an answer that is one of the head's classes
   becomes a label with provenance `human_verified` on the record of the same photo, in the split the photo
   already has. "other" / "unclear" add nothing. Test-split answers go to a NEW file, test_reviewed.jsonl
   (only the reviewed head is labelled there); the frozen test files are never touched.
   An answer that contradicts a trusted label of the same record (for example sleeve style "none" on a garment
   whose sleeve length is "short-sleeve") is not applied and is listed under `conflicts`.
4. Leakage: training records whose photo is near-identical (dHash, Hamming <= 4) to any test photo are dropped;
   validation records near-identical to a training or test photo are dropped (thresholds are chosen on validation).

    backend\\venv\\Scripts\\python ai_training\\scripts\\v2\\build_m42_manifests.py [--decisions <decisions.jsonl>]
Output: ai_training/data/manifests_m42/ (+ counts.json with everything that was changed). Local, git-ignored.
"""
import argparse
import hashlib
import json
import os
import shutil
import sys
from collections import Counter

sys.path.insert(0, ".")
from ai_training.training import labels15 as L  # noqa: E402
from ai_training.scripts.v2 import audit_datasets as audit  # noqa: E402

M41 = "ai_training/data/manifests_m41"
OUT = "ai_training/data/manifests_m42"
QUEUE = "ai_training/data/label_queue_m42/queue.jsonl"
CLASSES_FILE = "ai_training/config/classes_v2_15class.json"
FROZEN_TESTS = ["test.jsonl", "test_df2.jsonl", "test_fp.jsonl", "bench60.jsonl"]
PROXY = {"dmm_shop_category", "dmm_navel_uncovered"}
REVIEWED = "human_verified"
TANK_REASON = "tee shop category with a sleeveless human label = tank top, not a T-shirt"


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def finish(rec, classes):
    """Recompute the derived fields after a label change."""
    rec["class_indices"] = {h: (classes[h].index(rec["labels"][h]) if rec["labels"].get(h) is not None else None) for h in L.HEADS}
    rec["trusted"] = {h: bool(rec["masks"].get(h) and rec["provenance"].get(h) not in PROXY | {L.MASKED_PROVENANCE}) for h in L.HEADS}
    return rec


def mask_tank_tops(records, classes):
    """Fix 2. Returns the number of garment-type labels masked."""
    n = 0
    for r in records:
        if (r["labels"].get("garment_type") == "t-shirt" and r["provenance"].get("garment_type") == "dmm_shop_category"
                and r["labels"].get("sleeve_length") == "sleeveless"):
            r["labels"]["garment_type"], r["masks"]["garment_type"] = None, 0
            r["provenance"]["garment_type"] = L.MASKED_PROVENANCE
            r["masked_reason"] = dict(r.get("masked_reason") or {}, garment_type=TANK_REASON)
            finish(r, classes)
            n += 1
    return n


def blank_record(q, classes):
    """A record for a reviewed photo that no manifest holds yet (every head masked until the answer is applied)."""
    r = {"record_uid": q.get("record_uid") or f"fashionpedia:reviewed:{q['source_annotation_id']}",
         "source_dataset": q["source"], "source_image_uid": q.get("source_image_uid"), "split": q["split"],
         "labels": {h: None for h in L.HEADS}, "masks": {h: 0 for h in L.HEADS},
         "provenance": {h: L.MASKED_PROVENANCE for h in L.HEADS}}
    if q.get("bbox_xywh"):
        r.update(source_image_path=q["image_path"], crop_path=None, bbox=q["bbox_xywh"], source_annotation_id=q.get("source_annotation_id"))
    else:
        r.update(crop_path=q["image_path"], full_image_path=q.get("full_image_path") or q["image_path"], bbox=None)
    return finish(r, classes)


def find_record(q, records):
    if q.get("record_uid"):
        return next((r for r in records if r["record_uid"] == q["record_uid"]), None)
    ann = q.get("source_annotation_id")
    name = os.path.basename(q["image_path"])
    return next((r for r in records if r.get("source_annotation_id") == ann
                 and os.path.basename((r.get("source_image_path") or "").replace("\\", "/")) == name), None)


def conflict_of(rec, head, answer):
    """Why a reviewed answer cannot be applied to this record (None = it can)."""
    sl = rec["labels"].get("sleeve_length") if rec["masks"].get("sleeve_length") else None
    if head == "sleeve_style":
        if answer == "none" and sl in ("short-sleeve", "long-sleeve"):
            return f"answer 'none' but the record's sleeve length is '{sl}'"
        if answer != "none" and sl == "sleeveless":
            return f"answer '{answer}' but the record's sleeve length is 'sleeveless'"
    return None


def apply_decisions(sets, queue, decisions, classes):
    """Step 3. `sets` = {"train": [...], "val": [...]}; returns (test_reviewed records, report)."""
    by_id = {q["queue_id"]: q for q in queue}
    report = {"answers": Counter(), "applied": Counter(), "conflicts": [], "unknown_queue_ids": 0}
    reviewed_test = []
    for d in decisions:
        q = by_id.get(d.get("queue_id"))
        if not q:
            report["unknown_queue_ids"] += 1
            continue
        head, answer, split = q["head"], d.get("decision"), q["split"]
        report["answers"][f"{head}={answer}"] += 1
        if answer not in classes[head]:
            continue                                            # other / unclear: no label
        if split == "test":
            rec = blank_record(q, classes)                      # only the reviewed head is labelled in test_reviewed
        else:
            rec = find_record(q, sets[split])
            if rec is None:
                rec = blank_record(q, classes)
                sets[split].append(rec)
        why = conflict_of(rec, head, answer)
        if why:
            report["conflicts"].append({"queue_id": q["queue_id"], "reason": why})
            continue
        rec["labels"][head], rec["masks"][head], rec["provenance"][head] = answer, 1, REVIEWED
        rec.setdefault("reviewed", {})[head] = {"queue_id": q["queue_id"], "reviewer_id": d.get("reviewer_id"), "reviewed_at": d.get("reviewed_at")}
        rec.pop("masked_candidate", None) if head == "neckline_type" else None
        finish(rec, classes)
        report["applied"][f"{split}: {head}={answer}"] += 1
        if split == "test":
            reviewed_test.append(rec)
    report["answers"], report["applied"] = dict(report["answers"]), dict(report["applied"])
    return reviewed_test, report


def drop_near_duplicates(records, hashes, against, label, report):
    """Keep the records whose photo is not near-identical to any photo hashed in `against`."""
    if not against:
        return records
    photos = [audit.photo_of(r) for r in records]
    known = [p for p in dict.fromkeys(photos) if p in hashes and "error" not in hashes[p]]
    hit = audit.near_duplicates([hashes[p]["dhash"] for p in known], against)
    bad = {p for p, j in zip(known, hit) if j >= 0}
    kept = [r for r, p in zip(records, photos) if p not in bad]
    report[label] = len(records) - len(kept)
    return kept


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--decisions", default="ai_training/data/label_queue_m42/decisions.jsonl")
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    classes = L.load_classes(CLASSES_FILE)
    os.makedirs(OUT, exist_ok=True)
    report = {"copied_identical": {}, "fixes": {}, "dropped": {}}

    for t in FROZEN_TESTS:
        shutil.copyfile(f"{M41}/{t}", f"{OUT}/{t}")
        assert sha(f"{M41}/{t}") == sha(f"{OUT}/{t}") == sha(f"ai_training/data/manifests_m40/{t}"), t
        report["copied_identical"][t] = sha(f"{OUT}/{t}")[:16]

    sets = {s: L.load_jsonl(f"{M41}/{s}.jsonl") for s in ("train", "val")}
    test_dmm = L.load_jsonl(f"{M41}/test_dmm.jsonl")
    for name, recs in (("train", sets["train"]), ("val", sets["val"]), ("test_dmm", test_dmm)):
        report["fixes"][f"tank tops no longer labelled t-shirt ({name})"] = mask_tank_tops(recs, classes)

    decisions = L.load_jsonl(a.decisions) if os.path.exists(a.decisions) else []
    queue = L.load_jsonl(QUEUE) if os.path.exists(QUEUE) else []
    reviewed_test, review = apply_decisions(sets, queue, decisions, classes)
    report["review"] = dict(review, decisions_file=a.decisions if decisions else None, decisions=len(decisions))

    tests = {t: L.load_jsonl(f"{OUT}/{t}") for t in FROZEN_TESTS}
    everything = sets["train"] + sets["val"] + test_dmm + reviewed_test + [r for recs in tests.values() for r in recs]
    hashes = audit.image_hashes(sorted({p for p in (audit.photo_of(r) for r in everything) if p}), a.workers)

    def dh(records):
        return [hashes[p]["dhash"] for p in dict.fromkeys(audit.photo_of(r) for r in records) if p in hashes and "error" not in hashes[p]]

    test_dh = dh(test_dmm + reviewed_test + [r for recs in tests.values() for r in recs])
    sets["train"] = drop_near_duplicates(sets["train"], hashes, test_dh, "train records near-identical to a test photo", report["dropped"])
    sets["val"] = drop_near_duplicates(sets["val"], hashes, test_dh, "val records near-identical to a test photo", report["dropped"])
    sets["val"] = drop_near_duplicates(sets["val"], hashes, dh(sets["train"]), "val records near-identical to a training photo", report["dropped"])

    def keep(r):
        return any(r["masks"].get(h) == 1 for h in L.HEADS)

    def dump(name, recs):
        with open(f"{OUT}/{name}", "w", encoding="utf-8") as f:
            for r in recs:
                f.write(json.dumps(r) + "\n")

    dump("train.jsonl", [r for r in sets["train"] if keep(r)])
    dump("val.jsonl", [r for r in sets["val"] if keep(r)])
    dump("test_dmm.jsonl", [r for r in test_dmm if keep(r)])
    dump("test_reviewed.jsonl", reviewed_test)

    counts = {}
    for name in ("train.jsonl", "val.jsonl", "test_dmm.jsonl", "test_reviewed.jsonl"):
        recs = L.load_jsonl(f"{OUT}/{name}")
        counts[name] = {"records": len(recs), "by_source": dict(Counter(audit.source_of(r) for r in recs)),
                        "per_head": {h: dict(Counter(f"{r['labels'][h]} [{r['provenance'][h]}]" for r in recs if r["masks"].get(h) == 1))
                                     for h in L.HEADS}}
    json.dump({"report": report, "counts": counts}, open(f"{OUT}/counts.json", "w"), indent=2)
    print(json.dumps(report, indent=1))
    for n, c in counts.items():
        print(n, c["records"], c["by_source"])


if __name__ == "__main__":
    main()
