# Fashionpedia Dataset-Manifest Preparation Pipeline (AI-4A)

## Overview

Milestone **AI-4A** implements a deterministic, auditable, metadata-only preparation pipeline for converting Fashionpedia instance annotations into training candidate manifests for the Digital Tailor System four-head classification architecture:

> **Taxonomy Update Note**: This historical document evaluated a 29-class taxonomy. The active dataset taxonomy has since been updated to 28 classes by removing the unsupported `sleeve_style:cold-shoulder-sleeve` class, while preserving `neckline_type:off-shoulder`.
1. `garment_type`
2. `neckline_type`
3. `sleeve_length`
4. `sleeve_style`

No image binary archives are downloaded, no cropping is performed, no model training is executed, and no existing files outside `ai_training/` are modified.

---

## Rationale: Instance-Level Garment Crops vs. Full Images

### Why Instance-Level Bounding Box Crops Will Be Used Later
In real-world fashion images, photographs often contain complete outfits (e.g., upper garments, lower garments, outerwear, shoes, accessories) or multiple individuals. Training a multi-head classification model directly on full image frames introduces severe background noise, peripheral garment features, and non-target body parts. Utilizing instance-level bounding box crops isolates the specific upper-body garment region, standardizing input geometry for neural network feature extraction.

### Why Full Images Are Unsafe for Multi-Head Classification
1. **Multi-Garment Feature Contamination**: A photo featuring both a blouse and a skirt would force a global classifier to process lower-body features (pleats, hemline length, pattern) when attempting to classify upper-garment attributes like `neckline_type` or `sleeve_style`.
2. **Ambiguous Ground Truth**: When multiple upper garments appear in a single photo (e.g., a jacket worn over a t-shirt), full-image metadata lacks spatial ground-truth localization, causing label collisions across different garments in the same image frame.

---

## Fashionpedia Validation-Set Diagnostic Finding

A comprehensive empirical analysis of `ai_training/data/raw/fashionpedia/instances_attributes_val2020.json` yielded key insights into how Fashionpedia structures instance and attribute metadata:

- **Separate Part Annotations**: Fashionpedia stores sleeve and neckline information primarily on separate part annotations (Category 31 = `sleeve`, Category 33 = `neckline`) rather than directly on main upper-garment annotations (Category 0 = `shirt, blouse`, Category 1 = `top, t-shirt, sweatshirt`).
- **No Explicit Parent-Child Relationship**: Main upper-garment annotations and garment-part annotations do not contain an explicit parent-child relationship field. Annotation object keys are strictly: `image_id`, `category_id`, `attribute_ids`, `segmentation`, `bbox`, `area`, `iscrowd`, `id`.
- **Part-Attribute Localization**: Target sleeve and neckline attributes are attached almost entirely to Category 31 (`sleeve`) and Category 33 (`neckline`) part annotations (**1,956** part occurrences vs. only **1** occurrence directly on a main upper-garment annotation).
- **Co-Occurrence Metrics (547 unique images containing Cat 0 or Cat 1 garments)**:
  - `403` images contain sleeve part annotations (Category 31).
  - `431` images contain neckline part annotations (Category 33).
  - `298` images contain both sleeve and neckline part annotations.
  - `312` images contain multiple upper garments, introducing spatial association ambiguity across co-located garments.
- **Pipeline Decision Result**: Consequently, the current AI-4A single-annotation pipeline correctly produces **0** `training_ready` records and routes all **817** relevant upper-garment instances to `manual_review` due to unattached sleeve and neckline heads. These 817 records form a conservative candidate baseline, not final training samples.
- **Requirement for Milestone AI-4B**: Milestone AI-4B must perform evidence-preserving spatial part-to-garment association (e.g., bounding-box containment / IoU matching). Spatial association must not automatically accept ambiguous multi-garment images, and no parent relationship may be invented.

### Crop-Top Attribute & Category Eligibility
- Exactly **46** Category 1 (`top, t-shirt, sweatshirt`) annotations contain exact Attribute ID 8 `crop (top)`.
- These 46 annotations provide direct `crop-top` evidence under the configured crop-top precedence rule.
- The remaining occurrences of Attribute ID 8 on lower-body categories (Category 6 `pants`) or outerwear (Category 4 `jacket`) are excluded or prevented from becoming `crop-top` samples.

---

## Manifest Schema & Field Definitions

Each instance record in `all_instances.jsonl`, `training_ready.jsonl`, `manual_review.jsonl`, and `rejected.jsonl` adheres to the following machine-readable JSON structure:

| Field Name | Type | Description |
| :--- | :--- | :--- |
| `sample_id` | String | Unique record identifier (`fashionpedia_<source_annotation_id>`) |
| `source_dataset` | String | Origin dataset identifier (`fashionpedia`) |
| `source_image_id` | Integer | Raw Fashionpedia image ID |
| `source_annotation_id` | Integer | Raw Fashionpedia annotation ID |
| `source_file_name` | String | Image file name in source dataset |
| `source_url` | String / Null | Source image URL if provided in metadata |
| `bbox` | Array[Float] | Bounding box coordinates `[x, y, width, height]` in pixels |
| `fashionpedia_category` | Object | Category ID and name (`{id, name}`) |
| `fashionpedia_attributes` | Array[Object] | Array of attributes present (`[{id, name}]`) |
| `head_evaluations` | Object | Detailed head-by-head candidate evidence and status |
| `head_candidates` | Object | Summary of candidate labels per head |
| `assigned_labels` | Object | Final assigned target labels for all 4 heads (or null if not training ready) |
| `decision` | String | Instance decision: `training_ready`, `manual_review`, or `rejected` |
| `reason_codes` | Array[String] | Array of standardized audit reason codes |
| `split` | String | Deterministic dataset split assignment (`train`, `val`, or `test`) |

