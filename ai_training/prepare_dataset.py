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

    # Sleeve / Garment Mapping
    # 0: short-sleeve, 1: long-sleeve, 2: sleeveless, 3: one-shoulder, 4: round-neck, 5: v-neck
    category_map = {
        "short sleeve top": 0,
        "long sleeve top": 1,
        "vest": 2,
        "sling": 2
    }

    per_class_limit_train = {0: 35, 1: 35, 2: 30, 3: 20}
    per_class_limit_val = {0: 8, 1: 8, 2: 8, 3: 5}

    splits = ["train", "validation"]
    for split in splits:
        print(f"\nProcessing split: {split}...")
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

        split_name = "train" if split == "train" else "val"
        class_limits = per_class_limit_train if split == "train" else per_class_limit_val
        class_counts = {0: 0, 1: 0, 2: 0, 3: 0}

        img_out = os.path.join(out_dir, "images", split_name)
        lbl_out = os.path.join(out_dir, "labels", split_name)
        os.makedirs(img_out, exist_ok=True)
        os.makedirs(lbl_out, exist_ok=True)

        for row in reader:
            cat = row[cat_idx]
            if cat not in category_map:
                continue

            # Check if this sample is asymmetric / one-shoulder
            is_one_shoulder = False
            lms_raw = row[lm_idx].strip()
            pts = []
            if lms_raw and lms_raw != "[]":
                try:
                    lms = eval(lms_raw)
                    pts = [(lms[i], lms[i+1], lms[i+2]) for i in range(0, len(lms), 3)]
                except Exception:
                    pts = []

            if cat in ["short sleeve top", "long sleeve top"] and len(pts) >= 22:
                left_v = sum(1 for p in pts[6:14] if p[2] > 0)
                right_v = sum(1 for p in pts[14:22] if p[2] > 0)
                # Asymmetric sleeve presence -> One-shoulder
                if (left_v >= 4 and right_v == 0) or (right_v >= 4 and left_v == 0):
                    is_one_shoulder = True

            garment_class_id = 3 if is_one_shoulder else category_map[cat]

            if class_counts[garment_class_id] >= class_limits[garment_class_id]:
                continue

            # Parse garment bounding box [x1, y1, x2, y2]
            bbox_str = row[bbox_idx].strip("[]")
            x1, y1, x2, y2 = map(float, bbox_str.split(","))

            img_w = float(row[w_idx])
            img_h = float(row[h_idx])
            if img_w <= 0 or img_h <= 0:
                continue

            # Normalize garment bbox
            x_center = ((x1 + x2) / 2) / img_w
            y_center = ((y1 + y2) / 2) / img_h
            width = (x2 - x1) / img_w
            height = (y2 - y1) / img_h

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
            label_lines = [f"{garment_class_id} {x_center:.6f} {y_center:.6f} {width:.6f} {height:.6f}"]

            # Extract neckline bbox from collar landmarks (pts 0..5)
            if len(pts) >= 6 and not is_one_shoulder:
                neck_pts = [p for p in pts[:6] if p[2] > 0]
                if len(neck_pts) >= 3:
                    nx1 = min(p[0] for p in neck_pts)
                    ny1 = min(p[1] for p in neck_pts)
                    nx2 = max(p[0] for p in neck_pts)
                    ny2 = max(p[1] for p in neck_pts)
                    nw = nx2 - nx1
                    nh = ny2 - ny1
                    if nw > 12 and nh > 8:
                        neck_xc = ((nx1 + nx2) / 2) / img_w
                        neck_yc = ((ny1 + ny2) / 2) / img_h
                        neck_w = nw / img_w
                        neck_h = nh / img_h
                        # Class 5: v-neck if drop ratio > 0.38, else Class 4: round-neck
                        neck_cls = 5 if (nh / nw) > 0.38 else 4
                        label_lines.append(f"{neck_cls} {neck_xc:.6f} {neck_yc:.6f} {neck_w:.6f} {neck_h:.6f}")

            # Save label file
            lbl_name = os.path.splitext(img_name)[0] + ".txt"
            with open(os.path.join(lbl_out, lbl_name), "w") as f:
                f.write("\n".join(label_lines) + "\n")

            class_counts[garment_class_id] += 1

            # Check if all classes have met their limit
            if all(class_counts[c] >= class_limits[c] for c in class_limits):
                break

        print(f"Summary for {split_name}: {class_counts}")

    # Add user uploaded one-shoulder samples if available
    user_up_path = os.path.join(r"C:\Users\Asus\.gemini\antigravity\brain\3f091662-64ff-41bd-9949-0bb7bd99d547\.user_uploaded")
    if os.path.exists(user_up_path):
        target_imgs = ["media_1788547720014.png", "media_1788547705108.png", "media_1788545635629.png"]
        for t_img in target_imgs:
            src = os.path.join(user_up_path, t_img)
            if os.path.exists(src):
                dest_name = f"oneshoulder_{t_img}"
                dest_path = os.path.join(out_dir, "images", "train", dest_name)
                lbl_path = os.path.join(out_dir, "labels", "train", os.path.splitext(dest_name)[0] + ".txt")
                shutil.copy(src, dest_path)
                # Garment box (class 3: one-shoulder)
                with open(lbl_path, "w") as f:
                    f.write("3 0.500000 0.500000 0.850000 0.850000\n")
                print(f"Added user one-shoulder sample: {dest_name}")

    print("\nDataset preparation with Sleeves & Necklines complete!")

if __name__ == '__main__':
    prepare()
