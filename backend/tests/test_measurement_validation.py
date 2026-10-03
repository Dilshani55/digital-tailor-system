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
    # what the drafting method uses
    "bust_cm": 88.0, "waist_cm": 70.0, "hip_cm": 94.0, "shoulder_width_cm": 37.0, "back_waist_length_cm": 40.0,
    "shoulder_to_bust_cm": 25.0, "bust_point_distance_cm": 18.0, "waist_to_hip_cm": 20.0, "garment_length_cm": 65.0,
    "bicep_cm": 28.0, "sleeve_cm": 55.0, "sleeve_end_cm": 16.0,
    # design values (optional: empty = calculated)
    "neck_width_cm": 15.0, "front_neck_depth_cm": 8.0, "back_neck_depth_cm": 2.5, "armhole_depth_cm": 20.0,
    # legacy measurements of earlier versions: stored, never required, not used by the drafting method
    "neck_cm": 36.0, "height_cm": 162.0, "shoulder_cm": 12.0, "across_back_cm": 34.0, "wrist_cm": 16.0,
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


SLEEVELESS_BLOUSE = {"garment_type": "blouse", "neckline_type": "round-neck",
                   "sleeve_length": "sleeveless", "sleeve_style": "none"}
SHORT_BLOUSE = {"garment_type": "blouse", "neckline_type": "round-neck",
                "sleeve_length": "short-sleeve", "sleeve_style": "regular-sleeve"}
LONG_TSHIRT = {"garment_type": "t-shirt", "neckline_type": "round-neck",
               "sleeve_length": "long-sleeve", "sleeve_style": "regular-sleeve"}
LONG_PUFF = {"garment_type": "blouse", "neckline_type": "v-neck",
             "sleeve_length": "long-sleeve", "sleeve_style": "puff-sleeve"}
BODICE = ["bust_cm", "waist_cm", "shoulder_width_cm", "back_waist_length_cm", "garment_length_cm"]
BELOW_WAIST = ["hip_cm", "waist_to_hip_cm"]
DESIGN_VALUES = ["bust_point_distance_cm", "neck_width_cm", "front_neck_depth_cm", "back_neck_depth_cm", "armhole_depth_cm"]


class TestSchemaDefinition(unittest.TestCase):
    def test_sixteen_active_fields_five_legacy_plain_labels_and_no_rejecting_ranges(self):
        self.assertEqual(len(ms.ACTIVE_KEYS), 16)
        self.assertEqual(ms.LEGACY_KEYS, ("neck_cm", "height_cm", "shoulder_cm", "across_back_cm", "wrist_cm"))
        self.assertEqual(set(ms.FIELD_KEYS), set(VALID_CM))
        self.assertEqual(ms.LABELS["sleeve_cm"], "Sleeve length")            # not "full arm"
        self.assertEqual(ms.LABELS["bust_cm"], "Bust around")                 # plain words, not jargon
        self.assertEqual(ms.LABELS["bicep_cm"], "Upper arm around")
        self.assertEqual(ms.LABELS["sleeve_end_cm"], "Sleeve end around")
        self.assertEqual(ms.LABELS["back_waist_length_cm"], "Back neck to waist")
        for label in ms.LABELS.values():
            for jargon in ("circumference", "girth", "thoracic", "posterior", "distal", "parameter"):
                self.assertNotIn(jargon, label.lower())
        self.assertEqual({k for k, v in ms.KIND.items() if v == "design"}, set(DESIGN_VALUES))
        self.assertFalse(hasattr(ms, "get_ranges"))
        self.assertFalse(hasattr(ms, "validate_canonical"))

    def test_every_field_has_a_how_to_measure_guide_and_a_common_mistake(self):
        for f in ms.REQUIREMENTS["fields"]:
            self.assertGreater(len(f["guide"]), 40, f["key"])
            self.assertGreater(len(f["mistake"]), 15, f["key"])
            self.assertIn(f["view"], ("front", "back"), f["key"])
            self.assertIn(f["group"], [g["key"] for g in ms.REQUIREMENTS["groups"]], f["key"])
        views = {f["view"] for f in ms.REQUIREMENTS["fields"]}
        self.assertEqual(views, {"front", "back"})                            # both views are used

    def test_canonical_unit_is_cm_and_units_are_cm_in(self):
        self.assertEqual(ms.CANONICAL_UNIT, "cm")
        self.assertEqual(ms.UNITS, ("cm", "in"))
        self.assertEqual(ms.CM_PER_INCH, 2.54)

    def test_schema_payload(self):
        p = ms.schema_payload()
        self.assertEqual(len(p["fields"]), 16)
        self.assertEqual(p["requirement_rules"], ms.REQUIREMENTS["rules"])
        self.assertNotIn("min_cm", p["fields"][0])
        self.assertEqual(set(p["fields"][0]), {"key", "label", "description", "group", "kind", "view", "common_mistake"})
        self.assertEqual(p["schema_version"], 3)


