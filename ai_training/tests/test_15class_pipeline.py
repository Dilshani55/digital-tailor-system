"""Future 3/5/3/4 (15-class) pipeline: class config, masking, trusted counts, readiness, human decisions, guard."""
import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

from ai_training.training import labels15 as L                     # noqa: E402
from ai_training.scripts import train_15class_guarded as G          # noqa: E402
from ai_training.scripts import build_label_queue_15class as Q      # noqa: E402

CLASSES_PATH = os.path.join(ROOT, "ai_training", "config", "classes_v2_15class.json")
M13_CLASSES_PATH = os.path.join(ROOT, "ai_training", "config", "classes.json")
TARGETS_PATH = os.path.join(ROOT, "ai_training", "config", "label_targets_15class.json")
CLASSES = L.load_classes(CLASSES_PATH)
TARGETS = L.load_targets(TARGETS_PATH)


def rec(uid="r1", split="train", **over):
    """A manifest record in the existing (29-class) format; keyword args override labels, e.g. neckline_type='boat-neck'."""
    labels = {"garment_type": "blouse", "neckline_type": "round-neck", "sleeve_length": "short-sleeve", "sleeve_style": "regular-sleeve"}
    prov = {"garment_type": "human_verified", "neckline_type": "fashionpedia_direct",
            "sleeve_length": "fashionpedia_direct", "sleeve_style": "fashionpedia_rule_derived"}
    p_over = over.pop("prov", {})
    labels.update(over)
    prov.update(p_over)
    masks = {h: 0 if labels[h] is None else 1 for h in labels}
    return {"record_uid": uid, "split": split, "source_annotation_id": uid, "source_image_path": f"img/{uid}.jpg",
            "labels": labels, "masks": masks, "provenance": prov, "confidence": {h: 0.9 for h in labels}}


class TestClassConfig(unittest.TestCase):
    def test_exact_15_classes_in_exact_order(self):
        self.assertEqual(CLASSES, {
            "garment_type": ["blouse", "t-shirt", "crop-top"],
            "neckline_type": ["round-neck", "v-neck", "square-neck", "collared-neck", "off-shoulder"],
            "sleeve_length": ["sleeveless", "short-sleeve", "long-sleeve"],
            "sleeve_style": ["none", "regular-sleeve", "puff-sleeve", "bell-sleeve"]})
        self.assertEqual(sum(len(v) for v in CLASSES.values()), 15)

    def test_config_is_internally_consistent(self):
        cfg = json.load(open(CLASSES_PATH))
        self.assertEqual(cfg["class_counts"], {"garment_type": 3, "neckline_type": 5, "sleeve_length": 3, "sleeve_style": 4})
        for h, out in cfg["outputs"].items():
            self.assertEqual(out["class_count"], len(out["classes"]))
            for i, c in enumerate(out["classes"]):
                self.assertEqual(out["class_to_idx"][c], i)
                self.assertEqual(out["idx_to_class"][str(i)], c)
        self.assertIn("PLANNED", cfg["status"])

    def test_is_a_different_file_from_the_deployed_m13_config(self):
        m13 = json.load(open(M13_CLASSES_PATH))
        self.assertEqual(m13["class_counts"], {"garment_type": 3, "neckline_type": 10, "sleeve_length": 6, "sleeve_style": 9})
        self.assertNotEqual(os.path.abspath(CLASSES_PATH), os.path.abspath(M13_CLASSES_PATH))

    def test_wrong_dimensions_are_rejected(self):
        with self.assertRaises(ValueError):
            L.load_classes(M13_CLASSES_PATH)               # 3/10/6/9 must never be accepted as the 15-class config

    def test_removed_classes_listed_do_not_appear_as_active(self):
        cfg = json.load(open(CLASSES_PATH))
        for h, removed in cfg["removed_classes_are_masked_never_remapped"].items():
            self.assertFalse(set(removed) & set(CLASSES[h]))


