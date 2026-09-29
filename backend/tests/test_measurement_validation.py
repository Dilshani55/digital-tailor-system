"""
Phase 2 — measurement validation, unit handling and validated engine input.
"""

import math
import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app
from flask_jwt_extended import create_access_token
from app.logic import measurement_schema as ms
from app.logic import feature_schema as fs
from app.logic.taxonomy_map import confirmed_to_cad_features

VALID_CM = {
    "bust_cm": 88.0, "waist_cm": 70.0, "hip_cm": 94.0, "height_cm": 162.0, "neck_cm": 36.0,
    "shoulder_cm": 12.0, "across_back_cm": 34.0, "back_waist_length_cm": 40.0, "armhole_depth_cm": 20.0,
    "garment_length_cm": 65.0, "bicep_cm": 28.0, "sleeve_cm": 55.0, "wrist_cm": 16.0,
}

_APP = None


def _app():
    global _APP
    if _APP is None:
        _APP = create_app()
        _APP.config["TESTING"] = True
    return _APP


def _headers():
    with _app().app_context():
        return {"Authorization": f"Bearer {create_access_token(identity='user-1')}"}


def _codes(errors, field):
    return [e["code"] for e in errors.get(field, [])]


class TestSchemaDefinition(unittest.TestCase):
    def test_thirteen_fields_with_ranges_and_labels(self):
        self.assertEqual(len(ms.FIELD_KEYS), 13)
        self.assertEqual(set(ms.FIELD_KEYS), set(VALID_CM))
        for key, (lo, hi) in ms.get_ranges().items():
            self.assertTrue(0 < lo < hi, key)
            self.assertIn(key, ms.LABELS)

    def test_typical_measurements_pass(self):
        self.assertEqual(ms.validate_canonical(dict(VALID_CM)), {})

    def test_canonical_unit_is_cm_and_units_are_cm_in(self):
        self.assertEqual(ms.CANONICAL_UNIT, "cm")
        self.assertEqual(ms.UNITS, ("cm", "in"))

    def test_schema_payload(self):
        p = ms.schema_payload()
        self.assertEqual(p["required_for_profile"], list(ms.CORE_FIELDS))
        self.assertEqual(len(p["required_for_pattern"]), 13)
        self.assertEqual(len(p["fields"]), 13)

    def test_range_override_from_environment(self):
        with patch.dict(os.environ, {"MEASUREMENT_RANGES_JSON": '{"bust_cm": [50, 200]}'}):
            self.assertEqual(ms.get_ranges()["bust_cm"], (50.0, 200.0))
            self.assertEqual(ms.validate_canonical({"bust_cm": 190.0}), {})
        self.assertEqual(ms.get_ranges()["bust_cm"], (60.0, 160.0))

    def test_bad_environment_override_is_rejected(self):
        for bad in ('{"nope_cm": [1, 2]}', '{"bust_cm": [100, 50]}', "not json"):
            with patch.dict(os.environ, {"MEASUREMENT_RANGES_JSON": bad}):
                with self.assertRaises(ValueError):
                    ms.get_ranges()


class TestFrontendParity(unittest.TestCase):
    def test_frontend_schema_matches_backend(self):
        import re
        path = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "src", "utils", "measurementSchema.js")
        text = open(path, encoding="utf-8").read()
        found = re.findall(r"key: '([a-z_]+)', label: '([^']+)', min: ([\d.]+), max: ([\d.]+)", text)
        self.assertEqual([f[0] for f in found], list(ms.FIELD_KEYS))
        ranges = ms.get_ranges()
        for key, label, lo, hi in found:
            self.assertEqual((float(lo), float(hi)), ranges[key], key)
            self.assertEqual(label, ms.LABELS[key], key)
        self.assertIn("CM_PER_INCH = 2.54", text)
        core = re.search(r"CORE_FIELDS = \[([^\]]+)\]", text).group(1)
        self.assertEqual(re.findall(r"'([a-z_]+)'", core), list(ms.CORE_FIELDS))


