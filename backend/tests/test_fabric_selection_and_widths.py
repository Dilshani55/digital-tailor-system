"""Design-aware rule-based fabric recommendation, and fabric requirement at 36" / 45" / 60"."""
import copy
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from flask_jwt_extended import create_access_token

from app import create_app
from app.logic.fabric_selection import recommend_for_design, TRAITS
from app.logic.nesting_algorithm import estimate_fabric, STANDARD_FABRIC_WIDTHS
from app.logic.parametric_engine import ParametricEngine
from tests.fixtures import measurements, design


def D(garment="blouse", neck="round-neck", length="short-sleeve", style="regular-sleeve"):
    return {"garment_type": garment, "neckline_type": neck, "sleeve_length": length, "sleeve_style": style}


class TestRecommendation(unittest.TestCase):
    def test_tshirt_only_knit_blouse_only_woven(self):
        for garment, allowed in (("t-shirt", {"knit"}), ("blouse", {"woven"})):
            r = recommend_for_design(D(garment=garment))
            got = {f["construction"] for f in r["fabrics"] if f["compatible"]}
            self.assertEqual(got, allowed, garment)
            for f in r["fabrics"]:
                if not f["compatible"]:
                    self.assertTrue(f["incompatible_reason"])
                    self.assertFalse(f["recommended"])
                    self.assertIsNone(f["recommendation_score"])

    def test_two_to_four_compatible_fabrics_are_recommended_and_listed_first(self):
        for d in (D(), D(style="puff-sleeve"), D(length="long-sleeve", style="bell-sleeve"), D(garment="t-shirt"),
                  D(length="sleeveless", style="none")):
            r = recommend_for_design(d)
            rec = [f for f in r["fabrics"] if f["recommended"]]
            self.assertTrue(2 <= len(rec) <= 4, (d, len(rec)))
            self.assertEqual([f["id"] for f in r["fabrics"][:len(rec)]], r["recommended_ids"])
            self.assertTrue(all(f["compatible"] for f in rec))

    def test_sleeve_style_drives_the_choice(self):
        puff = recommend_for_design(D(style="puff-sleeve"))["recommended_ids"]
        bell = recommend_for_design(D(length="long-sleeve", style="bell-sleeve"))["recommended_ids"]
        self.assertTrue(all(TRAITS[f][1] <= 3 for f in puff), puff)     # crisp fabrics hold gathers
        self.assertTrue(all(TRAITS[f][1] >= 4 for f in bell), bell)     # fluid fabrics for a flare
        self.assertNotIn("silk-chiffon", puff)

    def test_sheer_fabric_carries_a_lining_warning_and_every_score_is_explained(self):
        r = recommend_for_design(D())
        chiffon = next(f for f in r["fabrics"] if f["id"] == "silk-chiffon")
        self.assertTrue(any("lining" in w for w in chiffon["warnings"]))
        for f in r["fabrics"]:
            if f["compatible"]:
                self.assertEqual(f["recommendation_score"], 60 + sum(x["delta"] for x in f["score_reasons"]))
            for banned in ("price", "stock", "availability", "sustainability"):
                self.assertNotIn(banned, f)
        self.assertIn("not machine-learned", r["method"])

    def test_route_uses_the_confirmed_design(self):
        app = create_app()
        app.config["TESTING"] = True
        c = app.test_client()
        r = c.post("/api/fabric/recommend", json={"confirmed_attributes": D(garment="t-shirt"), "fit_preference": "standard"})
        body = r.get_json()
        self.assertEqual(r.status_code, 200)
        self.assertEqual({f["construction"] for f in body["recommendations"] if f["recommended"]}, {"knit"})
        bad = c.post("/api/fabric/recommend", json={"confirmed_attributes": D(garment="dress")})
        self.assertEqual(bad.status_code, 400)

    def test_catalogue_lists_every_fabric_with_its_construction_and_no_recommendation(self):
        """Used by the fabric step before a design is confirmed: a plain list, nothing ranked or invented."""
        app = create_app()
        app.config["TESTING"] = True
        body = app.test_client().get("/api/fabric/catalog").get_json()
        self.assertEqual(body["total"], 10)
        self.assertEqual({f["construction"] for f in body["fabrics"]}, {"woven", "knit"})
        by_id = {f["id"]: f for f in body["fabrics"]}
        self.assertEqual(by_id["cotton-jersey-knit"]["construction"], "knit")
        self.assertEqual(by_id["cotton-poplin"]["construction"], "woven")
        for f in body["fabrics"]:
            for absent in ("recommended", "recommendation_score", "price", "stock"):
                self.assertNotIn(absent, f)


