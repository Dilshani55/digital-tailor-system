"""
Evaluation instrument: traditional (e.g. tailor) fabric estimate vs the system's estimate.
The system value must come from the real nesting code for the same width/mode; nothing is invented.
Also covers the hardened /research/feedback endpoint.
"""
import csv
import io
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from bson import ObjectId
from flask_jwt_extended import create_access_token

from app import create_app
from app.logic.nesting_algorithm import estimate_fabric
from app.logic.parametric_engine import ParametricEngine
from app.logic.research_metrics import summarize_fabric_comparisons
from app.models.fabric_comparison import FabricComparison
from app.routes import research as rr
from tests.fixtures import measurements, design

PIECES = ParametricEngine(
    measurements("medium", fabric_type="woven"),
    design_spec={"attributes": design("blouse", "round-neck", "short-sleeve", "regular-sleeve")},
).generate()["pattern_pieces"]


def _pattern(owner="u1", valid=True):
    return SimpleNamespace(
        id=ObjectId(), session_id=SimpleNamespace(user_id=SimpleNamespace(id=owner)),
        pattern_coordinates=PIECES, validation_passed=valid, garment_type="blouse",
        measurements_snapshot={"fabric_type": "woven"}, save=MagicMock(),
    )


class TestSummary(unittest.TestCase):
    def test_no_entries_means_not_measured(self):
        self.assertIsNone(summarize_fabric_comparisons([]))

    def test_descriptive_statistics_from_entered_values_only(self):
        rows = [
            {"traditional_m": 2.0, "system_m": 1.5, "source": "tailor", "pattern_id": "a"},
            {"traditional_m": 1.5, "system_m": 1.5, "source": "tailor", "pattern_id": "a"},
            {"traditional_m": 1.0, "system_m": 1.2, "source": "shop_rule_of_thumb", "pattern_id": "b"},
        ]
        s = summarize_fabric_comparisons(rows)
        self.assertEqual(s["n"], 3)
        self.assertEqual(s["patterns"], 2)
        self.assertAlmostEqual(s["mean_difference_m"], 0.1)          # (0.5 + 0 - 0.2) / 3
        self.assertAlmostEqual(s["median_difference_m"], 0.0)
        self.assertAlmostEqual(s["mean_relative_difference_percent"], round((25 + 0 - 20) / 3, 1))
        self.assertEqual((s["system_lower_count"], s["system_higher_count"], s["equal_count"]), (1, 1, 1))
        self.assertEqual(s["by_source"], {"tailor": 2, "shop_rule_of_thumb": 1})
        self.assertIsNotNone(s["sd_difference_m"])

    def test_single_entry_has_no_standard_deviation(self):
        s = summarize_fabric_comparisons([{"traditional_m": 2.0, "system_m": 1.5, "source": "tailor", "pattern_id": "a"}])
        self.assertIsNone(s["sd_difference_m"])

    def test_model_derives_difference_from_the_two_stored_numbers(self):
        c = FabricComparison(traditional_estimate_m=2.0, system_purchase_m=1.4)
        self.assertEqual(c.difference_m, 0.6)
        self.assertEqual(c.relative_difference_percent, 30.0)


