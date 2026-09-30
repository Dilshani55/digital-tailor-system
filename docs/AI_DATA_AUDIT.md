# 15-class data audit and training decision (30 Sep 2026)

Question: can a classifier with the exact 3 / 5 / 3 / 4 output heads be trained and *independently
validated* with the data that exists today? Answer: **no — the evidence for 9 of the 15 classes is
insufficient, and for 5 classes there is nothing to evaluate against.** The production model therefore
stays the validated M13 checkpoint (SHA-256 `3b69a470ed5d039844056135ad27c700a865b82196ef85dc6a5e9f53c84f0339`),
whose predictions outside the 15 classes are shown but never remapped.

Reproduce (local data, not in Git):

```powershell
$env:PYTHONPATH="."
backend\venv\Scripts\python ai_training\scripts\build_15class_manifests.py    # trusted counts + verdict
backend\venv\Scripts\python ai_training\scripts\audit_15class_classes.py      # this table + recovery candidates
backend\venv\Scripts\python ai_training\scripts\make_review_contact_sheets.py # human-review sheets
```

Manifest checksums of this run: `train.jsonl 4f2a1c34…57da0`, `val.jsonl 07c145e6…fe30ef`,
`test.jsonl 5fc3784d…f473d6` (full values in `ai_training/data/manifests_15class/counts.json`).
Targets per class (trusted labels): train ≥ 100, validation ≥ 30, test ≥ 30.

## Per-class table

"Raw count" = labelled records of the class before trust filtering; trusted = `human_verified`,
`fashionpedia_direct`, or `none` derived from an explicit sleeveless label; validation/test exclude images with a
near-duplicate (dHash ≤ 4) in training. "Upper bound" = images in the raw Fashionpedia annotations (train + val)
where the explicit attribute occurs together with exactly the garment we train on (a top/blouse and no other
upper garment) — the most any recovery could reach.

| Head | Class | Raw count | Trusted train | Val | Test | Locked benchmark | Train label provenance | Raw upper bound | Known risks |
|---|---|---:|---:|---:|---:|---:|---|---:|---|
| garment_type | blouse | 359 | **87** | 39 | 42 | 20 | human_verified 87, accepted_pseudo_label 191 | | Fashionpedia merges blouses with button-down shirts (the review sheets show men's shirts and jackets) |
| garment_type | t-shirt | 288 | 212 | 36 | 40 | 20 | human_verified 212 | | |
| garment_type | crop-top | 903 | 815 | 39 | 44 | 20 | fashionpedia_direct 764, human_verified 51, accepted_pseudo_label 5 | | |
| neckline_type | round-neck | 3621 | 2597 | 497 | 527 | 23 | fashionpedia_direct 2597 | | |
| neckline_type | v-neck | 1172 | 815 | 160 | 197 | 8 | fashionpedia_direct 815 | | |
| neckline_type | square-neck | 171 | 126 | **21** | **24** | **0** | fashionpedia_direct 126 | 134 | pool exhausted; not in the benchmark |
| neckline_type | collared-neck | 493 | **0** | **0** | **0** | **0** | fashionpedia_rule_derived 493 | | only a candidate rule (collar part present); nothing trusted anywhere |
| neckline_type | off-shoulder | 213 | 146 | **25** | 42 | 1 | fashionpedia_direct 146 | 214 | pool exhausted |
| sleeve_length | sleeveless | 22 | **16** | **4** | **2** | **0** | fashionpedia_direct 16 | 61 | very rare on tops; not in the benchmark |
| sleeve_length | short-sleeve | 3787 | 2722 | 543 | 522 | 29 | fashionpedia_direct 2722 | | |
| sleeve_length | long-sleeve | 5497 | 3895 | 778 | 824 | 13 | fashionpedia_direct 3895 | | |
| sleeve_style | none | 16 | **16** | **0** | **0** | **0** | derived_from_explicit_sleeveless 16 | | limited by sleeveless |
| sleeve_style | regular-sleeve | 494 | **0** | **0** | **0** | **0** | fashionpedia_rule_derived 494 | | "set-in sleeve" is a construction, not a style |
| sleeve_style | puff-sleeve | 194 | 142 | **19** | 33 | 8 | fashionpedia_direct 142 | 200 | pool exhausted |
| sleeve_style | bell-sleeve | 89 | **58** | **18** | **13** | 3 | fashionpedia_direct 58 | 95 | pool exhausted |

Bold = below target. Verdict of `build_15class_manifests.py`: **NOT_READY**.

## Weak-class recovery (spec §5.2)

* The raw annotations were searched directly. Explicit attributes sit on **part** annotations (sleeve,
  neckline, collar) and mostly belong to dresses/jackets: e.g. 951 puff-sleeve parts exist, but only ~200 of them
  are on images whose only upper garment is a top/blouse — and 194 are already used. The same holds for bell,
  square-neck and off-shoulder (upper bounds 95 / 134 / 214 vs 89 / 171 / 213 already used).
* `sleeveless`: 61 unambiguous images exist; after removing those already in the manifests **15 new candidates**
  remain (`ai_training/data/audits/sleeveless_recovery_candidates.jsonl`, provenance `fashionpedia_direct`, with
  `none` derived from it). Even with all of them sleeveless reaches ~37 labels versus the 160 needed. They are
  listed, not added: they must follow their source image's split and pass the near-duplicate check in a reviewed
  rebuild.
* A missing sleeve annotation is **never** treated as sleeveless (tested).
* `collared-neck` and `regular-sleeve` have no direct attribute; their only evidence is a rule (collar part /
  "set-in" construction) and the review sheets show why that is not trustworthy (suits, jackets, men's shirts).
  They need human review.

## Human review (prepared, not done)

`make_review_contact_sheets.py` produced 45 contact sheets (36 numbered crops each) and one CSV per sheet from the
existing 1,413-item queue (collared-neck, regular-sleeve, sleeveless candidates, blouse). A reviewer writes the
class, `reject` or `uncertain` and a reviewer id per number; `--collect` turns the CSVs into `decisions.jsonl`
for `build_15class_manifests.py --decisions`. The collected yield is unknown until someone reviews them.

## Training decision (spec §5.6–5.7, Milestone 3)

**No training run was started.** Reasons, all measured above:

1. Five classes (collared-neck, sleeveless, none, regular-sleeve, and square-neck) have **no example in the
   locked benchmark**, and three (collared-neck, none, regular-sleeve) have **no trusted validation or test
   example** — the acceptance gate's "no zero/near-zero recall on critical weak classes" criterion cannot even be
   computed, so no candidate could pass it honestly.
2. The three earlier controlled experiments on the same data (focal loss γ 2 / γ 1, label-safe augmentation)
   all failed the gate ([AI_EVIDENCE.md](AI_EVIDENCE.md) §4); repeating runs on unchanged data would spend
   3+ CPU hours without new information.
3. The guard `train_15class_guarded.py` refuses to train while the verdict is NOT_READY — by design.

What would change the decision: reviewed labels from the contact sheets (collared-neck, regular-sleeve, blouse),
and — for sleeveless/none, square-neck, bell, puff, off-shoulder — images from another **licensed** dataset
(to be proposed to and approved by the project owner per dataset) plus a new locked benchmark that contains every
class (≥ 10 each).

The production checkpoint is unchanged and its backup in `backend/app/ai/models/archive_m13_checkpoint/`
is intact.
