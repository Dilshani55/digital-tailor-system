#!/usr/bin/env python3
"""
multitask_classifier.py

Backend Multi-Task Inference Service for Digital Tailor AI (Milestone M13).
- Model type: IMAGE-LEVEL multi-task CLASSIFIER — a YOLOv8n-cls-derived backbone
  with four linear prediction heads (garment_type, neckline_type, sleeve_length,
  sleeve_style). It is NOT an object detector and produces no bounding boxes.
- Reconstructs YOLOv8MultiTaskClassifier offline without internet calls.
- Provides thread-safe singleton model loading using threading.Lock.
- Executes deterministic validation preprocessing (crop bbox or fallback to full image).
- Computes top-1, top-3, confidence scores, and low-confidence confirmation flags.
"""

import os
import sys
import time
import hashlib
import threading
import torch
import torch.nn as nn
from PIL import Image
from ultralytics import YOLO

# Add parent directory to path if needed for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

HEADS = ["garment_type", "neckline_type", "sleeve_length", "sleeve_style"]

DEFAULT_HEAD_DIMS = {
    "garment_type": 3,
    "neckline_type": 10,
    "sleeve_length": 6,
    "sleeve_style": 9,
}

DEFAULT_CONFIDENCE_THRESHOLDS = {
    "garment_type": 0.70,
    "neckline_type": 0.45,
    "sleeve_length": 0.50,
    "sleeve_style": 0.40,
}

DEPLOYED_MODEL_PATH = os.path.join(
    os.path.dirname(__file__), "models", "garment_multitask_yolov8_best.pt"
)

M14D_CANDIDATE_MODEL_PATH = os.path.abspath(os.path.join(
    os.path.dirname(__file__),
    "..", "..", "..",
    "ai_training", "data", "training_runs", "m14d_fresh", "exp_b_focal", "best.pt",
))

# Prefer the explicitly deployed checkpoint (currently byte-identical to the M12
# staged-training best.pt). NOTE: the M14D file has no "model_state_dict", so this
# loader cannot load it; if the deployed copy is missing, loading fails with a
# clear MultiTaskModelError rather than silently using another model.
DEFAULT_MODEL_PATH = (
    DEPLOYED_MODEL_PATH
    if os.path.exists(DEPLOYED_MODEL_PATH)
    else M14D_CANDIDATE_MODEL_PATH
)

DEFAULT_BACKBONE_PATH = os.path.join(
    os.path.dirname(__file__), "models", "yolov8n-cls.pt"
)


MODEL_TYPE = (
    "image-level multi-task classifier "
    "(YOLOv8n-cls-derived backbone, 4 classification heads; not an object detector)"
)


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def build_model_version(ckpt: dict, sha256: str) -> str:
    """
    Version string derived ONLY from what the loaded checkpoint really contains
    (training epoch/stage recorded in the file + content hash). Nothing is
    hard-coded, so two different checkpoints can never share a label.
    """
    parts = ["YOLOv8MultiTaskClassifier"]
    if ckpt.get("stage") is not None:
        parts.append(f"stage={ckpt['stage']}")
    if ckpt.get("epoch") is not None:
        parts.append(f"epoch={ckpt['epoch']}")
    parts.append(f"sha256={sha256[:12]}")
    return "|".join(parts)


class MultiTaskModelError(Exception):
    """Custom exception raised when multi-task model loading or inference fails."""
    pass


class YOLOv8MultiTaskClassifier(nn.Module):
    """
    Single YOLOv8 Multi-Task Classification Model for Backend Inference.
    Reconstructs shared YOLOv8 feature backbone and 4 task-specific classification heads.
    """
    def __init__(self, pretrained_path: str, head_dims: dict):
        super().__init__()
        self.pretrained_path = pretrained_path
        self.head_dims = head_dims

        if not os.path.exists(pretrained_path):
            raise MultiTaskModelError(
                f"Base pretrained backbone not found at {pretrained_path}"
            )

        # Load base architecture offline from local pretrained checkpoint
        yolo_wrapper = YOLO(pretrained_path)
        base_model = yolo_wrapper.model

        self.backbone = base_model.model[0:9]
        self.projection_conv = base_model.model[9].conv
        self.global_pool = base_model.model[9].pool
        self.dropout = base_model.model[9].drop
        self.embedding_dim = 1280

        self.heads = nn.ModuleDict({
            head_name: nn.Linear(self.embedding_dim, num_classes)
            for head_name, num_classes in head_dims.items()
        })

    def extract_features(self, x: torch.Tensor) -> torch.Tensor:
        feats = self.backbone(x)
        feats = self.projection_conv(feats)
        feats = self.global_pool(feats)
        feats = torch.flatten(feats, 1)
        feats = self.dropout(feats)
        return feats

    def forward(self, x: torch.Tensor) -> dict:
        feats = self.extract_features(x)
        return {
            head_name: head_module(feats)
            for head_name, head_module in self.heads.items()
        }


