"""
Phase 1 — design-feature contract.

Proves:
  * one taxonomy shared by classifier config, backend schema and frontend schema
  * user-corrected attributes are what the pattern engine receives (not raw ML output)
  * provenance + model confidence/checkpoint metadata are preserved
  * unsupported / stale / invalid designs are rejected, never silently replaced
"""

import json
import os
import re
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app
from flask_jwt_extended import create_access_token
from app.logic import feature_schema as fs
from app.logic.taxonomy_map import confirmed_to_cad_features

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

_APP = None


def _app():
    global _APP
    if _APP is None:
        _APP = create_app()
        _APP.config["TESTING"] = True
    return _APP


GOOD = {"garment_type": "blouse", "neckline_type": "round-neck",
        "sleeve_length": "short-sleeve", "sleeve_style": "regular-sleeve"}

PREDICTIONS = {
    "model_version": "YOLOv8MultiTaskClassifier|stage=Stage_B|epoch=7|sha256=3b69a470ed5d",
    "model_type": "image-level multi-task classifier",
    "checkpoint_sha256": "3b69a470ed5d" + "0" * 52,
    "predictions": {
        "garment_type": {"label": "blouse", "confidence": 0.91, "top_3": [], "requires_user_confirmation": False},
        "neckline_type": {"label": "v-neck", "confidence": 0.5026, "top_3": [], "requires_user_confirmation": False},
        "sleeve_length": {"label": "long-sleeve", "confidence": 0.62, "top_3": [], "requires_user_confirmation": False},
        "sleeve_style": {"label": "regular-sleeve", "confidence": 0.41, "top_3": [], "requires_user_confirmation": False},
    },
}


class TestTaxonomyParity(unittest.TestCase):
    def test_backend_schema_matches_classifier_config(self):
        with open(os.path.join(REPO_ROOT, "ai_training", "config", "classes.json"), encoding="utf-8") as f:
            cfg = json.load(f)["outputs"]
        for head in fs.HEADS:
            self.assertEqual(list(fs.TAXONOMY[head]), cfg[head]["classes"], head)

    def test_backend_schema_matches_model_head_sizes(self):
        from app.ai.multitask_classifier import DEFAULT_HEAD_DIMS, HEADS
        self.assertEqual(tuple(HEADS), fs.HEADS)
        for head in fs.HEADS:
            self.assertEqual(DEFAULT_HEAD_DIMS[head], len(fs.TAXONOMY[head]), head)

    def test_frontend_schema_matches_backend(self):
        text = open(os.path.join(REPO_ROOT, "frontend", "src", "utils", "designSchema.js"),
                    encoding="utf-8").read()
        block = text[text.index("export const DESIGN_SCHEMA"):text.index("/** { head: [{value,label}]")]
        found = {}
        for head in fs.HEADS:
            start = block.index(f"{head}: [")
            end = block.index("  ],", start)
            chunk = block[start:end]
            found[head] = re.findall(r"value: '([^']+)'.*?support: (IMPLEMENTED|APPROXIMATED|UNSUPPORTED)", chunk)
        level = {"IMPLEMENTED": fs.IMPLEMENTED, "APPROXIMATED": fs.APPROXIMATED, "UNSUPPORTED": fs.UNSUPPORTED}
        for head in fs.HEADS:
            self.assertEqual([v for v, _ in found[head]], list(fs.TAXONOMY[head]), head)
            for value, lvl in found[head]:
                self.assertEqual(level[lvl], fs.support_of(head, value)[0], f"{head}={value}")

    def test_frontend_review_component_uses_shared_schema(self):
        text = open(os.path.join(REPO_ROOT, "frontend", "src", "components", "PredictionReview.jsx"),
                    encoding="utf-8").read()
        self.assertIn("../utils/designSchema", text)
        self.assertNotIn("{ value: 'blouse'", text)   # no second, hand-copied taxonomy


