import unittest
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.logic.block_selection import select_drafting_block, WOVEN_BODICE, KNIT_BODICE
from app.logic.taxonomy_map import confirmed_to_cad_features
from app.logic.parametric_engine import ParametricEngine


class TestBlockSelection(unittest.TestCase):
    def test_blouse_woven(self):
        b = select_drafting_block("blouse", "woven")
        self.assertEqual(b["block_id"], WOVEN_BODICE)
        self.assertTrue(b["allow_darts"])

    def test_tshirt_knit(self):
        b = select_drafting_block("t-shirt", "knit")
        self.assertEqual(b["block_id"], KNIT_BODICE)
        self.assertTrue(b["add_neckband"])
        self.assertFalse(b["allow_darts"])

    def test_crop_woven_vs_knit(self):
        woven = select_drafting_block("crop-top", "woven")
        knit = select_drafting_block("crop-top", "knit")
        self.assertEqual(woven["block_id"], WOVEN_BODICE)
        self.assertEqual(knit["block_id"], KNIT_BODICE)
        self.assertTrue(woven["is_crop"])


class TestTaxonomyMap(unittest.TestCase):
    def test_round_neck_maps(self):
        cad = confirmed_to_cad_features({
            "garment_type": "blouse",
            "neckline_type": "round-neck",
            "sleeve_length": "short-sleeve",
            "sleeve_style": "regular-sleeve",
        })
        self.assertEqual(cad["neckline"], "round neck")
        self.assertEqual(cad["sleeves"], "short sleeve")
        self.assertEqual(cad["darts"], "bust dart")


class TestLockedMeasurements(unittest.TestCase):
    def test_uses_back_waist_length(self):
        measurements = {
            "bust_cm": 88.0,
            "waist_cm": 70.0,
            "hip_cm": 94.0,
            "height_cm": 162.0,
            "fabric_type": "woven",
            "fit_preference": "standard",
            "back_waist_length_cm": 41.0,
            "shoulder_cm": 13.0,
            "across_back_cm": 34.0,
            "armhole_depth_cm": 21.0,
            "garment_length_cm": 55.0,
            "neck_cm": 36.0,
            "bicep_cm": 28.0,
            "sleeve_cm": 22.0,
            "wrist_cm": 16.0,
        }
        features = {
            "garment_type": "blouse",
            "neckline": "round neck",
            "sleeves": "short sleeve",
            "darts": "bust dart",
        }
        engine = ParametricEngine(measurements, features)
        self.assertAlmostEqual(engine.back_neck_to_waist, 41.0, places=2)
        self.assertAlmostEqual(engine.armhole_depth, 21.0, places=2)
        self.assertEqual(engine.block["block_id"], WOVEN_BODICE)
        pattern = engine.generate()
        self.assertIn("drafting_block", pattern)
        self.assertTrue(any(p["name"] == "Back Bodice" for p in pattern["pattern_pieces"]))


if __name__ == "__main__":
    unittest.main()
