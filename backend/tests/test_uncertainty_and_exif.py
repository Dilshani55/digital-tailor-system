"""EXIF orientation of uploaded photos, per-head thresholds (sidecar) and the explicit `uncertain` flag."""
import json
import os
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import torch
from PIL import Image

from app.ai import multitask_classifier as mc
from app.utils.helpers import save_image

HEADS = mc.HEADS


class FakeFile:
    def __init__(self, path, name="p.jpg"):
        self.path, self.filename = path, name

    def save(self, dest):
        with open(self.path, "rb") as a, open(dest, "wb") as b:
            b.write(a.read())


def _exif_jpeg(path, orientation, size=(80, 40)):
    """A JPEG whose stored pixels are `size` (w, h) with an EXIF orientation tag; left half red, right half blue."""
    arr = np.zeros((size[1], size[0], 3), dtype=np.uint8)
    arr[:, : size[0] // 2] = (255, 0, 0)
    arr[:, size[0] // 2:] = (0, 0, 255)
    im = Image.fromarray(arr)
    exif = Image.Exif()
    exif[0x0112] = orientation
    im.save(path, "JPEG", exif=exif, quality=95)


class TestExifOrientation(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()

    def test_upload_bakes_the_camera_rotation_into_the_stored_pixels(self):
        src = os.path.join(self.d, "phone.jpg")
        _exif_jpeg(src, orientation=6)                      # "rotate 90 clockwise to display"
        folder = tempfile.mkdtemp()
        name = save_image(FakeFile(src), folder)
        with Image.open(os.path.join(folder, name)) as stored:
            self.assertEqual(stored.size, (40, 80))          # portrait after correction (was stored 80x40)
            self.assertNotIn(0x0112, stored.getexif())       # no stale orientation tag left behind

    def test_normal_orientation_is_unchanged(self):
        src = os.path.join(self.d, "flat.jpg")
        _exif_jpeg(src, orientation=1)
        folder = tempfile.mkdtemp()
        name = save_image(FakeFile(src), folder)
        with Image.open(os.path.join(folder, name)) as stored:
            self.assertEqual(stored.size, (80, 40))

    def test_model_input_is_orientation_corrected(self):
        rotated = os.path.join(self.d, "rot.jpg")
        _exif_jpeg(rotated, orientation=6)
        upright = os.path.join(self.d, "up.png")
        with Image.open(rotated) as im:
            im.load()
            from PIL import ImageOps
            ImageOps.exif_transpose(im).save(upright)         # the picture as a person sees it
        a = mc.preprocess_image_crop(rotated)
        b = mc.preprocess_image_crop(upright)
        self.assertLess(float((a - b).abs().mean()), 0.05)     # same view (JPEG vs PNG rounding only)
        raw = Image.open(rotated).convert("RGB").resize((224, 224))
        naive = torch.from_numpy(np.asarray(raw, dtype=np.float32) / 255.0).permute(2, 0, 1)
        naive = ((naive - torch.tensor([0.485, 0.456, 0.406]).view(3, 1, 1)) / torch.tensor([0.229, 0.224, 0.225]).view(3, 1, 1)).unsqueeze(0)
        self.assertGreater(float((a - naive).abs().mean()), 0.3)   # and clearly different from ignoring EXIF


class _FakeModel:
    """Returns fixed logits so that every head's top-1 probability is known."""
    def __init__(self, conf):
        self.conf = conf

    def __call__(self, x):
        out = {}
        for h, n in {"garment_type": 3, "neckline_type": 5, "sleeve_length": 3, "sleeve_style": 4}.items():
            p = self.conf[h]
            rest = (1 - p) / (n - 1)
            probs = torch.tensor([[p] + [rest] * (n - 1)])
            out[h] = torch.log(probs)
        return out


class TestUncertainFlag(unittest.TestCase):
    def _run(self, conf, sidecar=None):
        d = tempfile.mkdtemp()
        ck = os.path.join(d, "model.pt")
        open(ck, "wb").write(b"x")
        if sidecar is not None:
            json.dump(sidecar, open(os.path.join(d, "model.thresholds.json"), "w"))
        classes = {"garment_type": ["blouse", "t-shirt", "crop-top"],
                   "neckline_type": ["round-neck", "v-neck", "square-neck", "collared-neck", "off-shoulder"],
                   "sleeve_length": ["sleeveless", "short-sleeve", "long-sleeve"],
                   "sleeve_style": ["none", "regular-sleeve", "puff-sleeve", "bell-sleeve"]}
        meta = {"model_version": "t", "model_type": "t", "checkpoint_sha256": "x", "model_path": ck,
                "idx_to_class": {h: {str(i): c for i, c in enumerate(v)} for h, v in classes.items()},
                "class_to_idx": {h: {c: i for i, c in enumerate(v)} for h, v in classes.items()}}
        with patch.object(mc, "get_multitask_classifier", return_value=(_FakeModel(conf), meta)), \
                patch.object(mc, "preprocess_image_crop", return_value=torch.zeros(1, 3, 224, 224)):
            return mc.predict_multitask_features("x.jpg")

    def test_defaults_when_there_is_no_sidecar(self):
        out = self._run({"garment_type": 0.9, "neckline_type": 0.3, "sleeve_length": 0.9, "sleeve_style": 0.9})
        self.assertTrue(out["predictions"]["neckline_type"]["uncertain"])          # 0.30 < default 0.45
        self.assertFalse(out["predictions"]["garment_type"]["uncertain"])
        self.assertIn("neckline_type", out["low_confidence_heads"])
        self.assertTrue(out["requires_user_confirmation"])

    def test_sidecar_thresholds_from_validation_are_used(self):
        conf = {"garment_type": 0.8, "neckline_type": 0.8, "sleeve_length": 0.8, "sleeve_style": 0.8}
        out = self._run(conf, {"garment_type": 0.85, "neckline_type": 0.5, "sleeve_length": 0.7, "sleeve_style": 0.95})
        flags = {h: out["predictions"][h]["uncertain"] for h in HEADS}
        self.assertEqual(flags, {"garment_type": True, "neckline_type": False, "sleeve_length": False, "sleeve_style": True})
        self.assertEqual(out["predictions"]["garment_type"]["threshold_used"], 0.85)

    def test_a_null_threshold_means_always_uncertain_even_at_99_percent(self):
        conf = {h: 0.99 for h in HEADS}
        out = self._run(conf, {"garment_type": 0.5, "neckline_type": None, "sleeve_length": 0.5, "sleeve_style": 0.5})
        self.assertTrue(out["predictions"]["neckline_type"]["uncertain"])
        self.assertIsNone(out["predictions"]["neckline_type"]["threshold_used"])
        self.assertFalse(out["predictions"]["garment_type"]["uncertain"])
        # the genuine prediction and score are still reported
        self.assertEqual(out["predictions"]["neckline_type"]["label"], "round-neck")
        self.assertAlmostEqual(out["predictions"]["neckline_type"]["confidence"], 0.99, places=2)

    def test_broken_sidecar_falls_back_to_defaults(self):
        d = tempfile.mkdtemp()
        ck = os.path.join(d, "m.pt")
        open(os.path.join(d, "m.thresholds.json"), "w").write("{not json")
        self.assertEqual(mc.load_thresholds(ck), mc.DEFAULT_CONFIDENCE_THRESHOLDS)


if __name__ == "__main__":
    unittest.main()
