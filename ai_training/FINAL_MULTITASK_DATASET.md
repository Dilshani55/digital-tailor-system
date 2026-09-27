# Final Multi-task Dataset Construction & 4-Head Coverage Audit (Milestone M9B Corrected)

## Executive Overview

Milestone M9B constructs the final multi-task training, validation, and test datasets for the **Digital Tailor AI** project. This dataset evaluates the complete Fashionpedia spatial parent manifest universe (**34,679 physical parent records**: 33,862 from `train2020` and 817 from `val2020`).

Composite record identifiers (`record_uid = fashionpedia:{source_partition}:{source_annotation_id}`) are used to prevent annotation ID collisions across partitions. The dataset integrates verified human review decisions from Milestone M9A, direct Fashionpedia ontology attribute extractions, official extracted garment crops from Milestone M8, and zero-shot CLIP screening pseudo-labels.

---

## Input Sources & Composite Identifier Architecture

The dataset is constructed by left-joining authoritative sources onto the complete spatial parent universe:

1. **Complete Spatial Parent Universe** (34,679 physical parent records):
   - **`train2020` Spatial Manifest** (`ai_training/data/processed/fashionpedia_train_spatial_manifest/all_instances_spatial.jsonl`): 33,862 physical records.
   - **`val2020` Spatial Manifest** (`ai_training/data/processed/fashionpedia_spatial_manifest/all_instances_spatial.jsonl`): 817 physical records.
   - **Composite Identifiers**: `record_uid` (`fashionpedia:train2020:123` vs `fashionpedia:val2020:123`) and `source_image_uid` (`fashionpedia:train2020:456` vs `fashionpedia:val2020:456`).

2. **Verified Human Review Decisions** (`ai_training/data/human_review/human_decisions.jsonl`):
   - Exactly **700** unique human decisions joined back to `review_queue.jsonl`.
   - Any overwritten decisions use the latest decision record per queue item.
   - Records labelled `reject` or `uncertain` by human reviewers are excluded from training and evaluation.

3. **Official Candidate Crops** (`ai_training/data/labelling_official/expanded_crop_manifest.jsonl`):
   - 3,000 selected official crop candidate records. Non-selected spatial records preserve verified source image paths and bounding boxes for future deterministic cropping.

4. **AI Pseudo-Label Screening** (`ai_training/data/labelling_official/accepted_pseudo_labels.jsonl`):
   - OpenAI CLIP ViT-B/32 zero-shot pseudo-labels (`decision == "accepted"`). Permitted ONLY in the `train` split (sample weight = `0.5`).

---

## Verified Human Decision Arithmetic (Exact 700 Total)

The human decision dataset was recalculated and strictly verified directly from `review_queue.jsonl` and `human_decisions.jsonl`:

| Review Purpose | Split | Queue Target | Blouse | T-Shirt | Crop-Top | Reject | Uncertain | Purpose Total |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `val_gold_set` | `val` | 150 | 41 | 37 | 43 | 27 | 2 | **150** |
| `test_gold_set` | `test` | 150 | 42 | 42 | 45 | 1 | 20 | **150** |
| `train_tshirt_priority` | `train` | 250 | 12 | 212 | 1 | 20 | 5 | **250** |
| `train_blouse_audit` | `train` | 100 | 75 | 0 | 0 | 2 | 23 | **100** |
| `train_croptop_audit` | `train` | 50 | 0 | 0 | 50 | 0 | 0 | **50** |
| **Total** | | **700** | **170** | **291** | **139** | **50** | **50** | **700** |

- **Sum of Purpose Totals**: 150 + 150 + 250 + 100 + 50 = **700**
- **Sum of Split Totals**: 150 (`val`) + 150 (`test`) + 400 (`train`) = **700**
- **Sum of Final-Label Totals**: 170 + 291 + 139 + 50 + 50 = **700**
- **Mutually Exclusive Exclusions**: 50 `human_reject` + 50 `human_uncertain` = 100 excluded human records.

---

## Partition & Supervised Heads Distribution

Out of the 34,679 evaluated spatial parent records:
- **Usable Dataset Records**: **15,422** (`train`: 10,905, `val`: 2,219, `test`: 2,298)
- **Excluded Records**: **19,257** (19,157 `no_permitted_labels_across_all_heads`, 50 `human_reject`, 50 `human_uncertain`)
- **Total**: 15,422 + 19,257 = **34,679** physical records.

### Supervised Heads Distribution (Usable Records)

| Supervised Heads Count | Record Count | Percentage |
| :--- | :--- | :--- |
| **1 Head Supervised** | 9,991 | 64.8% |
| **2 Heads Supervised** | 4,301 | 27.9% |
| **3 Heads Supervised** | 1,053 | 6.8% |
| **4 Heads Supervised** | 77 | 0.5% |
| **Total Usable Records** | **15,422** | **100.0%** |

---

## Detailed 28-Class Taxonomy Coverage Audit