class TestComparisonRoutes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config["TESTING"] = True
        with cls.app.app_context():
            cls.h = {"Authorization": f"Bearer {create_access_token(identity='u1')}"}

    def _post(self, body, pattern=None):
        pattern = pattern or _pattern()
        with patch.object(rr, "User") as U, patch.object(rr, "PatternResult") as P, \
                patch.object(FabricComparison, "save", autospec=True) as save:
            U.objects.return_value.first.return_value = MagicMock()
            P.objects.return_value.first.return_value = pattern
            body = {"pattern_id": str(pattern.id), **body}
            r = self.app.test_client().post("/api/research/fabric-comparisons", json=body, headers=self.h)
        return r, pattern, save

    def test_system_value_is_the_real_nesting_result_for_the_same_width(self):
        # _comparison_json needs c.pattern_id.id; the unsaved document keeps the pattern object
        r, pattern, save = self._post({"fabric_width_cm": 114.3, "cutting_mode": "auto",
                                       "traditional_estimate_m": 2.5, "estimate_source": "tailor",
                                       "estimator_label": "Tailor A"})
        self.assertEqual(r.status_code, 201, r.get_json())
        expected = estimate_fabric(PIECES, 114.3, "auto", "woven")
        body = r.get_json()
        self.assertEqual(body["system_purchase_m"], expected["purchasing_recommended_m"])
        self.assertEqual(body["system_layout_length_cm"], expected["fabric_length_cm"])
        self.assertEqual(body["traditional_estimate_m"], 2.5)
        self.assertAlmostEqual(body["difference_m"], round(2.5 - expected["purchasing_recommended_m"], 3))
        self.assertEqual(body["estimator_label"], "Tailor A")
        save.assert_called_once()
        pattern.save.assert_not_called()              # the stored pattern / estimate is not changed

    def test_invalid_inputs_are_rejected_and_nothing_is_saved(self):
        base = {"fabric_width_cm": 114.3, "traditional_estimate_m": 2.0, "estimate_source": "tailor"}
        bad = [
            {"fabric_width_cm": 100},                 # not a supported width
            {"fabric_width_cm": True},
            {"traditional_estimate_m": 0},
            {"traditional_estimate_m": "2"},
            {"traditional_estimate_m": 50},
            {"estimate_source": "guess"},
            {"cutting_mode": "diagonal"},
            {"estimator_label": "x" * 41},
        ]
        for override in bad:
            r, _, save = self._post({**base, **override})
            self.assertEqual(r.status_code, 400, override)
            save.assert_not_called()

    def test_another_users_pattern_is_forbidden(self):
        r, _, save = self._post({"fabric_width_cm": 114.3, "traditional_estimate_m": 2.0, "estimate_source": "tailor"},
                                pattern=_pattern(owner="someone-else"))
        self.assertEqual(r.status_code, 403)
        save.assert_not_called()

    def test_a_pattern_that_failed_validation_cannot_be_compared(self):
        r, _, save = self._post({"fabric_width_cm": 114.3, "traditional_estimate_m": 2.0, "estimate_source": "tailor"},
                                pattern=_pattern(valid=False))
        self.assertEqual(r.status_code, 422)
        self.assertEqual(r.get_json()["error_code"], "PATTERN_NOT_VALID")
        save.assert_not_called()

    def test_requires_login(self):
        self.assertEqual(self.app.test_client().post("/api/research/fabric-comparisons", json={}).status_code, 401)

    def test_metrics_include_the_summary_for_researchers(self):
        comps = [SimpleNamespace(traditional_estimate_m=2.0, system_purchase_m=1.5, estimate_source="tailor",
                                 _data={"pattern_id": ObjectId()})]
        with patch.object(rr, "_is_researcher", return_value=True), \
                patch.object(rr, "ResearchRecord") as R, patch.object(rr, "FabricComparison") as F, \
                patch.object(rr, "load_model_evaluation", return_value={"available": False}):
            R.objects.all.return_value = []
            F.objects.all.return_value = comps
            body = self.app.test_client().get("/api/research/metrics", headers=self.h).get_json()
        self.assertTrue(body["available"])
        self.assertEqual(body["fabric_comparison"]["n"], 1)
        self.assertEqual(body["fabric_comparison"]["mean_difference_m"], 0.5)
        self.assertIsNone(body["avg_fabric_savings"])          # still no single "saving" claim

    def test_metrics_report_not_measured_when_nobody_entered_a_comparison(self):
        with patch.object(rr, "_is_researcher", return_value=True), \
                patch.object(rr, "ResearchRecord") as R, patch.object(rr, "FabricComparison") as F, \
                patch.object(rr, "load_model_evaluation", return_value={"available": True, "per_head": {}}):
            R.objects.all.return_value = []
            F.objects.all.return_value = []
            body = self.app.test_client().get("/api/research/metrics", headers=self.h).get_json()
        self.assertIsNone(body["fabric_comparison"])

    def test_comparison_csv_is_researcher_only_and_pseudonymised(self):
        self.app.config["RESEARCHER_EMAILS"] = ""
        r = self.app.test_client().get("/api/research/export/fabric-comparisons.csv", headers=self.h)
        self.assertEqual(r.status_code, 403)
        user = SimpleNamespace(id="user-object-id", email="real.person@example.com")
        c = FabricComparison(fabric_width_cm=114.0, cutting_mode="auto", system_cutting_mode="folded",
                             system_purchase_m=1.4, system_layout_length_cm=120.0, system_utilisation_percent=41.0,
                             traditional_estimate_m=2.0, estimate_source="tailor", estimator_label="Tailor A")
        c._data["user_id"] = user
        c._data["pattern_id"] = SimpleNamespace(id="p1", garment_type="blouse")
        c._data["created_at"] = __import__("datetime").datetime(2026, 9, 30, 10, 0)
        with patch.object(rr, "_is_researcher", return_value=True), patch.object(rr, "FabricComparison") as F:
            F.objects.all.return_value.order_by.return_value = [c]
            r = self.app.test_client().get("/api/research/export/fabric-comparisons.csv", headers=self.h)
        self.assertEqual(r.status_code, 200)
        rows = list(csv.reader(io.StringIO(r.get_data(as_text=True))))
        self.assertEqual(rows[1][1], rr._pseudonym(user))
        self.assertNotIn("real.person", r.get_data(as_text=True))
        self.assertEqual(rows[1][10], "2.0")
        self.assertEqual(rows[1][13], "0.6")


