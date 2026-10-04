"""Published-table provenance, user elicitation and the saved pattern contract.

All importance answers below are TEST INPUTS, not collected expert responses.
"""
import copy
import unittest

from app import create_app
from app.logic.fabric_mcda import RankingDataError
from app.logic.fabric_recommendation import get_fabric_by_id, validate_fabric_id
from app.logic.fabric_selection import fabric_construction, recommend_for_design
from app.logic.published_fabrics import load_studies, rank_user_samples, study_for_garment
from tests.test_fabric_selection_and_widths import D


def preferences(study, ratios=(1, 1, 1)):
    keys = [c["id"] for c in study["criteria"]]
    pairs = [(keys[0], keys[1]), (keys[0], keys[2]), (keys[1], keys[2])]
    return {"study_id": study["id"], "goals": {key: "cost" for key in keys},
            "comparisons": [{"left": a, "right": b, "ratio": r} for (a, b), r in zip(pairs, ratios)]}


class TestPublishedMeasurements(unittest.TestCase):
    def test_transcription_anchors_and_within_study_air_test_area(self):
        studies = load_studies()
        self.assertEqual([len(s["samples"]) for s in studies], [5, 13])
        knit = studies[0]
        sp, st = knit["samples"][0], knit["samples"][2]
        self.assertEqual(sp["sample_id"], "Y1 SP")
        self.assertEqual(sp["values"]["mass"]["value"], 260.38)
        self.assertEqual(st["values"]["mass"]["value"], 267.35)  # source decimal comma
        self.assertEqual(st["values"]["air_flow"]["value"], 206.14)
        self.assertEqual(st["values"]["thermal_resistance"]["value"], .0424)
        self.assertIn("20 cm2", st["values"]["air_flow"]["protocol"])
        woven = studies[1]
        self.assertEqual(woven["samples"][2]["values"]["mass"]["value"], 534)
        self.assertEqual(woven["samples"][9]["values"]["thermal_resistance"]["value"], .0047)
        for s in studies:
            self.assertEqual(len(s["data_sha256"]), 64)
            for sample in s["samples"]:
                self.assertTrue(all(o["source_url"] == s["url"] for o in sample["values"].values()))

    def test_sample_ids_are_selectable_without_invented_generic_properties(self):
        for garment in ("blouse", "t-shirt"):
            study = study_for_garment(garment)
            for sample in study["samples"]:
                self.assertTrue(validate_fabric_id(sample["fabric_id"].upper()))
                fabric = get_fabric_by_id(sample["fabric_id"])
                self.assertEqual(fabric_construction(fabric["id"]), study["construction"])
                self.assertEqual(fabric["research_sample"], sample)
                for absent in ("drape_level", "stretch", "care_instructions", "breathability"):
                    self.assertNotIn(absent, fabric)

    def test_no_preferences_means_no_default_weights_or_winner(self):
        r = recommend_for_design(D(garment="t-shirt"))
        self.assertEqual(r["ranking_status"], "awaiting_preferences")
        self.assertEqual(r["published_study"]["sample_count"], 5)
        self.assertIsNone(r["ranking_audit"])
        self.assertEqual(r["recommended_ids"], [])
        self.assertTrue(all(f["topsis_closeness"] is None for f in r["fabrics"]))

    def test_user_pairwise_weights_and_goals_change_the_comparison(self):
        study = study_for_garment("t-shirt")
        answers = preferences(study, (1/9, 1/3, 3))
        answers["goals"]["air_flow"] = "benefit"
        r = rank_user_samples(study, answers, design=D(garment="t-shirt"), fit="loose")
        for w, expected in zip(r["audit"]["ahp"]["weights"], (1/13, 9/13, 3/13)):
            self.assertAlmostEqual(w, expected)
        self.assertAlmostEqual(r["audit"]["ahp"]["consistency_ratio"], 0)
        self.assertEqual(r["audit"]["weight_source"], "user_preferences")
        self.assertNotIn("expert_sources", r["audit"])
        self.assertEqual(r["audit"]["fit_preference"], "loose")
        best = max(r["results"], key=lambda fid: r["results"][fid]["closeness"])
        self.assertEqual(best, "cubric-2022-y1-st")
        reverse = copy.deepcopy(answers)
        reverse["goals"]["air_flow"] = "cost"
        changed = rank_user_samples(study, reverse, design=D(garment="t-shirt"), fit="loose")
        self.assertNotEqual(max(changed["results"], key=lambda fid: changed["results"][fid]["closeness"]), best)

    def test_incomplete_duplicate_invalid_and_inconsistent_answers_are_rejected(self):
        study = study_for_garment("t-shirt")
        cases = []
        for key in ("goals", "comparisons"):
            p = preferences(study)
            p[key] = {} if key == "goals" else p[key][:2]
            cases.append(p)
        p = preferences(study); p["comparisons"][1] = copy.deepcopy(p["comparisons"][0]); cases.append(p)
        p = preferences(study); p["study_id"] = "wrong-study"; cases.append(p)
        p = preferences(study); p["samples"] = []; cases.append(p)
        for value in (True, "3", 0, 2, float("nan"), float("inf")):
            p = preferences(study); p["comparisons"][0]["ratio"] = value; cases.append(p)
        p = preferences(study); p["comparisons"][0]["left"] = {}; cases.append(p)
        cases.append(preferences(study, (9, 1/9, 9)))
        for p in cases:
            with self.subTest(preferences=p), self.assertRaises(RankingDataError):
                rank_user_samples(study, p, design=D(garment="t-shirt"), fit="standard")

    def test_generic_catalogue_choices_do_not_acquire_source_sample_scores(self):
        study = study_for_garment("blouse")
        r = recommend_for_design(D(), user_preferences=preferences(study))
        self.assertEqual(r["ranking_status"], "ranked")
        self.assertEqual(r["recommended_ids"], ["alam-2013-f06"])
        scored = [f for f in r["fabrics"] if f["rank"] is not None]
        self.assertEqual(len(scored), 13)
        self.assertTrue(all(f["study_id"] == study["id"] for f in scored))
        poplin = next(f for f in r["fabrics"] if f["id"] == "cotton-poplin")
        self.assertIsNone(poplin["topsis_closeness"])
        self.assertFalse(poplin["recommended"])


