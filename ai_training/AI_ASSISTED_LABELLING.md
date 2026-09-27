# AI-Assisted Garment Labelling & Official Crop Generation (Milestone M8)

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

## 2. Superseding original_url with Official CVDF Image Acquisition

In earlier prototypes (AI-6B), candidate images were fetched from Flickr using Fashionpedia annotation `original_url` values. However, empirical audit revealed that Flickr images suffered from resolution modifications (e.g. 1024x768 vs official 640x480), causing coordinate errors and geometry mismatches on 119 out of 450 crops (26.4% failure rate).

**Milestone M8 completely supersedes `original_url` acquisition:**
- **Zero original_url usage**: All crops are extracted directly from official CVDF Fashionpedia archives (`train2020.zip` and `val_test2020.zip`).
- **Official images root**: `ai_training/data/raw/fashionpedia/images/` (`train/` and `test/` subdirectories containing 48,823 official images).
- **100% Geometry Guarantee**:
  - Image files are decoded with PIL **without EXIF transpose**.
  - Decoded dimensions (`decoded_w`, `decoded_h`) MUST equal annotation metadata (`annotation_w`, `annotation_h`) 100%.
  - Fashionpedia bounding boxes `[x, y, w, h]` are applied directly without rescaling.
  - A configurable **5% context margin** is applied around valid bounding boxes.
  - Boundary-touching boxes are clipped numerically at outer image bounds (`[0, 0, img_w, img_h]`).
- **Empirical Verification**:
  - **Diagnostic run (450 candidates)**: 450 / 450 successful crops (100% success rate, 0 missing source, 0 dimension mismatches).
  - **Expanded run (3,000 candidates)**: 3,000 / 3,000 successful crops (100% success rate, 0 missing source, 0 dimension mismatches).

---

## 3. Direct Evidence vs. Candidate Evidence Rules

Candidate queue selection enforces strict ontology and attribute rules:

1. **`crop-top` Direct Evidence (Precedence)**:
   - Fashionpedia Category 0 or 1 with exact Attribute 8 `crop (top)`.
   - Direct evidence has highest priority and overrides base garment categories.
   - If CLIP pseudo-labelling disagrees with direct `crop-top` evidence, the record is routed to `manual_review` for human inspection rather than being silently rejected.

2. **`t-shirt` Candidate Evidence**:
   - Fashionpedia Category 1 (`top, t-shirt, sweatshirt`) with Attribute 0 (`classic`) or 4 (`ringer`), without Attr 8.
   - Treated as candidate evidence, not automatically verified ground truth.

3. **`blouse` Candidate Evidence**:
   - Fashionpedia Category 0 (`shirt, blouse`) without Attr 8.
   - Treated as candidate evidence, not automatically verified ground truth.

4. **Out-of-Scope Exclusion**:
   - Jackets (Cat 4), dresses (Cat 2), pants (Cat 3), coats, jumpsuits, and men's garments are strictly excluded.
   - Source terms (`shirt`, `top`, `sweatshirt`) are source ontology terms and are **never** used as project target labels.

---

## 4. Zero-Shot AI Pseudo-Labelling with CLIP

Zero-shot inference using `openai/clip-vit-base-patch32` performs screening of official cropped garment candidate regions.

### Natural Language Prompt Formulations:
- **`blouse`**:
  - *"a women’s blouse"*
  - *"a women’s casual blouse"*
  - *"a feminine blouse for women"*
  - *"a women’s tailored blouse"*
- **`t-shirt`**:
  - *"a women’s t-shirt"*
  - *"a short-sleeve women’s t-shirt"*
  - *"a casual women’s t-shirt"*
  - *"a short-sleeved women’s tee shirt"*
- **`crop-top`**:
  - *"a women’s crop top"*
  - *"a cropped women’s top"*
  - *"a women’s cropped blouse or t-shirt"*
- **`reject` (Out-of-Scope)**:
  - *"a men’s shirt"*
  - *"a men’s t-shirt"*
  - *"a sweatshirt or hoodie"*
  - *"a jacket"*
  - *"a dress"*
  - *"an unclear or non-garment image"*

