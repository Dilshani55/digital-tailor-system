# Fashionpedia Training Data Feasibility & Manual-Review Planning (Milestone AI-5)

## Overview

Milestone **AI-5** evaluates the training feasibility of the Digital Tailor System single multi-task model (`garment_type`, `neckline_type`, `sleeve_length`, `sleeve_style`) across 29 target classes using the Fashionpedia spatial dataset manifest.

No image archives were downloaded, no cropping was performed, no model training was executed, and no code outside `ai_training/` was modified.

---

## Target Taxonomy (29 Classes)

The project target taxonomy is defined strictly in `ai_training/config/classes.json`:

- **`garment_type` (3 classes)**: `blouse`, `t-shirt`, `crop-top`.
- **`neckline_type` (10 classes)**: `round-neck`, `v-neck`, `square-neck`, `scoop-neck`, `boat-neck`, `sweetheart-neck`, `halter-neck`, `high-neck`, `collared-neck`, `off-shoulder`.
- **`sleeve_length` (6 classes)**: `sleeveless`, `cap-length`, `short-sleeve`, `elbow-length`, `three-quarter-sleeve`, `long-sleeve`.
- **`sleeve_style` (10 classes)**: `none`, `regular-sleeve`, `puff-sleeve`, `bell-sleeve`, `bishop-sleeve`, `flutter-sleeve`, `raglan-sleeve`, `dolman-sleeve`, `cold-shoulder-sleeve`, `kimono-sleeve`.

> [!IMPORTANT]
> Fashionpedia source ontology terms such as `shirt`, `top`, and `sweatshirt` are merged source categories, **not** project target classes. They must never be treated as direct target labels.

---

## Record-Level Counting & Attribute Reconciliation

For every classification head and target class, counts are calculated per **unique parent record** (`source_annotation_id`), not per part annotation or attribute occurrence.

- **Deduplication**: A parent record contributes at most once to a target label for any head, regardless of how many attached sleeve/neckline parts (e.g. left and right sleeves) express that attribute.
- **Conflict Handling**: If attached parts express conflicting attributes for the same head (e.g. one short sleeve part and one long sleeve part), the head is marked `conflicting` and setting `labels[head] = null`, contributing zero usable training samples to both labels.
- **Discrepancy Investigation**: Fashionpedia val2020 contains 1,442 Category 31 sleeve-part annotations. The raw metadata diagnostic found Attribute 157 `short (length)` on 305 sleeve annotations and Attribute 160 `wrist-length` on 814 annotations in total, of which 813 belong to Category 31 sleeve and one anomalous occurrence belongs to Category 33 neckline. These raw part-annotation occurrences are not equivalent to unique eligible upper-garment parent records. After conservative spatial association, conflict handling, target-scope filtering, and parent-level deduplication, the feasibility analysis contains 68 unique short-sleeve parent records and 111 unique long-sleeve parent records. The earlier 509/366 figures were produced by a superseded buggy analysis and are not authoritative dataset statistics.

---

## Fully Labelled vs. Partially Labelled Samples

| Sample Type | Definition | Pipeline Status | Loss Treatment |
| :--- | :--- | :--- | :--- |
| **Fully Labelled Sample** | Record with verified **direct** labels for all four classification heads. | Automatically eligible for training (`training_ready`). | All four heads compute loss ($m_1=1, m_2=1, m_3=1, m_4=1$). |
| **Partially Labelled Sample** | Record with verified **direct** labels for 1, 2, or 3 heads, but candidate/missing labels for remaining heads. | Usable for training heads with direct labels using masked loss. | Unannotated/candidate heads contribute zero loss ($m_i=0$). |
| **Unusable Sample** | Record with 0 direct labels (all candidate mappings or missing). | Requires human manual review before inclusion. | Excluded from automated training until verified. |

---

## Masked Multi-Task Loss Concept

In our single multi-task classification network, the combined training loss is computed as a weighted masked sum:

$$L_{\text{total}} = \sum_{i=1}^{4} m_i \cdot L_{\text{head}_i}(y_i, \hat{y}_i)$$

where $m_i \in \{0, 1\}$ is a binary mask indicator:
- $m_i = 1$ if head $i$ possesses a verified, direct ground-truth label.
- $m_i = 0$ if head $i$ is unannotated, missing, candidate-mapped, or conflicting.

### Why Missing Labels Are Not Negative Classes
A missing label in Fashionpedia represents an **absence of annotation evidence**, not the physical absence of the garment feature. For example, an unannotated neckline on a t-shirt does not mean the garment lacks a neckline. Mapping unannotated heads to index `0` or a dummy fallback class would corrupt ground-truth probability distributions, forcing the neural network to learn false negative gradients. Setting $m_i = 0$ ensures missing heads contribute **zero loss** and backpropagate zero gradient into shared backbone features.

---

## Direct vs. Candidate Evidence Policies

- **Direct Evidence**: Unambiguous 1:1 ontology mappings (e.g. Attribute ID 8 `crop (top)` -> `crop-top`, Attr 183 `v-neck` -> `v-neck`, Attr 157 `short (length)` -> `short-sleeve`, Attr 209 `puff (sleeve)` -> `puff-sleeve`). Automatically accepted as verified training labels.
- **Candidate Mappings**: Merged source categories (Category 0 `shirt, blouse` -> candidate `blouse`, Category 1 `top, t-shirt, sweatshirt` -> candidate `t-shirt`), collar parts (Category 28 -> candidate `collared-neck`), and derived rules (`sleeve_style = none`). **Never** automatically promoted to direct labels without human verification.

