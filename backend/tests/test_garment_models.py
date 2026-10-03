"""The four garment models: picture preparation, thresholds, suggestions, missing models, the API routes.

The logic is tested with stand-in probabilities, so no weight file is needed. The last class loads the real files
from backend/model and skips visibly when they are not on this machine."""
import io
import json
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from flask_jwt_extended import create_access_token
from PIL import Image

from app import create_app
from app.ai import garment_models as gm
from app.ai import garment_parts
from app.ai.preprocess import crop_box, load_rgb, square_pad, PAD_COLOUR
from app.logic import feature_schema as fs

FAKE = {
    "garment_type": [("blouse", 0.80), ("t-shirt", 0.20)],
    "neckline_type": [("round-neck", 0.10), ("v-neck", 0.60), ("square-neck", 0.25), ("collared-neck", 0.05)],
    "sleeve_length": [("sleeveless", 0.02), ("short-sleeve", 0.95), ("long-sleeve", 0.03)],
    "sleeve_style": [("regular-sleeve", 0.60), ("puff-sleeve", 0.40)],
}


def _photo(size=(300, 400), orientation=None, colour=(180, 40, 60)):
    img = Image.new("RGB", size, colour)
    buf = io.BytesIO()
    if orientation:
        ex = Image.Exif()
        ex[0x0112] = orientation
        img.save(buf, "JPEG", exif=ex.tobytes())
    else:
        img.save(buf, "JPEG")
    fd, path = tempfile.mkstemp(suffix=".jpg")
    with os.fdopen(fd, "wb") as f:
        f.write(buf.getvalue())
    return path


class _ModelDir(unittest.TestCase):
    """A temporary model folder; `_probabilities` is replaced by stand-in answers."""

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.env = patch.dict(os.environ, {"GARMENT_MODEL_DIR": self.dir})
        self.env.start()
        gm.reset_models()
        self.answers = {h: list(v) for h, v in FAKE.items()}
        self.calls = []

        def fake(head, image, part=False):
            self.calls.append((f"{head}:part" if part else head, image.size))
            if head not in self.answers:
                raise gm.GarmentModelError(f"model file for {head} is missing")
            gm._cache[head] = {"sha256": f"{head}-sha"}
            return self.answers[head]

        self.probs = patch.object(gm, "_probabilities", side_effect=fake)
        self.probs.start()
        self.photo = _photo()

    def tearDown(self):
        self.probs.stop()
        self.env.stop()
        gm.reset_models()

    def thresholds(self, **values):
        with open(os.path.join(self.dir, gm.THRESHOLDS_FILE), "w", encoding="utf-8") as f:
            json.dump(values, f)


class TestPreparation(unittest.TestCase):
    def test_a_photo_is_turned_upright_before_anything_else(self):
        path = _photo(size=(400, 200), orientation=6)                # stored sideways, EXIF says rotate
        self.assertEqual(load_rgb(path).size, (200, 400))

    def test_square_pad_keeps_the_whole_garment_and_never_stretches_it(self):
        img = Image.new("RGB", (100, 300), (10, 200, 10))
        out = square_pad(img)
        self.assertEqual(out.size, (300, 300))
        self.assertEqual(out.getpixel((150, 5)), (10, 200, 10))      # the top of the garment (the neckline) is still there
        self.assertEqual(out.getpixel((150, 295)), (10, 200, 10))
        self.assertEqual(out.getpixel((5, 150)), PAD_COLOUR)         # the sides are neutral padding
        self.assertEqual(square_pad(img, 64).size, (64, 64))

    def test_crop_box_adds_the_margin_and_stays_inside_the_photo(self):
        img = Image.new("RGB", (200, 300))
        self.assertEqual(crop_box(img, [50, 100, 150, 200]).size, (120, 120))          # 10 % on every side
        self.assertEqual(crop_box(img, [50, 100, 150, 200], margin=0).size, (100, 100))
        self.assertEqual(crop_box(img, [0, 0, 200, 300]).size, (200, 300))             # clamped
        self.assertIs(crop_box(img, None), img)
        self.assertIs(crop_box(img, [10, 10, 10, 10]), img)                            # an empty box is ignored

    def test_the_models_see_the_caller_s_box_exactly(self):
        path = _photo(size=(200, 300))
        self.assertEqual(gm.prepare(path, [40, 90, 160, 210]).size, (120, 120))
        self.assertEqual(gm.prepare(path, None).size, (300, 300))
        with self.assertRaises(gm.GarmentModelError):
            gm.prepare(os.path.join(tempfile.gettempdir(), "no-such-photo.jpg"))