class TestValidation(unittest.TestCase):
    def test_valid_set(self):
        clean, errors = fs.validate_attributes(GOOD)
        self.assertEqual(clean, GOOD)
        self.assertEqual(errors, {})

    def test_strips_whitespace_but_not_case(self):
        clean, _ = fs.validate_attributes(dict(GOOD, garment_type=" blouse "))
        self.assertEqual(clean["garment_type"], "blouse")
        _, errors = fs.validate_attributes(dict(GOOD, garment_type="Blouse"))
        self.assertEqual(errors["garment_type"]["code"], "NOT_IN_TAXONOMY")

    def test_missing_and_non_string(self):
        for bad in (None, "", 5, ["blouse"]):
            _, errors = fs.validate_attributes(dict(GOOD, neckline_type=bad))
            self.assertEqual(errors["neckline_type"]["code"], "REQUIRED")
        _, errors = fs.validate_attributes(None)
        self.assertEqual(set(errors), set(fs.HEADS))

    def test_unknown_value_names_allowed_values(self):
        _, errors = fs.validate_attributes(dict(GOOD, sleeve_style="mutton-sleeve"))
        self.assertIn("puff-sleeve", errors["sleeve_style"]["message"])

    def test_sleeveless_with_sleeve_style_is_inconsistent(self):
        _, errors = fs.validate_attributes(dict(GOOD, sleeve_length="sleeveless"))
        self.assertEqual(errors["sleeve_style"]["code"], "INCONSISTENT")
        clean, errors = fs.validate_attributes(dict(GOOD, sleeve_length="sleeveless", sleeve_style="none"))
        self.assertEqual(errors, {})

    def test_support_report_flags_unsupported_and_approximated(self):
        clean, _ = fs.validate_attributes(dict(GOOD, neckline_type="halter-neck", sleeve_style="puff-sleeve"))
        report = fs.support_report(clean)
        self.assertFalse(report["supported"])
        self.assertEqual({u["value"] for u in report["unsupported"]}, {"halter-neck", "puff-sleeve"})
        self.assertTrue(all(u["note"] for u in report["unsupported"]))
        self.assertIn("cannot be drafted", fs.unsupported_message(report))

    def test_plain_round_neck_blouse_is_supported(self):
        report = fs.support_report(GOOD)
        self.assertTrue(report["supported"])

    def test_engine_rejects_unsupported_sleeve_styles_instead_of_ignoring_them(self):
        """Defence in depth: even called directly, the engine refuses styles it cannot draft."""
        from app.logic.parametric_engine import ParametricEngine
        from app.logic.drafting.ease import DraftingError
        from tests.fixtures import measurements
        for style in ("puff-sleeve", "bell-sleeve", "bishop-sleeve"):
            with self.assertRaises(DraftingError) as ctx:
                ParametricEngine(measurements(), confirmed_to_cad_features(dict(GOOD, sleeve_style=style))).generate()
            self.assertEqual(ctx.exception.code, "UNSUPPORTED_DESIGN", style)


class TestDesignSpec(unittest.TestCase):
    def test_accepted_and_corrected_provenance_with_confidence(self):
        clean, _ = fs.validate_attributes(dict(GOOD, sleeve_length="short-sleeve"))  # model said long-sleeve
        spec = fs.build_design_spec(clean, PREDICTIONS, confirmed_to_cad_features(clean))
        prov = spec["provenance"]
        self.assertEqual(prov["garment_type"]["source"], "ml_prediction_confirmed")
        self.assertEqual(prov["neckline_type"]["source"], "user_corrected")
        self.assertEqual(prov["neckline_type"]["predicted_label"], "v-neck")
        self.assertEqual(prov["neckline_type"]["predicted_confidence"], 0.5026)   # real confidence kept
        self.assertEqual(prov["sleeve_length"]["source"], "user_corrected")
        self.assertEqual(spec["attributes"], clean)                               # user's values are canonical
        self.assertEqual(spec["model"]["checkpoint_sha256"], PREDICTIONS["checkpoint_sha256"])
        self.assertEqual(spec["rule_based_features"]["derived_from"], "garment_type")

    def test_manual_selection_has_no_invented_confidence(self):
        spec = fs.build_design_spec(GOOD, None, confirmed_to_cad_features(GOOD))
        for head in fs.HEADS:
            self.assertEqual(spec["provenance"][head], {"source": "manual_selection"})
        self.assertIsNone(spec["model"])


def _headers():
    with _app().app_context():
        return {"Authorization": f"Bearer {create_access_token(identity='user-1')}"}


