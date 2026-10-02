"""Printable 1:1 tiled PDF + export routes (fabric estimate, PDF) - vector-level verification with PyMuPDF."""
import copy
import os
import re
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


def _generate(path, part="all", context=None, **kw):
    m, data, nest = _build(**kw)
    gen = pg.PDFGenerator(data, nest, m, {}, path, fabric_name="Cotton Poplin", garment_title="Test pattern",
                          part=part, context=context)
    gen.generate()
    return gen, data, nest


def _page(doc, title):
    """The page whose heading starts with `title` (pages are found by their title, not by position)."""
    hits = [p for p in doc if p.get_text().lstrip().startswith(title)]
    assert hits, f"no page titled '{title}'"
    return hits[0]


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
        self.assertEqual(len(self.doc), self.gen.front_pages + len(self.gen.tiles))
        # overview, cover, measurements, front, back, sleeve, why this size (2), pieces, fabric + printing instructions
        self.assertEqual(self.gen.front_pages, 11)
        self.assertEqual([k for k, _ in self.gen.plan].count("report"), 10)
        for page in self.doc:
            self.assertAlmostEqual(page.rect.width, 595.28, delta=0.5)
            self.assertAlmostEqual(page.rect.height, 841.89, delta=0.5)

    def test_printing_instructions_and_page_numbers(self):
        first = _page(self.doc, "Printing instructions").get_text()
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
        self.assertTrue(self._squares(_page(self.doc, "Printing instructions")), "printing page has no 5 cm calibration square")
        on_tiles = sum(1 for i in range(self.gen.front_pages, len(self.doc)) if self._squares(self.doc[i]))
        self.assertGreaterEqual(on_tiles, 1, "no tile carries the calibration square")

    def test_summary_page_contents(self):
        cover = self.doc[1].get_text()                                   # page 1 is the pattern overview
        meas = _page(self.doc, "Measurements").get_text()
        pieces = _page(self.doc, "Pattern pieces").get_text()
        for word in ("Cotton Poplin", "Round Neck", "Confirmed design", "Regular fit", "Drafting method", "toile"):
            self.assertIn(word, cover)
        for word in ("Bust around", "Waist around", "Shoulder to shoulder", "calculated value", "measured",
                     "Body measurement + ease = garment measurement", "Seam allowance is NOT ease"):
            self.assertIn(word, meas)
        self.assertIn("34.65", meas)                                       # 88 cm also shown in inches
        for word in ("Front Bodice", "Back Bodice", "Seam allowances", "shoulder 1.5", "armhole 1", "Sewing notes"):
            self.assertIn(word, pieces)

    def test_layout_page_and_estimate(self):
        text = _page(self.doc, "Fabric requirement").get_text()
        self.assertIn("NOT to scale", text)
        self.assertIn(str(self.nest["fabric_length_cm"]), text)

    def test_block_overview_pages_show_numbered_dimensions_and_say_not_to_scale(self):
        for title, words in (("FRONT block", ("Neck width", "Front neck depth", "Shoulder", "Armhole depth", "Armhole curve",
                                             "Bust width", "Waist width", "Hip width", "Garment length", "Bust dart",
                                             "CUT 1 ON FOLD", "FOLD - centre front")),
                             ("BACK block", ("Back neck depth", "Armhole curve", "Bust width", "Waist dart",
                                            "CUT 1 ON FOLD", "FOLD - centre back")),
                             ("SLEEVE block", ("Sleeve length", "Sleeve width", "Cap height", "Sleeve end width",
                                              "Front cap", "Back cap", "CUT 2"))):
            text = _page(self.doc, title).get_text()
            self.assertIn("NOT TO SCALE", text, title)
            for word in words:
                self.assertIn(word, text, (title, word))
            self.assertIn("cm (", text)                                    # every value in cm and in inches
        front = next(p for p in self.data["pattern_pieces"] if p["piece_type"] == "front_bodice")
        text = _page(self.doc, "FRONT block").get_text()
        bust = next(d for d in front["dimensions"] if d["id"] == "bust_width")
        self.assertIn(f"{bust['value_cm']:.2f} cm", text)                  # the value on the page is the drafted one
        self.assertIn("your measurement", text)
        self.assertIn("drafting method", text)

    def test_sleeve_page_reports_the_armhole_against_the_sleeve_cap(self):
        text = _page(self.doc, "SLEEVE block").get_text()
        cap = self.data["sleeve_cap"]
        for word in ("Does the sleeve fit the armhole?", "Front armhole curve", "Back armhole curve", "Bodice armhole seam",
                     "Sleeve cap seam", "Difference", "Allowed sleeve-cap ease", f"Status: {cap['status']}",
                     f"{cap['sleeve_cap_seam_cm']:.2f} cm", f"{cap['bodice_armhole_seam_cm']:.2f} cm"):
            self.assertIn(word, text)

    def test_why_this_size_shows_the_customers_own_numbers(self):
        text = " ".join(p.get_text() for p in self.doc if p.get_text().lstrip().startswith("Why this size?"))
        for word in ("Front width at the bust line", "88", "/ 4", "Armhole depth", "Sleeve cap seam", "Seam allowance: side",
                     "drafting method", "your measurement", "project rule", "seam allowance"):
            self.assertIn(word, text)
        self.assertNotIn("Aldrich", text)

    def test_report_and_cutting_pattern_can_be_made_separately(self):
        report, _, _ = _generate(os.path.join(self.tmp, "r.pdf"), part="report")
        doc = pymupdf.open(os.path.join(self.tmp, "r.pdf"))
        self.assertEqual(len(doc), 10)
        self.assertEqual(report.info["tiles"], 0)
        self.assertIn("Not a cutting template", doc[0].get_text())          # the overview page comes first
        for page in list(doc)[1:]:
            self.assertIn("NOT to scale", page.get_text())
        for page in doc:                                                    # nothing in the report claims to be 1:1
            self.assertIsNone(re.search(r"scale 1:1(?![0-9])", page.get_text()))
        pattern, _, _ = _generate(os.path.join(self.tmp, "c.pdf"), part="pattern")
        doc = pymupdf.open(os.path.join(self.tmp, "c.pdf"))
        self.assertEqual(len(doc), 1 + len(pattern.tiles))
        self.assertTrue(doc[0].get_text().lstrip().startswith("Printing instructions"))
        for page in doc:
            self.assertIn("scale 1:1", page.get_text())
        with self.assertRaises(ValueError):
            pg.PDFGenerator(self.data, self.nest, {}, {}, os.path.join(self.tmp, "bad.pdf"), part="everything")

    def test_overview_is_one_page_with_the_real_blocks_at_a_stated_reduced_scale(self):
        gen, data, _ = _generate(os.path.join(self.tmp, "o.pdf"), part="overview")
        doc = pymupdf.open(os.path.join(self.tmp, "o.pdf"))
        self.assertEqual((len(doc), gen.info["tiles"]), (1, 0))             # no real-size pages at all
        text = doc[0].get_text()
        n = gen.info["overview_scale"]
        self.assertIn(n, pg.OVERVIEW_SCALES)
        self.assertGreater(n, 1)                                            # reduced, never real size
        for word in ("Measurement-based pattern overview", "FRONT", "BACK", "SLEEVE", f"REDUCED SCALE 1:{n}",
                     "Not a cutting template", "MEASUREMENTS ENTERED", "ALL MEASUREMENTS IN CM", "Sleeve cap against armhole"):
            self.assertIn(word, text)
        self.assertNotIn("Actual size", text)
        self.assertEqual(self._squares(doc[0]), [])                         # no calibration square: nothing here is 1:1
        dims = {p["piece_type"]: {d["id"]: d["value_cm"] for d in p["dimensions"]} for p in data["pattern_pieces"]
                if p.get("dimensions")}
        for label, value in (("Bust width", dims["front_bodice"]["bust_width"]), ("Bust width", dims["back_bodice"]["bust_width"]),
                             ("Garment length", dims["back_bodice"]["garment_length"]), ("Sleeve width", dims["sleeve"]["sleeve_width"]),
                             ("Front neck depth", dims["front_bodice"]["neck_depth"])):
            self.assertIn(f"{label} {value:.1f} cm", text)                  # this pattern's own numbers, not sample values
        self.assertNotEqual(dims["front_bodice"]["bust_width"], dims["back_bodice"]["bust_width"])
        # the real block, really drawn at 1:n - the front's sewing line is as tall as the piece divided by n
        front = next(p for p in data["pattern_pieces"] if p["piece_type"] == "front_bodice")
        ys = [q[1] for q in front["outline"]]
        want = (max(ys) - min(ys)) / n * pg.CM
        heights = [d["rect"].height for d in doc[0].get_drawings() if d.get("fill") and d["rect"].height > 100]
        self.assertTrue(any(abs(h - want) < 1.0 for h in heights), (want, heights))

    def test_overview_in_inches_and_for_a_sleeveless_design(self):
        _generate(os.path.join(self.tmp, "oi.pdf"), part="overview", context={"unit": "in"})
        text = pymupdf.open(os.path.join(self.tmp, "oi.pdf"))[0].get_text()
        self.assertIn("ALL MEASUREMENTS IN INCHES", text)
        back = next(p for p in self.data["pattern_pieces"] if p["piece_type"] == "back_bodice")
        bust = next(d for d in back["dimensions"] if d["id"] == "bust_width")["value_cm"]
        self.assertIn(f"Bust width {bust / 2.54:.2f} in", text)
        path = os.path.join(self.tmp, "os.pdf")
        _generate(path, part="overview", sleeve="sleeveless")
        text = pymupdf.open(path)[0].get_text()
        self.assertIn("Sleeveless design: no sleeve piece.", text)
        self.assertNotIn("SLEEVE", [ln.strip() for ln in text.splitlines()])    # no sleeve panel is invented
        self.assertNotIn("Sleeve length", text)                             # nor sleeve measurements the design does not use

    def test_lengths_follow_the_selected_unit(self):
        _generate(os.path.join(self.tmp, "in.pdf"), part="report", context={"unit": "in"})
        text = _page(pymupdf.open(os.path.join(self.tmp, "in.pdf")), "BACK block").get_text()
        back = next(p for p in self.data["pattern_pieces"] if p["piece_type"] == "back_bodice")
        bust = next(d for d in back["dimensions"] if d["id"] == "bust_width")["value_cm"]
        self.assertIn(f"{bust / 2.54:.2f} in ({bust:.2f} cm)", text)        # inches first
        cm_text = _page(self.doc, "BACK block").get_text()
        self.assertIn(f"{bust:.2f} cm ({bust / 2.54:.2f} in)", cm_text)     # cm first

    def test_tile_pages_have_labels_marks_and_pieces(self):
        for i in range(self.gen.front_pages, len(self.doc)):
            text = self.doc[i].get_text()
            self.assertRegex(text, r"[A-Z]\d")
            self.assertIn("Actual size", text)
        all_text = " ".join(self.doc[i].get_text() for i in range(self.gen.front_pages, len(self.doc)))
        for word in ("FRONT BODICE", "BACK BODICE", "SLEEVE", "PLACE ON FOLD", "CUT 2", "SA 1.5 cm", "incl. SA",
                     "BP", "CROWN", "GRAIN"):
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
                   dict(garment="blouse", neck="square-neck", sleeve="sleeveless"),
                   dict(garment="blouse", neck="round-neck", sleeve="long-sleeve")):
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
        for width in (91.44, 114.3, 152.4):
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
        pat = self._pattern(summary={"fabric_width_cm": 152.4, "cutting_mode": "open"})
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
        self.assertIn('60 in / 152.4 cm *', _page(doc, "Fabric requirement").get_text())

    def test_pdf_prints_the_stored_pieces_and_never_redrafts(self):
        """The PDF must show the validated, nested stored pieces; the engine is not run again."""
        stored = copy.deepcopy(self.data["pattern_pieces"])
        stored[0]["name"] = "Front Bodice (as saved)"
        pat = self._pattern()
        pat.pattern_coordinates = stored
        self.app.config["OUTPUT_FOLDER"] = tempfile.mkdtemp()
        with patch("app.routes.export.PatternResult") as pr, patch("app.routes.export.PdfExport") as pe, \
                patch("app.routes.export.PDFGenerator") as gen, \
                patch("app.logic.parametric_engine.ParametricEngine.generate", side_effect=AssertionError("re-drafted")):
            pr.objects.return_value.first.return_value = pat
            pe.return_value.id = "e1"
            gen.return_value.info = {"pages": 9}
            r = self.app.test_client().post("/api/export/pdf/p1", headers=self.headers)
        self.assertEqual(r.status_code, 201, r.get_json())
        kw = gen.call_args.kwargs
        self.assertIs(kw["pattern_data"]["pattern_pieces"], stored)
        ctx = kw["context"]
        self.assertEqual([row["fabric_width_in"] for row in ctx["width_estimates"]], [36, 45, 60])
        self.assertEqual(set(ctx["width_layouts"]), {91.44, 114.3, 152.4})

    @unittest.skipIf(pymupdf is None, "SKIPPED: pymupdf not installed")
    def test_complete_customer_pdf_content(self):
        from PIL import Image
        upload = tempfile.mkdtemp()
        Image.new("RGB", (120, 160), (40, 120, 80)).save(os.path.join(upload, "design.png"))
        self.app.config["UPLOAD_FOLDER"] = upload
        out = tempfile.mkdtemp()
        self.app.config["OUTPUT_FOLDER"] = out
        pat = self._pattern(summary={"fabric_width_cm": 114.3, "cutting_mode": "folded"})
        pat.id = "65f0c0ffee00000000000001"
        pat.project_name = "Wedding blouse"
        pat.session_id.measurement_id.client_name = "Amara Silva"
        pat.session_id.measurement_id.email = "amara@example.com"
        pat.session_id.image_id.file_path = "design.png"
        pat.generated_at = __import__("datetime").datetime(2026, 9, 30, 10, 0)
        pat.width_estimates = []
        pat.drafting_info = {k: self.data[k] for k in ("drafting_block", "design_attributes", "measurements_used", "construction_notes")}
        pat.base_block = self.data["base_block"]
        pat.design_spec = {"attributes": design(), "provenance": {
            "garment_type": {"source": "ml_prediction_confirmed", "predicted_label": "blouse", "predicted_confidence": 0.91},
            "neckline_type": {"source": "user_corrected", "predicted_label": "v-neck", "predicted_confidence": 0.42},
            "sleeve_length": {"source": "manual_selection"}, "sleeve_style": {"source": "manual_selection"}},
            "model": {"model_type": "image classifier", "checkpoint_sha256": "3b69a470ed5d0398" + "0" * 48}}
        pat.measurements_snapshot["original_values"] = {"bust_cm": {"value": 34.65, "unit": "in"}}
        with patch("app.routes.export.PatternResult") as pr, patch("app.routes.export.PdfExport") as pe:
            pr.objects.return_value.first.return_value = pat
            pe.return_value.id = "e1"
            r = self.app.test_client().post("/api/export/pdf/p1", headers=self.headers)
        body = r.get_json()
        self.assertEqual(r.status_code, 201, body)
        doc = pymupdf.open(os.path.join(out, body["filename"]))
        cover = doc[1].get_text()                                        # page 1 is the pattern overview
        for word in ("Amara Silva", "amara@example.com", "Wedding blouse", "65f0c0ffee00000000000001", "2026-09-30",
                     "Corrected by user", "V Neck (42.0 %)", "AI prediction confirmed", "Blouse (91.0 %)", "Cotton Poplin",
                     "Fabric requirement"):
            self.assertIn(word, cover)
        self.assertTrue(doc[0].get_images(), "the customer's design image is not embedded")
        self.assertIn("34.65 in", _page(doc, "Measurements").get_text())   # value as entered
        overview = doc[0].get_text()
        self.assertIn("(typed 34.65 in)", overview)                        # typed in the other unit: shown next to the cm value
        self.assertEqual(overview.count("(typed"), 1)                      # values typed in cm are not repeated
        fabric = _page(doc, "Fabric requirement").get_text()
        for word in ("36 in / 91.44 cm", "45 in / 114.3 cm *", "60 in / 152.4 cm", "the width chosen", "Need to buy",
                     "Pattern area", "Fabric bought", "Waste", "Fabric use", " yd", " m2", " yd2",
                     "not automatically the best"):
            self.assertIn(word, fabric)
        for page in doc:
            t = page.get_text()
            self.assertIn("Pattern 65f0c0ffee00000000000001", t)
            self.assertIn("Customer Amara Silva", t)
            kinds = ("Units cm - scale 1:1" in t, "drawings NOT to scale" in t, "Overview at reduced scale 1:" in t)
            self.assertEqual(sum(kinds), 1, kinds)                           # every page says exactly which it is

    @unittest.skipIf(pymupdf is None, "SKIPPED: pymupdf not installed")
    def test_report_only_and_pattern_only_downloads(self):
        out = tempfile.mkdtemp()
        self.app.config["OUTPUT_FOLDER"] = out
        pages = {}
        for part in ("overview", "report", "pattern", "all"):
            with patch("app.routes.export.PatternResult") as pr, patch("app.routes.export.PdfExport") as pe:
                pr.objects.return_value.first.return_value = self._pattern()
                pe.return_value.id = "e1"
                r = self.app.test_client().post("/api/export/pdf/p1", json={"part": part, "unit": "in"}, headers=self.headers)
            body = r.get_json()
            self.assertEqual(r.status_code, 201, body)
            self.assertEqual((body["part"], body["unit"]), (part, "in"))
            pages[part] = body["pages"]
            self.assertEqual("NOT to scale" in body["print_scale"], part in ("report", "overview"))
            self.assertEqual(body["overview_scale"] is None, part == "pattern")
        self.assertEqual(pages["overview"], 1)                               # one page, reduced scale
        self.assertEqual(pages["report"] + pages["pattern"], pages["all"])
        for bad in ({"part": "everything"}, {"unit": "mm"}):
            with patch("app.routes.export.PatternResult") as pr:
                pr.objects.return_value.first.return_value = self._pattern()
                r = self.app.test_client().post("/api/export/pdf/p1", json=bad, headers=self.headers)
            self.assertEqual(r.status_code, 400)

    def test_pdf_failure_does_not_leak_internal_details(self):
        pat = self._pattern()
        self.app.config["OUTPUT_FOLDER"] = tempfile.mkdtemp()
        with patch("app.routes.export.PatternResult") as pr, \
                patch("app.routes.export.PDFGenerator", side_effect=OSError(r"C:\secret\outputs\x.pdf locked")):
            pr.objects.return_value.first.return_value = pat
            with self.assertLogs(self.app.logger, level="ERROR"):
                r = self.app.test_client().post("/api/export/pdf/p1", headers=self.headers)
        body = r.get_json()
        self.assertEqual(r.status_code, 500)
        self.assertEqual(body["error_code"], "PDF_GENERATION_FAILED")
        self.assertNotIn("secret", str(body))


if __name__ == "__main__":
    unittest.main()