class TestThresholds(_ModelDir):
    def test_no_file_means_nothing_is_answered_automatically(self):
        self.assertEqual(gm.load_thresholds(), {h: None for h in gm.HEADS})

    def test_only_sensible_numbers_are_accepted(self):
        self.thresholds(garment_type=0.9, neckline_type=None, sleeve_length="0.7", sleeve_style=1.7, _note="x")
        self.assertEqual(gm.load_thresholds(), {"garment_type": 0.9, "neckline_type": None, "sleeve_length": None, "sleeve_style": None})

    def test_a_broken_file_is_treated_as_no_thresholds(self):
        with open(os.path.join(self.dir, gm.THRESHOLDS_FILE), "w") as f:
            f.write("{not json")
        self.assertEqual(gm.load_thresholds(), {h: None for h in gm.HEADS})


class TestSuggestions(_ModelDir):
    def test_every_feature_is_please_select_without_thresholds(self):
        out = gm.predict_attributes(self.photo)
        self.assertEqual({h: p["label"] for h, p in out["predictions"].items()},
                         {"garment_type": "blouse", "neckline_type": "v-neck", "sleeve_length": "short-sleeve", "sleeve_style": "regular-sleeve"})
        self.assertTrue(all(p["uncertain"] and p["requires_user_confirmation"] for p in out["predictions"].values()))
        self.assertEqual(out["low_confidence_heads"], gm.HEADS)
        self.assertTrue(out["requires_user_confirmation"])

    def test_a_feature_is_filled_in_only_at_or_above_its_own_threshold(self):
        self.thresholds(garment_type=0.80, neckline_type=0.61, sleeve_length=0.90, sleeve_style=None)
        p = gm.predict_attributes(self.photo)["predictions"]
        self.assertFalse(p["garment_type"]["uncertain"])                 # 0.80 >= 0.80
        self.assertTrue(p["neckline_type"]["uncertain"])                 # 0.60 <  0.61
        self.assertFalse(p["sleeve_length"]["uncertain"])                # 0.95 >= 0.90
        self.assertTrue(p["sleeve_style"]["uncertain"])                  # no threshold
        self.assertEqual(p["sleeve_length"]["threshold_used"], 0.9)

    def test_scores_and_top_three_are_the_model_s_own(self):
        p = gm.predict_attributes(self.photo)["predictions"]["neckline_type"]
        self.assertEqual(p["confidence"], 0.6)
        self.assertEqual([t["class_name"] for t in p["top_3"]], ["v-neck", "square-neck", "round-neck"])
        self.assertEqual([t["confidence"] for t in p["top_3"]], [0.6, 0.25, 0.1])

    def test_a_sleeveless_garment_has_sleeve_style_none_without_asking_the_sleeve_design_model(self):
        self.answers["sleeve_length"] = [("sleeveless", 0.97), ("short-sleeve", 0.02), ("long-sleeve", 0.01)]
        self.thresholds(sleeve_length=0.9)
        out = gm.predict_attributes(self.photo)
        style = out["predictions"]["sleeve_style"]
        self.assertEqual((style["label"], style["derived_from"], style["uncertain"]), ("none", "sleeve_length", False))
        self.assertNotIn("sleeve_style", [h for h, _ in self.calls])
        self.thresholds(sleeve_length=0.99)                              # an uncertain "sleeveless" gives an uncertain "none"
        self.assertTrue(gm.predict_attributes(self.photo)["predictions"]["sleeve_style"]["uncertain"])

    def test_the_sleeve_design_model_never_answers_none(self):
        labels = {c for c, _ in FAKE["sleeve_style"]}
        self.assertNotIn("none", labels)
        self.assertEqual(gm.predict_attributes(self.photo)["predictions"]["sleeve_style"]["label"], "regular-sleeve")

    def test_every_suggestion_is_a_selectable_value(self):
        out = fs.annotate_predictions(gm.predict_attributes(self.photo))
        self.assertEqual(out["unsupported_heads"], [])
        for head, p in out["predictions"].items():
            self.assertIn(p["label"], fs.TAXONOMY[head])

    def test_a_missing_model_leaves_that_feature_to_the_user(self):
        del self.answers["neckline_type"]
        out = gm.predict_attributes(self.photo)
        self.assertNotIn("neckline_type", out["predictions"])
        self.assertEqual(out["heads_without_a_model"], ["neckline_type"])
        self.assertEqual(set(out["predictions"]), {"garment_type", "sleeve_length", "sleeve_style"})

    def test_no_model_at_all_is_an_error_not_an_empty_answer(self):
        self.answers.clear()
        with self.assertRaises(gm.GarmentModelError):
            gm.predict_attributes(self.photo)

    def test_all_models_see_the_same_square_picture(self):
        gm.predict_attributes(self.photo, bbox=[30, 40, 130, 240])
        self.assertEqual({size for _, size in self.calls}, {(200, 200)})


