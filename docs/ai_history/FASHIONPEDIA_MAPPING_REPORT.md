# Fashionpedia Ontology Inspection & 29-Label Mapping Report

> **Milestone AI-3 Metadata Mapping Report**
> *Note: This document presents the official metadata inspection of the Fashionpedia ontology and records evidence-based label mappings for all 29 target classes in the Digital Tailor System YOLOv8 multi-task model.*
> **Taxonomy Update Note**: The original inspection evaluated 29 classes with 1 unsupported class (`cold-shoulder-sleeve`). The active taxonomy has been finalized to 28 classes by removing `cold-shoulder-sleeve` and reindexing `sleeve_style` from 0 to 8 (`kimono-sleeve` is index 8).

---

## 1. Inspected Source & Metadata Verification

The ontology inspection script `ai_training/scripts/inspect_fashionpedia_ontology.py` was executed against the official downloaded Fashionpedia annotation metadata:

* **Official Source URL**: `https://s3.amazonaws.com/ifashionist-dataset/annotations/instances_attributes_val2020.json`
* **Local File Path**: `ai_training/data/raw/fashionpedia/instances_attributes_val2020.json`
* **File Size**: `14,533,475 bytes` (~14.53 MB)
* **SHA-256 Checksum**: `f831f415edad12d52acde8b138fe7ebd1592b57bf0dcd6a3b63ba8cabd208223`
* **Git Ignored Verification**: Path `ai_training/data/` is strictly ignored by Git via `ai_training/.gitignore`.

---

## 2. Actual JSON Structure & Correct Category Boundaries

The downloaded COCO-style JSON annotation metadata contains the following top-level structure:
* Top-level keys: `info`, `licenses`, `images`, `annotations`, `categories`, `attributes`.

### Recalculated Category & Attribute Totals
* **Categories**: **46** continuous entries, zero-indexed from **IDs 0 to 45**.
  * **27** main apparel & accessory categories (**IDs 0–26 inclusive**):
    * IDs 0–12 represent main clothing items (`shirt, blouse`, `top, t-shirt, sweatshirt`, `sweater`, `cardigan`, `jacket`, `vest`, `pants`, `shorts`, `skirt`, `coat`, `dress`, `jumpsuit`, `cape`).
    * IDs 13–26 represent headwear, footwear, bags, and accessories (`glasses`, `hat`, `headband/head covering`, `tie`, `glove`, `watch`, `belt`, `leg warmer`, `tights/stockings`, `sock`, `shoe`, `bag/wallet`, `scarf`, `umbrella`).
  * **19** apparel parts, closures, and decorations (**IDs 27–45 inclusive**):
    * **ID 27 (`hood`)** marks the exact boundary beginning the second group.
    * IDs 27–33 represent garment parts (`hood`, `collar`, `lapel`, `epaulette`, `sleeve`, `pocket`, `neckline`).
    * IDs 34–35 represent closures (`buckle`, `zipper`).
    * IDs 36–45 represent decorative elements (`applique`, `bead`, `bow`, `flower`, `fringe`, `ribbon`, `rivet`, `ruffle`, `sequin`, `tassel`).
* **Attributes**: **294** fine-grained attributes (IDs 1–340 with non-sequential numbering) across 20 supercategories (`neckline type`, `length`, `nickname`, `silhouette`, `waistline`, `opening type`, `textile pattern`, etc.).
* **Duplicates**: 0 duplicate IDs and 0 duplicate names detected in categories or attributes.

---

## 3. Upgraded Schema & 29-Label Mapping Table

