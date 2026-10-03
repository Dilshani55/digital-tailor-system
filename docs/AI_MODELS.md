# AI models — what they are, what they were trained on, what they achieve (2 Oct 2026)

The AI part only **suggests** a design from a garment photo. The user confirms or corrects every feature, and only
the confirmed design reaches the pattern engine.

## 1. Architecture

```
photo ─► garment detector (YOLOv8n) ─► crop + 10 % margin, padded to a square
      ─► garment type   MobileNetV3-Large   blouse · t-shirt
      ─► neckline       YOLOv8n-cls         round · V · square · collared
      ─► sleeve length  YOLOv8n-cls         sleeveless · short · long
      ─► sleeve design  YOLOv8n-cls         regular · puff · bell      (not asked when the garment is sleeveless: style = none)
```

Four separate classifiers, one per feature, each in its own file in `backend/model/`. Loading and inference:
`backend/app/ai/garment_models.py`; the picture preparation shared with training: `backend/app/ai/preprocess.py`.
All weights are PyTorch `.pt` files (TensorFlow / Keras is not used).

| File | Model | SHA-256 (first 16) |
|---|---|---|
| `garment_detector.pt` | YOLOv8n detector: top / outerwear / dress | `98e6e790a15b0a86` |
| `garment_mobilenetv3.pt` | garment type | `d964ee832c94e39f` |
| `neckline_yolov8.pt` | neckline | `257aa70a91994cf2` |
| `sleeve_length_yolov8.pt` | sleeve length | `0e513c2604e8444b` |
| `sleeve_design_yolov8.pt` | sleeve design | `5d7ae2a0cd8363c4` |

**When is a suggestion filled in automatically?** Only when the model's score is at or above its threshold in
`backend/model/thresholds.json`. The threshold is the lowest score at which the answers on the **validation** photos
are at least 90 % correct while at least 20 % of photos are still answered; it is never chosen on test photos. A
model for which no such score exists has no threshold and its feature is always shown as "please select" (with the
model's guess and score next to it).

## 2. Data

Sources (all non-commercial research use; images and weights stay on this computer):

| Dataset | Gives labels for |
|---|---|
| Fashionpedia (annotations CC BY 4.0) | neckline, sleeve length, puff / bell sleeves; garment type (human-verified subset) |
| DeepFashion2 | sleeve length; training data of the garment detector |
| DeepFashion-MultiModal | sleeve length and neckline (human shape annotation); garment type **by proxy** (shop category) |
| Human review of 1 Oct 2026 | collared neck, regular sleeve |

Photos used (training classes are balanced: a big class is capped, a small one is repeated; validation and test
photos are never repeated):

| Model | Training photos per class (× = repeated) | Validation | Test |
|---|---|---|---|
| Garment type | blouse 3,000 · t-shirt 3,000 (almost all proxy labels) | 600 · 600 | 42 · 40 human-verified; plus 1,908 proxy-labelled |
| Neckline | round 2,500 · V 1,762 · square 189 ×5 · collared 166 ×5 | 100 · 100 · 32 · 47 | 527 · 197 · 24 · 64 |
| Sleeve length | sleeveless 4,000 · short 4,000 · long 4,000 | 600 · 600 · 600 | 369 · 1,018 · 1,317 |
| Sleeve design | regular 169 ×2 · puff 147 ×3 · bell 61 ×5 | 52 · 20 · 17 | 66 · 35 · 13 |

Checks made on the data before training (1 Oct 2026):

* No photo, garment item or near-identical photo (perceptual hash) is shared between training and validation / test.
  An earlier version of the data had 36 test photos with a near-identical training photo; they were removed.
* 4,481 sleeveless knit tops (tank tops) carried the proxy label "t-shirt"; they are not used as T-shirts.
* Necklines and sleeves outside the classes (boat, halter, off-shoulder, three-quarter sleeve, raglan ...) are left
  out, never mapped to a look-alike class.

**Label quality of the two reviewed classes.** "Collared neck" and "regular sleeve" had no trusted label in any
dataset. 725 candidate photos were answered by **one reviewer in about 24 minutes**; a later look at a sample found
mostly correct answers and a few jackets and coats among them. A second reviewer has not checked them
([HUMAN_VALIDATION.md](HUMAN_VALIDATION.md) §5). The results for these two classes carry that uncertainty.

## 3. Training

One run per model, seed 42, CPU only, ImageNet-pretrained weights, input 224 px. The epoch with the best validation
result is kept. No model was retrained after looking at test results.

| Model | Settings | Time | Kept epoch |
|---|---|---|---|
| Garment type | 14 epochs, AdamW (backbone 1e-4, head 1e-3), label smoothing 0.05, best by validation macro-F1 | 77 min | 11 (validation macro-F1 0.901) |
| Neckline | up to 30 epochs, patience 8 | 47 min | 10 (stopped early after 18) |
| Sleeve length | 20 epochs, patience 6 | 121 min | 16 |
| Sleeve design | up to 60 epochs, patience 15 | 20 min | 14 (stopped early after 29) |

Scripts and commands: [backend/training/README.md](../backend/training/README.md).

## 4. Results

Accuracy / macro-F1 on photos never used for training, run through the same inference code as the app
(`backend/training/evaluate_models.py`; full output in `backend/training/runs/evaluation.md` and `.json`).
**Detector crop** is what the app does. "Dataset crop" uses the dataset's own garment box (an upper bound for the
detector); "whole photo" is what happens when no garment is found.

