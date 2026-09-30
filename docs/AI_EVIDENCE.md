# AI evidence: dataset audit, models and deployment decision

Everything here is produced by scripts in `ai_training/` from files on the development machine (data and checkpoints are not stored in Git). Commands to reproduce are at the end. Nothing in this file is estimated or copied from a report without being re-computed.

## 1. What the model is

One image-level classifier: a YOLOv8n-cls backbone (Ultralytics, ImageNet-pretrained, 224×224 input) with **four linear heads** — `garment_type` (3 classes), `neckline_type` (10), `sleeve_length` (6), `sleeve_style` (9) — 28 labels in total. It is **not an object detector** and it does not generate patterns. Training loss is masked (a head is trained only where a label exists) with capped class weights and provenance sample weights. CPU only (no CUDA on the development machine; PyTorch 2.13 CPU).

**Taxonomy in production.** The M13 checkpoint keeps its original output taxonomy (3 / 10 / 6 / 9 = 28 classes, order fixed by the checkpoint). The application lets the user choose from 15 *active* classes (3 / 5 / 3 / 4); a model prediction outside those 15 is kept as evidence, flagged, and never remapped to a look-alike. On the 60 benchmark photos M13 predicts at least one out-of-scope class for 49 images (82 %). A model with exactly the 15-class outputs is planned but not trained: see [FUTURE_15_CLASS_MODEL.md](FUTURE_15_CLASS_MODEL.md).

## 2. Dataset audit (`ai_training/scripts/audit_dataset.py`)

Source: **Fashionpedia** (annotations CC BY 4.0; the images belong to their original photographers/Flickr licences, so the raw images are kept local and are never redistributed). 34,679 annotated garment instances were considered; **15,794** met the labelling policy and form the splits below. Image files are split by *source image*, not by annotation.

| Split | Records | Distinct images | Human-verified | Weak (rule) labels |
|---|---:|---:|---:|---:|
| train | 11,277 | 11,219 | 350 | 1,355 |
| val | 2,219 | 2,210 | 121 | 0 |
| test (locked) | 2,298 | 2,290 | 129 | 0 |
| real-product benchmark (subset of test) | 60 | 60 | – | – |

Manifest fingerprints (SHA-256): `train.jsonl b4faec24…9df16cc`, `val.jsonl 3199ce52…d8fdba`, `test.jsonl 5db81180…e36e5ea9` (full values in `ai_training/data/audits/dataset_audit.json`).

**Integrity.** 15,719 distinct image files opened and fully decoded: **0 missing, 0 corrupt**. Exact duplicate files across splits: **0**. Source-image and record-ID overlap between any two splits: **0**. Taxonomy identical in `classes.json`, the model heads, the backend `feature_schema` and the frontend `designSchema` (checked automatically).

**Near-duplicates (perceptual hash, 64-bit dHash, Hamming ≤ 4).** 107 validation images (4.8 %) and 103 test images (4.5 %) have a near-twin in the training images; 38 test images have one in validation. This is real, so "zero leakage" must not be claimed — only "no shared image IDs and no exact duplicates". The acceptance gate therefore also scores a *clean* test split (test minus those 103 images, n = 2,195). The 60-image locked benchmark has **0** near-duplicates of training images (minimum distance 6) and none of its records is in `train.jsonl`.

**Label provenance and class coverage (train).** garment type is supervised for only 1,310 records (crop-top 820, blouse 278, t-shirt 212; 350 human-verified, 196 CLIP pseudo-labels weighted 0.5). Neckline 6,101 records (round 2,597 … square 126, halter 86), sleeve length 8,438 (long 3,895, short 2,722 … **sleeveless 16**), sleeve style 1,401 (raglan 315, regular 494 … **none 16**). In validation and test, `regular-sleeve`, `none` and `flutter-sleeve` (sleeve style) and `collared-neck` / `cap-length` have **zero** examples, and `sleeveless` has 4 / 2 — so the classes the supported scope needs most cannot be measured reliably, and the sleeve-style scores below describe mostly *out-of-scope* styles.

