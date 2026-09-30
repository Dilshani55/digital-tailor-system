"""Deployed M40 (3/5/3/4) classifier: checkpoint identity, frozen thresholds, real inference, API output, rollback."""
import json
import os
import unittest

from app.ai import multitask_classifier as mc
from app.logic import feature_schema as fs

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
M40_SHA256 = "3ed45bc121c0eea82fb44280a6a5b5e2e2beaf43035fc501cf3e5089436c66be"
BENCH = os.path.join(ROOT, "ai_training", "data", "eval_real_product_set", "images")
HEADS = mc.HEADS
HAVE = os.path.exists(mc.M40_MODEL_PATH) and os.path.exists(mc.DEFAULT_BACKBONE_PATH)


class TestThresholdFile(unittest.TestCase):
    """The sidecar is tracked in Git, so this runs everywhere."""

    def test_frozen_thresholds_and_their_meaning(self):
        th = mc.load_thresholds(mc.M40_MODEL_PATH)
        self.assertIsNone(th["garment_type"])          # never reached 90 % accepted accuracy on validation
        self.assertIsNone(th["neckline_type"])
        self.assertIsNone(th["sleeve_style"])          # regular-sleeve has no trusted data: forced uncertain
        self.assertAlmostEqual(th["sleeve_length"], 0.7006, places=3)
        note = json.load(open(os.path.splitext(mc.M40_MODEL_PATH)[0] + ".thresholds.json"))["_note"]
        self.assertIn("regular-sleeve", note)

    def test_default_model_selection_and_rollback_path(self):
        self.assertTrue(mc.M13_MODEL_PATH.endswith("garment_multitask_yolov8_best.pt"))
        self.assertTrue(mc.M40_MODEL_PATH.endswith("garment_multitask_m40_15class.pt"))


@unittest.skipUnless(HAVE, "SKIPPED: the M40 checkpoint is a local file (not in Git) and is absent here")
class TestDeployedM40(unittest.TestCase):
    def setUp(self):
        mc.reset_multitask_classifier_singleton()

    def tearDown(self):
        mc.reset_multitask_classifier_singleton()

    def test_identity_and_head_dimensions(self):
        _, meta = mc.get_multitask_classifier(model_path=mc.M40_MODEL_PATH)
        self.assertEqual(meta["checkpoint_sha256"], M40_SHA256)
        self.assertEqual([int(meta["head_dims"][h]) for h in HEADS], [3, 5, 3, 4])
        for h in HEADS:                                        # exactly the 15 active classes, in order
            self.assertEqual([meta["idx_to_class"][h][str(i)] for i in range(len(meta["idx_to_class"][h]))], list(fs.TAXONOMY[h]))

    def test_it_is_the_default_unless_overridden(self):
        if os.environ.get("GARMENT_MODEL_PATH"):
            self.skipTest("SKIPPED: GARMENT_MODEL_PATH is set in this environment")
        self.assertEqual(os.path.abspath(mc.DEFAULT_MODEL_PATH), os.path.abspath(mc.M40_MODEL_PATH))

    def test_real_photos_every_head_scored_and_uncertainty_follows_the_thresholds(self):
        if not os.path.isdir(BENCH):
            self.skipTest("SKIPPED: benchmark images are local data and absent here")
        names = sorted(os.listdir(BENCH))[::12][:5]
        seen_certain_length = False
        for name in names:
            out = mc.predict_multitask_features(os.path.join(BENCH, name), model_path=mc.M40_MODEL_PATH)
            for h in HEADS:
                p = out["predictions"][h]
                self.assertIn(p["label"], fs.TAXONOMY[h])
                self.assertTrue(0.0 <= p["confidence"] <= 1.0)
                self.assertEqual(len(p["top_3"]), 3 if h != "garment_type" else 3)
            for h in ("garment_type", "neckline_type", "sleeve_style"):
                self.assertTrue(out["predictions"][h]["uncertain"], h)          # null threshold => always "please select"
            sl = out["predictions"]["sleeve_length"]
            self.assertEqual(sl["uncertain"], sl["confidence"] < 0.7006)
            seen_certain_length |= not sl["uncertain"]
            ann = fs.annotate_predictions(out)
            self.assertEqual(ann["unsupported_heads"], [])                       # the model only outputs selectable classes
        self.assertTrue(seen_certain_length or len(names) < 3)

    def test_rollback_to_m13_is_one_setting(self):
        out = mc.predict_multitask_features(os.path.join(BENCH, sorted(os.listdir(BENCH))[0]), model_path=mc.M13_MODEL_PATH) \
            if os.path.isdir(BENCH) and os.path.exists(mc.M13_MODEL_PATH) else None
        if out is None:
            self.skipTest("SKIPPED: M13 rollback checkpoint or benchmark images absent")
        _, meta = mc.get_multitask_classifier(model_path=mc.M13_MODEL_PATH)
        self.assertEqual([int(meta["head_dims"][h]) for h in HEADS], [3, 10, 6, 9])


if __name__ == "__main__":
    unittest.main()
