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
        cases = [("t-shirt", "v-neck", "long-sleeve", "knit"), ("blouse", "square-neck", "sleeveless", "woven"),
                 ("blouse", "round-neck", "short-sleeve", "woven")]
        for garment, neck, sleeve, fabric in cases:
            pieces = _pattern(garment, neck, sleeve, fabric)
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


class TestUnitsLengthsAndAreas(unittest.TestCase):
    """Linear lengths and areas are different quantities with their own exact conversions."""

    def test_exact_conversion_factors(self):
        from app.logic import units
        self.assertEqual(units.CM_PER_INCH, 2.54)
        self.assertEqual(units.CM_PER_YARD, 91.44)                       # 1 yd = 36 in
        self.assertEqual(units.IN2_PER_YD2, 1296.0)
        self.assertAlmostEqual(units.CM2_PER_YD2, 8361.2736, places=9)
        self.assertAlmostEqual(units.cm_to_in(2.54), 1.0)
        self.assertAlmostEqual(units.cm_to_yd(91.44), 1.0)
        self.assertAlmostEqual(units.m_to_yd(0.9144), 1.0)
        self.assertAlmostEqual(units.cm2_to_m2(10000.0), 1.0)
        self.assertAlmostEqual(units.cm2_to_yd2(8361.2736), 1.0)
        self.assertAlmostEqual(units.in2_to_yd2(1296.0), 1.0)
        self.assertAlmostEqual(units.cm2_to_in2(6.4516), 1.0)
        self.assertAlmostEqual(units.in_to_cm(units.cm_to_in(37.3)), 37.3, places=12)   # round trip

    def test_a_linear_yard_is_not_a_square_yard(self):
        from app.logic import units
        # 2 yd of 45 in fabric is a rectangle 72 in x 45 in = 3240 in2 = 2.5 yd2, not 2 yd2
        area_cm2 = (2 * units.CM_PER_YARD) * (45 * units.CM_PER_INCH)
        self.assertAlmostEqual(units.cm2_to_yd2(area_cm2), 2.5, places=9)
        self.assertAlmostEqual(units.cm2_to_in2(area_cm2), 3240.0, places=6)

    def test_text_helpers_put_the_selected_unit_first(self):
        from app.logic import units
        self.assertEqual(units.both_lengths(25.4), "25.4 cm (10.0 in)")
        self.assertEqual(units.both_lengths(25.4, "in"), "10.0 in (25.4 cm)")
        self.assertEqual(units.length_text(25.4, "in", 2), "10.00 in")
        self.assertEqual(units.both_lengths(None), "-")


