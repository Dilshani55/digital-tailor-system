# AI training-data audit (1 Oct 2026)

What data exists on this machine for the garment classifier (heads 3 / 5 / 3 / 4), how far each label can be
trusted, what was wrong, what was fixed, and what still needs a person. Everything here is produced by one
read-only script from the manifests the trainer really reads:

```powershell
backend\venv\Scripts\python ai_training\scripts\v2\audit_datasets.py --out evidence\ai_data_audit
```

(`evidence/` and all datasets are local and git-ignored. The first run hashes about 43,500 photos and takes a few
minutes; later runs use a cache.)

## Datasets

| Dataset | Folder (local) | Licence | Used for |
|---|---|---|---|
| Fashionpedia | `ai_training/data/raw/fashionpedia` | annotations CC BY 4.0 | garment type (human-verified subset), neckline, sleeve length, puff / bell sleeves |
| DeepFashion2 | `ai_training/datasets/archive/DeepFashion2` → prepared tops in `ai_training/datasets/deepfashion2_tops` | non-commercial research | sleeve length (human category), `none` for sleeveless; garment detector training |
| DeepFashion-MultiModal (DMM) | `ai_training/datasets/deepfashion_multimodal` | non-commercial research | sleeve length and neckline (human shape annotation); garment type by **proxy** (shop category / navel rule) |

Every image a manifest names exists on disk; no image is unreadable.

## Labels per head and class

`trusted` = a person labelled this attribute (or `none` follows from an explicit sleeveless label).
`proxy` = a shop category or a rule stands in for the label. Counts are for the manifests of the next
candidate (`manifests_m42`, after the fixes below, before any human review).

| Head | Class | Train | Val | Test (test_all) | Test (test_dmm) | Benchmark (60) |
|---|---|---:|---:|---:|---:|---:|
| garment_type | blouse | 87 (+4,687 proxy) | 38 (+878 proxy) | 42 | 0 (+1,077 proxy) | 20 |
| garment_type | t-shirt | 211 (+4,047 proxy) | 36 (+821 proxy) | 40 | 0 (+675 proxy) | 20 |
| garment_type | crop-top | 814 (+1,779 proxy) | 38 (+355 proxy) | 44 | 0 (+380 proxy) | 20 |
| neckline_type | round-neck | 7,468 | 1,479 | 527 | 994 | 23 |
| neckline_type | v-neck | 1,762 | 335 | 197 | 168 | 8 |
| neckline_type | square-neck | 189 | 32 | **24** | **8** | **0** |
| neckline_type | collared-neck | **0** | **0** | **0** | **0** | **0** |
| neckline_type | off-shoulder | 146 | **25** | 42 | **0** | **1** |
| sleeve_length | sleeveless | 9,282 | 1,460 | 369 | 1,436 | **0** |
| sleeve_length | short-sleeve | 9,057 | 1,673 | 1,018 | 673 | 29 |
| sleeve_length | long-sleeve | 10,060 | 1,682 | 1,317 | 543 | 13 |
| sleeve_style | none | 9,282 | 1,456 | 367 | 1,436 | **0** |
| sleeve_style | regular-sleeve | **0** | **0** | **0** | **0** | **0** |
| sleeve_style | puff-sleeve | 142 | **18** | 33 | **0** | 8 |
| sleeve_style | bell-sleeve | **57** | **17** | **13** | **0** | 3 |

Bold = fewer than 30 validation / test examples, or fewer than 100 training examples.

What this means for the six classes the brief names:

| Class | Evidence | Consequence |
|---|---|---|
| regular-sleeve | **No trusted label anywhere.** 448 Fashionpedia candidates ("set-in sleeve" is a construction, not a style). | Cannot be learned or tested until a person reviews photos. The app shows "please select". |
| collared-neck | **No trusted label anywhere.** Candidates: 277 Fashionpedia (collar part), 810 DMM ("lapel": 582 train / 84 val / 144 test). | Same. The 582 lapel candidates stay masked: "lapel" also means a jacket lapel. |
| bell-sleeve | 57 train / 17 val / 13 test, Fashionpedia only; the source pool is exhausted. | Weak: test F1 rests on 13 photos. |
| square-neck | 189 train / 32 val / 24 test (+8 DMM). | Weak: just under 30 test photos. |
| off-shoulder | 146 train / 25 val / 42 test, Fashionpedia only. | Usable, small. |
| crop-top / T-shirt | Trusted test labels: 44 / 40 (126 garment-type test labels in total). Training is dominated by proxies. | One wrong test photo changes garment accuracy by 0.8 points; small differences between models are noise. |

