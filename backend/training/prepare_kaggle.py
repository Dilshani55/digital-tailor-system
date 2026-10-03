"""Add the Kaggle "Fashion Product Images Dataset" (paramaggarwal, MIT) to the neckline and sleeve-design training data.

    backend\\venv\\Scripts\\python backend\\training\\prepare_kaggle.py

Input:  backend/training/data/raw/archive (2).zip   (the full dataset: images + one JSON per product; not unzipped)
Output (local, git-ignored):
    backend/training/data/raw/kaggle_fashion/<id>.jpg           the product photos that are used (extracted once)
    backend/training/datasets/attributes_kaggle/<task>/train/<class>/*.jpg
    backend/training/datasets/attributes_kaggle/<task>/val      the SAME validation photos as before (unchanged)
    backend/training/datasets/attributes_kaggle/summary.json     counts and the label mapping

What is used: women's and girls' topwear (Tops, Tshirts, Shirts, Tunics, Kurtis, Kurtas) whose product page gives a
neckline ("Neck" / "Collar") or a sleeve design ("Sleeve Styling") that maps onto one of the app's classes. The
labels were entered by the shop; nobody has checked them for this project.

Fair comparison: every Kaggle photo goes to TRAINING only. Validation (checkpoint and threshold choice) and test
(datasets/attributes/<task>/eval.jsonl, used by evaluate_models.py) stay exactly as they were, so the new model is
compared with the current one on the same photos. Each Kaggle photo is cropped with the app's own garment detector,
exactly as the app crops an uploaded photo.

Training classes are balanced as before (prepare_datasets.py): a big class is capped, a small class is repeated.
The sleeve-design cap is raised from 400 to 800 because more photos are available; this was fixed before training.
"""
import json
import os
import random
import re
import shutil
import sys
import zipfile
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor

sys.path.insert(0, "backend")
sys.path.insert(0, "backend/training")
import common as C                                             # noqa: E402

ZIP = f"{C.ROOT}/data/raw/archive (2).zip"
RAW = f"{C.ROOT}/data/raw/kaggle_fashion"
OUT = f"{C.ROOT}/datasets/attributes_kaggle"
SIZE, SEED = 256, 42
TASKS = ("neckline", "sleeve_design")
TRAIN_CAP = {"neckline": 2500, "sleeve_design": 800}
TRAIN_FLOOR = {"neckline": 800, "sleeve_design": 300}
ARTICLE_TYPES = {"Tops", "Tshirts", "Shirts", "Tunics", "Kurtis", "Kurtas"}

# shop label -> app class (anything not listed is not used)
NECK = {"Round Neck": "round-neck", "Scoop Neck": "round-neck", "V-Neck": "v-neck", "Square Neck": "square-neck",
        "Mandarin Collar": "collared-neck", "Polo Collar": "collared-neck", "Shirt Collar": "collared-neck"}
COLLAR = {"Spread Collar": "collared-neck", "Mandarin Collar": "collared-neck", "Cutaway Collar": "collared-neck",
          "Slim Collar": "collared-neck", "Mock Collar": "collared-neck", "Peter Pan Collar": "collared-neck"}
SLEEVE_STYLE = {"Regular Sleeves": "regular-sleeve", "Puff Sleeves": "puff-sleeve", "Bell Sleeves": "bell-sleeve",
                "Flared Sleeves": "bell-sleeve"}
NO_SLEEVE = {"Sleeveless", "No Sleeves"}


def products(z):
    """{product id: (neckline class or None, sleeve-design class or None, image name in the zip)} - one per product."""
    names = z.namelist()
    images = {}
    for n in names:
        m = re.search(r"/images/(\d+)\.jpg$", n)
        if m:
            images.setdefault(m.group(1), n)
    out = {}
    for n in names:
        m = re.search(r"/styles/(\d+)\.json$", n)
        if not m or m.group(1) in out or m.group(1) not in images:
            continue
        try:
            data = json.loads(z.read(n)).get("data") or {}
        except (ValueError, KeyError):
            continue
        sub = (data.get("subCategory") or {}).get("typeName")
        art = (data.get("articleType") or {}).get("typeName")
        if sub != "Topwear" or art not in ARTICLE_TYPES or data.get("gender") not in ("Women", "Girls"):
            continue
        a = data.get("articleAttributes") or {}
        neck = NECK.get(str(a.get("Neck", "")).strip()) or COLLAR.get(str(a.get("Collar", "")).strip())
        sleeve = SLEEVE_STYLE.get(str(a.get("Sleeve Styling", "")).strip())
        if str(a.get("Sleeve Length", "")).strip() in NO_SLEEVE:
            sleeve = None                                   # a sleeve design needs a sleeve
        if neck or sleeve:
            out[m.group(1)] = (neck, sleeve, images[m.group(1)])
    return out


