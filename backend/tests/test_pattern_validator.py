import unittest
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.logic.parametric_engine import ParametricEngine
from app.logic.pattern_validator import validate_pattern


class TestPatternValidator(unittest.TestCase):
    def _base_meas(self):
        return {
            "bust_cm": 88.0,
            "waist_cm": 70.0,
            "hip_cm": 94.0,
            "height_cm": 162.0,
            "fabric_type": "woven",
            "fit_preference": "standard",
            "back_waist_length_cm": 40.0,
            "shoulder_cm": 12.0,
            "across_back_cm": 34.0,
            "armhole_depth_cm": 20.0,
            "garment_length_cm": 60.0,
            "neck_cm": 36.0,
            "bicep_cm": 28.0,
            "sleeve_cm": 22.0,
            "wrist_cm": 16.0,
        }

    def test_blouse_passes(self):
        features = {
            "garment_type": "blouse",
            "neckline": "round neck",
            "sleeves": "short sleeve",
            "darts": "bust dart",
        }
        pattern = ParametricEngine(self._base_meas(), features).generate()
        result = validate_pattern(
            pattern["pattern_pieces"],
            garment_type="blouse",
            fabric_type="woven",
            sleeves="short sleeve",
            measurements_used=pattern["measurements_used"],
            drafting_block=pattern["drafting_block"],
        )
        self.assertTrue(result["passed"])
        self.assertEqual(result["errors"], [])

    def test_missing_pieces_fails(self):
        result = validate_pattern(
            [{"name": "Front Bodice", "outline": [(0, 0), (10, 0), (10, 10), (0, 10)],
              "bounding_box": {"width_cm": 10, "height_cm": 10}}],
            garment_type="blouse",
            fabric_type="woven",
            sleeves="short sleeve",
        )
        self.assertFalse(result["passed"])
        self.assertTrue(any("Missing" in e for e in result["errors"]))


if __name__ == "__main__":
    unittest.main()