## What was wrong and what was done

| Finding | Measured | Action in `build_m42_manifests.py` |
|---|---|---|
| **Tank tops labelled "t-shirt".** DMM's shop category `Tees_Tanks` mixes tees and tanks; with a human sleeve label of "sleeveless" the garment is a tank top, not a T-shirt (class definition: knit tee *with sleeves*). | 4,481 labels (3,203 train, 566 val, 712 test_dmm) — 44 % of the DMM "t-shirt" proxy labels used by the M41 experiment | Garment type **masked** for those records (not relabelled); the human sleeve label is kept |
| Training photos near-identical to test photos (dHash, Hamming ≤ 4) | 25 test_all photos and 11 test_dmm photos had a near-twin in training | 43 training records dropped. The test files are not touched |
| Validation photos near-identical to training or test photos | 233 validation photos had a near-twin in training (199 of them DMM ~ DMM); 47 test photos had a near-twin in validation | 266 validation records dropped (thresholds are chosen on validation) |
| DeepFashion2 ids reused for different photos (its train and validation folders are numbered separately), so the id `df2:023609` names two photos | 116 ids | Not leakage: the photos differ (0 byte-identical photos across splits). The audit now identifies a DeepFashion2 photo by folder + id |
| Byte-identical photos across splits | 0 | – |
| Same DMM garment item in two splits | 0 | – |
| Labels outside a head's classes, class index ≠ label, mask ≠ label, masked provenance used as a label, `none` without sleeveless | 0 | – |
| DeepFashion2 category → sleeve length, DMM shape value → sleeve length / neckline, re-derived from the source files for every record | 0 mismatches | – |

After the fixes the same audit on `manifests_m42` reports no mapping problem and no identical or near-identical
photo between training, validation and any test set.

Labels that are correct but describe a garment the engine cannot draft (information only, kept): sleeveless blouse
(2,991 proxy), long-sleeved crop top (416 proxy, 88 Fashionpedia, 16 human-verified).

## Human review queue

`build_review_queue_m42.py` (seed 42) → `ai_training/data/label_queue_m42/queue.jsonl`, 725 photos:

| Question | Source | Train | Val | Test |
|---|---|---:|---:|---:|
| Neckline (collared-neck candidates) | Fashionpedia, collar part attached | 140 | 40 | 45 |
| Neckline (collared-neck candidates) | DMM front views, source value "lapel" | 100 | 30 | 35 |
| Sleeve style (regular-sleeve candidates) | Fashionpedia, "set-in sleeve" | 140 | 40 | 45 |
| Sleeve style (regular-sleeve candidates) | DeepFashion2 short / long sleeved tops | 60 | 20 | 30 |

The reviewer answers the class they see, or `other` / `unclear`. Class definitions:
[LABEL_GUIDE_15class.md](../ai_training/datasets/LABEL_GUIDE_15class.md).

**Review done on 1 Oct 2026: 725 of 725 answered by one reviewer (the project owner).**

| Question | Answers |
|---|---|
| Neckline (390) | collared-neck 278, other 62, unclear 49, off-shoulder 1 |
| Sleeve style (335) | regular-sleeve 288, other 18, unclear 16, puff-sleeve 9, bell-sleeve 4 |

Labels this gives (after the near-duplicate filter): collared-neck 166 train / 47 validation / 64 test;
regular-sleeve 169 train / 52 validation / 66 test. No answer contradicted a trusted label.

How far these labels can be trusted, stated plainly: the review took 24 minutes (median about one second per
photo), by one person, with no second reviewer. A sample of 24 "collared-neck" and 24 "regular-sleeve" answers was
looked at afterwards: most are right, but a few jackets and coats were labelled (the candidate photos contain
them). The labels are therefore human labels with some noise, not a verified gold standard, and results on
`test_reviewed` (64 and 66 photos) should be read with that in mind.