class TestParseNumber(unittest.TestCase):
    def test_accepts_numbers_and_numeric_strings(self):
        for raw, expected in ((88, 88.0), (88.5, 88.5), ("88.5", 88.5), (" 70 ", 70.0), ("1e2", 100.0)):
            self.assertEqual(ms.parse_number(raw), (expected, None))

    def test_blank_is_missing_not_error(self):
        for raw in (None, "", "   "):
            self.assertEqual(ms.parse_number(raw), (None, None))

    def test_rejects_non_numeric(self):
        for raw in ("abc", "88,5", "12cm", True, False, [88], {"v": 1}):
            value, err = ms.parse_number(raw)
            self.assertIsNone(value)
            self.assertEqual(err["code"], "NOT_A_NUMBER", repr(raw))

    def test_rejects_non_finite(self):
        for raw in (float("nan"), float("inf"), float("-inf"), "nan", "Infinity", "-inf"):
            value, err = ms.parse_number(raw)
            self.assertIsNone(value)
            self.assertEqual(err["code"], "NOT_FINITE", repr(raw))

    def test_rejects_zero_and_negative(self):
        for raw in (0, 0.0, "0", -5, "-1.5"):
            value, err = ms.parse_number(raw)
            self.assertEqual(err["code"], "NOT_POSITIVE", repr(raw))


class TestUnitConversion(unittest.TestCase):
    def test_normalize_unit(self):
        self.assertEqual(ms.normalize_unit(None), ("cm", None))
        self.assertEqual(ms.normalize_unit(""), ("cm", None))
        self.assertEqual(ms.normalize_unit("IN"), ("in", None))
        self.assertEqual(ms.normalize_unit("cm"), ("cm", None))
        for bad in ("mm", "feet", 5, "cms"):
            unit, err = ms.normalize_unit(bad)
            self.assertIsNone(unit)
            self.assertEqual(err["code"], "INVALID_UNIT")

    def test_inch_to_cm_exact_factor(self):
        canonical, original, errors = ms.convert_input({"bust_cm": 34.5, "height_cm": "64"}, "in")
        self.assertEqual(errors, {})
        self.assertEqual(canonical["bust_cm"], round(34.5 * 2.54, 2))    # 87.63
        self.assertEqual(canonical["height_cm"], 162.56)
        self.assertEqual(original["bust_cm"], {"value": 34.5, "unit": "in"})
        self.assertEqual(original["height_cm"], {"value": 64.0, "unit": "in"})

    def test_cm_is_unchanged(self):
        canonical, original, _ = ms.convert_input({"bust_cm": 88.25}, "cm")
        self.assertEqual(canonical["bust_cm"], 88.25)
        self.assertEqual(original["bust_cm"], {"value": 88.25, "unit": "cm"})

    def test_range_is_checked_after_conversion(self):
        # 88 typed as inches is 223.5 cm: plausible only if the user really meant inches.
        canonical, _, _ = ms.convert_input({"bust_cm": 88}, "in")
        errors = ms.validate_canonical(canonical)
        self.assertEqual(_codes(errors, "bust_cm"), ["OUT_OF_RANGE"])
        self.assertIn("in)", errors["bust_cm"][0]["message"])           # bounds shown in both units

    def test_armhole_alias(self):
        canonical, _, _ = ms.convert_input({"armhole_cm": 21}, "cm")
        self.assertEqual(canonical["armhole_depth_cm"], 21.0)

    def test_parse_errors_are_field_level(self):
        _, _, errors = ms.convert_input({"bust_cm": "abc", "waist_cm": -3, "hip_cm": float("nan")}, "cm")
        self.assertEqual(_codes(errors, "bust_cm"), ["NOT_A_NUMBER"])
        self.assertEqual(_codes(errors, "waist_cm"), ["NOT_POSITIVE"])
        self.assertEqual(_codes(errors, "hip_cm"), ["NOT_FINITE"])


class TestRanges(unittest.TestCase):
    def test_every_field_rejects_below_and_above_and_accepts_bounds(self):
        for key, (lo, hi) in ms.get_ranges().items():
            self.assertEqual(ms.validate_canonical({key: lo}), {}, f"{key} min")
            self.assertEqual(ms.validate_canonical({key: hi}), {}, f"{key} max")
            self.assertEqual(_codes(ms.validate_canonical({key: lo - 0.01}), key), ["OUT_OF_RANGE"], key)
            self.assertEqual(_codes(ms.validate_canonical({key: hi + 0.01}), key), ["OUT_OF_RANGE"], key)

    def test_extreme_values(self):
        errors = ms.validate_canonical({"bust_cm": 5.0, "waist_cm": 500.0, "height_cm": 30.0})
        self.assertEqual(set(errors), {"bust_cm", "waist_cm", "height_cm"})
        for e in errors.values():
            self.assertIn("min_cm", e[0])


