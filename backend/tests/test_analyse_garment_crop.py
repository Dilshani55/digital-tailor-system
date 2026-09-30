"""Analyse route + garment detector: the classifier receives the detected garment crop (tight box + 10 % margin),
falls back to the whole photo honestly, and flags garments that cannot be drafted."""
import io
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from flask_jwt_extended import create_access_token
from PIL import Image

from app import create_app

RAW = {"model_version": "t", "model_type": "t", "checkpoint_sha256": "abc",
       "predictions": {h: {"label": v, "class_index": 0, "confidence": 0.8, "top_3": [], "requires_user_confirmation": True,
                           "threshold_used": None}
                       for h, v in {"garment_type": "blouse", "neckline_type": "round-neck",
                                    "sleeve_length": "short-sleeve", "sleeve_style": "regular-sleeve"}.items()},
       "low_confidence_heads": [], "requires_user_confirmation": True}


class TestAnalyseWithGarmentCrop(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config["TESTING"] = True
        cls.tmp = tempfile.mkdtemp()
        cls.app.config["UPLOAD_FOLDER"] = cls.tmp
        b = io.BytesIO()
        Image.new("RGB", (200, 300), (200, 30, 60)).save(b, "PNG")
        with open(os.path.join(cls.tmp, "x.png"), "wb") as f:
            f.write(b.getvalue())
        with cls.app.app_context():
            cls.h = {"Authorization": f"Bearer {create_access_token(identity='u1')}"}

    def _analyse(self, detection):
        image = MagicMock()
        image.user_id.id = "u1"
        image.file_path = "x.png"
        image.id = "img1"
        predict = MagicMock(return_value=dict(RAW))
        with patch("app.routes.images.DesignImage") as DI, \
                patch("app.ai.multitask_classifier.get_multitask_classifier", return_value=(None, {})), \
                patch("app.ai.multitask_classifier.predict_multitask_features", predict), \
                patch("app.ai.garment_detector.detect_garment", return_value=detection), \
                patch("app.ai.yolo_detector.detect_features", return_value=({"source": "cv_heuristic"}, None)):
            DI.objects.return_value.first.return_value = image
            r = self.app.test_client().post("/api/images/img1/analyse", headers=self.h)
        return r, predict

    def _det(self, box, cls="top", available=True):
        return {"available": available, "box_xyxy": box, "class": cls if box else None, "score": 0.9 if box else None,
                "model_sha256": "d", "detections": [], "reason": None if box else "No garment found; full image used."}

    def test_classifier_gets_the_padded_detector_box(self):
        r, predict = self._analyse(self._det([50, 100, 150, 200]))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(predict.call_args.kwargs["bbox"], [40.0, 90.0, 160.0, 210.0])
        region = r.get_json()["garment_region"]
        self.assertEqual(region["used"], "garment_crop")
        self.assertTrue(region["supported_garment"])

    def test_no_box_falls_back_to_the_whole_photo_and_says_so(self):
        r, predict = self._analyse(self._det(None))
        self.assertIsNone(predict.call_args.kwargs["bbox"])
        region = r.get_json()["garment_region"]
        self.assertEqual(region["used"], "full_image")
        self.assertIn("full image", region["note"])

    def test_missing_detector_still_analyses_the_whole_photo(self):
        r, predict = self._analyse(self._det(None, available=False) | {"reason": "Garment detector not found"})
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(predict.call_args.kwargs["bbox"])
        self.assertFalse(r.get_json()["garment_region"]["detector_available"])

    def test_dress_or_outerwear_is_flagged_as_not_draftable(self):
        r, _ = self._analyse(self._det([10, 10, 190, 290], cls="dress"))
        region = r.get_json()["garment_region"]
        self.assertFalse(region["supported_garment"])
        self.assertIn("a dress", region["note"])
        self.assertIn("Only blouses, T-shirts and crop tops can be drafted", region["note"])

    def test_detector_crash_never_breaks_analysis(self):
        image = MagicMock()
        image.user_id.id = "u1"
        image.file_path = "x.png"
        predict = MagicMock(return_value=dict(RAW))
        with patch("app.routes.images.DesignImage") as DI, \
                patch("app.ai.multitask_classifier.get_multitask_classifier", return_value=(None, {})), \
                patch("app.ai.multitask_classifier.predict_multitask_features", predict), \
                patch("app.ai.garment_detector.detect_garment", side_effect=RuntimeError("boom")), \
                patch("app.ai.yolo_detector.detect_features", return_value=({}, None)):
            DI.objects.return_value.first.return_value = image
            r = self.app.test_client().post("/api/images/img1/analyse", headers=self.h)
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(predict.call_args.kwargs["bbox"])
        self.assertIn("unavailable", r.get_json()["garment_region"]["note"])


if __name__ == "__main__":
    unittest.main()
