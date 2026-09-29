import unittest
import sys
import os
import json

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.logic.fabric_recommendation import (
    recommend_fabrics,
    get_all_fabrics,
    get_fabric_by_id,
    validate_fabric_id
)


class TestFabricRecommendation(unittest.TestCase):

    def test_crop_top_recommendations(self):
        """Test structured crop-top design prioritises Cotton Poplin or Linen Blend."""
        recs = recommend_fabrics(garment_type="crop-top", darts="bust dart")
        self.assertTrue(len(recs) >= 4)
        top_match = recs[0]
        self.assertIn(top_match["id"], ["cotton-poplin", "linen-blend"])
        self.assertEqual(top_match["recommendation_status"], "Best Match")
        self.assertIn("structur", top_match["explanation"].lower())

    def test_blouse_recommendations(self):
        """Test flowing blouse design prioritises Rayon or Linen Blend."""
        recs = recommend_fabrics(garment_type="blouse", sleeves="bell sleeve")
        self.assertTrue(len(recs) >= 4)
        top_match = recs[0]
        self.assertIn(top_match["id"], ["rayon", "linen-blend"])
        self.assertEqual(top_match["recommendation_status"], "Best Match")
        self.assertIn("drape", top_match["explanation"].lower())

    def test_tshirt_recommendations(self):
        """Test T-shirt or stretch-fitting top prioritises Cotton Jersey Knit."""
        recs = recommend_fabrics(garment_type="t-shirt", sleeves="short sleeve")
        self.assertTrue(len(recs) >= 4)
        top_match = recs[0]
        self.assertEqual(top_match["id"], "cotton-jersey-knit")
        self.assertEqual(top_match["recommendation_status"], "Best Match")
        self.assertEqual(top_match["stretch"], "Stretchable")

    def test_unknown_garment_type(self):
        """Test unknown garment type handles gracefully without breaking."""
        recs = recommend_fabrics(garment_type="haute-couture-cape", neckline="unknown")
        self.assertTrue(len(recs) >= 4)
        self.assertIn(recs[0]["recommendation_status"], ["Best Match", "Highly Suitable", "Suitable"])

    def test_missing_features(self):
        """Test recommendation engine handles missing/None features."""
        recs = recommend_fabrics(garment_type=None, neckline=None, sleeves=None)
        self.assertTrue(len(recs) >= 4)

    def test_structure_and_stretch_multifeature_rules(self):
        """Verify rules consider physical structure and stretch, not garment type alone."""
        # A blouse with bust darts requires structure
        recs_structured = recommend_fabrics(garment_type="blouse", darts="bust dart")
        # A stretch fitted top requires stretch knit
        recs_stretch = recommend_fabrics(garment_type="stretch-top")
        
        poplin_structured_score = next(r["recommendation_score"] for r in recs_structured if r["id"] == "cotton-poplin")
        poplin_stretch_score = next(r["recommendation_score"] for r in recs_stretch if r["id"] == "cotton-poplin")
        
        self.assertGreater(poplin_structured_score, poplin_stretch_score)

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


class TestFeatureLabelNormalisation(unittest.TestCase):
    """One canonical normalisation path: hyphenated taxonomy labels == spaced CAD labels."""

    def _scores(self, **kw):
        return {f["id"]: f["recommendation_score"] for f in recommend_fabrics(**kw)}

    def test_normalizer(self):
        from app.logic.fabric_recommendation import normalize_feature_label as n
        self.assertEqual(n("sweetheart-neck"), "sweetheart neck")
        self.assertEqual(n("Sweetheart Neck"), "sweetheart neck")
        self.assertEqual(n("t-shirt"), "t shirt")
        self.assertEqual(n("T_Shirt"), "t shirt")
        self.assertEqual(n("off-shoulder"), n("off-the-shoulder"))
        self.assertEqual(n("off-the-shoulder"), "off the shoulder")
        self.assertEqual(n("  boat   neck "), "boat neck")
        self.assertEqual(n(None), "")

    def test_hyphenated_and_spaced_necklines_score_identically(self):
        for hyphen, spaced in (("sweetheart-neck", "sweetheart neck"), ("boat-neck", "boat neck"),
                               ("halter-neck", "halter neck"), ("off-shoulder", "off-the-shoulder")):
            self.assertEqual(self._scores(garment_type="blouse", neckline=hyphen),
                             self._scores(garment_type="blouse", neckline=spaced), hyphen)

    def test_party_neckline_bonus_now_applies_to_taxonomy_labels(self):
        """Regression: 'sweetheart-neck' never matched the rule, so the satin bonus was silently lost."""
        plain = self._scores(garment_type="blouse", neckline="round-neck")
        party = self._scores(garment_type="blouse", neckline="sweetheart-neck")
        self.assertTrue(any(party[k] > plain[k] for k in plain))           # some fabric gains (others are capped at 98)
        self.assertTrue(all(party[k] >= plain[k] for k in plain))
        crop_plain = self._scores(garment_type="crop-top", neckline="round-neck")
        crop_party = self._scores(garment_type="crop-top", neckline="halter-neck")
        self.assertGreater(crop_party["satin"], crop_plain["satin"])

    def test_garment_and_sleeve_labels_normalise_too(self):
        self.assertEqual(self._scores(garment_type="t-shirt"), self._scores(garment_type="T Shirt"))
        jersey = self._scores(garment_type="t-shirt")["cotton-jersey-knit"]
        poplin = self._scores(garment_type="t-shirt")["cotton-poplin"]
        self.assertGreater(jersey, poplin)                                  # stretch requirement still applies
        crop = self._scores(garment_type="crop-top")
        self.assertGreater(crop["cotton-poplin"], crop["silk-chiffon"])      # structure requirement still applies
        self.assertEqual(self._scores(garment_type="blouse", sleeves="bell-sleeve"),
                         self._scores(garment_type="blouse", sleeves="bell sleeve"))
        self.assertEqual(self._scores(garment_type="crop-top", sleeves="sleeveless"),
                         self._scores(garment_type="crop-top", sleeves="Sleeveless"))

    def test_explanations_keep_readable_garment_names(self):
        rec = recommend_fabrics(garment_type="t-shirt")
        jersey = next(f for f in rec if f["id"] == "cotton-jersey-knit")
        self.assertIn("t-shirt", jersey["explanation"])


if __name__ == "__main__":
    unittest.main()