class TestFabricRequirementNumbers(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from app.logic.nesting_algorithm import estimate_fabric
        cls.pieces = _pattern()
        cls.by_width = {w: estimate_fabric(cls.pieces, w) for w in STANDARD_FABRIC_WIDTHS}

    def test_pattern_area_is_the_polygon_area_of_the_pieces_actually_cut(self):
        expected = 0.0
        for p in self.pieces:
            half = calculate_shoelace_area([tuple(q) for q in p["cutting_line"]])
            expected += half * (2 if p["cut_on_fold"] else p["cut_count"])
        for n in self.by_width.values():
            self.assertAlmostEqual(n["total_pattern_piece_area_cm2"], expected, delta=0.2)     # the same on every width
            self.assertAlmostEqual(n["pattern_area_m2"], expected / 10000.0, places=3)
            self.assertAlmostEqual(n["pattern_area_yd2"], expected / 8361.2736, places=3)

    def test_lengths_and_areas_agree_in_both_unit_systems(self):
        for width, n in self.by_width.items():
            self.assertAlmostEqual(n["layout_length_m"], n["fabric_length_cm"] / 100.0, places=2)
            self.assertAlmostEqual(n["layout_length_yd"], n["fabric_length_cm"] / 91.44, places=2)
            self.assertAlmostEqual(n["purchase_length_yd"], n["purchase_length_m"] / 0.9144, places=2)
            self.assertEqual(n["purchase_length_m"], n["purchasing_recommended_m"])
            layout_cm2 = width * n["fabric_length_cm"]
            self.assertAlmostEqual(n["layout_area_m2"], layout_cm2 / 10000.0, places=3)
            self.assertAlmostEqual(n["layout_area_yd2"], layout_cm2 / 8361.2736, places=3)
            self.assertAlmostEqual(n["purchase_area_m2"], width * n["purchase_length_m"] / 100.0, places=3)
            self.assertAlmostEqual(n["waste_area_m2"], n["layout_area_m2"] - n["pattern_area_m2"], places=2)
            self.assertAlmostEqual(n["utilisation_percent"] + n["waste_percent"], 100.0, places=6)
            self.assertAlmostEqual(n["utilisation_percent"], 100.0 * n["pattern_area_m2"] / n["layout_area_m2"], delta=0.2)

    def test_the_layout_is_not_a_bounding_box_or_area_division(self):
        for width, n in self.by_width.items():
            by_area = n["total_pattern_piece_area_cm2"] / width             # "area / width": always too short
            self.assertGreater(n["fabric_length_cm"], by_area)
            boxes = sum(p["bounding_dimensions"]["width_cm"] * p["bounding_dimensions"]["height_cm"] for p in n["placed_pieces"])
            polygons = sum(p["polygon_area_cm2"] for p in n["placed_pieces"])
            self.assertLess(polygons, boxes)                                # real shapes, smaller than their boxes

    def test_every_width_gets_its_own_measured_result(self):
        lengths = {w: n["purchase_length_m"] for w, n in self.by_width.items()}
        waste = {w: n["waste_percent"] for w, n in self.by_width.items()}
        self.assertGreaterEqual(lengths[91.44], lengths[152.4])            # narrower cloth is never shorter here
        self.assertEqual(sorted(waste), sorted(STANDARD_FABRIC_WIDTHS))     # waste is reported per width, not assumed
        self.assertGreater(len(set(waste.values())), 1)

    def test_one_way_fabric_never_turns_a_piece(self):
        from app.logic.nesting_algorithm import estimate_fabric
        for width in STANDARD_FABRIC_WIDTHS:
            free = estimate_fabric(self.pieces, width, "open")
            nap = estimate_fabric(self.pieces, width, "open", one_way=True)
            self.assertTrue(nap["one_way_fabric"])
            self.assertEqual({p["rotation_deg"] for p in nap["placed_pieces"]}, {0})
            self.assertEqual(nap["validation_checks"]["status"], "PASSED")
            self.assertGreaterEqual(nap["fabric_length_cm"], free["fabric_length_cm"] - 1e-6)   # a restriction never helps
            self.assertIn("One-way fabric", " ".join(nap["assumptions"]))

    def test_the_best_of_three_placement_orders_is_kept_and_named(self):
        n = self.by_width[114.3]
        self.assertIn(n["placement_order"], NestingAlgorithm.ORDERS)
        again = NestingAlgorithm(self.pieces, fabric_width_cm=114.3, cutting_mode=n["cutting_mode"]).run()
        self.assertEqual(again["fabric_length_cm"], n["fabric_length_cm"])                     # deterministic
        self.assertEqual(again["placement_order"], n["placement_order"])
        self.assertEqual(n["piece_gap_cm"], 0.5)

    def test_sleeves_are_two_pieces_and_fold_pieces_stay_on_the_fold(self):
        folded = NestingAlgorithm(self.pieces, fabric_width_cm=152.4, cutting_mode="folded").run()
        sleeves = [p for p in folded["placed_pieces"] if p["piece_type"] == "sleeve"]
        self.assertEqual(sum(p["pieces_per_placement"] for p in sleeves), 2)                   # one placement, two layers
        for p in folded["placed_pieces"]:
            if p["cut_on_fold"]:
                self.assertAlmostEqual(p["x"], 0.0, places=6)
                self.assertEqual(p["rotation_deg"], 0)
        opened = NestingAlgorithm(self.pieces, fabric_width_cm=152.4, cutting_mode="open").run()
        self.assertEqual(len([p for p in opened["placed_pieces"] if p["piece_type"] == "sleeve"]), 2)


if __name__ == "__main__":
    unittest.main()
