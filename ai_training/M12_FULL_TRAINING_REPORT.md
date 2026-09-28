# Milestone M12 Full Staged Training and Final Evaluation Report

## Executive Summary

Milestone M12 executes full-dataset two-stage training for the unified **YOLOv8 Multi-Task Garment Classifier** (`YOLOv8MultiTaskClassifier`) on the 28-class taxonomy established in M9C-B. Model selection was strictly governed by validation set performance (mean supported macro-F1 score across all active classification heads), and final performance was measured on a locked, one-time test set split.

---

## Preflight and Environment Record

| Key Parameter | Measured Value |
|---|---|
| **Python Version** | `3.14.6` |
| **PyTorch Version** | `2.14.0+cpu` |
| **Ultralytics Version** | `8.4.146` |
| **Platform / CPU** | `Windows (Intel64 Family 6 Model 170, 22 vCPUs)` |
| **System RAM** | `15.37 GB` |
| **Free Disk Space** | `625.21 GB` |
| **Pretrained Weights Path** | `ai_training/data/training_runs/pretrained/yolov8n-cls.pt` |
| **Random Seed** | `42` |
| **Cross-Split Image Leakage** | `0 overlapping images across Train / Val / Test` |

---

## Training Run Details & Staged Protocol

- **Total Dataset**: 11,277 Train records, 2,219 Validation records, 2,298 Test records.
- **Total Training Duration**: 15,811.77 seconds (~4.39 hours on 22 CPU threads).
- **Optimization Strategy**:
  - **Stage A (Head Warm-up)**: 3 epochs with frozen backbone layers (`0..8` + `Classify.conv`), training only the 4 task heads at Learning Rate = `0.001`.
  - **Stage B (Partial Fine-Tuning)**: 8 epochs (Total Epochs `4..11`) unfreezing layer 8 and the `Classify.conv` projection layer (826,396 trainable parameters, 647,760 frozen parameters). Learning Rate = `0.0001` (backbone), `0.0005` (heads).
- **Selection Criteria**: Selected epoch with highest validation supported mean macro-F1 score.
  - **Best Checkpoint**: Total Epoch 7 (Stage B Epoch 4) with **Validation Supported Mean Macro-F1 = `0.5489`**.
- **Early Stopping**: Triggered after Total Epoch 11 (4 consecutive epochs without validation score improvement past Epoch 7).

---

## Validation Metrics (Best Checkpoint @ Total Epoch 7)

- **Overall Selection Score (Supported Mean Macro-F1)**: **`0.5489`**

### Detailed Head Performance on Validation Set

1. **`garment_type` Head** (121 evaluated records):
   - **Accuracy**: `81.82%` | **Macro-F1**: `0.8201` | **Macro-Precision**: `0.8288` | **Macro-Recall**: `0.8189`
   - `blouse`: Support = 41 | F1 = `0.8800` (Prec = `0.9706`, Rec = `0.8049`)
   - `t-shirt`: Support = 37 | F1 = `0.7848` (Prec = `0.7381`, Rec = `0.8378`)
   - `crop-top`: Support = 43 | F1 = `0.7955` (Prec = `0.7778`, Rec = `0.8140`)

2. **`neckline_type` Head** (1,132 evaluated records):
   - **Accuracy**: `49.82%` | **Macro-F1**: `0.4352` | **Macro-Precision**: `0.4733` | **Macro-Recall**: `0.4282`
   - Top Classes: `round-neck` (F1 = `0.6250`), `v-neck` (F1 = `0.5322`), `sweetheart-neck` (F1 = `0.5347`), `off-shoulder` (F1 = `0.4167`), `scoop-neck` (F1 = `0.4238`), `halter-neck` (F1 = `0.3871`).

3. **`sleeve_length` Head** (1,681 evaluated records):
   - **Accuracy**: `72.40%` | **Macro-F1**: `0.4763` | **Macro-Precision**: `0.4844` | **Macro-Recall**: `0.4868`
   - Top Classes: `long-sleeve` (F1 = `0.8562`), `short-sleeve` (F1 = `0.8103`), `three-quarter-sleeve` (F1 = `0.4010`), `elbow-length` (F1 = `0.3142`).

