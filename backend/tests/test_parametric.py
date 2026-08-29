import unittest
import sys
import os

# Adjust path to import app modules correctly
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.logic.parametric_engine import ParametricEngine

class TestParametric(unittest.TestCase):
    def setUp(self):
        self.measurements = {
            "bust_cm": 88.0,
            "waist_cm": 70.0,
            "hip_cm": 94.0,
            "height_cm": 162.0,
            "shoulder": 12.0
        }
        self.features = {
            "garment_type": "blouse",
            "neckline": "round neck",
            "sleeves": "short sleeve",
            "darts": "bust dart",
            "seams": "side seam"
        }

    def test_derived_calculations(self):
        """Test derived body dimensions based on Winifred Aldrich formulas."""
        engine = ParametricEngine(self.measurements, self.features)
        
        # Quarter bust calculation (eased bust / 4)
        # For woven fabric, default ease applied is +10cm (defined in ease_rules.py)
        # eased bust = 88.0 + 10 = 98.0
        # quarter bust = 98.0 / 4 = 24.5
        self.assertEqual(engine.quarter_bust, 24.5)
        
        # Height-based back neck to waist height proportion
        # height * 0.2413 = 162 * 0.2413 = 39.09 cm
        self.assertAlmostEqual(engine.back_neck_to_waist, 39.0906, places=4)

    def test_draft_back_bodice_endpoints(self):
        """Verify that back bodice pattern coordinate drafting contains valid values."""
        engine = ParametricEngine(self.measurements, self.features)
        pattern = engine.generate()
        
        # Verify pattern structure
        self.assertEqual(pattern["garment_type"], "blouse")
        self.assertEqual(pattern["fabric_type"], "woven")
        
        pieces = pattern["pattern_pieces"]
        self.assertTrue(len(pieces) >= 2)
        
        # Find back bodice piece
        back_piece = next(p for p in pieces if p["name"] == "Back Bodice")
        self.assertTrue("points" in back_piece)
        self.assertTrue("outline" in back_piece)
        self.assertTrue("bounding_box" in back_piece)
        
        # Verify first construction point A is origin (0, 0)
        self.assertEqual(back_piece["points"]["A"], (0, 0))

if __name__ == '__main__':
    unittest.main()
