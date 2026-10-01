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


SLEEVELESS_CROP = {"garment_type": "crop-top", "neckline_type": "round-neck",
                   "sleeve_length": "sleeveless", "sleeve_style": "none"}
SHORT_BLOUSE = {"garment_type": "blouse", "neckline_type": "round-neck",
                "sleeve_length": "short-sleeve", "sleeve_style": "regular-sleeve"}
LONG_TSHIRT = {"garment_type": "t-shirt", "neckline_type": "round-neck",
               "sleeve_length": "long-sleeve", "sleeve_style": "regular-sleeve"}
LONG_BELL = {"garment_type": "blouse", "neckline_type": "v-neck",
             "sleeve_length": "long-sleeve", "sleeve_style": "bell-sleeve"}
BODICE = ["bust_cm", "waist_cm", "neck_cm", "shoulder_cm", "across_back_cm", "back_waist_length_cm",
          "armhole_depth_cm", "garment_length_cm"]


class TestSchemaDefinition(unittest.TestCase):
    def test_thirteen_fields_with_labels_and_no_ranges(self):
        self.assertEqual(len(ms.FIELD_KEYS), 13)
        self.assertEqual(set(ms.FIELD_KEYS), set(VALID_CM))
        self.assertEqual(ms.LABELS["sleeve_cm"], "Sleeve length")            # not "full arm"
        self.assertFalse(hasattr(ms, "get_ranges"))
        self.assertFalse(hasattr(ms, "validate_canonical"))

    def test_canonical_unit_is_cm_and_units_are_cm_in(self):
        self.assertEqual(ms.CANONICAL_UNIT, "cm")
        self.assertEqual(ms.UNITS, ("cm", "in"))
        self.assertEqual(ms.CM_PER_INCH, 2.54)

    def test_schema_payload(self):
        p = ms.schema_payload()
        self.assertEqual(len(p["fields"]), 13)
        self.assertEqual(p["requirement_rules"], ms.REQUIREMENTS["rules"])
        self.assertNotIn("min_cm", p["fields"][0])


class TestRequiredForDesign(unittest.TestCase):
    """The design decides which measurements are needed - derived from what the drafting engine uses."""

    def test_sleeveless_crop_top_needs_only_the_bodice(self):
        self.assertEqual(ms.required_for_design(SLEEVELESS_CROP), BODICE)        # no hip, sleeve, wrist, height

    def test_short_sleeve_needs_bicep_and_sleeve_length_but_not_wrist(self):
        req = ms.required_for_design(SHORT_BLOUSE)
        self.assertIn("bicep_cm", req)
        self.assertIn("sleeve_cm", req)
        self.assertIn("hip_cm", req)                       # hem below the waist
        self.assertNotIn("wrist_cm", req)
        self.assertNotIn("height_cm", req)

    def test_long_plain_sleeve_needs_the_wrist_but_a_bell_sleeve_does_not(self):
        self.assertIn("wrist_cm", ms.required_for_design(LONG_TSHIRT))
        self.assertNotIn("wrist_cm", ms.required_for_design(LONG_BELL))

    def test_height_is_never_required(self):
        import itertools
        for gt, sl, ss in itertools.product(("blouse", "t-shirt", "crop-top"), ("sleeveless", "short-sleeve", "long-sleeve"),
                                            ("none", "regular-sleeve", "puff-sleeve", "bell-sleeve")):
            self.assertNotIn("height_cm", ms.required_for_design(
                {"garment_type": gt, "neckline_type": "round-neck", "sleeve_length": sl, "sleeve_style": ss}))

    def test_every_required_set_drafts_and_nothing_less_is_invented(self):
        """With exactly the required fields the engine drafts; the unrequired ones stay None."""
        from app.logic.parametric_engine import ParametricEngine
        for design, length in ((SLEEVELESS_CROP, 36.0), (SHORT_BLOUSE, 62.0), (LONG_TSHIRT, 62.0), (LONG_BELL, 62.0)):
            req = ms.required_for_design(design)
            m = {k: (VALID_CM[k] if k in req else None) for k in ms.FIELD_KEYS}
            m["garment_length_cm"] = length
            if design["sleeve_length"] == "short-sleeve":
                m["sleeve_cm"] = 24.0
            m.update(fabric_type="knit" if design["garment_type"] == "t-shirt" else "woven", fit_preference="standard")
            out = ParametricEngine(m, design_spec={"attributes": design}).generate()
            self.assertTrue(out["validation"]["final_pattern"]["passed"], design)
            for k in ms.FIELD_KEYS:
                if k not in req:
                    self.assertIsNone(out["measurements_used"]["raw"][k], (design, k))