The complete taxonomy mapping is recorded in [`ai_training/config/fashionpedia_mapping.json`](file:///C:/Research/Developing/digital-tailor-system/ai_training/config/fashionpedia_mapping.json) using an upgraded array-based evidence schema (`source_evidence: [...]`) and explicit `mapping_logic` (`single`, `any`, `all`, `derived`):

| Model Head | Target Label | Status | Mapping Logic | Source Evidence (IDs & Names) | Mapping Rule / Limitation Summary |
| :--- | :--- | :---: | :---: | :--- | :--- |
| `garment_type` | `blouse` | `candidate_mapping` | `single` | Cat `0` (`shirt, blouse`) | Merged with shirts; filtering required. |
| `garment_type` | `t-shirt` | `candidate_mapping` | `any` | Cat `1` (`top, t-shirt, sweatshirt`), Attr `0` (`classic (t-shirt)`), Attr `4` (`ringer (t-shirt)`) | Merged with generic tops and sweatshirts; filtering required. |
| `garment_type` | `crop-top` | `direct` | `single` | Attr `8` (`crop (top)`) | Direct match with Attribute ID 8 `crop (top)`. |
| `neckline_type` | `round-neck` | `direct` | `single` | Attr `182` (`round (neck)`) | Direct match with Attribute ID 182 `round (neck)`. |
| `neckline_type` | `v-neck` | `direct` | `single` | Attr `183` (`v-neck`) | Exact string match with Attribute ID 183 `v-neck`. |
| `neckline_type` | `square-neck` | `direct` | `single` | Attr `191` (`square (neckline)`) | Direct match with Attribute ID 191 `square (neckline)`. |
| `neckline_type` | `scoop-neck` | `direct` | `single` | Attr `190` (`scoop (neck)`) | Direct match with Attribute ID 190 `scoop (neck)`. |
| `neckline_type` | `boat-neck` | `direct` | `single` | Attr `189` (`boat (neck)`) | Direct match with Attribute ID 189 `boat (neck)`. |
| `neckline_type` | `sweetheart-neck` | `direct` | `single` | Attr `187` (`sweetheart (neckline)`) | Direct match with Attribute ID 187 `sweetheart (neckline)`. |
| `neckline_type` | `halter-neck` | `direct` | `single` | Attr `194` (`halter (neck)`) | Direct match with Attribute ID 194 `halter (neck)`. |
| `neckline_type` | `high-neck` | `direct` | `single` | Attr `197` (`high (neck)`) | Direct match with Attribute ID 197 `high (neck)`. |
| `neckline_type` | `collared-neck` | `candidate_mapping` | `any` | Cat `28` (`collar`), Attr `163` (`shirt (collar)`), Attr `164` (`polo (collar)`) | Candidate mapping derived from collar part or collar attributes. |
| `neckline_type` | `off-shoulder` | `direct` | `single` | Attr `202` (`off-the-shoulder`) | Direct match with Attribute ID 202 `off-the-shoulder`. |
| `sleeve_length` | `sleeveless` | `direct` | `single` | Attr `156` (`sleeveless`) | Exact string match with Attribute ID 156 `sleeveless`. |
| `sleeve_length` | `cap-length` | `candidate_mapping` | `single` | Attr `207` (`cap (sleeve)`) | Candidate mapping because source is a nickname/style attribute rather than length. |
| `sleeve_length` | `short-sleeve` | `direct` | `single` | Attr `157` (`short (length)`) | Direct match with Attribute ID 157 `short (length)`. |
| `sleeve_length` | `elbow-length` | `direct` | `single` | Attr `158` (`elbow-length`) | Exact string match with Attribute ID 158 `elbow-length`. |
| `sleeve_length` | `three-quarter-sleeve` | `direct` | `single` | Attr `159` (`three quarter (length)`) | Direct match with Attribute ID 159 `three quarter (length)`. |
| `sleeve_length` | `long-sleeve` | `direct` | `single` | Attr `160` (`wrist-length`) | Direct match with Attribute ID 160 `wrist-length` (normalized term). |
| `sleeve_style` | `none` | `candidate_mapping` | `derived` | Attr `156` (`sleeveless`) | Derived rule: assign `none` when `sleeve_length` is sleeveless. |
| `sleeve_style` | `regular-sleeve` | `candidate_mapping` | `single` | Attr `204` (`set-in sleeve`) | Candidate mapping; set-in construction is not always equivalent to regular. |
| `sleeve_style` | `puff-sleeve` | `direct` | `single` | Attr `209` (`puff (sleeve)`) | Direct match with Attribute ID 209 `puff (sleeve)`. |
| `sleeve_style` | `bell-sleeve` | `direct` | `single` | Attr `210` (`bell (sleeve)`) | Direct match with Attribute ID 210 `bell (sleeve)`. |
| `sleeve_style` | `bishop-sleeve` | `direct` | `single` | Attr `214` (`bishop (sleeve)`) | Direct match with Attribute ID 214 `bishop (sleeve)`. |
| `sleeve_style` | `flutter-sleeve` | `candidate_mapping` | `single` | Attr `211` (`circular flounce (sleeve)`) | Candidate mapping; circular flounce is related but not identical tailoring term. |
| `sleeve_style` | `raglan-sleeve` | `direct` | `single` | Attr `206` (`raglan (sleeve)`) | Direct match with Attribute ID 206 `raglan (sleeve)`. |
| `sleeve_style` | `dolman-sleeve` | `direct` | `single` | Attr `213` (`dolman (sleeve), batwing (sleeve)`) | Direct match with Attribute ID 213 `dolman (sleeve), batwing (sleeve)`. |
| `sleeve_style` | `cold-shoulder-sleeve` | `unsupported` | `None` | None | No native source label exists in Fashionpedia metadata. |
| `sleeve_style` | `kimono-sleeve` | `direct` | `single` | Attr `216` (`kimono (sleeve)`) | Direct match with Attribute ID 216 `kimono (sleeve)`. |

---

## 4. Final Totals & Classification Summary

* **Direct**: **21** (Inspected Fashionpedia terms explicitly representing target concept)
* **Candidate Mapping**: **7** (Requires rule derivation, category filtering, or tailoring concept transformation)
* **Unsupported**: **1** (`cold-shoulder-sleeve`)
* **Total Project Labels**: **29**

---

## 5. Detailed Candidate Mapping Limitations

Every candidate mapping is constrained by specific semantic limitations:

1. **`blouse`**: Source Category 0 (`shirt, blouse`) merges dressy blouses with casual button-down shirts, dress shirts, and men's shirts. Filtering out non-blouses requires post-processing or manual review.
2. **`t-shirt`**: Source Category 1 (`top, t-shirt, sweatshirt`) merges t-shirts with heavy sweatshirts, fleeces, hoodies, and generic tops. Filtering out non-t-shirts requires checking nickname attributes (e.g. ID 0 `classic (t-shirt)`, ID 4 `ringer (t-shirt)`).
3. **`collared-neck`**: Must be derived from collar-part presence (Category 28 `collar`) or specific collar attributes (IDs 163, 164).
4. **`cap-length`**: Source label ID 207 (`cap (sleeve)`) is a nickname/style attribute rather than a length label.
5. **`none` (sleeve style)**: Derived from `sleeveless` length evidence (Attribute ID 156) in accordance with project dependency rules.
6. **`regular-sleeve`**: Source label ID 204 (`set-in sleeve`) describes shoulder armhole construction, which is not always equivalent to regular sleeve style.
7. **`flutter-sleeve`**: Source label ID 211 (`circular flounce (sleeve)`) describes circular flounce construction, which is related to but not identical to flutter sleeve styling.

---

## 6. Compliance, Quality Control & Licensing Notice

> **Important Quality Control Notice**:  
> Direct taxonomy compatibility does not guarantee that every image annotation is correct; image-level QC remains required.

> **Licensing Notice**:  
> Mapping Fashionpedia taxonomy labels to our 29 target classes is a metadata ontology alignment step and does **NOT** imply licensing approval or copyright ownership of the underlying image assets. Each candidate image remains subject to its original source terms.

---

## 7. Recommended Next Action

* **Recommended Next Action**: Develop an automated candidate annotation parser script (`ai_training/scripts/parse_fashionpedia_annotations.py`) to extract candidate instances according to `fashionpedia_mapping.json` rules, followed by a manual review pass. *(Do not run image downloads or dataset parsing yet.)*
