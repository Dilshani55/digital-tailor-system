"""Catalogue integrity and removal of the unsupported legacy point-scoring API."""
import unittest
from app import create_app
from app.logic.fabric_recommendation import get_all_fabrics, get_fabric_by_id, validate_fabric_id


class TestFabricRecommendation(unittest.TestCase):
    def test_legacy_requests_cannot_bypass_confirmed_design_and_data_requirements(self):
        app = create_app()
        app.config["TESTING"] = True
        for payload in ({}, {"garment_type": "t-shirt"}, {"garment_type": "crop-top", "darts": "bust dart"}, []):
            with self.subTest(payload=payload):
                response = app.test_client().post("/api/fabric/recommend", json=payload)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.get_json()["error_code"], "CONFIRMED_DESIGN_REQUIRED")

    def test_fabric_id_validation_and_canonical_name(self):
        """Test backend fabric ID validation and canonical name derivation."""
        self.assertTrue(validate_fabric_id("cotton-poplin"))
        self.assertTrue(validate_fabric_id("RAYON"))
        self.assertFalse(validate_fabric_id("invalid-fabric-xyz"))

        fab = get_fabric_by_id("linen-blend")
        self.assertIsNotNone(fab)
        self.assertEqual(fab["name"], "Linen Blend")

    def test_all_fabrics_contain_required_fields(self):
        """Verify all fabrics in knowledge base contain required specification fields."""
        fabrics = get_all_fabrics()
        self.assertEqual(len(fabrics), 10, "Knowledge base should contain 10 real-world tailoring materials")
        required_keys = [
            "id", "name", "local_image", "simple_description", "feel", "weight",
            "stretch", "breathability", "drape", "best_garment_uses",
            "climate_suitability", "advantages", "limitations", "care_instructions",
            "sewing_difficulty", "technical_details", "recommendation_rules",
            "reference_source", "image_license"
        ]
        for fab in fabrics:
            for key in required_keys:
                self.assertIn(key, fab, f"Fabric '{fab.get('id')}' missing key '{key}'")
            tech = fab["technical_details"]
            self.assertIn("construction", tech)
            self.assertIn("typical_gsm_range", tech)
            self.assertIn("price_note", tech)
            self.assertEqual(tech["price_note"], "Price varies by supplier")

class TestNoInventedCitations(unittest.TestCase):
    def test_no_invented_citations(self):
        from app.logic.fabric_recommendation import FABRIC_KNOWLEDGE_BASE
        for fid, fab in FABRIC_KNOWLEDGE_BASE.items():
            self.assertNotIn("Aldrich", fab["reference_source"], fid)
            self.assertNotIn("Handbook", fab["reference_source"], fid)