## 3. Deployed model and baseline

`backend/app/ai/models/garment_multitask_yolov8_best.pt` — SHA-256 `3b69a470ed5d039844056135ad27c700a865b82196ef85dc6a5e9f53c84f0339` (byte-identical to `ai_training/data/training_runs/m12_full/checkpoints/best.pt`; the "M13" deployment is this same file). Trained in two stages (3 head-only epochs, then partial fine-tuning; best at total epoch 7; validation mean macro-F1 0.5489; seed 42).

| Head | Locked benchmark (60 images) accuracy / macro-F1 | Full test split (2,298 records) accuracy / macro-F1 |
|---|---|---|
| garment_type | 78.33 % / 0.7862 | 77.52 % / 0.7785 |
| neckline_type | 54.35 % / 0.4214 | 50.28 % / 0.3965 |
| sleeve_length | 59.26 % / 0.5989 | 73.53 % / 0.4871 |
| sleeve_style | 30.43 % / 0.3167 | 32.45 % / 0.2937 |
| mean macro-F1 | **0.5308** | 0.4889 |

The acceptance gate re-computed the locked-benchmark row through the production inference code and obtained exactly these values, so the comparison pipeline is sound.

## 4. Controlled experiments and the deployment decision

Three controlled experiments were run on the **same** train/validation manifests (fingerprints above), same backbone, CPU, two-stage schedule (3 head-only + up to 8 fine-tune epochs, best epoch chosen by validation mean macro-F1). Only the named factor changed. The locked benchmark and test split were never used for training or model selection.

| Run | Change vs the deployed recipe | Epochs | Best validation mean macro-F1 | Checkpoint SHA-256 (prefix) |
|---|---|---:|---:|---|
| **deployed (M12/"M13")** | class-weighted cross-entropy, seed 42 | 11 | **0.5489** | `3b69a470ed5d0398` |
| m20_focal | focal loss γ = 2, seed 42 | 10 | 0.5380 | `6d93d0963a929c0b` |
| m21_focal_g1 | focal loss γ = 1, seed 7 | 11 | 0.5457 | `ef38b5518a5fdec5` |
| m22_ce_augment | weighted CE + label-safe augmentation (random 80–100 % crop, ±8° rotation, colour jitter, flip), seed 42 | 11 | 0.5320 | `fa677a0f69fdbb32` |

(The older M14C/M14D "fresh head" runs from the earlier project phase reached a validation mean macro-F1 of only 0.386 and are not candidates.)

### Acceptance-gate results (candidate vs the deployed checkpoint, through the production inference code)

| Run | Locked benchmark mean macro-F1 (deployed 0.5308) | Clean test split, n = 2,195 (deployed 0.4996) | Worst head change on the benchmark | Gate |
|---|---:|---:|---|---|
| m20_focal | 0.5108 (−0.020) | 0.4944 (−0.005) | neckline −0.121 | **FAIL** |
| m21_focal_g1 | 0.4798 (−0.051) | 0.5074 (+0.008) | sleeve length −0.101 | **FAIL** |
| m22_ce_augment | 0.4866 (−0.044) | 0.4970 (−0.003) | sleeve style −0.102, garment type −0.055 | **FAIL** |

Per-head benchmark macro-F1 (garment / neckline / sleeve length / sleeve style): deployed 0.786 / 0.421 / 0.599 / 0.317; m20 0.786 / 0.301 / 0.547 / 0.409; m21 0.765 / 0.356 / 0.498 / 0.300; m22 0.732 / 0.451 / 0.548 / 0.215.

### Decision