class TestMaskingNeverRemaps(unittest.TestCase):
    REMOVED = {"neckline_type": ["scoop-neck", "boat-neck", "sweetheart-neck", "halter-neck", "high-neck"],
               "sleeve_length": ["cap-length", "elbow-length", "three-quarter-sleeve"],
               "sleeve_style": ["bishop-sleeve", "flutter-sleeve", "raglan-sleeve", "dolman-sleeve", "kimono-sleeve"]}

    def test_every_removed_class_masks_only_its_own_head(self):
        for head, labels in self.REMOVED.items():
            for lab in labels:
                out = L.convert_record(rec(**{head: lab}), CLASSES)
                self.assertIsNone(out["labels"][head], (head, lab))          # not turned into anything
                self.assertEqual(out["masks"][head], 0)
                self.assertEqual(out["provenance"][head], "masked_removed_class")
                self.assertIsNone(out["class_indices"][head])
                self.assertEqual(out["removed_class_masked"], [{"head": head, "removed_label": lab}])
                for other in L.HEADS:                                          # the other heads are unaffected
                    if other != head and other != "sleeve_style":
                        self.assertEqual(out["masks"][other], 1)

    def test_similar_looking_classes_are_not_substituted(self):
        pairs = [("sleeve_length", "cap-length", "short-sleeve"), ("sleeve_length", "elbow-length", "short-sleeve"),
                 ("sleeve_length", "three-quarter-sleeve", "long-sleeve"), ("neckline_type", "boat-neck", "round-neck"),
                 ("neckline_type", "scoop-neck", "round-neck"), ("sleeve_style", "bishop-sleeve", "puff-sleeve"),
                 ("sleeve_style", "flutter-sleeve", "puff-sleeve")]
        for head, removed, lookalike in pairs:
            self.assertNotEqual(L.convert_record(rec(**{head: removed}), CLASSES)["labels"][head], lookalike)

    def test_active_labels_keep_their_provenance_and_indices(self):
        out = L.convert_record(rec(neckline_type="collared-neck", sleeve_length="long-sleeve"), CLASSES)
        self.assertEqual(out["class_indices"]["neckline_type"], 3)
        self.assertEqual(out["class_indices"]["sleeve_length"], 2)
        self.assertTrue(out["trusted"]["neckline_type"])
        self.assertFalse(out["trusted"]["sleeve_style"])                     # rule-derived style stays untrusted

    def test_input_record_is_not_modified(self):
        r = rec(neckline_type="boat-neck")
        snap = copy.deepcopy(r)
        L.convert_record(r, CLASSES)
        self.assertEqual(r, snap)


class TestSleeveStyleNone(unittest.TestCase):
    def test_none_needs_an_explicit_trusted_sleeveless(self):
        no_annotation = L.convert_record(rec(sleeve_length=None, sleeve_style="none"), CLASSES)
        self.assertIsNone(no_annotation["labels"]["sleeve_style"])           # absence of a sleeve annotation is not evidence
        untrusted_len = L.convert_record(rec(sleeve_length="sleeveless", sleeve_style="none",
                                             prov={"sleeve_length": "fashionpedia_rule_derived"}), CLASSES)
        self.assertIsNone(untrusted_len["labels"]["sleeve_style"])
        with_sleeves = L.convert_record(rec(sleeve_length="short-sleeve", sleeve_style="none"), CLASSES)
        self.assertIsNone(with_sleeves["labels"]["sleeve_style"])

    def test_none_is_kept_and_trusted_with_explicit_sleeveless(self):
        out = L.convert_record(rec(sleeve_length="sleeveless", sleeve_style="none"), CLASSES)
        self.assertEqual(out["labels"]["sleeve_style"], "none")
        self.assertTrue(out["trusted"]["sleeve_style"])

    def test_a_sleeve_style_on_a_sleeveless_garment_is_masked(self):
        out = L.convert_record(rec(sleeve_length="sleeveless", sleeve_style="puff-sleeve"), CLASSES)
        self.assertIsNone(out["labels"]["sleeve_style"])
        self.assertIn("sleeve_style_conflict", out)


