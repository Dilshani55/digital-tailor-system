# Training the garment models

Four separate image classifiers suggest a design from a garment photo. The app (`backend/app/ai/garment_models.py`)
loads them from `backend/model/`; the user always confirms the design.

| Model | Classes | Architecture | Weights file |
|---|---|---|---|
| Garment type | blouse, t-shirt | MobileNetV3-Large (torchvision, ImageNet-pretrained) | `backend/model/garment_mobilenetv3.pt` |
| Neckline | round-neck, v-neck, square-neck, collared-neck | YOLOv8n-cls (Ultralytics, ImageNet-pretrained) | `backend/model/neckline_yolov8.pt` |
| Sleeve length | sleeveless, short-sleeve, long-sleeve | YOLOv8n-cls | `backend/model/sleeve_length_yolov8.pt` |
| Sleeve design | regular-sleeve, puff-sleeve (bell-sleeve removed 3 Oct 2026) | YOLOv8n-cls | `backend/model/sleeve_design_yolov8.pt` |

The sleeve-design model is asked only when the garment has sleeves; a sleeveless garment has sleeve style `none` by
definition. A fifth file, `backend/model/garment_detector.pt` (YOLOv8n detector: top / outerwear / dress), finds the
garment in the photo so the classifiers look at the garment and not the background.

Weights, datasets and run outputs are local files and are **not** in Git (size, and the datasets' licences do not
allow redistribution).

## Run (Windows, repository root, CPU is enough)

```powershell
backend\venv\Scripts\python backend\training\prepare_datasets.py     # one image folder per model (about 10 minutes)
backend\venv\Scripts\python backend\training\train_models.py         # all four, one after the other (several hours)
backend\venv\Scripts\python backend\training\evaluate_models.py      # test results + thresholds -> backend/model/thresholds.json
```

`train_models.py neckline` (or `garment`, `sleeve_length`, `sleeve_design`) trains one model;
`evaluate_models.py neckline` evaluates one. Settings (epochs, patience, learning rates, seed 42) are constants at
the top of `train_models.py`.

## Part models (neck area, sleeves)

A neckline or a sleeve is a small part of a garment photo. Fashionpedia marks every neckline, collar and sleeve with
its own box and style label, so the neckline and sleeve-design models can be trained on that part alone, and a
YOLOv8n **part detector** (classes `neck`, `sleeve`) finds the part inside the garment area in the app.

```powershell
backend\venv\Scripts\python backend\training\prepare_part_datasets.py                                   # datasets/parts/
backend\venv\Scripts\python backend\training\train_models.py neckline_part sleeve_design_part part_detector
backend\venv\Scripts\python backend\training\evaluate_models.py --candidate neckline sleeve_design     # runs/evaluation_candidate.md
```

The trained part models go to `runs/candidate_model/`, not to `backend/model/`.

**Switching to a candidate (rule written on 2 Oct 2026, before the candidates were evaluated).** A candidate replaces
the current model of a feature only if, on the same frozen test set and with the app's own pipeline ("detector
crop"), its macro-F1 is higher **and** its accuracy is not lower. Otherwise the current model stays and the
candidate's results are reported as an experiment. Thresholds are chosen on validation photos only, as before.

## Files

