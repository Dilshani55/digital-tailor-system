# Final Multi-task Dataset Construction & 4-Head Coverage Audit (Milestone M10 Completed)

## Executive Overview

Milestone M10 updates the final multi-task training, validation, and test datasets for the **Digital Tailor AI** project by completing automatic training-label derivation for the final 28-class taxonomy. This dataset evaluates the complete Fashionpedia spatial parent manifest universe (**34,679 physical parent records**: 33,862 from `train2020` and 817 from `val2020`).

Composite record identifiers (`record_uid = fashionpedia:{source_partition}:{source_annotation_id}`) are used to prevent annotation ID collisions across partitions. The dataset integrates verified human review decisions from Milestone M9A, direct Fashionpedia ontology attribute extractions, official extracted garment crops from Milestone M8, zero-shot CLIP screening pseudo-labels, and automatic Fashionpedia rule-derived weak labels from Milestone M10.

---

## Input Sources & Composite Identifier Architecture

The dataset is constructed by left-joining authoritative sources onto the complete spatial parent universe:

1. **Complete Spatial Parent Universe** (34,679 physical parent records):
   - **`train2020` Spatial Manifest** (`ai_training/data/processed/fashionpedia_train_spatial_manifest/all_instances_spatial.jsonl`): 33,862 physical records.
   - **`val2020` Spatial Manifest** (`ai_training/data/processed/fashionpedia_spatial_manifest/all_instances_spatial.jsonl`): 817 physical records.
   - **Composite Identifiers**: `record_uid` (`fashionpedia:train2020:123` vs `fashionpedia:val2020:123`) and `source_image_uid` (`fashionpedia:train2020:456` vs `fashionpedia:val2020:456`).

2. **Verified Human Review Decisions** (`ai_training/data/human_review/human_decisions.jsonl`):
   - Exactly **700** unique human decisions joined back to `review_queue.jsonl`.
   - Records labelled `reject` or `uncertain` by human reviewers are excluded from training and evaluation.

3. **Official Candidate Crops** (`ai_training/data/labelling_official/expanded_crop_manifest.jsonl`):
   - 3,000 selected official crop candidate records.

4. **AI Pseudo-Label Screening** (`ai_training/data/labelling_official/accepted_pseudo_labels.jsonl`):
   - OpenAI CLIP ViT-B/32 zero-shot pseudo-labels (`decision == "accepted"`). Permitted ONLY in the `train` split (sample weight = `0.5`).

5. **M10 Automatic Weak Label Policies** (`ai_training/config/weak_label_policy.json`):
   - Derives weak labels for 5 zero-sample classes (`collared-neck`, `cap-length`, `none`, `regular-sleeve`, `flutter-sleeve`) strictly for the `train` split (sample weight = `0.8`).

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

---

## Partition & Supervised Heads Distribution

Out of the 34,679 evaluated spatial parent records:
- **Usable Dataset Records**: **15,794** (`train`: 11,277, `val`: 2,219, `test`: 2,298)
- **Excluded Records**: **18,885** (18,785 `no_permitted_labels_across_all_heads`, 50 `human_reject`, 50 `human_uncertain`)
- **Total**: 15,794 + 18,885 = **34,679** physical records.

---

## Detailed 28-Class Taxonomy Coverage Audit (M10 Completed)

| Head | Class | Total Usable | Train | Val | Test | Provenance Breakdown |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **garment_type** | `blouse` | 361 | 278 | 41 | 42 | 170 Human / 191 Pseudo |
| **garment_type** | `t-shirt` | 291 | 212 | 37 | 42 | 291 Human |
| **garment_type** | `crop-top` | 908 | 820 | 43 | 45 | 139 Human / 764 Direct / 5 Pseudo |
| **neckline_type** | `round-neck` | 3,666 | 2,597 | 514 | 555 | 3,666 Direct |
| **neckline_type** | `v-neck` | 1,191 | 815 | 169 | 207 | 1,191 Direct |
| **neckline_type** | `square-neck` | 175 | 126 | 24 | 25 | 175 Direct |
| **neckline_type** | `scoop-neck` | 1,305 | 930 | 180 | 195 | 1,305 Direct |
| **neckline_type** | `boat-neck` | 671 | 458 | 108 | 105 | 671 Direct |
| **neckline_type** | `sweetheart-neck` | 279 | 192 | 41 | 46 | 279 Direct |
| **neckline_type** | `halter-neck` | 123 | 86 | 20 | 17 | 123 Direct |
| **neckline_type** | `high-neck` | 349 | 258 | 46 | 45 | 349 Direct |
| **neckline_type** | `collared-neck` | **500** | 500 | 0 | 0 | 500 Rule-Derived (Weak) |
| **neckline_type** | `off-shoulder` | 220 | 146 | 30 | 44 | 220 Direct |
| **sleeve_length** | `sleeveless` | 22 | 16 | 4 | 2 | 22 Direct |
| **sleeve_length** | `cap-length` | **479** | 479 | 0 | 0 | 479 Rule-Derived (Weak) |
| **sleeve_length** | `short-sleeve` | 3,888 | 2,722 | 594 | 572 | 3,888 Direct |
| **sleeve_length** | `elbow-length` | 766 | 556 | 99 | 111 | 766 Direct |
| **sleeve_length** | `three-quarter-sleeve` | 1,111 | 770 | 175 | 166 | 1,111 Direct |
| **sleeve_length** | `long-sleeve` | 5,557 | 3,895 | 809 | 853 | 5,557 Direct |
| **sleeve_style** | `none` | **16** | 16 | 0 | 0 | 16 Rule-Derived (Weak) |
| **sleeve_style** | `regular-sleeve` | **500** | 500 | 0 | 0 | 500 Rule-Derived (Weak) |
| **sleeve_style** | `puff-sleeve` | 196 | 142 | 21 | 33 | 196 Direct |
| **sleeve_style** | `bell-sleeve` | 91 | 58 | 18 | 15 | 91 Direct |
| **sleeve_style** | `bishop-sleeve` | 112 | 84 | 10 | 18 | 112 Direct |
| **sleeve_style** | `flutter-sleeve` | **59** | 59 | 0 | 0 | 59 Rule-Derived (Weak) |
| **sleeve_style** | `raglan-sleeve` | 450 | 315 | 63 | 72 | 450 Direct |
| **sleeve_style** | `dolman-sleeve` | 229 | 167 | 32 | 30 | 229 Direct |
| **sleeve_style** | `kimono-sleeve` | 99 | 67 | 12 | 20 | 99 Direct |

---

## Data Leakage & Integrity Verification

- **Zero Cross-Split Image Leakage**: 0 composite image UIDs occur across multiple splits (`train`, `val`, `test`).
- **Zero Record Overwrite**: All 34,679 composite `record_uid` entries are unique.
- **Zero Weak/Pseudo Labels in Val/Test**: 0 pseudo-labels and 0 weak rule-derived labels enter validation or test splits. All 250 evaluation garment labels are 100% `human_verified`.
- **SHA-256 Checksums**: Verified matching SHA-256 signatures for `train.jsonl`, `val.jsonl`, `test.jsonl`, `excluded.jsonl`, `coverage_summary.json`, `manifest_checksums.json`.

---

## Readiness Verdict

**`READY_FOR_MULTI_TASK_TRAINING`**

*Rationale*:
All four heads are fully functional and masked multi-task training is supported. Every single one of the 28 taxonomy classes has valid, usable training samples in the `train` split.

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