---

## Dataset Split Preservation

The 817 parent records in the spatial manifest inherit deterministic splits from the manifest pipeline:
- **`train`**: `585` records
- **`val`**: `113` records
- **`test`**: `119` records

Source package metadata (`instances_attributes_val2020.json`) represents the origin annotation package file, while project splits (`train`, `val`, `test`) remain isolated and invariant throughout analysis and manual-review queue ranking.

---

## Analysis Summary (`instances_attributes_val2020.json`, 817 Records)

### Usable Head Distribution
- **4 Usable Heads (Fully Labelled)**: **`2`** records
- **3 Usable Heads (Partial)**: **`22`** records
- **2 Usable Heads (Partial)**: **`115`** records
- **1 Usable Head  (Partial)**: **`237`** records
- **0 Usable Heads (Unusable)**: **`441`** records

### Direct Record Class Counts by Split

| Head | Target Class | Train | Val | Test | Total |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **`garment_type`** | `blouse` | 0 | 0 | 0 | **0** |
| | `t-shirt` | 0 | 0 | 0 | **0** |
| | `crop-top` | 38 | 4 | 4 | **46** |
| **`neckline_type`** | `round-neck` | 78 | 18 | 19 | **115** |
| | `v-neck` | 24 | 1 | 2 | **27** |
| | `square-neck` | 2 | 0 | 1 | **3** |
| | `scoop-neck` | 28 | 4 | 4 | **36** |
| | `boat-neck` | 11 | 5 | 1 | **17** |
| | `sweetheart-neck` | 12 | 2 | 2 | **16** |
| | `halter-neck` | 6 | 1 | 0 | **7** |
| | `high-neck` | 6 | 0 | 0 | **6** |
| | `collared-neck` | 0 | 0 | 0 | **0** |
| | `off-shoulder` | 5 | 3 | 4 | **12** |
| **`sleeve_length`** | `sleeveless` | 0 | 0 | 0 | **0** |
| | `cap-length` | 0 | 0 | 0 | **0** |
| | `short-sleeve` | 50 | 7 | 11 | **68** |
| | `elbow-length` | 20 | 3 | 3 | **26** |
| | `three-quarter-sleeve` | 15 | 1 | 3 | **19** |
| | `long-sleeve` | 76 | 21 | 14 | **111** |
| **`sleeve_style`** | `none` | 0 | 0 | 0 | **0** |
| | `regular-sleeve` | 0 | 0 | 0 | **0** |
| | `puff-sleeve` | 8 | 2 | 0 | **10** |
| | `bell-sleeve` | 0 | 2 | 2 | **4** |
| | `bishop-sleeve` | 1 | 0 | 0 | **1** |
| | `flutter-sleeve` | 0 | 0 | 0 | **0** |
| | `raglan-sleeve` | 7 | 0 | 0 | **7** |
| | `dolman-sleeve` | 6 | 1 | 2 | **9** |
| | `cold-shoulder-sleeve` | 0 | 0 | 0 | **0** |
| | `kimono-sleeve` | 1 | 0 | 0 | **1** |

### Four Mutually Exclusive Planning Bands (Total = 29)

1. **Zero Samples (`0`)**: `9` classes (`blouse`, `t-shirt`, `collared-neck`, `sleeveless`, `cap-length`, `none`, `regular-sleeve`, `flutter-sleeve`, `cold-shoulder-sleeve`).
2. **Below Baseline (`1 to 19`)**: `13` classes (`square-neck`, `boat-neck`, `sweetheart-neck`, `halter-neck`, `high-neck`, `off-shoulder`, `three-quarter-sleeve`, `puff-sleeve`, `bell-sleeve`, `bishop-sleeve`, `raglan-sleeve`, `dolman-sleeve`, `kimono-sleeve`).
3. **Below Recommended (`20 to 99`)**: `5` classes (`crop-top`, `v-neck`, `scoop-neck`, `short-sleeve`, `elbow-length`).
4. **Sufficient Samples (`100+`)**: `2` classes (`round-neck`, `long-sleeve`).

---

## Manual-Review Workload Breakdown

- **Total Review-Eligible Records**: `815` records
- **Needing Only `garment_type` Confirmation**: `22` records
- **Needing 1 Additional Head**: `22` records
- **Needing 2 or More Additional Heads**: `793` records

> [!NOTE]
> **Minimum manual-review workload cannot yet be determined without image availability.**

---

## Feasibility Verdict

**Verdict**: **`NOT_FEASIBLE_WITH_CURRENT_VALIDATION_SUBSET`**

> [!WARNING]
> **Verdict Disclaimer**: This verdict applies strictly to the currently inspected Fashionpedia validation annotation package (`instances_attributes_val2020.json`, 817 spatial parent instances). It evaluates direct label availability on this validation subset and does not represent an evaluation of the full Fashionpedia training dataset (`instances_attributes_train2020.json`).

### Rationale
1. **Unreviewed Candidate Data**: Category 0 (`shirt, blouse`) and Category 1 (`top, t-shirt, sweatshirt`) instances are stored as `candidate_mapping`. Until human annotators review the priority queue, direct sample counts for `blouse` and `t-shirt` remain `0`.
2. **Class Shortages**: 9 out of 29 target taxonomy classes currently possess zero direct evidence on this validation subset, and 22 classes fall below the 20-sample baseline threshold.