| File | What it does |
|---|---|
| `common.py` | the four tasks, their classes, and how a dataset record becomes a label for each task |
| `prepare_datasets.py` | builds `datasets/attributes/<task>/train|val|test/<class>/*.jpg` (garment crop padded to a square, 256 px) and `eval.jsonl` (validation and test photos for the evaluation with the detector) |
| `train_models.py` | trains the models; keeps the weights of the best validation epoch; copies them to `backend/model/` |
| `prepare_kaggle.py` | adds the Kaggle Fashion Product Images photos (shop labels for neck, collar, sleeve styling) to the neckline and sleeve-design TRAINING folders (`datasets/attributes_kaggle/`); validation and test unchanged; photos cropped with the app's garment detector |
| `train_kaggle.py` | trains neckline and sleeve design on those folders with the same settings into `runs/candidate_kaggle/` (never into `backend/model/`) |
| `evaluate_models.py` | runs the models through the production inference code on photos never trained on, three ways (detector crop = what the app does, the dataset's own crop, the whole photo); chooses the thresholds on validation; writes `runs/evaluation.json` and `runs/evaluation.md`; `--candidate-dir=<folder>` tests the models in another folder (report `runs/evaluation_<folder name>.md`) |

## Data

Source: the audited manifests in `data/manifests_m42/` (records from Fashionpedia, DeepFashion2 and
DeepFashion-MultiModal plus the human label review of 1 Oct 2026). The scripts that built those manifests (dataset
extraction, audit, review queue and review screen) were part of the earlier single-model pipeline and are in the Git
history up to commit `9b7df22` under `ai_training/`; their findings are summarised in `docs/AI_MODELS.md`.

| Dataset | Licence | Gives labels for |
|---|---|---|
| Fashionpedia | annotations CC BY 4.0 | neckline, sleeve length, puff / bell sleeves; garment type (human-verified subset) |
| DeepFashion2 | non-commercial research | sleeve length; training data of the garment detector |
| DeepFashion-MultiModal | non-commercial research | sleeve length and neckline (human shape annotation); garment type by proxy (shop category) |
| Human review, 1 Oct 2026 (725 photos, one reviewer) | project data | collared-neck, regular-sleeve |

Local folders the scripts read (all git-ignored; everything else from the earlier pipeline was deleted on 2 Oct 2026):

| Folder | Contents |
|---|---|
| `data/manifests_m42/` | the train / validation / test records |
| `data/label_queue_m42/` | the 725 human review answers |
| `data/eval_real_product_set/` | 60 web product photos (benchmark) |
| `data/raw/fashionpedia/images/`, `data/images/fashionpedia_official_expanded/crops/` | Fashionpedia photos and garment crops |
| `datasets/deepfashion2_tops/` | DeepFashion2 tops |
| `datasets/deepfashion_multimodal/` | DeepFashion-MultiModal crops (`images/`) and whole photos (`raw/images/`) |
| `datasets/attributes/` | written by `prepare_datasets.py`: one image folder per model |
| `runs/` | written by training and evaluation |

Splits: no photo, garment item or near-identical photo (perceptual hash) is shared between training and validation
or test. Training classes are balanced (a big class is capped, a small class repeated); validation and test photos
are never repeated.

## Class definitions

**Garment type** — *blouse*: a woven top (blouses and women's button shirts), with or without sleeves.
*T-shirt*: a knit tee with sleeves, crew or V neck. A sleeveless knit top (tank top) is not a T-shirt and is not
used as one. Most garment-type training labels are **proxies** (the shop category of a DeepFashion-MultiModal
photo); the test labels are human-verified.

**Neckline** — *round-neck*: curved, no collar. *V-neck*: two straight edges meeting at a centre-front point.
*Square-neck*: a straight edge across the chest with corners. *Collared-neck*: a shirt collar, a separate band
folded around the neck (a blazer or jacket lapel is not a collared neck). Other necklines (boat, halter, high neck,
off-shoulder ...) are not classes: such photos are left out, never mapped to a look-alike.

**Sleeve length** — *sleeveless*: no sleeve (vest, camisole, tank). *Short-sleeve*: ends above the elbow.
*Long-sleeve*: reaches the wrist. Cap, elbow-length and three-quarter sleeves are left out.

**Sleeve design** — *regular-sleeve*: a plain set-in sleeve, smooth at the shoulder, not flared.
*Puff-sleeve*: gathered at the shoulder and / or hem. (*Bell-sleeve* - fitted at the top, flaring towards the hem - was
removed from the scope on 3 Oct 2026: it was almost never recognised. Its photos are kept in
`datasets/removed_bell_sleeve/`; the three-class run in `runs/sleeve_design_3class/`.)
Raglan, dolman, kimono and flutter sleeves are left out.

If a feature cannot be seen in a photo (hidden by hair, arms, a jacket), the right answer is "please select", not a
guess: the app fills a feature in only when the model's score is at or above its validation-chosen threshold.
