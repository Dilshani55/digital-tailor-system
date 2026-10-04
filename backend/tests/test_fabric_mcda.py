"""Mathematical verification using explicitly synthetic, hand-computable fixtures."""

import copy
import json
from pathlib import Path
import tempfile
import unittest

from app.logic.fabric_mcda import RankingDataError, ahp_weights, group_ahp, topsis
from app.logic.fabric_research import check_dataset, rank_profile
from app.logic.fabric_selection import recommend_for_design
from tests.fabric_research_fixtures import research_data


class TestAHP(unittest.TestCase):
    def test_known_consistent_ratio_matrix_has_exact_weights_and_zero_cr(self):
        result = ahp_weights([[1, 1.5, 3], [2/3, 1, 2], [1/3, .5, 1]])
        for actual, expected in zip(result["weights"], (.5, 1/3, 1/6)):
            self.assertAlmostEqual(actual, expected, places=10)
        self.assertAlmostEqual(result["lambda_max"], 3)
        self.assertAlmostEqual(result["consistency_ratio"], 0)

    def test_inconsistent_judgements_are_rejected(self):
        with self.assertRaisesRegex(RankingDataError, "consistency ratio"):
            ahp_weights([[1, 9, 1/9], [1/9, 1, 9], [9, 1/9, 1]])

    def test_malformed_nonreciprocal_and_nonfinite_comparisons_are_rejected(self):
        for matrix in ([[1, 2], [2, 1]], [[2, 1], [1, 1]], [[1, 10], [.1, 1]],
                       [[1, 0], [1, 1]], [[1, float('nan')], [1, 1]], [[1, True], [1, 1]],
                       [[1, 2], [1]], [[1]]):
            with self.subTest(matrix=matrix), self.assertRaises(RankingDataError):
                ahp_weights(matrix)

    def test_geometric_aggregation_preserves_reciprocity(self):
        result = group_ahp([[[1, 4], [.25, 1]], [[1, 1], [1, 1]]])
        self.assertAlmostEqual(result["aggregated_matrix"][0][1], 2)
        self.assertAlmostEqual(result["aggregated_matrix"][1][0], .5)
        self.assertAlmostEqual(result["weights"][0], 2/3)
        self.assertEqual(len(result["individual_consistency_ratios"]), 2)

    def test_group_cannot_hide_inconsistent_individuals(self):
        with self.assertRaises(RankingDataError):
            group_ahp([[[1, 9, 1/9], [1/9, 1, 9], [9, 1/9, 1]],
                       [[1, 1/9, 9], [9, 1, 1/9], [1/9, 9, 1]]])


class TestTOPSIS(unittest.TestCase):
    def test_hand_calculated_best_middle_worst(self):
        result = topsis([[1, 3], [2, 2], [3, 1]], [.5, .5], ["benefit", "cost"])
        self.assertEqual([r["closeness"] for r in result["alternatives"]], [0, .5, 1])

    def test_criteria_weights_change_a_tradeoff_by_known_amount(self):
        result = topsis([[1, 1], [3, 3]], [.75, .25], ["benefit", "cost"])
        self.assertAlmostEqual(result["alternatives"][0]["closeness"], .25)
        self.assertAlmostEqual(result["alternatives"][1]["closeness"], .75)

    def test_column_unit_scaling_does_not_change_ranks(self):
        a = topsis([[1, 3], [2, 2], [3, 1]], [.7, .3], ["benefit", "cost"])
        b = topsis([[100, .03], [200, .02], [300, .01]], [.7, .3], ["benefit", "cost"])
        for x, y in zip(a["alternatives"], b["alternatives"]):
            self.assertAlmostEqual(x["closeness"], y["closeness"])

    def test_constant_zero_columns_and_identical_samples_do_not_invent_scores(self):
        differentiated = topsis([[1, 0], [3, 0]], [.5, .5], ["benefit", "cost"])
        self.assertEqual([r["closeness"] for r in differentiated["alternatives"]], [0, 1])
        identical = topsis([[2, 0], [2, 0]], [.5, .5], ["benefit", "cost"])
        self.assertFalse(identical["discriminating"])
        self.assertEqual([r["closeness"] for r in identical["alternatives"]], [None, None])

    def test_invalid_input_is_rejected(self):
        for values, weights, directions in (([[1, 2]], [.5, .5], ["benefit", "cost"]),
            ([[1, 2], [3]], [.5, .5], ["benefit", "cost"]),
            ([[1, 2], [3, 4]], [.1, .5], ["benefit", "cost"]),
            ([[1, 2], [3, 4]], [0, 1], ["benefit", "cost"]),
            ([[1, -2], [3, 4]], [.5, .5], ["benefit", "cost"]),
            ([[1, 2], [3, 4]], [.5, .5], ["benefit", "unknown"])):
            with self.subTest(values=values), self.assertRaises(RankingDataError):
                topsis(values, weights, directions)

    def test_nonfinite_and_overflowing_observations_are_rejected(self):
        for value in (float('inf'), float('nan'), 10**1000, 1.7e308):
            with self.subTest(value=str(value)[:20]), self.assertRaises(RankingDataError):
                topsis([[value, 1], [value, 2]], [.5, .5], ["benefit", "cost"])