def _image(confirmed=None, attrs=None, spec=None):
    img = SimpleNamespace(
        id="img1", user_id=SimpleNamespace(id="user-1"), file_path="x.jpg",
        garment_attributes=attrs if attrs is not None else PREDICTIONS,
        confirmed_attributes=confirmed or {}, design_spec=spec or {},
        detected_features={"source": "cv_heuristic"}, confidence_score=0.6, confirmed_at=None,
    )
    img.save = MagicMock()
    return img


class TestConfirmRoute(unittest.TestCase):
    def _confirm(self, payload, image):
        with patch("app.routes.images.DesignImage") as di:
            di.objects.return_value.first.return_value = image
            return _app().test_client().post("/api/images/img1/confirm-attributes",
                                             json=payload, headers=_headers())

    def test_user_correction_is_stored_with_provenance(self):
        image = _image()
        corrected = dict(GOOD, neckline_type="square-neck")      # model predicted v-neck
        resp = self._confirm(corrected, image)
        self.assertEqual(resp.status_code, 200)
        body = resp.get_json()
        self.assertEqual(body["confirmed_attributes"], corrected)
        self.assertEqual(image.confirmed_attributes, corrected)
        self.assertEqual(image.design_spec["provenance"]["neckline_type"]["source"], "user_corrected")
        self.assertEqual(image.design_spec["provenance"]["neckline_type"]["predicted_label"], "v-neck")
        self.assertEqual(image.garment_attributes, PREDICTIONS)   # raw model output untouched
        self.assertTrue(body["engine_support"]["supported"])

    def test_invalid_value_gives_field_errors(self):
        resp = self._confirm(dict(GOOD, neckline_type="cowl-neck"), _image())
        self.assertEqual(resp.status_code, 400)
        body = resp.get_json()
        self.assertEqual(body["error_code"], "INVALID_DESIGN_ATTRIBUTES")
        self.assertIn("neckline_type", body["field_errors"])

    def test_unsupported_design_can_be_recorded_but_is_flagged(self):
        resp = self._confirm(dict(GOOD, sleeve_style="puff-sleeve"), _image())
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.get_json()["engine_support"]["supported"])

    def test_schema_endpoint(self):
        resp = _app().test_client().get("/api/images/design-schema", headers=_headers())
        self.assertEqual(resp.status_code, 200)
        body = resp.get_json()
        self.assertEqual(set(body["heads"]), set(fs.HEADS))
        self.assertIn("not an object detector", body["model_type"])


MEAS = SimpleNamespace(
    id="m1", bust_cm=88.0, waist_cm=70.0, hip_cm=94.0, height_cm=162.0, neck_cm=36.0, shoulder_cm=12.0,
    across_back_cm=34.0, back_waist_length_cm=40.0, armhole_depth_cm=20.0, armhole_cm=20.0,
    garment_length_cm=65.0, bicep_cm=28.0, sleeve_cm=55.0, wrist_cm=16.0,
    fabric_type="woven", fit_preference="standard", unit="cm", original_values={},
)


