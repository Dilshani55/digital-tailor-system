# Targeted Human Verification Protocol & Gold-Label Review (Milestone M9A)

## 1. Overview & Research Protocol

In the **Digital Tailor** custom garment synthesis and recommendation system, AI zero-shot pseudo-labels (generated via CLIP or heuristics) serve as screening mechanisms. **AI pseudo-labels are not gold ground truth.**

To ensure rigorous evaluation and model training:
- Validation (`val`) and test (`test`) benchmarks **must be human verified**.
- Only an explicit human review action sets `human_verified=true`.
- Unreviewed candidates retain `human_verified=false` and `human_label=null`.
- Human decisions are recorded incrementally in `ai_training/data/human_review/human_decisions.jsonl` (which is kept 100% ignored by Git).

---

## 2. Garment Label Definitions

Reviewers must apply the following 5 exclusive labels when evaluating crops:

| Label | Definition & Rules |
|---|---|
| **`crop-top`** | A women’s upper garment whose hem clearly ends above the natural waist or visibly exposes the midriff. **Takes precedence over blouse or t-shirt.** |
| **`t-shirt`** | A women’s casual knitted tee with recognizable T-shirt construction (crewneck, v-neck, casual short sleeves). Exclude sweatshirts, hoodies, jackets, dresses, and men’s garments. |
| **`blouse`** | A women’s blouse or non-T-shirt upper-body top (button-up, woven, dressy feminine top). Exclude men’s shirts, sweatshirts, jackets, dresses, and crop-tops. |
| **`reject`** | Men’s garment, shirt outside project scope, sweatshirt, hoodie, jacket, dress, non-garment, severe occlusion, unusable crop, or clearly out-of-scope image. |
| **`uncertain`** | The reviewer cannot reliably distinguish the correct project label from the crop image. |

---

## 3. Targeted Review Queue Priorities & Capacity

The human review queue is constructed deterministically up to a **maximum of 700 unique records**:

1. **Gold Validation Set (`val_gold_set`)**:
   - Split: `val`
   - Target: Up to 50 records per proposed class (`blouse`: 50, `t-shirt`: 50, `crop-top`: 50).
   - Maximum: **150 records**.
2. **Gold Test Set (`test_gold_set`)**:
   - Split: `test`
   - Target: Up to 50 records per proposed class (`blouse`: 50, `t-shirt`: 50, `crop-top`: 50).
   - Maximum: **150 records**.
3. **Training Correction Set (`train_correction_set`)**:
   - Split: `train`
   - Target breakdown:
     - **`t-shirt` priority**: Up to **250 records** (prioritizing t-shirt shortage).
     - **`blouse` audit**: Up to **100 records**.
     - **`crop-top` audit**: Up to **50 records**.
   - Maximum: **400 records**.

---

## 4. Candidate Selection Rules

- **Priority Order**:
  1. Fashionpedia candidate evidence match (`candidate_garment_type == proposed_class`).
  2. CLIP accepted predictions (`decision == "accepted"`).
  3. Manual review records (`decision == "manual_review"`).
- **T-Shirt Priority Rule**: For `t-shirt` shortage, records proposed as `t-shirt` by Fashionpedia evidence are prioritized even if CLIP placed them in `manual_review`.
- **Exclusion**: Confident out-of-scope `rejected` records are excluded.
- **Zero Leakage**: No `source_annotation_id` duplication; zero `source_image_id` crossing splits.

---

## 5. Review UI Application Usage

A standalone review web application is provided under `ai_training/review_app.py`.

### Launching the Review Server:
```bash
python ai_training/review_app.py \
  --queue ai_training/data/human_review/review_queue.jsonl \
  --decisions ai_training/data/human_review/human_decisions.jsonl \
  --policy ai_training/config/human_review_policy.json \
  --port 5050 \
  --reviewer-id human_reviewer_01
```

> [!IMPORTANT]
> Do NOT launch the review server automatically in scripts. Reviewers must explicitly launch the server.

### UI Keyboard Shortcuts:
- `[1]`: Submit `blouse`
- `[2]`: Submit `t-shirt`
- `[3]`: Submit `crop-top`
- `[4]`: Submit `reject`
- `[5]`: Submit `uncertain`
- `[S]`: Skip item
- `[Left Arrow]`: Previous item
- `[Right Arrow]`: Next item

### Decision Correction & Resume:
- If an item was previously reviewed, its current verified label is highlighted in green.
- Selecting a new label prompts for confirmation before overwriting the saved decision.
- Progress counters display live verified, remaining, and total items.

---

## 6. Decision Schema & Atomic Persistence

Saved human decisions are written to `ai_training/data/human_review/human_decisions.jsonl`.

```json
{
  "source_annotation_id": 101,
  "source_image_id": 201,
  "split": "val",
  "crop_path": "ai_training/data/images/fashionpedia_official_expanded/crops/201_101_crop.jpg",
  "human_label": "blouse",
  "human_verified": true,
  "reviewer_id": "human_reviewer_01",
  "reviewed_at": "2026-09-27T16:30:00.000000+00:00",
  "previous_pseudo_label": "blouse",
  "fashionpedia_evidence": {
    "candidate_garment_type": "blouse",
    "candidate_garment_reason": "Fashionpedia Cat 0 shirt, blouse"
  },
  "decision_version": "1.0.0"
}
```

### Security & Integrity Controls:
- **Atomic Writes**: Written to a temporary file before atomic replacement (`os.replace`) to prevent file corruption.
- **Path Traversal Prevention**: Endpoint serves only image paths that match valid records in the loaded queue.

---

## 7. Pipeline Commands

```bash
# 1. Build Review Queue
python ai_training/scripts/build_human_review_queue.py \
  --labelling-dir ai_training/data/labelling_official/ \
  --policy ai_training/config/human_review_policy.json \
  --output-dir ai_training/data/human_review/

# 2. Validate Queue & Decisions
python ai_training/scripts/validate_human_review.py \
  --review-dir ai_training/data/human_review/ \
  --policy ai_training/config/human_review_policy.json

# 3. Launch Review UI (port 5050)
python ai_training/review_app.py --port 5050
```
