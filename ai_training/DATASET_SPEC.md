# Digital Tailor System — Dataset Specification & Protocol

> **Milestone AI-1 Definition Document**
> *Note: This document defines the dataset specifications, class taxonomies, and quality protocols for Milestone AI-1. The dataset itself has not yet been collected, downloaded, or reviewed in this repository.*
> **Taxonomy Update Note**: The initial specification defined 29 classes. The active taxonomy is now 28 classes (`garment_type`: 3, `neckline_type`: 10, `sleeve_length`: 6, `sleeve_style`: 9) following the removal of `cold-shoulder-sleeve`. `off-shoulder` neckline remains active.

---

## 1. Research Scope

The Digital Tailor System AI research pipeline is strictly bounded to **women’s upper garments** across three specific garment categories:

1. **Blouses**
2. **T-shirts**
3. **Crop tops**

Out-of-scope garment categories (such as dresses, jackets, coats, sweaters, skirts, trousers, men's apparel, or children's wear) are explicitly excluded from this system.

---

## 2. Single-Model Multi-Task Architecture

The system trains **ONE single YOLOv8-based multi-task classification model**, rather than four separate standalone classification models.

### Architectural Blueprint
* **Backbone**: One shared YOLOv8 feature-extraction backbone (e.g., YOLOv8n-cls / YOLOv8 feature extractor).
* **Output Heads**: Four separate, parallel classification output heads branching from the shared feature representation:
  1. `garment_type` head (3 logits)
  2. `neckline_type` head (10 logits)
  3. `sleeve_length` head (6 logits)
  4. `sleeve_style` head (10 logits)
* **Model Artifact**: A single trained model weight file (`.pt`) containing all backbone and multi-head parameters.
* **Loss Function**: Multi-task classification loss combining independent cross-entropy losses for each classification head.

---

## 3. The Four Prediction Outputs

For every valid input image, the single multi-task model produces exactly four categorical predictions:

| Output Group | Class Count | Target Attribute Description |
| :--- | :---: | :--- |
| `garment_type` | **3** | Core garment category taxonomy |
| `neckline_type` | **10** | Neckline cut and collar styling |
| `sleeve_length` | **6** | Arm coverage extension length |
| `sleeve_style` | **10** | Structural and visual sleeve design style |

**Total Classification Labels across Heads**: **29** (3 + 10 + 6 + 10).  
*Note: The 29 labels are grouped into four distinct output distributions, NOT treated as a single 29-class softmax list.*

---

## 4. Exact Definition of Every Class

### 4.1. Garment Type (3 Classes)

1. **`blouse`**: A dressy or tailored upper garment for women, typically constructed from woven or lightweight decorative fabric. May feature buttons, pleats, ruffles, or dress collar detailing.
2. **`t-shirt`**: A casual, knit-fabric (cotton/jersey) upper garment characterized by a classic T-shaped silhouette with standard waist-to-hip body length.
3. **`crop-top`**: An upper garment designed with a truncated hemline that ends above the natural waistline, exposing the midriff.

#### Garment Labeling Precedence
To ensure mutually exclusive garment-type decision making, annotators must apply the following decision hierarchy:
- If the hemline clearly ends above the natural waist and exposes or is designed to expose the midriff, label the garment as `crop-top`, regardless of whether its fabric resembles a T-shirt or blouse.
- Otherwise, if it is a casual knit top with a classic T-shaped construction, label it as `t-shirt`.
- Otherwise, if it is a dressy, tailored, woven, buttoned, pleated, ruffled, or decorative upper garment, label it as `blouse`.
- Reject the image if this decision cannot be made reliably.

---

### 4.2. Neckline Type (10 Classes)

1. **`round-neck`**: A classic, circular curved neckline fitting close to the base of the neck (crew neck).
2. **`v-neck`**: A neckline dropping in two converging linear edges forming a distinct "V" shape at the center chest.
3. **`square-neck`**: A neckline cut horizontally across the chest with sharp 90-degree vertical corners rising to the shoulders.
4. **`scoop-neck`**: A deep, wide "U"-shaped curved neckline dipping lower than a standard round neck.
5. **`boat-neck`**: A wide, high horizontal neckline stretching across the collarbone toward the shoulder points (bâteau neck).
6. **`sweetheart-neck`**: A decorative neckline shaped like the top half of a heart, featuring two curved lobes dipping in a central apex.
7. **`halter-neck`**: A front neckline supported by a band or straps wrapping around or tying behind the neck, leaving shoulders and upper back exposed.
8. **`high-neck`**: A neckline extending upward to cover part or all of the neck (mock neck, turtleneck, funnel neck).
9. **`collared-neck`**: A neckline featuring a folded, rolled, or standing collar construction (polo, button-down, or blouse collar).
10. **`off-shoulder`**: A neckline sitting entirely below the shoulder line, fully exposing both shoulder tops and collarbones.