**No candidate passed, so nothing was deployed and the deployed checkpoint is unchanged** (SHA-256 `3b69a470…`, verified after the runs; an identical backup exists in `backend/app/ai/models/archive_m13_checkpoint/`). None of the changes improved the model in a way that survives both evaluations; m21 gained 0.008 on the clean test split but lost 0.051 on the locked benchmark. The benchmark has only 23–54 labelled items per head, so these differences are noisy — which is why the rule requires both evaluations to agree. The most likely limit is the data (16 sleeveless and 16 "none" sleeve-style training examples; no regular-sleeve validation examples), not the loss function. Collecting and human-labelling more sleeveless / regular-sleeve / neckline examples is the productive next step, and would need a new locked benchmark that contains those classes.

Run outputs (`train_stdout.log`, `logs/training_history.json` with per-epoch, per-head, per-class metrics and confusion matrices, `gate_result.json`) are in `ai_training/data/training_runs/<run>/` (local, not in Git).

## 5. Reproduce

```powershell
$env:PYTHONPATH="."
# dataset audit -> ai_training/data/audits/dataset_audit.json
backend\venv\Scripts\python ai_training\scripts\audit_dataset.py
# training (CPU, seed in the config; ~45 min per run)
backend\venv\Scripts\python ai_training\scripts\train_multitask.py --config ai_training\config\m20_focal_config.json --output-dir ai_training\data\training_runs\m20_focal --focal-gamma 2.0
# deployment gate: candidate vs the deployed model, locked benchmark + clean test split
backend\venv\Scripts\python ai_training\scripts\acceptance_gate.py --candidate <best.pt> --output <gate.json>
```

Gate rule (`ai_training/scripts/acceptance_gate.py`): PASS only if the candidate loads in the production code with the right head sizes and passes an inference smoke test, has a **higher** mean macro-F1 than the deployed model on the locked benchmark **and** not lower on the clean test split, no head loses more than 0.03 (garment type) / 0.05 (others) macro-F1 on the benchmark, and there is no train/evaluation overlap. Improvement below 0.01 or disagreement between the two evaluations is AMBIGUOUS (human decision); nothing is deployed automatically.

## 7. M40 (3/5/3/4) — training, independent test results and deployment (30 Sep 2026)

Everything in this section is computed by `ai_training/scripts/evaluate_m40.py` from files on the development laptop (full output: [m40_evaluation.json](m40_evaluation.json)). **The 90 % target was NOT reached for garment type, neckline or sleeve design, and only partly for sleeve length.** Read the honest summary first.

### 7.1 Summary

| Head | Forced answer, garment crop (test, n) | Forced answer, WHOLE photo (test, n) | Majority-class baseline | Previous model M13 (crop / whole photo) | Reaches 90 %? |
|---|---|---|---|---|---|
| garment_type | acc 77.0%, macro-F1 0.766 (n=126) | acc 66.7%, macro-F1 0.665 (n=126) | 34.9% | acc 77.0% / 52.4% | **No** |
| neckline_type | acc 73.0%, macro-F1 0.578 (n=790) | acc 51.4%, macro-F1 0.395 (n=790) | 66.7% | acc 52.9% / 18.9% | **No** |
| sleeve_length | acc 85.7%, macro-F1 0.835 (n=2704) | acc 79.0%, macro-F1 0.759 (n=2704) | 48.7% | acc 57.2% / 45.8% | **No** |
| sleeve_style | acc 95.2%, macro-F1 0.731 (n=413) | acc 91.3%, macro-F1 0.512 (n=413) | 88.9% | acc 4.4% / 0.2% | **No** |

