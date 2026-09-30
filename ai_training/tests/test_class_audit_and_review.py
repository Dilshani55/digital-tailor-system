"""Weak-class recovery audit and human-review contact sheets (synthetic data, no local dataset needed)."""
import csv
import json
import os
import tempfile
import unittest

from PIL import Image

from ai_training.scripts import audit_15class_classes as audit
from ai_training.scripts import make_review_contact_sheets as sheets


def _raw(tmp, annotations, images=None):
    cats = [{"id": 0, "name": "shirt, blouse"}, {"id": 1, "name": "top, t-shirt, sweatshirt"},
            {"id": 10, "name": "dress"}, {"id": 31, "name": "sleeve"}]
    images = images or [{"id": i, "file_name": f"{i}.jpg"} for i in range(1, 6)]
    for split in ("train2020", "val2020"):
        data = {"categories": cats, "images": images, "attributes": [],
                "annotations": annotations if split == "train2020" else []}
        with open(os.path.join(tmp, f"instances_attributes_{split}.json"), "w", encoding="utf-8") as f:
            json.dump(data, f)


class TestSleevelessRecovery(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self._raw_dir = audit.RAW
        audit.RAW = self.tmp

    def tearDown(self):
        audit.RAW = self._raw_dir

    def test_only_unambiguous_single_tops_with_explicit_sleeveless_are_candidates(self):
        _raw(self.tmp, [
            # image 1: one top + sleeveless part -> candidate
            {"id": 11, "image_id": 1, "category_id": 1, "bbox": [0, 0, 10, 10], "attribute_ids": []},
            {"id": 12, "image_id": 1, "category_id": 31, "bbox": [0, 0, 2, 2], "attribute_ids": [156]},
            # image 2: top + dress -> ambiguous, skipped
            {"id": 21, "image_id": 2, "category_id": 1, "bbox": [0, 0, 10, 10], "attribute_ids": []},
            {"id": 22, "image_id": 2, "category_id": 10, "bbox": [0, 0, 10, 10], "attribute_ids": []},
            {"id": 23, "image_id": 2, "category_id": 31, "bbox": [0, 0, 2, 2], "attribute_ids": [156]},
            # image 3: two tops -> ambiguous, skipped
            {"id": 31, "image_id": 3, "category_id": 0, "bbox": [0, 0, 10, 10], "attribute_ids": []},
            {"id": 32, "image_id": 3, "category_id": 1, "bbox": [0, 0, 10, 10], "attribute_ids": []},
            {"id": 33, "image_id": 3, "category_id": 31, "bbox": [0, 0, 2, 2], "attribute_ids": [156]},
            # image 4: top WITHOUT any sleeve annotation -> absence is not evidence, skipped
            {"id": 41, "image_id": 4, "category_id": 1, "bbox": [0, 0, 10, 10], "attribute_ids": []},
            # image 5: already in the manifests -> skipped
            {"id": 51, "image_id": 5, "category_id": 1, "bbox": [0, 0, 10, 10], "attribute_ids": []},
            {"id": 52, "image_id": 5, "category_id": 31, "bbox": [0, 0, 2, 2], "attribute_ids": [156]},
        ])
        rows = audit.sleeveless_recovery_candidates({"fashionpedia:train2020:51"})
        self.assertEqual([r["source_record_uid"] for r in rows], ["fashionpedia:train2020:11"])
        self.assertEqual(rows[0]["provenance"], {"sleeve_length": "fashionpedia_direct",
                                                 "sleeve_style": "derived_from_explicit_sleeveless"})
        self.assertEqual(rows[0]["evidence_annotation_ids"], [12])

    def test_upper_bound_counts_explicit_attributes_on_unambiguous_images(self):
        _raw(self.tmp, [
            {"id": 11, "image_id": 1, "category_id": 1, "bbox": [0, 0, 1, 1], "attribute_ids": []},
            {"id": 12, "image_id": 1, "category_id": 31, "bbox": [0, 0, 1, 1], "attribute_ids": [209]},
            {"id": 21, "image_id": 2, "category_id": 10, "bbox": [0, 0, 1, 1], "attribute_ids": []},
            {"id": 22, "image_id": 2, "category_id": 31, "bbox": [0, 0, 1, 1], "attribute_ids": [209]},
        ])
        ub = audit.raw_upper_bounds()
        self.assertEqual(ub[("sleeve_style", "puff-sleeve")], 1)        # the dress image does not count
        self.assertEqual(ub[("sleeve_length", "sleeveless")], 0)

    def test_missing_raw_files_give_no_numbers(self):
        audit.RAW = os.path.join(self.tmp, "absent")
        self.assertIsNone(audit.raw_upper_bounds())
        self.assertEqual(audit.sleeveless_recovery_candidates(set()), [])


class TestContactSheets(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self._dirs = (sheets.QUEUE_DIR, sheets.OUT_DIR)
        sheets.QUEUE_DIR = self.tmp
        sheets.OUT_DIR = os.path.join(self.tmp, "contact_sheets")
        self.img = os.path.join(self.tmp, "g.jpg")
        Image.new("RGB", (100, 120), (200, 50, 50)).save(self.img)

    def tearDown(self):
        sheets.QUEUE_DIR, sheets.OUT_DIR = self._dirs

    def _row(self, i, cls="collared-neck", decision=""):
        return {"queue_id": f"q{i}", "split": "val", "target_head": "neckline_type", "target_class": cls,
                "source_image_path": self.img, "bbox": [10, 10, 50, 60], "decision": decision}

    def test_sheets_and_csv_list_every_undecided_row_with_empty_decisions(self):
        rows = [self._row(i) for i in range(40)] + [self._row(99, decision="collared-neck")]
        self.assertEqual(sheets.make_sheets(rows), 2)                     # 36 per sheet
        with open(os.path.join(sheets.OUT_DIR, "collared-neck_val_01.csv"), encoding="utf-8") as f:
            listed = list(csv.DictReader(f))
        self.assertEqual(len(listed), 36)
        self.assertTrue(all(r["decision"] == "" and r["reviewer_id"] == "" for r in listed))
        self.assertTrue(os.path.exists(os.path.join(sheets.OUT_DIR, "collared-neck_val_02.png")))

    def test_collect_keeps_only_answered_rows_with_a_reviewer(self):
        sheets.make_sheets([self._row(i) for i in range(3)])
        path = os.path.join(sheets.OUT_DIR, "collared-neck_val_01.csv")
        with open(path, encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        rows[0].update(decision="collared-neck", reviewer_id="R1")
        rows[1].update(decision="reject", reviewer_id="")               # no reviewer -> ignored
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
        sheets.collect()
        with open(os.path.join(self.tmp, "decisions.jsonl"), encoding="utf-8") as f:
            decisions = [json.loads(line) for line in f]
        self.assertEqual([(d["queue_id"], d["decision"], d["reviewer_id"]) for d in decisions], [("q0", "collared-neck", "R1")])


if __name__ == "__main__":
    unittest.main()
