# M41 — documented experiment: M40 + DeepFashion-MultiModal data (1 Oct 2026) — not deployed, not a candidate

**Result in one line:** on the unchanged M40 test set (`test_all`) with the detector crop the app uses, M41 is
better than M40 for sleeve length (0.840 → 0.861), equal within noise for garment type (0.762 → 0.770, n = 126,
i.e. one photo), and **worse for neckline (0.663 → 0.644)**. M41 therefore does **not** clearly beat M40, and
**M40 stays the default model**. Switching would need the other work stream's agreement and the project owner's
decision. No head reaches 90 % on the independent test set.

## What changed (only the data)

| Item | Value |
|---|---|
| Settings | identical to M40 (`ai_training/config/m41_config.json` = `m40_config.json` + provenance weights for the new sources); YOLOv8n-cls backbone + 3/5/3/4 heads, seed 42, 3 head-only epochs + 6 partial fine-tuning epochs, 50 % whole-photo training |
| Training data | `ai_training/data/manifests_m41/train.jsonl` = M40 train (9,133 Fashionpedia + 9,000 DeepFashion2) **+ 13,716 DeepFashion-MultiModal (DMM)** records = 31,849 |
| DMM labels used | sleeve length and neckline (V / round / square) from DMM's human shape annotation; sleeve design `none` only for sleeveless; garment type from the shop category / navel rule (**proxies**, weight 0.5); `lapel → collared` candidates **masked** (collared-neck still has 0 trusted examples); see `ai_training/datasets/deepfashion_multimodal/README.md` |
| Crops | DMM crops made by the deployed garment detector (same rule as the app: tight box + 10 %; whole photo when no box) |
| Leakage control | M40 test files copied byte-identical (sha256 verified); 18 DMM train + 2 DMM val photos that near-duplicated (dHash ≤ 4) any of the 6,404 M40 test photos removed; 246 DMM test photos that near-duplicated a DMM train photo removed; DMM split by garment item |
| Training | 65 min, CPU only (no GPU). Best validation epoch = **epoch 9, the last allowed epoch**: training stopped at the epoch limit while validation was still improving, so M41 is **not converged** and is not a final or best-possible model |
| Checkpoint | `ai_training/data/training_runs/m41_dmm_df2_fp_15class/checkpoints/best.pt` (local, not deployed) |

## Test results (accuracy / macro-F1)

Computed by `ai_training/scripts/v2/eval_m41.py` (uses `evaluate_m40.py` read-only and the detector-crop script);
table: `ai_training/data/training_runs/m41_dmm_df2_fp_15class/evaluation/comparison_m41_vs_m40.md`.
"Detector crop" is what the app does now; "GT crop" uses the dataset's own garment box (upper bound).

| Set | Head | n | Majority | M40 whole | M41 whole | M40 detector crop | **M41 detector crop** | M40 GT crop | M41 GT crop |
|---|---|---:|---:|---|---|---|---|---|---|
| test_all | garment_type | 126 | 0.318 | 0.667 / 0.665 | 0.556 / 0.514 | 0.762 / 0.759 | **0.770 / 0.764** | 0.770 / 0.766 | 0.746 / 0.742 |
| test_all | neckline_type | 790 | 0.667 | 0.514 / 0.395 | 0.482 / 0.387 | 0.663 / 0.503 | **0.644 / 0.500** | 0.730 / 0.578 | 0.709 / 0.577 |
| test_all | sleeve_length | 2704 | 0.487 | 0.790 / 0.759 | 0.816 / 0.792 | 0.840 / 0.817 | **0.861 / 0.841** | 0.857 / 0.835 | 0.879 / 0.862 |
| test_all | sleeve_style | 413 | 0.889 | 0.913 / 0.512 | 0.906 / 0.635 | 0.930 / 0.617 | **0.932 / 0.645** | 0.952 / 0.731 | 0.940 / 0.682 |
| test_df2 | sleeve_length | 1356 | 0.364 | 0.702 / 0.700 | 0.727 / 0.729 | 0.769 / 0.769 | **0.791 / 0.793** | 0.791 / 0.791 | 0.811 / 0.813 |
| test_fp | sleeve_length | 1348 | 0.611 | 0.878 / 0.587 | 0.904 / 0.604 | 0.911 / 0.613 | **0.932 / 0.625** | 0.924 / 0.621 | 0.947 / 0.633 |
| test_fp | sleeve_style | 46 | 0.000 | 0.457 / 0.339 | 0.565 / 0.583 | 0.457 / 0.464 | **0.565 / 0.529** | 0.630 / 0.625 | 0.674 / 0.597 |
| bench60 | garment_type | 60 | 0.333 | 0.617 / 0.619 | 0.483 / 0.430 | 0.717 / 0.718 | **0.750 / 0.748** | 0.767 / 0.764 | 0.700 / 0.699 |
| bench60 | neckline_type | 32 | 0.719 | 0.344 / 0.267 | 0.438 / 0.393 | 0.688 / 0.560 | **0.781 / 0.724** | 0.625 / 0.518 | 0.719 / 0.642 |
| bench60 | sleeve_length | 42 | 0.309 | 0.738 / 0.793 | 0.881 / 0.896 | 0.905 / 0.897 | **0.929 / 0.923** | 0.857 / 0.862 | 1.000 / 1.000 |
| **test_dmm** | garment_type | 2844 | 0.488 | 0.415 / 0.412 | 0.731 / 0.705 | 0.413 / 0.416 | **0.781 / 0.760** | 0.415 / 0.416 | 0.787 / 0.768 |
| **test_dmm** | neckline_type | 1170 | 0.850 | 0.305 / 0.233 | 0.695 / 0.411 | 0.452 / 0.334 | **0.815 / 0.512** | 0.415 / 0.309 | 0.832 / 0.529 |
| **test_dmm** | sleeve_length | 2652 | 0.205 | 0.891 / 0.867 | 0.969 / 0.966 | 0.934 / 0.919 | **0.972 / 0.969** | 0.936 / 0.922 | 0.968 / 0.965 |
| **test_dmm** | sleeve_style | 1436 | 1.000 | 0.987 / 0.993 | 0.999 / 1.000 | 0.996 / 0.998 | **0.998 / 0.999** | 0.996 / 0.998 | 0.998 / 0.999 |