### Test set

| Model | n | Majority class | **Detector crop** | Dataset crop | Whole photo |
|---|---:|---:|---|---|---|
| Garment type (human-verified labels) | 82 | 0.512 | **0.890 / 0.890** | 0.890 / 0.890 | 0.732 / 0.730 |
| Neckline | 812 | 0.649 | **0.712 / 0.596** | 0.773 / 0.674 | 0.599 / 0.416 |
| Sleeve length | 2,704 | 0.487 | **0.880 / 0.865** | 0.913 / 0.901 | 0.693 / 0.655 |
| Sleeve design | 114 | 0.579 | **0.605 / 0.455** | 0.623 / 0.497 | 0.535 / 0.367 |

### Per class (test set, detector crop)

| Model | Class | Test photos | Precision | Recall | F1 |
|---|---|---:|---:|---:|---:|
| Garment type | blouse | 42 | 0.90 | 0.88 | 0.89 |
| Garment type | t-shirt | 40 | 0.88 | 0.90 | 0.89 |
| Neckline | round | 527 | 0.89 | 0.73 | 0.80 |
| Neckline | V | 197 | 0.51 | 0.74 | 0.61 |
| Neckline | square | 24 | 0.35 | 0.46 | 0.40 |
| Neckline | collared | 64 | 0.56 | 0.59 | 0.58 |
| Sleeve length | sleeveless | 369 | 0.85 | 0.79 | 0.82 |
| Sleeve length | short | 1,018 | 0.89 | 0.86 | 0.87 |
| Sleeve length | long | 1,317 | 0.89 | 0.92 | 0.90 |
| Sleeve design | regular | 66 | 0.69 | 0.73 | 0.71 |
| Sleeve design | puff | 35 | 0.56 | 0.57 | 0.56 |
| Sleeve design | bell | 13 | 0.13 | 0.08 | 0.10 |

### What is filled in automatically (detector crop)

| Model | Threshold (from validation) | Validation: correct when answered / photos answered | Test: correct when answered / photos answered |
|---|---:|---|---|
| Garment type | 0.557 | 90.0 % / 97.9 % | 90.0 % / 97.6 % |
| Neckline | 0.955 | 90.3 % / 55.2 % | 91.0 % / 42.5 % |
| Sleeve length | 0.424 | 94.0 % / 100 % | **88.1 %** / 99.8 % |
| Sleeve design | none | – | never: always "please select" |