class TestFeedbackHardening(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config["TESTING"] = True
        with cls.app.app_context():
            cls.h = {"Authorization": f"Bearer {create_access_token(identity='u1')}"}

    def _post(self, body, owner="u1"):
        with patch.object(rr, "User") as U, patch.object(rr, "PatternResult") as P, \
                patch.object(rr, "ResearchRecord") as R:
            U.objects.return_value.first.return_value = MagicMock()
            P.objects.return_value.first.return_value = _pattern(owner=owner)
            r = self.app.test_client().post("/api/research/feedback", json={"pattern_id": "p", **body}, headers=self.h)
        return r, R

    def test_feedback_on_someone_elses_pattern_is_forbidden(self):
        r, R = self._post({"feedback_score": 5}, owner="other-user")
        self.assertEqual(r.status_code, 403)
        R.assert_not_called()

    def test_valid_feedback_records_the_measured_times_and_nothing_invented(self):
        pattern = _pattern()
        pattern.generation_time_sec = 0.1234
        pattern.yardage_metres = 1.4
        pattern.nesting_summary = {"utilisation_percent": 41.0}
        pattern.session_id.image_id = SimpleNamespace(garment_attributes={}, confirmed_attributes={},
                                                      confidence_score=0.0, analysis_time_sec=0.05)
        with patch.object(rr, "User") as U, patch.object(rr, "PatternResult") as P, \
                patch.object(rr, "ResearchRecord") as R:
            U.objects.return_value.first.return_value = MagicMock()
            P.objects.return_value.first.return_value = pattern
            r = self.app.test_client().post("/api/research/feedback",
                                            json={"pattern_id": "p", "feedback_score": "4"}, headers=self.h)
        self.assertEqual(r.status_code, 201)
        kw = R.call_args.kwargs
        self.assertEqual((kw["processing_time_sec"], kw["pattern_generation_time_sec"]), (0.05, 0.1234))
        self.assertEqual(kw["feedback_score"], 4)
        self.assertIsNone(kw["ai_confidence_avg"])        # the classifier did not run (no predictions)
        self.assertNotIn("baseline_yardage_m", kw)         # no invented baseline

    def test_score_must_be_a_whole_number_from_1_to_5(self):
        for score in ("abc", 0, 6, 2.5, True, [3]):
            r, R = self._post({"feedback_score": score})
            self.assertEqual(r.status_code, 400, score)
            R.assert_not_called()


if __name__ == "__main__":
    unittest.main()