class TestCountsAndReadiness(unittest.TestCase):
    def _counts(self, records):
        return L.count_classes({s: [L.convert_record(r, CLASSES) for r in rs] for s, rs in records.items()}, CLASSES)

    def test_only_trusted_labels_count_toward_readiness(self):
        recs = {"train": [rec(f"a{i}", sleeve_style="regular-sleeve") for i in range(150)], "val": [], "test": []}
        c = self._counts(recs)
        self.assertEqual(c["train"]["sleeve_style"]["regular-sleeve"], {"total": 150, "trusted": 0})   # rule-derived
        self.assertEqual(c["train"]["neckline_type"]["round-neck"], {"total": 150, "trusted": 150})

    def test_missing_counts_are_exact(self):
        recs = {"train": [rec(f"t{i}") for i in range(40)], "val": [rec(f"v{i}", "val") for i in range(10)], "test": []}
        rep = L.readiness(self._counts(recs), TARGETS, CLASSES)
        self.assertEqual(rep["verdict"], "NOT_READY")
        self.assertEqual(rep["missing"]["train"]["neckline_type"]["round-neck"], 60)     # target 100 - 40
        self.assertEqual(rep["missing"]["val"]["neckline_type"]["round-neck"], 20)       # target 30 - 10
        self.assertEqual(rep["missing"]["test"]["neckline_type"]["round-neck"], 30)
        self.assertNotIn("round-neck", [c["class"] for c in rep["insufficient_classes"] if False])

    def test_ready_only_when_every_one_of_the_15_classes_meets_every_target(self):
        counts = {s: {h: {c: {"total": 500, "trusted": 500} for c in CLASSES[h]} for h in L.HEADS} for s in L.SPLITS}
        self.assertEqual(L.readiness(counts, TARGETS, CLASSES)["verdict"], "READY")
        counts["test"]["sleeve_length"]["sleeveless"]["trusted"] = 29                  # one class, one split, one short
        rep = L.readiness(counts, TARGETS, CLASSES)
        self.assertEqual(rep["verdict"], "NOT_READY")
        self.assertEqual(rep["insufficient_classes"], [{"head": "sleeve_length", "class": "sleeveless"}])
        self.assertEqual(len(rep["rows"]), 15)

    def test_table_prints_all_15_classes(self):
        counts = {s: {h: {c: {"total": 1, "trusted": 1} for c in CLASSES[h]} for h in L.HEADS} for s in L.SPLITS}
        table = L.format_table(counts, L.readiness(counts, TARGETS, CLASSES), CLASSES)
        for h in L.HEADS:
            for c in CLASSES[h]:
                self.assertIn(c, table)
        self.assertEqual(len(table.splitlines()), 16)


