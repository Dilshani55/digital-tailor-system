import unittest

from app.logic.drafting import geometry as g
from app.logic.nesting_algorithm import (
    NestingAlgorithm, NestingError, calculate_shoelace_area, polygons_overlap, STANDARD_FABRIC_WIDTHS,
)
from app.logic.parametric_engine import ParametricEngine
from tests.fixtures import measurements, design


def _pattern(garment="blouse", neck="round-neck", sleeve="short-sleeve", fabric="woven", **over):
    style = "none" if sleeve == "sleeveless" else "regular-sleeve"
    m = measurements("medium", fabric_type=fabric, **over)
    return ParametricEngine(m, design_spec={"attributes": design(garment, neck, sleeve, style)}).generate()["pattern_pieces"]


class TestGeometryHelpers(unittest.TestCase):
    def test_shoelace_area(self):
        self.assertAlmostEqual(calculate_shoelace_area([(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)]), 100.0)
        self.assertAlmostEqual(calculate_shoelace_area([(0, 0), (10, 0), (5, 10), (0, 0)]), 50.0)

    def test_polygon_overlap_exact(self):
        a = [(0, 0), (10, 0), (10, 10), (0, 10)]
        self.assertTrue(polygons_overlap(a, [(5, 5), (15, 5), (15, 15), (5, 15)]))
        self.assertFalse(polygons_overlap(a, [(10, 0), (20, 0), (20, 10), (10, 10)]))       # touching only
        self.assertFalse(polygons_overlap(a, [(11, 0), (20, 0), (20, 10), (11, 10)]))
        self.assertTrue(polygons_overlap(a, [(2, 2), (4, 2), (4, 4), (2, 4)]))               # containment


