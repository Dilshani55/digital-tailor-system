# DeepFashion-MultiModal (DMM) — neckline / sleeve-length / crop-length evidence

## Source and licence

* **Dataset:** DeepFashion-MultiModal — Y. Jiang, S. Yang, H. Qiu, W. Wu, C. C. Loy, Z. Liu, *"Text2Human:
  Text-Driven Controllable Human Image Generation"*, ACM TOG 2022. <https://github.com/yumingj/DeepFashion-MultiModal>
* **Files:** `images.zip` (44,096 JPGs, ≈5.4 GB), `labels.zip` (shape / fabric / pattern text files), `segm.zip`
  (12,701 human-parsing masks), downloaded with `gdown` from the authors' Google Drive folder
  `1An2c_ZCkeGmhJg0zUjtZF46vyJgQwIr2` on **30 Sep 2026**.
* **Licence:** "The DeepFashion-MultiModal dataset is available for **non-commercial research purposes only**."
  The images come from DeepFashion (In-shop); DeepFashion's release agreement forbids redistribution. This project
  is non-commercial research; everything stays on this laptop, `raw/`, `images/`, `annotations/*.jsonl` and any crops
  are git-ignored. Do not publish the images, crops or a model trained on them for commercial use.
* Download approval: the project owner's standing rule (datasets whose licence clearly permits research use).

## What the labels mean (from the authors' README)

`labels/shape/shape_anno_all.txt`: one line per image, 12 integers.
Index 0 sleeve length (0 sleeveless, 1 short, 2 medium, 3 long, 4 not long, 5 NA); index 9 neckline (0 V-shape,
1 square, 2 round, 3 standing, 4 lapel, 5 suspenders, 6 NA); index 11 upper clothing covering navel (0 no, 1 yes,
2 NA). Parsing masks: 1 top, 2 outer, 3 skirt, 4 dress, … (24 classes).

## Mapping to the project's 15 classes

Done by `ai_training/scripts/v2/build_dmm_annotations.py` (see its docstring). Only source labels are used; a
value outside the 15 classes is **masked, never remapped**: medium sleeves, "standing" and "suspenders" necklines
and all NA values are masked; necklines are masked on back views; sleeve design is `none` only for sleeveless
(DMM has no puff / bell / regular information). `lapel → collared-neck` is only enabled after a visual check.
Garment type comes from the shop category in the file name (`Blouses_Shirts` → blouse, `Tees_Tanks` /
`Graphic_Tees` → t-shirt) and becomes crop-top when the navel is not covered; these are *merchant categories and a
length rule*, recorded as provenance `dmm_shop_category` / `dmm_navel_uncovered`, not human garment-type labels.

## Scope and splits

WOMEN images of Blouses_Shirts, Tees_Tanks and Graphic_Tees. Every item (`id_XXXXXXXX`) has several views; all
views of one item stay in one split (stable hash, 70 / 15 / 15), so the same garment never crosses splits.

## Known limits

Plain-background shop photos of models (a different domain from street photos, close to shop uploads); few
square necklines (≈250 women's images); no sleeve-design labels; blouse vs shirt is not separated by the shop
category.
