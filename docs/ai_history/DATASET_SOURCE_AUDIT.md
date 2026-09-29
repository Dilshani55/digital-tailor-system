# Digital Tailor System — Official Dataset-Source Audit

> **Milestone AI-2 Audit Document**
> *Note: This document provides an official audit of external fashion dataset candidates for the Digital Tailor System YOLOv8 multi-task model. No dataset has been downloaded, ingested, or approved yet.*
> **Taxonomy Update Note**: This historical audit evaluated a 29-class taxonomy. The active dataset taxonomy has since been updated to 28 classes by removing the unsupported `sleeve_style:cold-shoulder-sleeve` class, while preserving `neckline_type:off-shoulder`.

---

## 1. Executive Summary & Evidence Rules

> **Core Evidence Rule**:  
> Dataset descriptions indicate potential coverage only. A target label is not considered supported until its exact annotation name and examples have been inspected.

### Key Audit Findings
1. **Fashionpedia** is the recommended **primary candidate** for this research project because its published architecture features 27 main apparel categories, 19 apparel parts, and 294 fine-grained attributes.
2. **Fashionpedia annotations and ontology** are licensed under Creative Commons Attribution 4.0 International (**CC BY 4.0**). Fashionpedia does not own the image copyrights; each image remains subject to its original source terms.
3. **DeepFashion Attribute Prediction** benchmark contains 289,222 images, 50 categories, and 1,000 attributes. Access and applicable usage terms must be verified before downloading or using the dataset.
4. **DeepFashion2** contains 491,000 images across 13 coarse categories with bounding boxes, masks, landmarks, and style pairs. It defines 294 landmark types in total across its 13 clothing categories; the applicable landmarks vary by category.
5. **DeepFashion2 does not directly provide the full detailed neckline and sleeve-style taxonomy** required by this project.
6. **No reviewed source has yet been proven to map one-to-one to all 29 project labels.**
7. **Manual taxonomy mapping and manual quality review will be strictly required.**
8. **No dataset has been downloaded, ingested, or approved yet in this workspace.**

---

## 2. Detailed Dataset Audit Profiles

### 2.1. Fashionpedia