* **Sleeve length** is the only head that comes close, and only because the app now answers it automatically when the score is high: with the threshold frozen on validation, the answered predictions were correct **92.2 %** of the time on garment crops (coverage 82 %) and **89.7 %** on whole photos (coverage 68 %) on the combined test set; on the Fashionpedia-only test set 95.5 % (crop, 90 % coverage) and 94.5 % (whole photo, 80 % coverage). On DeepFashion2 whole photos it was 83.0 % (57 % coverage), and on the 60-image benchmark 88.0 %. So "≥ 90 % when it answers" holds on two of four test sets, not everywhere.
* **Sleeve design accuracy (91–95 %) is misleading**: the majority class "none" is 88.9 % of the labelled test images (all sleeveless DeepFashion2 tops). Macro-F1 is 0.73 (crop) / 0.51 (whole photo); **bell-sleeve recall is 0.0** and **regular-sleeve has no trusted training or test examples at all**, so the head cannot be trusted and is always shown as "uncertain — please select".
* **Neckline** is barely above the majority-class baseline on crops (73.0 % vs 66.7 %) and **worse than it** on whole photos (51.4 %). **Garment type** is 77 % on crops and 67 % on whole photos (n = 126 human-verified images).
* **Whole photos are much harder than garment crops for both models** (M13 collapses to 19 % on neckline). Cropping to the garment before classification is therefore important; a detector is being trained by a second work stream and is not yet part of the product (see 7.6).

### 7.2 Test sets (none used for training, threshold selection or model selection)

| Set | Images | Source | Notes |
|---|---:|---|---|
| test_all | 3172 | DeepFashion2 official *validation* split (separate collection) + Fashionpedia test split | union of the next two |
| test_df2 | 1356 | DeepFashion2 tops: 496 short / 493 long / 367 sleeveless | sleeve length (+ sleeveless → sleeve design "none") only; near-duplicates of train/val removed |
| test_fp | 1816 | Fashionpedia, trusted labels, near-duplicates of train removed | garment 126 human-verified; neckline 790; sleeve length 1,348; sleeve design 46 |
| bench60 | 60 | the locked 60-image real-product benchmark used for M13 | 11–60 labelled images per head: indicative only |

Validation (2,848 images) was used only to choose the uncertainty thresholds and to stop training (best epoch 5). The test sets are disjoint from training by source image and, for DeepFashion2 and Fashionpedia, near-duplicate-filtered (dHash ≤ 4).

### 7.3 Full results per head (accuracy / macro-precision / macro-recall / macro-F1)

**test_all — garment crop**

| Head | n | M40 acc | M40 P | M40 R | M40 F1 | M13 acc | M13 F1 | M13 answers outside the 15 classes | majority |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| garment_type | 126 | 77.0% | 0.771 | 0.767 | 0.766 | 77.0% | 0.772 | 0 | 34.9% |
| neckline_type | 790 | 73.0% | 0.562 | 0.609 | 0.578 | 52.9% | 0.509 | 235 | 66.7% |
| sleeve_length | 2704 | 85.7% | 0.823 | 0.862 | 0.835 | 57.2% | 0.482 | 790 | 48.7% |
| sleeve_style | 413 | 95.2% | 0.850 | 0.686 | 0.731 | 4.4% | 0.082 | 222 | 88.9% |

**test_all — whole photo**

| Head | n | M40 acc | M40 P | M40 R | M40 F1 | M13 acc | M13 F1 | M13 answers outside the 15 classes | majority |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| garment_type | 126 | 66.7% | 0.666 | 0.664 | 0.665 | 52.4% | 0.515 | 0 | 34.9% |
| neckline_type | 790 | 51.4% | 0.400 | 0.464 | 0.395 | 18.9% | 0.160 | 216 | 66.7% |
| sleeve_length | 2704 | 79.0% | 0.753 | 0.784 | 0.759 | 45.8% | 0.335 | 792 | 48.7% |
| sleeve_style | 413 | 91.3% | 0.493 | 0.535 | 0.512 | 0.2% | 0.011 | 269 | 88.9% |

**test_df2 — garment crop**

| Head | n | M40 acc | M40 P | M40 R | M40 F1 | M13 acc | M13 F1 | M13 answers outside the 15 classes | majority |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| sleeve_length | 1356 | 79.1% | 0.791 | 0.801 | 0.791 | 36.6% | 0.365 | 513 | 36.4% |
| sleeve_style | 367 | 99.2% | 1.000 | 0.992 | 0.996 | 1.4% | 0.027 | 194 | 100.0% |

**test_df2 — whole photo**

