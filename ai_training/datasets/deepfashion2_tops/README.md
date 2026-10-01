# DeepFashion2 tops (sleeve-length subset)

Built by `ai_training/scripts/build_df2_tops_dataset.py` from the **local** DeepFashion2 copy in `ai_training/datasets/archive/` (moved from `Dataset/archive/`)
(`archive.zip`, downloaded 14 June 2026 by the project owner from the Kaggle mirror named in the research
proposal, section 4.3.2: *deepfashion2-original-with-dataframes*). No new download was needed.

## Source and licence — read before citing

* **Dataset:** DeepFashion2 — Y. Ge, R. Zhang, X. Wang, X. Tang, P. Luo, *"DeepFashion2: A Versatile Benchmark for
  Detection, Pose Estimation, Segmentation and Re-Identification of Clothing Images"*, CVPR 2019.
* **Licence:** released by its authors **for non-commercial research use**; the images were collected from
  shopping sites and users and remain the property of their owners. The archive on this laptop contains **no
  licence file**, and the Kaggle mirror states no separate licence, so the authors' non-commercial research terms
  are the only known terms. This use — a non-commercial final-year research project, images kept on the local
  machine, nothing redistributed, no images or derived crops committed to Git — is consistent with them, but
  **the project owner should confirm the terms on the DeepFashion2 / Kaggle page before submission.**
  Do not publish the images, the crops in this folder, or a model trained on them for commercial use.

## What is labelled (and what is not)

DeepFashion2 has a human-annotated **category** per garment instance. Only these are used:

| DeepFashion2 category | `sleeve_length` | `sleeve_style` |
|---|---|---|
| 1 short_sleeved_shirt | short-sleeve | masked (not labelled) |
| 2 long_sleeved_shirt | long-sleeve | masked |
| 5 vest, 6 sling | sleeveless | `none` (derived only from this explicit sleeveless category) |

DeepFashion2 has **no neckline, no garment-type (blouse / T-shirt / crop-top) and no sleeve-design (puff / bell /
regular) labels**. Those heads are **masked** for every record here; nothing was inferred or invented. Outerwear
(3, 4), dresses (10–13) and bottoms are not used.

## Preprocessing (all recorded in `annotations/summary.json`)

1. Keep photos with **exactly one top-category instance** (layered outfits are ambiguous), occlusion ≤ 2, bounding box
   ≥ 100 px per side.
2. EXIF orientation applied; `_crop.jpg` = bbox + 10 % margin (max side 320 px); `_full.jpg` = whole photo (max side 480 px).
3. **Splits:** train ← official DeepFashion2 *train*; val and test ← official *validation* split (a separate
   collection), divided by a hash of the image id. Sampling with seed 42.
4. **Near-duplicate control:** 64-bit dHash, Hamming ≤ 4 — val/test images with a near-twin in train, and test images
   with a near-twin in val, were removed (7 + 9 + 18 images).

## Counts

| Split | short-sleeve | long-sleeve | sleeveless | total |
|---|---:|---:|---:|---:|
| train | 3000 | 3000 | 3000 (1500 vest + 1500 sling) | 9000 |
| val | 400 | 397 | 317 | 1114 |
| test | 496 | 493 | 367 | 1356 |

Folders: `images/{train,val,test}/` (git-ignored — local data), `annotations/{train,val,test}.jsonl`
(git-ignored) and `annotations/summary.json` (tracked). Known limits: DeepFashion2 is dominated by shop and street
photos, "vest" and "sling" mix camisoles, tanks and vests, and it contains no neckline or sleeve-design information.
