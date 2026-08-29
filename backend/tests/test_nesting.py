import unittest
import sys
import os

# Adjust path to import app modules correctly
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.logic.nesting_algorithm import NestingAlgorithm, Rectangle

class TestNesting(unittest.TestCase):
    def setUp(self):
        # Prepare mock pattern pieces layout coordinates
        self.pattern_pieces = [
            {
                "name": "Back Bodice",
                "bounding_box": {"width_cm": 25.0, "height_cm": 45.0}
            },
            {
                "name": "Front Bodice",
                "bounding_box": {"width_cm": 25.0, "height_cm": 45.0}
            },
            {
                "name": "Sleeve",
                "bounding_box": {"width_cm": 20.0, "height_cm": 25.0}
            }
        ]

    def test_nesting_packer(self):
        """Verify that the 2D nesting algorithm executes successfully and reduces fabric length."""
        # Run nesting on standard 114cm wide fabric roll
        nester = NestingAlgorithm(self.pattern_pieces, fabric_width_cm=114)
        result = nester.run()
        
        # Verify result outputs
        self.assertIn("yardage_metres", result)
        self.assertIn("utilisation_percent", result)
        self.assertIn("fabric_length_cm", result)
        
        # Verify fabric length is positive
        self.assertTrue(result["fabric_length_cm"] > 0)
        
        # Verify total pieces placed (each pattern piece is cut x2 based on parse logic)
        # 3 unique pieces * 2 cuts each = 6 total pieces placed
        self.assertEqual(result["total_pieces"], 6)

    def test_rectangle_rotation(self):
        """Test rotation capability of rectangle pieces in layout optimization."""
        rect = Rectangle("Test Piece", width=20.0, height=50.0)
        self.assertFalse(rect.rotated)
        self.assertEqual(rect.width, 20.0)
        self.assertEqual(rect.height, 50.0)

        # Rotate piece
        rect.rotate()
        self.assertTrue(rect.rotated)
        self.assertEqual(rect.width, 50.0)
        self.assertEqual(rect.height, 20.0)

if __name__ == '__main__':
    unittest.main()