class TestRelations(unittest.TestCase):
    def _bad(self, **changes):
        return ms.validate_canonical(dict(VALID_CM, **changes))

    def test_each_relationship(self):
        cases = [
            ("wrist_cm", dict(wrist_cm=24.0, bicep_cm=20.0)),
            ("neck_cm", dict(neck_cm=54.0, waist_cm=50.0, bust_cm=88.0)),
            ("armhole_depth_cm", dict(armhole_depth_cm=30.0, back_waist_length_cm=30.0, height_cm=140.0)),
            ("back_waist_length_cm", None),                                      # set below
            ("sleeve_cm", dict(sleeve_cm=75.0, height_cm=130.0)),
            ("garment_length_cm", dict(garment_length_cm=100.0, height_cm=130.0)),
        ]
        for field, changes in cases:
            if field == "back_waist_length_cm":
                changes = dict(back_waist_length_cm=30.0, height_cm=210.0)     # 14% of height (< 18%)
            errors = self._bad(**changes)
            self.assertIn("RELATION", _codes(errors, field), f"{field}: {errors}")

    def test_every_relation_can_actually_fire_within_the_ranges(self):
        """Guards against dead rules: each rule's field must be reachable by some in-range input."""
        fired = set()
        r = ms.get_ranges()
        probes = [
            dict(wrist_cm=r["wrist_cm"][1], bicep_cm=r["bicep_cm"][0]),
            dict(neck_cm=r["neck_cm"][1], waist_cm=r["waist_cm"][0]),
            dict(armhole_depth_cm=r["armhole_depth_cm"][1], back_waist_length_cm=r["back_waist_length_cm"][0]),
            dict(back_waist_length_cm=r["back_waist_length_cm"][0], height_cm=r["height_cm"][1]),
            dict(sleeve_cm=r["sleeve_cm"][1], height_cm=r["height_cm"][0]),
            dict(garment_length_cm=r["garment_length_cm"][1], height_cm=r["height_cm"][0]),
        ]
        for probe in probes:
            fired |= {f for f, errs in ms.validate_canonical(probe).items()
                      if any(e["code"] == "RELATION" for e in errs)}
        self.assertEqual(fired, set(ms._INVOLVED))

    def test_relation_needs_both_values_present(self):
        self.assertEqual(ms.validate_canonical({"wrist_cm": 24.0}), {})     # no bicep given -> nothing to compare

    def test_relation_skipped_when_a_value_is_already_out_of_range(self):
        errors = ms.validate_canonical({"wrist_cm": 24.0, "bicep_cm": 5.0})
        self.assertEqual(_codes(errors, "bicep_cm"), ["OUT_OF_RANGE"])
        self.assertNotIn("wrist_cm", errors)                                # no confusing second error

    def test_partial_update_scope_limits_reporting(self):
        merged = dict(VALID_CM, wrist_cm=24.0, bicep_cm=20.0)               # pre-existing bad pair
        self.assertEqual(ms.validate_canonical(merged, only={"neck_cm"}), {})
        self.assertIn("wrist_cm", ms.validate_canonical(merged, only={"bicep_cm"}))


class _Profile(SimpleNamespace):
    pass


def _profile(**over):
    base = dict(VALID_CM, armhole_cm=20.0, fabric_type="woven", fit_preference="standard", original_values={})
    base.update(over)
    return _Profile(**base)


