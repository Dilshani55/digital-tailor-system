# Full Fashionpedia Training Data Feasibility & Manual-Review Planning (Milestone AI-6A)

## Overview

Milestone **AI-6A** performs a comprehensive feasibility audit on the official Fashionpedia training annotation package (`instances_attributes_train2020.json`) for the Digital Tailor System single multi-task model (`garment_type`, `neckline_type`, `sleeve_length`, `sleeve_style`) across all 29 project target classes.

No image archives were downloaded, no cropping was performed, no model training was executed, and no code outside `ai_training/` was modified. All generated data remains strictly isolated under `ai_training/data/` and ignored by Git.

---

## Source Annotation Package & Ontology Verification

- **Official Source URL**: `https://s3.amazonaws.com/ifashionist-dataset/annotations/instances_attributes_train2020.json`
- **Local File Path**: [instances_attributes_train2020.json](file:///C:/Research/Developing/digital-tailor-system/ai_training/data/raw/fashionpedia/instances_attributes_train2020.json)
- **File Size**: `542,193,045` bytes (517.08 MB)
- **SHA-256 Checksum**: `f6af94fb8712bd8170a49c857e842e1227e6806c4f33f32340db0c849133e006`
- **Download Date/Time**: `2026-09-26T05:42:51 UTC`
- **Total Source Images**: `45,623`
- **Total Source Annotations**: `333,401`
- **Relevant Upper-Garment Parent Instances**: `33,862` records (Category 0 `shirt, blouse` and Category 1 `top, t-shirt, sweatshirt`)

### Programmatic Ontology Comparison Result
Direct programmatic comparison (`v['categories'] == t['categories']` and `v['attributes'] == t['attributes']`) confirms that `instances_attributes_train2020.json` and `instances_attributes_val2020.json` contain **100% IDENTICAL** category and attribute dictionaries:
- **Category Structure**: `46` total category/part entries with IDs `0` through `45` (comprising `27` main apparel/accessory categories and `19` apparel-part/decorative categories).
- **Attribute Structure**: `294` total attribute entries, with sparse non-contiguous IDs ranging from `0` to `340`.

---

## Target Taxonomy (29 Classes)

The project target taxonomy is defined strictly in `ai_training/config/classes.json`:

- **`garment_type` (3 classes)**: `blouse`, `t-shirt`, `crop-top`.
- **`neckline_type` (10 classes)**: `round-neck`, `v-neck`, `square-neck`, `scoop-neck`, `boat-neck`, `sweetheart-neck`, `halter-neck`, `high-neck`, `collared-neck`, `off-shoulder`.
- **`sleeve_length` (6 classes)**: `sleeveless`, `cap-length`, `short-sleeve`, `elbow-length`, `three-quarter-sleeve`, `long-sleeve`.
- **`sleeve_style` (10 classes)**: `none`, `regular-sleeve`, `puff-sleeve`, `bell-sleeve`, `bishop-sleeve`, `flutter-sleeve`, `raglan-sleeve`, `dolman-sleeve`, `cold-shoulder-sleeve`, `kimono-sleeve`.

> [!IMPORTANT]
> Merged source categories (`shirt`, `top`, `sweatshirt`) are source ontology terms, **not** project target classes, and are excluded from all target class counts.

---

## Spatial Part Association Breakdown (`train2020`)

Spatial part association evaluated **103,865** candidate garment-part annotations against the 33,862 upper-garment parent instances:

- **Total Evaluated Part Annotations**: `103,865` (Sleeve: 59,448, Neckline: 34,258, Collar: 10,159)
- **Accepted Spatial Associations**: `44,842` (Sleeve: 24,220, Neckline: 14,372, Collar: 6,250)
- **Ambiguous Spatial Associations**: `756` (Sleeve: 186, Neckline: 534, Collar: 36)
- **Unassociated Parts**: `58,267` (Sleeve: 35,042, Neckline: 19,352, Collar: 3,873)

---

## Usable Head Distribution & Record Partition

Across all 33,862 upper-garment parent records in `train2020`:

- **4 Usable Heads (Fully Labelled)**: **`26`** records
- **3 Usable Heads (Partial)**: **`727`** records
- **2 Usable Heads (Partial)**: **`4,489`** records
- **1 Usable Head  (Partial)**: **`10,009`** records
- **0 Usable Heads (Unusable)**: **`18,611`** records
- **Fully Labelled Total**: **`26`** records
- **Partially Labelled Total**: **`15,225`** records
- **Training-Eligible Records Total**: **`15,251`** records (possessing at least 1 usable direct head label)
- **Manual Review Queue Size**: **`33,805`** records (`manual_review_priority.jsonl`)

---

## Unique-Record Direct Class Counts by Split (`train2020`)

Counts reflect **unique parent records** (`source_annotation_id`) with direct verified labels. Split assignments (`train`: 24,196, `val`: 4,819, `test`: 4,847) remain strictly isolated.

| Head | Target Class | Train | Val | Test | Total Direct Records |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **`garment_type`** | `blouse` | 0 | 0 | 0 | **0** *(1,556 candidates)* |
| | `t-shirt` | 0 | 0 | 0 | **0** *(32,201 candidates)* |
| | `crop-top` | 776 | 165 | 164 | **1,105** |
| **`neckline_type`** | `round-neck` | 2,528 | 506 | 537 | **3,571** |
| | `v-neck` | 796 | 169 | 205 | **1,170** |
| | `square-neck` | 126 | 24 | 24 | **174** |
| | `scoop-neck` | 908 | 177 | 192 | **1,277** |
| | `boat-neck` | 453 | 104 | 105 | **662** |
| | `sweetheart-neck` | 180 | 39 | 44 | **263** |
| | `halter-neck` | 80 | 19 | 17 | **116** |
| | `high-neck` | 253 | 47 | 45 | **345** |
| | `collared-neck` | 0 | 0 | 0 | **0** *(6,250 candidates)* |
| | `off-shoulder` | 141 | 27 | 40 | **208** |
| **`sleeve_length`** | `sleeveless` | 16 | 4 | 2 | **22** |
| | `cap-length` | 0 | 0 | 0 | **0** *(31 candidates)* |
| | `short-sleeve` | 2,684 | 591 | 562 | **3,837** |
| | `elbow-length` | 540 | 98 | 108 | **746** |
| | `three-quarter-sleeve` | 758 | 177 | 164 | **1,099** |
| | `long-sleeve` | 3,850 | 804 | 858 | **5,512** |
| **`sleeve_style`** | `none` | 0 | 0 | 0 | **0** *(22 derived candidates)* |
| | `regular-sleeve` | 0 | 0 | 0 | **0** *(15,901 candidates)* |
| | `puff-sleeve` | 137 | 20 | 33 | **190** |
| | `bell-sleeve` | 59 | 18 | 13 | **90** |
| | `bishop-sleeve` | 85 | 10 | 19 | **114** |
| | `flutter-sleeve` | 0 | 0 | 0 | **0** *(121 candidates)* |
| | `raglan-sleeve` | 311 | 66 | 72 | **449** |
| | `dolman-sleeve` | 163 | 33 | 28 | **224** |
| | `cold-shoulder-sleeve` | 0 | 0 | 0 | **0** *(unsupported)* |
| | `kimono-sleeve` | 66 | 12 | 20 | **98** |

### Direct Head Label Arithmetic Breakdown
- **`garment_type` direct labels**: `1,105`
- **`neckline_type` direct labels**: `7,786`
- **`sleeve_length` direct labels**: `11,216`
- **`sleeve_style` direct labels**: `1,165`
- **Grand Total Direct Head Labels**: **`21,272`** usable head labels across all records.

> [!NOTE]
> **Arithmetic Clarification**: The grand total of `21,272` is a count of usable direct head label instances across all records. It is distinct from the `15,251` training-eligible records because one record can contribute to multiple different heads (up to 4). However, each record contributes at most once to each individual head.

---

## Four Mutually Exclusive Planning Bands (Total = 29)

1. **Zero Direct Samples (`0`)**: **`8`** classes (`blouse`, `t-shirt`, `collared-neck`, `cap-length`, `none`, `regular-sleeve`, `flutter-sleeve`, `cold-shoulder-sleeve`). Seven of the eight zero-direct classes have candidate or derived evidence requiring visual/manual review; `cold-shoulder-sleeve` is unsupported by Fashionpedia. Candidate volumes vary substantially by class.
2. **Below Baseline (`1 to 19`)**: **`0`** classes.
3. **Below Recommended (`20 to 99`)**: **`3`** classes (`sleeveless`: 22, `bell-sleeve`: 90, `kimono-sleeve`: 98).
4. **Sufficient Samples (`100+`)**: **`18`** classes (`crop-top`: 1,105, `round-neck`: 3,571, `v-neck`: 1,170, `square-neck`: 174, `scoop-neck`: 1,277, `boat-neck`: 662, `sweetheart-neck`: 263, `halter-neck`: 116, `high-neck`: 345, `off-shoulder`: 208, `short-sleeve`: 3,837, `elbow-length`: 746, `three-quarter-sleeve`: 1,099, `long-sleeve`: 5,512, `puff-sleeve`: 190, `bishop-sleeve`: 114, `raglan-sleeve`: 449, `dolman-sleeve`: 224).

$$\text{Sum} = 8 + 0 + 3 + 18 = 29 \text{ target classes}$$

---

## Comparison: `train2020` vs. `val2020`

| Metric | `val2020` Subset | `train2020` Full Set | Growth Multiplier |
| :--- | :---: | :---: | :---: |
| **Upper-Garment Instances** | 817 | 33,862 | ~41.4x |
| **Accepted Part Associations** | 1,039 | 44,842 | ~43.2x |
| **4-Head Fully Labelled Records** | 2 | 26 | 13.0x |
| **Partial-Label Training Records** | 374 | 15,225 | ~40.7x |
| **Sufficient Classes ($\ge 100$)** | 2 | 18 | 9.0x |
| **Zero Direct Sample Classes** | 9 | 8 | -1 class |
| **Classes Below Baseline ($< 20$)** | 22 | 8 | -14 classes |

---

## Class Imbalance Risks

Significant class imbalance exists within specific heads on `train2020`:
- **`sleeve_length`**: `long-sleeve` (5,512) vs `sleeveless` (22) $\rightarrow$ imbalance ratio of **250.5x** (exceeds 5.0 warning threshold).
- **`neckline_type`**: `round-neck` (3,571) vs `halter-neck` (116) $\rightarrow$ imbalance ratio of **30.8x** (exceeds 5.0 warning threshold).
- **`sleeve_style`**: `raglan-sleeve` (449) vs `bell-sleeve` (90) $\rightarrow$ imbalance ratio of **5.0x**.

---

## Feasibility Verdict

**Verdict**: **`READY_AFTER_TARGETED_MANUAL_REVIEW`**

> [!NOTE]
> **Verdict Scope**: This verdict applies specifically to the inspected Fashionpedia full training dataset package (`instances_attributes_train2020.json`, 33,862 spatial parent instances).

### Rationale
1. **18 Target Classes Immediately Viable**: 18 of the 29 target classes possess over 100 direct verified samples (totaling 21,272 direct head annotations across 15,251 training-eligible records).
2. **Abundant Candidate Evidence**: Seven zero-direct classes (such as `blouse`, `t-shirt`, `collared-neck`, `regular-sleeve`) have tens of thousands of candidate mapping records in `manual_review_priority.jsonl` (e.g. 32,201 `t-shirt` candidates, 15,901 `regular-sleeve` candidates, and 6,250 `collared-neck` candidates).
3. **No Image Content Claims**: No image pixels have been visually inspected. Minimum manual-review workload cannot yet be determined without image availability.

---

## Next Recommended Steps

1. Implement a masked multi-task loss training script using the 15,251 eligible records (26 fully labelled + 15,225 partial) for multi-head baseline training.
2. Execute targeted manual review or heuristic filtering on high-priority `garment_type` items in `manual_review_priority.jsonl`.
3. Do not attempt model training until pipeline scripts and data verification are fully completed.
