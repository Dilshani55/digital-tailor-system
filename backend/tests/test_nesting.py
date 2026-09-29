import unittest
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.logic.nesting_algorithm import NestingAlgorithm, Rectangle, calculate_shoelace_area
from app.logic.parametric_engine import ParametricEngine
from tests.fixtures import measurements

class TestNesting(unittest.TestCase):
    def setUp(self):
        self.pattern_pieces = [
            {
                "name": "Back Bodice",
                "cut_count": 1,
                "cut_on_fold": True,
                "seam_allowance_cm": 1.5,
                "bounding_box": {"width_cm": 25.0, "height_cm": 45.0},
                "polygon_area_cm2": 850.0,
                "outline": [(0, 0), (25, 0), (25, 45), (0, 45), (0, 0)]
            },
            {
                "name": "Front Bodice",
                "cut_count": 1,
                "cut_on_fold": True,
                "seam_allowance_cm": 1.5,
                "bounding_box": {"width_cm": 25.0, "height_cm": 45.0},
                "polygon_area_cm2": 870.0,
                "outline": [(0, 0), (25, 0), (25, 45), (0, 45), (0, 0)]
            },
            {
                "name": "Sleeve (short sleeve)",
                "cut_count": 2,
                "cut_on_fold": False,
                "seam_allowance_cm": 1.5,
                "bounding_box": {"width_cm": 20.0, "height_cm": 25.0},
                "polygon_area_cm2": 420.0,
                "outline": [(0, 0), (20, 0), (20, 25), (0, 25), (0, 0)]
            }
        ]

    def test_shoelace_area_calculation(self):
        """Verify mathematical polygon area calculation using Shoelace formula."""
        square = [(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)]
        self.assertAlmostEqual(calculate_shoelace_area(square), 100.0)

        triangle = [(0, 0), (10, 0), (5, 10), (0, 0)]
        self.assertAlmostEqual(calculate_shoelace_area(triangle), 50.0)

    def test_fabric_widths_90_114_150(self):
        """Automated test for 90 cm, 114 cm, and 150 cm fabric widths in folded mode."""
        for width in [90, 114, 150]:
            nester = NestingAlgorithm(self.pattern_pieces, fabric_width_cm=width, cutting_mode="folded")
            res = nester.run()

            self.assertEqual(res["full_bolt_width_cm"], float(width))
            self.assertEqual(res["usable_width_cm"], width / 2.0)
            self.assertEqual(res["cutting_mode"], "folded")
            self.assertTrue(res["fabric_length_cm"] > 0)
            self.assertTrue(res["yardage_metres"] > 0)
            self.assertTrue(0.0 <= res["utilisation_percent"] <= 100.0)

            # Check validation report
            val = res["validation_checks"]
            self.assertTrue(val["no_overlap"])
            self.assertTrue(val["within_bounds"])
            self.assertTrue(val["efficiency_in_range"])
            self.assertTrue(val["theoretical_lower_bound_satisfied"])
            self.assertEqual(val["status"], "PASSED")

    def test_piece_metadata_storage(self):
        """Verify that every pattern piece stores all requested mathematical metadata."""
        nester = NestingAlgorithm(self.pattern_pieces, fabric_width_cm=114, cutting_mode="folded")
        res = nester.run()

        for p in res["placed_pieces"]:
            self.assertIn("cut_quantity", p)
            self.assertIn("cut_on_fold", p)
            self.assertIn("polygon_coordinates", p)
            self.assertIn("seam_allowance_cm", p)
            self.assertIn("bounding_dimensions", p)
            self.assertIn("rotation_deg", p)
            self.assertIn("final_nested_position", p)
            self.assertIn("polygon_area_cm2", p)

    def test_sleeve_quantity_rules(self):
        """A normal short-sleeve design cuts two sleeves."""
        # Standard short sleeve
        engine_std = ParametricEngine(
            measurements("medium"),
            {"garment_type": "blouse", "neckline": "round neck", "sleeves": "short sleeve"}
        )
        pattern_std = engine_std.generate()
        sleeve_std = [p for p in pattern_std["pattern_pieces"] if "Sleeve" in p["name"]][0]
        self.assertEqual(sleeve_std["cut_count"], 2)

        # Single-sleeve / one-shoulder designs are NOT supported (rejected by the engine, not approximated).

    def test_pattern_dimensions_invariant_on_fabric_width_change(self):
        """Verify pattern piece dimensions do not change when only fabric width changes."""
        engine = ParametricEngine(
            measurements("medium"),
            {"garment_type": "blouse", "neckline": "v-neck", "sleeves": "short sleeve"}
        )
        pat_data = engine.generate()

        n90  = NestingAlgorithm(pat_data["pattern_pieces"], fabric_width_cm=90).run()
        n114 = NestingAlgorithm(pat_data["pattern_pieces"], fabric_width_cm=114).run()
        n150 = NestingAlgorithm(pat_data["pattern_pieces"], fabric_width_cm=150).run()

        # Compare piece bounding dimensions across fabric widths
        p90_dims  = [p["bounding_dimensions"] for p in n90["placed_pieces"]]
        p114_dims = [p["bounding_dimensions"] for p in n114["placed_pieces"]]
        p150_dims = [p["bounding_dimensions"] for p in n150["placed_pieces"]]

        self.assertEqual(p90_dims, p114_dims)
        self.assertEqual(p114_dims, p150_dims)

    def test_rectangle_rotation(self):
        """Test rotation capability of rectangle pieces in layout optimization."""
        rect = Rectangle("Test Piece", width=20.0, height=50.0)
        self.assertFalse(rect.rotated)
        rect.rotate()
        self.assertTrue(rect.rotated)
        self.assertEqual(rect.width, 50.0)
        self.assertEqual(rect.height, 20.0)

    def test_mathematical_consistency_and_purchasing_allowance(self):
        """Verify strict mathematical area consistency and purchasing recommendation allowance."""
        nester = NestingAlgorithm(self.pattern_pieces, fabric_width_cm=114, cutting_mode="folded")
        res = nester.run()

        usable_w = res["usable_width_cm"]
        marker_l = res["fabric_length_cm"]
        total_pattern_area = res["total_pattern_piece_area_cm2"]

        expected_usable_area = round(usable_w * marker_l, 1)
        self.assertEqual(res["usable_area_cm2"], expected_usable_area)

        expected_efficiency = round((total_pattern_area / (usable_w * marker_l)) * 100.0, 1)
        self.assertEqual(res["utilisation_percent"], expected_efficiency)

        expected_waste_area = round(expected_usable_area - total_pattern_area, 1)
        self.assertEqual(res["waste_cm2"], expected_waste_area)

        expected_waste_percent = round(100.0 - expected_efficiency, 1)
        self.assertEqual(res["waste_percent"], expected_waste_percent)

        exact_m = round(marker_l / 100.0, 2)
        self.assertGreaterEqual(res["purchasing_recommended_m"], exact_m)
        self.assertAlmostEqual(res["purchasing_recommended_m"] - exact_m, res["handling_allowance_m"], places=2)

if __name__ == '__main__':
    unittest.main()

