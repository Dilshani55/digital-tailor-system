"""Deployment gate logic, dataset-audit helpers (leakage / near-duplicates), taxonomy parity, model load + inference."""
import json
import os
import sys
import tempfile
import unittest

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from ai_training.scripts import acceptance_gate as gate          # noqa: E402
from ai_training.scripts import audit_dataset as audit            # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DEPLOYED = os.path.join(ROOT, "backend", "app", "ai", "models", "garment_multitask_yolov8_best.pt")
BACKBONE = os.path.join(ROOT, "backend", "app", "ai", "models", "yolov8n-cls.pt")
CLASSES = os.path.join(ROOT, "ai_training", "config", "classes.json")
HEADS = gate.HEADS


class TestGateDecision(unittest.TestCase):
    ok = [True] * 5

    def test_pass_needs_improvement_on_both_evaluations(self):
        self.assertEqual(gate.decide(self.ok, 0.03, 0.01), "PASS")

    def test_fail_when_locked_benchmark_does_not_improve(self):
        self.assertEqual(gate.decide(self.ok, -0.02, 0.01), "FAIL")
        self.assertEqual(gate.decide(self.ok, 0.0, 0.01), "FAIL")

    def test_fail_on_any_hard_check(self):
        for i in range(5):
            checks = [True] * 5
            checks[i] = False
            self.assertEqual(gate.decide(checks, 0.05, 0.05), "FAIL")

    def test_ambiguous_when_clean_test_disagrees_or_gain_is_tiny(self):
        self.assertEqual(gate.decide(self.ok, 0.05, -0.001), "AMBIGUOUS")
        self.assertEqual(gate.decide(self.ok, 0.004, 0.02), "AMBIGUOUS")

    def test_critical_head_regression_limits(self):
        base = {h: 0.0 for h in HEADS}
        self.assertTrue(gate.regression_ok(base))
        self.assertFalse(gate.regression_ok(dict(base, garment_type=-0.031)))     # garment head is the strictest
        self.assertTrue(gate.regression_ok(dict(base, garment_type=-0.029)))
        self.assertFalse(gate.regression_ok(dict(base, neckline_type=-0.051)))
        self.assertTrue(gate.regression_ok(dict(base, sleeve_style=-0.049)))

    def test_mean_macro_f1_ignores_heads_without_labels(self):
        scores = {h: {"macro_f1": 0.5, "evaluated": 10} for h in HEADS}
        scores["sleeve_style"] = {"macro_f1": 0.0, "evaluated": 0}
        self.assertAlmostEqual(gate.mean_f1(scores), 0.5)


class TestAuditHelpers(unittest.TestCase):
    def test_near_pairs_uses_hamming_distance(self):
        a = [0b0000, 0b1111_0000]
        b = [0b0001, 0b1010_1010_1010]
        pairs = audit.near_pairs(a, b, 1)
        self.assertEqual(pairs, [(0, 0, 1)])
        self.assertEqual(audit.near_pairs(a, b, 0), [])

    def test_dhash_is_identical_for_the_same_picture_and_differs_for_others(self):
        d = tempfile.mkdtemp()
        rng = np.random.default_rng(3)
        img = Image.fromarray(rng.integers(0, 255, (80, 60, 3), dtype=np.uint8))
        other = Image.fromarray(rng.integers(0, 255, (80, 60, 3), dtype=np.uint8))
        p1, p2, p3 = (os.path.join(d, n) for n in ("a.png", "a_copy.png", "b.png"))
        img.save(p1)
        img.resize((120, 160)).save(p2)                      # rescaled copy = near duplicate
        other.save(p3)
        h1, h2, h3 = audit.dhash(p1), audit.dhash(p2), audit.dhash(p3)
        self.assertLessEqual(bin(h1 ^ h2).count("1"), 8)
        self.assertGreater(bin(h1 ^ h3).count("1"), 8)

    def test_corrupt_and_missing_images_are_detected(self):
        d = tempfile.mkdtemp()
        good = os.path.join(d, "g.png")
        Image.new("RGB", (10, 10)).save(good)
        bad = os.path.join(d, "b.png")
        open(bad, "wb").write(b"not an image")
        self.assertTrue(audit.check_image(good)[0])
        self.assertFalse(audit.check_image(bad)[0])
        self.assertFalse(audit.check_image(os.path.join(d, "missing.png"))[0])

    def test_sha256_changes_with_content(self):
        d = tempfile.mkdtemp()
        p = os.path.join(d, "x")
        open(p, "wb").write(b"abc")
        h1 = audit.sha256_file(p)
        open(p, "wb").write(b"abd")
        self.assertNotEqual(h1, audit.sha256_file(p))