class TestParts(_ModelDir):
    """The neckline and the sleeve style can use a part model (neck area, sleeves). The part detector is replaced by
    stand-in boxes and the part model files are empty stand-ins."""

    def setUp(self):
        super().setUp()
        for name in gm.PART_FILES.values():
            open(os.path.join(self.dir, name), "wb").close()
        self.part_answers = {}                                         # head -> list of answers, one per part picture

        def fake(head, image, part=False):
            self.calls.append((f"{head}:part" if part else head, image.size))
            if part:
                gm._cache[f"{head}:part"] = {"sha256": f"{head}-part-sha"}
                return self.part_answers[head].pop(0)
            if head not in self.answers:
                raise gm.GarmentModelError(f"model file for {head} is missing")
            gm._cache[head] = {"sha256": f"{head}-sha"}
            return self.answers[head]

        self.probs.stop()
        self.probs = patch.object(gm, "_probabilities", side_effect=fake)
        self.probs.start()

    def inputs(self, **values):
        with open(os.path.join(self.dir, gm.INPUTS_FILE), "w", encoding="utf-8") as f:
            json.dump(values, f)

    def found(self, neck=None, sleeves=()):
        p = patch.object(garment_parts, "find_parts", return_value={"neck": neck, "sleeves": list(sleeves)})
        p.start()
        self.addCleanup(p.stop)

    def test_without_an_inputs_file_every_feature_uses_its_garment_model(self):
        self.assertEqual(gm.load_inputs(), {h: "garment" for h in gm.HEADS})
        self.inputs(neckline_type="garment+neck", sleeve_style="neck", garment_type="neck", sleeve_length=7)   # only valid kinds count
        self.assertEqual(gm.load_inputs(), {"garment_type": "garment", "neckline_type": "garment+neck",
                                            "sleeve_length": "garment", "sleeve_style": "garment"})
        self.assertEqual(gm.input_kinds("sleeve_style"), ("garment", "sleeve", "garment+sleeve"))
        self.assertEqual(gm.input_kinds("garment_type"), ("garment",))

    def test_the_part_model_sees_the_neck_area_and_the_others_the_garment(self):
        self.inputs(neckline_type="neck")
        self.found(neck=[100, 20, 200, 80])                           # 100 x 60 in a 400 x 400 picture
        self.part_answers["neckline_type"] = [[("round-neck", 0.1), ("v-neck", 0.2), ("square-neck", 0.6), ("collared-neck", 0.1)]]
        p = gm.predict_attributes(self.photo)["predictions"]["neckline_type"]
        sizes = dict(self.calls)
        self.assertEqual(sizes["neckline_type:part"], (130, 130))     # 15 % margin on every side, padded square
        self.assertNotIn("neckline_type", sizes)                      # the garment model is not asked
        self.assertEqual(sizes["garment_type"], (400, 400))
        self.assertEqual((p["label"], p["confidence"], p["part_found"]), ("square-neck", 0.6, True))

    def test_the_scores_of_both_sleeves_are_averaged(self):
        self.inputs(sleeve_style="sleeve")
        self.found(sleeves=[[0, 100, 80, 300], [320, 100, 400, 300]])
        self.part_answers["sleeve_style"] = [[("puff-sleeve", 0.7), ("regular-sleeve", 0.3)],
                                             [("puff-sleeve", 0.5), ("regular-sleeve", 0.5)]]
        p = gm.predict_attributes(self.photo)["predictions"]["sleeve_style"]
        self.assertEqual((p["label"], p["confidence"], p["part_found"]), ("puff-sleeve", 0.6, True))

    def test_part_only_a_part_that_is_not_found_is_never_an_automatic_answer(self):
        self.inputs(neckline_type="neck", sleeve_style="sleeve")
        self.thresholds(neckline_type=0.5, sleeve_style=0.4)
        self.found(neck=None, sleeves=[])
        out = gm.predict_attributes(self.photo)
        for head in ("neckline_type", "sleeve_style"):
            p = out["predictions"][head]
            self.assertFalse(p["part_found"])
            self.assertTrue(p["uncertain"], head)                      # 0.6 / 0.5 is above the threshold, still uncertain
            self.assertEqual(p["label"], max(FAKE[head], key=lambda x: x[1])[0])   # the garment model's guess is shown
        self.assertIn("neckline_type", out["low_confidence_heads"])

    def test_both_models_their_answers_are_averaged_by_class_name(self):
        self.inputs(neckline_type="garment+neck")
        self.thresholds(neckline_type=0.5)
        self.found(neck=[100, 20, 200, 80])
        # the part model lists its classes in another order than the garment model
        self.part_answers["neckline_type"] = [[("collared-neck", 0.05), ("round-neck", 0.10), ("square-neck", 0.05), ("v-neck", 0.80)]]
        p = gm.predict_attributes(self.photo)["predictions"]["neckline_type"]
        self.assertEqual((p["label"], p["confidence"], p["uncertain"]), ("v-neck", 0.7, False))      # (0.60 + 0.80) / 2
        self.assertEqual(p["top_3"][1], {"class_name": "square-neck", "confidence": 0.15})            # (0.25 + 0.05) / 2

    def test_both_models_without_the_part_the_garment_model_answers_alone(self):
        self.inputs(neckline_type="garment+neck")
        self.thresholds(neckline_type=0.5)
        self.found(neck=None)
        p = gm.predict_attributes(self.photo)["predictions"]["neckline_type"]
        self.assertEqual((p["label"], p["confidence"], p["uncertain"]), ("v-neck", 0.6, False))      # as before the part models
        self.assertNotIn("neckline_type:part", dict(self.calls))

    def test_a_missing_part_model_file_falls_back_to_the_garment_model(self):
        os.remove(os.path.join(self.dir, gm.PART_FILES["neckline_type"]))
        self.inputs(neckline_type="garment+neck")
        self.found(neck=[100, 20, 200, 80])
        self.assertEqual(gm.predict_attributes(self.photo)["predictions"]["neckline_type"]["confidence"], 0.6)

    def test_the_part_detector_is_asked_once_per_photo(self):
        self.inputs(neckline_type="neck", sleeve_style="sleeve")
        self.part_answers = {"neckline_type": [FAKE["neckline_type"]], "sleeve_style": [FAKE["sleeve_style"]]}
        with patch.object(garment_parts, "find_parts", return_value={"neck": [100, 20, 200, 80], "sleeves": [[0, 100, 80, 300]]}) as find:
            gm.predict_attributes(self.photo)
        self.assertEqual(find.call_count, 1)

    def test_without_a_detector_file_no_part_is_found(self):
        self.assertFalse(garment_parts.available(self.dir))
        self.assertEqual(garment_parts.find_parts(Image.new("RGB", (64, 64)), self.dir), {"neck": None, "sleeves": []})

    def test_only_confident_boxes_are_used_one_neck_and_at_most_two_sleeves(self):
        d = [{"class": "neck", "score": 0.34, "box_xyxy": [0, 0, 1, 1]},
             {"class": "sleeve", "score": 0.9, "box_xyxy": [1, 1, 2, 2]}, {"class": "sleeve", "score": 0.5, "box_xyxy": [2, 2, 3, 3]},
             {"class": "sleeve", "score": 0.6, "box_xyxy": [3, 3, 4, 4]}, {"class": "sleeve", "score": 0.2, "box_xyxy": [4, 4, 5, 5]}]
        out = garment_parts.choose(d)
        self.assertIsNone(out["neck"])                                 # 0.34 is below the fixed 0.35
        self.assertEqual(out["sleeves"], [[1, 1, 2, 2], [3, 3, 4, 4]])
        d.append({"class": "neck", "score": 0.35, "box_xyxy": [9, 9, 10, 10]})
        self.assertEqual(garment_parts.choose(d)["neck"], [9, 9, 10, 10])