def _pieces(style="regular-sleeve", length="short-sleeve"):
    return ParametricEngine(measurements("medium"), design_spec={"attributes": design("blouse", "round-neck", length, style)}).generate()["pattern_pieces"]


class TestStandardWidthEstimates(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config["TESTING"] = True
        with cls.app.app_context():
            cls.h = {"Authorization": f"Bearer {create_access_token(identity='u1')}"}
        cls.pieces = _pieces()

    def _pattern(self, pieces=None, owner="u1", valid=True):
        return SimpleNamespace(id="p1", session_id=SimpleNamespace(user_id=SimpleNamespace(id=owner)),
                               pattern_coordinates=pieces or self.pieces, validation_passed=valid,
                               measurements_snapshot={"fabric_type": "woven"}, nesting_summary={}, width_estimates=[],
                               yardage_metres=0.0, save=MagicMock())

    def _post(self, pattern, body=None):
        with patch("app.routes.export.PatternResult") as P:
            P.objects.return_value.first.return_value = pattern
            return self.app.test_client().post("/api/export/estimates/p1", json=body or {}, headers=self.h)

    def test_three_standard_widths_with_real_values(self):
        self.assertEqual(STANDARD_FABRIC_WIDTHS, (91.44, 114.3, 152.4))
        pat = self._pattern()
        r = self._post(pat)
        body = r.get_json()
        self.assertEqual(r.status_code, 200, body)
        self.assertEqual([(e["fabric_width_in"], e["fabric_width_cm"]) for e in body["estimates"]],
                         [(36, 91.44), (45, 114.3), (60, 152.4)])
        for e in body["estimates"]:
            ref = estimate_fabric(self.pieces, e["fabric_width_cm"], "auto", "woven")
            self.assertTrue(e["fits"])
            self.assertEqual(e["base_layout_length_cm"], ref["fabric_length_cm"])
            self.assertEqual(e["recommended_purchase_m"], ref["purchasing_recommended_m"])
            self.assertAlmostEqual(e["purchasing_allowance_cm"], ref["purchasing_recommended_m"] * 100 - ref["fabric_length_cm"], 1)
            self.assertEqual(e["utilisation_percent"], ref["utilisation_percent"])
            self.assertEqual(e["validation_checks"]["status"], "PASSED")
        best = min(body["estimates"], key=lambda e: e["recommended_purchase_m"])
        self.assertEqual(body["selected_width_cm"], best["fabric_width_cm"])
        self.assertEqual(len(pat.width_estimates), 3)
        self.assertNotIn("placed_pieces", pat.width_estimates[0])          # layouts not duplicated in the record
        self.assertEqual(pat.nesting_summary["fabric_width_cm"], best["fabric_width_cm"])

    def test_selected_width_is_saved_and_pieces_are_unchanged(self):
        before = copy.deepcopy(self.pieces)
        pat = self._pattern()
        body = self._post(pat, {"selected_width_cm": 91.44}).get_json()
        self.assertEqual(body["selected_width_cm"], 91.44)
        self.assertEqual([e["selected"] for e in body["estimates"]], [True, False, False])
        self.assertEqual(pat.nesting_summary["fabric_width_cm"], 91.44)
        self.assertEqual(self.pieces, before)

    def test_a_width_where_a_piece_cannot_fit_is_reported_not_estimated(self):
        wide = copy.deepcopy(self.pieces)
        sleeve = next(p for p in wide if p["piece_type"] == "sleeve")
        sleeve["cutting_line"] = [[x * 3.6, y] for x, y in sleeve["cutting_line"]]   # ~130 cm wide sleeve
        sleeve["cut_bounding_box"]["width_cm"] *= 3.6
        body = self._post(self._pattern(pieces=wide)).get_json()
        fits = {e["fabric_width_in"]: e["fits"] for e in body["estimates"]}
        self.assertEqual(fits, {36: False, 45: False, 60: True})
        narrow = body["estimates"][0]
        self.assertEqual(narrow["error_code"], "PIECE_DOES_NOT_FIT")
        self.assertNotIn("recommended_purchase_m", narrow)
        self.assertEqual(body["selected_width_cm"], 152.4)

    def test_failed_validation_ownership_and_bad_width(self):
        r = self._post(self._pattern(valid=False))
        self.assertEqual(r.status_code, 422)
        self.assertEqual(r.get_json()["error"], "Pattern validation failed. Fabric estimation and PDF export are "
                                                "unavailable until the pattern is corrected.")
        self.assertEqual(self._post(self._pattern(owner="someone-else")).status_code, 403)
        self.assertEqual(self._post(self._pattern(), {"selected_width_cm": 150}).status_code, 400)


if __name__ == "__main__":
    unittest.main()