class TestPublishedWorkflow(unittest.TestCase):
    def test_api_uses_server_observations_and_explicit_user_priorities(self):
        app = create_app(); app.config["TESTING"] = True
        study = study_for_garment("t-shirt")
        payload = {"confirmed_attributes": D(garment="t-shirt"), "user_preferences": preferences(study),
                   "research_data": {"samples": [{"values": {"mass": 1}}]}}
        response = app.test_client().post("/api/fabric/recommend", json=payload)
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(body["ranking_status"], "ranked")
        self.assertEqual(body["ranking_audit"]["decision_matrix"][0], [260.38, 140.12, .0444])
        self.assertEqual(body["ranking_audit"]["weight_source"], "user_preferences")
        payload["user_preferences"]["comparisons"].pop()
        failed = app.test_client().post("/api/fabric/recommend", json=payload)
        self.assertEqual(failed.status_code, 422)
        self.assertEqual(failed.get_json()["error_code"], "INVALID_FABRIC_PREFERENCES")
        self.assertEqual(failed.get_json()["recommended_ids"], [])

    def test_pattern_generation_recomputes_and_saves_the_selected_source_sample(self):
        from tests.test_measurement_validation import TestGenerateUsesValidatedMeasurements, _profile
        study = study_for_garment("blouse")
        answers = preferences(study)
        response, engine, record = TestGenerateUsesValidatedMeasurements()._generate(
            _profile(sleeve_cm=24.0, sleeve_end_cm=27.0),
            body={"fabric_id": "alam-2013-f06", "fabric_name": "Client cannot rename source sample",
                  "fabric_preferences": answers, "fabric_selection_snapshot": {"fake": True}})
        self.assertEqual(response.status_code, 201, response.get_json())
        saved = record.call_args.kwargs["fabric_selection_snapshot"]
        self.assertEqual(saved, response.get_json()["fabric_selection_snapshot"])
        self.assertEqual(saved["selection_method"], "user_ahp_topsis")
        self.assertEqual(saved["sample"]["sample_id"], "6")
        self.assertEqual(saved["sample"]["values"]["mass"]["value"], 144)
        self.assertEqual(saved["ranking_audit"]["preferences"], answers)
        self.assertEqual(engine.call_args.args[0]["fabric_type"], "woven")
        self.assertNotEqual(saved["fabric_name"], "Client cannot rename source sample")

    def test_bad_preferences_or_wrong_construction_cannot_reach_the_engine(self):
        from tests.test_measurement_validation import TestGenerateUsesValidatedMeasurements, _profile
        study = study_for_garment("blouse")
        for body, code in (({"fabric_id": "alam-2013-f06", "fabric_preferences": preferences(study, (9, 1/9, 9))}, "INVALID_FABRIC_PREFERENCES"),
                           ({"fabric_id": "cubric-2022-y1-sp"}, "FABRIC_NOT_COMPATIBLE")):
            response, engine, record = TestGenerateUsesValidatedMeasurements()._generate(_profile(sleeve_cm=24), body=body)
            self.assertEqual(response.status_code, 422, response.get_json())
            self.assertEqual(response.get_json()["error_code"], code)
            engine.assert_not_called(); record.assert_not_called()