class TestRequiredForDesign(unittest.TestCase):
    """The design decides which measurements are needed - derived from what the drafting engine uses."""

    def test_sleeveless_blouse_needs_the_bodice_and_hip_but_no_sleeve_measurements(self):
        req = ms.required_for_design(SLEEVELESS_BLOUSE)
        self.assertEqual(set(req), set(BODICE) | set(BELOW_WAIST) | {"shoulder_to_bust_cm"})   # no arm measurements

    def test_short_sleeve_needs_bicep_and_sleeve_length_but_not_wrist(self):
        req = ms.required_for_design(SHORT_BLOUSE)
        self.assertIn("bicep_cm", req)
        self.assertIn("sleeve_cm", req)
        self.assertIn("sleeve_end_cm", req)                # the sleeve narrows to the arm where it ends
        self.assertIn("hip_cm", req)                       # hem below the waist
        self.assertNotIn("wrist_cm", req)
        self.assertNotIn("height_cm", req)

    def test_every_sleeve_needs_its_end_measurement_and_a_sleeveless_design_none(self):
        self.assertIn("sleeve_end_cm", ms.required_for_design(LONG_TSHIRT))
        self.assertIn("sleeve_end_cm", ms.required_for_design(LONG_PUFF))
        self.assertNotIn("sleeve_end_cm", ms.required_for_design(SLEEVELESS_BLOUSE))

    def test_only_a_woven_blouse_needs_the_bust_point(self):
        self.assertIn("shoulder_to_bust_cm", ms.required_for_design(SHORT_BLOUSE))
        self.assertNotIn("shoulder_to_bust_cm", ms.required_for_design(LONG_TSHIRT))

    def test_design_values_and_legacy_measurements_are_never_required(self):
        import itertools
        for gt, sl, ss in itertools.product(("blouse", "t-shirt"), ("sleeveless", "short-sleeve", "long-sleeve"),
                                            ("none", "regular-sleeve", "puff-sleeve")):
            req = ms.required_for_design({"garment_type": gt, "neckline_type": "round-neck", "sleeve_length": sl, "sleeve_style": ss})
            self.assertFalse(set(req) & (set(DESIGN_VALUES) | set(ms.LEGACY_KEYS)), (gt, sl, ss))

    def test_height_is_never_required(self):
        import itertools
        for gt, sl, ss in itertools.product(("blouse", "t-shirt"), ("sleeveless", "short-sleeve", "long-sleeve"),
                                            ("none", "regular-sleeve", "puff-sleeve")):
            self.assertNotIn("height_cm", ms.required_for_design(
                {"garment_type": gt, "neckline_type": "round-neck", "sleeve_length": sl, "sleeve_style": ss}))

    def test_every_required_set_drafts_and_nothing_less_is_invented(self):
        """With exactly the required fields the engine drafts; the unrequired ones stay None."""
        from app.logic.parametric_engine import ParametricEngine
        for design, length in ((SLEEVELESS_BLOUSE, 62.0), (SHORT_BLOUSE, 62.0), (LONG_TSHIRT, 62.0), (LONG_PUFF, 62.0)):
            req = ms.required_for_design(design)
            m = {k: (VALID_CM[k] if k in req else None) for k in ms.FIELD_KEYS}
            m["garment_length_cm"] = length
            if design["sleeve_length"] == "short-sleeve":
                m["sleeve_cm"], m["sleeve_end_cm"] = 24.0, 27.0
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

    def test_round_trip_cm_inch_cm_keeps_the_value(self):
        for cm in (88.0, 70.25, 37.3, 0.5, 162.56):
            inches = cm / ms.CM_PER_INCH
            self.assertAlmostEqual(ms.to_cm(inches, "in"), cm, places=9)
        self.assertEqual(ms.to_cm(1, "in"), 2.54)
        self.assertEqual(ms.to_cm(10, "cm"), 10.0)