### Decision Rules & Acceptance Criteria:
A pseudo-label is **accepted** only when all four conditions pass:
1. **Top-1 Class**: Is one of `blouse`, `t-shirt`, or `crop-top`.
2. **Confidence Threshold**: Aggregated class probability $\ge 0.60$.
3. **Margin Threshold**: Top-1 minus Top-2 margin $\ge 0.10$.
4. **Multi-Prompt Agreement**: At least 2 prompt formulations within the Top-1 class rank higher than non-Top-1 prompts.

Records with low confidence, low margin, prompt disagreement, or direct evidence conflicts are routed to `manual_review.jsonl`. Confident out-of-scope predictions are routed to `rejected.jsonl`.

---

## 5. Human Verification & Leakage Prevention

- **`human_verified: false`**: Every AI pseudo-label explicitly sets `human_verified=false` and `label_origin="ai_assisted_pseudo_label"`.
- **Split Preservation**: Source image split assignments (`train`, `val`, `test`) are strictly preserved. No `source_image_id` crosses splits.
- **Git Ignore**: All raw images, crops, manifests, and model outputs under `ai_training/data/` remain 100% Git-ignored.

---

## 6. Execution Commands

```bash
# 1. Selection (Expanded 3,000 Candidates)
python ai_training/scripts/select_labelling_candidates.py \
  --spatial-manifest ai_training/data/processed/fashionpedia_spatial_manifest/all_instances_spatial.jsonl ai_training/data/processed/fashionpedia_train_spatial_manifest/all_instances_spatial.jsonl \
  --annotations ai_training/data/raw/fashionpedia/instances_attributes_val2020.json ai_training/data/raw/fashionpedia/instances_attributes_train2020.json \
  --classes ai_training/config/classes.json \
  --config ai_training/config/ai_assisted_labelling.json \
  --output-dir ai_training/data/labelling_official/ \
  --per-class-target 1000 \
  --output-prefix expanded_

# 2. Crop Generation (3,000 Official Crops)
python ai_training/scripts/create_selected_crops.py \
  --queue ai_training/data/labelling_official/expanded_candidate_queue.jsonl \
  --annotations ai_training/data/raw/fashionpedia/instances_attributes_val2020.json ai_training/data/raw/fashionpedia/instances_attributes_train2020.json \
  --official-images-root ai_training/data/raw/fashionpedia/images \
  --config ai_training/config/ai_assisted_labelling.json \
  --output-dir ai_training/data/images/fashionpedia_official_expanded/crops/ \
  --manifest-dir ai_training/data/labelling_official/ \
  --manifest-prefix expanded_

# 3. CLIP Zero-Shot Pseudo-Labelling
python ai_training/scripts/ai_assisted_label.py \
  --crop-manifest ai_training/data/labelling_official/expanded_crop_manifest.jsonl \
  --config ai_training/config/ai_assisted_labelling.json \
  --output-dir ai_training/data/labelling_official/ \
  --batch-size 32

# 4. Validation
python ai_training/scripts/validate_candidate_selection.py \
  --queue ai_training/data/labelling_official/expanded_candidate_queue.jsonl \
  --classes ai_training/config/classes.json \
  --config ai_training/config/ai_assisted_labelling.json \
  --max-target 3000

python ai_training/scripts/validate_ai_labels.py \
  --labelling-dir ai_training/data/labelling_official/ \
  --classes ai_training/config/classes.json \
  --config ai_training/config/ai_assisted_labelling.json
```

---

## 7. Class Distribution & Validation Summary

| Dataset / Run | Candidates | Successful Crops | Accepted Pseudo-Labels | Manual Review | Rejected AI | Failed |
|---|---|---|---|---|---|---|
| **Diagnostic (450)** | 450 | 450 (100%) | - | - | - | 0 |
| **Expanded (3,000)** | 3,000 | 3,000 (100%) | 1,270 | 983 | 747 | 0 |

### Breakdown of Accepted Pseudo-Labels (1,270 Total):
- **`blouse`**: 464
- **`t-shirt`**: 85
- **`crop-top`**: 721

> [!NOTE]
> Final YOLOv8 multi-head model training has NOT been started. All outputs remain uncommitted and ignored by Git.