class TestEngineMeasurements(unittest.TestCase):
    def test_complete_valid_profile(self):
        m, code, errors = ms.engine_measurements(_profile())
        self.assertEqual((code, errors), (None, {}))
        for key in ms.FIELD_KEYS:
            self.assertEqual(m[key], VALID_CM[key])
        self.assertEqual(m["fabric_type"], "woven")
        self.assertEqual(m["armhole_cm"], 20.0)

    def test_missing_measurement_is_never_defaulted(self):
        for key in ms.FIELD_KEYS:
            m, code, errors = ms.engine_measurements(_profile(**{key: None, "armhole_cm": None}))
            self.assertIsNone(m, key)
            self.assertEqual(code, "MEASUREMENTS_INCOMPLETE")
            self.assertEqual(list(errors), [key])

    def test_armhole_falls_back_to_legacy_alias_only_if_present(self):
        m, _, _ = ms.engine_measurements(_profile(armhole_depth_cm=None, armhole_cm=21.0))
        self.assertEqual(m["armhole_depth_cm"], 21.0)

    def test_implausible_values_are_rejected(self):
        m, code, errors = ms.engine_measurements(_profile(bust_cm=5.0, waist_cm=500.0))
        self.assertIsNone(m)
        self.assertEqual(code, "MEASUREMENTS_INVALID")
        self.assertEqual(set(errors), {"bust_cm", "waist_cm"})

    def test_corrupt_stored_values_are_rejected(self):
        for bad in (float("nan"), -1, 0, "abc"):
            m, code, errors = ms.engine_measurements(_profile(neck_cm=bad))
            self.assertIsNone(m)
            self.assertIn("neck_cm", errors)

    def test_invalid_fabric_or_fit(self):
        m, code, errors = ms.engine_measurements(_profile(fabric_type="silk", fit_preference="tight"))
        self.assertIsNone(m)
        self.assertEqual(set(errors), {"fabric_type", "fit_preference"})


# ── routes ────────────────────────────────────────────────────────────────────
class FakeProfile:
    """Stand-in for MeasurementProfile that records what would be saved."""
    saved = []

    def __init__(self, **kw):
        self.id = "m1"
        self.email = None
        self.notes = "No notes."
        self.client_name = "Customer Profile"
        self.fabric_type = "woven"
        self.fit_preference = "standard"
        self.unit = "cm"
        self.original_values = {}
        self.measurement_schema_version = 1
        self.created_at = "2026-09-01"
        for k in ms.FIELD_KEYS + ("armhole_cm",):
            setattr(self, k, None)
        for k, v in kw.items():
            setattr(self, k, v)
        self.user_id = SimpleNamespace(id="user-1")

    def save(self):
        FakeProfile.saved.append(self)