4. **`sleeve_style` Head** (156 evaluated records):
   - **Accuracy**: `45.51%` | **Macro-F1**: `0.4641` | **Macro-Precision**: `0.5515` | **Macro-Recall**: `0.4635`
   - Top Classes: `raglan-sleeve` (F1 = `0.6392`), `dolman-sleeve` (F1 = `0.5424`), `bishop-sleeve` (F1 = `0.5143`), `puff-sleeve` (F1 = `0.4000`), `kimono-sleeve` (F1 = `0.3810`).

---

## One-Time Locked Test Set Evaluation (2,298 Test Records)

Model selection was performed **100% independently of test set results**. Evaluation on the test split yielded:

- **Overall Supported-Head Mean Macro-F1**: **`0.4889`**

### Head Summary on Test Split

| Classification Head | Evaluated Count | Test Accuracy | Macro-Precision | Macro-Recall | Macro-F1 |
|---|---|---|---|---|---|
| **`garment_type`** | 129 | **`77.52%`** | `0.7845` | `0.7757` | **`0.7785`** |
| **`neckline_type`** | 1,239 | **`50.28%`** | `0.4328` | `0.4031` | **`0.3965`** |
| **`sleeve_length`** | 1,704 | **`73.53%`** | `0.4932` | `0.4996` | **`0.4871`** |
| **`sleeve_style`** | 188 | **`32.45%`** | `0.3473` | `0.2684` | **`0.2937`** |

---

## Three-Garment Crop Inference Verification

Direct single-image crop forward passes were executed on representative sample garments from the dataset using `best.pt`:

1. **`BLOUSE`** (`fashionpedia:train2020:110447`):
   - Input Tensor Shape: `torch.Size([1, 3, 224, 224])`
   - Output Logits Shapes: `garment_type` `[1, 3]`, `neckline_type` `[1, 10]`, `sleeve_length` `[1, 6]`, `sleeve_style` `[1, 9]`
   - Output Predictions: `garment_type` = `crop-top` (conf `0.8116`), `neckline_type` = `high-neck` (conf `0.2927`), `sleeve_length` = `cap-length` (conf `0.7436`), `sleeve_style` = `regular-sleeve` (conf `0.5309`).

2. **`T-SHIRT`** (`fashionpedia:train2020:115733`):
   - Input Tensor Shape: `torch.Size([1, 3, 224, 224])`
   - Output Predictions: `garment_type` = `t-shirt` (conf `0.9997`), `neckline_type` = `round-neck` (conf `0.8575`), `sleeve_length` = `short-sleeve` (conf `0.9279`), `sleeve_style` = `raglan-sleeve` (conf `0.6247`).

3. **`CROP-TOP`** (`fashionpedia:train2020:115187`):
   - Input Tensor Shape: `torch.Size([1, 3, 224, 224])`
   - Output Predictions: `garment_type` = `crop-top` (conf `0.9952`), `neckline_type` = `sweetheart-neck` (conf `0.7274`), `sleeve_length` = `cap-length` (conf `0.6191`), `sleeve_style` = `raglan-sleeve` (conf `0.3814`).

---

## Artifact Verification and Safety Audit

1. **Model Checkpoint Integrity**:
   - `ai_training/data/training_runs/m12_full/checkpoints/best.pt` (Size: 12.02 MB)
   - `ai_training/data/training_runs/m12_full/checkpoints/stage_a_best.pt` (Size: 12.02 MB)
   - `ai_training/data/training_runs/m12_full/checkpoints/last.pt` (Size: 12.02 MB)
2. **Git Status & Isolation**:
   - `ai_training/data/` is 100% ignored (`!! ai_training/data/`).
   - No `.pt` files, checkpoints, logs, or JSONL manifests are tracked by Git.
   - Clean `git diff --check` with zero whitespace errors.
3. **Backend/Frontend Boundaries**:
   - Backend and frontend code remain untouched.
   - The model checkpoint has not been copied to backend directory.