### Other sets

| Model | Set | n | Detector crop | Automatic answers |
|---|---|---:|---|---|
| Garment type | DeepFashion-MultiModal, proxy labels | 1,908 | 0.902 / 0.895 | 90.8 % on 98.0 % |
| Garment type | 40 web product photos (benchmark) | 40 | 0.875 / 0.875 | 89.5 % on 95.0 % |
| Neckline | DeepFashion-MultiModal (no collared photos, 8 square) | 1,170 | 0.879 / 0.612 | 95.9 % on 64.3 % |
| Neckline | benchmark (round and V only) | 31 | 0.677 / 0.636 | 86.7 % on 48.4 % |
| Sleeve length | DeepFashion-MultiModal | 2,652 | 0.975 / 0.973 | 97.5 % on 99.9 % |
| Sleeve length | benchmark (short and long only) | 42 | 0.929 / 0.935 | 92.9 % on 100 % |
| Sleeve design | benchmark (puff 8, bell 3) | 11 | 0.636 / 0.438 | never |

### Experiment: more training photos from the Kaggle Fashion Product Images dataset (3 Oct 2026) - not adopted

*Data.* Kaggle "Fashion Product Images Dataset" (paramaggarwal, MIT licence), the full version with one JSON file per
product. Used: women's and girls' topwear (Tops, Tshirts, Shirts, Tunics, Kurtis, Kurtas) whose shop-entered "Neck",
"Collar" or "Sleeve Styling" maps onto an app class: 3,307 products, each cropped with the app's garment detector
(`backend/training/prepare_kaggle.py`). Round and scoop neck -> round-neck; V-neck -> v-neck; square neck ->
square-neck; mandarin, polo, shirt, spread and other collars -> collared-neck; regular / puff / bell and flared
sleeves -> the three sleeve designs. The labels are the shop's; nobody checked them for this project.

*New unique training photos.* Neckline: collared 166 -> 788, square 189 -> 253, V 1,762 -> 2,192 (round stays at the
2,500 cap). Sleeve design: regular 169 -> 592, puff 147 -> 281, bell 61 -> 72 (the dataset has almost no bell sleeves).

*Training.* The same YOLOv8n-cls model, settings and seed; only the training photos differ; the validation photos and
the frozen test set are unchanged (`backend/training/train_kaggle.py`; sleeve-design training cap raised from 400 to
800 before training). Weights: `backend/training/runs/candidate_kaggle/` (not in Git).

*Result* (same frozen test set, detector crop, accuracy / macro-F1; `runs/evaluation_candidate_kaggle.md`):

| Model | Current | With the Kaggle photos | Decision (rule: macro-F1 higher and accuracy not lower) |
|---|---|---|---|
| Neckline (812 test photos) | 0.712 / 0.596 | 0.720 / 0.586 | not adopted: macro-F1 lower |
| Sleeve design (114 test photos) | 0.605 / 0.455 | 0.614 / 0.446 | not adopted: macro-F1 lower |

Per class, the neckline model found more collared necks (recall 0.59 -> 0.80, F1 0.58 -> 0.60) and V-necks (F1
0.61 -> 0.63) but fewer square necks (F1 0.40 -> 0.31); on the shop test set (DeepFashion-MultiModal, 1,170 photos)
its accuracy fell from 0.879 to 0.838, and on validation it was slightly worse (0.718 -> 0.706 macro-F1). The
sleeve-design model was better for regular sleeves, worse for puff sleeves, unchanged for bell sleeves (F1 0.10),
and clearly worse on validation (0.594 -> 0.426 macro-F1). So more shop photos with shop labels did not, on this
test set, improve the two weakest models: the missing piece is still labelled bell sleeves and square necks.

## 5. How to read these numbers