class TestWarnings(unittest.TestCase):
    """Unusual values are WARNED about, never rejected and never changed."""

    def test_usual_measurements_give_no_warning(self):
        usual = {k: v for k, v in VALID_CM.items() if k in ms.ACTIVE_KEYS}
        self.assertEqual(ms.measurement_warnings(usual), [])

    def test_a_value_outside_the_usual_range_warns_and_names_the_unit(self):
        w = ms.measurement_warnings({"bust_cm": 34.0})                 # inches typed while cm was selected
        self.assertEqual([(x["field"], x["code"]) for x in w], [("bust_cm", "UNUSUAL_VALUE")])
        self.assertIn("unit", w[0]["message"])
        self.assertEqual(ms.measurement_warnings({"bust_cm": 223.52})[0]["code"], "UNUSUAL_VALUE")

    def test_proportion_warnings(self):
        codes = lambda m: {(x["field"], x["code"]) for x in ms.measurement_warnings(m)}   # noqa: E731
        self.assertIn(("shoulder_width_cm", "CHECK_PROPORTION"), codes({"bust_cm": 88, "shoulder_width_cm": 46}))
        self.assertIn(("sleeve_end_cm", "CHECK_PROPORTION"), codes({"bicep_cm": 28, "sleeve_end_cm": 31}))
        self.assertIn(("garment_length_cm", "CHECK_PROPORTION"), codes({"back_waist_length_cm": 40, "garment_length_cm": 36}))
        self.assertIn(("shoulder_to_bust_cm", "CHECK_PROPORTION"), codes({"back_waist_length_cm": 40, "shoulder_to_bust_cm": 41}))

    def test_no_judgement_about_the_body(self):
        text = repr(ms.measurement_warnings({"bust_cm": 150, "waist_cm": 140, "hip_cm": 165})).lower()
        for word in ("bmi", "overweight", "underweight", "obese", "too fat", "too thin"):
            self.assertNotIn(word, text)

    def test_parse_errors_are_field_level(self):
        _, _, errors = ms.convert_input({"bust_cm": "abc", "waist_cm": -3, "hip_cm": float("nan")}, "cm")
        self.assertEqual(_codes(errors, "bust_cm"), ["NOT_A_NUMBER"])
        self.assertEqual(_codes(errors, "waist_cm"), ["NOT_POSITIVE"])
        self.assertEqual(_codes(errors, "hip_cm"), ["NOT_FINITE"])


class _Profile(SimpleNamespace):
    pass


def _profile(**over):
    base = dict(VALID_CM, armhole_cm=None, fabric_type="woven", fit_preference="standard", original_values={})
    base.update(over)
    return _Profile(**base)


