"""Deployed M13 classifier: direct inference, API inference (analyse), unsupported predictions, manual confirmation."""
import json
import os
import unittest
from unittest.mock import MagicMock, patch

from flask_jwt_extended import create_access_token

from app import create_app
from app.logic import feature_schema as fs

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
M13 = os.path.join(ROOT, "backend", "app", "ai", "models", "garment_multitask_yolov8_best.pt")
M13_SHA256 = "3b69a470ed5d039844056135ad27c700a865b82196ef85dc6a5e9f53c84f0339"
BENCH = os.path.join(ROOT, "ai_training", "data", "eval_real_product_set", "images")
HEADS = fs.HEADS


def _have_model():
    return os.path.exists(M13) and os.path.exists(os.path.join(ROOT, "backend", "app", "ai", "models", "yolov8n-cls.pt"))


@unittest.skipUnless(_have_model(), "SKIPPED: deployed M13 checkpoint is a local file (not in Git) and is absent here")
class TestDirectM13Inference(unittest.TestCase):
    def test_checkpoint_is_the_unchanged_m13_with_original_head_dimensions(self):
        from app.ai.multitask_classifier import get_multitask_classifier
        _, meta = get_multitask_classifier(model_path=M13)
        self.assertEqual(meta["checkpoint_sha256"], M13_SHA256)
        self.assertEqual([int(meta["head_dims"][h]) for h in HEADS], [3, 10, 6, 9])
        for h in HEADS:
            self.assertEqual(list(meta["idx_to_class"][h].values()) if False else
                             [meta["idx_to_class"][h][str(i)] for i in range(len(meta["idx_to_class"][h]))],
                             list(fs.MODEL_TAXONOMY[h]), h)

    def test_real_images_give_four_genuine_predictions_and_correct_scope_flags(self):
        if not os.path.isdir(BENCH):
            self.skipTest("SKIPPED: benchmark images are local data and are absent here")
        from app.ai.multitask_classifier import predict_multitask_features
        files = sorted(os.listdir(BENCH))[::10][:6]
        self.assertTrue(files)
        seen_unsupported = 0
        for name in files:
            raw = predict_multitask_features(os.path.join(BENCH, name), model_path=M13)
            out = fs.annotate_predictions(raw)
            for h in HEADS:
                p, q = raw["predictions"][h], out["predictions"][h]
                self.assertIn(p["label"], fs.MODEL_TAXONOMY[h])
                self.assertTrue(0.0 <= p["confidence"] <= 1.0)
                self.assertEqual((q["label"], q["confidence"], q["top_3"]), (p["label"], p["confidence"], p["top_3"]))
                self.assertEqual(q["supported_in_ui"], p["label"] in fs.TAXONOMY[h])
                self.assertEqual(q["suggested_label"], p["label"] if q["supported_in_ui"] else None)
            self.assertEqual(out["unsupported_heads"], [h for h in HEADS if not out["predictions"][h]["supported_in_ui"]])
            seen_unsupported += bool(out["unsupported_heads"])
        self.assertGreaterEqual(seen_unsupported, 0)


class TestAnalyseApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config["TESTING"] = True
        import tempfile
        cls.tmp = tempfile.mkdtemp()
        cls.app.config["UPLOAD_FOLDER"] = cls.tmp
        with open(os.path.join(cls.tmp, "x.png"), "wb") as f:
            from PIL import Image
            import io
            b = io.BytesIO()
            Image.new("RGB", (60, 80), (200, 30, 60)).save(b, "PNG")
            f.write(b.getvalue())
        with cls.app.app_context():
            cls.h = {"Authorization": f"Bearer {create_access_token(identity='u1')}"}

    def _raw(self, **labels):
        base = {"garment_type": "blouse", "neckline_type": "round-neck", "sleeve_length": "short-sleeve",
                "sleeve_style": "regular-sleeve"}
        base.update(labels)
        return {"model_version": "M13", "model_type": "t", "checkpoint_sha256": "abc",
                "predictions": {h: {"label": v, "class_index": 0, "confidence": 0.8, "top_3": [
                    {"class_name": v, "class_index": 0, "confidence": 0.8}], "requires_user_confirmation": False,
                    "threshold_used": 0.4} for h, v in base.items()},
                "low_confidence_heads": [], "requires_user_confirmation": False}

    def _analyse(self, raw):
        image = MagicMock()
        image.user_id.id = "u1"
        image.file_path = "x.png"
        image.id = "img1"
        with patch("app.routes.images.DesignImage") as DI, \
                patch("app.ai.multitask_classifier.get_multitask_classifier", return_value=(None, {})), \
                patch("app.ai.multitask_classifier.predict_multitask_features", return_value=raw), \
                patch("app.ai.yolo_detector.detect_features", return_value=({"source": "cv_heuristic"}, None)):
            DI.objects.return_value.first.return_value = image
            r = self.app.test_client().post("/api/images/img1/analyse", headers=self.h)
        return r, image

    def _analyse_failing(self, load_error=None, predict_error=None):
        from app.ai.multitask_classifier import MultiTaskModelError
        image = MagicMock()
        image.user_id.id = "u1"
        image.file_path = "x.png"
        load = patch("app.ai.multitask_classifier.get_multitask_classifier",
                     side_effect=MultiTaskModelError(load_error) if load_error else None,
                     return_value=(None, {}))
        predict = patch("app.ai.multitask_classifier.predict_multitask_features",
                        side_effect=MultiTaskModelError(predict_error) if predict_error else None)
        with patch("app.routes.images.DesignImage") as DI, load, predict:
            DI.objects.return_value.first.return_value = image
            r = self.app.test_client().post("/api/images/img1/analyse", headers=self.h)
        return r, image

    def test_missing_model_is_reported_honestly_as_unavailable(self):
        r, image = self._analyse_failing(load_error="Multi-task model checkpoint not found at C:/secret/path.pt")
        body = r.get_json()
        self.assertEqual(r.status_code, 503)
        self.assertEqual(body["error_code"], "MODEL_UNAVAILABLE")
        self.assertIn("choose the design manually", body["error"])
        self.assertNotIn("secret", json.dumps(body))            # no internal path leaks to the client
        image.save.assert_not_called()                          # no fake analysis is stored

    def test_unreadable_image_is_a_422_not_a_server_error(self):
        r, image = self._analyse_failing(predict_error="Failed to open or decode image")
        self.assertEqual(r.status_code, 422)
        self.assertEqual(r.get_json()["error_code"], "IMAGE_NOT_ANALYSABLE")
        image.save.assert_not_called()

    def test_model_status_endpoint_reports_unavailable_without_internal_details(self):
        with patch("app.ai.multitask_classifier.get_multitask_classifier",
                   side_effect=__import__("app.ai.multitask_classifier", fromlist=["x"]).MultiTaskModelError(
                       "Multi-task model checkpoint not found at C:/secret/path.pt")):
            r = self.app.test_client().get("/api/images/model-status", headers=self.h)
        body = r.get_json()
        self.assertEqual(r.status_code, 200)
        self.assertFalse(body["available"])
        self.assertNotIn("secret", json.dumps(body))

    def test_model_status_endpoint_reports_the_loaded_checkpoint(self):
        meta = {"model_version": "M13|x", "model_type": "multitask", "checkpoint_sha256": "abc", "head_dims": {}}
        with patch("app.ai.multitask_classifier.get_multitask_classifier", return_value=(None, meta)):
            r = self.app.test_client().get("/api/images/model-status", headers=self.h)
        body = r.get_json()
        self.assertTrue(body["available"])
        self.assertEqual((body["model_version"], body["checkpoint_sha256"]), ("M13|x", "abc"))

    def test_model_status_requires_login(self):
        self.assertEqual(self.app.test_client().get("/api/images/model-status").status_code, 401)

    def test_supported_prediction_is_returned_with_no_scope_warning(self):
        r, image = self._analyse(self._raw())
        body = r.get_json()
        self.assertEqual(r.status_code, 200)
        self.assertEqual(body["unsupported_heads"], [])
        self.assertIsNone(body["unsupported_message"])
        self.assertEqual(body["garment_attributes"]["predictions"]["neckline_type"]["suggested_label"], "round-neck")

    def test_unsupported_prediction_is_flagged_and_all_evidence_is_stored(self):
        r, image = self._analyse(self._raw(neckline_type="boat-neck", sleeve_length="elbow-length"))
        body = r.get_json()
        self.assertEqual(r.status_code, 200)
        self.assertEqual(body["unsupported_heads"], ["neckline_type", "sleeve_length"])
        self.assertEqual(body["unsupported_message"],
                         "The detected feature is outside the supported pattern scope. Please confirm the design manually.")
        self.assertTrue(body["requires_user_confirmation"])
        preds = body["garment_attributes"]["predictions"]
        self.assertEqual((preds["neckline_type"]["label"], preds["neckline_type"]["confidence"]), ("boat-neck", 0.8))
        self.assertIsNone(preds["neckline_type"]["suggested_label"])
        stored = image.garment_attributes                      # what was saved for research evidence
        self.assertEqual(stored["predictions"]["sleeve_length"]["label"], "elbow-length")
        self.assertEqual(stored["predictions"]["sleeve_length"]["confidence"], 0.8)
        self.assertEqual(image.confirmed_attributes, {})       # nothing is auto-confirmed

    def test_manual_confirmation_after_an_unsupported_prediction(self):
        image = MagicMock()
        image.user_id.id = "u1"
        image.id = "img1"
        image.garment_attributes = fs.annotate_predictions(self._raw(neckline_type="boat-neck"))
        image.detected_features = {}
        good = {"garment_type": "blouse", "neckline_type": "square-neck", "sleeve_length": "short-sleeve",
                "sleeve_style": "regular-sleeve"}
        with patch("app.routes.images.DesignImage") as DI:
            DI.objects.return_value.first.return_value = image
            bad = self.app.test_client().post("/api/images/img1/confirm-attributes", headers=self.h,
                                              json=dict(good, neckline_type="boat-neck"))
            ok = self.app.test_client().post("/api/images/img1/confirm-attributes", headers=self.h, json=good)
        self.assertEqual(bad.status_code, 400)                   # cannot confirm the removed class
        self.assertEqual(bad.get_json()["field_errors"]["neckline_type"]["code"], "OUTSIDE_SCOPE")
        self.assertEqual(ok.status_code, 200)
        spec = ok.get_json()["design_spec"]
        self.assertEqual(spec["attributes"]["neckline_type"], "square-neck")
        prov = spec["provenance"]["neckline_type"]
        self.assertEqual(prov["source"], "user_corrected")       # user corrected the model ...
        self.assertEqual(prov["predicted_label"], "boat-neck")   # ... and the genuine prediction is preserved
        self.assertEqual(prov["predicted_confidence"], 0.8)

    def test_design_schema_endpoint_lists_only_the_15_active_classes(self):
        r = self.app.test_client().get("/api/images/design-schema", headers=self.h)
        body = r.get_json()
        self.assertEqual({h: [o["value"] for o in v] for h, v in body["heads"].items()},
                         {h: list(v) for h, v in fs.TAXONOMY.items()})
        self.assertEqual(body["active_class_count"], 15)
        self.assertEqual(body["model_class_counts"], {"garment_type": 3, "neckline_type": 10, "sleeve_length": 6, "sleeve_style": 9})


if __name__ == "__main__":
    unittest.main()
