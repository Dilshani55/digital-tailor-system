# AI-Assisted Garment Labelling & Targeted Acquisition (Milestone AI-6B)

## 1. Overview & Motivation

Fashionpedia’s original ontology merges distinct garment types into broad parent categories:
- **Category 0**: `shirt, blouse` (combines tailored woven blouses and structured men's/women's shirts)
- **Category 1**: `top, t-shirt, sweatshirt` (combines casual knit t-shirts, athletic tops, smocks, and heavy sweatshirts)

For the **Digital Tailor** custom garment synthesis and recommendation system, accurate garment classification requires precise separation of female upper garments into three target classes:
1. **`blouse`**: Woven or tailored women's tops, button-up or dressy feminine tops.
2. **`t-shirt`**: Casual knit tops, classic crewneck/v-neck tees, ringer tees, short-sleeved casual tees.
3. **`crop-top`**: Cropped tops, midriff-exposing upper garments (identified via Fashionpedia Attribute 8 `crop (top)` across Category 0 and 1).

All other categories (jackets, coats, dresses, pants, jumpsuits, men's apparel, sweatshirts/hoodies) are out of scope and categorized as `reject`.

---

## 2. Targeted Image Candidate Acquisition

To avoid downloading the entire ~30GB Fashionpedia image archive, Milestone AI-6B performs **targeted acquisition** of a small candidate subset:
- Maximum download limit: **450 images** (~150 candidates per target class).
- Source: Fashionpedia `instances_attributes_train2020.json` original Flickr URLs.

### Candidate Selection Rules:
1. **`crop-top` pool** (Precedence): Category 0 or 1 with exact Attribute ID 8 `crop (top)`.
2. **`t-shirt` pool**: Category 1 with exact Attribute ID 0 `classic (t-shirt)` or Attribute ID 4 `ringer (t-shirt)` (without Attr 8).
3. **`blouse` pool**: Category 0 (`shirt, blouse`) without Attr 8.
4. **Out-of-scope exclusion**: Parent categories other than 0 and 1 are strictly excluded.
5. **Split Preservation**: Records maintain their exact original dataset split (`train`, `val`, `test`). No records are moved across splits.

---

## 3. Zero-Shot AI Pseudo-Labelling with CLIP

A pretrained vision-language model (`openai/clip-vit-base-patch32`) is used as an external pseudo-labeller to evaluate cropped garment candidate regions.

### Multi-Prompt Formulations:
- **Blouse**:
  - *"a women’s blouse"*
  - *"a feminine blouse for women"*
  - *"a women’s tailored blouse"*
- **T-shirt**:
  - *"a women’s t-shirt"*
  - *"a short-sleeved women’s tee shirt"*
  - *"a casual women’s t-shirt"*
- **Crop-top**:
  - *"a women’s crop top"*
  - *"a cropped top for women"*
  - *"a women’s cropped blouse or t-shirt"*
- **Reject / Out-of-Scope**:
  - *"a men’s shirt"*
  - *"a sweatshirt or hoodie"*
  - *"a dress, jacket or coat"*
  - *"not a women’s blouse, t-shirt or crop top"*
  - *"an unclear or unsuitable garment image"*

### Decision & Acceptance Rules:
To accept an AI-assisted pseudo-label, all four conditions must be satisfied:
1. **Top-1 Class**: Must be a target class (`blouse`, `t-shirt`, `crop-top`).
2. **Confidence Threshold**: Top-1 class aggregated probability $\ge 0.60$.
3. **Top-1 / Top-2 Margin**: Margin $\ge 0.10$.
4. **Multi-Prompt Agreement**: At least 2 prompt formulations within the top-1 class must rank higher than competing non-top-1 prompts.

Records failing any of these criteria are routed to `review_required.jsonl`. Records classified as `reject` are routed to `rejected.jsonl`.

---

## 4. Why AI Pseudo-Labels Are Not Ground Truth

AI-assisted pseudo-labels serve as a screening mechanism to filter raw candidate crops.
- Every generated pseudo-label explicitly retains:
  - `label_origin`: `"ai_assisted_pseudo_label"`
  - `human_verified`: `false`
- Zero-shot vision-language models can exhibit domain shift, background sensitivity, or misclassification on atypical fashion items.
- Unverified AI pseudo-labels are **never** treated as ground truth for model training without human spot-checking.

---

## 5. Human Spot-Checking & Quality Review

A standalone review web app is provided under `ai_training/review_app.py`:
- Built with Flask for isolated local review.
- Renders one crop at a time with AI prediction details, top-2 class, confidence, margin, and source evidence.
- Prioritizes **15 accepted predictions per target class** for human spot-checking.
- Saves verified decisions incrementally to `ai_training/data/labelling/human_review.jsonl` with `human_verified: true`.

### Command to Start Review App:
```bash
python ai_training/review_app.py --port 5000
```

---

## 6. Reproducibility & Pipeline Execution

All steps are deterministic:
- Random Seed: `42`
- Pipeline commands:

```bash
# 1. Selection
python ai_training/scripts/select_labelling_candidates.py --spatial-manifest ai_training/data/processed/fashionpedia_train_spatial_manifest/all_instances_spatial.jsonl --annotations ai_training/data/raw/fashionpedia/instances_attributes_train2020.json --classes ai_training/config/classes.json --config ai_training/config/ai_assisted_labelling.json --output-dir ai_training/data/labelling

# 2. Download
python ai_training/scripts/download_selected_images.py --queue ai_training/data/labelling/candidate_queue.jsonl --config ai_training/config/ai_assisted_labelling.json --output-dir ai_training/data/images/fashionpedia_selected/original --manifest-dir ai_training/data/labelling

# 3. Crop
python ai_training/scripts/create_selected_crops.py --download-manifest ai_training/data/labelling/download_manifest.jsonl --queue ai_training/data/labelling/candidate_queue.jsonl --config ai_training/config/ai_assisted_labelling.json --output-dir ai_training/data/images/fashionpedia_selected/crops --manifest-dir ai_training/data/labelling

# 4. CLIP Labelling
python ai_training/scripts/ai_assisted_label.py --crop-manifest ai_training/data/labelling/crop_manifest.jsonl --config ai_training/config/ai_assisted_labelling.json --output-dir ai_training/data/labelling

# 5. Validation
python ai_training/scripts/validate_candidate_selection.py --queue ai_training/data/labelling/candidate_queue.jsonl --classes ai_training/config/classes.json --config ai_training/config/ai_assisted_labelling.json
python ai_training/scripts/validate_ai_labels.py --labelling-dir ai_training/data/labelling --classes ai_training/config/classes.json --config ai_training/config/ai_assisted_labelling.json
```

---

## 7. Status & Next Steps

> [!NOTE]
> The final YOLOv8-based multi-head garment detection and classification model **has not been trained**. Milestone AI-6B establishes the verified crop acquisition and pseudo-labelling pipeline.

**Next Steps**:
1. Conduct human spot-checks using `python ai_training/review_app.py`.
2. Generate final approved training crops and segmentations.
3. Train the multi-task YOLOv8 head model on approved crops.