| Head | Class | Total Usable | Train | Val | Test | Provenance Breakdown |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **garment_type** | `blouse` | 361 | 278 | 41 | 42 | 170 Human / 191 Pseudo |
| **garment_type** | `t-shirt` | 291 | 212 | 37 | 42 | 291 Human |
| **garment_type** | `crop-top` | 908 | 820 | 43 | 45 | 139 Human / 764 Direct / 5 Pseudo |
| **neckline_type** | `round-neck` | 3666 | 2597 | 514 | 555 | 3666 Direct |
| **neckline_type** | `v-neck` | 1191 | 815 | 169 | 207 | 1191 Direct |
| **neckline_type** | `square-neck` | 175 | 126 | 24 | 25 | 175 Direct |
| **neckline_type** | `scoop-neck` | 1305 | 930 | 180 | 195 | 1305 Direct |
| **neckline_type** | `boat-neck` | 671 | 458 | 108 | 105 | 671 Direct |
| **neckline_type** | `sweetheart-neck` | 279 | 192 | 41 | 46 | 279 Direct |
| **neckline_type** | `halter-neck` | 123 | 86 | 20 | 17 | 123 Direct |
| **neckline_type** | `high-neck` | 349 | 258 | 46 | 45 | 349 Direct |
| **neckline_type** | `collared-neck` | **0** | 0 | 0 | 0 | Masked (Candidate Mapping) |
| **neckline_type** | `off-shoulder` | 220 | 146 | 30 | 44 | 220 Direct |
| **sleeve_length** | `sleeveless` | 22 | 16 | 4 | 2 | 22 Direct |
| **sleeve_length** | `cap-length` | **0** | 0 | 0 | 0 | Masked (Candidate Mapping) |
| **sleeve_length** | `short-sleeve` | 3888 | 2722 | 594 | 572 | 3888 Direct |
| **sleeve_length** | `elbow-length` | 766 | 556 | 99 | 111 | 766 Direct |
| **sleeve_length** | `three-quarter-sleeve` | 1111 | 770 | 175 | 166 | 1111 Direct |
| **sleeve_length** | `long-sleeve` | 5557 | 3895 | 809 | 853 | 5557 Direct |
| **sleeve_style** | `none` | **0** | 0 | 0 | 0 | Masked (Candidate Mapping) |
| **sleeve_style** | `regular-sleeve` | **0** | 0 | 0 | 0 | Masked (Candidate Mapping) |
| **sleeve_style** | `puff-sleeve` | 196 | 142 | 21 | 33 | 196 Direct |
| **sleeve_style** | `bell-sleeve` | 91 | 58 | 18 | 15 | 91 Direct |
| **sleeve_style** | `bishop-sleeve` | 112 | 84 | 10 | 18 | 112 Direct |
| **sleeve_style** | `flutter-sleeve` | **0** | 0 | 0 | 0 | Masked (Candidate Mapping) |
| **sleeve_style** | `raglan-sleeve` | 450 | 315 | 63 | 72 | 450 Direct |
| **sleeve_style** | `dolman-sleeve` | 229 | 167 | 32 | 30 | 229 Direct |
| **sleeve_style** | `kimono-sleeve` | 99 | 67 | 12 | 20 | 99 Direct |

---

## Data Leakage & Integrity Verification

- **Zero Cross-Split Image Leakage**: 0 composite image UIDs occur across multiple splits (`train`, `val`, `test`).
- **Zero Record Overwrite**: All 34,679 composite `record_uid` entries are unique.
- **Zero Pseudo/Direct Garment Labels in Val/Test**: 0 pseudo-labels and 0 direct Fashionpedia labels supervise `garment_type` in validation or test splits. All 250 evaluation garment labels are 100% `human_verified`.
- **Unused Val/Test Images**: Exactly 2,560 physical extracted images in `val`/`test` folders are not referenced by the upper-garment spatial parent manifest.
- **SHA-256 Checksums**: Verified matching SHA-256 signatures for `train.jsonl`, `val.jsonl`, `test.jsonl`, `excluded.jsonl`, `coverage_summary.json`, `gold_topup_requirements.json`.

---

## Readiness Verdict

**`READY_FOR_PARTIAL_COVERAGE_BASELINE_ONLY`**

*Rationale*:
All four heads are functional and partial-label masked-loss training is supported. However, five taxonomy classes (`collared-neck`, `cap-length`, `none`, `regular-sleeve`, `flutter-sleeve`) currently have zero direct positive training samples due to candidate-mapping status in the Fashionpedia ontology. Therefore, the dataset is ready for baseline multi-task model training on supported classes, but is NOT ready for full 28-class training.

---

## Reproducibility Commands

```bash
# Rebuild final dataset
python ai_training/scripts/build_final_multitask_dataset.py

# Validate final dataset
python ai_training/scripts/validate_final_multitask_dataset.py

# Run complete test suite
python -m unittest discover -s ai_training/tests -p "test_*.py" -v
```
