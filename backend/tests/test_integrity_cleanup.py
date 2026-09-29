"""
Regression tests for the research-integrity cleanup (Step 1).

Each test guards against a previously discovered fake value or hidden fallback:
  1. legacy detector returned invented confidence (0.93 / 0.90-0.96 / 0.92)
  2. unknown fabric_id silently became cotton-poplin
  3. an unplaceable piece was dropped and a hard-coded 50 cm "success" returned
  4. research API returned invented metrics (0.91, 0.93/0.90/0.91, 2.5 m baseline...)
  5. multitask model_version was hard-coded regardless of checkpoint
"""

import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from PIL import Image

from app import create_app
from flask_jwt_extended import create_access_token
from app.logic.nesting_algorithm import NestingAlgorithm, NestingError
from app.logic.research_metrics import (
    compute_feature_corrections, load_model_evaluation, mean_or_none,
)
from app.models.research_record import ResearchRecord, METRICS_INTEGRITY_VERSION


def _piece(name, w, h, qty=1, fold=False):
    return {
        "name": name,
        "bounding_box": {"width_cm": w, "height_cm": h},
        "outline": [(0, 0), (w, 0), (w, h), (0, h)],
        "cut_count": qty,
        "cut_on_fold": fold,
        "seam_allowance_cm": 1.5,
    }


_APP = None   # create_app() opens a (lazy) Mongo client; build it once for the module


class AppTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        global _APP
        if _APP is None:
            _APP = create_app()
            _APP.config["TESTING"] = True
        cls.app = _APP
        with cls.app.app_context():
            token = create_access_token(identity="user-1")
        cls.headers = {"Authorization": f"Bearer {token}"}


# ── 1. Detector confidence ────────────────────────────────────────────────────
class TestDetectorHasNoFakeConfidence(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.img = os.path.join(self.tmp, "g.jpg")
        Image.new("RGB", (200, 300), color=(180, 40, 60)).save(self.img)

    def test_no_trained_detector_means_no_confidence(self):
        from app.ai import yolo_detector
        with patch.object(yolo_detector, "get_model", return_value=None):
            features, conf = yolo_detector.detect_features(self.img)
        self.assertIsNone(conf, "heuristic output must not carry an invented confidence")
        self.assertIn(features["source"], ("cv_heuristic", "default_not_detected"))
        self.assertNotIn("is_mock", features)

    def test_unreadable_image_is_flagged_not_detected(self):
        from app.ai import yolo_detector
        with patch.object(yolo_detector, "get_model", return_value=None):
            features, conf = yolo_detector.detect_features(os.path.join(self.tmp, "missing.jpg"))
        self.assertIsNone(conf)
        self.assertEqual(features["source"], "default_not_detected")

    def test_detector_with_no_detections_has_no_confidence(self):
        from app.ai import yolo_detector
        stub_result = SimpleNamespace(boxes=[])
        stub_model = MagicMock()
        stub_model.predict.return_value = [stub_result]
        with patch.object(yolo_detector, "get_model", return_value=stub_model):
            _, conf = yolo_detector.detect_features(self.img)
        self.assertIsNone(conf)

    def test_features_are_native_types_so_mongodb_can_store_them(self):
        """Regression: real photos produced np.bool_ which made /analyse fail with bson InvalidDocument."""
        import numpy as np
        import bson
        from app.ai import yolo_detector
        numpy_heavy = {"neckline": "round neck", "is_crop_top": np.bool_(True),
                       "aspect": np.float32(0.8), "nested": {"flag": np.bool_(False)}, "n": np.int64(3)}
        with patch.object(yolo_detector, "_heuristic_features", return_value=numpy_heavy),              patch.object(yolo_detector, "get_model", return_value=None):
            features, conf = yolo_detector.detect_features(self.img)
        bson.encode(features)                       # would raise InvalidDocument for numpy types
        self.assertIs(type(features["is_crop_top"]), bool)
        self.assertIs(type(features["nested"]["flag"]), bool)
        self.assertIsNone(conf)

    def test_no_invented_constants_in_source(self):
        src = open(os.path.join(os.path.dirname(__file__), "..", "app", "ai", "yolo_detector.py"),
                   encoding="utf-8").read()
        for fake in ("return geom, 0.93", "0.91 + raw_best", ", 0.92", "is_mock"):
            self.assertNotIn(fake, src)


# ── 2. Fabric fallback ────────────────────────────────────────────────────────
class TestFabricIdNotSilentlyReplaced(AppTestCase):
    def _post(self, payload):
        with patch("app.routes.patterns.User") as user_cls, \
             patch("app.routes.patterns.MeasurementProfile") as meas_cls, \
             patch("app.routes.patterns.PatternResult") as pattern_cls:
            user_cls.objects.return_value.first.return_value = object()
            resp = self.app.test_client().post(
                "/api/patterns/generate", json=payload, headers=self.headers)
            return resp, meas_cls, pattern_cls

    def test_unknown_fabric_id_is_rejected(self):
        resp, meas_cls, pattern_cls = self._post(
            {"measurement_id": "m1", "image_id": "i1", "fabric_id": "unobtainium-silk"})
        self.assertEqual(resp.status_code, 400)
        body = resp.get_json()
        self.assertEqual(body["error_code"], "INVALID_FABRIC_ID")
        self.assertIn("unobtainium-silk", body["error"])
        self.assertNotIn("selected_fabric_id", body)
        pattern_cls.assert_not_called()     # nothing generated / saved
        meas_cls.objects.assert_not_called()

    def test_missing_fabric_id_is_rejected_not_defaulted(self):
        resp, _, pattern_cls = self._post({"measurement_id": "m1", "image_id": "i1"})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.get_json()["error_code"], "FABRIC_ID_REQUIRED")
        pattern_cls.assert_not_called()

    def test_valid_fabric_id_passes_fabric_validation(self):
        # Gets past fabric validation; then stops at the (mocked, empty) measurement lookup.
        with patch("app.routes.patterns.User") as user_cls, \
             patch("app.routes.patterns.MeasurementProfile") as meas_cls:
            user_cls.objects.return_value.first.return_value = object()
            meas_cls.objects.return_value.first.return_value = None
            resp = self.app.test_client().post(
                "/api/patterns/generate",
                json={"measurement_id": "m1", "image_id": "i1", "fabric_id": "satin"},
                headers=self.headers)
        self.assertEqual(resp.status_code, 404)   # measurement not found, NOT a fabric error
        self.assertEqual(resp.get_json()["error"], "Measurement profile not found")


