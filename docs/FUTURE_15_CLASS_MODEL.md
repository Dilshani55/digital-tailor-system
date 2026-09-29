# Future 15-class (3 / 5 / 3 / 4) model — NOT trained, NOT deployed

**Status: planned. Nothing in this document has been trained or evaluated, and nothing here is connected to the backend or the frontend.** The application today runs the unchanged M13 checkpoint (3 / 10 / 6 / 9 outputs) and only *limits what the user can choose* to the 15 active classes (see [ARCHITECTURE](ARCHITECTURE.md)). The old checkpoint is never reused for the new model.

## 1. The 15 classes (exact order)

| Head | Classes (output order) |
|---|---|
| garment_type (3) | blouse, t-shirt, crop-top |
| neckline_type (5) | round-neck, v-neck, square-neck, collared-neck, off-shoulder |
| sleeve_length (3) | sleeveless, short-sleeve, long-sleeve |
| sleeve_style (4) | none, regular-sleeve, puff-sleeve, bell-sleeve |

Versioned configuration: `ai_training/config/classes_v2_15class.json` (schema 2.0.0, `PLANNED`). Loading a 3/10/6/9 file with the new code raises an error.

## 2. Label rules

* A label outside the 15 classes is **masked for that head only** (mask 0, label empty). It is never converted to a look-alike: cap/elbow-length ↛ short-sleeve, three-quarter ↛ long-sleeve, boat/scoop ↛ round-neck, bishop/flutter ↛ puff-sleeve.
* `sleeve_style = none` only when the same record has an explicit, trusted `sleeveless`. A missing sleeve annotation is not evidence.
* Only `human_verified` and `fashionpedia_direct` (and `none` derived from those) count as **trusted**. Rule-derived, CLIP-pseudo-labelled and "candidate mapping" labels never count toward readiness.
* Leakage control: splits are by source image; val/test images with a near-duplicate (dHash ≤ 4) in train are excluded from evaluation; a human-labelled image inherits its source image's split and is checked for near-duplicates before use.

## 3. Exact trustworthy counts today (after masking and near-duplicate exclusion)

Produced by `build_15class_manifests.py`; `n (trusted)`; targets are train ≥ 100, val ≥ 30, test ≥ 30 trusted per class (`config/label_targets_15class.json`, with the reasoning).

| Class | Train | Val | Test | Missing (train / val / test) |
|---|---:|---:|---:|---|
| blouse | 278 (87) | 39 (39) | 42 (42) | 13 / 0 / 0 |
| t-shirt | 212 (212) | 36 (36) | 40 (40) | 0 / 0 / 0 |
| crop-top | 820 (815) | 39 (39) | 44 (44) | 0 / 0 / 0 |
| round-neck | 2597 (2597) | 497 (497) | 527 (527) | 0 / 0 / 0 |
| v-neck | 815 (815) | 160 (160) | 197 (197) | 0 / 0 / 0 |
| square-neck | 126 (126) | 21 (21) | 24 (24) | 0 / **9** / **6** |
| collared-neck | 493 (**0**) | **0** | **0** | **100 / 30 / 30** |
| off-shoulder | 146 (146) | 25 (25) | 42 (42) | 0 / **5** / 0 |
| sleeveless | 16 (16) | 4 (4) | 2 (2) | **84 / 26 / 28** |
| short-sleeve | 2722 (2722) | 543 (543) | 522 (522) | 0 / 0 / 0 |
| long-sleeve | 3895 (3895) | 778 (778) | 824 (824) | 0 / 0 / 0 |
| none | 16 (16) | **0** | **0** | **84 / 30 / 30** |
| regular-sleeve | 494 (**0**) | **0** | **0** | **100 / 30 / 30** |
| puff-sleeve | 142 (142) | 19 (19) | 33 (33) | 0 / **11** / 0 |
| bell-sleeve | 58 (58) | 18 (18) | 13 (13) | **42 / 12 / 17** |