class TestStatus(unittest.TestCase):
    def test_an_empty_model_folder_is_reported_as_unavailable_without_paths(self):
        d = tempfile.mkdtemp()
        with patch.dict(os.environ, {"GARMENT_MODEL_DIR": d}):
            gm.reset_models()
            status = gm.models_status()
        gm.reset_models()
        self.assertFalse(status["available"])
        self.assertFalse(status["complete"])
        self.assertIsNone(status["checkpoint_sha256"])
        self.assertNotIn(d, json.dumps(status))
        self.assertEqual({m["architecture"] for m in status["models"].values()}, {"MobileNetV3-Large", "YOLOv8n-cls"})

    def test_a_file_that_is_not_a_model_is_unavailable_not_a_crash(self):
        d = tempfile.mkdtemp()
        for name in gm.FILES.values():
            with open(os.path.join(d, name), "wb") as f:
                f.write(b"not a checkpoint")
        with patch.dict(os.environ, {"GARMENT_MODEL_DIR": d}):
            gm.reset_models()
            status = gm.models_status()
        gm.reset_models()
        self.assertFalse(status["available"])


class TestRoutes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config["TESTING"] = True
        cls.tmp = tempfile.mkdtemp()
        cls.app.config["UPLOAD_FOLDER"] = cls.tmp
        Image.new("RGB", (200, 300), (200, 30, 60)).save(os.path.join(cls.tmp, "x.png"))
        with open(os.path.join(cls.tmp, "broken.png"), "wb") as f:
            f.write(b"not an image")
        with cls.app.app_context():
            cls.h = {"Authorization": f"Bearer {create_access_token(identity='u1')}"}

    def _image(self, name="x.png"):
        image = MagicMock()
        image.user_id.id = "u1"
        image.file_path = name
        image.id = "img1"
        return image

    def _status(self, available=True):
        models = {h: {"available": available, "architecture": gm.ARCHITECTURE[h], "sha256": "s" if available else None} for h in gm.HEADS}
        return {"available": available, "complete": available, "model_type": gm.MODEL_TYPE, "model_version": gm.MODEL_VERSION,
                "checkpoint_sha256": "abc" if available else None, "models": models,
                "thresholds": {"garment_type": None, "neckline_type": None, "sleeve_length": 0.8, "sleeve_style": None}}

    def test_model_status_says_which_features_are_answered_automatically(self):
        with patch("app.ai.garment_models.models_status", return_value=self._status()):
            body = self.app.test_client().get("/api/images/model-status", headers=self.h).get_json()
        self.assertTrue(body["available"])
        self.assertEqual({h: m["answers_automatically"] for h, m in body["models"].items()},
                         {"garment_type": False, "neckline_type": False, "sleeve_length": True, "sleeve_style": False})
        self.assertEqual(body["models"]["garment_type"]["architecture"], "MobileNetV3-Large")

    def test_model_status_reports_unavailable_without_internal_details(self):
        with patch("app.ai.garment_models.models_status", return_value=self._status(False)):
            r = self.app.test_client().get("/api/images/model-status", headers=self.h)
        self.assertEqual(r.get_json()["available"], False)
        self.assertNotIn("model", r.get_json().get("message", "").lower().replace("ai garment model", ""))
        self.assertNotIn(":\\", r.get_data(as_text=True))

    def test_analyse_without_models_is_a_503_that_keeps_the_manual_path(self):
        with patch("app.routes.images.DesignImage") as DI, patch("app.ai.garment_models.models_status", return_value=self._status(False)):
            DI.objects.return_value.first.return_value = self._image()
            r = self.app.test_client().post("/api/images/img1/analyse", headers=self.h)
        self.assertEqual((r.status_code, r.get_json()["error_code"]), (503, "MODEL_UNAVAILABLE"))
        self.assertIn("manually", r.get_json()["error"])

    def test_an_unreadable_photo_is_a_422_not_a_server_error(self):
        with patch("app.routes.images.DesignImage") as DI, patch("app.ai.garment_models.models_status", return_value=self._status()), \
                patch("app.ai.garment_detector.detect_garment", return_value={"available": False, "box_xyxy": None, "class": None,
                                                                              "score": None, "reason": "x"}):
            DI.objects.return_value.first.return_value = self._image("broken.png")
            r = self.app.test_client().post("/api/images/img1/analyse", headers=self.h)
        self.assertEqual((r.status_code, r.get_json()["error_code"]), (422, "IMAGE_NOT_ANALYSABLE"))

    def test_analyse_stores_the_genuine_suggestions_and_clears_any_old_confirmation(self):
        image = self._image()
        image.confirmed_attributes = {"garment_type": "blouse"}
        answer = {"model_version": gm.MODEL_VERSION, "model_type": gm.MODEL_TYPE, "checkpoint_sha256": "abc",
                  "predictions": {"garment_type": {"label": "t-shirt", "confidence": 0.7, "top_3": [], "uncertain": True,
                                                   "requires_user_confirmation": True, "threshold_used": None}},
                  "heads_without_a_model": [], "low_confidence_heads": ["garment_type"], "requires_user_confirmation": True}
        with patch("app.routes.images.DesignImage") as DI, patch("app.ai.garment_models.models_status", return_value=self._status()), \
                patch("app.ai.garment_models.predict_attributes", return_value=answer), \
                patch("app.ai.garment_detector.detect_garment", return_value={"available": True, "box_xyxy": None, "class": None,
                                                                              "score": None, "reason": "No garment found; full image used."}):
            DI.objects.return_value.first.return_value = image
            r = self.app.test_client().post("/api/images/img1/analyse", headers=self.h)
        body = r.get_json()
        self.assertEqual(r.status_code, 200, body)
        self.assertEqual(body["garment_attributes"]["predictions"]["garment_type"]["label"], "t-shirt")
        self.assertTrue(body["requires_user_confirmation"])
        self.assertEqual(image.confirmed_attributes, {})
        self.assertEqual(image.confidence_score, 0.7)
        image.save.assert_called_once()

    def test_design_schema_lists_exactly_the_selectable_classes(self):
        body = self.app.test_client().get("/api/images/design-schema", headers=self.h).get_json()
        self.assertEqual({h: [o["value"] for o in body["heads"][h]] for h in body["heads"]}, {h: list(v) for h, v in fs.TAXONOMY.items()})
        self.assertEqual(body["active_class_count"], 12)                      # bell sleeve removed 3 Oct 2026
        self.assertEqual(set(body["scope"]), {"blouse", "t-shirt"})
        self.assertNotIn("crop", json.dumps(body).lower())