# ── 3. Nesting failure ────────────────────────────────────────────────────────
class TestNestingFailsExplicitly(AppTestCase):
    def test_piece_wider_than_fabric_raises_with_details(self):
        pieces = [_piece("Front Bodice", 30, 60), _piece("Huge Panel", 200, 50)]
        with self.assertRaises(NestingError) as ctx:
            NestingAlgorithm(pieces, 114, "woven", "open").run()
        err = ctx.exception
        self.assertEqual(err.error_code, "PIECE_DOES_NOT_FIT")
        names = [f["name"] for f in err.failed_pieces]
        self.assertEqual(names, ["Huge Panel"])
        self.assertIn("usable", err.failed_pieces[0]["reason"])
        self.assertNotIn("fabric_length_cm", err.details)   # never a fabricated requirement

    def test_folded_mode_uses_half_width_and_reports_it(self):
        pieces = [_piece("Wide Piece", 70, 40)]     # fits 114 open, not 57 folded
        NestingAlgorithm(pieces, 114, "woven", "open").run()   # succeeds
        with self.assertRaises(NestingError) as ctx:
            NestingAlgorithm(pieces, 114, "woven", "folded").run()
        self.assertIn("folded", ctx.exception.failed_pieces[0]["reason"])

    def test_no_pieces_is_an_error(self):
        with self.assertRaises(NestingError) as ctx:
            NestingAlgorithm([], 114, "woven", "open").run()
        self.assertEqual(ctx.exception.error_code, "NO_PIECES")

    def test_invalid_fabric_width_is_an_error(self):
        for bad in (0, -5, "abc", None):
            with self.assertRaises(NestingError):
                NestingAlgorithm([_piece("A", 10, 10)], bad)

    def test_successful_nesting_is_unchanged(self):
        result = NestingAlgorithm([_piece("A", 30, 40), _piece("B", 30, 40)], 114, "woven", "open").run()
        self.assertEqual(result["total_pieces"], 2)
        self.assertGreater(result["fabric_length_cm"], 0)
        self.assertNotEqual(result["fabric_length_cm"], 50.0)

    def test_yardage_route_returns_422_without_any_fabric_requirement(self):
        pattern = MagicMock()
        pattern.session_id.user_id.id = "user-1"
        pattern.validation_passed = True
        pattern.pattern_coordinates = [_piece("Huge Panel", 200, 50)]
        with patch("app.routes.export.PatternResult") as pr:
            pr.objects.return_value.first.return_value = pattern
            resp = self.app.test_client().post(
                "/api/export/yardage/abc123", json={"fabric_width_cm": 114, "cutting_mode": "open"},
                headers=self.headers)
        self.assertEqual(resp.status_code, 422)
        body = resp.get_json()
        self.assertTrue(body["nesting_failed"])
        self.assertEqual(body["nesting_failure"]["failed_pieces"][0]["name"], "Huge Panel")
        for key in ("yardage_metres", "fabric_length_cm", "utilisation_percent", "placed_pieces"):
            self.assertNotIn(key, body)
        pattern.save.assert_not_called()     # no fake yardage persisted