| Head | n | M40 acc | M40 P | M40 R | M40 F1 | M13 acc | M13 F1 | M13 answers outside the 15 classes | majority |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| sleeve_length | 1356 | 70.2% | 0.705 | 0.712 | 0.700 | 30.3% | 0.265 | 494 | 36.4% |
| sleeve_style | 367 | 97.0% | 1.000 | 0.970 | 0.985 | 0.0% | 0.000 | 230 | 100.0% |

**test_fp — garment crop**

| Head | n | M40 acc | M40 P | M40 R | M40 F1 | M13 acc | M13 F1 | M13 answers outside the 15 classes | majority |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| garment_type | 126 | 77.0% | 0.771 | 0.767 | 0.766 | 77.0% | 0.772 | 0 | 34.9% |
| neckline_type | 790 | 73.0% | 0.562 | 0.609 | 0.578 | 52.9% | 0.509 | 235 | 66.7% |
| sleeve_length | 1348 | 92.4% | 0.636 | 0.609 | 0.621 | 78.0% | 0.573 | 277 | 61.1% |
| sleeve_style | 46 | 63.0% | 0.831 | 0.533 | 0.625 | 28.3% | 0.283 | 28 | 0.0% |

**test_fp — whole photo**

| Head | n | M40 acc | M40 P | M40 R | M40 F1 | M13 acc | M13 F1 | M13 answers outside the 15 classes | majority |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| garment_type | 126 | 66.7% | 0.666 | 0.664 | 0.665 | 52.4% | 0.515 | 0 | 34.9% |
| neckline_type | 790 | 51.4% | 0.400 | 0.464 | 0.395 | 18.9% | 0.160 | 216 | 66.7% |
| sleeve_length | 1348 | 87.8% | 0.609 | 0.572 | 0.587 | 61.4% | 0.390 | 298 | 61.1% |
| sleeve_style | 46 | 45.6% | 0.362 | 0.318 | 0.339 | 2.2% | 0.029 | 39 | 0.0% |

**bench60 — garment crop**

| Head | n | M40 acc | M40 P | M40 R | M40 F1 | M13 acc | M13 F1 | M13 answers outside the 15 classes | majority |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| garment_type | 60 | 76.7% | 0.769 | 0.767 | 0.764 | 78.3% | 0.786 | 0 | 33.3% |
| neckline_type | 32 | 62.5% | 0.509 | 0.717 | 0.518 | 56.2% | 0.790 | 12 | 71.9% |
| sleeve_length | 42 | 85.7% | 0.861 | 0.897 | 0.862 | 54.8% | 0.722 | 19 | 30.9% |
| sleeve_style | 11 | 72.7% | 0.938 | 0.604 | 0.688 | 36.4% | 0.333 | 6 | 0.0% |

**bench60 — whole photo**

| Head | n | M40 acc | M40 P | M40 R | M40 F1 | M13 acc | M13 F1 | M13 answers outside the 15 classes | majority |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| garment_type | 60 | 61.7% | 0.626 | 0.617 | 0.619 | 53.3% | 0.528 | 0 | 33.3% |
| neckline_type | 32 | 34.4% | 0.381 | 0.268 | 0.267 | 6.2% | 0.078 | 15 | 71.9% |
| sleeve_length | 42 | 73.8% | 0.843 | 0.768 | 0.793 | 28.6% | 0.324 | 18 | 30.9% |
| sleeve_style | 11 | 63.6% | 0.350 | 0.438 | 0.389 | 0.0% | 0.000 | 10 | 0.0% |

