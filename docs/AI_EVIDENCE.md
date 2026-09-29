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
