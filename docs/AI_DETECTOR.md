# Garment detector — crop the garment before classification (1 Oct 2026)

**Why.** The classifiers were trained on garment crops, but the app used to classify the whole uploaded photo.
On whole photos M40 is much less accurate (neckline 51 % vs 73 % on crops; [AI_EVIDENCE.md](AI_EVIDENCE.md) §7.1).
The detector finds the garment so the classifier sees what it was trained on.

## Model

| Item | Value |
|---|---|
| Architecture | YOLOv8n object detector (transfer learning from the COCO-pretrained `yolov8n.pt` in the repo root, sha256 `f59b3d83…c83b36`) |
| Classes | 0 top (DeepFashion2 short/long-sleeve top, vest, sling) · 1 outerwear · 2 dress |
| Training data | 9,000 DeepFashion2 *train* images (seed 7; 3,460 contain a "no-wear" product view), 70 % used per epoch (`fraction 0.7`) — `ai_training/datasets/deepfashion2_det/` |
| Checkpoint selection | 1,200 DeepFashion2 *validation* images, **excluding all 2,470 images M40 uses as val/test** |
| Training | 10 epochs, imgsz 416, batch 8, seed 7, CPU only (no GPU on this laptop; 22-thread CPU), 3.21 h; run folder `ai_training/runs_v2/detector/df2_top_outer_dress_v1/` |
| Deployed weights | `backend/app/ai/models/garment_detector_v1.pt` (git-ignored local file), **sha256 `98e6e790a15b0a86472002324d40e888dabf4249ca20912c3bc2a8a37a29a077`** (= `best.pt` of the run) |
| Validation (selection split) | mAP50 0.753 (top 0.872, dress 0.805, outerwear 0.581), mAP50-95 0.621 |

## How the app uses it (`backend/app/ai/garment_detector.py`, `routes/images.py:_locate_garment`)

1. The photo is EXIF-rotated, then the detector runs (imgsz 512).
2. The most confident detection with score ≥ **MIN_SCORE 0.35** is used. 0.35 was **fixed before any testing**
   as a conventional moderate cut-off; it was **not tuned** on the M40 test sets, the detector test sets or the
   detector's validation split.
