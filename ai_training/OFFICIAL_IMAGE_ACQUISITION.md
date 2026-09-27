# Official Fashionpedia Image Acquisition and Geometry Verification (Milestone M7)

## 1. Overview & Rejection of `original_url` Images

Earlier image download experiments utilizing the `original_url` field (Flickr source links) in Fashionpedia metadata resulted in geometry and bounding-box mismatches. Flickr images have undergone arbitrary user re-uploads, server-side resizing, or deletion.

To ensure **100% exact bounding-box geometry alignment** across all 45,623 training images and 1,158 validation images, Milestone M7 acquires and verifies ONLY the official Computer Vision for Fashion (CVDF) Fashionpedia image archives.

---

## 2. Official Archive Specification & Verification

| Dataset Split Archive | Official Source URL | File Size (Bytes) | File Size (GB) | ETag | SHA-256 Checksum |
|---|---|---|---|---|---|
| **`train2020.zip`** | `https://s3.amazonaws.com/ifashionist-dataset/images/train2020.zip` | `3,344,364,592` | ~3.34 GB | `"cb16738d9ac445cb5e3fc6035dcd6951-399"` | `d896792104a4c35efa7859a18cf605fddae779f5c2372e87e08d7b45949244e2` |
| **`val_test2020.zip`** | `https://s3.amazonaws.com/ifashionist-dataset/images/val_test2020.zip` | `236,499,034` | ~0.24 GB | `"391ebfbf1c8eba0b4b80803cb70612d1-29"` | `44eb1685364b6ed6bda4595fe0dc07a252e9b923112b97b24ff4d440751a2acc` |

- **Local Archive Directory**: `ai_training/data/raw/fashionpedia/archives/`
- **Download Manifest**: `ai_training/data/raw/fashionpedia/download_manifest.json`

---

## 3. Safe Extraction & Archive Audit

Both archives were tested with Python `zipfile.ZipFile.testzip()`, checked for path safety (zero `..` traversal or absolute path violations), and extracted via streamed I/O into `ai_training/data/raw/fashionpedia/images/`.

- **`train2020.zip`**: Extracted 45,623 image files. `testzip()` passed with zero corrupted entries.
- **`val_test2020.zip`**: Extracted 3,200 image files (covering `val2020` and `test2020`). `testzip()` passed with zero corrupted entries.
- **Total Extracted Images on Disk**: `48,823` image files.

---

## 4. Full Geometry & Dimension Verification Results

Every image record in `instances_attributes_train2020.json` and `instances_attributes_val2020.json` was fully decoded with PIL (EXIF transpose disabled) and compared against official annotation `width` and `height`.

### Verification Summary Table:

| Metric | Training Split (`train2020`) | Validation Split (`val2020`) |
|---|---|---|
| **Annotation Records** | `45,623` | `1,158` |
| **Exact Dimension Matches** | **`45,623` (100.00%)** | **`1,158` (100.00%)** |
| **Missing Files** | `0` | `0` |
| **Corrupt / Undecodable Files** | `0` | `0` |
| **Width Mismatches** | `0` | `0` |
| **Height Mismatches** | `0` | `0` |
| **Aspect Ratio Mismatches** | `0` | `0` |
| **Duplicate Image IDs** | `0` | `0` |
| **Duplicate File Names** | `0` | `0` |
| **Audit Report Path** | `ai_training/data/analysis/official_image_audit/train_report.json` | `ai_training/data/analysis/official_image_audit/val_report.json` |

---

## 5. Licensing & Source Attribution

- **Dataset**: Fashionpedia (CVDF / AWS Open Data).
- **Licensing**: Images are provided for non-commercial educational and academic research purposes under original Flickr Creative Commons licenses.

---

## 6. Reproducible Execution Commands

```bash
# 1. Download official archives with HTTP Range resume
python ai_training/scripts/download_fashionpedia_images.py --output-dir ai_training/data/raw/fashionpedia/archives --include-train --include-val-test --resume

# 2. Safely validate and extract archives
python ai_training/scripts/extract_fashionpedia_images.py --archive ai_training/data/raw/fashionpedia/archives/val_test2020.zip --output-dir ai_training/data/raw/fashionpedia/images
python ai_training/scripts/extract_fashionpedia_images.py --archive ai_training/data/raw/fashionpedia/archives/train2020.zip --output-dir ai_training/data/raw/fashionpedia/images

# 3. Verify exact geometry and dimensions
python ai_training/scripts/verify_fashionpedia_images.py --annotations ai_training/data/raw/fashionpedia/instances_attributes_train2020.json --images-root ai_training/data/raw/fashionpedia/images --split train --output-report ai_training/data/analysis/official_image_audit/train_report.json
python ai_training/scripts/verify_fashionpedia_images.py --annotations ai_training/data/raw/fashionpedia/instances_attributes_val2020.json --images-root ai_training/data/raw/fashionpedia/images --split val --output-report ai_training/data/analysis/official_image_audit/val_report.json

# 4. Run test suite
python -m unittest discover -s ai_training/tests -p "test_*.py" -v
```

---

## 7. Git Ignore Status

All image binaries (`.zip`, extracted `.jpg`), downloads, manifests, and audit reports reside under `ai_training/data/` and remain 100% ignored by Git (`!! ai_training/data/`).