# Thread-safe Singleton Container
_model_instance = None
_model_metadata = None
_model_cache_key = None
_model_lock = threading.Lock()


def get_multitask_classifier(model_path: str = None, backbone_path: str = None):
    """
    Returns cached model singleton and metadata. Loads model once thread-safely.
    """
    global _model_instance, _model_metadata, _model_cache_key

    target_model_path = os.path.abspath(model_path or DEFAULT_MODEL_PATH)
    target_backbone_path = os.path.abspath(backbone_path or DEFAULT_BACKBONE_PATH)
    cache_key = (target_model_path, target_backbone_path)

    if not os.path.exists(target_model_path):
        raise MultiTaskModelError(
            f"Multi-task model checkpoint not found at {target_model_path}"
        )

    with _model_lock:
        if _model_instance is None or _model_cache_key != cache_key:
            t0 = time.perf_counter()
            try:
                ckpt = torch.load(target_model_path, map_location="cpu", weights_only=False)
            except Exception as e:
                raise MultiTaskModelError(
                    f"Failed to load checkpoint file at {target_model_path}: {e}"
                )

            required_keys = ["model_state_dict", "class_to_idx", "idx_to_class"]
            for k in required_keys:
                if k not in ckpt:
                    raise MultiTaskModelError(
                        f"Checkpoint at {target_model_path} missing required key '{k}'"
                    )

            config = ckpt.get("config") or {}
            head_dims = (
                ckpt.get("head_dimensions")
                or config.get("head_dims")
                or DEFAULT_HEAD_DIMS
            )

            if set(head_dims) != set(HEADS):
                raise MultiTaskModelError(
                    f"Checkpoint at {target_model_path} has invalid head dimensions: {head_dims}"
                )
            for head in HEADS:
                expected = int(head_dims[head])
                if len(ckpt["class_to_idx"].get(head, {})) != expected:
                    raise MultiTaskModelError(
                        f"Checkpoint taxonomy for '{head}' does not match head size {expected}"
                    )

            if not os.path.exists(target_backbone_path):
                # Fallback check under ai_training/data/
                alt_backbone = "ai_training/data/training_runs/pretrained/yolov8n-cls.pt"
                if os.path.exists(alt_backbone):
                    target_backbone_path = alt_backbone
                else:
                    raise MultiTaskModelError(
                        f"Pretrained backbone weight not found at {target_backbone_path}"
                    )

            try:
                model = YOLOv8MultiTaskClassifier(
                    pretrained_path=target_backbone_path,
                    head_dims=head_dims,
                )
                model.load_state_dict(ckpt["model_state_dict"])
                model.eval()
            except Exception as e:
                raise MultiTaskModelError(
                    f"Failed to reconstruct and load state_dict: {e}"
                )

            load_time_ms = round((time.perf_counter() - t0) * 1000, 2)
            ckpt_sha256 = _sha256_file(target_model_path)
            _model_instance = model
            _model_metadata = {
                "model_version": build_model_version(ckpt, ckpt_sha256),
                "model_type": MODEL_TYPE,
                "checkpoint_sha256": ckpt_sha256,
                "stage": ckpt.get("stage"),
                "pretrained_backbone_identifier": ckpt.get("pretrained_backbone_identifier"),
                "random_seed": ckpt.get("random_seed"),
                "load_time_ms": load_time_ms,
                "class_to_idx": ckpt["class_to_idx"],
                "idx_to_class": ckpt["idx_to_class"],
                "head_dims": head_dims,
                "epoch": ckpt.get("epoch", None),
                "selection_score": ckpt.get("selection_score", ckpt.get("val_macro_f1")),
                "loss_type": ckpt.get("loss_type"),
                "model_path": target_model_path,
            }
            _model_cache_key = cache_key

    return _model_instance, _model_metadata


def reset_multitask_classifier_singleton():
    """Resets singleton state for testing purposes."""
    global _model_instance, _model_metadata, _model_cache_key
    with _model_lock:
        _model_instance = None
        _model_metadata = None
        _model_cache_key = None


