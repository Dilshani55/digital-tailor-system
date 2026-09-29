#!/usr/bin/env python3
"""
generate_evidence.py - reproducible pattern / nesting / PDF evidence (no database, no server needed).

For representative blouse, T-shirt and crop-top designs (medium measurements) it writes to --out:
  <case>.pdf                  the printable 1:1 tiled PDF (114 cm fabric, best layout)
  <case>_page<N>.png          renders of the first pages (visual inspection)
  evidence.json               validation reports, nesting results for 90/114/150 cm, PDF facts

Usage (from backend/):   python tools/generate_evidence.py --out ../evidence
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.logic.nesting_algorithm import estimate_fabric                       # noqa: E402
from app.logic.parametric_engine import ParametricEngine                      # noqa: E402
from app.logic.pdf_generator import PDFGenerator                              # noqa: E402
from tests.fixtures import measurements                                       # noqa: E402

CASES = [
    ("blouse_round_short_woven", "blouse", "round-neck", "short-sleeve", "regular-sleeve", "woven", {}),
    ("blouse_v_long_woven", "blouse", "v-neck", "long-sleeve", "regular-sleeve", "woven", {}),
    ("tshirt_round_short_knit", "t-shirt", "round-neck", "short-sleeve", "regular-sleeve", "knit", {}),
    ("tshirt_v_long_knit", "t-shirt", "v-neck", "long-sleeve", "regular-sleeve", "knit", {}),
    ("croptop_square_sleeveless_woven", "crop-top", "square-neck", "sleeveless", "none", "woven", {"garment_length_cm": 36}),
    ("croptop_round_short_knit", "crop-top", "round-neck", "short-sleeve", "regular-sleeve", "knit", {"garment_length_cm": 36}),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="../evidence")
    ap.add_argument("--no-render", action="store_true")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    try:
        import pymupdf
    except ImportError:
        pymupdf = None

    report = {}
    for name, garment, neck, sleeve, style, fabric, over in CASES:
        m = measurements("medium", fabric_type=fabric, **over)
        data = ParametricEngine(m, design_spec={"attributes": {
            "garment_type": garment, "neckline_type": neck, "sleeve_length": sleeve, "sleeve_style": style}}).generate()
        val = data["validation"]["final_pattern"]
        nest = {}
        for width in (90, 114, 150):
            r = estimate_fabric(data["pattern_pieces"], width, "auto", fabric)
            nest[str(width)] = {k: r[k] for k in ("cutting_mode", "fabric_length_cm", "exact_yardage_metres",
                                                  "purchasing_recommended_m", "utilisation_percent", "waste_percent",
                                                  "total_pieces")}
            nest[str(width)]["checks"] = r["validation_checks"]["status"]
            nest[str(width)]["mode_comparison"] = r["mode_comparison"]
        pdf_path = os.path.join(args.out, f"{name}.pdf")
        chosen = estimate_fabric(data["pattern_pieces"], 114, "auto", fabric)
        gen = PDFGenerator(data, chosen, m, {}, pdf_path, fabric_name="Cotton Poplin" if fabric == "woven" else "Cotton Jersey Knit",
                           garment_title=f"{garment.title()} sewing pattern")
        gen.generate()
        entry = {
            "design": {"garment": garment, "neckline": neck, "sleeve": sleeve, "fabric": fabric},
            "pieces": [{"name": p["name"], "cut": p["cut_count"], "fold": p["cut_on_fold"],
                        "seam_allowances": p["seam_allowances"], "notches": len(p["notches"]),
                        "cut_area_cm2": p["cut_polygon_area_cm2"], "seam_area_cm2": p["polygon_area_cm2"]}
                       for p in data["pattern_pieces"]],
            "validation": {"passed": val["passed"], "checks": len(val["checks"]), "errors": val["errors"],
                           "armhole_sleeve": val.get("armhole_sleeve")},
            "nesting": nest,
            "pdf": {"file": os.path.basename(pdf_path), "pages": gen.info["pages"], "a4_tiles": gen.info["tiles"],
                    "sheet_cm": gen.info["sheet_cm"], "bytes": os.path.getsize(pdf_path)},
        }
        if pymupdf and not args.no_render:
            doc = pymupdf.open(pdf_path)
            for i in range(min(4, len(doc))):
                doc[i].get_pixmap(dpi=60).save(os.path.join(args.out, f"{name}_page{i + 1}.png"))
        report[name] = entry
        print(f"{name}: validation={'PASS' if val['passed'] else 'FAIL'} ({len(val['checks'])} checks), "
              f"pdf {gen.info['pages']} pages, nesting " +
              ", ".join(f"{w}cm->{nest[w]['fabric_length_cm']}cm/{nest[w]['purchasing_recommended_m']}m/{nest[w]['utilisation_percent']}%" for w in nest))
    with open(os.path.join(args.out, "evidence.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"\nEvidence written to {os.path.abspath(args.out)}")


if __name__ == "__main__":
    main()