class TestHumanDecisions(unittest.TestCase):
    queue = [{"queue_id": "q1", "target_head": "sleeve_length", "target_class": "sleeveless", "split": "val", "source_image_id": 1,
              "source_annotation_id": 11, "source_image_path": "i.jpg", "bbox": [0, 0, 10, 10], "source_image_uid": "fashionpedia:val:1"},
             {"queue_id": "q2", "target_head": "neckline_type", "target_class": "collared-neck", "split": "train", "source_image_id": 2,
              "source_annotation_id": 22, "source_image_path": "j.jpg", "bbox": [0, 0, 10, 10], "source_image_uid": "fashionpedia:train:2"}]

    def test_only_valid_active_decisions_with_a_named_reviewer_are_accepted(self):
        decisions = [
            {"queue_id": "q1", "decision": "sleeveless", "reviewer_id": "rev1"},
            {"queue_id": "q2", "decision": "boat-neck", "reviewer_id": "rev1"},        # removed class -> refused
            {"queue_id": "q2", "decision": "collared-neck", "reviewer_id": ""},         # no reviewer -> refused
            {"queue_id": "zzz", "decision": "collared-neck", "reviewer_id": "rev1"},    # not in the queue
            {"queue_id": "q2", "decision": "uncertain", "reviewer_id": "rev1"},         # recorded, adds no label
        ]
        accepted, problems = L.validate_decisions(self.queue, decisions, CLASSES)
        self.assertEqual([a["queue"]["queue_id"] for a in accepted], ["q1"])
        self.assertEqual(len(problems), 3)

    def test_a_decision_from_the_wrong_head_is_refused(self):
        _, problems = L.validate_decisions(self.queue, [{"queue_id": "q1", "decision": "collared-neck", "reviewer_id": "r"}], CLASSES)
        self.assertEqual(len(problems), 1)

    def test_accepted_decision_labels_exactly_one_head_as_human_verified(self):
        accepted, _ = L.validate_decisions(self.queue, [{"queue_id": "q1", "decision": "sleeveless", "reviewer_id": "rev1"}], CLASSES)
        r = L.record_from_decision(accepted[0], CLASSES)
        self.assertEqual(r["labels"], {"garment_type": None, "neckline_type": None, "sleeve_length": "sleeveless", "sleeve_style": None})
        self.assertEqual(r["provenance"]["sleeve_length"], "human_verified")
        self.assertTrue(r["trusted"]["sleeve_length"])
        self.assertEqual(r["split"], "val")                                          # inherits the split of its source image
        self.assertEqual(sum(r["masks"].values()), 1)


class TestQueueHints(unittest.TestCase):
    def parent(self, cat=0, parts=(), **labels):
        return {"fashionpedia_category_id": cat, "attached_parts": [{"part_type": p} for p in parts],
                "labels": {h: {"label": v, "status": "candidate_mapping"} for h, v in labels.items()}}

    def test_sleeveless_hint_is_only_a_reason_to_look(self):
        self.assertIsNotNone(Q.candidate_hint(self.parent(cat=0), "sleeve_length", "sleeveless"))
        self.assertIsNone(Q.candidate_hint(self.parent(cat=0, parts=["sleeve"]), "sleeve_length", "sleeveless"))
        self.assertIsNone(Q.candidate_hint(self.parent(cat=4), "sleeve_length", "sleeveless"))       # jacket is out of scope

    def test_collar_and_set_in_sleeve_hints_need_their_evidence(self):
        self.assertIsNotNone(Q.candidate_hint(self.parent(parts=["collar"], neckline_type="collared-neck"), "neckline_type", "collared-neck"))
        self.assertIsNone(Q.candidate_hint(self.parent(parts=["sleeve"], neckline_type="collared-neck"), "neckline_type", "collared-neck"))
        self.assertIsNotNone(Q.candidate_hint(self.parent(sleeve_style="regular-sleeve"), "sleeve_style", "regular-sleeve"))
        self.assertIsNone(Q.candidate_hint(self.parent(sleeve_style="puff-sleeve"), "sleeve_style", "regular-sleeve"))

    def test_exhausted_classes_have_no_candidates(self):
        for head, cls in (("neckline_type", "square-neck"), ("neckline_type", "off-shoulder"),
                          ("sleeve_style", "puff-sleeve"), ("sleeve_style", "bell-sleeve")):
            self.assertIsNone(Q.candidate_hint(self.parent(neckline_type=cls, sleeve_style=cls), head, cls))