def preprocess_image_crop(image_path: str, bbox: list = None) -> torch.Tensor:
    """
    Deterministically preprocesses an image or crop for multi-task inference.
    1. Validates bounding box `[x_min, y_min, x_max, y_max]`.
    2. Crops image if valid bbox provided; falls back to full image if missing/invalid.
    3. Resizes to (224, 224) and normalizes using ImageNet mean & std.
    Returns: torch.Tensor of shape [1, 3, 224, 224]
    """
    if not os.path.exists(image_path):
        raise MultiTaskModelError(f"Image file not found at {image_path}")

    try:
        pil_img = Image.open(image_path).convert("RGB")
    except Exception as e:
        raise MultiTaskModelError(f"Failed to open or decode image {image_path}: {e}")

    img_w, img_h = pil_img.size

    valid_crop = False
    if bbox is not None and isinstance(bbox, (list, tuple)) and len(bbox) == 4:
        try:
            x_min, y_min, x_max, y_max = [float(v) for v in bbox]
            # Ensure bounds are within image dimensions and form positive area
            if (0 <= x_min < x_max <= img_w) and (0 <= y_min < y_max <= img_h):
                if (x_max - x_min) >= 5 and (y_max - y_min) >= 5:
                    pil_img = pil_img.crop((x_min, y_min, x_max, y_max))
                    valid_crop = True
        except Exception:
            valid_crop = False

    # Resize to 224x224
    pil_img = pil_img.resize((224, 224), Image.Resampling.BILINEAR)

    # Convert to float tensor [3, 224, 224] scaled 0..1
    tensor = torch.from_numpy(
        __import__("numpy").array(pil_img, dtype=__import__("numpy").float32) / 255.0
    ).permute(2, 0, 1)

    # Normalize ImageNet stats
    mean = torch.tensor([0.485, 0.456, 0.406]).view(3, 1, 1)
    std = torch.tensor([0.229, 0.224, 0.225]).view(3, 1, 1)
    tensor = (tensor - mean) / std

    # Add batch dimension -> [1, 3, 224, 224]
    return tensor.unsqueeze(0)


def predict_multitask_features(
    image_path: str,
    bbox: list = None,
    thresholds: dict = None,
    model_path: str = None,
) -> dict:
    """
    Runs multi-task classification inference on an image file.
    Returns standard prediction dictionary containing 4 heads, top-3 predictions,
    per-head threshold flags, and overall user confirmation requirement.
    """
    model, meta = get_multitask_classifier(model_path=model_path)
    input_tensor = preprocess_image_crop(image_path, bbox=bbox)

    if thresholds is None:
        thresholds = DEFAULT_CONFIDENCE_THRESHOLDS
    else:
        # Merge defaults with custom provided thresholds
        merged_thresholds = DEFAULT_CONFIDENCE_THRESHOLDS.copy()
        merged_thresholds.update(thresholds)
        thresholds = merged_thresholds

    with torch.inference_mode():
        logits_dict = model(input_tensor)

    predictions = {}
    low_confidence_heads = []

    class_to_idx = meta["class_to_idx"]
    idx_to_class = meta["idx_to_class"]

    for head in HEADS:
        logits = logits_dict[head][0]
        probs = torch.softmax(logits, dim=0)

        top_val, top_idx = torch.topk(probs, k=min(3, probs.size(0)))
        top_idx_list = top_idx.tolist()
        top_val_list = top_val.tolist()

        pred_class_idx = top_idx_list[0]
        pred_label = idx_to_class[head].get(str(pred_class_idx), f"class_{pred_class_idx}")
        confidence = round(float(top_val_list[0]), 4)

        top_3 = []
        for v, idx in zip(top_val_list, top_idx_list):
            label_name = idx_to_class[head].get(str(idx), f"class_{idx}")
            top_3.append({
                "class_name": label_name,
                "class_index": int(idx),
                "confidence": round(float(v), 4)
            })

        thresh = float(thresholds.get(head, DEFAULT_CONFIDENCE_THRESHOLDS[head]))
        head_requires_confirm = confidence < thresh

        if head_requires_confirm:
            low_confidence_heads.append(head)

        predictions[head] = {
            "label": pred_label,
            "class_index": pred_class_idx,
            "confidence": confidence,
            "top_3": top_3,
            "requires_user_confirmation": head_requires_confirm,
            "threshold_used": thresh,
        }

    overall_requires_confirm = len(low_confidence_heads) > 0

    return {
        "model_version": meta["model_version"],
        "model_type": meta["model_type"],
        "checkpoint_sha256": meta["checkpoint_sha256"],
        "predictions": predictions,
        "low_confidence_heads": low_confidence_heads,
        "requires_user_confirmation": overall_requires_confirm,
    }
