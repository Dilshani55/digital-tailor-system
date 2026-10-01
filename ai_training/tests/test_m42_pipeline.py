"""M42 pipeline: acceptance gate (fixed before training), audit helpers, manifest fixes, review decisions, review tool.

No dataset or checkpoint is needed, except the fine-tuning-depth test, which skips visibly without the pretrained file.
"""
import copy
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath("."))

from ai_training.scripts.v2 import audit_datasets as audit  # noqa: E402
from ai_training.scripts.v2 import build_m42_manifests as bm  # noqa: E402
from ai_training.scripts.v2 import build_review_queue_m42 as bq  # noqa: E402
from ai_training.scripts.v2 import check_m42_gate as gate_mod  # noqa: E402
from ai_training.training import labels15 as L  # noqa: E402

GATE = json.load(open("ai_training/config/m42_acceptance.json", encoding="utf-8"))
CLASSES = L.load_classes("ai_training/config/classes_v2_15class.json")
PRETRAINED = "ai_training/data/training_runs/pretrained/yolov8n-cls.pt"


def head(acc, f1, threshold=None, coverage=0.0, answered_acc=None, n=100):
    return {"n": n, "accuracy": acc, "macro_f1": f1,
            "answered": {"threshold": threshold, "coverage": coverage, "accuracy_when_answered": answered_acc}}


def passing():
    return {"garment_type": head(0.80, 0.80), "neckline_type": head(0.70, 0.55),
            "sleeve_length": head(0.86, 0.84, 0.6, 0.80, 0.93), "sleeve_style": head(0.93, 0.65)}


def record(uid="r1", source="deepfashion_multimodal", **labels):
    prov = {"garment_type": "dmm_shop_category", "neckline_type": "dmm_human_shape", "sleeve_length": "dmm_human_shape",
            "sleeve_style": "derived_from_explicit_sleeveless"}
    r = {"record_uid": uid, "source_dataset": source, "split": "train", "crop_path": f"{uid}_crop.jpg", "full_image_path": f"{uid}_full.jpg",
         "labels": {h: labels.get(h) for h in L.HEADS}, "masks": {h: int(labels.get(h) is not None) for h in L.HEADS},
         "provenance": {h: (prov[h] if labels.get(h) is not None else L.MASKED_PROVENANCE) for h in L.HEADS}}
    return bm.finish(r, CLASSES)


