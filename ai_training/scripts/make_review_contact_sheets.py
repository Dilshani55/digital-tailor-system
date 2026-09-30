"""
Contact sheets for the human-review queue (build_label_queue_15class.py -> queue.jsonl).

One PNG per (class, split) page with numbered garment crops, plus a review CSV per sheet listing the
queue_id of every tile and an empty `decision` column. A reviewer looks at the sheet and writes, for each
number, the class name, `reject` or `uncertain`, and their reviewer id. The filled CSVs are converted to
decisions.jsonl with --collect and passed to build_15class_manifests.py --decisions (which validates them).
The hint shown in the queue is never a label.

    $env:PYTHONPATH="."; backend\\venv\\Scripts\\python ai_training\\scripts\\make_review_contact_sheets.py
    $env:PYTHONPATH="."; backend\\venv\\Scripts\\python ai_training\\scripts\\make_review_contact_sheets.py --collect
"""
import argparse
import csv
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone

from PIL import Image, ImageDraw

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
QUEUE_DIR = os.path.join(ROOT, "ai_training", "data", "label_queue_15class")
OUT_DIR = os.path.join(QUEUE_DIR, "contact_sheets")
TILE, COLS, PER_SHEET = 220, 6, 36


def _crop(row):
    path = row["source_image_path"]
    if not os.path.isabs(path):
        path = os.path.join(ROOT, path)
    img = Image.open(path).convert("RGB")
    x, y, w, h = row["bbox"]
    pad = 0.08
    box = (max(0, x - w * pad), max(0, y - h * pad), min(img.width, x + w * (1 + pad)), min(img.height, y + h * (1 + pad)))
    crop = img.crop(box)
    crop.thumbnail((TILE - 8, TILE - 30))
    return crop


def make_sheets(rows):
    os.makedirs(OUT_DIR, exist_ok=True)
    groups = defaultdict(list)
    for r in rows:
        if not r.get("decision"):
            groups[(r["target_head"], r["target_class"], r["split"])].append(r)
    made = 0
    for (head, cls, split), items in sorted(groups.items()):
        for page in range(0, len(items), PER_SHEET):
            chunk = items[page:page + PER_SHEET]
            nrows = (len(chunk) + COLS - 1) // COLS
            sheet = Image.new("RGB", (COLS * TILE, nrows * TILE + 40), "white")
            draw = ImageDraw.Draw(sheet)
            name = f"{cls}_{split}_{page // PER_SHEET + 1:02d}"
            draw.text((8, 10), f"{head} = {cls}?  split={split}  sheet {name}  (answer per number: {cls} / reject / uncertain)",
                      fill="black")
            with open(os.path.join(OUT_DIR, f"{name}.csv"), "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["number", "queue_id", "target_head", "target_class", "decision", "reviewer_id"])
                for i, row in enumerate(chunk):
                    cx, cy = (i % COLS) * TILE, (i // COLS) * TILE + 40
                    try:
                        sheet.paste(_crop(row), (cx + 4, cy + 26))
                    except (OSError, ValueError):
                        draw.text((cx + 8, cy + 60), "image missing", fill="red")
                    draw.text((cx + 6, cy + 6), f"#{i + 1}", fill="black")
                    draw.rectangle([cx, cy, cx + TILE - 1, cy + TILE - 1], outline="#bbbbbb")
                    w.writerow([i + 1, row["queue_id"], head, cls, "", ""])
            sheet.save(os.path.join(OUT_DIR, f"{name}.png"))
            made += 1
    return made


def collect():
    """Turn filled review CSVs into decisions.jsonl (rows without a decision or reviewer are skipped)."""
    out, skipped = [], 0
    for name in sorted(os.listdir(OUT_DIR)):
        if not name.endswith(".csv"):
            continue
        with open(os.path.join(OUT_DIR, name), encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if not r["decision"].strip() or not r["reviewer_id"].strip():
                    skipped += 1
                    continue
                out.append({"queue_id": r["queue_id"], "decision": r["decision"].strip(),
                            "reviewer_id": r["reviewer_id"].strip(),
                            "reviewed_at": datetime.now(timezone.utc).isoformat()})
    path = os.path.join(QUEUE_DIR, "decisions.jsonl")
    with open(path, "w", encoding="utf-8") as f:
        for d in out:
            f.write(json.dumps(d) + "\n")
    print(f"{len(out)} decisions written to {path} ({skipped} unanswered rows skipped)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--collect", action="store_true", help="convert filled CSVs to decisions.jsonl")
    args = ap.parse_args()
    if args.collect:
        collect()
        return 0
    with open(os.path.join(QUEUE_DIR, "queue.jsonl"), encoding="utf-8") as f:
        rows = [json.loads(line) for line in f if line.strip()]
    print(f"{make_sheets(rows)} contact sheets written to {OUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
