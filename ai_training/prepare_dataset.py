import os
import zipfile
import csv
import io
import sys

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

    category_map = {
        "short sleeve top": 0,
        "long sleeve top": 1,
        "vest": 2
    }

    splits = ["train", "validation"]
    for split in splits:
        print(f"Processing split: {split}...")
        csv_name = f"DeepFashion2 Resized/input/{split}.csv"
        csv_data = z.read(csv_name).decode('utf-8')
        
        reader = csv.reader(io.StringIO(csv_data))
        header = next(reader)
        # Find column indices
        path_idx = header.index("path")
        bbox_idx = header.index("b_box")
        cat_idx = header.index("category_name")
        w_idx = header.index("img_width")
        h_idx = header.index("img_height")

        count = 0
        limit = 100 if split == "train" else 20
        
        # Output folders
        split_name = "train" if split == "train" else "val"
        img_out = os.path.join(out_dir, "images", split_name)
        lbl_out = os.path.join(out_dir, "labels", split_name)
        os.makedirs(img_out, exist_ok=True)
        os.makedirs(lbl_out, exist_ok=True)

        for row in reader:
            cat = row[cat_idx]
            if cat not in category_map:
                continue
                
            class_id = category_map[cat]
            # Parse bounding box [x1, y1, x2, y2]
            bbox_str = row[bbox_idx].strip("[]")
            x1, y1, x2, y2 = map(float, bbox_str.split(","))
            
            img_w = float(row[w_idx])
            img_h = float(row[h_idx])
            
            # Normalize to YOLO format
            x_center = ((x1 + x2) / 2) / img_w
            y_center = ((y1 + y2) / 2) / img_h
            width = (x2 - x1) / img_w
            height = (y2 - y1) / img_h

            # Extract image
            img_zip_path = "DeepFashion2 Resized/" + row[path_idx].lstrip("/")
            img_data = z.read(img_zip_path)
            
            # Save image
            img_name = os.path.basename(img_zip_path)
            with open(os.path.join(img_out, img_name), "wb") as f:
                f.write(img_data)
                
            # Save label file
            lbl_name = os.path.splitext(img_name)[0] + ".txt"
            with open(os.path.join(lbl_out, lbl_name), "w") as f:
                f.write(f"{class_id} {x_center:.6f} {y_center:.6f} {width:.6f} {height:.6f}\n")

            count += 1
            if count >= limit:
                break
                
        print(f"Extracted {count} images for {split_name}.")

    print("Dataset preparation complete!")

if __name__ == '__main__':
    prepare()
