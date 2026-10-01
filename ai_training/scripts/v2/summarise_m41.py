"""Build the M41 vs M40 comparison table (markdown) from the eval_m41.py outputs.
    backend\\venv\\Scripts\\python ai_training\\scripts\\v2\\summarise_m41.py
"""
import json
import os

E = "ai_training/data/training_runs/m41_dmm_df2_fp_15class/evaluation"
HEADS = ["garment_type", "neckline_type", "sleeve_length", "sleeve_style"]


def main():
    cf = json.load(open(f"{E}/crop_and_full/evaluation.json"))
    det = {t: json.load(open(f"{E}/detector_crop_{t}/m40_detector_crop_eval.json"))["sets"] for t in ("m41", "m40")}
    lines = ["| Set | Head | n | Majority | M40 whole photo | M41 whole photo | M40 detector crop | **M41 detector crop** | M40 GT crop | M41 GT crop |",
             "|---|---|---:|---:|---|---|---|---|---|---|"]
    f = lambda m: f"{m['accuracy']:.3f} / {m['macro_f1']:.3f}" if m and m.get("n") else "–"  # noqa: E731
    for s in cf["eval"]:
        for h in HEADS:
            c41 = cf["eval"][s]["crop"]["candidate"][h]
            if not c41.get("n"):
                continue
            c40 = cf["eval"][s]["crop"]["m13"][h]            # evaluate_m40 calls the baseline "m13"; here it is M40
            w41 = cf["eval"][s]["full"]["candidate"][h]
            w40 = cf["eval"][s]["full"]["m13"][h]
            d41 = det["m41"].get(s, {}).get("heads", {}).get(h)
            d40 = det["m40"].get(s, {}).get("heads", {}).get(h)
            lines.append(f"| {s} | {h} | {c41['n']} | {c41['majority_baseline_accuracy']:.3f} | {f(w40)} | {f(w41)} | "
                         f"{f(d40)} | **{f(d41)}** | {f(c40)} | {f(c41)} |")
    lines += ["", "Accuracy / macro-F1. GT crop = the dataset's own garment box (upper bound); detector crop = what the app does.",
              "", "### Answered automatically (validation thresholds), detector crop: accuracy when answered / coverage", "",
              "| Set | Head | M40 | M41 |", "|---|---|---|---|"]
    for s in det["m41"]:
        for h in HEADS:
            a41 = det["m41"][s]["heads"].get(h, {}).get("answered")
            a40 = det["m40"].get(s, {}).get("heads", {}).get(h, {}).get("answered")
            if not a41:
                continue
            g = lambda a: "always uncertain" if not a or a.get("threshold") is None else f"{a['accuracy_when_answered']} / {a['coverage']}"  # noqa: E731
            lines.append(f"| {s} | {h} | {g(a40)} | {g(a41)} |")
    lines += ["", f"M41 thresholds (chosen on M41 validation, whole-photo mode): {cf['thresholds_chosen_on_validation']}"]
    out = "\n".join(lines) + "\n"
    open(f"{E}/comparison_m41_vs_m40.md", "w", encoding="utf-8").write(out)
    print(out)


if __name__ == "__main__":
    main()
