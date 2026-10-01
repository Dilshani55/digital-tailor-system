# Label guide — the 15 selectable classes

Used by `docs/`, the review screen and the training manifests. "Trusted" = a person or the dataset's own
annotation stated it (`human_verified`, `fashionpedia_direct`, DeepFashion2 category). A rule, a CLIP pseudo-label or
a model guess is **never** ground truth. A label outside these 15 classes is masked for that head, never mapped to a
look-alike. If a feature cannot be seen (hidden by hair, arms, a jacket, a crop), the correct answer is
"uncertain — please select", not a guess.

## garment_type
| Class | Definition | Trusted data source |
|---|---|---|
| blouse | **Woven** top (the drafting block is the woven bodice): blouses and women's button shirts, with or without sleeves. | Fashionpedia (human-verified subset only; the raw "shirt, blouse" category also contains men's shirts). Proxy: DeepFashion-MultiModal shop category `Blouses_Shirts` |
| t-shirt | **Knit tee with sleeves** (the drafting block is the knit bodice), crew or V neck, short or long sleeve. A sleeveless knit top (tank top) is **not** a T-shirt. | Fashionpedia (human-verified). Proxy: shop categories `Tees_Tanks` / `Graphic_Tees`, only when the human sleeve label is short or long |
| crop-top | Top whose hem ends **above the natural waist**, whatever the fabric. | Fashionpedia direct attribute. Proxy: DeepFashion-MultiModal "upper clothing does not cover the navel" |

These definitions follow the block the pattern engine drafts and were confirmed by the project owner on 1 Oct 2026.
A **proxy** is a shop category or a rule standing in for a human garment-type label: it is used for training with
half weight, is reported separately, and never counts as a trusted test label.

A crop top and a T-shirt can look identical in a photo (the difference is the *length worn*). The photo alone cannot
establish the user's intent, so the app asks the user to confirm.

## neckline_type
| Class | Definition | Trusted data |
|---|---|---|
| round-neck | Curved neckline without collar. | Fashionpedia direct |
| v-neck | Two straight edges meeting at a point at centre front. | Fashionpedia direct |
| square-neck | Straight horizontal front edge with corners. | Fashionpedia direct (126 train) |
| collared-neck | A shirt collar: a separate band folded around the neck (shirts, polo collars). A blazer or jacket **lapel is not** a collared neck. | **none yet**: only candidates (a collar part in Fashionpedia, the value "lapel" in DeepFashion-MultiModal). Labels come from the human review queue |
| off-shoulder | Neckline sits below the shoulder line; shoulders bare. | Fashionpedia direct |

## sleeve_length
| Class | Definition | Trusted data |
|---|---|---|
| sleeveless | No sleeve: vest, camisole/sling, tank. | DeepFashion2 categories vest + sling (+16 Fashionpedia) |
| short-sleeve | Sleeve ends above the elbow. | DeepFashion2 category 1; Fashionpedia direct |
| long-sleeve | Sleeve reaches the wrist. | DeepFashion2 category 2; Fashionpedia direct |

Cap, elbow-length and three-quarter sleeves are outside the 15 classes: masked, never converted to short/long.

## sleeve_style
| Class | Definition | Trusted data |
|---|---|---|
| none | Only for a sleeveless garment; derived from an explicit sleeveless label, never from a missing sleeve annotation. | derived from sleeveless |
| regular-sleeve | Plain set-in sleeve: smooth at the shoulder, no gathers, not flared; short or long. Raglan, dolman, kimono, flutter and cap sleeves are **not** regular (they are outside the 15 classes). | **none yet**: only candidates ("set-in sleeve" in Fashionpedia is a construction, not a style). Labels come from the human review queue |
| puff-sleeve | Sleeve gathered/voluminous at the cap and/or hem. | Fashionpedia direct (142 train) |
| bell-sleeve | Sleeve flaring wider towards the hem. | Fashionpedia direct (58 train) |

Bishop, flutter, raglan, dolman and kimono sleeves are outside the 15 classes and are masked.

Uncertain items (annotator unsure, garment cut off, several garments) are excluded, not labelled.

## Human review (collared-neck, regular-sleeve)

`ai_training/scripts/v2/build_review_queue_m42.py` picks 725 candidate photos (seed 42; each keeps its train / val /
test split) and `ai_training/tools/review_labels.py` shows them one at a time with these definitions. The reviewer
answers the class they **see** (the hint only says why the photo was picked), or `other` / `unclear`, which add no
label. An answer becomes a `human_verified` label; an answer that contradicts a trusted label of the same garment
(sleeve style `none` on a short-sleeved garment) is listed as a conflict and not used.
