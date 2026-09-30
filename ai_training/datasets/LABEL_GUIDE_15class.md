# Label guide — the 15 selectable classes

Used by `docs/`, the review screen and the training manifests. "Trusted" = a person or the dataset's own
annotation stated it (`human_verified`, `fashionpedia_direct`, DeepFashion2 category). A rule, a CLIP pseudo-label or
a model guess is **never** ground truth. A label outside these 15 classes is masked for that head, never mapped to a
look-alike. If a feature cannot be seen (hidden by hair, arms, a jacket, a crop), the correct answer is
"uncertain — please select", not a guess.

## garment_type
| Class | Definition | Trusted data source |
|---|---|---|
| blouse | Woven-style top with the hem at or below the waist; usually softer, may have buttons/gathers. | Fashionpedia (human-verified subset only; the raw "shirt, blouse" category also contains men's shirts) |
| t-shirt | Knit top, hem at or below the waist, crew/V neck, short or long sleeve. | Fashionpedia (human-verified) |
| crop-top | Top whose hem ends above the natural waist. | Fashionpedia direct attribute |

A crop top and a T-shirt can look identical in a photo (the difference is the *length worn*). The photo alone cannot
establish the user's intent, so the app asks the user to confirm.

## neckline_type
| Class | Definition | Trusted data |
|---|---|---|
| round-neck | Curved neckline without collar. | Fashionpedia direct |
| v-neck | Two straight edges meeting at a point at centre front. | Fashionpedia direct |
| square-neck | Straight horizontal front edge with corners. | Fashionpedia direct (126 train) |
| collared-neck | A folded/standing collar piece is attached. | **none** (only a rule) → unsupported |
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
| regular-sleeve | Plain sleeve without gathering or flare. | **none** (only the "set-in" construction rule) → unsupported |
| puff-sleeve | Sleeve gathered/voluminous at the cap and/or hem. | Fashionpedia direct (142 train) |
| bell-sleeve | Sleeve flaring wider towards the hem. | Fashionpedia direct (58 train) |

Bishop, flutter, raglan, dolman and kimono sleeves are outside the 15 classes and are masked.

Uncertain items (annotator unsure, garment cut off, several garments) are excluded, not labelled.
