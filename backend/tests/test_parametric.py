import unittest
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.logic.parametric_engine import ParametricEngine
from tests.fixtures import measurements


class TestParametric(unittest.TestCase):
    def setUp(self):
        self.measurements = measurements("medium")
        self.features = {"garment_type": "blouse", "neckline": "round neck", "sleeves": "short sleeve",
                         "darts": "bust dart", "seams": "side seam"}

    def test_derived_calculations(self):
        """Quarter bust = (body bust + explicit woven ease) / 4; back waist length is the MEASURED value."""
        engine = ParametricEngine(self.measurements, self.features)
        # regular-fit woven bust ease = 3 1/2 in (the drafting source): (88 + 8.89) / 4
        self.assertAlmostEqual(engine.quarter_bust, (88 + 3.5 * 2.54) / 4)
        self.assertEqual(engine.back_neck_to_waist, 40.0)     # measured, not height * constant
        self.assertAlmostEqual(engine.armhole_depth, 88 / 4 - 2.54)     # the method: a quarter of the bust - 1 in

    def test_pattern_structure_and_geometry_fields(self):
        pattern = ParametricEngine(self.measurements, self.features).generate()
        self.assertEqual(pattern["garment_type"], "blouse")
        self.assertEqual(pattern["fabric_type"], "woven")
        for key in ("base_block", "final_pattern", "pattern_pieces", "validation", "measurements_used"):
            self.assertIn(key, pattern)
        back = next(p for p in pattern["pattern_pieces"] if p["name"] == "Back Bodice")
        for key in ("points", "segments", "outline", "bounding_box", "grain_line", "cut_count", "cut_on_fold"):
            self.assertIn(key, back)
        self.assertEqual(back["points"]["NECK_POINT"][1], 0.0)   # neck/shoulder-point level is y = 0

    def test_every_needed_measurement_is_required(self):
        from app.logic.drafting.ease import DraftingError
        for key in ("shoulder_width_cm", "bicep_cm", "shoulder_to_bust_cm"):
            m = dict(self.measurements)
            del m[key]
            with self.assertRaises(DraftingError):
                ParametricEngine(m, self.features).generate()


if __name__ == '__main__':
    unittest.main()
