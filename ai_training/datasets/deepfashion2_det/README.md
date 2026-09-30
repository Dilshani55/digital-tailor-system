# DeepFashion2 garment-detection subset (top / outerwear / dress)

Built by `ai_training/scripts/v2/build_df2_detector_dataset.py` from the **local** DeepFashion2 copy
(`Dataset/archive/DeepFashion2`, Kaggle mirror *deepfashion2-original-with-dataframes*, named in the approved
proposal §4.3.2). No download.

* **Licence:** DeepFashion2 is released for **non-commercial research use** only. Images are hard-linked (not
  copied or published); `images/`, `labels/` and `data.yaml` are git-ignored. See also
  `../deepfashion2_tops/README.md`.
* **Classes:** 0 top (short/long-sleeve top, vest, sling) · 1 outerwear (short/long-sleeve outwear) · 2 dress
  (all four dress categories). Bottoms are not labelled. Boxes are DeepFashion2's human boxes.
* **Train:** 9,000 images sampled (seed 7) from the official DF2 *train* split; one third of the draw is images
  with a "no-wear" (product) view so shop-style photos are represented (3,460 such images).
* **Val (checkpoint selection):** 1,200 images from the official DF2 *validation* split, **excluding all 2,470
  images that `deepfashion2_tops` uses as classifier val/test**, so the classifier test stays independent.
* **Independent test:** `ai_training/scripts/v2/eval_detector.py` — DF2 validation images not in this val split, and
  DeepFashion-MultiModal shop photos with ground truth from human parsing masks (a different source).
* Counts: `build_stats.json`.