class TestTaxonomyParity(unittest.TestCase):
    def test_dataset_model_backend_and_frontend_taxonomies_agree(self):
        cwd = os.getcwd()
        os.chdir(ROOT)
        try:
            rep = audit.taxonomy_report(CLASSES)
        finally:
            os.chdir(cwd)
        self.assertEqual(rep["classes_json"], {"garment_type": 3, "neckline_type": 10, "sleeve_length": 6, "sleeve_style": 9})
        for name, ok in rep["checks"].items():
            self.assertIs(ok, True, f"{name}: {ok}")


class TestManifestIntegrity(unittest.TestCase):
    def test_locked_evaluation_records_are_not_in_the_training_manifest(self):
        ev = os.path.join(ROOT, "ai_training", "data", "eval_real_product_set", "eval_manifest.jsonl")
        tr = os.path.join(ROOT, "ai_training", "data", "final_multitask", "train.jsonl")
        if not (os.path.exists(ev) and os.path.exists(tr)):
            self.skipTest("SKIPPED: dataset manifests are local data and not present on this machine")
        train_uids = {json.loads(x)["record_uid"] for x in open(tr, encoding="utf-8") if x.strip()}
        eval_uids = [json.loads(x)["original_record_uid"] for x in open(ev, encoding="utf-8") if x.strip()]
        self.assertEqual(len(eval_uids), 60)
        self.assertFalse(train_uids & set(eval_uids))

    def test_splits_share_no_source_image(self):
        base = os.path.join(ROOT, "ai_training", "data", "final_multitask")
        if not os.path.exists(os.path.join(base, "train.jsonl")):
            self.skipTest("SKIPPED: dataset manifests are local data and not present on this machine")
        uid = {}
        for name in ("train", "val", "test"):
            uid[name] = {json.loads(x)["source_image_uid"] for x in open(os.path.join(base, f"{name}.jsonl"), encoding="utf-8") if x.strip()}
        self.assertFalse(uid["train"] & uid["val"])
        self.assertFalse(uid["train"] & uid["test"])
        self.assertFalse(uid["val"] & uid["test"])


class TestDeployedModel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (os.path.exists(DEPLOYED) and os.path.exists(BACKBONE)):
            raise unittest.SkipTest("SKIPPED: deployed checkpoint / backbone are local files (not in Git) and are absent here")

    def test_loads_in_production_code_with_matching_heads_and_predicts(self):
        import torch
        import torch.nn.functional as F
        sys.path.insert(0, os.path.join(ROOT, "backend"))
        from backend.app.ai.multitask_classifier import get_multitask_classifier, preprocess_image_crop
        model, meta = get_multitask_classifier(model_path=DEPLOYED)
        want = json.load(open(CLASSES))["outputs"]
        for h in HEADS:
            self.assertEqual(len(meta["class_to_idx"][h]), len(want[h]["classes"]))
        d = tempfile.mkdtemp()
        p = os.path.join(d, "x.png")
        Image.fromarray(np.random.default_rng(1).integers(0, 255, (200, 150, 3), dtype=np.uint8)).save(p)
        with torch.no_grad():
            out = model(preprocess_image_crop(p))
        for h in HEADS:
            probs = F.softmax(out[h][0], dim=0)
            self.assertEqual(probs.numel(), len(want[h]["classes"]))
            self.assertAlmostEqual(float(probs.sum()), 1.0, places=4)
            self.assertTrue(bool(torch.isfinite(probs).all()))


if __name__ == "__main__":
    unittest.main()