* **Dataset Name**: Fashionpedia
* **Official Source**: 
  * Project Homepage: [https://fashionpedia.github.io/home/Fashionpedia_download.html](https://fashionpedia.github.io/home/Fashionpedia_download.html)
  * Code Repository: [https://github.com/cvdfoundation/fashionpedia](https://github.com/cvdfoundation/fashionpedia)
  * License Page: [https://fashionpedia.github.io/home/data_license.html](https://fashionpedia.github.io/home/data_license.html)
  * ECCV 2020 Paper: [https://www.ecva.net/papers/eccv_2020/papers_ECCV/papers/123460307.pdf](https://www.ecva.net/papers/eccv_2020/papers_ECCV/papers/123460307.pdf)
* **Image Count**: Approximately 48,000 images, as described by the official Fashionpedia project/paper. Exact usable train/validation counts must be confirmed after downloading and inspecting the annotation packages.
* **Category Count**: 27 main apparel categories
* **Attribute Count**: 19 apparel parts and 294 fine-grained attributes
* **Annotation Types**: Instance segmentation masks, bounding boxes, 27 main categories, 19 apparel parts, 294 attributes
* **Download/Access Method**: Official CVDF / AWS S3 storage and Kaggle dataset access (where verified).
* **Known License or Usage Restrictions**: Fashionpedia annotations and ontology are CC BY 4.0. Fashionpedia does not own the image copyrights; each image remains subject to its original source terms.
* **Suitability for Garment Type**: Promising candidate; exact compatibility remains unverified until the ontology and annotation JSON files are inspected.
* **Suitability for Neckline Type**: Promising candidate; exact compatibility remains unverified until the ontology and annotation JSON files are inspected.
* **Suitability for Sleeve Length**: Promising candidate; exact compatibility remains unverified until the ontology and annotation JSON files are inspected.
* **Suitability for Sleeve Style**: Promising candidate; exact compatibility remains unverified until the ontology and annotation JSON files are inspected.
* **Data-Leakage Grouping Information**: URL/image metadata may help construct a `source_id`, but grouping rules must be derived and manually validated before splitting.
* **Limitations**: Requires downloading and inspecting COCO-style annotation files to verify whether published attribute IDs align with our 29 multi-task labels.
* **Recommended Role**: **Primary Candidate** for initial dataset inspection and taxonomy mapping.

---

### 2.2. DeepFashion (Category & Attribute Prediction Benchmark)

* **Dataset Name**: DeepFashion (Attribute Prediction Benchmark)
* **Official Source**: [https://mmlab.ie.cuhk.edu.hk/projects/DeepFashion/AttributePrediction.html](https://mmlab.ie.cuhk.edu.hk/projects/DeepFashion/AttributePrediction.html)
* **Image Count**: 289,222 images
* **Category Count**: 50 categories
* **Attribute Count**: 1,000 attributes
* **Annotation Types**: Category labels, 1,000 sparse attribute tags (neckline, sleeve, fabric, style), bounding boxes, landmark points
* **Download/Access Method**: Official web links via CUHK MMLab page. Access and applicable usage terms must be verified before downloading or using the dataset.
* **Known License or Usage Restrictions**: Access and applicable usage terms must be verified before downloading or using the dataset.
* **Suitability for Garment Type**: Unverified pending annotation inspection.
* **Suitability for Neckline Type**: Unverified pending annotation inspection.
* **Suitability for Sleeve Length**: Unverified pending annotation inspection.
* **Suitability for Sleeve Style**: Unverified pending annotation inspection.
* **Data-Leakage Grouping Information**: Availability and meaning of item-level grouping metadata remain Unverified. Before splitting, inspect the downloaded annotations and construct a validated `source_id` using confirmed item identifiers or image-similarity checks.
* **Limitations**: Attribute annotations are sparse and noisy; exact label alignment is Unverified pending annotation inspection.
* **Recommended Role**: **Secondary Gap-Filling Candidate** (strictly subject to usage-term verification and annotation inspection).

---

### 2.3. DeepFashion2

* **Dataset Name**: DeepFashion2
* **Official Source**: [https://github.com/switchablenorms/deepfashion2](https://github.com/switchablenorms/deepfashion2)
* **Image Count**: 491,000 images (801K clothing items)
* **Category Count**: 13 coarse clothing categories
* **Attribute Count**: 13 coarse categories, 294 landmark types defined in total across categories, style pair IDs
* **Annotation Types**: Bounding boxes, instance masks, 13 coarse categories, landmark points (the dataset defines 294 landmark types in total across its 13 clothing categories; the applicable landmarks vary by category), style pair IDs
* **Download/Access Method**: Form-based request / password access as described in the official repository. Applicable licence and redistribution conditions remain Unverified and must be checked before use.
* **Known License or Usage Restrictions**: Applicable licence and redistribution conditions remain Unverified and must be checked before use.
* **Suitability for Garment Type**: Coarse category evidence only (provides `short sleeve top`, `long sleeve top`, `vest`, etc.).
* **Suitability for Neckline Type**: **Unsupported** (Does not provide fine-grained neckline classification taxonomy).
* **Suitability for Sleeve Length**: Direct evidence for `short sleeve top` and `long sleeve top` coarse categories; Candidate mapping for `sleeveless` via vest/sling categories.
* **Suitability for Sleeve Style**: **Unsupported** (Does not provide detailed sleeve style taxonomy such as bishop, bell, puff, kimono, flutter).
* **Data-Leakage Grouping Information**: `pair_id` may help group linked commercial-consumer images of the same clothing item. Its exact semantics and completeness must be verified before using it as `source_id`. Do not assume that `pair_id` or style fields represent photoshoot groupings.
* **Limitations**: Lacks detailed 29-label neckline and sleeve style taxonomy.
* **Recommended Role**: **Structural / Cropping Support Only** (for upper garment localization and bounding-box cropping).

---

## 3. 29-Label Coverage Matrix

The following matrix evaluates label availability across audited candidates using strictly permitted status values:
* **Direct**: Official inspected label/category explicitly matches.
* **Candidate mapping**: A proposed derivation that still requires validation (e.g., deriving a `none` sleeve style from `sleeveless`).
* **Unverified**: Exact annotation names have not yet been inspected.
* **Unsupported**: Official dataset scope does not provide that target.

| Classification Head | Target Label | Fashionpedia | DeepFashion Attribute | DeepFashion2 |
| :--- | :--- | :---: | :---: | :---: |
| **garment_type** | `blouse` | Unverified | Unverified | Unverified |
| **garment_type** | `t-shirt` | Unverified | Unverified | Candidate mapping |
| **garment_type** | `crop-top` | Unverified | Unverified | Unverified |
| **neckline_type** | `round-neck` | Unverified | Unverified | Unsupported |
| **neckline_type** | `v-neck` | Unverified | Unverified | Unsupported |
| **neckline_type** | `square-neck` | Unverified | Unverified | Unsupported |
| **neckline_type** | `scoop-neck` | Unverified | Unverified | Unsupported |
| **neckline_type** | `boat-neck` | Unverified | Unverified | Unsupported |
| **neckline_type** | `sweetheart-neck` | Unverified | Unverified | Unsupported |
| **neckline_type** | `halter-neck` | Unverified | Unverified | Unsupported |
| **neckline_type** | `high-neck` | Unverified | Unverified | Unsupported |
| **neckline_type** | `collared-neck` | Unverified | Unverified | Unsupported |
| **neckline_type** | `off-shoulder` | Unverified | Unverified | Unsupported |
| **sleeve_length** | `sleeveless` | Unverified | Unverified | Candidate mapping |
| **sleeve_length** | `cap-length` | Unverified | Unverified | Unsupported |
| **sleeve_length** | `short-sleeve` | Unverified | Unverified | Direct |
| **sleeve_length** | `elbow-length` | Unverified | Unverified | Unsupported |
| **sleeve_length** | `three-quarter-sleeve` | Unverified | Unverified | Unsupported |
| **sleeve_length** | `long-sleeve` | Unverified | Unverified | Direct |
| **sleeve_style** | `none` | Candidate mapping | Candidate mapping | Candidate mapping |
| **sleeve_style** | `regular-sleeve` | Unverified | Unverified | Unsupported |
| **sleeve_style** | `puff-sleeve` | Unverified | Unverified | Unsupported |
| **sleeve_style** | `bell-sleeve` | Unverified | Unverified | Unsupported |
| **sleeve_style** | `bishop-sleeve` | Unverified | Unverified | Unsupported |
| **sleeve_style** | `flutter-sleeve` | Unverified | Unverified | Unsupported |
| **sleeve_style** | `raglan-sleeve` | Unverified | Unverified | Unsupported |
| **sleeve_style** | `dolman-sleeve` | Unverified | Unverified | Unsupported |
| **sleeve_style** | `cold-shoulder-sleeve` | Unverified | Unverified | Unsupported |
| **sleeve_style** | `kimono-sleeve` | Unverified | Unverified | Unsupported |

---

## 4. Final Recommendation & Next Steps

* **Primary Candidate**: **Fashionpedia**
* **Secondary Gap-Filling Candidate**: **DeepFashion Attribute Prediction**, subject to usage-term verification
* **Structural / Cropping Support Only**: **DeepFashion2**
* **Required Next Action**: Inspect official Fashionpedia annotation names and JSON ontology structure before downloading full image archives.