class TestAcceptanceGate(unittest.TestCase):
    def test_the_gate_was_written_before_training_with_numeric_targets(self):
        self.assertTrue(GATE["written_before_training"])
        self.assertEqual(GATE["baseline"]["sha256"], "3ed45bc121c0eea82fb44280a6a5b5e2e2beaf43035fc501cf3e5089436c66be")
        self.assertEqual(GATE["required"]["macro_f1_min"], {"garment_type": 0.79, "neckline_type": 0.53, "sleeve_length": 0.81, "sleeve_style": 0.61})
        self.assertEqual(GATE["required"]["auto_answer"]["min_accuracy_when_answered"], 0.9)
        for h, target in GATE["required"]["macro_f1_min"].items():            # every target is above or within 0.01 of M40
            self.assertGreaterEqual(target, GATE["baseline"]["detector_crop_test_all"][h]["macro_f1"] - 0.01)

    def test_m40_itself_does_not_pass_so_a_candidate_must_really_be_better(self):
        base = GATE["baseline"]["detector_crop_test_all"]
        m40 = {h: head(v["accuracy"], v["macro_f1"]) for h, v in base.items()}
        m40["sleeve_length"] = head(0.8399, 0.8174, 0.70, 0.797, 0.922)
        result = gate_mod.decide(GATE, m40, None, True)
        self.assertEqual(result["decision"], "FAIL")
        failed = {i["item"] for i in result["items"] if not i["passed"]}
        self.assertEqual(failed, {"garment_type: macro-F1", "neckline_type: macro-F1"})

    def test_a_candidate_that_meets_every_item_passes(self):
        result = gate_mod.decide(GATE, passing(), None, True)
        self.assertEqual(result["decision"], "PASS", [i for i in result["items"] if not i["passed"]])
        self.assertIn("rollback", result["action"])

    def test_each_single_shortfall_fails_and_is_named_with_its_target(self):
        cases = {
            "garment_type: macro-F1": lambda c: c["garment_type"].update(macro_f1=0.789),
            "neckline_type: accuracy not below M40": lambda c: c["neckline_type"].update(accuracy=0.65),
            "sleeve_length: accuracy when answered": lambda c: c["sleeve_length"]["answered"].update(accuracy_when_answered=0.899),
            "sleeve_length: coverage": lambda c: c["sleeve_length"]["answered"].update(coverage=0.74),
            "sleeve_length: still answered automatically": lambda c: c["sleeve_length"]["answered"].update(threshold=None),
            "garment_type: accuracy when answered": lambda c: c["garment_type"]["answered"].update(threshold=0.9, coverage=0.5, accuracy_when_answered=0.85),
        }
        for name, break_it in cases.items():
            cand = passing()
            break_it(cand)
            result = gate_mod.decide(GATE, cand, None, True)
            self.assertEqual(result["decision"], "FAIL", name)
            failed = [i for i in result["items"] if not i["passed"]]
            self.assertEqual([i["item"] for i in failed], [name])
            self.assertIsNotNone(failed[0]["target"])

    def test_unverified_integrity_or_a_missing_head_is_a_failure(self):
        self.assertEqual(gate_mod.decide(GATE, passing(), None, None)["decision"], "FAIL")
        self.assertEqual(gate_mod.decide(GATE, passing(), None, False)["decision"], "FAIL")
        cand = passing()
        del cand["sleeve_style"]
        self.assertEqual(gate_mod.decide(GATE, cand, None, True)["decision"], "FAIL")

    def test_new_classes_are_offered_only_with_enough_reviewed_test_examples_and_f1(self):
        def reviewed(support, f1):
            return {"neckline_type": {"per_class": {"collared-neck": {"support": support, "f1": f1}}},
                    "sleeve_style": {"per_class": {"regular-sleeve": {"support": 40, "f1": 0.7}}}}
        none = gate_mod.decide(GATE, passing(), None, True)["new_classes"]
        self.assertFalse(none["collared-neck"]["offered_as_ai_suggestion"])
        self.assertFalse(gate_mod.decide(GATE, passing(), reviewed(29, 0.9), True)["new_classes"]["collared-neck"]["offered_as_ai_suggestion"])
        self.assertFalse(gate_mod.decide(GATE, passing(), reviewed(60, 0.59), True)["new_classes"]["collared-neck"]["offered_as_ai_suggestion"])
        ok = gate_mod.decide(GATE, passing(), reviewed(60, 0.61), True)
        self.assertTrue(ok["new_classes"]["collared-neck"]["offered_as_ai_suggestion"])
        self.assertTrue(ok["new_classes"]["regular-sleeve"]["offered_as_ai_suggestion"])
        self.assertEqual(ok["decision"], "PASS")                               # new classes never decide pass / fail


class TestAuditHelpers(unittest.TestCase):
    def test_trust_tiers(self):
        for p in ("human_verified", "fashionpedia_direct", "df2_human_category", "dmm_human_shape", "derived_from_explicit_sleeveless"):
            self.assertEqual(audit.tier(p), "trusted")
        for p in ("dmm_shop_category", "dmm_navel_uncovered", "accepted_pseudo_label"):
            self.assertEqual(audit.tier(p), "proxy")
        for p in ("fashionpedia_rule_derived", "candidate_dmm_lapel_needs_human_review", "missing/masked"):
            self.assertEqual(audit.tier(p), "other")

    def test_deepfashion2_ids_from_different_folders_are_different_photos(self):
        train = {"record_uid": "df2:train:023609", "source_image_uid": "df2:023609",
                 "full_image_path": "ai_training/datasets/deepfashion2_tops/images/train/023609_full.jpg"}
        test = {"record_uid": "df2:test:023609", "source_image_uid": "df2:023609",
                "full_image_path": "ai_training/datasets/deepfashion2_tops/images/test/023609_full.jpg"}
        self.assertNotEqual(audit.photo_identity(train), audit.photo_identity(test))
        fp = {"record_uid": "fashionpedia:train2020:1", "source_image_uid": "fashionpedia:train2020:41604", "source_dataset": "fashionpedia"}
        self.assertEqual(audit.photo_identity(fp), "fashionpedia:train2020:41604")

    def test_near_duplicates_use_hamming_distance_4(self):
        train = [0b0, 0xFFFF0000FFFF0000]
        hits = audit.near_duplicates([0b1111, 0b11111, 0xFFFF0000FFFF0001, 0x0F0F0F0F0F0F0F0F], train)
        self.assertEqual(hits, [0, -1, 1, -1])

    def test_photo_of_prefers_the_whole_photo(self):
        self.assertEqual(audit.photo_of({"crop_path": "c.jpg", "full_image_path": "a\\b.jpg"}), "a/b.jpg")
        self.assertEqual(audit.photo_of({"crop_path": None, "source_image_path": "s.jpg"}), "s.jpg")