class TestMeasurementRoutes(unittest.TestCase):
    def setUp(self):
        FakeProfile.saved = []
        self.client = _app().test_client()

    def _post(self, payload):
        with patch("app.routes.measurements.User") as user_cls, \
             patch("app.routes.measurements.MeasurementProfile", FakeProfile):
            user_cls.objects.return_value.first.return_value = object()
            return self.client.post("/api/measurements/", json=payload, headers=_headers())

    def test_valid_cm_profile_is_saved_as_canonical(self):
        resp = self._post(dict(VALID_CM, client_name="Amara"))
        self.assertEqual(resp.status_code, 201, resp.get_json())
        profile = resp.get_json()["profile"]
        self.assertTrue(profile["complete"])
        self.assertEqual(profile["missing_fields"], [])
        self.assertEqual(profile["bust_cm"], 88.0)
        self.assertEqual(profile["original_values"]["bust_cm"], {"value": 88.0, "unit": "cm"})
        self.assertEqual(profile["canonical_unit"], "cm")

    def test_inch_profile_stores_original_and_canonical(self):
        inches = {k: round(v / 2.54, 2) for k, v in VALID_CM.items()}
        resp = self._post(dict(inches, unit="in"))
        self.assertEqual(resp.status_code, 201, resp.get_json())
        saved = FakeProfile.saved[0]
        self.assertEqual(saved.unit, "in")
        self.assertAlmostEqual(saved.bust_cm, VALID_CM["bust_cm"], delta=0.05)          # canonical cm
        self.assertEqual(saved.original_values["bust_cm"], {"value": inches["bust_cm"], "unit": "in"})
        self.assertEqual(saved.armhole_cm, saved.armhole_depth_cm)

    def test_inch_values_that_are_really_cm_are_rejected_not_accepted(self):
        resp = self._post(dict(VALID_CM, unit="in"))       # 88 "inches" = 223 cm bust
        self.assertEqual(resp.status_code, 400)
        self.assertIn("bust_cm", resp.get_json()["field_errors"])
        self.assertEqual(FakeProfile.saved, [])

    def test_field_level_errors_for_bad_inputs(self):
        payload = dict(VALID_CM, bust_cm="abc", waist_cm=-4, hip_cm=0, height_cm=999, neck_cm=None)
        resp = self._post(payload)
        self.assertEqual(resp.status_code, 400)
        body = resp.get_json()
        self.assertEqual(body["error_code"], "MEASUREMENT_VALIDATION_FAILED")
        fe = body["field_errors"]
        self.assertEqual(fe["bust_cm"][0]["code"], "NOT_A_NUMBER")
        self.assertEqual(fe["waist_cm"][0]["code"], "NOT_POSITIVE")
        self.assertEqual(fe["hip_cm"][0]["code"], "NOT_POSITIVE")
        self.assertEqual(fe["height_cm"][0]["code"], "OUT_OF_RANGE")
        self.assertNotIn("neck_cm", fe)          # optional at profile level
        self.assertEqual(FakeProfile.saved, [])

    def test_nan_and_infinity_json_are_rejected(self):
        with patch("app.routes.measurements.User") as user_cls, \
             patch("app.routes.measurements.MeasurementProfile", FakeProfile):
            user_cls.objects.return_value.first.return_value = object()
            raw = '{"bust_cm": NaN, "waist_cm": Infinity, "hip_cm": 94, "height_cm": 162}'
            resp = self.client.post("/api/measurements/", data=raw, headers=dict(
                _headers(), **{"Content-Type": "application/json"}))
        self.assertEqual(resp.status_code, 400)
        fe = resp.get_json()["field_errors"]
        self.assertEqual(fe["bust_cm"][0]["code"], "NOT_FINITE")
        self.assertEqual(fe["waist_cm"][0]["code"], "NOT_FINITE")

    def test_missing_core_fields(self):
        resp = self._post({"client_name": "X"})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(set(resp.get_json()["field_errors"]), set(ms.CORE_FIELDS))

    def test_core_only_profile_is_saved_but_marked_incomplete(self):
        resp = self._post({k: VALID_CM[k] for k in ms.CORE_FIELDS})
        self.assertEqual(resp.status_code, 201)
        p = resp.get_json()["profile"]
        self.assertFalse(p["complete"])
        self.assertEqual(len(p["missing_fields"]), 9)
        self.assertIsNone(p["neck_cm"])                     # nothing fabricated

    def test_invalid_unit_and_choices_and_body(self):
        self.assertEqual(self._post(dict(VALID_CM, unit="mm")).get_json()["field_errors"]["unit"][0]["code"],
                         "INVALID_UNIT")
        r = self._post(dict(VALID_CM, fabric_type="silk", fit_preference="tight"))
        self.assertEqual(set(r.get_json()["field_errors"]), {"fabric_type", "fit_preference"})
        with patch("app.routes.measurements.User") as u:
            u.objects.return_value.first.return_value = object()
            resp = self.client.post("/api/measurements/", data="[1,2]", headers=dict(
                _headers(), **{"Content-Type": "application/json"}))
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.get_json()["error_code"], "INVALID_BODY")

    def test_relationship_error_is_reported_on_the_field(self):
        resp = self._post(dict(VALID_CM, wrist_cm=24.0, bicep_cm=20.0))
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.get_json()["field_errors"]["wrist_cm"][0]["code"], "RELATION")

    def _put(self, profile, payload):
        with patch("app.routes.measurements.MeasurementProfile") as mp:
            mp.objects.return_value.first.return_value = profile
            return self.client.put("/api/measurements/m1", json=payload, headers=_headers())

    def test_partial_update_converts_units_and_keeps_originals(self):
        profile = FakeProfile(**dict(VALID_CM, armhole_cm=20.0, original_values={
            "bust_cm": {"value": 88.0, "unit": "cm"}}))
        resp = self._put(profile, {"waist_cm": 27.5, "unit": "in"})
        self.assertEqual(resp.status_code, 200, resp.get_json())
        self.assertEqual(profile.waist_cm, round(27.5 * 2.54, 2))
        self.assertEqual(profile.original_values["waist_cm"], {"value": 27.5, "unit": "in"})
        self.assertEqual(profile.original_values["bust_cm"], {"value": 88.0, "unit": "cm"})   # preserved
        self.assertEqual(profile.bust_cm, 88.0)

    def test_update_rejects_bad_value_and_leaves_profile_untouched(self):
        profile = FakeProfile(**dict(VALID_CM, armhole_cm=20.0))
        resp = self._put(profile, {"bust_cm": "abc"})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(profile.bust_cm, 88.0)
        self.assertEqual(FakeProfile.saved, [])

    def test_update_relation_against_existing_values(self):
        profile = FakeProfile(**dict(VALID_CM, armhole_cm=20.0, neck_cm=50.0))
        resp = self._put(profile, {"waist_cm": 45.0})      # stored neck 50 cm is not smaller than the new waist
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.get_json()["field_errors"]["neck_cm"][0]["code"], "RELATION")

    def test_update_ignores_unrelated_legacy_problem(self):
        legacy = dict(VALID_CM, armhole_cm=20.0, wrist_cm=24.0, bicep_cm=20.0)   # bad pair from before
        profile = FakeProfile(**legacy)
        resp = self._put(profile, {"neck_cm": 35.0})
        self.assertEqual(resp.status_code, 200)

    def test_schema_endpoint(self):
        resp = self.client.get("/api/measurements/schema", headers=_headers())
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.get_json()["fields"]), 13)


