"""
labels15.py - label logic for the FUTURE 3/5/3/4 (15-class) model. Not used by production.

Rules (see config/classes_v2_15class.json):
  * a label outside the 15 active classes is MASKED for that head (mask 0, label None). It is never
    converted into a "similar" active class.
  * sleeve_style == "none" is kept only when the same record has an explicit, trusted sleeve_length
    "sleeveless". A missing sleeve annotation is not evidence.
  * only human_verified / fashionpedia_direct labels count as TRUSTED evidence for readiness.
"""

import json
import math
import os

HEADS = ["garment_type", "neckline_type", "sleeve_length", "sleeve_style"]
DERIVED_NONE = "derived_from_explicit_sleeveless"
TRUSTED = {"human_verified", "fashionpedia_direct", DERIVED_NONE}
MASKED_PROVENANCE = "missing/masked"
REMOVED_PROVENANCE = "masked_removed_class"
SPLITS = ("train", "val", "test")


def load_classes(path):
    with open(path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    out = {h: list(cfg["outputs"][h]["classes"]) for h in HEADS}
    dims = [len(out[h]) for h in HEADS]
    if dims != [3, 5, 3, 4]:
        raise ValueError(f"Expected head dimensions 3/5/3/4, found {dims}")
    return out


def load_targets(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def convert_record(rec, classes):
    """Return a copy of a 28/29-class manifest record re-expressed for the 15 active classes."""
    new = dict(rec)
    labels, masks, prov, conf = {}, {}, {}, {}
    trusted, removed = {}, []
    for h in HEADS:
        lab = (rec.get("labels") or {}).get(h)
        m = (rec.get("masks") or {}).get(h, 0)
        p = (rec.get("provenance") or {}).get(h, MASKED_PROVENANCE)
        c = (rec.get("confidence") or {}).get(h)
        if m == 1 and lab in classes[h]:
            labels[h], masks[h], prov[h], conf[h] = lab, 1, p, c
        elif m == 1 and lab is not None:
            labels[h], masks[h], prov[h], conf[h] = None, 0, REMOVED_PROVENANCE, None
            removed.append({"head": h, "removed_label": lab})
        else:
            labels[h], masks[h], prov[h], conf[h] = None, 0, MASKED_PROVENANCE, None
        trusted[h] = bool(masks[h] and prov[h] in TRUSTED)

    # sleeve_style "none" needs an explicit trusted "sleeveless"; nothing else may sit on a sleeveless garment
    sl_ok = labels["sleeve_length"] == "sleeveless" and trusted["sleeve_length"]
    if labels["sleeve_style"] == "none" and not sl_ok:
        labels["sleeve_style"], masks["sleeve_style"], prov["sleeve_style"] = None, 0, MASKED_PROVENANCE
        conf["sleeve_style"], trusted["sleeve_style"] = None, False
        new["sleeve_style_none_rejected"] = "no explicit trusted sleeveless label"
    elif labels["sleeve_length"] == "sleeveless" and labels["sleeve_style"] not in (None, "none"):
        labels["sleeve_style"], masks["sleeve_style"], prov["sleeve_style"] = None, 0, MASKED_PROVENANCE
        conf["sleeve_style"], trusted["sleeve_style"] = None, False
        new["sleeve_style_conflict"] = "style given for a sleeveless garment"

    if labels["sleeve_style"] == "none":       # explicit trusted sleeveless on the same record -> deterministic, trusted
        prov["sleeve_style"] = DERIVED_NONE
        trusted["sleeve_style"] = True

    new["labels"], new["masks"], new["provenance"], new["confidence"] = labels, masks, prov, conf
    new["trusted"] = trusted
    new["removed_class_masked"] = removed
    new["class_indices"] = {h: (classes[h].index(labels[h]) if labels[h] is not None else None) for h in HEADS}
    new["taxonomy"] = "15class-v2"
    return new


def count_classes(records_by_split, classes):
    """{split: {head: {class: {"total": n, "trusted": m}}}} plus masked-removed tallies."""
    out = {}
    for split, recs in records_by_split.items():
        out[split] = {}
        for h in HEADS:
            row = {c: {"total": 0, "trusted": 0} for c in classes[h]}
            for r in recs:
                lab = r["labels"].get(h)
                if lab in row and r["masks"].get(h) == 1:
                    row[lab]["total"] += 1
                    row[lab]["trusted"] += 1 if r["trusted"].get(h) else 0
            out[split][h] = row
    return out


def readiness(counts, targets, classes, splits=SPLITS):
    """Compare TRUSTED counts with the minimum targets. Returns a report dict (never raises)."""
    need = targets["minimum_trusted_per_class"]
    rows, missing, ok = [], {s: {h: {} for h in HEADS} for s in splits}, True
    for h in HEADS:
        for c in classes[h]:
            row = {"head": h, "class": c}
            for s in splits:
                have = counts.get(s, {}).get(h, {}).get(c, {"total": 0, "trusted": 0})
                short = max(0, need[s] - have["trusted"])
                row[s] = {"total": have["total"], "trusted": have["trusted"], "target": need[s], "missing": short}
                if short:
                    missing[s][h][c] = short
                    ok = False
            rows.append(row)
    insufficient = sorted({(r["head"], r["class"]) for r in rows if any(r[s]["missing"] for s in splits)})
    return {"verdict": "READY" if ok else "NOT_READY", "targets": need, "rows": rows, "missing": missing,
            "insufficient_classes": [{"head": h, "class": c} for h, c in insufficient]}


def format_table(counts, report, classes, splits=SPLITS):
    lines = [f"{'head':14}{'class':16}" + "".join(f"{s + ' n(trusted)':>20}" for s in splits) + "   status"]
    for r in report["rows"]:
        cells = "".join(f"{str(r[s]['total']) + ' (' + str(r[s]['trusted']) + ')':>20}" for s in splits)
        bad = [s for s in splits if r[s]["missing"]]
        status = "ok" if not bad else "MISSING " + ", ".join(f"{s}:{r[s]['missing']}" for s in bad)
        lines.append(f"{r['head']:14}{r['class']:16}{cells}   {status}")
    return "\n".join(lines)


# ── human decisions ───────────────────────────────────────────────────────────
def load_jsonl(path):
    with open(path, "r", encoding="utf-8") as f:
        return [json.loads(x) for x in f if x.strip()]


def validate_decisions(queue_rows, decisions, classes):
    """
    Returns (accepted_rows, problems). A decision is accepted only if the queue id exists, the reviewer is
    named, and the decision is one of the ACTIVE classes of the queue row's head (or reject/uncertain,
    which are recorded but add no label).
    """
    by_id = {q["queue_id"]: q for q in queue_rows}
    seen, accepted, problems = {}, [], []
    for d in decisions:
        qid = d.get("queue_id")
        q = by_id.get(qid)
        if q is None:
            problems.append(f"{qid}: not in the queue")
            continue
        if not str(d.get("reviewer_id") or "").strip():
            problems.append(f"{qid}: reviewer_id missing")
            continue
        val = d.get("decision")
        if val in ("reject", "uncertain"):
            seen[qid] = val
            continue
        if val not in classes[q["target_head"]]:
            problems.append(f"{qid}: '{val}' is not an active class of {q['target_head']}")
            continue
        if qid in seen and seen[qid] != val:
            problems.append(f"{qid}: conflicting duplicate decisions")
            continue
        seen[qid] = val
        accepted.append({"queue": q, "label": val, "reviewer_id": d["reviewer_id"], "reviewed_at": d.get("reviewed_at")})
    return accepted, problems


def record_from_decision(acc, classes):
    """A new manifest record with exactly ONE labelled head (human_verified); every other head masked."""
    q, h, lab = acc["queue"], acc["queue"]["target_head"], acc["label"]
    labels = {x: None for x in HEADS}
    masks = {x: 0 for x in HEADS}
    prov = {x: MASKED_PROVENANCE for x in HEADS}
    labels[h], masks[h], prov[h] = lab, 1, "human_verified"
    rec = {
        "record_uid": f"human15:{q['source_annotation_id']}:{h}",
        "source_dataset": "fashionpedia",
        "source_image_id": q["source_image_id"],
        "source_image_uid": q.get("source_image_uid"),
        "source_annotation_id": q["source_annotation_id"],
        "source_image_path": q["source_image_path"],
        "crop_path": None, "bbox": q["bbox"], "split": q["split"],
        "labels": labels, "masks": masks, "provenance": prov, "confidence": {x: None for x in HEADS},
        "human_verified": True, "reviewer_id": acc["reviewer_id"], "reviewed_at": acc.get("reviewed_at"),
        "sample_weight": 1.0,
    }
    return convert_record(rec, classes)


def sha256_file(path):
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def stable_order(key, seed):
    import hashlib
    return hashlib.sha1(f"{seed}:{key}".encode()).hexdigest()


def quota(missing, factor):
    return int(math.ceil(missing * factor))
