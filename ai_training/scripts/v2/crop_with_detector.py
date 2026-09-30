"""Add garment crops to a JSONL annotation set using the SAME detector and crop rule as the app
(tight detector box + gd.CROP_MARGIN, EXIF-rotated; saved like deepfashion2_tops: crop max side 320 px,
full photo max side 480 px). Records where the detector finds no garment keep crop_path = null and are counted.

    backend\\venv\\Scripts\\python ai_training\\scripts\\v2\\crop_with_detector.py --dataset ai_training/datasets/deepfashion_multimodal --detector <best.pt>
"""
import argparse
import json
import os
import sys
from collections import Counter

from PIL import Image, ImageOps

sys.path.insert(0, ".")
sys.path.insert(0, "backend")
from backend.app.ai import garment_detector as gd  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--detector", required=True)
    a = ap.parse_args()
    stats = {}
    for sp in ("train", "val", "test"):
        src = f"{a.dataset}/annotations/{sp}.jsonl"
        recs = [json.loads(l) for l in open(src, encoding="utf-8") if l.strip()]
        out_dir = f"{a.dataset}/images/{sp}"
        os.makedirs(out_dir, exist_ok=True)
        c = Counter()
        for i, r in enumerate(recs):
            stem = r["record_uid"].split(":", 1)[1]
            full_out, crop_out = f"{out_dir}/{stem}_full.jpg", f"{out_dir}/{stem}_crop.jpg"
            with Image.open(r["full_image_path"]) as im:
                img = ImageOps.exif_transpose(im).convert("RGB")
            d = gd.detect_garment(r["full_image_path"], model_path=a.detector)
            if d["box_xyxy"]:
                box = gd.pad_box(d["box_xyxy"], *img.size)
                crop = img.crop(tuple(int(round(v)) for v in box))
                crop.thumbnail((320, 320))
                crop.save(crop_out, quality=92)
                r["crop_path"], r["bbox_xyxy_detector"] = crop_out, [round(v, 1) for v in box]
                r["detector_class"], r["detector_score"] = d["class"], d["score"]
                c[f"box_{d['class']}"] += 1
            else:
                r["crop_path"], r["detector_class"] = None, None
                c["no_box"] += 1
            full = img.copy()
            full.thumbnail((480, 480))
            full.save(full_out, quality=92)
            r["full_image_path_original"], r["full_image_path"] = r["full_image_path"], full_out
            if i % 1000 == 0:
                print(sp, i, "/", len(recs), dict(c), flush=True)
        with open(src, "w", encoding="utf-8") as f:
            for r in recs:
                f.write(json.dumps(r) + "\n")
        stats[sp] = dict(c)
    stats["detector_sha256"] = gd._sha256(a.detector)
    json.dump(stats, open(f"{a.dataset}/annotations/crop_stats.json", "w"), indent=2)
    print(json.dumps(stats, indent=1))


if __name__ == "__main__":
    main()