---

### 4.3. Sleeve Length (6 Classes)

1. **`sleeveless`**: No sleeve extension; the armhole finishes directly at the shoulder seam point.
2. **`cap-length`**: An ultra-short sleeve covering only the peak of the shoulder and not extending down the arm.
3. **`short-sleeve`**: Sleeve coverage extending from shoulder down to the mid-bicep area (well above the elbow).
4. **`elbow-length`**: Sleeve coverage extending down to end right at or near the elbow joint.
5. **`three-quarter-sleeve`**: Sleeve coverage extending past the elbow down to mid-forearm (ending between elbow and wrist).
6. **`long-sleeve`**: Full-length sleeve extending down to the wrist line or hand.

---

### 4.4. Sleeve Style (10 Classes)

1. **`none`**: Mandatory designation used **if and only if** `sleeve_length` is `sleeveless`.
2. **`regular-sleeve`**: Standard straight or fitted set-in sleeve without puffing, flare, or special architectural shaping.
3. **`puff-sleeve`**: Sleeve gathered tightly at shoulder cap and/or cuff, producing a voluminous, gathered puff shape.
4. **`bell-sleeve`**: Sleeve expanding progressively in a flared, bell-like shape from shoulder or elbow toward the hem opening.
5. **`bishop-sleeve`**: Full, voluminous sleeve gathered softly along the arm and cinched into a tight cuff at the wrist.
6. **`flutter-sleeve`**: A wide, loose, flowing ruffle-like sleeve draping fluidly over the arm.
7. **`raglan-sleeve`**: Sleeve running in a continuous piece up to the neckline with diagonal seams extending from underarm to collarbone.
8. **`dolman-sleeve`**: Deeply cut sleeve continuous with the garment torso without a distinct armhole seam (batwing sleeve).
9. **`cold-shoulder-sleeve`**: Sleeve featuring deliberate shoulder cutouts exposing the top of the shoulder while preserving sleeve length.
10. **`kimono-sleeve`**: Wide, flat, rectangular-cut sleeve integrated seamlessly into the bodice without armhole gathering.

---

## 5. Master CSV Schema

All dataset annotations must adhere to the following master CSV schema:

```csv
image_path,garment_type,neckline_type,sleeve_length,sleeve_style,source,source_id,split,review_status
```

### Field Definitions
* **`image_path`**: Relative path to stored image file (e.g., `data/images/img_00102.jpg`).
* **`garment_type`**: Enum string (`blouse`, `t-shirt`, `crop-top`).
* **`neckline_type`**: Enum string (one of the 10 neckline classes).
* **`sleeve_length`**: Enum string (one of the 6 sleeve length classes).
* **`sleeve_style`**: Enum string (one of the 10 sleeve style classes).
* **`source`**: Dataset origin name or platform identifier (e.g., `deepfashion`, `internal_catalog`).
* **`source_id`**: Parent product or photoshoot grouping ID to prevent data leakage.
* **`split`**: Dataset partition identifier (`train`, `val`, `test`).
* **`review_status`**: Data lifecycle approval stage (`pending`, `approved`, `rejected`).

---

## 6. Inclusion Criteria for Images

To be included in the dataset, candidate images must fulfill all of the following requirements:
1. **Garment Scope**: Focuses strictly on a woman's blouse, t-shirt, or crop top.
2. **Clear Orientation**: Front-facing or clear three-quarter view showing the primary front features of the garment.
3. **Visibility**: Clear, unobscured visibility of the garment body, neckline region, shoulder line, and full sleeve extent.
4. **Resolution**: Sufficient image sharpness and clarity (minimum 256x256 resolution) without pixelation or heavy compression artifacts.
5. **Single Target Subject**: High-clarity e-commerce, catalog, or research photography with a clearly identifiable target garment.

---

## 7. Exclusion Criteria

Candidate images MUST be rejected if they meet any of the following criteria:
1. **Non-Real Photographs**: Technical drawings, vector artwork, flat sewing blocks, pattern CAD drawings, or digital mockups.
2. **Back Views**: Back-view-only images.
3. **Neckline Occlusion**: Neckline hidden or obstructed by hair, scarves, bulky necklaces, outer garments (jackets/coats), or image cropping.
4. **Sleeve Occlusion**: Sleeve length or style obscured by limbs, posture, crop boundaries, or pose truncation.
5. **Ambiguous Multi-Garment Scenes**: Images containing multiple garments of equal prominence where the target garment is unclear.
6. **Low Quality**: Heavily edited collages, multi-angle composite images, pixelated thumbnails, or blurry photographs.

---

## 8. Rules for Ambiguous Images