class TestManifestFixes(unittest.TestCase):
    def test_a_sleeveless_tee_category_record_is_masked_not_relabelled(self):
        tank = record("tank", garment_type="t-shirt", sleeve_length="sleeveless", sleeve_style="none")
        tee = record("tee", garment_type="t-shirt", sleeve_length="short-sleeve")
        blouse = record("blouse", garment_type="blouse", sleeve_length="sleeveless", sleeve_style="none")
        human = record("human", garment_type="t-shirt", sleeve_length="sleeveless")
        human["provenance"]["garment_type"] = "human_verified"
        self.assertEqual(bm.mask_tank_tops([tank, tee, blouse, human], CLASSES), 1)
        self.assertIsNone(tank["labels"]["garment_type"])
        self.assertEqual((tank["masks"]["garment_type"], tank["provenance"]["garment_type"]), (0, L.MASKED_PROVENANCE))
        self.assertIn("tank top", tank["masked_reason"]["garment_type"])
        self.assertEqual(tank["labels"]["sleeve_length"], "sleeveless")           # the human sleeve label is kept
        self.assertEqual(tank["class_indices"]["garment_type"], None)
        self.assertEqual(tee["labels"]["garment_type"], "t-shirt")
        self.assertEqual(blouse["labels"]["garment_type"], "blouse")              # a sleeveless blouse is still a blouse
        self.assertEqual(human["labels"]["garment_type"], "t-shirt")              # a person's label is never overridden

    def test_proxy_and_masked_labels_are_not_trusted(self):
        r = record(garment_type="blouse", neckline_type="v-neck")
        self.assertEqual(r["trusted"], {"garment_type": False, "neckline_type": True, "sleeve_length": False, "sleeve_style": False})


