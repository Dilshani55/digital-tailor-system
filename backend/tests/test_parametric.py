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
        # ease_rules woven bust ease = +10 cm (project assumption): (88 + 10) / 4
        self.assertEqual(engine.quarter_bust, 24.5)
        self.assertEqual(engine.back_neck_to_waist, 40.0)     # measured, not height * constant
        self.assertEqual(engine.armhole_depth, 20.0)

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
        for key in ("neck_cm", "bicep_cm", "across_back_cm"):
            m = dict(self.measurements)
            del m[key]
            with self.assertRaises(DraftingError):
                ParametricEngine(m, self.features).generate()


if __name__ == '__main__':
    unittest.main()
