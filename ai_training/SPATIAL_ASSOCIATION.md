# Evidence-Preserving Spatial Part-to-Garment Association (Milestone AI-4B)

## Overview

Milestone **AI-4B** implements a deterministic, evidence-preserving spatial association pipeline that links standalone Fashionpedia garment-part annotations:
- Category 28: `collar`
- Category 31: `sleeve`
- Category 33: `neckline`

to their corresponding parent upper-garment instances (Category 0 `shirt, blouse` and Category 1 `top, t-shirt, sweatshirt`) within the same image frame (`image_id`).

---

## Why Intersection over Union (IoU) Alone Is Unsuitable

Standard Intersection over Union (IoU):
$$\text{IoU} = \frac{\text{Area}(B_{\text{part}} \cap B_{\text{parent}})}{\text{Area}(B_{\text{part}} \cup B_{\text{parent}})}$$

is mathematically unsuitable for associating small garment parts (sleeves, necklines, collars) with large parent garment boxes:
1. **Area Disparity**: A sleeve or neckline bounding box is typically 5%–15% the size of the full upper-garment bounding box.
2. **Artificial Suppression**: Even if a sleeve box is 100% contained within a blouse bounding box, the union area $\text{Area}(B_{\text{part}} \cup B_{\text{parent}}) \approx \text{Area}(B_{\text{parent}})$, driving IoU values down to $\approx 0.05 - 0.15$.
3. **Misleading Thresholding**: Applying standard IoU thresholds (e.g., IoU >= 0.50) would falsely reject virtually 100% of valid garment-part annotations.

---

## Part-Coverage & Centre-Inside Method

To resolve spatial association accurately without area bias, AI-4B uses a dual geometric coverage and center-localization approach:

### 1. Part Coverage Metric
$$\text{part\_coverage} = \frac{\text{Area}(B_{\text{part}} \cap B_{\text{parent}})}{\text{Area}(B_{\text{part}})}$$
Measures the proportion of the part bounding box that lies inside the parent garment bounding box.

### 2. Parent Coverage Metric
$$\text{parent\_coverage} = \frac{\text{Area}(B_{\text{part}} \cap B_{\text{parent}})}{\text{Area}(B_{\text{parent}})}$$
Measures the proportion of the parent garment bounding box occupied by the part.

### 3. Centre-Inside Constraint
Let $(c_{px}, c_{py}) = (x_p + \frac{w_p}{2}, y_p + \frac{h_p}{2})$ be the center coordinates of the part bounding box. The center-inside constraint requires:
$$x_g \le c_{px} \le x_g + w_g \quad \text{and} \quad y_g \le c_{py} \le y_g + h_g$$

### 4. Normalized Centre Distance
$$\text{center\_dist} = \sqrt{(c_{px} - c_{gx})^2 + (c_{py} - c_{gy})^2}$$
$$\text{norm\_centre\_dist} = \min\left(1.0, \frac{\text{center\_dist}}{\sqrt{w_g^2 + h_g^2}}\right)$$

---

## Scoring Formula & Threshold Configuration

For any part annotation $P$ and candidate parent garment $G$ in the same image frame, a spatial score is calculated:

$$\text{Score}(P, G) = \begin{cases} 0.60 \cdot \text{part\_coverage} + 0.30 \cdot (1.0 - \text{norm\_centre\_dist}) + 0.10 \cdot \text{parent\_coverage} & \text{if } \text{part\_coverage} \ge 0.80 \text{ and } \text{part\_centre\_inside} = \text{True} \\ 0.0 & \text{otherwise} \end{cases}$$

### Configured Threshold Parameters (`ai_training/config/part_association.json`)
- `minimum_part_coverage`: `0.80` (at least 80% of part area inside parent box)
- `minimum_score_margin`: `0.15` (top score must exceed 2nd-best score by at least 0.15)
- `centre_inside_parent`: `true` (part center must fall inside parent bounding box)

---

## Unique-Winner Margin & Ambiguity Handling

When an image contains multiple upper garments (e.g., layered tops or multiple people in frame):
1. **Candidate Ranking**: All candidate parent garments are scored.
2. **Single Winner**: If exactly one candidate parent qualifies with $\text{Score} > 0.0$, the part is assigned to that parent.
3. **Score Margin Rule**: If multiple parent candidates qualify ($S_1 \ge S_2 \ge \dots$):
   - If $S_1 - S_2 \ge 0.15$: Candidate 1 is declared the clear spatial winner.
   - If $S_1 - S_2 < 0.15$: Spatial association is flagged as **ambiguous**.
4. **Ambiguity Policy**: Ambiguous parts are **never** assigned automatically to any parent garment. They are recorded in `ambiguous_associations.jsonl` for human manual review.

---

## Evidence Provenance & Conflict Handling

### Complete Evidence Provenance
When a part is associated with a parent instance, full origin metadata is attached:
- `part_annotation_id`
- `part_category_id` & `part_category_name`
- `part_attribute_ids` & `part_attribute_names`
- `geometry_metrics` (intersection area, coverages, center distance)
- `association_score` & `winning_margin`

### Conflict Handling
If multiple attached parts or parent attributes yield conflicting target labels for the same head (e.g., one sleeve part marked `short-sleeve` and another marked `long-sleeve`):
- The head evaluation records `CONFLICT_HEAD_<HEAD_NAME>`.
- The parent instance is assigned decision = `manual_review`.

---

## Limitations of Bounding-Box-Only Association

1. **2D Bounding Box Overlap**: In photographs with layered garments (e.g. jacket over blouse) or overlapping people, 2D rectangular bounding boxes can overlap even when garments are spatially separate in 3D space.
2. **Pseudo-Label Classification**: Spatial association is a **conservative pseudo-label estimation method**, not manual ground truth.
3. **Candidate Mapping Preservation**: Category 0 (`shirt, blouse`), Category 1 (`top, t-shirt, sweatshirt`), Category 28 (`collar` -> `collared-neck`), and derived `sleeve_style = none` remain classified as `candidate_mapping` and require human verification before automated model training.

---

## Image Copyright & Licensing Disclaimer

- Preparing spatial candidate manifests does **not** download, distribute, or alter image binaries.
- No image licensing approval is implied. Fashionpedia image binaries remain subject to their original copyright holders and source terms as audited in `DATASET_SOURCE_AUDIT.md`.