class TestTrainingGuard(unittest.TestCase):
    def _dir(self, verdict):
        d = tempfile.mkdtemp()
        sums = {}
        for s in L.SPLITS:
            p = os.path.join(d, f"{s}.jsonl")
            open(p, "w").write("{}\n")
            sums[f"{s}.jsonl"] = L.sha256_file(p)
        doc = {"readiness": {"verdict": verdict, "insufficient_classes": [{"head": "sleeve_length", "class": "sleeveless"}] if verdict != "READY" else []},
               "manifest_sha256": sums, "classes_config_sha256": L.sha256_file(CLASSES_PATH)}
        json.dump(doc, open(os.path.join(d, "counts.json"), "w"))
        return d

    def _args(self, d):
        class A:
            manifest_dir = d
            classes = CLASSES_PATH
            config = os.path.join(ROOT, "ai_training", "config", "m30_15class_config.json")
            output_dir = os.path.join(tempfile.mkdtemp(), "run")
            print_command = False
        return A

    def test_refuses_when_not_ready_and_launches_nothing(self):
        A = self._args(self._dir("NOT_READY"))
        ok, problems, _ = G.preflight(A)
        self.assertFalse(ok)
        self.assertIn("sleeve_length=sleeveless", " ".join(problems))
        with patch.object(subprocess, "call") as call, patch.object(sys, "argv", ["x", "--manifest-dir", A.manifest_dir]):
            self.assertEqual(G.main(), 2)
            call.assert_not_called()

    def test_refuses_when_counts_json_is_missing(self):
        A = self._args(tempfile.mkdtemp())
        self.assertFalse(G.preflight(A)[0])

    def test_detects_manifests_changed_after_the_readiness_check(self):
        d = self._dir("READY")
        open(os.path.join(d, "train.jsonl"), "a").write('{"tampered": true}\n')
        ok, problems, _ = G.preflight(self._args(d))
        self.assertFalse(ok)
        self.assertIn("changed", " ".join(problems))

    def test_ready_uses_the_15_class_config_and_never_an_old_checkpoint(self):
        A = self._args(self._dir("READY"))
        ok, problems, _ = G.preflight(A)
        self.assertTrue(ok, problems)
        cmd = G.training_command(A)
        self.assertIn(CLASSES_PATH, cmd)
        self.assertNotIn("--resume", cmd)
        self.assertFalse([c for c in cmd if "init" in c.lower() and "checkpoint" in c.lower()])
        self.assertTrue(any(c.endswith("train_multitask.py") for c in cmd))

    def test_wrong_checkpoint_dimensions_are_detected(self):
        import torch
        d = tempfile.mkdtemp()
        good, bad = os.path.join(d, "g.pt"), os.path.join(d, "b.pt")
        torch.save({"head_dimensions": {"garment_type": 3, "neckline_type": 5, "sleeve_length": 3, "sleeve_style": 4}}, good)
        torch.save({"head_dimensions": {"garment_type": 3, "neckline_type": 10, "sleeve_length": 6, "sleeve_style": 9}}, bad)
        self.assertTrue(G.verify_checkpoint(good)[0])
        self.assertFalse(G.verify_checkpoint(bad)[0])

    def test_refuses_output_inside_the_production_model_folder(self):
        A = self._args(self._dir("READY"))
        A.output_dir = "backend/app/ai/models/oops"
        ok, problems, _ = G.preflight(A)
        self.assertFalse(ok)


class TestProductionIsolation(unittest.TestCase):
    def test_backend_and_frontend_do_not_reference_the_future_pipeline(self):
        needles = ("classes_v2_15class", "labels15", "manifests_15class", "m30_15class", "train_15class")
        for base in ("backend/app", "frontend/src"):
            for dirpath, _, files in os.walk(os.path.join(ROOT, base)):
                if "node_modules" in dirpath or "__pycache__" in dirpath:
                    continue
                for f in files:
                    if f.endswith((".py", ".js", ".jsx")):
                        text = open(os.path.join(dirpath, f), encoding="utf-8", errors="ignore").read()
                        for n in needles:
                            self.assertNotIn(n, text, f"{f} references {n}")

    def test_deployed_m13_taxonomy_file_is_unchanged(self):
        m13 = json.load(open(M13_CLASSES_PATH))
        self.assertEqual(m13["total_label_count"], 28)
        self.assertEqual(m13["outputs"]["neckline_type"]["class_count"], 10)


if __name__ == "__main__":
    unittest.main()