class TestRecordedProfiles(unittest.TestCase):
    def setUp(self):
        self.data = research_data()
        self.profile = self.data["profiles"][0]
        self.ids = [s["fabric_id"] for s in self.profile["samples"]]

    def test_complete_profile_is_ranked_and_fully_auditable(self):
        result = recommend_for_design(self.profile["design"], research_data=self.data)
        self.assertEqual(result["ranking_status"], "ranked")
        self.assertEqual(result["recommended_ids"], ["cotton-jersey-knit"])
        self.assertEqual(result["ranking_audit"]["decision_matrix"], [[3, 1], [1, 3]])
        winner = result["fabrics"][0]
        self.assertEqual(winner["topsis_closeness"], 1)
        self.assertEqual(winner["rank"], 1)
        self.assertIn("Synthetic", winner["research_sample"]["values"]["air"]["source"])
        self.assertIsNone(winner["recommendation_score"])

    def test_fit_or_design_mismatch_never_reuses_unrelated_expert_preferences(self):
        for attrs, fit in ((self.profile["design"], "close"),
                           ({**self.profile["design"], "neckline_type": "v-neck"}, "standard")):
            result = recommend_for_design(attrs, fit, research_data=self.data)
            self.assertEqual(result["ranking_status"], "awaiting_data")
            self.assertEqual(result["recommended_ids"], [])

    def test_incomplete_coverage_different_units_and_missing_sources_block_ranking(self):
        for mode in ("partial", "unit", "protocol", "source", "numeric", "criterion", "duplicate"):
            data = copy.deepcopy(self.data)
            p = data["profiles"][0]
            observation = p["samples"][0]["values"]["air"]
            if mode == "partial": p["samples"].pop()
            if mode in ("unit", "protocol"): observation[mode] = "different"
            if mode == "source": observation["source"] = ""
            if mode == "numeric": observation["value"] = "3"
            if mode == "criterion": p["samples"][0]["values"].pop("air")
            if mode == "duplicate": p["samples"][1]["sample_id"] = p["samples"][0]["sample_id"]
            with self.subTest(mode=mode):
                result = recommend_for_design(p["design"], research_data=data)
                self.assertEqual(result["ranking_status"], "invalid_data")
                self.assertEqual(result["recommended_ids"], [])
                self.assertTrue(all(f["topsis_closeness"] is None for f in result["fabrics"]))

    def test_target_is_an_explicit_project_transform_not_a_more_is_better_assumption(self):
        c = self.profile["criteria"][1]
        c.update(objective="target", target=3)
        self.profile["experts"][0]["matrix"] = [[1, 1/9], [9, 1]]
        result = rank_profile(self.profile, self.ids)
        self.assertEqual(result["audit"]["decision_matrix"], [[3, 2], [1, 0]])
        self.assertGreater(result["results"]["french-terry-knit"]["closeness"],
                           result["results"]["cotton-jersey-knit"]["closeness"])

    def test_identical_data_gives_no_winner(self):
        self.profile["samples"][1]["values"] = copy.deepcopy(self.profile["samples"][0]["values"])
        result = recommend_for_design(self.profile["design"], research_data=self.data)
        self.assertEqual(result["ranking_status"], "indistinguishable")
        self.assertEqual(result["recommended_ids"], [])

    def test_duplicate_profile_context_is_rejected(self):
        duplicate = copy.deepcopy(self.profile)
        duplicate["id"] = "different-id"
        self.data["profiles"].append(duplicate)
        with self.assertRaises(RankingDataError):
            check_dataset(self.data)


class TestResearchRoute(unittest.TestCase):
    def setUp(self):
        from app import create_app
        self.app = create_app()
        self.app.config["TESTING"] = True
        self.data = research_data()
        self.design = self.data["profiles"][0]["design"]

    def test_route_loads_only_server_study_data_and_returns_numeric_audit(self):
        with tempfile.TemporaryDirectory(prefix="fabric-test-") as directory:
            path = Path(directory) / "study.json"
            path.write_text(json.dumps(self.data), encoding="utf-8")
            self.app.config["FABRIC_RESEARCH_DATA_PATH"] = str(path)
            response = self.app.test_client().post("/api/fabric/recommend", json={
                "confirmed_attributes": self.design, "fit_preference": "standard",
                "research_data": {"schema_version": 1, "profiles": []},
            })
            self.assertEqual(response.status_code, 200)
            body = response.get_json()
            self.assertEqual(body["ranking_status"], "ranked")
            self.assertEqual(body["total_recommended"], 1)
            self.assertEqual(body["ranking_audit"]["ahp"]["weights"], [.5, .5])
            self.assertEqual(body["recommended_ids"], ["cotton-jersey-knit"])

    def test_missing_server_file_never_falls_back_to_old_scores_or_client_data(self):
        with tempfile.TemporaryDirectory(prefix="fabric-test-") as directory:
            self.app.config["FABRIC_RESEARCH_DATA_PATH"] = str(Path(directory) / "not-created.json")
            body = self.app.test_client().post("/api/fabric/recommend", json={
                "confirmed_attributes": self.design, "research_data": self.data,
            }).get_json()
            self.assertEqual(body["ranking_status"], "invalid_data")
            self.assertEqual(body["recommended_ids"], [])
            self.assertTrue(all(f["recommendation_score"] is None for f in body["fabrics"]))

    def test_invalid_fit_is_rejected_instead_of_using_default_weights(self):
        response = self.app.test_client().post("/api/fabric/recommend", json={
            "confirmed_attributes": self.design, "fit_preference": "invented-fit",
        })
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error_code"], "INVALID_FIT")