```powershell
backend\venv\Scripts\python ai_training\tools\review_labels.py --reviewer "your name"     # then open http://127.0.0.1:5090
```

## Acceptance targets (fixed before training)

`ai_training/config/m42_acceptance.json`, committed before any M42 run. The gate set is the unchanged M40 test set
(`test_all`) with the crop the app uses (garment detector, box + 10 %):

| Item | M40 (baseline) | Candidate must reach |
|---|---|---|
| Garment type macro-F1 | 0.759 | ≥ 0.79 |
| Neckline macro-F1 | 0.503 | ≥ 0.53 |
| Sleeve length macro-F1 | 0.817 | ≥ 0.81 |
| Sleeve style macro-F1 | 0.617 | ≥ 0.61 |
| Accuracy of every head | 0.762 / 0.663 / 0.840 / 0.930 | not more than 0.01 below M40 |
| Sleeve length answered automatically | 92.2 % correct at 79.7 % coverage | ≥ 90 % correct, coverage ≥ 75 % |
| Any other head answered automatically | none | ≥ 90 % correct when answered |
| Integrity | – | loads in the production code; test files byte-identical to M40's; no near-identical train / test photos |

The checkpoint and all thresholds are chosen on validation only. A head is answered automatically only if every one
of its classes has at least 15 trusted validation examples. New classes (collared-neck, regular-sleeve) are offered
as AI suggestions only with ≥ 30 reviewed test examples and F1 ≥ 0.60 on them; that does not decide pass / fail.
Pass → the candidate becomes the default and M40 is kept as rollback. Fail → M40 stays and the gap is reported.
M40 itself does not pass this gate (garment type and neckline), so a candidate has to be really better.

## Training status

One M42 training run was started on 1 Oct 2026 after the review (see the result section when it has finished). Order of work:

```powershell
backend\venv\Scripts\python ai_training\scripts\v2\build_m42_manifests.py                 # applies the fixes + the reviewed labels
$env:AUDIT_MANIFESTS="ai_training/data/manifests_m42"; backend\venv\Scripts\python ai_training\scripts\v2\audit_datasets.py --out evidence\ai_data_audit\m42
backend\venv\Scripts\python ai_training\scripts\train_multitask.py --config ai_training/config/m42_config.json --classes ai_training/config/classes_v2_15class.json --train-manifest ai_training/data/manifests_m42/train.jsonl --val-manifest ai_training/data/manifests_m42/val.jsonl --output-dir ai_training/data/training_runs/m42
backend\venv\Scripts\python ai_training\scripts\v2\eval_m42.py --candidate ai_training/data/training_runs/m42/checkpoints/best.pt --out ai_training/data/training_runs/m42/evaluation
```

`m42_config.json` is the M40 / M41 recipe with a longer schedule (M41 was still improving at its last allowed
epoch): up to 40 fine-tuning epochs with early stopping (patience 8), backbone layers 4–8 trainable instead of only
layer 8. CPU only on this laptop: plan one overnight run. `eval_m42.py` reports whole-photo, detector-crop and
ground-truth-crop results separately, per-head accuracy and macro-F1, per-class precision / recall / F1, confusion
matrices and auto-answer accuracy with coverage, then writes `gate.json` with PASS or FAIL.

Until a candidate passes, the deployed model is **M40** (auto-fills sleeve length only) with the garment detector;
see [AI_EVIDENCE.md](AI_EVIDENCE.md), [AI_DETECTOR.md](AI_DETECTOR.md) and [AI_M41.md](AI_M41.md).

## Earlier audit (30 Sep 2026, Fashionpedia only)

The first audit concerned the older 28-class model (M13) and Fashionpedia alone; its per-class table is superseded
by the one above. Its conclusions that still hold: explicit Fashionpedia attributes for puff, bell, square-neck and
off-shoulder are exhausted (no more examples can be recovered from that dataset); a missing sleeve annotation is
never treated as sleeveless; rule-derived collared-neck and regular-sleeve labels are not trustworthy without a
person (the review sheets showed suits, jackets and men's shirts).
