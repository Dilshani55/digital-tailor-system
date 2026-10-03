#!/usr/bin/env python3
"""
verify_pdf.py - digital check of a pattern PDF produced by the app (any downloaded "sewing_pattern_*.pdf").

It reads the PDF's own vector data and text; it does not look at a printout. It answers:
  * is every page A4 (210 x 297 mm)?
  * is the calibration square drawn at exactly 5.00 x 5.00 cm (1 cm = 72 / 2.54 pt), on the instruction page
    and on at least one pattern tile?
  * does the PDF say to print at 100 % / Actual size, and are the pages numbered "Page i of n"?
  * are the customer-facing sections there: confirmed design, fabric, measurements, labelled pieces, cutting
    instructions, the 36" / 45" / 60" fabric requirement (metres, yards, areas), the front / back block overviews
    marked NOT TO SCALE and the list of calculations ("Why this size?")?

A PASS here means the FILE is at true scale. Whether a printer prints it at true scale is checked by a person
with a ruler on the printed 5 cm square (see docs/HUMAN_VALIDATION.md).

Usage (from backend/):   venv\\Scripts\\python tools\\verify_pdf.py path\\to\\sewing_pattern.pdf
Exit code 0 = every check passed, 1 = a check failed.
"""

import json
import sys

try:
    import pymupdf
except ImportError:                                         # pragma: no cover
    sys.exit("pymupdf is needed for this check:  venv\\Scripts\\python -m pip install -r requirements-dev.txt")

PT_PER_CM = 72.0 / 2.54
A4_PT = (595.28, 841.89)
SQUARE_CM = 5.0
TOLERANCE_PT = 0.4          # 0.14 mm


def squares(page):
    """Sizes (cm) of the 5 cm squares drawn on a page, measured from the vector rectangles."""
    found = []
    for d in page.get_drawings():
        r = d["rect"]
        if abs(r.width - SQUARE_CM * PT_PER_CM) < TOLERANCE_PT and abs(r.height - SQUARE_CM * PT_PER_CM) < TOLERANCE_PT:
            found.append((round(r.width / PT_PER_CM, 3), round(r.height / PT_PER_CM, 3)))
    return found


def verify(path):
    doc = pymupdf.open(path)
    n = len(doc)
    texts = [page.get_text() for page in doc]
    everything = "\n".join(texts)
    per_page = [squares(page) for page in doc]
    instruction_pages = [i for i, t in enumerate(texts) if "ACTUAL SIZE" in t]
    tile_pages = [i for i, t in enumerate(texts) if "Actual size" in t and i not in instruction_pages]

    def has(*words):
        return all(w in everything for w in words)

    real_size = bool(instruction_pages)              # the 1:1 cutting pattern is only there when it was asked for
    checks = {
        "every page is A4": all(abs(p.rect.width - A4_PT[0]) < 0.5 and abs(p.rect.height - A4_PT[1]) < 0.5 for p in doc),
        "pages are numbered 'Page i of n'": all(f"Page {i} of {n}" in t for i, t in enumerate(texts, 1)),
        "confirmed design section": has("Confirmed design"),
        "measurements section": has("Bust", "Waist"),
        "pieces listed with cut quantity, fold and seam allowances": has("Pattern pieces and sewing notes", "On fold", "Seam allowances (cm)"),
        "fabric requirement for 36\" / 45\" / 60\"": has("36 in / 91.44 cm", "45 in / 114.3 cm", "60 in / 152.4 cm"),
        "fabric lengths in metres and yards, areas in m2 and yd2": has(" yd", " m2", " yd2"),
        "front, back and sleeve block overviews (not to scale)": has(
            "FRONT block - measurement overview", "BACK block - measurement overview", "NOT TO SCALE"),
        "calculations listed (Why this size?)": has("Why this size?"),
        "one-page pattern overview at a stated reduced scale": has("Measurement-based pattern overview", "REDUCED SCALE 1:",
                                                                   "Not a cutting template"),
        "layout drawing is marked not to scale": has("NOT to scale"),
    }
    if real_size:
        checks.update({
            "print instruction: 100 % / Actual size, not 'Fit to page'": has("ACTUAL SIZE", "100 %", "Fit to page"),
            "5 cm calibration square on the instruction page": any(per_page[i] for i in instruction_pages),
            "5 cm calibration square on a pattern tile": any(per_page[i] for i in tile_pages),
            "labelled pattern pieces": has("FRONT BODICE", "BACK BODICE", "GRAIN"),
            "cutting instructions (fold / quantity / seam allowance)": has("PLACE ON FOLD", "SA "),
        })
    else:
        checks["no page claims to be real size"] = not tile_pages and "scale 1:1" not in everything
    measured = sorted({s for page in per_page for s in page})
    return {"file": path, "pages": n, "real_size_pages": real_size, "tile_pages": len(tile_pages), "calibration_squares_cm": measured,
            "points_per_cm": round(PT_PER_CM, 4), "checks": checks, "passed": all(checks.values())}


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    report = verify(sys.argv[1])
    print(json.dumps(report, indent=2))
    sys.exit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()
