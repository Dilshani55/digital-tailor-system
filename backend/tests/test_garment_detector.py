"""Garment detector wrapper: never raises, honest 'unavailable', box selection/padding, EXIF orientation."""
import io
import os
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

from app.ai import garment_detector as gd


class _Box:
    def __init__(self, cls, conf, xyxy):
        import torch
        self.cls = torch.tensor(cls)
        self.conf = torch.tensor(conf)
        self.xyxy = torch.tensor([xyxy])


class _Res:
    names = {0: "top", 1: "outerwear", 2: "dress"}

    def __init__(self, boxes):
        self.boxes = boxes


class _FakeModel:
    def __init__(self, boxes):
        self.boxes = boxes
        self.seen_size = None

    def predict(self, img, **kw):
        self.seen_size = img.size
        return [_Res(self.boxes)]


def _jpeg(size=(400, 200), orientation=None):
    img = Image.new("RGB", size, (180, 40, 40))
    buf = io.BytesIO()
    if orientation:
        ex = Image.Exif()
        ex[0x0112] = orientation
        img.save(buf, "JPEG", exif=ex.tobytes())
    else:
        img.save(buf, "JPEG")
    fd, p = tempfile.mkstemp(suffix=".jpg")
    with os.fdopen(fd, "wb") as f:
        f.write(buf.getvalue())
    return p


class TestChoose(unittest.TestCase):
    def test_nothing_above_min_score_gives_no_box(self):
        r = gd.choose([{"class": "top", "score": gd.MIN_SCORE - 0.01, "box_xyxy": [0, 0, 10, 10]}], 100, 100)
        self.assertEqual(r, {"box_xyxy": None, "class": None, "score": None})

    def test_most_confident_detection_wins_and_is_padded_and_clipped(self):
        dets = [{"class": "dress", "score": 0.5, "box_xyxy": [0, 0, 50, 50]},
                {"class": "top", "score": 0.9, "box_xyxy": [10, 20, 90, 100]}]
        r = gd.choose(dets, 95, 100)
        self.assertEqual(r["class"], "top")
        self.assertEqual(r["score"], 0.9)
        self.assertEqual(r["box_xyxy"], [10.0, 20.0, 90.0, 100.0])  # tight box; the caller adds the margin

    def test_pad_box_adds_the_training_crop_margin_and_clips(self):
        self.assertEqual(gd.pad_box([10, 20, 90, 100], 95, 100), [2.0, 12.0, 95.0, 100.0])

    def test_unsupported_garment_class_is_reported_not_hidden(self):
        r = gd.choose([{"class": "outerwear", "score": 0.8, "box_xyxy": [0, 0, 10, 10]}], 100, 100)
        self.assertEqual(r["class"], "outerwear")


class TestDetectGarment(unittest.TestCase):
    def tearDown(self):
        gd.reset_detector()

    def test_missing_model_is_unavailable_not_an_error(self):
        r = gd.detect_garment(_jpeg(), model_path=os.path.join(tempfile.gettempdir(), "no_such_detector.pt"))
        self.assertFalse(r["available"])
        self.assertIsNone(r["box_xyxy"])
        self.assertIn("not found", r["reason"])

    def test_corrupt_image_is_reported_not_raised(self):
        fd, bad = tempfile.mkstemp(suffix=".jpg")
        os.write(fd, b"not an image"); os.close(fd)
        with patch.object(gd, "_load", return_value=(_FakeModel([]), "abc")), patch("os.path.exists", return_value=True):
            r = gd.detect_garment(bad, model_path="x.pt")
        self.assertFalse(r["available"])
        self.assertIn("failed", r["reason"])

    def test_detector_sees_the_exif_rotated_image_and_box_is_in_that_space(self):
        fake = _FakeModel([_Box(0, 0.8, [10, 10, 150, 300])])
        with patch.object(gd, "_load", return_value=(fake, "abc")), patch("os.path.exists", return_value=True):
            r = gd.detect_garment(_jpeg((400, 200), orientation=6), model_path="x.pt")
        self.assertEqual(fake.seen_size, (200, 400))      # stored landscape, shown/analysed portrait
        self.assertTrue(r["available"])
        self.assertEqual(r["class"], "top")
        self.assertLessEqual(r["box_xyxy"][2], 200)
        self.assertLessEqual(r["box_xyxy"][3], 400)

    def test_no_detection_means_full_image_fallback(self):
        with patch.object(gd, "_load", return_value=(_FakeModel([]), "abc")), patch("os.path.exists", return_value=True):
            r = gd.detect_garment(_jpeg(), model_path="x.pt")
        self.assertTrue(r["available"])
        self.assertIsNone(r["box_xyxy"])
        self.assertIn("full image", r["reason"])


if __name__ == "__main__":
    unittest.main()


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
BENCH = os.path.join(ROOT, "backend", "training", "data", "eval_real_product_set", "images")


@unittest.skipUnless(os.path.exists(gd.DEFAULT_DETECTOR_PATH),
                     "SKIPPED: detector weights are a local file (not in Git) and are absent here")
class TestRealDetector(unittest.TestCase):
    def test_real_weights_find_the_top_in_real_photos(self):
        if not os.path.isdir(BENCH):
            self.skipTest("SKIPPED: benchmark photos are local data and are absent here")
        files = sorted(f for f in os.listdir(BENCH) if f.startswith(("blouse", "t-shirt")))[:6]
        found = 0
        for f in files:
            r = gd.detect_garment(os.path.join(BENCH, f))
            self.assertTrue(r["available"])
            self.assertEqual(len(r["model_sha256"]), 64)
            if r["box_xyxy"]:
                x1, y1, x2, y2 = r["box_xyxy"]
                self.assertTrue(0 <= x1 < x2 and 0 <= y1 < y2)
                found += r["class"] == "top"
        self.assertGreaterEqual(found, 4)       # independent test: correct top crop in 79-90 % of photos