class TestGenerateRoute(unittest.TestCase):
    def _generate(self, payload, image, engine=None):
        with patch("app.routes.patterns.User") as user_cls, \
             patch("app.routes.patterns.MeasurementProfile") as meas_cls, \
             patch("app.routes.patterns.DesignImage") as di, \
             patch("app.routes.patterns.Session") as sess, \
             patch("app.routes.patterns.PatternResult") as pr:
            user_cls.objects.return_value.first.return_value = object()
            meas_cls.objects.return_value.first.return_value = MEAS
            di.objects.return_value.first.return_value = image
            pr.return_value.id = "p1"
            sess.return_value.id = "s1"
            if engine:
                with patch("app.routes.patterns.ParametricEngine") as eng:
                    eng.side_effect = engine
                    resp = _app().test_client().post("/api/patterns/generate", json=payload, headers=_headers())
            else:
                resp = _app().test_client().post("/api/patterns/generate", json=payload, headers=_headers())
            return resp, pr, di

    def base(self, **extra):
        return dict({"measurement_id": "m1", "image_id": "img1", "fabric_id": "cotton-poplin"}, **extra)

    def _confirmed_image(self, confirmed):
        clean, _ = fs.validate_attributes(confirmed)
        spec = fs.build_design_spec(clean, PREDICTIONS, confirmed_to_cad_features(clean))
        return _image(confirmed=clean, spec=spec)

    def test_user_corrected_attributes_reach_the_engine_and_are_stored(self):
        corrected = dict(GOOD, neckline_type="square-neck")   # model predicted v-neck
        image = self._confirmed_image(corrected)
        seen = {}
        from app.logic.parametric_engine import ParametricEngine as Real

        def capture(measurements, features, design_spec=None):
            seen["features"], seen["measurements"] = features, measurements
            return Real(measurements, features, design_spec=design_spec)

        resp, pr, _ = self._generate(self.base(), image, engine=capture)
        self.assertEqual(resp.status_code, 201, resp.get_json())
        self.assertEqual(seen["features"]["neckline"], "square neck")        # corrected, not "v-neck"
        self.assertEqual(seen["features"]["garment_type"], "blouse")
        saved_spec = pr.call_args.kwargs["design_spec"]
        self.assertEqual(saved_spec["attributes"], corrected)
        self.assertEqual(saved_spec["provenance"]["neckline_type"]["source"], "user_corrected")
        self.assertEqual(resp.get_json()["design_spec"]["attributes"], corrected)

    def test_client_supplied_detected_features_are_ignored(self):
        image = self._confirmed_image(GOOD)
        seen = {}
        from app.logic.parametric_engine import ParametricEngine as Real

        def capture(m, f, design_spec=None):
            seen["features"] = f
            return Real(m, f, design_spec=design_spec)

        resp, _, _ = self._generate(
            self.base(detected_features={"neckline": "halter neck", "sleeves": "sleeveless"}), image, engine=capture)
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(seen["features"]["neckline"], "round neck")
        self.assertEqual(seen["features"]["sleeves"], "short sleeve")

    def test_unsupported_design_is_rejected_not_replaced(self):
        image = self._confirmed_image(dict(GOOD, neckline_type="halter-neck", sleeve_style="puff-sleeve"))
        resp, pr, _ = self._generate(self.base(), image)
        self.assertEqual(resp.status_code, 422)
        body = resp.get_json()
        self.assertEqual(body["error_code"], "UNSUPPORTED_DESIGN")
        self.assertEqual({u["value"] for u in body["unsupported_features"]}, {"halter-neck", "puff-sleeve"})
        pr.assert_not_called()

    def test_unconfirmed_design_is_rejected(self):
        resp, pr, _ = self._generate(self.base(), _image(confirmed={}))
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.get_json()["error_code"], "DESIGN_NOT_CONFIRMED")
        pr.assert_not_called()

    def test_stale_client_confirmation_is_rejected(self):
        image = self._confirmed_image(GOOD)   # server confirmed round-neck
        stale = dict(GOOD, neckline_type="v-neck")
        resp, pr, _ = self._generate(self.base(confirmed_attributes=stale), image)
        self.assertEqual(resp.status_code, 409)
        self.assertEqual(resp.get_json()["error_code"], "CONFIRMED_DESIGN_MISMATCH")
        pr.assert_not_called()

    def test_matching_client_confirmation_is_accepted(self):
        image = self._confirmed_image(GOOD)
        resp, _, _ = self._generate(self.base(confirmed_attributes=GOOD), image)
        self.assertEqual(resp.status_code, 201)

    def test_manual_mode_validates_client_attributes(self):
        resp, pr, di = self._generate(
            self.base(image_id="manual", confirmed_attributes=dict(GOOD, neckline_type="cowl-neck")), _image())
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.get_json()["error_code"], "INVALID_DESIGN_ATTRIBUTES")
        pr.assert_not_called()

    def test_manual_mode_without_attributes_is_rejected(self):
        resp, _, _ = self._generate(self.base(image_id="manual"), _image())
        self.assertEqual(resp.status_code, 400)

    def test_manual_mode_records_manual_provenance(self):
        resp, pr, _ = self._generate(self.base(image_id="manual", confirmed_attributes=GOOD), _image())
        self.assertEqual(resp.status_code, 201, resp.get_json())
        spec = pr.call_args.kwargs["design_spec"]
        self.assertEqual(spec["provenance"]["garment_type"], {"source": "manual_selection"})


if __name__ == "__main__":
    unittest.main()