3. The tight box plus a 10 % margin (the same margin as the classifier's training crops) is passed to the
   classifier.
4. **Fallback:** no detector file, a detector error, or no box ≥ 0.35 → the whole photo is classified and the review
   screen says "The AI looked at the whole photo (no garment area was found), so its suggestions are less reliable."
5. If the box is a dress or outerwear, the review screen warns that only blouses, T-shirts and crop tops can be
   drafted. The response carries `garment_region` (class, score, boxes, used = garment_crop | full_image).

## Independent tests (never used for training, checkpoint selection or setting MIN_SCORE)

**All test photos are shop, street or model photos from DeepFashion2 / DeepFashion-MultiModal / Fashionpedia.
None are photos taken by users of this app with a phone; accuracy on real user uploads is not verified.**

### A. Does the app crop the right garment?  (`ai_training/scripts/v2/eval_detector.py`)

| Test set | n | Box returned | Correct top crop (class "top", IoU ≥ 0.5) | Correct main class |
|---|---:|---:|---:|---:|
| DeepFashion2 validation, single-top photos not in the detector's val split (seed 2026) | 600 | 96.2 % | **79.0 %** | 80.8 % |
| DeepFashion-MultiModal women's tops, ground truth from human parsing masks (different source) | 600 | 98.7 % | **90.2 %** | 91.5 % |

### B. Does the crop improve M40?  (`ai_training/scripts/v2/eval_m40_detector_crop.py`)

Same test manifests and the same frozen thresholds as `evaluate_m40.py`. "Whole photo" and "ground-truth crop" are
M40's own results from [m40_evaluation.json](m40_evaluation.json). Accuracy / macro-F1:

| Set | Head | n | Whole photo (old app) | **Detector crop (app now)** | Ground-truth crop (upper bound) |
|---|---|---:|---|---|---|
| test_all | garment_type | 126 | 0.667 / 0.665 | **0.762 / 0.759** | 0.770 / 0.766 |
| test_all | neckline_type | 790 | 0.514 / 0.395 | **0.663 / 0.503** | 0.730 / 0.578 |
| test_all | sleeve_length | 2704 | 0.790 / 0.759 | **0.840 / 0.817** | 0.857 / 0.835 |
| test_all | sleeve_style | 413 | 0.913 / 0.512 | **0.930 / 0.617** | 0.952 / 0.731 |
| test_df2 | sleeve_length | 1356 | 0.702 / 0.700 | **0.769 / 0.769** | 0.791 / 0.791 |
| test_df2 | sleeve_style | 367 | 0.970 / 0.985 | **0.989 / 0.995** | 0.992 / 0.996 |
| test_fp | garment_type | 126 | 0.667 / 0.665 | **0.762 / 0.759** | 0.770 / 0.766 |
| test_fp | neckline_type | 790 | 0.514 / 0.395 | **0.663 / 0.503** | 0.730 / 0.578 |
| test_fp | sleeve_length | 1348 | 0.878 / 0.587 | **0.911 / 0.613** | 0.924 / 0.621 |
| test_fp | sleeve_style | 46 | 0.457 / 0.339 | **0.457 / 0.464** | 0.630 / 0.625 |
| bench60 | garment_type | 60 | 0.617 / 0.619 | **0.717 / 0.718** | 0.767 / 0.764 |
| bench60 | neckline_type | 32 | 0.344 / 0.267 | **0.688 / 0.560** | 0.625 / 0.518 |
| bench60 | sleeve_length | 42 | 0.738 / 0.793 | **0.905 / 0.897** | 0.857 / 0.862 |
| bench60 | sleeve_style | 11 | 0.636 / 0.389 | **0.455 / 0.357** | 0.727 / 0.688 |

Sleeve length answered automatically (M40's validation threshold 0.7006), detector crop — accuracy when answered /
coverage: test_all 92.2 % / 79.7 %, test_df2 87.6 % / 70.9 %, test_fp 95.9 % / 88.6 %, bench60 96.9 % / 76.2 %.
Garment type, neckline and sleeve design stay "uncertain — please select" (M40 thresholds are null for them).

**Install decision.** Agreed rule before testing: install only if the detector crop beats the whole photo on
garment type, neckline *and* sleeve length. It does on every test set, so the weights were installed. Sleeve design
is mixed on the two tiny sets (n = 46, 11) and is always shown as uncertain. **The 90 % target is still not reached
for garment type (76 %) or neckline (66 %).** The remaining gap to ground-truth crops (neckline 0.66 vs 0.73) comes
from detector misses and mis-sized boxes.

Detector counts on the test photos: test_all 3,022 boxes (top 2,431, dress 275, outerwear 316) and 150 whole-photo
fallbacks out of 3,172. Outerwear/dress boxes on labelled tops are detector errors (or layered outfits).

Files: `ai_training/runs_v2/detector/df2_top_outer_dress_v1/independent_test/` (`detector_independent_test.json`,
`m40_detector_crop_eval.json`, `comparison_table.md`, per-image rows).

## Limits

* No user phone photos in any test; flat-lay/hanger shots are represented only through DeepFashion2 "no-wear"
  product images.
* "Outerwear" is the weakest class (val AP50 0.58); a top worn under a jacket may be cropped as outerwear.
* Licence: DeepFashion2 and DeepFashion-MultiModal are non-commercial research only; weights and data stay local.

## Reproduce (Windows, repo root)

```powershell
backend\venv\Scripts\python ai_training\scripts\v2\build_df2_detector_dataset.py --train 9000 --val 1200
backend\venv\Scripts\python -c "from ultralytics import YOLO; YOLO('ai_training/runs_v2/detector/yolov8n_coco_pretrained.pt').train(data='ai_training/datasets/deepfashion2_det/data.yaml', epochs=10, imgsz=416, batch=8, device='cpu', workers=2, fraction=0.7, seed=7, deterministic=True, patience=4, project='ai_training/runs_v2/detector', name='df2_top_outer_dress_v1')"
backend\venv\Scripts\python ai_training\scripts\v2\eval_detector.py --weights <best.pt> --out <dir> --n 600
backend\venv\Scripts\python ai_training\scripts\v2\eval_m40_detector_crop.py --detector <best.pt> --out <dir>
```
(Ultralytics may place the run under `runs/detect/...`; the run used here was moved to `ai_training/runs_v2/detector/`.)