**Verdict: NOT_READY** — 9 of the 15 classes lack trusted evidence: blouse (train only), square-neck, collared-neck, off-shoulder, sleeveless, none, regular-sleeve, puff-sleeve, bell-sleeve. Masking removes many labels. Retained training labels per head (sum of the train column): garment 1,310, neckline 4,177 (was 6,101), sleeve length 6,633 (was 8,438), sleeve style 710 (was 1,401) — see `counts.json`.

## 4. What must be done (human-review queue)

`build_label_queue_15class.py` writes `ai_training/data/label_queue_15class/queue.jsonl|csv` with real annotated garments a person can confirm. Each row has a *hint* (never a label) and an empty decision. Current queue (1,413 rows, ≈ 3× the missing count):

| Class | Candidate evidence | Pool (train / val / test) | Queued | Yield |
|---|---|---|---|---|
| collared-neck | collar part annotated, candidate mapping | 3212 / 703 / 739 | 300 / 90 / 90 | unknown until reviewed |
| regular-sleeve | set-in sleeve attribute (204), candidate mapping | 5912 / 1259 / 1259 | 300 / 90 / 90 | unknown until reviewed |
| sleeveless | shirt/blouse/top with **no** sleeve part annotated (a reason to look only) | 7386 / 1560 / 1574 | 252 / 78 / 84 | **low expected**: only 22 sleeveless annotations exist in all 34,679 instances |
| blouse (train) | garment-category mapping | 4269 / 918 / 934 | 39 / 0 / 0 | high |
| none | derived automatically from accepted human `sleeveless` | – | – | follows sleeveless |
| square-neck, off-shoulder, puff-sleeve, bell-sleeve | **pool exhausted** – every annotated example is already used | 0 | 0 | needs images from another source |

Reviewers write decisions (`{"queue_id", "decision": "<active class | reject | uncertain>", "reviewer_id", "reviewed_at"}`) to `decisions.jsonl`. Only a decision that is an active class of the row's head, with a named reviewer, is accepted; anything else is reported as a problem. Accepted labels are added as `human_verified` for that head only.

Realistic outlook: collared-neck, regular-sleeve and blouse can probably reach the targets by reviewing the queue (thousands of candidates). **sleeveless (and therefore none) probably cannot** from Fashionpedia alone; square-neck, off-shoulder, puff and bell need additional annotated images (another dataset, or new photographs labelled by hand). A new locked benchmark with ≥ 10 images per class, disjoint from training, is also required (the current 60-image benchmark has none of square-neck, collared-neck, sleeveless, none, regular-sleeve).

## 5. Commands (in order; do not skip the guard)

```powershell
$env:PYTHONPATH="."
# 1. exact counts + readiness (rebuild after every batch of reviewed decisions)
backend\venv\Scripts\python ai_training\scripts\build_15class_manifests.py
#    after reviewing: 
backend\venv\Scripts\python ai_training\scripts\build_15class_manifests.py --queue ai_training\data\label_queue_15class\queue.jsonl --decisions <decisions.jsonl> --near-duplicate-check
# 2. what to review
backend\venv\Scripts\python ai_training\scripts\build_label_queue_15class.py
# 3. training – refuses (exit code 2) unless the verdict is READY and the manifests are unchanged
backend\venv\Scripts\python ai_training\scripts\train_15class_guarded.py
#    exact command it will run:  ... train_15class_guarded.py --print-command
```

**Do not run step 3 until step 1 prints `VERDICT: READY`.** The guard enforces this, verifies the manifest checksums, never accepts an initial checkpoint, refuses to write into the production model folder, and after training verifies that the checkpoint heads are 3/5/3/4.

## 6. Deployment (future)

The M13 checkpoint stays the production model and safe backup until the new model has passed: (1) the readiness targets; (2) validation and a **new** locked benchmark; (3) load + inference smoke tests in the production code with head sizes 3/5/3/4; (4) API tests; (5) UI tests; (6) an acceptance gate adapted to compare the two taxonomies on the classes they share. Only then can the backend `DEFAULT_HEAD_DIMS`, `classes.json` and `MODEL_TAXONOMY` be switched together, in one reviewed change.