def _crop(job):
    """Detector crop of one photo, the same way the app crops an upload."""
    src, dst = job
    try:
        if os.path.exists(dst):
            return dst, None
        from app.ai import garment_detector as gd
        from app.ai.preprocess import crop_box, load_rgb, square_pad
        image = load_rgb(src)
        d = gd.detect_garment(src)
        box = gd.pad_box(d["box_xyxy"], image.width, image.height) if d.get("box_xyxy") else None
        square_pad(crop_box(image, box, margin=0.0) if box else image, SIZE).save(dst, "JPEG", quality=90)
        return dst, None
    except Exception as exc:                                   # an unreadable photo is reported, not hidden
        return None, f"{src}: {type(exc).__name__}: {exc}"


def unique_existing(folder):
    """The photos of an existing training class folder without its repeated copies (name_r1.jpg, ...)."""
    if not os.path.isdir(folder):
        return []
    return sorted(os.path.join(folder, f) for f in os.listdir(folder)
                  if f.lower().endswith(".jpg") and not re.search(r"_r\d+\.jpg$", f))


def main():
    rnd = random.Random(SEED)
    z = zipfile.ZipFile(ZIP)
    found = products(z)
    print(f"products with a usable label: {len(found)}", flush=True)
    os.makedirs(RAW, exist_ok=True)
    for pid, (_, _, member) in found.items():
        dst = f"{RAW}/{pid}.jpg"
        if not os.path.exists(dst):
            with z.open(member) as fsrc, open(dst, "wb") as fdst:
                shutil.copyfileobj(fsrc, fdst)
    crops_dir = f"{RAW}/crops"
    os.makedirs(crops_dir, exist_ok=True)
    jobs = [(f"{RAW}/{pid}.jpg", f"{crops_dir}/kaggle_{pid}.jpg") for pid in found]
    errors = []
    with ProcessPoolExecutor(max_workers=4) as pool:
        for i, (_, err) in enumerate(pool.map(_crop, jobs, chunksize=16), 1):
            if err:
                errors.append(err)
            if i % 500 == 0:
                print(f"  cropped {i}/{len(jobs)}", flush=True)
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    summary = {"source": "Kaggle Fashion Product Images Dataset (paramaggarwal), MIT licence; shop-entered labels",
               "mapping": {"neckline": {**NECK, **COLLAR}, "sleeve_design": SLEEVE_STYLE},
               "train_cap": TRAIN_CAP, "train_floor": TRAIN_FLOOR, "unreadable": errors, "tasks": {}}
    for t, task in enumerate(TASKS):
        kaggle = defaultdict(list)
        for pid, labels in sorted(found.items()):
            crop = f"{crops_dir}/kaggle_{pid}.jpg"
            if labels[t] and os.path.exists(crop):
                kaggle[labels[t]].append(crop)
        counts = {}
        for cls in C.TASKS[task]:
            old = unique_existing(f"{C.OUT}/{task}/train/{cls}")
            pool_ = old + kaggle.get(cls, [])
            rnd.shuffle(pool_)
            chosen = pool_[:TRAIN_CAP[task]]
            dst_dir = f"{OUT}/{task}/train/{cls}"
            os.makedirs(dst_dir, exist_ok=True)
            for src in chosen:
                shutil.copyfile(src, f"{dst_dir}/{os.path.basename(src)}")
            extra, k = 0, 1                                     # small class: repeat until the floor
            while chosen and len(chosen) + extra < TRAIN_FLOOR[task]:
                for src in chosen:
                    if len(chosen) + extra >= TRAIN_FLOOR[task]:
                        break
                    base, ext = os.path.splitext(os.path.basename(src))
                    shutil.copyfile(src, f"{dst_dir}/{base}_r{k}{ext}")
                    extra += 1
                k += 1
            counts[cls] = {"existing_unique": len(old), "kaggle": len(kaggle.get(cls, [])), "used_unique": len(chosen),
                           "files": len(chosen) + extra}
        shutil.copytree(f"{C.OUT}/{task}/val", f"{OUT}/{task}/val")   # validation unchanged
        summary["tasks"][task] = counts
        print(task, json.dumps(counts, indent=1), flush=True)
    json.dump(summary, open(f"{OUT}/summary.json", "w", encoding="utf-8"), indent=1)
    print(f"unreadable photos: {len(errors)}")


if __name__ == "__main__":
    main()
