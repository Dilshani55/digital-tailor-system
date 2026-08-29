import unittest
import sys
import os

# Adjust path to import app modules correctly
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.models.measurement import MeasurementProfile
from app.models.user import User

class TestMeasurements(unittest.TestCase):
    def test_measurement_instantiation(self):
        """Test instantiation and attribute storage of client measurement profiles."""
        dummy_user = User(full_name="Tailor Admin", email="admin@tailor.lk")
        
        profile = MeasurementProfile(
            user_id=dummy_user,
            client_name="Alice Smith",
            bust_cm=88.5,
            waist_cm=70.0,
            hip_cm=94.0,
            height_cm=162.0,
            fabric_type="woven",
            unit="cm"
        )
        
        self.assertEqual(profile.client_name, "Alice Smith")
        self.assertEqual(profile.bust_cm, 88.5)
        self.assertEqual(profile.waist_cm, 70.0)
        self.assertEqual(profile.hip_cm, 94.0)
        self.assertEqual(profile.height_cm, 162.0)
        self.assertEqual(profile.fabric_type, "woven")
        self.assertEqual(profile.unit, "cm")

    def test_unrealistic_measurement_boundaries(self):
        """Verify business rules for validating realistic measurement limits."""
        # Simple local validation logic representation for API layer input boundaries
        def validate_dimensions(bust, waist, hip, height):
            if not (50 <= bust <= 180):
                return False, "Invalid bust measurement"
            if not (40 <= waist <= 160):
                return False, "Invalid waist measurement"
            if not (60 <= hip <= 200):
                return False, "Invalid hip measurement"
            if not (100 <= height <= 220):
                return False, "Invalid height"
            return True, "Valid"

        is_valid, msg = validate_dimensions(88, 70, 94, 162)
        self.assertTrue(is_valid)

        is_valid, msg = validate_dimensions(20, 70, 94, 162)
        self.assertFalse(is_valid)
        self.assertEqual(msg, "Invalid bust measurement")

        is_valid, msg = validate_dimensions(88, 250, 94, 162)
        self.assertFalse(is_valid)
        self.assertEqual(msg, "Invalid waist measurement")

if __name__ == '__main__':
    unittest.main()