# ── pattern generation only ever sees validated measurements ─────────────────
CONFIRMED = {"garment_type": "blouse", "neckline_type": "round-neck",
             "sleeve_length": "short-sleeve", "sleeve_style": "regular-sleeve"}


class TestGenerateUsesValidatedMeasurements(unittest.TestCase):
    def _generate(self, profile, engine=None):
        clean, _ = fs.validate_attributes(CONFIRMED)
        image = SimpleNamespace(
            id="img1", user_id=SimpleNamespace(id="user-1"), file_path="x.jpg", garment_attributes={},
            confirmed_attributes=clean,
            design_spec=fs.build_design_spec(clean, None, confirmed_to_cad_features(clean)),
            detected_features={}, confidence_score=0.0, confirmed_at=None, save=MagicMock())
        with patch("app.routes.patterns.User") as u, patch("app.routes.patterns.MeasurementProfile") as mp, \
             patch("app.routes.patterns.DesignImage") as di, patch("app.routes.patterns.Session") as sess, \
             patch("app.routes.patterns.PatternResult") as pr, \
             patch("app.routes.patterns.ParametricEngine") as eng:
            u.objects.return_value.first.return_value = object()
            mp.objects.return_value.first.return_value = profile
            di.objects.return_value.first.return_value = image
            pr.return_value.id = "p1"
            sess.return_value.id = "s1"
            from app.logic.parametric_engine import ParametricEngine as Real
            eng.side_effect = engine or (lambda m, f, design_spec=None: Real(m, f, design_spec=design_spec))
            resp = _app().test_client().post("/api/patterns/generate", headers=_headers(), json={
                "measurement_id": "m1", "image_id": "img1", "fabric_id": "cotton-poplin"})
            return resp, eng, pr

    def test_valid_profile_reaches_engine_and_snapshot_is_stored(self):
        resp, eng, pr = self._generate(_profile(original_values={"bust_cm": {"value": 34.65, "unit": "in"}}))
        self.assertEqual(resp.status_code, 201, resp.get_json())
        passed = eng.call_args.args[0]
        for key in ms.FIELD_KEYS:
            self.assertEqual(passed[key], VALID_CM[key], key)
        snap = pr.call_args.kwargs["measurements_snapshot"]
        self.assertEqual(snap["canonical_cm"], VALID_CM)
        self.assertEqual(snap["canonical_unit"], "cm")
        self.assertEqual(snap["original_values"]["bust_cm"], {"value": 34.65, "unit": "in"})

    def test_incomplete_profile_is_rejected_without_calling_the_engine(self):
        resp, eng, pr = self._generate(_profile(neck_cm=None, bicep_cm=None))
        self.assertEqual(resp.status_code, 422)
        body = resp.get_json()
        self.assertEqual(body["error_code"], "MEASUREMENTS_INCOMPLETE")
        self.assertEqual(set(body["field_errors"]), {"neck_cm", "bicep_cm"})
        eng.assert_not_called()
        pr.assert_not_called()

    def test_implausible_profile_is_rejected(self):
        resp, eng, _ = self._generate(_profile(bust_cm=5.0))
        self.assertEqual(resp.status_code, 422)
        self.assertEqual(resp.get_json()["error_code"], "MEASUREMENTS_INVALID")
        eng.assert_not_called()