* **Garment type** is the strongest result, but the human-verified test set is small (82 photos): one photo is 1.2
  percentage points. The training labels are shop categories, not a tailor's judgement of woven against knit.
* **Sleeve length** is good on shop photos (97.5 %) and weaker on the mixed test set (88.0 %). Its automatic answers
  were 94 % correct on validation but **88.1 % on the test set, below the 90 % aim**. The threshold was not changed
  after seeing this, because a threshold tuned on test photos would not be an honest measurement.
* **Neckline** as a forced answer is only moderately better than always answering "round" (0.712 against 0.649).
  It is useful because of the threshold: on the 42.5 % of test photos where it is confident it is 91 % correct, and
  the rest are left to the user. Square and collared necks rest on 24 and 64 test photos.
* **Sleeve design does not work well enough**: 0.605 accuracy against 0.579 for always answering "regular", and bell
  sleeves are almost never recognised (13 test photos, 61 training photos). It is therefore never filled in
  automatically. More labelled puff, bell and regular sleeves are needed.
* The gap between "detector crop" and "dataset crop" (neckline 0.71 against 0.77) is the cost of detector misses and
  loose boxes. The gap to "whole photo" shows why the detector is used.
* All test photos are shop, street or model photos from the datasets. **No photo taken by a user of this app with a
  phone is in any test set**, so accuracy on real uploads is not measured.
* Each model was trained once. Differences of a few points on the small sets are within noise.
* A 90 % accuracy target for every feature is **not** reached.

## 6. Garment detector

YOLOv8n object detector (COCO-pretrained, then trained on 9,000 DeepFashion2 training images, 10 epochs, CPU;
classes top / outerwear / dress; validation mAP50 0.753). The app uses the most confident box with score ≥ 0.35 (a
value fixed before testing, not tuned), adds a 10 % margin and falls back to the whole photo when there is no box;
the review screen then says so.

Independent test of the crop (photos never used for training or selection): the correct top was cropped (class
"top", IoU ≥ 0.5) in 79.0 % of 600 DeepFashion2 validation photos and 90.2 % of 600 DeepFashion-MultiModal photos.
"Outerwear" is its weakest class: a top worn under a jacket may be cropped as outerwear.

## 7. Earlier models (history)

| Model | What it was | Outcome |
|---|---|---|
| M13 | one YOLOv8n-cls backbone with four heads (3 / 10 / 6 / 9 classes), Fashionpedia | first deployed model; weak on neckline and sleeve style |
| M40 | same design with 3 / 5 / 3 / 4 classes, DeepFashion2 + Fashionpedia | deployed until 1 Oct 2026. Detector crop: garment type 0.762 / 0.759 (n = 126, three classes), neckline 0.663 / 0.503 (five classes), sleeve length 0.840 / 0.817, sleeve style 0.930 / 0.617; only sleeve length was filled in automatically; could not recognise regular sleeve or collared neck (no labels) |
| M41 | experiment with proxy garment labels | not deployed: better than M40 for sleeve length (0.861) but worse for neckline (0.644), so it did not clearly beat M40; the tank-top label error above was found in its data |
| M42 | single four-head model on the audited data | training stopped on 1 Oct 2026 when the project changed to four separate models; never evaluated |

The M40 numbers are **not directly comparable** with section 4: the classes changed (crop top and off-shoulder were
removed; regular sleeve and collared neck became recognisable) and the test sets were cleaned of near-duplicates.
The four separate models replaced M40 by a project decision (1 Oct 2026), not because of a like-for-like comparison.
The code of the earlier pipeline is in the Git history up to commit `9b7df22` (folder `ai_training/`).

## 8. Reproduce

```powershell
backend\venv\Scripts\python backend\training\prepare_datasets.py
backend\venv\Scripts\python backend\training\train_models.py
backend\venv\Scripts\python backend\training\evaluate_models.py
```
