"""Printable 1:1 tiled PDF + export routes (fabric estimate, PDF) - vector-level verification with PyMuPDF."""
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

try:
    import pymupdf
except ImportError:                      # dev dependency (requirements-dev.txt); reported, never silent
    pymupdf = None

from app import create_app
from flask_jwt_extended import create_access_token
from app.logic import pdf_generator as pg
from app.logic.nesting_algorithm import estimate_fabric
from app.logic.parametric_engine import ParametricEngine
from tests.fixtures import measurements, design

CM = 72.0 / 2.54


def _build(garment="blouse", neck="round-neck", sleeve="short-sleeve", fabric="woven", width=114, mode="auto", **over):
    style = "none" if sleeve == "sleeveless" else "regular-sleeve"
    m = measurements("medium", fabric_type=fabric, **over)
    data = ParametricEngine(m, design_spec={"attributes": design(garment, neck, sleeve, style)}).generate()
    nest = estimate_fabric(data["pattern_pieces"], width, mode, fabric)
    return m, data, nest


def _generate(path, **kw):
    m, data, nest = _build(**kw)
    gen = pg.PDFGenerator(data, nest, m, {}, path, fabric_name="Cotton Poplin", garment_title="Test pattern")
    gen.generate()
    return gen, data, nest


@unittest.skipIf(pymupdf is None, "SKIPPED: pymupdf not installed (pip install -r requirements-dev.txt)")
class TestPrintablePdf(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.path = os.path.join(cls.tmp, "p.pdf")
        cls.gen, cls.data, cls.nest = _generate(cls.path)
        cls.doc = pymupdf.open(cls.path)

    def test_pages_and_a4(self):
        self.assertEqual(len(self.doc), self.gen.info["pages"])
        self.assertEqual(len(self.doc), 3 + len(self.gen.tiles))
        for page in self.doc:
            self.assertAlmostEqual(page.rect.width, 595.28, delta=0.5)
            self.assertAlmostEqual(page.rect.height, 841.89, delta=0.5)

    def test_printing_instructions_and_page_numbers(self):
        first = self.doc[0].get_text()
        self.assertIn("ACTUAL SIZE", first)
        self.assertIn("100 %", first)
        self.assertIn("Fit to page", first)
        n = len(self.doc)
        for i, page in enumerate(self.doc, 1):
            self.assertIn(f"Page {i} of {n}", page.get_text())

    def _squares(self, page):
        out = []
        for d in page.get_drawings():
            r = d["rect"]
            if abs(r.width - 5 * CM) < 0.4 and abs(r.height - 5 * CM) < 0.4:
                out.append(r)
        return out

    def test_calibration_square_is_exactly_5cm(self):
        self.assertTrue(self._squares(self.doc[0]), "cover page has no 5 cm calibration square")
        on_tiles = sum(1 for i in range(3, len(self.doc)) if self._squares(self.doc[i]))
        self.assertGreaterEqual(on_tiles, 1, "no tile carries the calibration square")

    def test_summary_page_contents(self):
        text = self.doc[1].get_text()
        for word in ("Bust", "Waist", "Cotton Poplin", "Fabric estimate", "Front Bodice", "Back Bodice", "hem SA"):
            self.assertIn(word, text)
        self.assertIn("Round Neck", self.doc[0].get_text())

    def test_layout_page_and_estimate(self):
        text = self.doc[2].get_text()
        self.assertIn("NOT to scale", text)
        self.assertIn(str(self.nest["fabric_length_cm"]), text)

    def test_tile_pages_have_labels_marks_and_pieces(self):
        for i in range(3, len(self.doc)):
            text = self.doc[i].get_text()
            self.assertRegex(text, r"[A-Z]\d")
            self.assertIn("Actual size", text)
        all_text = " ".join(self.doc[i].get_text() for i in range(3, len(self.doc)))
        for word in ("FRONT BODICE", "BACK BODICE", "SLEEVE", "PLACE ON FOLD", "CUT 2", "SA 1.5 cm"):
            self.assertIn(word, all_text)

    def test_every_piece_is_on_some_tile_and_tiles_overlap(self):
        self.assertAlmostEqual(pg.STEP_X, pg.TILE_W_CM - pg.OVERLAP_CM)
        self.assertAlmostEqual(pg.STEP_Y, pg.TILE_H_CM - pg.OVERLAP_CM)
        for pl in self.gen.placements:
            covered = [(c, r) for (c, r) in self.gen.tiles
                       if pl["x"] < c * pg.STEP_X + pg.TILE_W_CM and pl["x"] + pl["w"] > c * pg.STEP_X
                       and pl["y"] < r * pg.STEP_Y + pg.TILE_H_CM and pl["y"] + pl["h"] > r * pg.STEP_Y]
            self.assertTrue(covered)

    def test_metadata_says_actual_size(self):
        meta = self.doc.metadata
        self.assertIn("Actual Size", meta["subject"])

    def test_true_scale_on_a_known_rectangle(self):
        """A 10 x 15 cm piece must be drawn 283.46 x 425.2 pt (1 cm = 28.3465 pt)."""
        rect = [(0, 0), (10, 0), (10, 15), (0, 15)]
        piece = {"name": "Test Block", "piece_type": "test", "cut_count": 1, "cut_on_fold": False,
                 "cutting_line": rect, "outline": [(1, 1), (9, 1), (9, 14), (1, 14)],
                 "cut_bounding_box": {"width_cm": 10, "height_cm": 15, "min_x": 0, "min_y": 0},
                 "bounding_box": {"width_cm": 8, "height_cm": 13, "min_x": 1, "min_y": 1},
                 "grain_line": {"start": [5, 3], "end": [5, 12]}, "fold_line": None, "darts": [], "notches": [],
                 "seam_allowances": {"seam": 1.0}, "seam_allowance_cm": 1.0, "polygon_area_cm2": 104}
        path = os.path.join(self.tmp, "block.pdf")
        pg.PDFGenerator({"pattern_pieces": [piece], "design_attributes": {}, "drafting_block": {}},
                        {}, {}, {}, path).generate()
        doc = pymupdf.open(path)
        found = False
        for page in doc:
            for d in page.get_drawings():
                r = d["rect"]
                if abs(r.width - 10 * CM) < 0.5 and abs(r.height - 15 * CM) < 0.5:
                    found = True
        self.assertTrue(found, "the 10 x 15 cm cutting line was not drawn at 1:1")

    def test_pages_render_to_images(self):
        for i in (0, 1, 2, 3):
            pix = self.doc[i].get_pixmap(dpi=50)
            self.assertGreater(pix.width, 300)
            self.assertGreater(len(pix.samples), 1000)

    def test_every_supported_design_produces_a_pdf(self):
        for kw in (dict(garment="t-shirt", neck="v-neck", sleeve="long-sleeve", fabric="knit"),
                   dict(garment="crop-top", neck="square-neck", sleeve="sleeveless", garment_length_cm=36),
                   dict(garment="crop-top", neck="round-neck", sleeve="short-sleeve", fabric="knit", garment_length_cm=36)):
            gen, _, _ = _generate(os.path.join(self.tmp, "x.pdf"), **kw)
            self.assertGreaterEqual(len(pymupdf.open(os.path.join(self.tmp, "x.pdf"))), 4)


class TestExportRoutes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config["TESTING"] = True
        with cls.app.app_context():
            cls.headers = {"Authorization": f"Bearer {create_access_token(identity='user-1')}"}
        cls.m, cls.data, _ = _build()

    def _pattern(self, passed=True, summary=None):
        pat = MagicMock()
        pat.id = "p1"
        pat.session_id.user_id.id = "user-1"
        pat.session_id.image_id.detected_features = {}
        pat.validation_passed = passed
        pat.validation_report = {"errors": ["broken"]}
        pat.pattern_coordinates = self.data["pattern_pieces"]
        pat.nesting_summary = summary or {}
        pat.measurements_snapshot = {"fabric_type": "woven", "fit_preference": "standard",
                                     "canonical_cm": {k: v for k, v in self.m.items() if k.endswith("_cm")}}
        pat.design_spec = {"attributes": design()}
        pat.selected_fabric_name = "Cotton Poplin"
        pat.selected_fabric_id = "cotton-poplin"
        pat.garment_type = "blouse"
        pat.yardage_metres = 0.0
        return pat

    def test_estimate_blocked_when_validation_failed(self):
        with patch("app.routes.export.PatternResult") as pr:
            pr.objects.return_value.first.return_value = self._pattern(passed=False)
            r = self.app.test_client().post("/api/export/yardage/x", json={}, headers=self.headers)
        self.assertEqual(r.status_code, 422)
        self.assertNotIn("yardage_metres", r.get_json())

    def test_pdf_blocked_when_validation_failed(self):
        with patch("app.routes.export.PatternResult") as pr:
            pr.objects.return_value.first.return_value = self._pattern(passed=False)
            r = self.app.test_client().post("/api/export/pdf/x", headers=self.headers)
        self.assertEqual(r.status_code, 422)

    def test_estimate_for_each_standard_width(self):
        for width in (90, 114, 150):
            pat = self._pattern()
            with patch("app.routes.export.PatternResult") as pr:
                pr.objects.return_value.first.return_value = pat
                r = self.app.test_client().post("/api/export/yardage/x", json={"fabric_width_cm": width},
                                                headers=self.headers)
            body = r.get_json()
            self.assertEqual(r.status_code, 200, body)
            self.assertEqual(body["fabric_width_cm"], width)
            self.assertEqual(body["validation_checks"]["status"], "PASSED")
            self.assertTrue(body["assumptions"])
            self.assertIn("folded", body["mode_comparison"])
            pat.save.assert_called()

    def test_estimate_rejects_bad_width(self):
        with patch("app.routes.export.PatternResult") as pr:
            pr.objects.return_value.first.return_value = self._pattern()
            r = self.app.test_client().post("/api/export/yardage/x", json={"fabric_width_cm": -5}, headers=self.headers)
        self.assertEqual(r.status_code, 422)
        self.assertEqual(r.get_json()["error_code"], "INVALID_FABRIC_WIDTH")

    @unittest.skipIf(pymupdf is None, "SKIPPED: pymupdf not installed")
    def test_pdf_route_writes_a_tiled_pdf_using_stored_layout(self):
        pat = self._pattern(summary={"fabric_width_cm": 150, "cutting_mode": "open"})
        out = tempfile.mkdtemp()
        self.app.config["OUTPUT_FOLDER"] = out
        with patch("app.routes.export.PatternResult") as pr, patch("app.routes.export.PdfExport") as pe:
            pr.objects.return_value.first.return_value = pat
            pe.return_value.id = "e1"
            r = self.app.test_client().post("/api/export/pdf/p1", headers=self.headers)
        body = r.get_json()
        self.assertEqual(r.status_code, 201, body)
        self.assertIn("1:1", body["print_scale"])
        doc = pymupdf.open(os.path.join(out, body["filename"]))
        self.assertEqual(len(doc), body["pages"])
        self.assertIn("150", doc[1].get_text())


if __name__ == "__main__":
    unittest.main()