class TestReviewDecisions(unittest.TestCase):
    def setUp(self):
        self.train = [record("dmm:a", sleeve_length="long-sleeve"), record("df2:train:7", source="deepfashion2", sleeve_length="short-sleeve"),
                      record("df2:train:8", source="deepfashion2", sleeve_length="sleeveless", sleeve_style="none")]
        self.train[0]["masked_candidate"] = {"neckline_type": "collared-neck"}
        self.sets = {"train": self.train, "val": []}

        def q(qid, head_, split, uid=None, **extra):
            return dict(queue_id=qid, head=head_, split=split, source="x", record_uid=uid, image_path=f"{qid}.jpg",
                        options=bq.OPTIONS[head_], **extra)
        self.queue = [q("q-collar", "neckline_type", "train", "dmm:a"), q("q-regular", "sleeve_style", "train", "df2:train:7"),
                      q("q-none-conflict", "sleeve_style", "train", "df2:train:7"), q("q-sleeveless-regular", "sleeve_style", "train", "df2:train:8"),
                      q("q-test", "neckline_type", "test", "dmm:t", full_image_path="t_full.jpg"),
                      q("q-new-val", "sleeve_style", "val", None, bbox_xywh=[1, 2, 3, 4], source_annotation_id=99),
                      q("q-other", "neckline_type", "train", "dmm:a")]

    def apply(self, *pairs):
        decisions = [{"queue_id": a, "decision": b, "reviewer_id": "rev", "reviewed_at": "2026-10-01T00:00:00Z"} for a, b in pairs]
        return bm.apply_decisions(self.sets, self.queue, decisions, CLASSES)

    def test_a_class_answer_becomes_a_human_verified_label_on_the_same_record(self):
        test, report = self.apply(("q-collar", "collared-neck"), ("q-regular", "regular-sleeve"))
        a, b = self.train[0], self.train[1]
        self.assertEqual((a["labels"]["neckline_type"], a["provenance"]["neckline_type"], a["masks"]["neckline_type"]), ("collared-neck", "human_verified", 1))
        self.assertNotIn("masked_candidate", a)
        self.assertEqual(a["class_indices"]["neckline_type"], 3)
        self.assertTrue(a["trusted"]["neckline_type"])
        self.assertEqual(a["labels"]["sleeve_length"], "long-sleeve")             # other heads untouched
        self.assertEqual((b["labels"]["sleeve_style"], b["reviewed"]["sleeve_style"]["reviewer_id"]), ("regular-sleeve", "rev"))
        self.assertEqual(test, [])
        self.assertEqual(report["applied"], {"train: neckline_type=collared-neck": 1, "train: sleeve_style=regular-sleeve": 1})

    def test_other_and_unclear_add_no_label(self):
        before = copy.deepcopy(self.train)
        _, report = self.apply(("q-collar", "unclear"), ("q-regular", "other"))
        self.assertEqual(self.train, before)
        self.assertEqual(report["applied"], {})
        self.assertEqual(report["answers"], {"neckline_type=unclear": 1, "sleeve_style=other": 1})

    def test_the_hint_is_never_used_without_an_answer(self):
        _, report = self.apply()
        self.assertIsNone(self.train[0]["labels"]["neckline_type"])               # the lapel candidate stays masked
        self.assertEqual(report["applied"], {})

    def test_an_answer_that_contradicts_a_trusted_label_is_reported_not_applied(self):
        _, report = self.apply(("q-none-conflict", "none"), ("q-sleeveless-regular", "regular-sleeve"))
        self.assertIsNone(self.train[1]["labels"]["sleeve_style"])
        self.assertEqual(self.train[2]["labels"]["sleeve_style"], "none")
        self.assertEqual([c["queue_id"] for c in report["conflicts"]], ["q-none-conflict", "q-sleeveless-regular"])

    def test_test_split_answers_go_to_a_separate_file_with_only_the_reviewed_head(self):
        test, _ = self.apply(("q-test", "collared-neck"))
        self.assertEqual(len(test), 1)
        self.assertEqual(test[0]["labels"], {"garment_type": None, "neckline_type": "collared-neck", "sleeve_length": None, "sleeve_style": None})
        self.assertEqual(test[0]["split"], "test")
        self.assertEqual(len(self.train), 3)                                      # nothing added to training

    def test_a_reviewed_photo_not_yet_in_a_manifest_is_added_to_its_own_split(self):
        self.apply(("q-new-val", "regular-sleeve"))
        self.assertEqual(len(self.sets["val"]), 1)
        new = self.sets["val"][0]
        self.assertEqual((new["split"], new["bbox"], new["labels"]["sleeve_style"]), ("val", [1, 2, 3, 4], "regular-sleeve"))
        self.assertEqual(len(self.train), 3)

    def test_unknown_or_invalid_answers_are_ignored(self):
        _, report = self.apply(("nope", "collared-neck"), ("q-collar", "blouse"))
        self.assertEqual(report["unknown_queue_ids"], 1)
        self.assertIsNone(self.train[0]["labels"]["neckline_type"])


