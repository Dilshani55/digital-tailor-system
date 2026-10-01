"""Apply the M42 acceptance gate (ai_training/config/m42_acceptance.json, written before training) to a candidate.

Input: the detector-crop evaluation of the candidate (the JSON written by eval_m40_detector_crop.py, as run by
eval_m42.py). Output: PASS or FAIL with every item, its measured value and its target. Nothing is deployed here.

    backend\\venv\\Scripts\\python ai_training\\scripts\\v2\\check_m42_gate.py --candidate-eval <.../m40_detector_crop_eval.json> --out <gate.json>
       [--reviewed-eval <same file; set test_reviewed is read from it>] [--integrity-ok]
"""
import argparse
import json
import sys

HEADS = ("garment_type", "neckline_type", "sleeve_length", "sleeve_style")


def decide(gate, candidate_heads, reviewed_heads=None, integrity_ok=None):
    """
    gate            : the acceptance JSON
    candidate_heads : {head: {"n", "accuracy", "macro_f1", "answered": {"threshold", "coverage", "accuracy_when_answered"}}}
                      measured on test_all with the detector crop
    reviewed_heads  : the same structure measured on test_reviewed (may be None: not reviewed yet)
    integrity_ok    : True / False from the integrity checks, None = not checked (counts as a failure)
    Returns {"decision": "PASS" | "FAIL", "items": [...], "new_classes": {...}}.
    """
    req = gate["required"]
    base = gate["baseline"]["detector_crop_test_all"]
    items = []

    def item(name, value, target, ok, comparison):
        items.append({"item": name, "measured": value, "target": target, "rule": comparison, "passed": bool(ok)})

    for h in HEADS:
        m = candidate_heads.get(h)
        target = req["macro_f1_min"][h]
        if not m:
            item(f"{h}: macro-F1", None, target, False, ">= target (head not evaluated)")
            continue
        item(f"{h}: macro-F1", m["macro_f1"], target, m["macro_f1"] >= target, ">= target")
        floor = round(base[h]["accuracy"] - req["accuracy_max_drop_vs_baseline"], 4)
        item(f"{h}: accuracy not below M40", m["accuracy"], floor, m["accuracy"] >= floor, ">= M40 accuracy - 0.01")

    auto = req["auto_answer"]
    for h in HEADS:
        a = (candidate_heads.get(h) or {}).get("answered") or {}
        answered = a.get("threshold") is not None
        must = auto["heads_that_must_stay_auto_answered"].get(h)
        if must and not answered:
            item(f"{h}: still answered automatically", "not answered", "answered", False, "the head must keep a validation-chosen threshold")
            continue
        if answered:
            acc = a.get("accuracy_when_answered")
            item(f"{h}: accuracy when answered", acc, auto["min_accuracy_when_answered"],
                 acc is not None and acc >= auto["min_accuracy_when_answered"], ">= target")
            if must:
                item(f"{h}: coverage", a.get("coverage"), must["min_coverage"], (a.get("coverage") or 0) >= must["min_coverage"], ">= target")

    item("integrity checks (loads in production code, identical test files, no train/test near-duplicates)",
         integrity_ok, True, integrity_ok is True, "must be verified true")

    new = {}
    rule = gate["new_classes"]
    for h, cls in rule["classes"].items():
        per = ((reviewed_heads or {}).get(h) or {}).get("per_class", {}).get(cls)
        if not per:
            new[cls] = {"offered_as_ai_suggestion": False, "reason": "no human-reviewed test examples yet"}
            continue
        ok = per["support"] >= rule["min_reviewed_test_examples"] and per["f1"] >= rule["min_f1_on_test_reviewed"]
        new[cls] = {"offered_as_ai_suggestion": bool(ok), "support": per["support"], "f1": per["f1"],
                    "targets": {"support": rule["min_reviewed_test_examples"], "f1": rule["min_f1_on_test_reviewed"]}}

    failed = [i for i in items if not i["passed"]]
    return {"decision": "PASS" if not failed else "FAIL", "failed_items": len(failed), "items": items, "new_classes": new,
            "action": gate["decision"]["pass" if not failed else "fail"]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gate", default="ai_training/config/m42_acceptance.json")
    ap.add_argument("--candidate-eval", required=True)
    ap.add_argument("--integrity-ok", action="store_true", help="pass only after build_m42_manifests.py and eval_m42.py reported no integrity problem")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    gate = json.load(open(a.gate, encoding="utf-8"))
    ev = json.load(open(a.candidate_eval, encoding="utf-8"))
    sets = ev["sets"]
    result = decide(gate, sets["test_all"]["heads"], (sets.get("test_reviewed") or {}).get("heads"), True if a.integrity_ok else None)
    result["candidate"] = {"classifier": ev.get("classifier"), "sha256": ev.get("classifier_sha256"), "thresholds": ev.get("thresholds_used")}
    json.dump(result, open(a.out, "w", encoding="utf-8"), indent=2)
    print(result["decision"], "-", result["action"])
    for i in result["items"]:
        print(("  ok   " if i["passed"] else "  FAIL ") + f"{i['item']}: {i['measured']} (target {i['target']})")
    for cls, v in result["new_classes"].items():
        print(f"  new class {cls}: {v}")
    sys.exit(0 if result["decision"] == "PASS" else 2)


if __name__ == "__main__":
    main()