class TestGeometryAwareNesting(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pieces = _pattern()

    def test_fabric_widths_36_45_60_inch_folded_and_open(self):
        for mode in ("folded", "open"):
            lengths = {}
            for width in STANDARD_FABRIC_WIDTHS:
                res = NestingAlgorithm(self.pieces, fabric_width_cm=width, cutting_mode=mode).run()
                with self.subTest(width=width, mode=mode):
                    self.assertEqual(res["full_bolt_width_cm"], float(width))
                    self.assertEqual(res["usable_width_cm"], width / 2.0 if mode == "folded" else float(width))
                    self.assertEqual(res["validation_checks"]["status"], "PASSED", res["validation_checks"])
                    self.assertGreater(res["fabric_length_cm"], 0)
                    self.assertGreater(res["yardage_metres"], res["exact_yardage_metres"])
                    self.assertTrue(0.0 < res["utilisation_percent"] <= 100.0)
                    self.assertTrue(res["assumptions"])
                lengths[width] = res["fabric_length_cm"]
            self.assertLessEqual(lengths[152.4], lengths[91.44])    # wider cloth never needs more length

    def test_uses_cutting_line_geometry_not_bounding_boxes(self):
        res = NestingAlgorithm(self.pieces, fabric_width_cm=114).run()
        for p in res["placed_pieces"]:
            src = next(s for s in self.pieces if p["name"].startswith(s["name"]))
            self.assertEqual(p["polygon_area_cm2"], round(calculate_shoelace_area([tuple(q) for q in src["cutting_line"]]), 2))
            bb = p["width"] * p["height"]
            self.assertLess(p["polygon_area_cm2"], bb)             # a real polygon, smaller than its box
        # polygon nesting beats the summed bounding boxes of the same pieces
        boxes = sum(p["width"] * p["height"] for p in res["placed_pieces"])
        self.assertLess(res["total_pattern_piece_area_cm2"], boxes * 2)

    def test_fold_grain_and_quantities(self):
        res = NestingAlgorithm(self.pieces, fabric_width_cm=114, cutting_mode="folded").run()
        for p in res["placed_pieces"]:
            self.assertIn(p["rotation_deg"], (0, 180))
            if p["cut_on_fold"]:
                self.assertEqual(p["x"], 0.0)
                self.assertEqual(p["rotation_deg"], 0)
        v = res["validation_checks"]
        self.assertTrue(v["fold_alignment"] and v["grain_preserved"] and v["quantities_satisfied"])
        sleeves = [p for p in res["placed_pieces"] if p["piece_type"] == "sleeve"]
        self.assertEqual(sum(p["pieces_per_placement"] for p in sleeves), 2)

    def test_open_mode_mirrors_fold_pieces_to_full_shape(self):
        res = NestingAlgorithm(self.pieces, fabric_width_cm=150, cutting_mode="open").run()
        front = next(p for p in res["placed_pieces"] if p["piece_type"] == "front_bodice")
        half = next(s for s in self.pieces if s["piece_type"] == "front_bodice")
        self.assertAlmostEqual(front["polygon_area_cm2"], 2 * half["cut_polygon_area_cm2"], delta=0.5)

    def test_pattern_dimensions_invariant_on_fabric_width_change(self):
        areas = []
        for width in STANDARD_FABRIC_WIDTHS:
            res = NestingAlgorithm(self.pieces, fabric_width_cm=width).run()
            areas.append(sorted((p["name"], p["polygon_area_cm2"]) for p in res["placed_pieces"]))
        self.assertEqual(areas[0], areas[1])
        self.assertEqual(areas[1], areas[2])

    def test_mathematical_consistency_and_purchase_allowance(self):
        res = NestingAlgorithm(self.pieces, fabric_width_cm=114).run()
        # fabric_length_cm is reported rounded to 0.01 cm, so 114 x it can differ by up to 114 x 0.005 cm2
        self.assertAlmostEqual(res["usable_area_cm2"], 114 * res["fabric_length_cm"], delta=114 * 0.005 + 0.05)
        self.assertAlmostEqual(res["utilisation_percent"],
                               res["total_pattern_piece_area_cm2"] / res["usable_area_cm2"] * 100, delta=0.1)
        self.assertAlmostEqual(res["waste_percent"], 100 - res["utilisation_percent"], delta=0.11)
        self.assertGreaterEqual(res["purchasing_recommended_m"], res["exact_yardage_metres"] * 1.03)
        self.assertAlmostEqual(res["purchasing_recommended_m"] - res["exact_yardage_metres"],
                               res["handling_allowance_m"], places=2)

    def test_no_placed_polygons_overlap_or_leave_the_cloth(self):
        res = NestingAlgorithm(self.pieces, fabric_width_cm=90).run()
        polys = [p["polygon_coordinates"] for p in res["placed_pieces"]]
        for a in range(len(polys)):
            self.assertLessEqual(g.bbox(polys[a])[2], res["usable_width_cm"] + 0.01)
            for b in range(a + 1, len(polys)):
                self.assertFalse(polygons_overlap(polys[a], polys[b]))

    def test_every_supported_design_nests_on_every_width(self):
        cases = [("t-shirt", "v-neck", "long-sleeve", "knit"), ("crop-top", "square-neck", "sleeveless", "woven"),
                 ("crop-top", "round-neck", "short-sleeve", "knit")]
        for garment, neck, sleeve, fabric in cases:
            over = {"garment_length_cm": 36} if garment == "crop-top" else {}
            pieces = _pattern(garment, neck, sleeve, fabric, **over)
            for width in STANDARD_FABRIC_WIDTHS:
                res = NestingAlgorithm(pieces, fabric_width_cm=width).run()
                self.assertEqual(res["validation_checks"]["status"], "PASSED", (garment, width))

    def test_piece_wider_than_the_cloth_fails_explicitly(self):
        wide = [{"name": "Huge", "piece_type": "x", "cut_count": 1, "cut_on_fold": False,
                 "cutting_line": [(0, 0), (60, 0), (60, 20), (0, 20)]}]
        with self.assertRaises(NestingError) as ctx:
            NestingAlgorithm(wide, fabric_width_cm=90, cutting_mode="folded").run()      # 45 cm usable
        self.assertEqual(ctx.exception.error_code, "PIECE_DOES_NOT_FIT")
        self.assertEqual(ctx.exception.failed_pieces[0]["name"], "Huge")
        NestingAlgorithm(wide, fabric_width_cm=90, cutting_mode="open").run()            # fits when opened out

    def test_invalid_inputs(self):
        with self.assertRaises(NestingError):
            NestingAlgorithm(self.pieces, fabric_width_cm=0)
        with self.assertRaises(NestingError):
            NestingAlgorithm(self.pieces, fabric_width_cm="abc")
        with self.assertRaises(NestingError):
            NestingAlgorithm([], fabric_width_cm=114).run()
        with self.assertRaises(NestingError):
            NestingAlgorithm(self.pieces, cutting_mode="diagonal")

    def test_deterministic(self):
        a = NestingAlgorithm(self.pieces, fabric_width_cm=114).run()
        b = NestingAlgorithm(self.pieces, fabric_width_cm=114).run()
        self.assertEqual(a["placed_pieces"], b["placed_pieces"])


if __name__ == "__main__":
    unittest.main()