class TestEngineMeasurements(unittest.TestCase):
    def test_complete_valid_profile(self):
        m, code, errors = ms.engine_measurements(_profile(), LONG_TSHIRT)
        self.assertEqual((code, errors), (None, {}))
        for key in ms.FIELD_KEYS:
            self.assertEqual(m[key], VALID_CM[key])
        self.assertEqual(m["fabric_type"], "woven")
        self.assertEqual(m["required_fields"], ms.required_for_design(LONG_TSHIRT))

    def test_missing_required_measurement_is_never_defaulted(self):
        for key in ms.required_for_design(LONG_TSHIRT):
            m, code, errors = ms.engine_measurements(_profile(**{"wrist_cm": None, key: None}), LONG_TSHIRT)
            self.assertIsNone(m, key)
            self.assertEqual(code, "MEASUREMENTS_INCOMPLETE")
            self.assertEqual(list(errors), [key])

    def test_measurements_the_design_does_not_need_may_be_missing(self):
        m, code, errors = ms.engine_measurements(
            _profile(height_cm=None, bicep_cm=None, sleeve_cm=None, wrist_cm=None, sleeve_end_cm=None,
                     front_neck_depth_cm=None, armhole_depth_cm=None), SLEEVELESS_BLOUSE)
        self.assertEqual((code, errors), (None, {}))
        for key in ("height_cm", "bicep_cm", "sleeve_cm", "wrist_cm", "sleeve_end_cm", "front_neck_depth_cm", "armhole_depth_cm"):
            self.assertIsNone(m[key])                                  # passed as missing, never invented

    def test_an_old_profile_is_asked_for_the_new_measurements_not_estimated(self):
        old = _profile(shoulder_width_cm=None, shoulder_to_bust_cm=None, waist_to_hip_cm=None, sleeve_end_cm=None,
                       bust_point_distance_cm=None, neck_width_cm=None, front_neck_depth_cm=None, back_neck_depth_cm=None)
        m, code, errors = ms.engine_measurements(old, SHORT_BLOUSE)       # still has neck, shoulder, across-back, wrist
        self.assertIsNone(m)
        self.assertEqual(code, "MEASUREMENTS_INCOMPLETE")
        self.assertEqual(set(errors), {"shoulder_width_cm", "shoulder_to_bust_cm", "waist_to_hip_cm", "sleeve_end_cm"})
        self.assertIn("Shoulder to shoulder", errors["shoulder_width_cm"][0]["message"])

    def test_the_wrist_of_an_old_profile_is_the_sleeve_end_of_a_long_sleeve_only(self):
        old = _profile(sleeve_end_cm=None, wrist_cm=15.5)
        m, code, _ = ms.engine_measurements(old, LONG_TSHIRT)
        self.assertIsNone(code)
        self.assertEqual(m["sleeve_end_cm"], 15.5)                     # a long sleeve ends at the wrist
        m, code, errors = ms.engine_measurements(old, SHORT_BLOUSE)    # a short sleeve does not
        self.assertEqual(code, "MEASUREMENTS_INCOMPLETE")
        self.assertEqual(list(errors), ["sleeve_end_cm"])

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
        need = set(BODICE) | set(BELOW_WAIST) | {"shoulder_to_bust_cm"}
        resp = self._post({"client_name": "X", "design": SLEEVELESS_BLOUSE, "bust_cm": 88})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(set(resp.get_json()["field_errors"]), need - {"bust_cm"})          # no sleeve/wrist/height
        ok = self._post(dict({k: VALID_CM[k] for k in need}, design=SLEEVELESS_BLOUSE))
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
        resp = self._put(profile, {"waist_cm": 71.5, "design": SHORT_BLOUSE})   # hip, bust point, sleeve ... still missing
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(set(resp.get_json()["field_errors"]),
                         {"hip_cm", "waist_to_hip_cm", "shoulder_to_bust_cm", "bicep_cm", "sleeve_cm", "sleeve_end_cm"})
        self.assertEqual(profile.waist_cm, 70.0)                                  # untouched

    def test_a_design_value_can_be_emptied_again_but_a_measurement_cannot(self):
        profile = FakeProfile(**dict(VALID_CM, original_values={"armhole_depth_cm": {"value": 20.0, "unit": "cm"}}))
        resp = self._put(profile, {"clear": ["armhole_depth_cm", "neck_width_cm"]})
        self.assertEqual(resp.status_code, 200, resp.get_json())
        self.assertIsNone(profile.armhole_depth_cm)                              # empty again: the calculated value is used
        self.assertIsNone(profile.neck_width_cm)
        self.assertNotIn("armhole_depth_cm", profile.original_values)
        self.assertEqual(profile.bust_cm, 88.0)                                  # nothing else touched
        # a value sent in the same request wins over "clear"
        resp = self._put(profile, {"front_neck_depth_cm": 9, "clear": ["front_neck_depth_cm"]})
        self.assertEqual(resp.status_code, 200, resp.get_json())
        self.assertEqual(profile.front_neck_depth_cm, 9.0)
        # body measurements are never cleared this way
        saved = len(FakeProfile.saved)
        resp = self._put(profile, {"clear": ["bust_cm"]})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(_codes(resp.get_json()["field_errors"], "clear"), ["INVALID_CLEAR"])
        self.assertEqual(profile.bust_cm, 88.0)
        self.assertEqual(len(FakeProfile.saved), saved)

    def test_schema_endpoint(self):
        resp = self.client.get("/api/measurements/schema", headers=_headers())
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.get_json()["fields"]), 16)
        self.assertEqual(resp.get_json()["requirement_rules"], ms.REQUIREMENTS["rules"])

    def test_saving_returns_warnings_but_still_saves(self):
        resp = self._post({"client_name": "X", "bust_cm": 34, "waist_cm": 70})       # bust probably typed in inches
        self.assertEqual(resp.status_code, 201, resp.get_json())
        self.assertEqual(FakeProfile.saved[0].bust_cm, 34.0)                          # saved as entered, not changed
        warnings = resp.get_json()["warnings"]
        self.assertEqual([w["field"] for w in warnings], ["bust_cm"])
        self.assertEqual(self._post({"bust_cm": 88, "waist_cm": 70}).get_json()["warnings"], [])


# ── pattern generation only ever sees validated measurements ─────────────────
CONFIRMED = {"garment_type": "blouse", "neckline_type": "round-neck",
             "sleeve_length": "short-sleeve", "sleeve_style": "regular-sleeve"}


