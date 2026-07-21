import os
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.lib.styles import getSampleStyleSheet
from datetime import datetime

# ── Colour palette ─────────────────────────────────────────────────────────────
BLUE       = colors.HexColor("#1F4E79")
LBLUE      = colors.HexColor("#2E75B6")
TEAL       = colors.HexColor("#0F6E56")
CORAL      = colors.HexColor("#D85A30")
LIGHT_GRAY = colors.HexColor("#F5F5F5")
MID_GRAY   = colors.HexColor("#CCCCCC")
DARK_GRAY  = colors.HexColor("#444441")
WHITE      = colors.white
BLACK      = colors.black


class PDFGenerator:
    """
    Generates a production-ready PDF drafting guide using ReportLab.

    Pages:
        1. Cover page
        2. Garment information & measurements
        3. Fabric cutting layout (nesting diagram)
        4. Pattern pieces (scaled drawings)
        5. Construction notes
    """

    PAGE_W, PAGE_H = A4
    MARGIN = 2 * cm

    def __init__(self, pattern_data, nesting_data,
                 measurements, features, output_path):
        """
        Args:
            pattern_data  (dict): from ParametricEngine.generate()
            nesting_data  (dict): from NestingAlgorithm.run()
            measurements  (dict): raw body measurements
            features      (dict): detected garment features
            output_path   (str):  where to save the PDF
        """
        self.pattern    = pattern_data
        self.nesting    = nesting_data
        self.meas       = measurements
        self.features   = features
        self.out        = output_path
        self.c          = canvas.Canvas(output_path, pagesize=A4)
        self.c.setTitle("Digital Tailor — Drafting Guide")

    # ── HELPERS ───────────────────────────────────────────────────────────────
    def _header(self, title):
        """Draws page header with title."""
        c = self.c
        c.setFillColor(BLUE)
        c.rect(0, self.PAGE_H - 2.2 * cm,
               self.PAGE_W, 2.2 * cm, fill=1, stroke=0)
        c.setFillColor(WHITE)
        c.setFont("Helvetica-Bold", 14)
        c.drawString(self.MARGIN,
                     self.PAGE_H - 1.5 * cm, title)
        c.setFillColor(DARK_GRAY)
        c.setFont("Helvetica", 8)
        c.drawRightString(
            self.PAGE_W - self.MARGIN,
            self.PAGE_H - 1.5 * cm,
            f"AI Digital Tailor System  |  {datetime.now().strftime('%d %b %Y')}"
        )

    def _footer(self, page_num):
        """Draws page footer."""
        c = self.c
        c.setFillColor(LBLUE)
        c.rect(0, 0, self.PAGE_W, 0.8 * cm, fill=1, stroke=0)
        c.setFillColor(WHITE)
        c.setFont("Helvetica", 8)
        c.drawCentredString(
            self.PAGE_W / 2, 0.25 * cm,
            f"Page {page_num}  —  AI-Assisted Digital Tailor System  "
            f"|  D N M Vitharana  |  Index: 28404"
        )

    def _label(self, x, y, text, size=9, bold=False, color=DARK_GRAY):
        self.c.setFillColor(color)
        font = "Helvetica-Bold" if bold else "Helvetica"
        self.c.setFont(font, size)
        self.c.drawString(x, y, text)

    def _value_row(self, x, y, label, value, label_w=5 * cm):
        """Draws a label: value pair."""
        self._label(x, y, label, bold=True, color=LBLUE)
        self._label(x + label_w, y, str(value), color=DARK_GRAY)

    # ── PAGE 1: COVER ─────────────────────────────────────────────────────────
    def _page_cover(self):
        c  = self.c
        cx = self.PAGE_W / 2

        # Background stripe
        c.setFillColor(BLUE)
        c.rect(0, self.PAGE_H * 0.55,
               self.PAGE_W, self.PAGE_H * 0.45, fill=1, stroke=0)

        # Title block
        c.setFillColor(WHITE)
        c.setFont("Helvetica-Bold", 22)
        c.drawCentredString(cx, self.PAGE_H * 0.78,
                            "AI-Assisted Digital Tailor")
        c.setFont("Helvetica-Bold", 16)
        c.drawCentredString(cx, self.PAGE_H * 0.72,
                            "Production Drafting Guide")

        c.setFont("Helvetica", 10)
        c.setFillColor(colors.HexColor("#C8D8E8"))
        c.drawCentredString(cx, self.PAGE_H * 0.66,
                            "Generated automatically from your design image "
                            "and body measurements")

        # Info card
        card_y = self.PAGE_H * 0.28
        card_h = self.PAGE_H * 0.30
        c.setFillColor(LIGHT_GRAY)
        c.roundRect(self.MARGIN, card_y,
                    self.PAGE_W - 2 * self.MARGIN, card_h,
                    10, fill=1, stroke=0)

        garment = self.pattern.get("garment_type", "blouse").title()
        fabric  = self.pattern.get("fabric_type", "woven").title()
        yards   = self.nesting.get("yardage_metres", 0)
        width   = self.nesting.get("fabric_width_cm", 114)

        rows = [
            ("Garment type",     garment),
            ("Fabric type",      fabric),
            ("Fabric width",     f"{width} cm"),
            ("Fabric required",  f"{yards} metres  "
                                 f"({self.nesting.get('yardage_yards', 0)} yards)"),
            ("Pattern pieces",   f"{len(self.pattern.get('pattern_pieces', []))} pieces  "
                                 f"(cut × 2 each)"),
            ("Utilisation",      f"{self.nesting.get('utilisation_percent', 0)}%  "
                                 f"fabric efficiency"),
        ]

        row_h = card_h / (len(rows) + 1)
        for i, (lbl, val) in enumerate(rows):
            ry = card_y + card_h - (i + 1.3) * row_h
            self._value_row(self.MARGIN + cm, ry, lbl + ":", val)

        # Generated date
        c.setFillColor(DARK_GRAY)
        c.setFont("Helvetica", 8)
        c.drawCentredString(
            cx, card_y - 0.6 * cm,
            f"Generated: {datetime.now().strftime('%d %B %Y  %H:%M')}"
        )

        self._footer(1)
        c.showPage()

    # ── PAGE 2: MEASUREMENTS & FEATURES ───────────────────────────────────────
    def _page_measurements(self):
        c = self.c
        self._header("Garment Information & Measurements")
        y = self.PAGE_H - 3.5 * cm

        # Body measurements section
        c.setFillColor(LBLUE)
        c.roundRect(self.MARGIN, y - 0.1 * cm,
                    self.PAGE_W - 2 * self.MARGIN, 0.7 * cm,
                    4, fill=1, stroke=0)
        c.setFillColor(WHITE)
        c.setFont("Helvetica-Bold", 11)
        c.drawString(self.MARGIN + 0.3 * cm, y + 0.1 * cm,
                     "Body Measurements")
        y -= 1.0 * cm

        eased = self.pattern.get("measurements_used", {}).get("eased", {})
        raw   = self.meas

        headers = ["Measurement", "Your body (cm)",
                   "With ease (cm)", "Difference"]
        col_x   = [self.MARGIN, self.MARGIN + 5*cm,
                   self.MARGIN + 10*cm, self.MARGIN + 15*cm]

        # Table header
        c.setFillColor(LIGHT_GRAY)
        c.rect(self.MARGIN, y - 0.2*cm,
               self.PAGE_W - 2*self.MARGIN, 0.6*cm,
               fill=1, stroke=0)
        for i, h in enumerate(headers):
            self._label(col_x[i] + 0.1*cm, y + 0.1*cm,
                        h, bold=True, color=BLUE, size=9)
        y -= 0.7 * cm

        meas_rows = [
            ("Bust",   raw.get("bust_cm"),   eased.get("bust_cm")),
            ("Waist",  raw.get("waist_cm"),  eased.get("waist_cm")),
            ("Hip",    raw.get("hip_cm"),    eased.get("hip_cm")),
            ("Height", raw.get("height_cm"), eased.get("height_cm")),
        ]

        for i, (name, body, ease) in enumerate(meas_rows):
            bg = LIGHT_GRAY if i % 2 == 0 else WHITE
            c.setFillColor(bg)
            c.rect(self.MARGIN, y - 0.2*cm,
                   self.PAGE_W - 2*self.MARGIN, 0.55*cm,
                   fill=1, stroke=0)
            diff = round(ease - body, 1) if ease and body else 0
            diff_str = f"+{diff}" if diff >= 0 else str(diff)
            row_vals = [name, f"{body}", f"{ease}", diff_str]
            for j, val in enumerate(row_vals):
                color = TEAL if j == 3 and diff > 0 else (
                    CORAL if j == 3 and diff < 0 else DARK_GRAY)
                self._label(col_x[j] + 0.1*cm, y + 0.05*cm,
                            str(val), color=color, size=9)
            y -= 0.6 * cm

        y -= 0.8 * cm

        # Detected features section
        c.setFillColor(TEAL)
        c.roundRect(self.MARGIN, y - 0.1*cm,
                    self.PAGE_W - 2*self.MARGIN, 0.7*cm,
                    4, fill=1, stroke=0)
        c.setFillColor(WHITE)
        c.setFont("Helvetica-Bold", 11)
        c.drawString(self.MARGIN + 0.3*cm, y + 0.1*cm,
                     "Detected Garment Features (YOLOv8)")
        y -= 1.0 * cm

        feature_rows = [
            ("Garment type",  self.features.get("garment_type", "—").title()),
            ("Neckline",      self.features.get("neckline",     "—").title()),
            ("Sleeves",       self.features.get("sleeves",      "—").title()),
            ("Darts",         self.features.get("darts",        "—").title()),
            ("Seams",         self.features.get("seams",        "—").title()),
        ]

        for i, (lbl, val) in enumerate(feature_rows):
            bg = LIGHT_GRAY if i % 2 == 0 else WHITE
            c.setFillColor(bg)
            c.rect(self.MARGIN, y - 0.2*cm,
                   self.PAGE_W - 2*self.MARGIN, 0.55*cm,
                   fill=1, stroke=0)
            self._label(self.MARGIN + 0.2*cm, y + 0.05*cm,
                        lbl, bold=True, color=BLUE, size=9)
            self._label(self.MARGIN + 7*cm, y + 0.05*cm,
                        val, color=DARK_GRAY, size=9)
            y -= 0.6 * cm

        self._footer(2)
        c.showPage()

    # ── PAGE 3: FABRIC CUTTING LAYOUT ─────────────────────────────────────────
    def _page_nesting(self):
        c = self.c
        self._header("Fabric Cutting Layout")

        nesting = self.nesting
        fw      = nesting.get("fabric_width_cm",  114)
        fl      = nesting.get("fabric_length_cm", 200)

        # Summary strip
        y = self.PAGE_H - 3.2 * cm
        summary = [
            ("Fabric width",    f"{fw} cm"),
            ("Fabric length",   f"{fl} cm"),
            ("Fabric required", f"{nesting.get('yardage_metres')} m"),
            ("Efficiency",      f"{nesting.get('utilisation_percent')}%"),
        ]
        col_gap = (self.PAGE_W - 2 * self.MARGIN) / len(summary)
        for i, (lbl, val) in enumerate(summary):
            bx = self.MARGIN + i * col_gap
            c.setFillColor(LBLUE)
            c.roundRect(bx, y, col_gap - 0.3*cm, 1.5*cm,
                        6, fill=1, stroke=0)
            c.setFillColor(WHITE)
            c.setFont("Helvetica-Bold", 14)
            c.drawCentredString(bx + (col_gap - 0.3*cm) / 2,
                                y + 0.6*cm, val)
            c.setFont("Helvetica", 7)
            c.drawCentredString(bx + (col_gap - 0.3*cm) / 2,
                                y + 0.2*cm, lbl)

        # Nesting diagram
        y -= 1.0 * cm
        diagram_h = self.PAGE_H * 0.50
        diagram_w = self.PAGE_W - 2 * self.MARGIN
        diagram_y = y - diagram_h

        # Fabric rectangle background
        c.setFillColor(colors.HexColor("#EEF4FB"))
        c.setStrokeColor(BLUE)
        c.setLineWidth(1.5)
        c.rect(self.MARGIN, diagram_y,
               diagram_w, diagram_h, fill=1)

        # Scale factors
        scale_x = diagram_w / fw if fw else 1
        scale_y = diagram_h / fl if fl else 1

        piece_colors = [
            colors.HexColor("#C8D8E8"),
            colors.HexColor("#C8E8D8"),
            colors.HexColor("#E8D8C8"),
            colors.HexColor("#D8C8E8"),
            colors.HexColor("#E8E8C8"),
            colors.HexColor("#E8C8D8"),
        ]

        for i, piece in enumerate(nesting.get("placed_pieces", [])):
            px = self.MARGIN + piece["x"] * scale_x
            py = diagram_y + diagram_h - (
                piece["y"] + piece["height"]) * scale_y
            pw = piece["width"]  * scale_x
            ph = piece["height"] * scale_y

            fill_color = piece_colors[i % len(piece_colors)]
            c.setFillColor(fill_color)
            c.setStrokeColor(DARK_GRAY)
            c.setLineWidth(0.5)
            c.rect(px, py, pw, ph, fill=1)

            if pw > 1.5*cm and ph > 0.5*cm:
                c.setFillColor(BLUE)
                c.setFont("Helvetica", 6)
                short_name = piece["name"].replace(
                    "Bodice", "").replace("(cut ", "#").replace(")", "")
                c.drawCentredString(px + pw / 2,
                                    py + ph / 2,
                                    short_name.strip())

            if piece.get("rotated"):
                c.setFillColor(CORAL)
                c.setFont("Helvetica-Bold", 6)
                c.drawString(px + 0.1*cm, py + 0.1*cm, "R")

        c.setFillColor(DARK_GRAY)
        c.setFont("Helvetica", 7)
        c.drawCentredString(
            self.MARGIN + diagram_w / 2,
            diagram_y - 0.4*cm,
            f"← Fabric width: {fw} cm →"
        )
        c.rotate(90)
        c.drawCentredString(
            diagram_y + diagram_h / 2,
            -(self.MARGIN - 0.3*cm),
            f"← Fabric length: {fl} cm →"
        )
        c.rotate(-90)

        legend_y = diagram_y - 1.2 * cm
        c.setFillColor(DARK_GRAY)
        c.setFont("Helvetica-Bold", 8)
        c.drawString(self.MARGIN, legend_y, "Legend:")
        c.setFillColor(CORAL)
        c.setFont("Helvetica-Bold", 8)
        c.drawString(self.MARGIN + 2*cm, legend_y, "R")
        c.setFillColor(DARK_GRAY)
        c.setFont("Helvetica", 8)
        c.drawString(self.MARGIN + 2.5*cm, legend_y,
                     "= Piece rotated 90°  |  "
                     "All pieces include 1 cm cutting gap")

        self._footer(3)
        c.showPage()

    # ── PAGE 4: PATTERN PIECES ─────────────────────────────────────────────────
    def _page_pattern_pieces(self):
        c       = self.c
        pieces  = self.pattern.get("pattern_pieces", [])
        page_no = 4

        for piece in pieces:
            self._header(f"Pattern Piece — {piece['name']}")
            y = self.PAGE_H - 3.5 * cm

            bbox = piece.get("bounding_box", {})
            pw   = bbox.get("width_cm",  20)
            ph   = bbox.get("height_cm", 40)

            info = [
                ("Width",          f"{pw} cm"),
                ("Height",         f"{ph} cm"),
                ("Seam allowance", f"{piece.get('seam_allowance_cm', 1.5)} cm"),
                ("Cut",            "× 2"),
            ]
            col_w  = (self.PAGE_W - 2 * self.MARGIN) / len(info)
            for i, (lbl, val) in enumerate(info):
                bx = self.MARGIN + i * col_w
                c.setFillColor(LIGHT_GRAY)
                c.roundRect(bx, y - 0.5*cm, col_w - 0.2*cm,
                            1.2*cm, 4, fill=1, stroke=0)
                c.setFillColor(BLUE)
                c.setFont("Helvetica-Bold", 11)
                c.drawCentredString(bx + (col_w - 0.2*cm) / 2,
                                    y + 0.1*cm, val)
                c.setFillColor(DARK_GRAY)
                c.setFont("Helvetica", 7)
                c.drawCentredString(bx + (col_w - 0.2*cm) / 2,
                                    y - 0.3*cm, lbl)
            y -= 1.5 * cm

            avail_w = self.PAGE_W  - 2 * self.MARGIN
            avail_h = self.PAGE_H  * 0.55
            scale   = min(avail_w / pw, avail_h / ph) if pw and ph else 1
            scale   = min(scale, 4.0)

            draw_w = pw * scale
            draw_h = ph * scale
            ox     = self.MARGIN + (avail_w - draw_w) / 2
            oy     = y - draw_h

            c.setStrokeColor(MID_GRAY)
            c.setLineWidth(0.3)
            for gx in range(0, int(pw) + 1):
                lx = ox + gx * scale
                c.line(lx, oy, lx, oy + draw_h)
            for gy in range(0, int(ph) + 1):
                ly = oy + gy * scale
                c.line(ox, ly, ox + draw_w, ly)

            outline = piece.get("outline", [])
            if outline:
                c.setStrokeColor(BLUE)
                c.setLineWidth(1.5)
                path = c.beginPath()
                path.moveTo(ox + outline[0][0] * scale,
                            oy + draw_h - outline[0][1] * scale)
                for pt in outline[1:]:
                    path.lineTo(ox + pt[0] * scale,
                                oy + draw_h - pt[1] * scale)
                path.close()
                c.setFillColor(colors.HexColor("#EEF4FB"))
                c.drawPath(path, fill=1, stroke=1)

            grain = piece.get("grain_line", {})
            if grain:
                gs  = grain["start"]
                ge  = grain["end"]
                gsx = ox + gs[0] * scale
                gsy = oy + draw_h - gs[1] * scale
                gex = ox + ge[0] * scale
                gey = oy + draw_h - ge[1] * scale
                c.setStrokeColor(CORAL)
                c.setLineWidth(1.0)
                c.line(gsx, gsy, gex, gey)
                c.setFillColor(CORAL)
                c.circle(gex, gey, 2, fill=1)
                c.setFont("Helvetica-Bold", 7)
                c.setFillColor(CORAL)
                c.drawCentredString((gsx + gex) / 2 + 0.4*cm,
                                    (gsy + gey) / 2,
                                    "grain")

            c.setFillColor(DARK_GRAY)
            c.setFont("Helvetica", 7)
            c.drawString(ox, oy - 0.4*cm,
                         f"Scale: 1 grid square = 1 cm")

            points = piece.get("points", {})
            c.setFont("Helvetica-Bold", 6)
            c.setFillColor(TEAL)
            for label, (px_pt, py_pt) in list(points.items())[:8]:
                lx = ox + px_pt * scale
                ly = oy + draw_h - py_pt * scale
                c.circle(lx, ly, 1.5, fill=1)
                c.drawString(lx + 2, ly + 2, label)

            self._footer(page_no)
            page_no += 1
            c.showPage()

    # ── PAGE: CONSTRUCTION NOTES ───────────────────────────────────────────────
    def _page_notes(self, page_no):
        c = self.c
        self._header("Construction Notes")
        y = self.PAGE_H - 3.5 * cm

        notes = self.pattern.get("construction_notes", [])

        c.setFillColor(TEAL)
        c.roundRect(self.MARGIN, y - 0.1*cm,
                    self.PAGE_W - 2*self.MARGIN, 0.7*cm,
                    4, fill=1, stroke=0)
        c.setFillColor(WHITE)
        c.setFont("Helvetica-Bold", 11)
        c.drawString(self.MARGIN + 0.3*cm, y + 0.1*cm,
                     "Tailor Construction Instructions")
        y -= 1.2 * cm

        for i, note in enumerate(notes):
            c.setFillColor(LIGHT_GRAY if i % 2 == 0 else WHITE)
            c.rect(self.MARGIN, y - 0.3*cm,
                   self.PAGE_W - 2*self.MARGIN, 0.9*cm,
                   fill=1, stroke=0)
            c.setFillColor(LBLUE)
            c.circle(self.MARGIN + 0.4*cm, y + 0.15*cm,
                     0.25*cm, fill=1)
            c.setFillColor(WHITE)
            c.setFont("Helvetica-Bold", 7)
            c.drawCentredString(
                self.MARGIN + 0.4*cm, y + 0.08*cm, str(i + 1))
            c.setFillColor(DARK_GRAY)
            c.setFont("Helvetica", 9)
            c.drawString(self.MARGIN + 0.9*cm, y + 0.1*cm, note)
            y -= 1.0 * cm

        y -= 0.5 * cm
        c.setFillColor(CORAL)
        c.roundRect(self.MARGIN, y - 0.1*cm,
                    self.PAGE_W - 2*self.MARGIN, 0.7*cm,
                    4, fill=1, stroke=0)
        c.setFillColor(WHITE)
        c.setFont("Helvetica-Bold", 11)
        c.drawString(self.MARGIN + 0.3*cm, y + 0.1*cm,
                     "General Sewing Tips")
        y -= 1.0 * cm

        tips = [
            "Always press seams open after stitching for a flat finish.",
            "Cut all pieces on a single layer of fabric unless stated.",
            "Transfer all pattern markings (darts, notches) before removing pattern.",
            "Stay-stitch curved edges (neckline, armhole) before joining pieces.",
            "Check fit on a dress form or by basting before final stitching.",
        ]
        for tip in tips:
            c.setFillColor(DARK_GRAY)
            c.setFont("Helvetica", 9)
            c.drawString(self.MARGIN + 0.3*cm, y, f"•  {tip}")
            y -= 0.65 * cm

        self._footer(page_no)
        c.showPage()

    # ── GENERATE FULL PDF ──────────────────────────────────────────────────────
    def generate(self):
        """Generates all pages and saves the PDF."""
        self._page_cover()
        self._page_measurements()
        self._page_nesting()
        self._page_pattern_pieces()
        self._page_notes(
            page_no = 4 + len(self.pattern.get("pattern_pieces", []))
        )
        self.c.save()
        print(f"PDF saved to: {self.out}")
        return self.out
