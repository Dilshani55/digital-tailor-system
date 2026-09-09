import os
import zipfile
import csv
import io
import sys
import shutil
from PIL import Image

def prepare():
    workspace = r"C:\Research\Developing\digital-tailor-system"
    zip_path = os.path.join(workspace, "ai_training", "dataset", "images", "archive (1).zip")
    out_dir = os.path.join(workspace, "ai_training", "dataset")

    print("Opening dataset zip...")
    if not os.path.exists(zip_path):
        print(f"Error: Dataset archive (1).zip not found at {zip_path}")
        return

    csv.field_size_limit(sys.maxsize)
    z = zipfile.ZipFile(zip_path)

    # 11-Class Taxonomy:
    # 0: crop-top, 1: blouse, 2: t-shirt
    # 3: round-neck, 4: v-neck, 5: off-the-shoulder, 6: one-shoulder, 7: square-neck
    # 8: sleeveless, 9: short-sleeve, 10: long-sleeve

    categories = ["short sleeve top", "long sleeve top", "vest", "sling"]
    per_class_limit_train = {
        "short sleeve top": 250,
        "long sleeve top": 250,
        "vest": 200,
        "sling": 150
    }
    per_class_limit_val = {
        "short sleeve top": 35,
        "long sleeve top": 35,
        "vest": 30,
        "sling": 20
    }

    # Ensure clean output directories
    for split in ["train", "val"]:
        img_out = os.path.join(out_dir, "images", split)
        lbl_out = os.path.join(out_dir, "labels", split)
        if os.path.exists(img_out):
            shutil.rmtree(img_out)
        if os.path.exists(lbl_out):
            shutil.rmtree(lbl_out)
        os.makedirs(img_out, exist_ok=True)
        os.makedirs(lbl_out, exist_ok=True)

    splits = ["train", "validation"]
    for split in splits:
        split_name = "train" if split == "train" else "val"
        print(f"\nProcessing split: {split_name}...")
        csv_name = f"DeepFashion2 Resized/input/{split}.csv"
        try:
            csv_data = z.read(csv_name).decode('utf-8')
        except Exception as e:
            print(f"Could not read {csv_name}: {e}")
            continue

        reader = csv.reader(io.StringIO(csv_data))
        header = next(reader)
        path_idx = header.index("path")
        bbox_idx = header.index("b_box")
        cat_idx = header.index("category_name")
        lm_idx = header.index("landmarks")
        w_idx = header.index("img_width")
        h_idx = header.index("img_height")

        class_limits = per_class_limit_train if split_name == "train" else per_class_limit_val
        class_counts = {c: 0 for c in categories}

        img_out = os.path.join(out_dir, "images", split_name)
        lbl_out = os.path.join(out_dir, "labels", split_name)

        total_extracted = 0

        for row in reader:
            cat = row[cat_idx]
            if cat not in categories:
                continue

            if class_counts[cat] >= class_limits[cat]:
                continue

            # Parse bounding box [x1, y1, x2, y2]
            bbox_str = row[bbox_idx].strip("[]")
            x1, y1, x2, y2 = map(float, bbox_str.split(","))

            img_w = float(row[w_idx])
            img_h = float(row[h_idx])
            if img_w <= 0 or img_h <= 0:
                continue

            bw = x2 - x1
            bh = y2 - y1
            if bw <= 10 or bh <= 10:
                continue

            # Normalized garment bbox
            x_center = ((x1 + x2) / 2) / img_w
            y_center = ((y1 + y2) / 2) / img_h
            norm_w = bw / img_w
            norm_h = bh / img_h

            aspect = bh / bw

            # Landmarks extraction
            lms_raw = row[lm_idx].strip()
            pts = []
            if lms_raw and lms_raw != "[]":
                try:
                    lms = eval(lms_raw)
                    pts = [(lms[i], lms[i+1], lms[i+2]) for i in range(0, len(lms), 3)]
                except Exception:
                    pts = []

            # 1. Determine Garment Type (0: crop-top, 1: blouse, 2: t-shirt)
            is_crop = False
            if cat == "sling":
                is_crop = True
            elif aspect < 0.86:
                is_crop = True
            elif len(pts) >= 25:
                # Check hem points (pts 22..24)
                hem_y = [p[1] for p in pts[22:25] if p[2] > 0]
                if hem_y and (max(hem_y) / 600.0) < 0.65:
                    is_crop = True

            if is_crop:
                garment_cls = 0  # crop-top
            elif cat == "short sleeve top":
                garment_cls = 2  # t-shirt
            else:
                garment_cls = 1  # blouse

            # 2. Determine Sleeve Type (8: sleeveless, 9: short-sleeve, 10: long-sleeve)
            is_one_shoulder = False
            if len(pts) >= 22:
                left_v = sum(1 for p in pts[6:14] if p[2] > 0)
                right_v = sum(1 for p in pts[14:22] if p[2] > 0)
                if (left_v >= 4 and right_v == 0) or (right_v >= 4 and left_v == 0):
                    is_one_shoulder = True

            if is_one_shoulder:
                sleeve_cls = 6  # one-shoulder
            elif cat in ["vest", "sling"]:
                sleeve_cls = 8  # sleeveless
            elif cat == "short sleeve top":
                sleeve_cls = 9  # short-sleeve
            else:
                sleeve_cls = 10 # long-sleeve

            # 3. Determine Neckline from collar landmarks (pts 0..5)
            neck_cls = 3  # default round-neck
            if is_one_shoulder:
                neck_cls = 6  # one-shoulder
            elif cat == "sling":
                neck_cls = 5  # off-the-shoulder / strapless
            elif len(pts) >= 6:
                valid_neck = [p for p in pts[:6] if p[2] > 0]
                if len(valid_neck) >= 3:
                    n_min_x = min(p[0] for p in valid_neck)
                    n_max_x = max(p[0] for p in valid_neck)
                    n_min_y = min(p[1] for p in valid_neck)
                    n_max_y = max(p[1] for p in valid_neck)
                    span_w = max(1.0, n_max_x - n_min_x)
                    span_h = max(1.0, n_max_y - n_min_y)
                    drop_ratio = span_h / span_w

                    if drop_ratio > 0.38:
                        neck_cls = 4  # v-neck
                    elif drop_ratio < 0.20:
                        neck_cls = 5  # off-the-shoulder
                    elif len(valid_neck) >= 4 and abs(pts[2][1] - pts[3][1]) < 8 and drop_ratio > 0.24:
                        neck_cls = 7  # square-neck

            # Physically bounded neckline region at upper garment chest
            neck_xc = x_center
            neck_yc = max(0.05, min(0.95, (y1 + 0.14 * bh) / img_h))
            neck_w  = max(0.08, min(0.90, (0.52 * bw) / img_w))
            neck_h  = max(0.05, min(0.40, (0.26 * bh) / img_h))

            # Load image from zip
            img_name = os.path.basename(row[path_idx])
            img_zip_path = f"DeepFashion2 Resized/resized/{split}/{img_name}"
            try:
                img_data = z.read(img_zip_path)
            except KeyError:
                continue

            # Save image
            with open(os.path.join(img_out, img_name), "wb") as f:
                f.write(img_data)

            # Build label lines
            # Line 1: Garment Type (0: crop-top, 1: blouse, 2: t-shirt)
            label_lines = [f"{garment_cls} {x_center:.6f} {y_center:.6f} {norm_w:.6f} {norm_h:.6f}"]

            # Line 2: Sleeve Feature (8: sleeveless, 9: short-sleeve, 10: long-sleeve, 6: one-shoulder)
            label_lines.append(f"{sleeve_cls} {x_center:.6f} {y_center:.6f} {norm_w:.6f} {norm_h:.6f}")

            # Line 3: Neckline (3: round, 4: v-neck, 5: off-the-shoulder, 6: one-shoulder, 7: square)
            label_lines.append(f"{neck_cls} {neck_xc:.6f} {neck_yc:.6f} {neck_w:.6f} {neck_h:.6f}")

            # Save label file
            lbl_name = os.path.splitext(img_name)[0] + ".txt"
            with open(os.path.join(lbl_out, lbl_name), "w") as f:
                f.write("\n".join(label_lines) + "\n")

            class_counts[cat] += 1
            total_extracted += 1

            if all(class_counts[c] >= class_limits[c] for c in categories):
                break

        print(f"Summary for {split_name}: {class_counts}, Total: {total_extracted} images")

    # Add user uploaded real-world samples with ground-truth labels
    print("\nIntegrating user uploaded samples...")
    train_img_dir = os.path.join(out_dir, "images", "train")
    train_lbl_dir = os.path.join(out_dir, "labels", "train")

    backend_uploads = os.path.join(workspace, "backend", "uploads")
    user_up_dir = os.path.join(r"C:\Users\Asus\.gemini\antigravity\brain\3f091662-64ff-41bd-9949-0bb7bd99d547\.user_uploaded")

    # 1. Pink Strapless Knot Crop Top (3ee420f214614fd6af7e928b07c2acef.jpg)
    pink_src = os.path.join(backend_uploads, "3ee420f214614fd6af7e928b07c2acef.jpg")
    if os.path.exists(pink_src):
        for copy_idx in range(5):  # Replicate 5 times with slight name variation to give strong weight
            dest_img = f"user_pink_croptop_{copy_idx}.jpg"
            dest_lbl = f"user_pink_croptop_{copy_idx}.txt"
            shutil.copy(pink_src, os.path.join(train_img_dir, dest_img))
            with open(os.path.join(train_lbl_dir, dest_lbl), "w") as f:
                # 0: crop-top, 5: off-the-shoulder (strapless/sweetheart), 8: sleeveless
                f.write("0 0.500000 0.520000 0.720000 0.440000\n")
                f.write("5 0.500000 0.320000 0.650000 0.160000\n")
                f.write("8 0.500000 0.520000 0.880000 0.460000\n")
        print("Added Pink Strapless Crop Top (5 weight-augmented samples)")

    # 2. One-shoulder user uploaded samples
    if os.path.exists(user_up_dir):
        one_shoulder_samples = ["media_1788547720014.png", "media_1788547705108.png", "media_1788545635629.png"]
        for sample in one_shoulder_samples:
            s_path = os.path.join(user_up_dir, sample)
            if os.path.exists(s_path):
                dest_img = f"user_oneshoulder_{sample}"
                dest_lbl = os.path.splitext(dest_img)[0] + ".txt"
                shutil.copy(s_path, os.path.join(train_img_dir, dest_img))
                with open(os.path.join(train_lbl_dir, dest_lbl), "w") as f:
                    # 0: crop-top, 6: one-shoulder
                    f.write("0 0.500000 0.500000 0.800000 0.800000\n")
                    f.write("6 0.500000 0.360000 0.650000 0.280000\n")
                print(f"Added user one-shoulder sample: {sample}")

    print("\nDataset preparation with 11 Classes successfully completed!")

if __name__ == '__main__':
    prepare()