class TestGenerateUsesValidatedMeasurements(unittest.TestCase):
    def _generate(self, profile, engine=None, body=None):
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
            eng.side_effect = engine or (lambda m, f, **kw: Real(m, f, **kw))
            resp = _app().test_client().post("/api/patterns/generate", headers=_headers(), json=dict({
                "measurement_id": "m1", "image_id": "img1", "fabric_id": "cotton-poplin"}, **(body or {})))
            return resp, eng, pr

    def test_response_explains_the_pattern_and_the_same_is_stored_with_it(self):
        resp, _, pr = self._generate(_profile(sleeve_cm=24.0, sleeve_end_cm=27.0, armhole_depth_cm=None,
                                              neck_width_cm=None, front_neck_depth_cm=None, back_neck_depth_cm=None),
                                     body={"display_unit": "in"})
        self.assertEqual(resp.status_code, 201, resp.get_json())
        body = resp.get_json()
        for key in ("drafting_method", "units", "ease", "why_this_size", "armhole_lengths", "sleeve_cap",
                    "seam_allowances_cm", "derived_measurements", "warnings", "validation"):
            self.assertIn(key, body, key)
        method = body["drafting_method"]                                         # only the source that was read is named
        self.assertIn("Pattern Making and Grading", method["source"]["title"])
        self.assertNotIn("Aldrich", method["name"] + str(method["source"]))
        self.assertIn("not Winifred Aldrich", method["note"])
        lengths = body["armhole_lengths"]
        self.assertAlmostEqual(lengths["front_armhole_curve_cm"] + lengths["back_armhole_curve_cm"], lengths["total_armhole_cm"], places=1)
        self.assertNotAlmostEqual(lengths["front_armhole_curve_cm"], lengths["back_armhole_curve_cm"], places=1)   # front and back are not the same curve
        cap = body["sleeve_cap"]
        self.assertIn(cap["status"], ("PASS", "REVIEW"))
        self.assertAlmostEqual(cap["sleeve_cap_seam_cm"] - cap["bodice_armhole_seam_cm"], cap["difference_cm"], places=1)
        rows = {r["id"]: r for r in body["why_this_size"]}
        self.assertIn("88", rows["front_bust_width"]["formula"])                 # traceable to the customer's bust
        stored = pr.call_args.kwargs
        self.assertEqual(stored["drafting_info"]["why_this_size"], body["why_this_size"])
        self.assertEqual(stored["drafting_info"]["sleeve_cap"], cap)
        self.assertEqual(stored["measurements_snapshot"]["display_unit"], "in")
        self.assertEqual(stored["measurements_snapshot"]["canonical_unit"], "cm")       # geometry stays in cm

    def test_display_unit_defaults_to_cm_and_unknown_units_are_ignored(self):
        for sent in (None, "furlong"):
            _, _, pr = self._generate(_profile(sleeve_cm=24.0, sleeve_end_cm=27.0), body={"display_unit": sent} if sent else None)
            self.assertEqual(pr.call_args.kwargs["measurements_snapshot"]["display_unit"], "cm")

    def test_seam_allowances_can_be_set_per_edge_and_bad_values_are_refused(self):
        profile = _profile(sleeve_cm=24.0, sleeve_end_cm=27.0)
        default = self._generate(profile)[0].get_json()
        resp, _, _ = self._generate(profile, body={"seam_allowances": {"side": 2.0}})
        self.assertEqual(resp.status_code, 201, resp.get_json())
        changed = resp.get_json()
        self.assertEqual(changed["seam_allowances_cm"]["side"], 2.0)
        self.assertEqual(default["seam_allowances_cm"]["side"], 1.5)
        self.assertEqual(changed["seam_allowances_cm"]["armhole"], default["seam_allowances_cm"]["armhole"])
        # the sewing line (the fit) is the same; only the cutting line moves
        a = next(p for p in default["pattern_pieces"] if p["piece_type"] == "front_bodice")
        b = next(p for p in changed["pattern_pieces"] if p["piece_type"] == "front_bodice")
        self.assertEqual(a["outline"], b["outline"])
        self.assertNotEqual(a["cutting_line"], b["cutting_line"])
        bad, _, pr = self._generate(profile, body={"seam_allowances": {"side": -1}})
        self.assertEqual(bad.status_code, 422, bad.get_json())
        self.assertEqual(bad.get_json()["error_code"], "INVALID_SEAM_ALLOWANCE")
        pr.assert_not_called()

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
        resp, eng, pr = self._generate(_profile(shoulder_width_cm=None, bicep_cm=None, neck_cm=None))
        self.assertEqual(resp.status_code, 422)
        body = resp.get_json()
        self.assertEqual(body["error_code"], "MEASUREMENTS_INCOMPLETE")
        self.assertEqual(set(body["field_errors"]), {"shoulder_width_cm", "bicep_cm"})    # the unused neck is not asked for
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
