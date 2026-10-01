"""Puff and bell sleeve transformations: real geometry, validated, nestable at 36" / 45" / 60"."""
import math
import unittest

from app.logic import feature_schema as fs
from app.logic.drafting.assumptions import A
from app.logic.nesting_algorithm import estimate_fabric
from app.logic.parametric_engine import ParametricEngine
from tests.fixtures import measurements, design, SHORT_SLEEVE_CM

WIDTHS_CM = (91.44, 114.3, 152.4)       # 36, 45 and 60 inches


def _gen(garment, length, style, size="medium", fabric="woven", neck="round-neck"):
    over = {}
    if length == "short-sleeve":
        over["sleeve_cm"] = SHORT_SLEEVE_CM[size]           # the wanted short-sleeve length, not a full arm
    return ParametricEngine(measurements(size, fabric_type=fabric, **over),
                            design_spec={"attributes": design(garment, neck, length, style)}).generate()


def _piece(result, ptype):
    return next(p for p in result["pattern_pieces"] if p["piece_type"] == ptype)


class TestPuffSleeve(unittest.TestCase):
    def test_short_puff_is_wider_gathered_and_has_a_band(self):
        plain = _piece(_gen("blouse", "short-sleeve", "regular-sleeve"), "sleeve")
        r = _gen("blouse", "short-sleeve", "puff-sleeve")
        puff = _piece(r, "sleeve")
        m = puff["measurements"]
        self.assertAlmostEqual(m["width_bicep_cm"], plain["measurements"]["width_bicep_cm"] * (1 + A["puff_spread_fraction"]), 3)
        self.assertAlmostEqual(m["cap_height_cm"], plain["measurements"]["cap_height_cm"] + A["puff_crown_rise_cm"], 3)
        self.assertEqual(m["width_hem_cm"], m["width_bicep_cm"])                 # straight sides, gathered into band
        lo, hi = A["puff_gather_excess_range_cm"]
        self.assertTrue(lo <= r["armhole_sleeve"]["cap_ease_cm"] <= hi, r["armhole_sleeve"])
        band = _piece(r, "sleeve_band")
        self.assertEqual(band["cut_count"], 2)
        self.assertAlmostEqual(band["bounding_box"]["width_cm"], plain["measurements"]["width_bicep_cm"], 2)
        checks = r["validation"]["final_pattern"]["checks"]
        self.assertTrue(checks["puff cap flat below notches"]["ok"], checks["puff cap flat below notches"])
        self.assertTrue(checks["puff cap gathering vs armhole"]["ok"])
        t = next(t for t in r["final_pattern"]["transformations"] if t["id"] == "sleeve_style")
        self.assertEqual(t["type"], "puff_slash_and_spread")

    def test_long_puff_tapers_to_the_wrist_without_a_band(self):
        plain = _piece(_gen("blouse", "long-sleeve", "regular-sleeve"), "sleeve")
        r = _gen("blouse", "long-sleeve", "puff-sleeve")
        puff = _piece(r, "sleeve")
        self.assertAlmostEqual(puff["measurements"]["width_hem_cm"], plain["measurements"]["width_hem_cm"], 3)
        self.assertNotIn("sleeve_band", [p["piece_type"] for p in r["pattern_pieces"]])
        # the underarm-to-hem length of the plain sleeve is kept
        self.assertAlmostEqual(puff["measurements"]["length_cm"] - puff["measurements"]["cap_height_cm"],
                               plain["measurements"]["length_cm"] - plain["measurements"]["cap_height_cm"], 3)


class TestBellSleeve(unittest.TestCase):
    def test_bell_keeps_the_fitted_cap_and_flares_to_a_curved_hem(self):
        for length in ("short-sleeve", "long-sleeve"):
            plain_r = _gen("blouse", length, "regular-sleeve")
            r = _gen("blouse", length, "bell-sleeve")
            bell = _piece(r, "sleeve")
            m = bell["measurements"]
            self.assertAlmostEqual(r["armhole_sleeve"]["cap_ease_cm"], plain_r["armhole_sleeve"]["cap_ease_cm"], 3)
            self.assertAlmostEqual(m["width_hem_cm"], m["width_bicep_cm"] * (1 + A["bell_flare_fraction"][length]), 3)
            hem = next(s for s in bell["segments"] if s["id"] == "hem")
            self.assertEqual(hem["type"], "cubic")
            p0, p1, p2, p3 = hem["p"]
            seam_r = next(s for s in bell["segments"] if s["id"] == "underarm_right")["p"]
            seam_dir = (seam_r[1][0] - seam_r[0][0], seam_r[1][1] - seam_r[0][1])
            tangent = (p1[0] - p0[0], p1[1] - p0[1])
            cos = (seam_dir[0] * tangent[0] + seam_dir[1] * tangent[1]) / (math.hypot(*seam_dir) * math.hypot(*tangent))
            self.assertAlmostEqual(cos, 0.0, 4)                              # hem meets the seam at 90 degrees
            self.assertGreater(bell["points"]["HEM_CENTRE"][1], bell["points"]["HEM_LEFT"][1])   # curved, longer at centre
            xs = [q[0] for q in bell["cutting_line"]]
            self.assertTrue(r["validation"]["final_pattern"]["passed"])
            self.assertTrue(r["validation"]["final_pattern"]["checks"]["bell sleeve flares"]["ok"])
            self.assertGreaterEqual(min(q[0] for q in bell["outline"]), -1e-9)
            self.assertGreater(max(xs) - min(xs), m["width_hem_cm"])         # seam allowance outside the hem width


class TestAllDraftableCombinations(unittest.TestCase):
    def test_every_scope_combination_drafts_and_validates_for_three_body_sizes(self):
        count = 0
        for garment, d in fs.SCOPE.items():
            fabrics = {"blouse": ("woven",), "t-shirt": ("knit",)}[garment]
            for length, styles in d["sleeves"].items():
                for style in styles:
                    for neck in d["neckline_type"]:
                        for size in ("small", "medium", "large"):
                            for fabric in fabrics:
                                r = _gen(garment, length, style, size, fabric, neck)
                                self.assertTrue(r["validation"]["final_pattern"]["passed"], (garment, length, style, neck, size))
                                count += 1
        self.assertEqual(count, 25 * 3)            # every draftable combination x three body sizes


class TestNestingAtStandardWidths(unittest.TestCase):
    def test_puff_and_bell_patterns_fit_36_45_60_inch_fabric_without_changing_the_pieces(self):
        for style in ("puff-sleeve", "bell-sleeve"):
            r = _gen("blouse", "long-sleeve", style, "large")
            before = [(p["name"], p["cut_bounding_box"]) for p in r["pattern_pieces"]]
            lengths = []
            for w in WIDTHS_CM:
                n = estimate_fabric(r["pattern_pieces"], w, "auto", "woven")
                self.assertEqual(n["validation_checks"]["status"], "PASSED", (style, w))
                lengths.append(n["fabric_length_cm"])
            self.assertEqual(before, [(p["name"], p["cut_bounding_box"]) for p in r["pattern_pieces"]])
            self.assertGreaterEqual(lengths[0], lengths[2])                  # wider cloth never needs more length


if __name__ == "__main__":
    unittest.main()