M13 is scored on exactly the same images. M13 predicts 28 classes; an answer outside the 15 selectable classes counts as wrong (it would make the user choose), and is never remapped. M13 was trained on Fashionpedia only, so the DeepFashion2 rows favour M40 by construction; **test_fp is the fair comparison** (M13's own domain): M40 is better or equal on every head (sleeve length 92.4 % vs 78.0 %, neckline 73.0 % vs 52.9 %, garment type tied at 77.0 %) on crops, and far better on whole photos.

### 7.4 Per-class results and confusion matrices (test_all, whole photo — the situation in the app)

**garment_type** — classes without any test example: none

| Class | test images | precision | recall | F1 |
|---|---:|---:|---:|---:|
| blouse | 42 | 0.775 | 0.738 | 0.756 |
| t-shirt | 40 | 0.564 | 0.550 | 0.557 |
| crop-top | 44 | 0.660 | 0.705 | 0.681 |

Confusion matrix (rows = true, columns = predicted): **blouse** → [31, 8, 3, 0] · **t-shirt** → [5, 22, 13, 0] · **crop-top** → [4, 9, 31, 0]; columns = ['blouse', 't-shirt', 'crop-top', '<outside 15 classes>']

**neckline_type** — classes without any test example: collared-neck

| Class | test images | precision | recall | F1 |
|---|---:|---:|---:|---:|
| round-neck | 527 | 0.826 | 0.467 | 0.596 |
| v-neck | 197 | 0.365 | 0.685 | 0.476 |
| square-neck | 24 | 0.207 | 0.250 | 0.226 |
| collared-neck | 0 | 0.000 | — | — |
| off-shoulder | 42 | 0.204 | 0.452 | 0.281 |

Confusion matrix (rows = true, columns = predicted): **round-neck** → [246, 212, 17, 0, 52, 0] · **v-neck** → [39, 135, 4, 0, 19, 0] · **square-neck** → [2, 13, 6, 0, 3, 0] · **collared-neck** → [0, 0, 0, 0, 0, 0] · **off-shoulder** → [11, 10, 2, 0, 19, 0]; columns = ['round-neck', 'v-neck', 'square-neck', 'collared-neck', 'off-shoulder', '<outside 15 classes>']

**sleeve_length** — classes without any test example: none

| Class | test images | precision | recall | F1 |
|---|---:|---:|---:|---:|
| sleeveless | 369 | 0.578 | 0.805 | 0.673 |
| short-sleeve | 1018 | 0.848 | 0.671 | 0.749 |
| long-sleeve | 1317 | 0.834 | 0.877 | 0.855 |

Confusion matrix (rows = true, columns = predicted): **sleeveless** → [297, 37, 35, 0] · **short-sleeve** → [140, 683, 195, 0] · **long-sleeve** → [77, 85, 1155, 0]; columns = ['sleeveless', 'short-sleeve', 'long-sleeve', '<outside 15 classes>']

**sleeve_style** — classes without any test example: regular-sleeve

| Class | test images | precision | recall | F1 |
|---|---:|---:|---:|---:|
| none | 367 | 0.954 | 0.970 | 0.962 |
| regular-sleeve | 0 | 0.000 | — | — |
| puff-sleeve | 33 | 0.525 | 0.636 | 0.575 |
| bell-sleeve | 13 | 0.000 | 0.000 | 0.000 |

Confusion matrix (rows = true, columns = predicted): **none** → [356, 0, 11, 0, 0] · **regular-sleeve** → [0, 0, 0, 0, 0] · **puff-sleeve** → [12, 0, 21, 0, 0] · **bell-sleeve** → [5, 0, 8, 0, 0]; columns = ['none', 'regular-sleeve', 'puff-sleeve', 'bell-sleeve', '<outside 15 classes>']

Confusion matrices for every set and mode (crop and whole photo) are in [m40_evaluation.json](m40_evaluation.json).

### 7.5 Uncertainty: what the app does with the scores

Thresholds were chosen on the **validation** split only (whole-photo mode): the smallest score at which accepted predictions are ≥ 90 % correct with ≥ 20 % coverage. Result: garment_type **none**, neckline_type **none**, sleeve_length **0.701**, sleeve_style 0.388. `none` means the head never reached 90 % on validation, so it is **always** shown as "Uncertain — please select" (the model's best guess and score are shown, but nothing is pre-selected). The sleeve-design threshold was additionally forced to *always uncertain* (`backend/app/ai/models/garment_multitask_m40_15class.thresholds.json`) because validation contains no regular-sleeve examples and therefore cannot reveal that head's main failure. The user must confirm every feature in any case, and a crop top vs T-shirt question is asked explicitly.

### 7.6 Deployment decision, hardware, files

* **Decision:** M40 is now the default suggestion model (M13 stays in `backend/app/ai/models/` as the rollback: set `GARMENT_MODEL_PATH` to it). Reason: on the large independent test sets it is better than or equal to M13 on every head in M13's own domain, dramatically better on whole photos, it outputs only selectable classes, and it passes loading / head-size / inference / API / browser tests. **This is not a claim that the model is accurate enough to trust**: the pre-stated targets were not met and the acceptance rule was fixed after seeing the results, so treat the decision as a practical improvement, not a validation.
* **Checkpoint:** `backend/app/ai/models/garment_multitask_m40_15class.pt`, SHA-256 `3ed45bc121c0eea82fb44280a6a5b5e2e2beaf43035fc501cf3e5089436c66be` (head sizes 3/5/3/4; not in Git). Training run, logs and history: `ai_training/data/training_runs/m40_df2_fp_15class/` (local).
* **Training:** `ai_training/scripts/train_multitask.py --config ai_training/config/m40_config.json --classes ai_training/config/classes_v2_15class.json --train-manifest ai_training/data/manifests_m40/train.jsonl --val-manifest ai_training/data/manifests_m40/val.jsonl --output-dir ai_training/data/training_runs/m40_df2_fp_15class` — YOLOv8n-cls backbone + 4 heads, seed 42, 3 head-only epochs then partial fine-tuning, 50 % of training images shown as whole photos, stopped early at epoch 8 (best epoch 5, validation mean macro-F1 0.723). **Hardware:** Windows laptop, CPU only (Intel Arc graphics, no CUDA), 15.4 GB RAM; 56 minutes.
* **Training data (trusted labels only):** 18,133 images — DeepFashion2 tops 9,000 (sleeve length, sleeveless → design "none") + Fashionpedia 9,133 with trusted labels (neckline, garment type, puff/bell). Class counts per head are in `ai_training/data/manifests_m40/counts.json`; dataset sources, licences and label guide: `ai_training/datasets/deepfashion2_tops/README.md`, `ai_training/datasets/LABEL_GUIDE_15class.md`.
* **Not in the model:** `collared-neck` and `regular-sleeve` have **no trusted example anywhere**, so M40 cannot recognise them (they remain selectable by the user). `square-neck` (126 train), `off-shoulder` (146), `bell-sleeve` (58) and `blouse` (87 human-verified) are too small to be reliable.
* **Garment detection / cropping:** a YOLOv8n garment detector (second work stream, `backend/app/ai/garment_detector.py`) now crops the garment before M40 classifies it, falling back to the whole photo when nothing is detected. Its independent test and the detector-crop vs whole-photo comparison on the M40 test sets are in [AI_DETECTOR.md](AI_DETECTOR.md). The M40 tables above (7.1–7.4) are the **whole-photo and ground-truth-crop** results, measured before the detector existed; they are not re-labelled. Both were measured on shop/street photos, not on user phone photos.
* **EXIF:** uploaded photos are now rotated upright before storage and before classification (previously a sideways phone photo reached the model sideways); covered by tests.

### 7.7 Known limitations of this evaluation

* The two test collections are labelled differently (DeepFashion2 by category, Fashionpedia by attributes); there is no single neutral dataset covering all four heads with human-verified labels, and no test images of user-uploaded photos.
* garment_type has only 126 human-verified test images (42 / 40 / 44), neckline classes square-neck (24) and off-shoulder (42) and sleeve design puff (33) / bell (13) are small: per-class numbers there are noisy.
* The benchmark (60 images) is tiny; differences of a few points on it are noise.
* Sleeve-design results are dominated by the sleeveless-derived "none" class.
* Thresholds came from one validation split; they were not re-tuned on the test sets, but the acceptance rule for deployment was chosen after the results were known.
