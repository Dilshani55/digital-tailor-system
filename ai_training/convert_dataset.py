import json
import os
import shutil
from pathlib import Path

# ── DeepFashion2 category mapping ─────────────────────────────────────────────
# We only keep the 3 garment types in our scope
CATEGORY_MAP = {
    2: 0,   # short sleeve top   → class 0 (t-shirt)
    3: 1,   # long sleeve top    → class 1 (blouse)
    6: 2,   # vest / crop top    → class 2 (crop-top)
}

# These are the class names YOLOv8 will learn
CLASS_NAMES = ["t-shirt", "blouse", "crop-top"]


def convert_annotation(anno_path, image_path, output_label_path,
                        output_image_path):
    """
    Converts one DeepFashion2 JSON annotation to YOLO format .txt file.
    YOLO format: class_id  x_center  y_center  width  height
    All values normalised to 0.0 - 1.0
    """
    with open(anno_path, "r") as f:
        data = json.load(f)

    # Get image dimensions from first item
    img_w = data.get("width",  800)
    img_h = data.get("height", 1024)

    lines = []
    for key, item in data.items():
        if not isinstance(item, dict):
            continue

        category_id = item.get("category_id")
        if category_id not in CATEGORY_MAP:
            continue   # skip out-of-scope garment types

        class_id = CATEGORY_MAP[category_id]

        # Bounding box from DeepFashion2: [x1, y1, x2, y2]
        bbox = item.get("bounding_box", [])
        if len(bbox) != 4:
            continue

        x1, y1, x2, y2 = bbox
        x_center = ((x1 + x2) / 2) / img_w
        y_center = ((y1 + y2) / 2) / img_h
        width    = (x2 - x1) / img_w
        height   = (y2 - y1) / img_h

        lines.append(
            f"{class_id} {x_center:.6f} {y_center:.6f} "
            f"{width:.6f} {height:.6f}"
        )

    if not lines:
        return False   # no valid annotations found

    # Write label file
    with open(output_label_path, "w") as f:
        f.write("\n".join(lines))

    # Copy image
    shutil.copy(image_path, output_image_path)
    return True


def convert_split(image_dir, anno_dir, out_image_dir, out_label_dir,
                  max_images=None):
    """Converts a full train/val/test split."""
    os.makedirs(out_image_dir, exist_ok=True)
    os.makedirs(out_label_dir, exist_ok=True)

    image_files = list(Path(image_dir).glob("*.jpg"))
    if max_images:
        image_files = image_files[:max_images]

    converted = 0
    skipped   = 0

    for img_path in image_files:
        anno_path = Path(anno_dir) / img_path.with_suffix(".json").name
        if not anno_path.exists():
            skipped += 1
            continue

        out_img   = Path(out_image_dir) / img_path.name
        out_label = Path(out_label_dir) / img_path.with_suffix(".txt").name

        if convert_annotation(str(anno_path), str(img_path),
                               str(out_label), str(out_img)):
            converted += 1
        else:
            skipped += 1

    print(f"Converted: {converted}  |  Skipped: {skipped}")


if __name__ == "__main__":
    print("Converting training set...")
    convert_split(
        image_dir     = "deepfashion2/train/image",
        anno_dir      = "deepfashion2/train/annos",
        out_image_dir = "dataset/images/train",
        out_label_dir = "dataset/labels/train",
        max_images    = 5000   # start with 5000 for faster training
    )

    print("Converting validation set...")
    convert_split(
        image_dir     = "deepfashion2/validation/image",
        anno_dir      = "deepfashion2/validation/annos",
        out_image_dir = "dataset/images/val",
        out_label_dir = "dataset/labels/val",
        max_images    = 500
    )

    print("Done! Dataset ready for training.")