# ── 4. Research API ───────────────────────────────────────────────────────────
def _record(version, **fields):
    base = dict(
        id="r1", user_id=SimpleNamespace(id="u1", full_name="Test User"),
        metrics_integrity_version=version, correction_rate=None, ai_confidence_avg=None,
        processing_time_sec=None, pattern_generation_time_sec=None, baseline_yardage_m=None,
        optimized_yardage_m=None, fabric_savings_m=None, layout_efficiency=None,
        feedback_score=4, feedback_comment="ok", pattern_id=None,
        created_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
    )
    base.update(fields)
    return SimpleNamespace(**base)


class TestResearchApiHasNoInventedMetrics(AppTestCase):
    INVENTED = (0.91, 0.93, 0.90, 0.82, 0.38, 2.5)

    def _metrics(self, records, model_eval=None):
        model_eval = model_eval or {"available": False, "reason": "test"}
        with patch("app.routes.research.ResearchRecord") as rr, \
             patch("app.routes.research.load_model_evaluation", return_value=model_eval):
            rr.objects.all.return_value = records
            with patch("app.routes.research._is_researcher", return_value=True):
                resp = self.app.test_client().get("/api/research/metrics", headers=self.headers)
        self.assertEqual(resp.status_code, 200)
        return resp.get_json()

    def test_nothing_recorded_means_unavailable(self):
        self.assertFalse(self._metrics([])["available"])

    def test_missing_measurements_are_null_not_defaults(self):
        body = self._metrics([_record(METRICS_INTEGRITY_VERSION)])
        for key in ("ai_accuracy", "precision", "recall", "f1_score", "avg_fabric_savings",
                    "avg_processing_time", "avg_correction_rate", "avg_ai_confidence"):
            self.assertIsNone(body[key], key)

    def test_legacy_records_do_not_leak_invented_values(self):
        legacy = _record(1, correction_rate=0.0, ai_confidence_avg=0.91, processing_time_sec=0.82,
                         pattern_generation_time_sec=0.38, baseline_yardage_m=2.5,
                         optimized_yardage_m=1.8, fabric_savings_m=0.7, layout_efficiency=72.0)
        body = self._metrics([legacy])
        self.assertIsNone(body["avg_correction_rate"])
        self.assertIsNone(body["avg_processing_time"])
        self.assertIsNone(body["avg_ai_confidence"])
        self.assertIsNone(body["avg_fabric_savings"])
        self.assertEqual(body["legacy_records_excluded_from_measured_fields"], 1)
        self.assertEqual(body["usability_score"], 4.0)      # genuine survey input is kept

    def test_measured_values_are_averaged_from_real_records(self):
        recs = [_record(METRICS_INTEGRITY_VERSION, correction_rate=25.0, ai_confidence_avg=0.6),
                _record(METRICS_INTEGRITY_VERSION, correction_rate=75.0, ai_confidence_avg=0.8),
                _record(METRICS_INTEGRITY_VERSION)]      # not measured -> excluded, not zero
        body = self._metrics(recs)
        self.assertEqual(body["avg_correction_rate"], 50.0)
        self.assertEqual(body["correction_rate_n"], 2)
        self.assertEqual(body["avg_ai_confidence"], 0.7)

    def test_model_metrics_come_from_evaluation_source(self):
        ev = {"available": True, "per_head": {"garment_type": {"accuracy": 0.7752}}}
        body = self._metrics([], model_eval=ev)
        self.assertTrue(body["available"])
        self.assertEqual(body["model_evaluation"]["per_head"]["garment_type"]["accuracy"], 0.7752)
        for key in ("precision", "recall", "f1_score"):
            self.assertIsNone(body[key])

    def test_csv_export_blank_for_unmeasured(self):
        with patch("app.routes.research.ResearchRecord") as rr:
            rr.objects.all.return_value = [_record(1, baseline_yardage_m=2.5, layout_efficiency=72.0)]
            with patch("app.routes.research._is_researcher", return_value=True):
                resp = self.app.test_client().get("/api/research/export/csv", headers=self.headers)
        text = resp.get_data(as_text=True)
        self.assertNotIn("2.5", text.splitlines()[1])
        self.assertNotIn("72.0", text.splitlines()[1])