class TestEndToEndContract(unittest.TestCase):
    """
    classifier output -> user correction (confirm route) -> canonical design spec
    + measurements entered in INCHES (measurement route) -> pattern-generation route.
    """

    def test_full_chain(self):
        predictions = {
            "model_version": "YOLOv8MultiTaskClassifier|stage=Stage_B|epoch=7|sha256=3b69a470ed5d",
            "model_type": "image-level multi-task classifier", "checkpoint_sha256": "3b" * 32,
            "predictions": {
                "garment_type": {"label": "blouse", "confidence": 0.9, "top_3": []},
                "neckline_type": {"label": "v-neck", "confidence": 0.5, "top_3": []},
                "sleeve_length": {"label": "long-sleeve", "confidence": 0.6, "top_3": []},
                "sleeve_style": {"label": "regular-sleeve", "confidence": 0.4, "top_3": []},
            },
        }
        image = SimpleNamespace(
            id="img1", user_id=SimpleNamespace(id="user-1"), file_path="x.jpg", garment_attributes=predictions,
            confirmed_attributes={}, design_spec={}, detected_features={"source": "cv_heuristic"},
            confidence_score=0.6, confirmed_at=None, save=MagicMock())
        client = _app().test_client()

        # 1. user corrects neckline + sleeve length at confirmation
        with patch("app.routes.images.DesignImage") as di:
            di.objects.return_value.first.return_value = image
            corrected = dict(CONFIRMED, neckline_type="square-neck", sleeve_length="elbow-length")
            r = client.post("/api/images/img1/confirm-attributes", json=corrected, headers=_headers())
        self.assertEqual(r.status_code, 200, r.get_json())

        # 2. measurements entered in inches are stored canonically in cm
        FakeProfile.saved = []
        inches = {k: round(v / 2.54, 2) for k, v in VALID_CM.items()}
        with patch("app.routes.measurements.User") as u, patch("app.routes.measurements.MeasurementProfile", FakeProfile):
            u.objects.return_value.first.return_value = object()
            r = client.post("/api/measurements/", json=dict(inches, unit="in"), headers=_headers())
        self.assertEqual(r.status_code, 201, r.get_json())
        stored = FakeProfile.saved[0]

        # 3. generation consumes the confirmed design + validated cm measurements
        seen = {}
        from app.logic.parametric_engine import ParametricEngine as Real

        def capture(m, f, design_spec=None):
            seen["m"], seen["f"] = m, f
            return Real(m, f, design_spec=design_spec)

        with patch("app.routes.patterns.User") as u, patch("app.routes.patterns.MeasurementProfile") as mp, \
             patch("app.routes.patterns.DesignImage") as di, patch("app.routes.patterns.Session") as sess, \
             patch("app.routes.patterns.PatternResult") as pr, patch("app.routes.patterns.ParametricEngine") as eng:
            u.objects.return_value.first.return_value = object()
            mp.objects.return_value.first.return_value = stored
            di.objects.return_value.first.return_value = image
            pr.return_value.id = "p1"
            sess.return_value.id = "s1"
            eng.side_effect = capture
            r = client.post("/api/patterns/generate", headers=_headers(), json={
                "measurement_id": "m1", "image_id": "img1", "fabric_id": "cotton-poplin"})
        self.assertEqual(r.status_code, 201, r.get_json())
        self.assertEqual(seen["f"]["neckline"], "square neck")                  # corrected, canonical design
        self.assertEqual(seen["f"]["sleeves"], "elbow sleeve")
        self.assertAlmostEqual(seen["m"]["bust_cm"], 88.0, delta=0.05)          # inches -> cm
        spec = pr.call_args.kwargs["design_spec"]
        self.assertEqual(spec["provenance"]["neckline_type"]["source"], "user_corrected")
        self.assertEqual(spec["provenance"]["neckline_type"]["predicted_confidence"], 0.5)
        snap = pr.call_args.kwargs["measurements_snapshot"]
        self.assertEqual(snap["original_values"]["bust_cm"]["unit"], "in")     # original preserved
        self.assertAlmostEqual(snap["canonical_cm"]["bust_cm"], 88.0, delta=0.05)


if __name__ == "__main__":
    unittest.main()
