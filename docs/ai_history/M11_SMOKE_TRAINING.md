# Milestone M11 — Single YOLOv8 Multi-Task Model & CPU Smoke Training Report

## Executive Overview

Milestone M11 constructs a single multi-task neural network model for **Digital Tailor AI**. Built upon the pretrained Ultralytics `yolov8n-cls` feature extractor backbone and projection layer, the network produces a 1,280-dimensional shared feature embedding feeding four task-specific classification heads:
1. `garment_type`: 3 logits
2. `neckline_type`: 10 logits
3. `sleeve_length`: 6 logits
4. `sleeve_style`: 9 logits

The model was validated via a CPU smoke training run (1 epoch, 256 coverage-aware train records covering all 28 target classes, 128 validation records). All pretrained weights, checkpoints (`last.pt`, `best.pt`), logs, and evaluation metrics were stored exclusively under the Git-ignored directory `ai_training/data/training_runs/`.

---

## 1. Network Architecture & Parameter Counts

- **Model Class**: `YOLOv8MultiTaskClassifier` ([multitask_yolov8.py](file:///c:/Research/Developing/digital-tailor-system/ai_training/models/multitask_yolov8.py))
- **Pretrained Backbone**: Ultralytics YOLOv8 Nano Classification (`yolov8n-cls.pt`)
- **Shared Projection**: Layers 0–8 backbone + Layer 9 (`Classify.conv`, `Classify.pool`, `Classify.drop`)
- **Shared Embedding Dimension**: 1,280 channels

| Network Component | Output Shape | Parameters | Status in CPU Smoke Run |
| :--- | :--- | :--- | :--- |
| **Shared Backbone & Projection** | `[B, 1280]` | 1,438,288 | **Frozen** (`requires_grad = False`) |
| **Head 1: garment_type** | `[B, 3]` | 3,843 | Trainable (`requires_grad = True`) |
| **Head 2: neckline_type** | `[B, 10]` | 12,810 | Trainable (`requires_grad = True`) |
| **Head 3: sleeve_length** | `[B, 6]` | 7,686 | Trainable (`requires_grad = True`) |
| **Head 4: sleeve_style** | `[B, 9]` | 11,529 | Trainable (`requires_grad = True`) |
| **Total Model Parameters** | | **1,474,156** | **35,868 Trainable / 1,438,288 Frozen** |

---

## 2. Gradient & Freeze Verification Results

During the 1-epoch smoke run:
- **Head Gradient Check**: `PASSED` (Classification heads successfully received non-null gradients during backward pass).
- **Backbone Freeze Check**: `PASSED` (Shared backbone and projection weights remained 100% identical after optimizer step).

---

## 3. CPU Smoke Training Execution & Record Counts

- **Device**: CPU (`PyTorch 2.14.0+cpu`)
- **Execution Time**: **7.72 seconds**
- **Train Records**: **256** records (Coverage-aware stratified sampling, covering all **28/28** target classes)
- **Validation Records**: **128** records (Gold validation evaluation)
- **Batch Size**: 8 (`num_workers = 0` for Windows safe execution)

### Loss Values (1 Epoch Smoke Run)

- **Overall Train Loss**: `1.2365`
- **Overall Validation Loss**: `1.1636`
- **Per-Head Losses**:
  - `garment_type`: Train Loss `0.7393`
  - `neckline_type`: Train Loss `1.6638`
  - `sleeve_length`: Train Loss `0.9418`
  - `sleeve_style`: Train Loss `1.0720`

---

## 4. Per-Head Smoke Validation Metrics

> [!NOTE]
> Smoke metrics from a 1-epoch CPU run on 256 records are for workflow validation ONLY, not final model accuracy. Validation gold evaluation classes without test ground truth support are explicitly marked N/A.

| Head | Evaluated Active Val Records | Val Accuracy | Macro Precision | Macro Recall | Macro F1 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `garment_type` | 120 | 0.4000 | 0.3541 | 0.3340 | 0.3175 |
| `neckline_type` | 116 | 0.1379 | 0.0833 | 0.0601 | 0.0675 |
| `sleeve_length` | 112 | 0.5446 | 0.3204 | 0.4022 | 0.3543 |
| `sleeve_style` | 12 | 0.0833 | 0.0833 | 0.0556 | 0.0667 |

---

## 5. Checkpoint Metadata & Storage Locations

All checkpoints and pretrained weights were verified under `ai_training/data/training_runs/`:

- **Pretrained Weights**: `ai_training/data/training_runs/pretrained/yolov8n-cls.pt` (5.30 MB, Git-ignored)
- **Last Checkpoint**: `ai_training/data/training_runs/run_smoke/checkpoints/last.pt` (5.98 MB, Git-ignored)
- **Best Checkpoint**: `ai_training/data/training_runs/run_smoke/checkpoints/best.pt` (5.98 MB, Git-ignored)

Every checkpoint contains mandatory keys:
- `epoch`: `1`
- `model_state_dict`: Complete PyTorch model state
- `optimizer_state_dict`: Complete AdamW optimizer state
- `config`: Training configuration parameters
- `class_to_idx`: 28-class taxonomy mapping
- `idx_to_class`: Index to class name mapping
- `head_dimensions`: `{"garment_type": 3, "neckline_type": 10, "sleeve_length": 6, "sleeve_style": 9}`
- `val_metrics`: Per-head evaluation metrics
- `pretrained_backbone_identifier`: `"yolov8n-cls"`
- `random_seed`: `42`

---

## 6. Real-Image Garment Crop Inference Verification

Reloaded checkpoint `best.pt` and executed single-image crop inference on validation record `fashionpedia:train2020:100255`:

- **Input Tensor Shape**: `torch.Size([1, 3, 224, 224])`
- **Output Predictions Across All 4 Heads**:
  - `garment_type`: Tensor shape `[1, 3]` -> Predicted Class: **`t-shirt`** (Index=1, Confidence=0.4651)
  - `neckline_type`: Tensor shape `[1, 10]` -> Predicted Class: **`scoop-neck`** (Index=3, Confidence=0.2771)
  - `sleeve_length`: Tensor shape `[1, 6]` -> Predicted Class: **`short-sleeve`** (Index=2, Confidence=0.4912)
  - `sleeve_style`: Tensor shape `[1, 9]` -> Predicted Class: **`regular-sleeve`** (Index=1, Confidence=0.3406)

---

## 7. Verification Suite Summary

1. `py_compile`: PASSED on all 7 python files.
2. Unit Test Suite: PASSED (`Ran 92 tests in 1.45s, OK`).
3. `git diff --check`: PASSED (0 whitespace/formatting errors).
4. Data Directory Isolation: `ai_training/data/` remains 100% Git-ignored.