class TestResearchDefaultsAndHelpers(unittest.TestCase):
    def test_model_defaults_are_not_measured(self):
        r = ResearchRecord()
        for field in ("correction_rate", "ai_confidence_avg", "processing_time_sec",
                      "pattern_generation_time_sec", "baseline_yardage_m",
                      "optimized_yardage_m", "fabric_savings_m", "layout_efficiency"):
            self.assertIsNone(getattr(r, field), field)

    def test_model_evaluation_missing_file(self):
        result = load_model_evaluation(log_dir=os.path.join(tempfile.gettempdir(), "does-not-exist-xyz"))
        self.assertFalse(result["available"])

    def test_model_evaluation_read_from_file_not_invented(self):
        d = tempfile.mkdtemp()
        with open(os.path.join(d, "test_metrics_final.json"), "w", encoding="utf-8") as f:
            json.dump({"record_count": 10, "overall_supported_head_mean_macro_f1": 0.5,
                       "metrics_by_head": {"garment_type": {
                           "evaluated_count": 10, "accuracy": 0.6, "macro_precision": 0.61,
                           "macro_recall": "N/A", "macro_f1": 0.62}}}, f)
        result = load_model_evaluation(log_dir=d, eval_checkpoint=os.path.join(d, "a.pt"),
                                       deployed_checkpoint=os.path.join(d, "b.pt"))
        head = result["per_head"]["garment_type"]
        self.assertEqual(head["accuracy"], 0.6)
        self.assertIsNone(head["macro_recall"])          # "N/A" stays null
        self.assertIsNone(result["evaluates_deployed_checkpoint"])   # unverifiable -> not claimed

    def test_feature_corrections_from_stored_predictions(self):
        preds = {"garment_type": {"label": "blouse"}, "neckline_type": {"label": "v-neck"},
                 "sleeve_length": {"label": "long-sleeve"}, "sleeve_style": {"label": "puff-sleeve"}}
        conf = {"garment_type": "blouse", "neckline_type": "round-neck",
                "sleeve_length": "long-sleeve", "sleeve_style": "puff-sleeve"}
        corrections, rate = compute_feature_corrections(preds, conf)
        self.assertEqual(rate, 25.0)
        self.assertEqual(corrections["neckline_type"], {"predicted": "v-neck", "confirmed": "round-neck"})
        self.assertEqual(compute_feature_corrections({}, conf), ({}, None))   # nothing to compare -> None

    def test_mean_or_none(self):
        self.assertIsNone(mean_or_none([None, None]))
        self.assertEqual(mean_or_none([None, 2.0, 4.0]), 3.0)


# ── 5. Model version derived from checkpoint ─────────────────────────────────
class TestModelVersionIsDerived(unittest.TestCase):
    def test_version_reflects_checkpoint_content(self):
        from app.ai.multitask_classifier import build_model_version
        a = build_model_version({"stage": "Stage_B", "epoch": 7}, "a" * 64)
        b = build_model_version({"stage": "Stage_B", "epoch": 9}, "b" * 64)
        self.assertNotEqual(a, b)
        self.assertIn("epoch=7", a)
        self.assertIn("sha256=" + "a" * 12, a)
        self.assertNotIn("m14d", a)

    def test_missing_fields_are_omitted_not_invented(self):
        from app.ai.multitask_classifier import build_model_version
        v = build_model_version({}, "c" * 64)
        self.assertNotIn("epoch", v)
        self.assertNotIn("stage", v)


if __name__ == "__main__":
    unittest.main()