---

## Partitioning Decisions & Audit Meanings

Every evaluated instance receives exactly one top-level decision:

### 1. `training_ready`
- **Criteria**:
  - Valid bounding box (`width >= 10` and `height >= 10`).
  - Exactly one valid target label for **all four** model heads.
  - Zero missing heads and zero conflicting candidates.
  - All four assigned target labels are backed strictly by **direct** ontology mappings.
- **Usage**: Automatically eligible for training/validation/testing without human intervention.

### 2. `manual_review`
- **Criteria**:
  - Valid bounding box.
  - Contains candidate mappings requiring verification (e.g., Category 0 `shirt, blouse` or Category 1 `top, t-shirt, sweatshirt`).
  - Contains derived label logic (e.g., deriving `sleeve_style = none` from sleeveless attributes).
  - Has missing required heads or conflicting attribute evidence across any head.
- **Usage**: Placed in `manual_review.jsonl` with explicit `reason_codes` for targeted human review. Candidate mappings are **never** silently promoted to trusted labels.

### 3. `rejected`
- **Criteria**:
  - Invalid, non-numeric, zero, or sub-threshold bounding box dimensions (`width < 10` or `height < 10`).
  - Irrelevant lower-body or outerwear garment categories.
- **Usage**: Excluded from dataset manifests with machine-readable rejection reasons (e.g., `INVALID_BBOX_ZERO_AREA`, `INVALID_BBOX_SUB_THRESHOLD`).

---

## Direct vs. Candidate Mapping Policies

| Policy Type | Treatment | Pipeline Behavior |
| :--- | :--- | :--- |
| **Direct Mapping** | 1:1 unambiguous mapping between Fashionpedia label and target taxonomy label. | Automatically populates target head and permits `training_ready` status if all heads are direct and complete. |
| **Candidate Mapping** | Ambiguous or merged source labels (e.g., Category 0 `shirt, blouse` -> `blouse` candidate; Category 1 `top, t-shirt, sweatshirt` -> `t-shirt` candidate). | Populates candidate evidence but **forces** decision to `manual_review` with reason code `CANDIDATE_MAPPING_REVIEW_REQUIRED`. |
| **Precedence Rule** | Verified `crop (top)` attribute (Attribute ID 8) on eligible top instances overrides `garment_type` to `crop-top`. | Applied only when explicit crop evidence exists on eligible top categories. |
| **Derived Rule** | Sleeveless evidence (Attr 156) derives `sleeve_style = none`. | Derivation recorded with evidence and flagged for `manual_review` (`DERIVED_SLEEVELESS_NONE_REVIEW`). |

---

## Deterministic Source-Level Splitting & Data-Leakage Prevention

### Deterministic Hash Assignment Strategy
Dataset splits are assigned deterministically based on a SHA-256 hash of the `source_image_id` combined with the pipeline seed (`42`):
$$\text{hash\_val} = \text{SHA256}(\text{"fashionpedia\_" } + \text{source\_image\_id} + \text{"\_seed\_42"}) \pmod{10000}$$
- `0 <= hash_val < 7000`: **`train`** (70%)
- `7000 <= hash_val < 8500`: **`val`** (15%)
- `8500 <= hash_val < 10000`: **`test`** (15%)

### Data-Leakage Prevention
Because split assignment is derived purely from `source_image_id`, **all instances belonging to the same source image are guaranteed to receive the exact same dataset split**. This prevents cross-split data leakage (e.g., training on one garment crop while testing on another crop from the identical background frame).

---

## Manual-Review Workflow

1. **Review Manifest**: Inspect `manual_review.jsonl` filtered by reason codes (e.g., `HEAD_GARMENT_TYPE_CANDIDATE`, `HEAD_NECKLINE_TYPE_MISSING`).
2. **Human Verification**: Review candidate instance bounding box and image asset to resolve ambiguities (e.g., confirm whether Category 0 `shirt, blouse` is a `blouse` or `t-shirt`).
3. **Approval**: Approved candidate annotations are logged into an approved candidate override file for subsequent pipeline runs.

---

## Current Limitation & Taxonomy Coverage

- **Unsupported Label**: `sleeve_style = cold-shoulder-sleeve`.
- **Reason**: Fashionpedia's ontology (46 categories, 294 attributes) contains no category or attribute representing cold-shoulder cutouts.
- **Handling**: `cold-shoulder-sleeve` remains explicitly marked `unsupported` in `fashionpedia_mapping.json`. No Fashionpedia instance will assign this label.

---

## Image Copyright & Licensing Disclaimer

- Preparing metadata candidate manifests does **not** download, distribute, or alter image binaries.
- No image licensing approval is implied. Fashionpedia image binaries remain subject to their original copyright holders and source terms as audited in `DATASET_SOURCE_AUDIT.md`.

---

## Next Steps (Milestone AI-4B Preview)

- **Do Not Perform Now**: The next milestone will implement spatial part-to-garment association and image fetching/cropping pipeline using the generated candidate manifests.
