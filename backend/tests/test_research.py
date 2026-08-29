import unittest
import sys
import os

# Adjust path to import app modules correctly
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.models.research_record import ResearchRecord
from app.models.user import User

class TestResearch(unittest.TestCase):
    def test_research_record_attributes(self):
        """Test instantiation and attribute fields of ResearchRecord for survey answers."""
        dummy_user = User(full_name="Dilshani Vitharana", email="dilshani@email.com")
        
        record = ResearchRecord(
            user_id=dummy_user,
            corrections_made={"neckline": True, "sleeves": False},
            correction_rate=20.0,
            ai_confidence_avg=0.92,
            processing_time_sec=0.85,
            pattern_generation_time_sec=0.42,
            baseline_yardage_m=2.5,
            optimized_yardage_m=1.8,
            fabric_savings_m=0.7,
            layout_efficiency=72.0,
            feedback_score=5,
            feedback_comment="Highly accurate layout optimization!"
        )
        
        self.assertEqual(record.user_id.full_name, "Dilshani Vitharana")
        self.assertEqual(record.correction_rate, 20.0)
        self.assertEqual(record.ai_confidence_avg, 0.92)
        self.assertEqual(record.fabric_savings_m, 0.7)
        self.assertEqual(record.feedback_score, 5)
        self.assertEqual(record.feedback_comment, "Highly accurate layout optimization!")

if __name__ == '__main__':
    unittest.main()