(test_fp garment/neckline equal test_all's, because all labelled garment/neckline test images are Fashionpedia.)

### How to read this honestly

* **test_all is the fair comparison** (unchanged images, not from DMM). There M41's gains are small, garment type is
  within noise (n = 126), and neckline is worse.
* **test_dmm is in-distribution for M41** (same source as 13,716 of its training images, although item-disjoint and
  near-duplicate-filtered) and out-of-distribution for M40, so the large M41 gains there mostly show that M41 learned
  that photo style. On test_dmm the garment-type labels are shop-category / navel-rule **proxies**, and M41's
  neckline accuracy (0.815) is **below the majority baseline (0.850)** because almost all DMM necklines are round.
* Sleeve design accuracy is dominated by "none" (sleeveless); macro-F1 is the meaningful number. Regular-sleeve still
  has **no trusted training or test data** and collared-neck has none either, so neither can be recognised.

### Uncertainty thresholds (chosen on M41 validation only — and why they cannot be used as they are)

M41's validation-selected thresholds: garment 0.898, neckline none, sleeve length 0.431, sleeve design 0.471.
With the detector crop on test_all: garment answered 51.6 % of the time with 90.8 % accuracy (≈ 65 photos, wide
uncertainty); sleeve length answered 99.1 % with 86.6 % — **below the 90 % target and worse than M40 (92.2 % at
79.7 % coverage)**. The M41 validation split is dominated by easier DMM photos, so its thresholds are too lenient
for other photo types. Sleeve design would have to stay forced to "uncertain" (no regular-sleeve data), as for M40.

## Decision and next steps

* **Not deployed and not recommended for deployment.** Both work streams agreed to keep M40 as the default; `DEPLOYED_MODEL_PATH` and M40's thresholds are unchanged. M41 is kept on disk only as a documented experiment.
* What would most likely help: human review of the `candidate_dmm_lapel_needs_human_review` records (collared),
  human garment-type labels for DMM (instead of proxies), more square-neck / off-shoulder / bell-sleeve / regular-sleeve
  examples, a longer training schedule (M41 was still improving at its last epoch), thresholds chosen on a validation
  mix that matches the test photo mix, and a test set of real user phone photos (none exists).

## Reproduce (Windows, repo root)

```powershell
backend\venv\Scripts\python ai_training\scripts\v2\build_dmm_annotations.py --lapel-as-collared
backend\venv\Scripts\python ai_training\scripts\v2\crop_with_detector.py --dataset ai_training/datasets/deepfashion_multimodal --detector backend/app/ai/models/garment_detector_v1.pt
backend\venv\Scripts\python ai_training\scripts\v2\build_m41_manifests.py
backend\venv\Scripts\python ai_training\scripts\train_multitask.py --config ai_training/config/m41_config.json --classes ai_training/config/classes_v2_15class.json --train-manifest ai_training/data/manifests_m41/train.jsonl --val-manifest ai_training/data/manifests_m41/val.jsonl --output-dir ai_training/data/training_runs/m41_dmm_df2_fp_15class
backend\venv\Scripts\python ai_training\scripts\v2\eval_m41.py --m41 ai_training/data/training_runs/m41_dmm_df2_fp_15class/checkpoints/best.pt --out ai_training/data/training_runs/m41_dmm_df2_fp_15class/evaluation
backend\venv\Scripts\python ai_training\scripts\v2\summarise_m41.py
```