class TestFrontendParity(unittest.TestCase):
    def test_frontend_reads_the_same_requirement_file_and_factor(self):
        path = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "src", "utils", "measurementSchema.js")
        text = open(path, encoding="utf-8").read()
        self.assertIn("config/measurement_requirements.json", text)
        self.assertIn("CM_PER_INCH = 2.54", text)
        self.assertNotIn("min:", text)                       # no plausibility ranges on the client either
        self.assertNotIn("full arm", text)


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
        self.assertAlmostEqual(canonical["bust_cm"], 87.63, places=9)
        self.assertAlmostEqual(canonical["height_cm"], 162.56, places=9)
        self.assertEqual(original["bust_cm"], {"value": 34.5, "unit": "in"})
        self.assertEqual(original["height_cm"], {"value": 64.0, "unit": "in"})

    def test_inch_conversion_keeps_full_precision(self):
        canonical, _, _ = ms.convert_input({"neck_cm": 13.337}, "in")
        self.assertAlmostEqual(canonical["neck_cm"], 13.337 * 2.54, places=9)   # not rounded to 2 decimals

    def test_per_field_units(self):
        canonical, original, errors = ms.convert_input({"bust_cm": 34.5, "waist_cm": "70.25"}, "cm", {"bust_cm": "in"})
        self.assertEqual(errors, {})
        self.assertAlmostEqual(canonical["bust_cm"], 87.63, places=9)
        self.assertEqual(canonical["waist_cm"], 70.25)
        self.assertEqual(original["bust_cm"]["unit"], "in")
        self.assertEqual(original["waist_cm"]["unit"], "cm")
        _, _, errors = ms.convert_input({"bust_cm": 34.5}, "cm", {"bust_cm": "mm"})
        self.assertEqual(_codes(errors, "bust_cm"), ["INVALID_UNIT"])

    def test_cm_is_unchanged(self):
        canonical, original, _ = ms.convert_input({"bust_cm": 88.25}, "cm")
        self.assertEqual(canonical["bust_cm"], 88.25)
        self.assertEqual(original["bust_cm"], {"value": 88.25, "unit": "cm"})

    def test_unusual_but_positive_values_are_accepted_unchanged(self):
        # no plausibility ranges: values are never clamped or rejected for being large or small
        canonical, _, errors = ms.convert_input({"bust_cm": 223.52, "wrist_cm": 0.5, "height_cm": 300}, "cm")
        self.assertEqual(errors, {})
        self.assertEqual(canonical, {"bust_cm": 223.52, "wrist_cm": 0.5, "height_cm": 300.0})

    def test_armhole_alias(self):
        canonical, _, _ = ms.convert_input({"armhole_cm": 21}, "cm")
        self.assertEqual(canonical["armhole_depth_cm"], 21.0)

    def test_parse_errors_are_field_level(self):
        _, _, errors = ms.convert_input({"bust_cm": "abc", "waist_cm": -3, "hip_cm": float("nan")}, "cm")
        self.assertEqual(_codes(errors, "bust_cm"), ["NOT_A_NUMBER"])
        self.assertEqual(_codes(errors, "waist_cm"), ["NOT_POSITIVE"])
        self.assertEqual(_codes(errors, "hip_cm"), ["NOT_FINITE"])


class _Profile(SimpleNamespace):
    pass


def _profile(**over):
    base = dict(VALID_CM, armhole_cm=20.0, fabric_type="woven", fit_preference="standard", original_values={})
    base.update(over)
    return _Profile(**base)