1. **Zero-Guessing Policy**: Annotators MUST NOT guess or infer labels for unclear images.
2. **Rejection Rule**: If any of the four attributes cannot be determined clearly according to this annotation protocol, the entire image MUST be marked as `review_status=rejected`.
3. **Hemline Ambiguity**: If tucking or pose makes it impossible to distinguish between `crop-top` and `t-shirt` / `blouse`, reject the image.
4. **Sleeve-Style Ambiguity & Combined Styles**: The current `sleeve_style` output is single-label. If an image visibly combines two sleeve-style classes, such as `puff-sleeve` with `cold-shoulder-sleeve`, reject it from the initial training dataset instead of guessing or assigning multiple labels.

---

## 9. Label Consistency & Dependency Rules

Every accepted dataset entry MUST follow these strict rules:

1. **Four Output Completeness**: Every accepted image must have exactly one valid label for each of the four output groups.
2. **Sleeveless Rule**: If `sleeve_length` is `sleeveless`, then `sleeve_style` MUST be `none`.
3. **Real Sleeve Rule**: If `sleeve_length` is NOT `sleeveless` (i.e. `cap-length`, `short-sleeve`, `elbow-length`, `three-quarter-sleeve`, `long-sleeve`), then `sleeve_style` MUST NOT be `none`.
4. **Invalid State Handling**: Any entry violating sleeve dependency constraints must be flagged and rejected immediately.

---

## 10. Dataset Balance Requirements

1. **Multi-Head Class Balance**: Annotation efforts must actively monitor class frequencies across all four heads to prevent severe class imbalance.
2. **Attribute Co-occurrence**: Ensure diverse representation across combinations (e.g., avoiding dataset bias where all `crop-top` entries are `sleeveless`).
3. **Class-Balance Readiness Rule**: Training must not begin until every class has a documented sample count. Any severe imbalance must be corrected through additional data collection or documented training mitigation. Do not invent a minimum image count before the dataset-source audit.

---

## 11. Duplicate-Image Prevention

1. **Checksum Verification**: Compute MD5 hashes on ingest to eliminate exact binary duplicate files.
2. **Perceptual Hashing**: Use perceptual hashing (pHash) to detect resized, recropped, or color-adjusted duplicate images.
3. **Split Isolation for Duplicates**: Any unavoidable near-duplicates must be strictly assigned to the SAME dataset split (`train`, `val`, or `test`).

---

## 12. Data-Leakage Prevention

To guarantee zero data leakage between training, validation, and testing partitions:
1. **Source Grouping**: All candidate images originating from the same product listing, photoshoot, or vendor model session MUST share the same `source_id`.
2. **Group-Level Partitioning**: Splitting is strictly performed on unique `source_id` units, NEVER on individual image rows independently.

---

## 13. Source-Image-Level Train / Validation / Test Splitting

The dataset split allocations are calculated based on unique `source_id` groups according to the following ratio:

* **Train Split**: **70%** (`split=train`)
* **Validation Split**: **15%** (`split=val`)
* **Test Split**: **15%** (`split=test`)

---

## 14. Manual-Review Process

1. **Initial State**: All newly ingested annotations are created with `review_status=pending`.
2. **Automated Validation**: Automated scripts parse the CSV, verifying schema types and label dependency rules (e.g., checking sleeveless constraints).
3. **Manual Verification**: Annotation reviewers inspect each candidate image and confirm label accuracy.
4. **Second Review & Quality Control**: Every approved record must be independently reviewed by a second reviewer, or re-reviewed in a separate quality-control pass. Disagreements must be resolved before `review_status` is set to `approved`.
5. **Final Status**:
   * Approved records are set to `review_status=approved`.
   * Rejected records are set to `review_status=rejected`.
   * Only `approved` entries are exported for model training.

---

## 15. Dataset Licensing & Source-Recording Requirements

1. **Provenance Tracking**: The `source` and `source_id` fields must be populated for every entry to document origin.
2. **License Compliance**: All external dataset sources must be checked for open research usage rights, attribution rules, and terms of service before ingestion.

---

## 16. Acceptance Criteria Before Model Training

Before model training may commence, the dataset pipeline must validate the following readiness criteria:
1. All training data entries have `review_status=approved`.
2. 100% schema compliance: all 4 output labels present and matching exact string keys in `ai_training/config/classes.json`.
3. 100% compliance with `sleeveless` $\leftrightarrow$ `none` sleeve style dependency rules.
4. Zero `source_id` overlap across `train`, `val`, and `test` splits.
5. Validated 70% / 15% / 15% split distribution by `source_id`.
6. Successful execution of `ai_training/config/classes.json` Python verification checks.
7. Documented sample count for every class, with any severe imbalance corrected via additional data collection or documented training mitigation prior to training.