REAL = all(os.path.isfile(os.path.join(gm.MODEL_DIR, f)) for f in gm.FILES.values())


@unittest.skipUnless(REAL, "SKIPPED: the trained model files are not in backend/model on this machine")
class TestRealModels(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        gm.reset_models()
        cls.status = gm.models_status()

    def test_all_four_models_load_with_the_expected_classes(self):
        self.assertTrue(self.status["complete"], self.status)
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "training"))
        import common as training
        expected = {"garment_type": training.TASKS["garment"], "neckline_type": training.TASKS["neckline"],
                    "sleeve_length": training.TASKS["sleeve_length"], "sleeve_style": training.TASKS["sleeve_design"]}
        for head, classes in expected.items():
            self.assertEqual(sorted(self.status["models"][head]["classes"]), sorted(classes), head)
            self.assertEqual(len(self.status["models"][head]["sha256"]), 64)

    def test_a_real_photo_gets_four_probability_distributions(self):
        out = gm.predict_attributes(_photo(size=(320, 480), colour=(230, 220, 120)))
        self.assertEqual(set(out["predictions"]), set(gm.HEADS))
        for head, p in out["predictions"].items():
            self.assertIn(p["label"], fs.TAXONOMY[head])
            self.assertTrue(0.0 < p["confidence"] <= 1.0)
        for head in ("garment_type", "neckline_type", "sleeve_length"):
            total = sum(v for _, v in gm._probabilities(head, gm.prepare(_photo())))
            self.assertAlmostEqual(total, 1.0, places=3)

    def test_the_same_photo_gives_the_same_answer(self):
        path = _photo(size=(300, 300), colour=(90, 120, 200))
        a, b = gm.predict_attributes(path), gm.predict_attributes(path)
        self.assertEqual(a["predictions"], b["predictions"])


if __name__ == "__main__":
    unittest.main()