class TestReviewQueueAndTool(unittest.TestCase):
    def test_the_queue_plan_and_options(self):
        total = sum(n for per in bq.PLAN.values() for n in per.values())
        self.assertTrue(600 <= total <= 800, total)
        for head_, options in bq.OPTIONS.items():
            self.assertTrue(set(options) - {"other", "unclear"} <= set(CLASSES[head_]), head_)
            self.assertEqual(options[-2:], ["other", "unclear"])
        self.assertIn("collared-neck", bq.OPTIONS["neckline_type"])
        self.assertIn("regular-sleeve", bq.OPTIONS["sleeve_style"])
        for key, per in bq.PLAN.items():
            self.assertGreaterEqual(per["val"], 20, key)                          # each class can be validated and tested
            self.assertGreaterEqual(per["test"], 30, key)

    def test_the_review_tool_saves_valid_answers_only_and_resumes(self):
        from PIL import Image
        from ai_training.tools import review_labels as tool
        d = tempfile.mkdtemp()
        img = os.path.join(d, "a.jpg")
        Image.new("RGB", (200, 300), (120, 80, 60)).save(img)
        queue = os.path.join(d, "queue.jsonl")
        rows = [dict(queue_id="q1", head="neckline_type", source="s", split="train", hint="h", question="Q?", image_path=img,
                     options=bq.OPTIONS["neckline_type"], bbox_xywh=[20, 30, 100, 150]),
                dict(queue_id="q2", head="sleeve_style", source="s", split="val", hint="h", question="Q?", image_path=img,
                     options=bq.OPTIONS["sleeve_style"])]
        with open(queue, "w", encoding="utf-8") as f:
            f.write("\n".join(json.dumps(r) for r in rows) + "\n")
        decisions = os.path.join(d, "out", "decisions.jsonl")
        tool.configure(queue, decisions, "Reviewer A")
        c = tool.app.test_client()
        self.assertEqual(c.get("/api/state").get_json()["total"], 2)
        item = c.get("/api/item/0").get_json()
        self.assertEqual([o["value"] for o in item["options"]], bq.OPTIONS["neckline_type"])
        self.assertTrue(all(o["en"] and o["si"] for o in item["options"]))        # a definition for every answer
        self.assertEqual(c.get("/img/0/crop").mimetype, "image/jpeg")
        self.assertEqual(c.get("/img/9/crop").status_code, 404)
        self.assertEqual(c.post("/api/decide", json={"queue_id": "q1", "decision": "regular-sleeve"}).status_code, 400)   # wrong head's class
        self.assertEqual(c.post("/api/decide", json={"queue_id": "zzz", "decision": "v-neck"}).status_code, 404)
        self.assertFalse(os.path.exists(decisions))
        self.assertEqual(c.post("/api/decide", json={"queue_id": "q1", "decision": "collared-neck"}).status_code, 200)
        self.assertEqual(c.post("/api/decide", json={"queue_id": "q1", "decision": "v-neck"}).status_code, 200)            # corrected
        saved = L.load_jsonl(decisions)
        self.assertEqual(len(saved), 1)
        self.assertEqual((saved[0]["decision"], saved[0]["reviewer_id"], saved[0]["human_verified"]), ("v-neck", "Reviewer A", True))
        tool.configure(queue, decisions, "Reviewer A")                            # restart: the answer is still there
        self.assertEqual(tool.app.test_client().get("/api/state").get_json()["items"][0]["decision"], "v-neck")


class TestFineTuningDepth(unittest.TestCase):
    @unittest.skipUnless(os.path.exists(PRETRAINED), "SKIPPED: pretrained yolov8n-cls.pt not on this machine")
    def test_default_depth_is_unchanged_and_a_smaller_number_unfreezes_more(self):
        from ai_training.models.multitask_yolov8 import YOLOv8MultiTaskClassifier
        model = YOLOv8MultiTaskClassifier(pretrained_path=PRETRAINED, head_dims={"garment_type": 3, "neckline_type": 5, "sleeve_length": 3, "sleeve_style": 4},
                                          freeze_backbone=True)

        def trainable_layers():
            return [i for i in range(9) if all(p.requires_grad for p in model.backbone[i].parameters()) and list(model.backbone[i].parameters())]

        model.unfreeze_partial_backbone()
        self.assertEqual(trainable_layers(), [8])                                  # exactly what M40 / M41 trained
        self.assertTrue(all(p.requires_grad for p in model.projection_conv.parameters()))
        model.unfreeze_partial_backbone(4)
        self.assertEqual(trainable_layers(), [4, 5, 6, 7, 8])
        model.unfreeze_partial_backbone(8)
        self.assertEqual(trainable_layers(), [8])                                  # and it can be narrowed again

    def test_the_m42_recipe_is_written_down(self):
        cfg = json.load(open("ai_training/config/m42_config.json", encoding="utf-8"))
        self.assertEqual((cfg["stage_b_unfreeze_from"], cfg["stage_b_epochs"], cfg["early_stopping_patience"], cfg["random_seed"]), (4, 40, 8, 42))
        self.assertEqual(cfg["provenance_weights"]["candidate_dmm_lapel_needs_human_review"], 0.0)
        self.assertEqual(cfg["provenance_weights"]["fashionpedia_rule_derived"], 0.0)
        self.assertEqual(cfg["provenance_weights"]["human_verified"], 1.0)


if __name__ == "__main__":
    unittest.main()
