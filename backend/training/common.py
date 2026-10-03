"""What the four garment models are, and how a dataset record becomes a label for each of them.

Four separate image classifiers (run from the repository root, see README.md in this folder):

  garment        blouse / t-shirt                          MobileNetV3-Large (torchvision, ImageNet-pretrained)
  neckline       round-neck / v-neck / square-neck / collared-neck    YOLOv8n-cls
  sleeve_length  sleeveless / short-sleeve / long-sleeve               YOLOv8n-cls
  sleeve_design  regular-sleeve / puff-sleeve (bell removed 3 Oct 2026) YOLOv8n-cls  (asked only when the garment has sleeves)

Labels come from the audited manifests in data/manifests_m42 (Fashionpedia, DeepFashion2, DeepFashion-MultiModal
and the human review of 1 Oct 2026). A value outside a task's classes is dropped for that task, never remapped.
"""
import json
import os

ROOT = "backend/training"
MANIFESTS = f"{ROOT}/data/manifests_m42"
OUT = f"{ROOT}/datasets/attributes"
MODEL_DIR = "backend/model"

TASKS = {
    "garment": ["blouse", "t-shirt"],
    "neckline": ["round-neck", "v-neck", "square-neck", "collared-neck"],
    "sleeve_length": ["sleeveless", "short-sleeve", "long-sleeve"],
    "sleeve_design": ["regular-sleeve", "puff-sleeve"],          # bell-sleeve removed from the design scope on 3 Oct 2026
}
HEAD = {"neckline": "neckline_type", "sleeve_length": "sleeve_length", "sleeve_design": "sleeve_style"}
WEIGHTS = {"garment": "garment_mobilenetv3.pt", "neckline": "neckline_yolov8.pt",
           "sleeve_length": "sleeve_length_yolov8.pt", "sleeve_design": "sleeve_design_yolov8.pt"}
TRUSTED = {"human_verified", "fashionpedia_direct", "df2_human_category", "dmm_human_shape"}
DMM_GARMENT = {"Blouses_Shirts": "blouse", "Tees_Tanks": "t-shirt", "Graphic_Tees": "t-shirt"}


def load_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def local(path):
    """Manifest paths were written when this folder was called ai_training/."""
    if not path:
        return None
    p = path.replace("\\", "/")
    return ROOT + p[len("ai_training"):] if p.startswith("ai_training/") else p


def label_of(task, rec):
    """(class, tier) of a record for a task, or None. tier: 'trusted' (a person labelled it) or 'proxy'."""
    if task == "garment":
        uid = rec["record_uid"]
        if uid.startswith("dmm:"):
            # shop category of the photo; a tee category with a sleeveless label is a tank top, not a T-shirt
            category = uid.split("-")[1] if "-" in uid else ""
            sleeve = rec["labels"].get("sleeve_length")
            if category == "Blouses_Shirts":
                return "blouse", "proxy"
            if DMM_GARMENT.get(category) == "t-shirt" and sleeve in ("short-sleeve", "long-sleeve"):
                return "t-shirt", "proxy"
            return None
        g = rec["labels"].get("garment_type") if rec["masks"].get("garment_type") else None
        if g in TASKS["garment"] and rec["provenance"].get("garment_type") == "human_verified":
            return g, "trusted"
        return None                                  # crop-top labels are not used: that class no longer exists
    head = HEAD[task]
    value = rec["labels"].get(head) if rec["masks"].get(head) else None
    if value in TASKS[task] and rec["provenance"].get(head) in TRUSTED:
        return value, "trusted"
    return None


def whole_photo(rec):
    for key in ("full_image_path", "source_image_path", "crop_path"):
        p = local(rec.get(key))
        if p and os.path.exists(p):
            return p
    return None


def garment_crop(rec):
    """(image path, box xyxy or None): the dataset's own garment crop."""
    p = local(rec.get("crop_path"))
    if p and os.path.exists(p):
        return p, None
    b = rec.get("bbox")
    box = [b[0], b[1], b[0] + b[2], b[1] + b[3]] if b and len(b) == 4 else None
    return local(rec.get("source_image_path")), box