class TestEngineMeasurements(unittest.TestCase):
    def test_complete_valid_profile(self):
        m, code, errors = ms.engine_measurements(_profile(), LONG_TSHIRT)
        self.assertEqual((code, errors), (None, {}))
        for key in ms.FIELD_KEYS:
            self.assertEqual(m[key], VALID_CM[key])
        self.assertEqual(m["fabric_type"], "woven")
        self.assertEqual(m["armhole_cm"], 20.0)
        self.assertEqual(m["required_fields"], ms.required_for_design(LONG_TSHIRT))

    def test_missing_required_measurement_is_never_defaulted(self):
        for key in ms.required_for_design(LONG_TSHIRT):
            m, code, errors = ms.engine_measurements(_profile(**{key: None, "armhole_cm": None}), LONG_TSHIRT)
            self.assertIsNone(m, key)
            self.assertEqual(code, "MEASUREMENTS_INCOMPLETE")
            self.assertEqual(list(errors), [key])

    def test_measurements_the_design_does_not_need_may_be_missing(self):
        m, code, errors = ms.engine_measurements(
            _profile(hip_cm=None, height_cm=None, bicep_cm=None, sleeve_cm=None, wrist_cm=None), SLEEVELESS_CROP)
        self.assertEqual((code, errors), (None, {}))
        for key in ("hip_cm", "height_cm", "bicep_cm", "sleeve_cm", "wrist_cm"):
            self.assertIsNone(m[key])                                  # passed as missing, never invented

    def test_armhole_falls_back_to_legacy_alias_only_if_present(self):
        m, _, _ = ms.engine_measurements(_profile(armhole_depth_cm=None, armhole_cm=21.0), SHORT_BLOUSE)
        self.assertEqual(m["armhole_depth_cm"], 21.0)

    def test_corrupt_stored_values_are_rejected(self):
        for bad in (float("nan"), float("inf"), -1, 0, "abc"):
            m, code, errors = ms.engine_measurements(_profile(neck_cm=bad), SHORT_BLOUSE)
            self.assertIsNone(m)
            self.assertEqual(code, "MEASUREMENTS_INVALID")
            self.assertIn("neck_cm", errors)

    def test_invalid_fabric_or_fit(self):
        m, code, errors = ms.engine_measurements(_profile(fabric_type="silk", fit_preference="tight"), SHORT_BLOUSE)
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
        self.assertEqual(profile["entered_fields"], list(ms.FIELD_KEYS))
        self.assertEqual(profile["bust_cm"], 88.0)
        self.assertEqual(profile["original_values"]["bust_cm"], {"value": 88.0, "unit": "cm"})
        self.assertEqual(profile["canonical_unit"], "cm")

    def test_inch_profile_stores_original_and_canonical(self):
        inches = {k: round(v / 2.54, 2) for k, v in VALID_CM.items()}
        resp = self._post(dict(inches, unit="in"))
        self.assertEqual(resp.status_code, 201, resp.get_json())
        saved = FakeProfile.saved[0]
        self.assertEqual(saved.unit, "in")
        self.assertAlmostEqual(saved.bust_cm, inches["bust_cm"] * 2.54, places=9)       # exact canonical cm
        self.assertEqual(saved.original_values["bust_cm"], {"value": inches["bust_cm"], "unit": "in"})
        self.assertEqual(saved.armhole_cm, saved.armhole_depth_cm)

    def test_large_inch_values_are_converted_not_clamped_or_rejected(self):
        resp = self._post(dict(VALID_CM, unit="in"))       # 88 in = 223.52 cm: unusual, but the user's value
        self.assertEqual(resp.status_code, 201, resp.get_json())
        self.assertAlmostEqual(FakeProfile.saved[0].bust_cm, 223.52, places=9)

    def test_field_level_errors_for_bad_inputs(self):
        payload = dict(VALID_CM, bust_cm="abc", waist_cm=-4, hip_cm=0, height_cm="Infinity", neck_cm=None)
        resp = self._post(payload)
        self.assertEqual(resp.status_code, 400)
        body = resp.get_json()
        self.assertEqual(body["error_code"], "MEASUREMENT_VALIDATION_FAILED")
        fe = body["field_errors"]
        self.assertEqual(fe["bust_cm"][0]["code"], "NOT_A_NUMBER")
        self.assertEqual(fe["waist_cm"][0]["code"], "NOT_POSITIVE")
        self.assertEqual(fe["hip_cm"][0]["code"], "NOT_POSITIVE")
        self.assertEqual(fe["height_cm"][0]["code"], "NOT_FINITE")
        self.assertNotIn("neck_cm", fe)          # not required without a design
        self.assertEqual(FakeProfile.saved, [])

    def test_decimals_are_accepted(self):
        resp = self._post({"bust_cm": "88.75", "waist_cm": 70.125})
        self.assertEqual(resp.status_code, 201, resp.get_json())
        self.assertEqual(FakeProfile.saved[0].bust_cm, 88.75)
        self.assertEqual(FakeProfile.saved[0].waist_cm, 70.125)

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

    def test_without_a_design_no_measurement_is_required(self):
        resp = self._post({"client_name": "X", "bust_cm": 88})
        self.assertEqual(resp.status_code, 201, resp.get_json())
        p = resp.get_json()["profile"]
        self.assertEqual(p["entered_fields"], ["bust_cm"])
        self.assertIsNone(p["neck_cm"])                     # nothing fabricated

    def test_with_a_design_exactly_its_measurements_are_required(self):
        resp = self._post({"client_name": "X", "design": SLEEVELESS_CROP, "bust_cm": 88})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(set(resp.get_json()["field_errors"]), set(BODICE) - {"bust_cm"})   # no hip/sleeve/height
        ok = self._post(dict({k: VALID_CM[k] for k in BODICE}, design=SLEEVELESS_CROP))
        self.assertEqual(ok.status_code, 201, ok.get_json())

    def test_short_sleeve_design_does_not_require_the_wrist(self):
        payload = {k: VALID_CM[k] for k in ms.required_for_design(SHORT_BLOUSE)}
        resp = self._post(dict(payload, design=SHORT_BLOUSE))
        self.assertEqual(resp.status_code, 201, resp.get_json())
        self.assertIsNone(FakeProfile.saved[0].wrist_cm)

    def test_invalid_design_is_rejected(self):
        resp = self._post({"bust_cm": 88, "design": {"garment_type": "dress"}})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("design", resp.get_json()["field_errors"])

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

    def _put(self, profile, payload):
        with patch("app.routes.measurements.MeasurementProfile") as mp:
            mp.objects.return_value.first.return_value = profile
            return self.client.put("/api/measurements/m1", json=payload, headers=_headers())

    def test_partial_update_converts_units_and_keeps_originals(self):
        profile = FakeProfile(**dict(VALID_CM, armhole_cm=20.0, original_values={
            "bust_cm": {"value": 88.0, "unit": "cm"}}))
        resp = self._put(profile, {"waist_cm": 27.5, "unit": "in"})
        self.assertEqual(resp.status_code, 200, resp.get_json())
        self.assertAlmostEqual(profile.waist_cm, 27.5 * 2.54, places=9)
        self.assertEqual(profile.original_values["waist_cm"], {"value": 27.5, "unit": "in"})
        self.assertEqual(profile.original_values["bust_cm"], {"value": 88.0, "unit": "cm"})   # preserved
        self.assertEqual(profile.bust_cm, 88.0)

    def test_update_rejects_bad_value_and_leaves_profile_untouched(self):
        profile = FakeProfile(**dict(VALID_CM, armhole_cm=20.0))
        resp = self._put(profile, {"bust_cm": "abc"})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(profile.bust_cm, 88.0)
        self.assertEqual(FakeProfile.saved, [])

    def test_update_with_a_design_checks_the_merged_profile(self):
        profile = FakeProfile(**dict({k: VALID_CM[k] for k in BODICE}, armhole_cm=20.0))
        resp = self._put(profile, {"waist_cm": 71.5, "design": SHORT_BLOUSE})   # hip, bicep, sleeve still missing
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(set(resp.get_json()["field_errors"]), {"hip_cm", "bicep_cm", "sleeve_cm"})
        self.assertEqual(profile.waist_cm, 70.0)                                  # untouched

    def test_schema_endpoint(self):
        resp = self.client.get("/api/measurements/schema", headers=_headers())
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.get_json()["fields"]), 13)
        self.assertEqual(resp.get_json()["requirement_rules"], ms.REQUIREMENTS["rules"])


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
        resp, eng, pr = self._generate(_profile(sleeve_cm=24.0, original_values={"bust_cm": {"value": 34.65, "unit": "in"}}))
        self.assertEqual(resp.status_code, 201, resp.get_json())
        passed = eng.call_args.args[0]
        for key in ms.FIELD_KEYS:
            self.assertEqual(passed[key], dict(VALID_CM, sleeve_cm=24.0)[key], key)
        snap = pr.call_args.kwargs["measurements_snapshot"]
        self.assertEqual(snap["canonical_cm"], dict(VALID_CM, sleeve_cm=24.0))
        self.assertEqual(snap["required_fields"], ms.required_for_design(CONFIRMED))
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

    def test_short_sleeve_design_generates_without_wrist_or_height(self):
        resp, eng, _ = self._generate(_profile(wrist_cm=None, height_cm=None, sleeve_cm=24.0))
        self.assertEqual(resp.status_code, 201, resp.get_json())
        self.assertIsNone(eng.call_args.args[0]["wrist_cm"])

    def test_measurements_that_cannot_be_drafted_are_reported_by_the_engine(self):
        resp, _, pr = self._generate(_profile(bust_cm=5.0, sleeve_cm=24.0))     # no range check, but no valid block
        self.assertEqual(resp.status_code, 422)
        self.assertIn(resp.get_json()["error_code"], ("MEASUREMENTS_NOT_DRAFTABLE", "BASE_BLOCK_INVALID",
                                                      "SLEEVE_TOO_WIDE_FOR_ARMHOLE", "DESIGN_MEASUREMENT_CONFLICT"))
        pr.assert_not_called()


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
            corrected = dict(CONFIRMED, neckline_type="square-neck", sleeve_length="long-sleeve")
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
        self.assertEqual(seen["f"]["sleeves"], "long sleeve")
        self.assertAlmostEqual(seen["m"]["bust_cm"], 88.0, delta=0.05)          # inches -> cm
        spec = pr.call_args.kwargs["design_spec"]
        self.assertEqual(spec["provenance"]["neckline_type"]["source"], "user_corrected")
        self.assertEqual(spec["provenance"]["neckline_type"]["predicted_confidence"], 0.5)
        snap = pr.call_args.kwargs["measurements_snapshot"]
        self.assertEqual(snap["original_values"]["bust_cm"]["unit"], "in")     # original preserved
        self.assertAlmostEqual(snap["canonical_cm"]["bust_cm"], 88.0, delta=0.05)


if __name__ == "__main__":
    unittest.main()
