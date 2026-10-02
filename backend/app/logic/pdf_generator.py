"""
Sewing-pattern PDF (ReportLab). Everything is drawn from STORED data: the validated pieces, the measurement
snapshot, the saved calculation list and the saved estimates - the pattern is never re-drafted here.

PART A - MEASUREMENT REPORT (overview drawings are NOT TO SCALE and say so)
    Project summary     customer, garment, fabric, fit, unit, the design photo, confirmed features, drafting method
    Measurements        every measurement as entered, in cm and in inches, and the calculated values
    Front / Back / Sleeve block
                        the block with every important dimension drawn on it as a numbered line, and the list of
                        those dimensions; the sleeve page also holds the armhole / sleeve-cap check
    Why this size?      every pattern dimension with the calculation that produced it and where the rule comes from
    Pieces and notes    piece list, cut quantities, seam allowances, sewing notes
    Fabric              36", 45" and 60": length to buy (m / yd), areas (m2 / yd2), waste, use; the layout of each
PART B - CUTTING PATTERN (true 1:1 scale)
    Printing instructions with a 5 cm calibration square
    The pattern tiled onto A4 sheets with an overlap, crop marks, tile labels and page numbers

PATTERN OVERVIEW (first page of part A, or alone)
    The real front, back and sleeve side by side at one reduced scale 1:n, the important dimensions written
    on them, the measurements entered. For reading, not a cutting template.

`part` = "all" (default), "overview" (that one page), "report" (part A only) or "pattern" (part B only).
Footer on every page: page x of N, pattern ID, customer, scale note, creation timestamp.

Every piece shows: cutting line (solid), seam line (dashed), grainline, fold line, darts, notches, name, cut
quantity, "cut on fold" and the seam allowance. All coordinates are centimetres and are converted with
1 cm = 72/2.54 pt, so a printer set to "Actual size" reproduces real dimensions.
"""

import math
from datetime import datetime, timezone

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from app.logic import measurement_schema as ms
from app.logic import units

CM = 72.0 / 2.54
PAGE_W, PAGE_H = A4

MARGIN_CM = 1.0                                   # crop-mark zone around the printable area
TILE_W_CM = PAGE_W / CM - 2 * MARGIN_CM           # ~ 19.0
TILE_H_CM = PAGE_H / CM - 2 * MARGIN_CM           # ~ 27.7
OVERLAP_CM = 1.0
STEP_X = TILE_W_CM - OVERLAP_CM
STEP_Y = TILE_H_CM - OVERLAP_CM
CALIBRATION_CM = 5.0
SHEET_MAX_W_CM = 3 * STEP_X - 1.0                 # widest pattern sheet: three tiles across
PIECE_GAP_CM = 2.0

BLUE = colors.HexColor("#1F4E79")
GRAY = colors.HexColor("#666666")
LIGHT = colors.HexColor("#F2F2F2")
RED = colors.HexColor("#B71C1C")

INSTRUCTIONS = [
    "Print this document at 100 % scale - choose 'Actual size' / 'Scale: 100' in the print dialog.",
    "Do NOT use 'Fit to page' or 'Shrink oversized pages'; that makes the pattern the wrong size.",
    f"Measure the calibration square on this page: it must be exactly {CALIBRATION_CM:g} cm x {CALIBRATION_CM:g} cm.",
    "Pattern pages are tiled (A1, A2, ...). Cut along the inner crop marks and join tiles by matching the "
    f"marked {OVERLAP_CM:g} cm overlap and the tile labels.",
    "Solid line = CUTTING line (seam allowance included). Dashed line = SEWING line. Triangles = notches.",
    "Cut-on-fold pieces are printed as half pieces: place the FOLD edge on the fold of the cloth.",
    "Keep the grainline arrow parallel to the selvedge of the fabric.",
]


KEY_POINTS = {"NECK_POINT": "NP", "SHOULDER_POINT": "SP", "UNDERARM": "UA", "WAIST_SIDE": "W",
              "BUST_POINT": "BP", "CROWN": "CROWN", "UNDERARM_LEFT": "UA", "UNDERARM_RIGHT": "UA"}
SOURCE_WORDS = {"measurement": "your measurement", "method": "drafting method", "figure": "drafting method (figure)",
                "design": "design value", "ease": "ease", "seam": "seam allowance", "extension": "project rule"}
DIM_COLOUR = colors.HexColor("#B45309")
PARTS = ("all", "overview", "report", "pattern")
GREEN = colors.HexColor("#4F6F5B")
PALE = colors.HexColor("#EAF0EB")
OVERVIEW_FILL = colors.HexColor("#F7FAF7")
# pattern overview page: the blocks side by side at one reduced scale 1:n
OVERVIEW_SCALES = (4, 5, 6, 7, 8, 10, 12, 15, 20)
OVERVIEW_LEFT_CM, OVERVIEW_WIDTH_CM, OVERVIEW_HEIGHT_CM = 1.0, 19.0, 11.0
OVERVIEW_GUTTER_LEFT_CM = 0.85                    # room for the dimension lines left of a block
OVERVIEW_GUTTER_CM = 1.9                          # left + right room per block


def _fmt(v, nd=1):
    return "-" if v is None else f"{v:.{nd}f}"


# ── sheet layout (where each piece sits on the virtual pattern sheet, in cm) ──────────────────
CALIBRATION_NAME = "__calibration__"
SHEET_WIDTH_CANDIDATES_CM = (36.0, 40.0, 46.0, 57.0, 60.0, 72.0, 75.0)


def _count_tiles(placements, sheet_w, sheet_h):
    cols, rows = tile_grid(sheet_w, sheet_h)
    n = 0
    for ry in range(rows):
        for cx in range(cols):
            x0, y0 = cx * STEP_X, ry * STEP_Y
            x1, y1 = x0 + TILE_W_CM, y0 + TILE_H_CM
            if any(pl["x"] < x1 and pl["x"] + pl["w"] > x0 and pl["y"] < y1 and pl["y"] + pl["h"] > y0 for pl in placements):
                n += 1
    return n


def layout_sheet(pieces):
    """
    Arrange one copy of every piece (cut-on-fold pieces stay half pieces) plus a calibration square on
    a virtual sheet using the polygon nesting in 'sheet' mode. The sheet width with the fewest A4 pages
    wins. Returns (placements, sheet_w, sheet_h); a placement has the piece, its offset (dx, dy) and box.
    """
    from app.logic.nesting_algorithm import NestingAlgorithm
    square = {"name": CALIBRATION_NAME, "piece_type": "calibration", "cut_count": 1, "cut_on_fold": False,
              "cutting_line": [(0, 0), (CALIBRATION_CM, 0), (CALIBRATION_CM, CALIBRATION_CM), (0, CALIBRATION_CM)]}
    by_name = {p["name"]: p for p in pieces}
    best = None
    for width in SHEET_WIDTH_CANDIDATES_CM:
        try:
            res = NestingAlgorithm(pieces + [square], fabric_width_cm=width, cutting_mode="sheet").run()
        except Exception:
            continue
        placements = []
        for pp in res["placed_pieces"]:
            piece = by_name.get(pp["name"], square)
            box = piece.get("cut_bounding_box") or {"min_x": 0.0, "min_y": 0.0}
            placements.append({"piece": piece, "dx": pp["x"] - box["min_x"], "dy": pp["y"] - box["min_y"],
                               "x": pp["x"], "y": pp["y"], "w": pp["width"], "h": pp["height"],
                               "calibration": piece is square})
        sheet_w = max(pl["x"] + pl["w"] for pl in placements)
        sheet_h = max(pl["y"] + pl["h"] for pl in placements)
        key = (_count_tiles(placements, sheet_w, sheet_h), width)
        if best is None or key < best[0]:
            best = (key, placements, sheet_w, sheet_h)
    if best is None:
        raise ValueError("The pattern pieces could not be arranged on a printable sheet.")
    return best[1], best[2], best[3]


def tile_grid(sheet_w, sheet_h):
    cols = max(1, int(math.ceil((sheet_w - OVERLAP_CM) / STEP_X)))
    rows = max(1, int(math.ceil((sheet_h - OVERLAP_CM) / STEP_Y)))
    return cols, rows


def tile_label(col, row):
    return f"{chr(ord('A') + row)}{col + 1}"


class PDFGenerator:
    def __init__(self, pattern_data, nesting_data, measurements, features, output_path,
                 design_spec=None, fabric_name=None, garment_title=None, context=None, part="all"):
        if part not in PARTS:
            raise ValueError(f"part must be one of {PARTS}")
        self.part = part
        self.pattern = pattern_data
        self.nesting = nesting_data or {}
        self.meas = measurements or {}
        self.features = features or {}
        self.design_spec = design_spec or {}
        # customer / project / provenance / width comparison (all optional; missing values print as "-")
        self.ctx = dict(context or {})
        self.ctx.setdefault("design_spec", self.design_spec)
        self.created_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        self.fabric_name = fabric_name
        self.out = output_path
        self.pieces = pattern_data["pattern_pieces"]
        self.title = garment_title or "Custom sewing pattern"
        self.c = canvas.Canvas(output_path, pagesize=A4)
        self.c.setTitle(self.title)
        self.c.setAuthor("AI-Assisted Digital Tailor System")
        self.c.setSubject("Printable 1:1 sewing pattern - tiled A4 - print at Actual Size (100%)"
                          if part in ("all", "pattern") else "Pattern overview at a reduced scale - not a cutting template"
                          if part == "overview" else "Measurement report - overview drawings are not to scale")
        self.c.setKeywords("sewing pattern, 1:1, A4 tiled, actual size")
        self.placements, self.sheet_w, self.sheet_h = layout_sheet(self.pieces)
        self.cols, self.rows = tile_grid(self.sheet_w, self.sheet_h)
        self.tiles = [(cx, ry) for ry in range(self.rows) for cx in range(self.cols) if self._tile_has_content(cx, ry)]
        self.unit = self.ctx.get("unit") if self.ctx.get("unit") in ("cm", "in") else "cm"
        self.trace = {r.get("id"): r for r in (self.pattern.get("why_this_size") or [])}
        self.plan = self._plan()
        self.front_pages = sum(1 for kind, _ in self.plan if kind != "tile")
        self.total_pages = len(self.plan)
        self.page_no = 0
        self.info = {}

    # ── what goes into this document ────────────────────────────────────────
    def _block_pieces(self):
        order = {"front_bodice": 0, "back_bodice": 1, "sleeve": 2}
        return sorted((p for p in self.pieces if p.get("piece_type") in order), key=lambda p: order[p["piece_type"]])

    def _why_pages(self):
        rows = self.pattern.get("why_this_size") or []
        per_page = 30
        return [rows[i:i + per_page] for i in range(0, len(rows), per_page)]

    def _plan(self):
        """[(kind, callable)] in print order; kind 'tile' marks the 1:1 pages."""
        plan = []
        if self.part in ("all", "report", "overview") and self._block_pieces():
            plan.append(("report", self._page_overview))
        if self.part in ("all", "report"):
            plan.append(("report", self._page_cover))
            plan.append(("report", self._page_measurements))
            for piece in self._block_pieces():
                plan.append(("report", lambda piece=piece: self._page_block(piece)))
            for k, rows in enumerate(self._why_pages()):
                plan.append(("report", lambda rows=rows, k=k: self._page_why(rows, k)))
            plan.append(("report", self._page_pieces))
            plan.append(("report", self._page_layout))
        if self.part in ("all", "pattern"):
            plan.append(("print", self._page_print))
            for col, row in self.tiles:
                plan.append(("tile", lambda col=col, row=row: self._page_tile(col, row)))
        return plan

    def _len(self, cm, digits=1):
        return units.both_lengths(cm, self.unit, digits)

    # ── helpers ─────────────────────────────────────────────────────────────
    def _footer(self):
        c = self.c
        self.page_no += 1
        c.setFont("Helvetica", 7.5)
        c.setFillColor(GRAY)
        scale = (getattr(self, "_scale_note", None) or
                 ("Units cm - scale 1:1 - print at 100% Actual size" if getattr(self, "_on_pattern_page", False)
                  else "Measurement report - drawings NOT to scale"))
        parts = [f"Page {self.page_no} of {self.total_pages}", f"Pattern {self.ctx.get('pattern_id') or '-'}",
                 f"Customer {self.ctx.get('customer_name') or '-'}", scale, f"Created {self.created_at}"]
        c.drawCentredString(PAGE_W / 2, 0.45 * CM, "   |   ".join(parts))

    def _title(self, text, sub=None):
        c = self.c
        c.setFillColor(BLUE)
        c.setFont("Helvetica-Bold", 17)
        c.drawString(2 * CM, PAGE_H - 2.2 * CM, text)
        if sub:
            c.setFont("Helvetica", 9)
            c.setFillColor(GRAY)
            c.drawString(2 * CM, PAGE_H - 2.8 * CM, sub)
        c.setStrokeColor(BLUE)
        c.setLineWidth(1)
        c.line(2 * CM, PAGE_H - 3.1 * CM, PAGE_W - 2 * CM, PAGE_H - 3.1 * CM)

    def _text(self, x, y, s, size=9, bold=False, color=colors.black):
        self.c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
        self.c.setFillColor(color)
        self.c.drawString(x, y, s)

    def _calibration_square(self, x, y):
        """x, y = lower-left corner in points. Exactly CALIBRATION_CM square."""
        c = self.c
        c.setStrokeColor(colors.black)
        c.setLineWidth(0.8)
        c.rect(x, y, CALIBRATION_CM * CM, CALIBRATION_CM * CM, fill=0)
        c.setLineWidth(0.3)
        for i in range(1, int(CALIBRATION_CM)):
            c.line(x + i * CM, y, x + i * CM, y + 0.25 * CM)
            c.line(x, y + i * CM, x + 0.25 * CM, y + i * CM)
        c.setFont("Helvetica-Bold", 7)
        c.setFillColor(colors.black)
        c.drawCentredString(x + CALIBRATION_CM * CM / 2, y + CALIBRATION_CM * CM / 2 + 3,
                            f"{CALIBRATION_CM:g} cm x {CALIBRATION_CM:g} cm")
        c.setFont("Helvetica", 6.5)
        c.drawCentredString(x + CALIBRATION_CM * CM / 2, y + CALIBRATION_CM * CM / 2 - 7, "must measure exactly")

    # ── shared page furniture ───────────────────────────────────────────────
    def _wrap(self, text, width_pt, size=8.5, font="Helvetica"):
        words, cur, lines = str(text).split(), "", []
        for w in words:
            if self.c.stringWidth((cur + " " + w).strip(), font, size) > width_pt:
                lines.append(cur)
                cur = w
            else:
                cur = (cur + " " + w).strip()
        if cur:
            lines.append(cur)
        return lines or [""]

    def _para(self, x, y, text, width_pt, size=8.5, bold=False, color=colors.black, leading=0.42):
        for ln in self._wrap(text, width_pt, size, "Helvetica-Bold" if bold else "Helvetica"):
            self._text(x, y, ln, size, bold, color)
            y -= leading * CM
        return y

    def _kv(self, x, y, label, value, lw=4.2, width_cm=6.2):
        self._text(x, y, f"{label}:", 8.5, True)
        lines = self._wrap(str(value if value not in (None, "") else "-"), width_cm * CM)
        for k, ln in enumerate(lines):
            self._text(x + lw * CM, y - k * 0.4 * CM, ln, 8.5)
        return y - (0.5 + 0.4 * (len(lines) - 1)) * CM

    # ── page 1: project summary ─────────────────────────────────────────────
    def _page_cover(self):
        c, ctx = self.c, self.ctx
        attrs = self.pattern.get("design_attributes", {})
        self._title(self.title, {"all": "Measurement report and printable 1:1 sewing pattern (tiled A4)",
                                 "report": "Measurement report (the 1:1 cutting pattern is a separate download)",
                                 "pattern": "Printable 1:1 sewing pattern (tiled A4)"}[self.part])
        y = PAGE_H - 4.0 * CM
        y = self._kv(2 * CM, y, "Customer", ctx.get("customer_name"))
        y = self._kv(2 * CM, y, "Contact / reference", ctx.get("customer_contact"))
        y = self._kv(2 * CM, y, "Design / project", ctx.get("project_name"))
        y = self._kv(2 * CM, y, "Pattern ID", ctx.get("pattern_id"))
        y = self._kv(2 * CM, y, "Pattern generated", ctx.get("generated_at"))
        y = self._kv(2 * CM, y, "Fabric", self.fabric_name)
        ease = (self.pattern.get("measurements_used") or {}).get("ease_profile") or {}
        fit = ease.get("fit_label") or ease.get("fit_preference") or self.meas.get("fit_preference")
        y = self._kv(2 * CM, y, "Fit / ease", f"{fit or '-'}: bust +{_fmt(ease.get('bust_cm'))}, waist "
                                                 f"+{_fmt(ease.get('waist_cm'))}, hip +{_fmt(ease.get('hip_cm'))} cm" if ease else fit)
        y = self._kv(2 * CM, y, "Drafting block", (self.pattern.get("drafting_block") or {}).get("block_label"))
        y = self._kv(2 * CM, y, "Shown in", "inches (and cm)" if self.unit == "in" else "cm (and inches)")
        method = self.pattern.get("drafting_method") or {}
        if method.get("name"):
            y = self._kv(2 * CM, y, "Drafting method", method["name"])

        # uploaded design image (right column)
        img_path = ctx.get("image_path")
        box_x, box_y, box_w, box_h = 12.6 * CM, PAGE_H - 10.2 * CM, 6.4 * CM, 6.2 * CM
        c.setStrokeColor(colors.HexColor("#BBBBBB"))
        c.setLineWidth(0.5)
        c.rect(box_x, box_y, box_w, box_h, fill=0)
        drawn = False
        if img_path:
            try:
                from reportlab.lib.utils import ImageReader
                img = ImageReader(img_path)
                iw, ih = img.getSize()
                s = min((box_w - 0.3 * CM) / iw, (box_h - 0.3 * CM) / ih)
                c.drawImage(img, box_x + (box_w - iw * s) / 2, box_y + (box_h - ih * s) / 2, iw * s, ih * s)
                drawn = True
            except Exception:                           # noqa: BLE001 - a missing/corrupt photo must not stop the PDF
                drawn = False
        if not drawn:
            self._text(box_x + 0.4 * CM, box_y + box_h / 2, "No design photo (design chosen manually)"
                       if not img_path else "Design photo could not be read", 8, False, GRAY)
        self._text(box_x, box_y - 0.4 * CM, "Customer's garment design image", 7.5, False, GRAY)

        # confirmed design, AI confidence and user corrections
        y = min(y, box_y) - 0.9 * CM
        self._text(2 * CM, y, "Confirmed design", 11, True, BLUE)
        y -= 0.6 * CM
        heads = [("garment_type", "Garment type"), ("neckline_type", "Neckline"),
                 ("sleeve_length", "Sleeve length"), ("sleeve_style", "Sleeve style")]
        cols = [2.0, 6.2, 10.4, 14.2]
        for h, xcm in zip(("Feature", "Confirmed", "AI prediction (confidence)", "Source"), cols):
            self._text(xcm * CM, y, h, 8, True)
        y -= 0.45 * CM
        prov = (ctx.get("design_spec") or {}).get("provenance") or {}
        pretty = lambda v: str(v).replace("-", " ").title() if v else "-"    # noqa: E731
        for key, label in heads:
            p = prov.get(key) or {}
            conf = p.get("predicted_confidence")
            ai = f"{pretty(p.get('predicted_label'))} ({conf * 100:.1f} %)" if p.get("predicted_label") and conf is not None else "-"
            source = {"ml_prediction_confirmed": "AI prediction confirmed", "user_corrected": "Corrected by user",
                      "manual_selection": "Chosen manually"}.get(p.get("source"), "-")
            for txt, xcm in zip((label, pretty(attrs.get(key)), ai, source), cols):
                self._text(xcm * CM, y, txt, 8)
            y -= 0.42 * CM
        model = (ctx.get("design_spec") or {}).get("model") or {}
        if model.get("checkpoint_sha256"):
            y -= 0.15 * CM
            self._text(2 * CM, y, f"Classifier: {model.get('model_type') or 'image classifier'}; checkpoint SHA-256 "
                                  f"{str(model['checkpoint_sha256'])[:16]}...  AI output is a suggestion; the design above was confirmed by the user.",
                       6.8, False, GRAY)
            y -= 0.4 * CM

        # fabric requirement summary
        rows = ctx.get("width_estimates") or []
        if rows:
            y -= 0.5 * CM
            self._text(2 * CM, y, "Fabric requirement", 11, True, BLUE)
            y -= 0.55 * CM
            for r in rows:
                txt = (f"{r['fabric_width_in']}\" ({r['fabric_width_cm']} cm): buy {r['recommended_purchase_m']} m"
                       f" / {r.get('recommended_purchase_yd', '-')} yd"
                       f"  (layout {r['base_layout_length_cm']} cm, fabric use {r['utilisation_percent']} %)"
                       if r.get("fits") else f"{r['fabric_width_in']}\" ({r['fabric_width_cm']} cm): does not fit - {r.get('error', '')}")
                self._text(2.2 * CM, y, ("> " if r.get("selected") else "  ") + txt, 8.5, bool(r.get("selected")))
                y -= 0.45 * CM
        self._text(2 * CM, 2.0 * CM, "Status: PROTOTYPE - the calculation passed geometric validation; the fit is not tested. "
                                     "Confirm the fit with a toile (test garment) before cutting the final fabric.", 8, False, RED)
        self._footer()
        c.showPage()

    # ── pattern overview: front, back and sleeve on ONE page at a reduced scale ──
    def _one(self, cm):
        """A length in the chosen unit only (short enough for a label on a drawing)."""
        if cm is None:
            return "-"
        return f"{units.cm_to_in(cm):.2f} in" if self.unit == "in" else f"{cm:.1f} cm"

    def _overview_scale(self, blocks):
        """The largest reduction 1:n at which the blocks fit side by side with room for their dimension lines."""
        for n in OVERVIEW_SCALES:
            width = sum(b["w"] for b in blocks) / n + OVERVIEW_GUTTER_CM * len(blocks)
            if width <= OVERVIEW_WIDTH_CM and max(b["h"] for b in blocks) / n <= OVERVIEW_HEIGHT_CM:
                return n
        return OVERVIEW_SCALES[-1]

    def _fit_text(self, text, width_pt, size, min_size=4.2, font="Helvetica"):
        """(text, size) that fits the width: first a smaller size, then cut with '...'."""
        text = str(text)
        while size > min_size and self.c.stringWidth(text, font, size) > width_pt:
            size -= 0.2
        while len(text) > 4 and self.c.stringWidth(text, font, size) > width_pt:
            text = text[:-4].rstrip() + "..."
        return text, size

    def _dim_h(self, xa, xb, y, label, sub=None, above=True):
        c = self.c
        c.setStrokeColor(DIM_COLOUR)
        c.setFillColor(DIM_COLOUR)
        c.setLineWidth(0.6)
        c.line(xa, y, xb, y)
        for x, sgn in ((xa, 1), (xb, -1)):
            pth = c.beginPath()
            pth.moveTo(x, y)
            pth.lineTo(x + sgn * 3.2, y + 1.3)
            pth.lineTo(x + sgn * 3.2, y - 1.3)
            pth.close()
            c.drawPath(pth, stroke=0, fill=1)
        mid = (xa + xb) / 2

        def write(text, yy, font, size, colour):
            half = c.stringWidth(text, font, size) / 2 + 1.5              # a light patch keeps the text readable over lines
            c.setFillColor(OVERVIEW_FILL)
            c.rect(mid - half, yy - 1.2, 2 * half, size + 1.0, stroke=0, fill=1)
            c.setFillColor(colour)
            c.setFont(font, size)
            c.drawCentredString(mid, yy, text)

        write(label, y + 2.2 if above else y - 6.6, "Helvetica-Bold", 5.6, colors.black)
        if sub:
            txt, size = self._fit_text(sub, max(abs(xb - xa) - 4, 30), 5.0)
            write(txt, y - 6.4 if above else y - 12.4, "Helvetica", size, GRAY)

    def _dim_v(self, x, ya, yb, label, left=True):
        """Vertical dimension line from ya (top) to yb (bottom); the label is written along it."""
        c = self.c
        c.setStrokeColor(DIM_COLOUR)
        c.setFillColor(DIM_COLOUR)
        c.setLineWidth(0.6)
        c.line(x, ya, x, yb)
        for y, sgn in ((ya, -1), (yb, 1)):
            pth = c.beginPath()
            pth.moveTo(x, y)
            pth.lineTo(x - 1.3, y + sgn * 3.2)
            pth.lineTo(x + 1.3, y + sgn * 3.2)
            pth.close()
            c.drawPath(pth, stroke=0, fill=1)
        width = c.stringWidth(label, "Helvetica-Bold", 5.6)
        # centred on the line; a label longer than its line hangs down from the line's top instead
        top = ya if abs(ya - yb) < width else (ya + yb) / 2 + width / 2
        c.saveState()
        c.translate(x - 2.0 if left else x + 6.0, top - width)
        c.rotate(90)
        c.setFillColor(colors.black)
        c.setFont("Helvetica-Bold", 5.6)
        c.drawString(0, 0, label)
        c.restoreState()

    def _page_overview(self):
        """
        One page that can be read at a glance: the real front, back and sleeve side by side at the same reduced
        scale 1:n, the important dimensions written on them with this customer's numbers, and the measurements
        entered. It is an overview, not a cutting template.
        """
        c, ctx = self.c, self.ctx
        attrs = self.pattern.get("design_attributes", {}) or {}
        pretty = lambda v: str(v).replace("-", " ").capitalize() if v else "-"    # noqa: E731
        c.setFillColor(GREEN)
        c.setFont("Helvetica-Bold", 20)
        c.drawCentredString(PAGE_W / 2, PAGE_H - 1.7 * CM, "DIGITAL TAILOR SYSTEM")
        c.setFillColor(colors.black)
        c.setFont("Helvetica-Bold", 12)
        c.drawCentredString(PAGE_W / 2, PAGE_H - 2.4 * CM, "Measurement-based pattern overview")

        # customer and design
        left, right = OVERVIEW_LEFT_CM * CM, (OVERVIEW_LEFT_CM + OVERVIEW_WIDTH_CM) * CM
        top = PAGE_H - 3.0 * CM
        c.setFillColor(PALE)
        c.roundRect(left, top - 3.5 * CM, 11.0 * CM, 3.5 * CM, 6, stroke=0, fill=1)
        ease = (self.pattern.get("measurements_used") or {}).get("ease_profile") or {}
        sleeve = pretty(attrs.get("sleeve_length"))
        if attrs.get("sleeve_style") not in (None, "none"):
            sleeve += " / " + pretty(attrs.get("sleeve_style")).lower()
        y = top - 0.55 * CM
        for label, value in (("Customer", ctx.get("customer_name")), ("Garment", pretty(attrs.get("garment_type"))),
                             ("Neckline", pretty(attrs.get("neckline_type"))), ("Sleeve", sleeve),
                             ("Fabric", self.fabric_name), ("Fit", ease.get("fit_label") or self.meas.get("fit_preference"))):
            self._text(left + 0.4 * CM, y, f"{label}:", 8.5, True, GREEN)
            self._text(left + 3.2 * CM, y, str(value or "-")[:46], 8.5)
            y -= 0.5 * CM
        c.setFillColor(PALE)
        c.roundRect(left + 11.6 * CM, top - 0.7 * CM, right - left - 11.6 * CM, 0.7 * CM, 5, stroke=0, fill=1)
        c.setFillColor(GREEN)
        c.setFont("Helvetica-Bold", 8)
        c.drawCentredString((left + 11.6 * CM + right) / 2, top - 0.47 * CM,
                            "ALL MEASUREMENTS IN INCHES" if self.unit == "in" else "ALL MEASUREMENTS IN CM")
        if ctx.get("image_path"):
            try:
                from reportlab.lib.utils import ImageReader
                img = ImageReader(ctx["image_path"])
                iw, ih = img.getSize()
                bw, bh = right - left - 11.6 * CM, 2.6 * CM
                r = min(bw / iw, bh / ih)
                c.drawImage(img, left + 11.6 * CM + (bw - iw * r) / 2, top - 3.5 * CM + (bh - ih * r) / 2, iw * r, ih * r)
            except Exception:                           # noqa: BLE001 - a missing/corrupt photo must not stop the PDF
                pass

        # the blocks, all at one scale
        names = {"front_bodice": "FRONT", "back_bodice": "BACK", "sleeve": "SLEEVE"}
        blocks = []
        for piece in self._block_pieces():
            xs_ = [q[0] for q in piece["outline"]]
            ys_ = [q[1] for q in piece["outline"]]
            blocks.append({"piece": piece, "min_x": min(xs_), "min_y": min(ys_), "w": max(xs_) - min(xs_), "h": max(ys_) - min(ys_)})
        n = self._overview_scale(blocks)
        k = CM / n                                                         # points on the page per cm of pattern
        self.overview_scale = n
        spare = OVERVIEW_WIDTH_CM - sum(b["w"] for b in blocks) / n - OVERVIEW_GUTTER_CM * len(blocks)
        gap = max(spare, 0.0) / len(blocks) * CM
        bar_top = top - 4.1 * CM
        y0 = bar_top - 1.6 * CM                                            # top of every block
        lowest = y0
        cursor = left
        for b in blocks:
            piece, kind = b["piece"], b["piece"].get("piece_type")
            panel_w = b["w"] * k + OVERVIEW_GUTTER_CM * CM + gap
            x0 = cursor + OVERVIEW_GUTTER_LEFT_CM * CM + gap / 2

            def P(q, x0=x0, b=b):
                return x0 + (q[0] - b["min_x"]) * k, y0 - (q[1] - b["min_y"]) * k

            c.setFillColor(GREEN)
            c.roundRect(cursor + 2, bar_top - 0.6 * CM, panel_w - 4, 0.6 * CM, 4, stroke=0, fill=1)
            c.setFillColor(colors.white)
            c.setFont("Helvetica-Bold", 9)
            c.drawCentredString(cursor + panel_w / 2, bar_top - 0.42 * CM, names[kind])

            pth = c.beginPath()
            pth.moveTo(*P(piece["outline"][0]))
            for q in piece["outline"][1:]:
                pth.lineTo(*P(q))
            pth.close()
            c.setStrokeColor(colors.black)
            c.setFillColor(OVERVIEW_FILL)
            c.setLineWidth(1.0)
            c.drawPath(pth, stroke=1, fill=1)
            if piece.get("fold_line"):
                c.setDash(3, 2)
                c.setLineWidth(0.9)
                c.line(*P(piece["fold_line"]["start"]), *P(piece["fold_line"]["end"]))
                c.setDash()
            c.setStrokeColor(colors.HexColor("#8A8F94"))
            c.setLineWidth(0.5)
            for d in piece.get("darts") or []:
                for leg in ("leg_a", "leg_b"):
                    c.line(*P(d["apex"]), *P(d[leg]))
                    if "lower_apex" in d:
                        c.line(*P(d["lower_apex"]), *P(d[leg]))

            block_right = x0 + b["w"] * k
            below = []
            for d in piece.get("dimensions") or []:
                a, e = P(d["a"]), P(d["b"])
                value = self._one(d["value_cm"])
                formula = str((self.trace.get(d.get("trace")) or {}).get("formula") or "").split(";")[0].strip()
                sub = (("cm: " if self.unit == "in" else "") + formula) if formula and any(ch.isdigit() for ch in formula) else None
                did = d["id"]
                if did == "neck_width":
                    self._dim_h(a[0], e[0], y0 + 0.45 * CM, f"Neck {value}")
                elif did == "shoulder":
                    c.saveState()
                    c.translate((a[0] + e[0]) / 2, (a[1] + e[1]) / 2)
                    c.rotate(math.degrees(math.atan2(e[1] - a[1], e[0] - a[0])))
                    c.setFillColor(colors.black)
                    c.setFont("Helvetica-Bold", 5.2)
                    c.drawCentredString(0, 2.4, f"Shoulder {value}")
                    c.restoreState()
                elif did == "neck_depth":
                    self._dim_v(x0 - 0.3 * CM, a[1], e[1], f"{d['label']} {value}")
                elif did == "shoulder_to_waist":
                    self._dim_v(x0 - 0.65 * CM, a[1], e[1], f"Length to waist {value}")
                elif did == "armhole_depth":
                    self._dim_v(block_right + 0.3 * CM, a[1], e[1], f"Armhole depth {value}", left=False)
                elif did == "garment_length":
                    self._dim_v(block_right + 0.7 * CM, a[1], e[1], f"Garment length {value}", left=False)
                elif did in ("bust_width", "waist_width", "hip_width", "sleeve_width"):
                    self._dim_h(a[0], e[0], a[1], f"{d['label']} {value}", sub)
                elif did == "sleeve_length":
                    self._dim_v(x0 - 0.3 * CM, a[1], e[1], f"Sleeve length {value}")
                elif did == "cap_height":
                    self._dim_v(block_right + 0.3 * CM, a[1], e[1], f"Cap height {value}", left=False)
                elif did == "sleeve_end":
                    self._dim_h(a[0], e[0], a[1] - 0.3 * CM, f"Sleeve end {value}", sub, above=False)
                else:                                                      # short or curved: listed under the block
                    below.append(f"{d['label']}: {value}")
            if kind == "sleeve":
                yy = y0 - b["h"] * k + 0.3 * CM
                c.setFillColor(GRAY)
                c.setFont("Helvetica", 5.2)
                c.drawCentredString(x0 + b["w"] * k * 0.34, yy, "front")
                c.drawCentredString(x0 + b["w"] * k * 0.66, yy, "back")
            yy = y0 - b["h"] * k - (1.15 if kind == "sleeve" else 0.5) * CM
            for line in below:
                self._text(x0, yy, line, 6.2, False, colors.HexColor("#333333"))
                yy -= 0.3 * CM
            if kind == "sleeve":
                yy = self._overview_sleeve_check(cursor + 0.2 * CM, yy - 0.25 * CM, panel_w - 0.4 * CM)
            lowest = min(lowest, yy)
            cursor += panel_w
        if not any(b["piece"].get("piece_type") == "sleeve" for b in blocks):
            self._text(left, lowest - 0.1 * CM, "Sleeveless design: no sleeve piece.", 7, False, GRAY)

        # measurements entered (those this design uses)
        table_top = 7.7 * CM
        c.setFillColor(PALE)
        c.roundRect(left, table_top - 0.1 * CM, right - left, 0.6 * CM, 4, stroke=0, fill=1)
        self._text(left + 0.3 * CM, table_top + 0.08 * CM, "MEASUREMENTS ENTERED", 9, True, GREEN)
        entered = ctx.get("original_values") or {}
        needed = set(ms.required_for_design(attrs))                        # a sleeveless design lists no sleeve values
        rows = []
        for f in ms.REQUIREMENTS["fields"]:
            v = self.meas.get(f["key"])
            if v is None or (f["kind"] != "design" and f["key"] not in needed):
                continue
            e = entered.get(f["key"]) or {}
            typed = f"{e['value']:g} {e.get('unit', '')}".strip() if isinstance(e.get("value"), (int, float)) else None
            shown = self._one(v)
            other_unit = typed and e.get("unit") in ("cm", "in") and e.get("unit") != self.unit
            rows.append((f["label"], f"{shown}  (typed {typed})" if other_unit else shown))   # only when typed in the other unit
        half = max((len(rows) + 1) // 2, 1)
        col_w = (right - left) / 2
        c.setStrokeColor(colors.HexColor("#C9D3CC"))
        c.setLineWidth(0.4)
        for i, (label, value) in enumerate(rows):
            col, row = divmod(i, half)
            x, y = left + col * col_w, table_top - 0.55 * CM - row * 0.42 * CM
            self._text(x + 0.3 * CM, y, label, 7.8, True)
            self._text(x + 5.0 * CM, y, value, 7.8)
            c.line(x + 0.2 * CM, y - 0.12 * CM, x + col_w - 0.2 * CM, y - 0.12 * CM)

        # what this page is
        c.setFillColor(PALE)
        c.roundRect(left, 0.9 * CM, right - left, 2.3 * CM, 6, stroke=0, fill=1)
        c.setFillColor(colors.black)
        c.setFont("Helvetica-Bold", 11)
        c.drawCentredString(PAGE_W / 2, 2.6 * CM, f"REDUCED SCALE 1:{n}  -  Overview  -  Not a cutting template")
        c.setFont("Helvetica", 7.4)
        for i, line in enumerate((
                f"Drawn 1:{n} when printed at 100 %: 1 cm on this page is {n} cm of the pattern. The real-size pattern is a separate download.",
                "Dimensions are on the sewing line: ease is included, seam allowance is not. Neck width and neck depths are design values you can change.",
                "The values come from a geometric calculation; the fit has not been tested. Sew a test garment before cutting good fabric.")):
            c.drawCentredString(PAGE_W / 2, (2.15 - 0.36 * i) * CM, line)
        self._scale_note = f"Overview at reduced scale 1:{n} - not a cutting template"
        self._footer()
        self._scale_note = None
        c.showPage()

    def _overview_sleeve_check(self, x, y, width):
        """Armhole against sleeve cap, and the fabric to buy, in the free space under the sleeve block."""
        cap = self.pattern.get("sleeve_cap") or {}
        if cap.get("has_sleeve"):
            status = cap.get("status", "-")
            self._text(x, y, "Sleeve cap against armhole", 7.2, True, GREEN)
            y -= 0.36 * CM
            for label, value in (("Armhole (front + back)", self._one(cap.get("bodice_armhole_seam_cm"))),
                                 ("Sleeve cap", self._one(cap.get("sleeve_cap_seam_cm"))),
                                 (str(cap.get("difference_is", "ease")).capitalize(), self._one(cap.get("difference_cm")))):
                self._text(x, y, f"{label}: {value}", 6.6)
                y -= 0.3 * CM
            self._text(x, y, f"Result: {status}", 7.2, True, RED if status == "REVIEW" else colors.HexColor("#1B5E20"))
            y -= 0.55 * CM
        rows = self.ctx.get("width_estimates") or []
        if rows:
            self._text(x, y, "Fabric to buy", 7.2, True, GREEN)
            y -= 0.36 * CM
            for r in rows:
                txt = (f"{r['fabric_width_in']} in wide: {r['recommended_purchase_m']} m / {r.get('recommended_purchase_yd', '-')} yd"
                       if r.get("fits") else f"{r['fabric_width_in']} in wide: does not fit")
                self._text(x, y, txt, 6.6)
                y -= 0.3 * CM
            y = self._para(x, y, "From the full-size layout of the pieces.", width, 6, color=GRAY, leading=0.28)
        return y

    # ── page 2: printing ────────────────────────────────────────────────────
    def _page_print(self):
        c = self.c
        self._on_pattern_page = True
        self._title("Printing instructions", "Read before printing the pattern pages")
        box_top = PAGE_H - 3.8 * CM
        c.setFillColor(LIGHT)
        c.setStrokeColor(RED)
        c.setLineWidth(1.5)
        c.rect(2 * CM, box_top - 8.2 * CM, PAGE_W - 4 * CM, 8.2 * CM, fill=1, stroke=1)
        self._text(2.4 * CM, box_top - 0.7 * CM, "PRINTING INSTRUCTIONS  -  PRINT AT 100 % (ACTUAL SIZE)", 11, True, RED)
        yy = box_top - 1.4 * CM
        for i, line in enumerate(INSTRUCTIONS, 1):
            for j, ln in enumerate(self._wrap(line, PAGE_W - 5.4 * CM)):
                self._text(2.4 * CM if j == 0 else 3.0 * CM, yy, (f"{i}. " if j == 0 else "") + ln, 8.5)
                yy -= 0.42 * CM
            yy -= 0.05 * CM
        self._calibration_square(2.4 * CM, box_top - 15.0 * CM)
        self._text(8.6 * CM, box_top - 11.0 * CM, f"Pattern sheet: {self.sheet_w:.0f} x {self.sheet_h:.0f} cm", 9, True)
        self._text(8.6 * CM, box_top - 11.6 * CM, f"Printed on {len(self.tiles)} A4 page(s), tiles {self.cols} x {self.rows} grid", 9)
        self._text(8.6 * CM, box_top - 12.2 * CM, f"Overlap {OVERLAP_CM:g} cm; crop marks at every tile corner.", 9)
        self._footer()
        c.showPage()

    # ── measurements ────────────────────────────────────────────────────────
    def _page_measurements(self):
        self._title("Measurements", "As entered, in centimetres and in inches. The pattern is calculated from the cm values "
                                    "(1 in = 2.54 cm).")
        y = PAGE_H - 4.0 * CM
        xs = (2.0, 7.6, 10.8, 13.2, 15.6)
        entered = self.ctx.get("original_values") or {}
        derived = (self.pattern.get("measurements_used") or {}).get("derived") or {}
        for h, xcm in zip(("Measurement", "As entered", "cm", "inch", "What it is"), xs):
            self._text(xcm * CM, y, h, 8.5, True)
        y -= 0.45 * CM
        calculated = {"neck_width_cm": derived.get("neck_width_cm"), "front_neck_depth_cm": derived.get("front_neck_depth_cm"),
                      "back_neck_depth_cm": derived.get("back_neck_depth_cm"), "armhole_depth_cm": derived.get("armhole_depth_cm"),
                      "bust_point_distance_cm": derived.get("bust_point_distance_cm")}
        for f in ms.REQUIREMENTS["fields"]:
            key = f["key"]
            v = self.meas.get(key)
            e = entered.get(key) or {}
            if v is None and f["kind"] == "design" and calculated.get(key) is not None:
                v, as_entered, what = calculated[key], "-", "calculated value"
            elif v is None:
                as_entered, what = "-", "not needed for this design"
            else:
                as_entered = f"{e['value']:g} {e.get('unit', '')}".strip() if isinstance(e.get("value"), (int, float)) else f"{v:g} cm"
                what = "design value" if f["kind"] == "design" else "measured"
            row = (f["label"], as_entered, _fmt(v), _fmt(units.cm_to_in(v), 2) if v is not None else "-", what)
            for txt, xcm in zip(row, xs):
                self._text(xcm * CM, y, txt, 8.5, False, GRAY if what == "not needed for this design" else colors.black)
            y -= 0.42 * CM
        old = [(ms.LABELS[k], self.meas.get(k)) for k in ms.LEGACY_KEYS if self.meas.get(k) is not None]
        if old:
            y -= 0.2 * CM
            self._text(2 * CM, y, "Saved earlier, not used by the drafting method: "
                       + ", ".join(f"{label} {value:g} cm" for label, value in old), 7.5, False, GRAY)
            y -= 0.42 * CM
        y -= 0.4 * CM
        self._text(2 * CM, y, "Body measurement + ease = garment measurement", 11, True, BLUE)
        y -= 0.55 * CM
        ease = (self.pattern.get("measurements_used") or {}).get("ease_profile") or {}
        eased = (self.pattern.get("measurements_used") or {}).get("eased") or {}
        for h, xcm in zip(("", "Body", "+ Ease", "= Garment"), (2.0, 7.6, 10.8, 13.2)):
            self._text(xcm * CM, y, h, 8.5, True)
        y -= 0.45 * CM
        for label, key in (("Bust", "bust_cm"), ("Waist", "waist_cm"), ("Hip", "hip_cm")):
            body, e, g_ = self.meas.get(key), ease.get(key), eased.get(key)
            if body is None or g_ is None:
                continue
            for txt, xcm in zip((label, self._len(body), self._len(e), self._len(g_)), (2.0, 7.6, 10.8, 13.2)):
                self._text(xcm * CM, y, txt, 8.5)
            y -= 0.42 * CM
        y -= 0.2 * CM
        y = self._para(2 * CM, y, f"Fit: {ease.get('fit_label') or ease.get('fit_preference') or '-'}. Ease is the room needed "
                       "to move and breathe; it is part of the garment size. Seam allowance is NOT ease: it is added outside "
                       "the sewing line and is listed with the pattern pieces.", PAGE_W - 4 * CM, 8, color=GRAY)
        warnings = self.ctx.get("warnings") or []
        if warnings:
            y -= 0.3 * CM
            self._text(2 * CM, y, "Please check", 11, True, RED)
            y -= 0.5 * CM
            for w in warnings[:6]:
                y = self._para(2 * CM, y, "- " + str(w.get("message", "")), PAGE_W - 4 * CM, 8)
        self._footer()
        self.c.showPage()

    # ── block overview: the piece with its dimensions drawn on it (NOT to scale) ──
    def _page_block(self, piece):
        c = self.c
        kind = piece.get("piece_type")
        name = {"front_bodice": "FRONT", "back_bodice": "BACK", "sleeve": "SLEEVE"}[kind]
        self._title(f"{name} block - measurement overview",
                    "NOT TO SCALE: drawn to fit this page so the dimensions can be read. The cutting pattern is on the 1:1 pages.")
        outline = piece["outline"]
        cutline = piece.get("cutting_line") or outline
        xs_ = [q[0] for q in cutline]
        ys_ = [q[1] for q in cutline]
        min_x, max_x, min_y, max_y = min(xs_), max(xs_), min(ys_), max(ys_)
        box_w, box_h = 9.6 * CM, 19.0 * CM
        scale = min(box_w / (max_x - min_x), box_h / (max_y - min_y))
        ox, oy = 2.2 * CM, PAGE_H - 4.2 * CM

        def P(q):
            return ox + (q[0] - min_x) * scale, oy - (q[1] - min_y) * scale

        def path(points, close=True):
            pth = c.beginPath()
            pth.moveTo(*P(points[0]))
            for q in points[1:]:
                pth.lineTo(*P(q))
            if close:
                pth.close()
            return pth

        c.setStrokeColor(colors.HexColor("#9AA0A6"))
        c.setLineWidth(0.6)
        c.drawPath(path(cutline), stroke=1, fill=0)                       # cutting line
        c.setStrokeColor(colors.black)
        c.setFillColor(colors.HexColor("#F4F7F4"))
        c.setLineWidth(1.1)
        c.drawPath(path(outline), stroke=1, fill=1)                       # sewing line
        if piece.get("fold_line"):
            a, b = P(piece["fold_line"]["start"]), P(piece["fold_line"]["end"])
            c.setStrokeColor(RED)
            c.setLineWidth(2.0)
            c.line(*a, *b)
            c.saveState()
            c.translate(a[0] - 0.25 * CM, (a[1] + b[1]) / 2)
            c.rotate(90)
            c.setFillColor(RED)
            c.setFont("Helvetica-Bold", 7)
            c.drawCentredString(0, 0, "FOLD - centre " + ("front" if kind == "front_bodice" else "back"))
            c.restoreState()
        gl = piece["grain_line"]
        ga, gb = P(gl["start"]), P(gl["end"])
        c.setStrokeColor(colors.HexColor("#1565C0"))
        c.setLineWidth(0.7)
        c.line(*ga, *gb)
        for tip, tail in ((ga, gb), (gb, ga)):
            ang = math.atan2(tip[1] - tail[1], tip[0] - tail[0])
            for sgn in (-0.4, 0.4):
                c.line(tip[0], tip[1], tip[0] - 0.3 * CM * math.cos(ang + sgn), tip[1] - 0.3 * CM * math.sin(ang + sgn))
        c.setStrokeColor(colors.HexColor("#6A1B9A"))
        for d in piece.get("darts") or []:
            apex = P(d["apex"])
            for leg in ("leg_a", "leg_b"):
                c.line(*apex, *P(d[leg]))
                if "lower_apex" in d:
                    c.line(*P(d["lower_apex"]), *P(d[leg]))
        c.setFillColor(colors.black)
        for nt in piece.get("notches") or []:
            q = P(nt["point"])
            c.circle(q[0], q[1], 0.07 * CM, stroke=0, fill=1)

        # numbered dimension lines
        dims = piece.get("dimensions") or []
        c.setFont("Helvetica-Bold", 6.5)
        for n, d in enumerate(dims, 1):
            a, b = P(d["a"]), P(d["b"])
            c.setStrokeColor(DIM_COLOUR)
            c.setFillColor(DIM_COLOUR)
            c.setLineWidth(0.9)
            if d["kind"] != "curve" and (abs(a[0] - b[0]) > 0.5 or abs(a[1] - b[1]) > 0.5):
                c.line(*a, *b)
                ang = math.atan2(b[1] - a[1], b[0] - a[0]) + math.pi / 2
                for q in (a, b):                                           # end ticks
                    c.line(q[0] - 0.1 * CM * math.cos(ang), q[1] - 0.1 * CM * math.sin(ang),
                           q[0] + 0.1 * CM * math.cos(ang), q[1] + 0.1 * CM * math.sin(ang))
            mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
            c.setFillColor(colors.white)
            c.circle(mx, my, 0.19 * CM, stroke=1, fill=1)
            c.setFillColor(DIM_COLOUR)
            c.drawCentredString(mx, my - 2.2, str(n))

        # the list of dimensions
        lx = 12.4 * CM
        y = PAGE_H - 4.0 * CM
        self._text(lx, y, "Dimensions (sewing line, without seam allowance)", 8.5, True)
        y -= 0.5 * CM
        for n, d in enumerate(dims, 1):
            c.setFillColor(DIM_COLOUR)
            c.setFont("Helvetica-Bold", 7.5)
            c.drawString(lx, y, str(n))
            self._text(lx + 0.5 * CM, y, d["label"], 7.8, True)
            self._text(lx + 0.5 * CM, y - 0.33 * CM, self._len(d["value_cm"], 2), 7.8)
            src = (self.trace.get(d.get("trace")) or {}).get("source")
            if src:
                self._text(lx + 4.3 * CM, y - 0.33 * CM, SOURCE_WORDS.get(src, src), 6.8, False, GRAY)
            y -= 0.78 * CM
        y -= 0.1 * CM
        cut_txt = f"CUT {piece['cut_count']}" + (" ON FOLD" if piece.get("cut_on_fold") else "")
        self._text(lx, y, cut_txt, 9, True, BLUE)
        y -= 0.42 * CM
        self._text(lx, y, "Blue arrow = grain direction (parallel to the selvedge)", 7.2, False, GRAY)
        y -= 0.36 * CM
        self._text(lx, y, "Black line = sewing line; grey line = cutting line", 7.2, False, GRAY)
        y -= 0.36 * CM
        sa = piece.get("seam_allowances") or {}
        if sa:
            y = self._para(lx, y, "Seam allowances (cm): " + ", ".join(f"{k.replace('_', ' ')} {v:g}" for k, v in sa.items()),
                           PAGE_W - lx - 1.6 * CM, 7.2, color=GRAY, leading=0.34)
        if kind == "sleeve":
            self._sleeve_report(lx, y - 0.4 * CM)
        self._text(2 * CM, 1.6 * CM, "Each numbered line on the drawing is the dimension with the same number in the list. "
                                     "How every value is calculated: see \"Why this size?\".", 7.5, False, GRAY)
        self._footer()
        c.showPage()

    def _sleeve_report(self, x, y):
        cap = self.pattern.get("sleeve_cap") or {}
        if not cap.get("has_sleeve"):
            return y
        self._text(x, y, "Does the sleeve fit the armhole?", 9, True, BLUE)
        y -= 0.48 * CM
        lo, hi = (cap.get("allowed_cm") or [None, None])[:2]
        rows = [("Front armhole curve", self._len(cap.get("front_armhole_curve_cm"), 2)),
                ("Back armhole curve", self._len(cap.get("back_armhole_curve_cm"), 2)),
                ("Bodice armhole seam", self._len(cap.get("bodice_armhole_seam_cm"), 2)),
                ("Sleeve cap seam", self._len(cap.get("sleeve_cap_seam_cm"), 2)),
                ("Difference", self._len(cap.get("difference_cm"), 2)),
                ("Allowed " + str(cap.get("difference_is", "sleeve-cap ease")), f"{_fmt(lo)} to {_fmt(hi)} cm")]
        for label, value in rows:
            self._text(x, y, label, 7.6, True)
            self._text(x, y - 0.32 * CM, value, 7.6)
            y -= 0.7 * CM
        status = cap.get("status", "-")
        self._text(x, y, f"Status: {status}", 9, True, RED if status == "REVIEW" else colors.HexColor("#1B5E20"))
        y -= 0.42 * CM
        return self._para(x, y, cap.get("note", ""), PAGE_W - x - 1.6 * CM, 7.2, color=GRAY, leading=0.34)

    # ── why this size? ──────────────────────────────────────────────────────
    def _page_why(self, rows, page_index):
        self._title("Why this size?" + (f" (continued {page_index + 1})" if page_index else ""),
                    "Every pattern dimension, the calculation that produced it with this customer's numbers, and where the rule comes from")
        y = PAGE_H - 4.0 * CM
        xs = (2.0, 7.4, 10.6, 17.0)
        for h, xcm in zip(("Dimension", "Value", "How it is calculated (cm)", "From"), xs):
            self._text(xcm * CM, y, h, 8.2, True)
        y -= 0.45 * CM
        for r in rows:
            formula = self._wrap(str(r.get("formula", "")), 6.2 * CM, 7.2)[:3]
            self._text(xs[0] * CM, y, str(r.get("label") or r.get("name", ""))[:36], 7.6)
            self._text(xs[1] * CM, y, self._len(r.get("value_cm"), 2), 7.4)
            for k, ln in enumerate(formula):
                self._text(xs[2] * CM, y - k * 0.3 * CM, ln, 7.2)
            src = r.get("source") or r.get("status")
            self._text(xs[3] * CM, y, SOURCE_WORDS.get(src, str(src or "-"))[:22], 6.8, True,
                       RED if src == "extension" else BLUE if src in ("method", "figure") else colors.black)
            y -= (0.42 + 0.3 * (len(formula) - 1)) * CM
        method = self.pattern.get("drafting_method") or {}
        src = (method.get("source") or {}).get("title")
        if src and page_index == 0:
            self._para(2 * CM, 2.6 * CM, f"Drafting method: {src}. 'project rule' = needed for this project and not covered "
                       "by that source; it must be confirmed by a fitting trial.", PAGE_W - 4 * CM, 7, color=GRAY, leading=0.32)
        self._footer()
        self.c.showPage()

    # ── pieces and sewing notes ─────────────────────────────────────────────
    def _page_pieces(self):
        self._title("Pattern pieces and sewing notes")
        y = PAGE_H - 4.0 * CM
        heads = ["Piece", "Cut", "On fold", "Seam allowances (cm)", "Size with SA (cm)"]
        xs = [2, 6.6, 7.8, 9.4, 16.2]
        for h, x in zip(heads, xs):
            self._text(x * CM, y, h, 8.5, True)
        y -= 0.5 * CM
        for p in self.pieces:
            box = p.get("cut_bounding_box") or p.get("bounding_box") or {}
            sa = p.get("seam_allowances") or {}
            sa_txt = ", ".join(f"{k.replace('_', ' ')} {v:g}" for k, v in sa.items()) if sa else f"{p.get('seam_allowance_cm')}"
            lines = self._wrap(sa_txt, 6.4 * CM, 7.6)[:2]
            for t, x in zip([p["name"], str(p["cut_count"]), "yes" if p["cut_on_fold"] else "no", lines[0],
                             f"{box.get('width_cm', 0):.1f} x {box.get('height_cm', 0):.1f}"], xs):
                self._text(x * CM, y, t, 7.8)
            if len(lines) > 1:
                self._text(xs[3] * CM, y - 0.32 * CM, lines[1], 7.6)
            y -= (0.45 + 0.32 * (len(lines) - 1)) * CM
        y -= 0.5 * CM
        self._text(2 * CM, y, "Sewing notes", 11, True, BLUE)
        y -= 0.55 * CM
        notes = self.pattern.get("construction_notes") or []
        if not notes:
            self._text(2 * CM, y, "Sewing notes were not stored for this older pattern.", 8, False, GRAY)
        for note in notes[:14]:
            y = self._para(2 * CM, y, "- " + note, PAGE_W - 4 * CM, 7.8, leading=0.38)
            if y < 2.4 * CM:
                break
        self._footer()
        self.c.showPage()

    # ── page 5: fabric requirement for 36" / 45" / 60" ──────────────────────
    def _draw_layout(self, n, ox, oy, box_w, box_h, label):
        c = self.c
        uw, length = n["usable_width_cm"], n["fabric_length_cm"]
        scale = min(box_w / uw, box_h / max(length, 1))
        c.setStrokeColor(colors.black)
        c.setLineWidth(0.8)
        c.rect(ox, oy - length * scale, uw * scale, length * scale, fill=0)
        if n.get("cutting_mode") == "folded":
            c.setLineWidth(2)
            c.line(ox, oy, ox, oy - length * scale)
        for p in n.get("placed_pieces", []):
            pts = [(ox + x * scale, oy - y * scale) for x, y in p["polygon_coordinates"]]
            path = c.beginPath()
            path.moveTo(*pts[0])
            for q in pts[1:]:
                path.lineTo(*q)
            path.close()
            c.setFillColor(colors.Color(0.85, 0.9, 0.97))
            c.setStrokeColor(BLUE)
            c.setLineWidth(0.5)
            c.drawPath(path, fill=1, stroke=1)
        self._text(ox, oy + 0.3 * CM, label, 8, True)
        self._text(ox, oy - length * scale - 0.45 * CM,
                   f"{'folded' if n.get('cutting_mode') == 'folded' else 'open'}; {n['fabric_length_cm']} cm long", 7)

    def _page_layout(self):
        c = self.c
        self._title("Fabric requirement - 36\", 45\" and 60\" widths",
                    "Calculated from the pattern pieces above by the nesting algorithm; layouts drawn to fit, NOT to scale")
        rows = self.ctx.get("width_estimates") or []
        layouts = self.ctx.get("width_layouts") or {}
        y = PAGE_H - 4.0 * CM
        heads = ["Fabric width", "Layout length", "Need to buy", "Pattern area", "Fabric bought", "Waste", "Fabric use"]
        xs = [2.0, 5.0, 7.6, 11.0, 13.9, 16.6, 17.9]
        for h, x in zip(heads, xs):
            self._text(x * CM, y, h, 7.6, True)
        y -= 0.45 * CM
        for r in rows:
            sel = bool(r.get("selected"))
            self._text(xs[0] * CM, y, f"{r['fabric_width_in']} in / {r['fabric_width_cm']} cm" + (" *" if sel else ""), 7.6, sel)
            if r.get("fits"):
                vals = [f"{r['base_layout_length_cm']} cm",
                        f"{r['recommended_purchase_m']} m / {r.get('recommended_purchase_yd', '-')} yd",
                        f"{r.get('pattern_area_m2', '-')} m2 / {r.get('pattern_area_yd2', '-')} yd2",
                        f"{r.get('purchase_area_m2', '-')} m2 / {r.get('purchase_area_yd2', '-')} yd2",
                        f"{r['waste_percent']} %", f"{r['utilisation_percent']} %"]
                for t, x in zip(vals, xs[1:]):
                    self._text(x * CM, y, t, 7.6, sel)
            else:
                self._text(xs[1] * CM, y, f"Does not fit: {r.get('error', '')}"[:90], 7.6, False, RED)
            y -= 0.45 * CM
        if any(r.get("selected") for r in rows):
            self._text(2 * CM, y, "* the width chosen for this pattern", 7, False, GRAY)
            y -= 0.35 * CM
        if not rows and self.nesting:                    # older pattern: only the saved single estimate exists
            n = self.nesting
            self._text(2 * CM, y, f"Fabric width {n['fabric_width_cm']:g} cm: layout {n['fabric_length_cm']} cm, purchase "
                                  f"{n['purchasing_recommended_m']} m, utilisation {n['utilisation_percent']} %", 8)
            y -= 0.45 * CM
            layouts = {n["fabric_width_cm"]: n}
        y -= 0.4 * CM
        y = self._para(2 * CM, y, "Need to buy = layout length + 3 % shrinkage + 10 cm cutting margin, rounded up to 10 cm "
                                  "(a LENGTH: metres or yards of that width). Areas are square metres / square yards: pattern "
                                  "area = the pieces themselves; waste and fabric use compare the pieces with the fabric the "
                                  "layout occupies. Layout: real piece shapes placed by a checked heuristic (pieces never overlap, "
                                  "grain kept, fold pieces on the fold) - feasible, not proven minimal. The widest fabric is "
                                  "not automatically the best: compare length, waste and price.",
                       PAGE_W - 4 * CM, 7.3, color=GRAY, leading=0.36)
        y -= 0.9 * CM
        items = [(w, n) for w, n in layouts.items() if n and n.get("placed_pieces")]
        if items:
            col_w = (PAGE_W - 4 * CM - (len(items) - 1) * 0.8 * CM) / len(items)
            for k, (w, n) in enumerate(items):
                inch = next((r["fabric_width_in"] for r in rows if r["fabric_width_cm"] == w), None)
                label = f"{inch}\" ({w:g} cm)" if inch else f"{w:g} cm"
                self._draw_layout(n, 2 * CM + k * (col_w + 0.8 * CM), y, col_w, y - 3.2 * CM, label)
        else:
            self._text(2 * CM, y, "No layout available.", 10)
        self._footer()
        c.showPage()

    # ── tiles ───────────────────────────────────────────────────────────────
    def _tile_has_content(self, col, row):
        x0, y0 = col * STEP_X, row * STEP_Y
        x1, y1 = x0 + TILE_W_CM, y0 + TILE_H_CM
        for pl in self.placements:
            if pl["x"] < x1 and pl["x"] + pl["w"] > x0 and pl["y"] < y1 and pl["y"] + pl["h"] > y0:
                return True
        return False

    def _to_page(self, sx, sy, col, row):
        """Sheet (cm, y down) -> page points for tile (col, row)."""
        px = (MARGIN_CM + sx - col * STEP_X) * CM
        py = PAGE_H - (MARGIN_CM + sy - row * STEP_Y) * CM
        return px, py

    def _poly(self, pts, dx, dy, col, row, close=True):
        path = self.c.beginPath()
        first = True
        for x, y in pts:
            px, py = self._to_page(x + dx, y + dy, col, row)
            if first:
                path.moveTo(px, py)
                first = False
            else:
                path.lineTo(px, py)
        if close:
            path.close()
        return path

    def _draw_piece(self, pl, col, row):
        c, p = self.c, pl["piece"]
        dx, dy = pl["dx"], pl["dy"]
        # seam line (dashed)
        c.setStrokeColor(colors.HexColor("#1565C0"))
        c.setLineWidth(0.6)
        c.setDash(3, 2)
        c.drawPath(self._poly(p["outline"], dx, dy, col, row), stroke=1, fill=0)
        c.setDash()
        # cutting line (solid)
        c.setStrokeColor(colors.black)
        c.setLineWidth(1.0)
        c.drawPath(self._poly(p["cutting_line"], dx, dy, col, row), stroke=1, fill=0)
        # fold line
        if p.get("fold_line"):
            a, b = p["fold_line"]["start"], p["fold_line"]["end"]
            pa, pb = self._to_page(a[0] + dx, a[1] + dy, col, row), self._to_page(b[0] + dx, b[1] + dy, col, row)
            c.setStrokeColor(RED)
            c.setLineWidth(2.2)
            c.line(*pa, *pb)
            c.saveState()
            c.translate((pa[0] + pb[0]) / 2 + 0.35 * CM, (pa[1] + pb[1]) / 2)
            c.rotate(90)
            c.setFillColor(RED)
            c.setFont("Helvetica-Bold", 7)
            c.drawCentredString(0, 0, "PLACE ON FOLD")
            c.restoreState()
        # grainline with arrowheads
        gl = p["grain_line"]
        ga = self._to_page(gl["start"][0] + dx, gl["start"][1] + dy, col, row)
        gb = self._to_page(gl["end"][0] + dx, gl["end"][1] + dy, col, row)
        c.setStrokeColor(colors.black)
        c.setLineWidth(0.7)
        c.line(*ga, *gb)
        for tip, tail in ((ga, gb), (gb, ga)):
            ang = math.atan2(tip[1] - tail[1], tip[0] - tail[0])
            for s in (-0.4, 0.4):
                c.line(tip[0], tip[1], tip[0] - 0.4 * CM * math.cos(ang + s), tip[1] - 0.4 * CM * math.sin(ang + s))
        # darts
        c.setStrokeColor(colors.HexColor("#6A1B9A"))
        c.setLineWidth(0.7)
        for d in p.get("darts") or []:
            apex = self._to_page(d["apex"][0] + dx, d["apex"][1] + dy, col, row)
            for leg in ("leg_a", "leg_b"):
                q = self._to_page(d[leg][0] + dx, d[leg][1] + dy, col, row)
                c.line(*apex, *q)
            if "lower_apex" in d:
                low = self._to_page(d["lower_apex"][0] + dx, d["lower_apex"][1] + dy, col, row)
                for leg in ("leg_a", "leg_b"):
                    q = self._to_page(d[leg][0] + dx, d[leg][1] + dy, col, row)
                    c.line(*low, *q)
        # notches: small filled triangles pointing outward from the piece centre
        cx = sum(q[0] for q in p["outline"]) / len(p["outline"])
        cy = sum(q[1] for q in p["outline"]) / len(p["outline"])
        c.setFillColor(colors.black)
        c.setStrokeColor(colors.black)
        for nt in p.get("notches") or []:
            nx, ny = nt["point"]
            vx, vy = nx - cx, ny - cy
            L = math.hypot(vx, vy) or 1.0
            ux, uy = vx / L, vy / L
            reach = 0.6 + (p.get("seam_allowance_cm") or 1.0)
            tip = self._to_page(nx + ux * min(reach, 1.0) + dx, ny + uy * min(reach, 1.0) + dy, col, row)
            base_l = self._to_page(nx - uy * 0.25 + dx, ny + ux * 0.25 + dy, col, row)
            base_r = self._to_page(nx + uy * 0.25 + dx, ny - ux * 0.25 + dy, col, row)
            tri = c.beginPath()
            tri.moveTo(*base_l)
            tri.lineTo(*tip)
            tri.lineTo(*base_r)
            tri.close()
            c.drawPath(tri, fill=1, stroke=1)
        # label: beside the grainline, moved so that the whole label lies inside ONE tile (never cut by a page edge)
        lx_, ly_ = (gl["start"][0] + gl["end"][0]) / 2 + dx + 0.5, (gl["start"][1] + gl["end"][1]) / 2 + dy
        tc, tr = int(lx_ // STEP_X), int(ly_ // STEP_Y)
        lx_ = min(max(lx_, tc * STEP_X + OVERLAP_CM + 0.3), tc * STEP_X + TILE_W_CM - OVERLAP_CM - 6.8)
        ly_ = min(max(ly_, tr * STEP_Y + OVERLAP_CM + 0.6), tr * STEP_Y + TILE_H_CM - OVERLAP_CM - 2.6)
        gmid = self._to_page(lx_, ly_, col, row)
        c.setFillColor(colors.black)
        box = p.get("cut_bounding_box") or p.get("bounding_box") or {}
        lines = [p["name"].upper(), f"CUT {p['cut_count']}" + ("  ON FOLD" if p["cut_on_fold"] else ""),
                 f"SA {p.get('seam_allowance_cm')} cm",
                 f"{box.get('width_cm', 0):.1f} x {box.get('height_cm', 0):.1f} cm incl. SA",
                 f"GRAIN = selvedge   |   {self.ctx.get('pattern_id') or ''}".strip(" |")]
        if p.get("side"):
            lines.insert(1, f"{p['side'].upper()} - {p.get('units', 'cm')}")
        for k, ln in enumerate(lines):
            c.setFont("Helvetica-Bold" if k == 0 else "Helvetica", 8 if k == 0 else 7)
            c.drawString(gmid[0], gmid[1] - k * 0.38 * CM, ln)
        # key points (small circles with a code)
        c.setFont("Helvetica", 6)
        for key, code in KEY_POINTS.items():
            q = (p.get("points") or {}).get(key)
            if not q:
                continue
            pp = self._to_page(q[0] + dx, q[1] + dy, col, row)
            c.setStrokeColor(colors.HexColor("#2E7D32"))
            c.setLineWidth(0.5)
            c.circle(pp[0], pp[1], 0.08 * CM, stroke=1, fill=0)
            c.setFillColor(colors.HexColor("#2E7D32"))
            c.drawString(pp[0] + 0.15 * CM, pp[1] + 0.1 * CM, code)
        c.setFillColor(colors.black)

    def _crop_marks(self, col, row):
        c = self.c
        c.setStrokeColor(colors.black)
        c.setLineWidth(0.5)
        x0, y0 = MARGIN_CM * CM, MARGIN_CM * CM
        x1, y1 = PAGE_W - MARGIN_CM * CM, PAGE_H - MARGIN_CM * CM
        m = 0.5 * CM
        for (x, y) in ((x0, y0), (x1, y0), (x0, y1), (x1, y1)):
            c.line(x - m, y, x + m, y)
            c.line(x, y - m, x, y + m)
            c.circle(x, y, 2, stroke=1, fill=0)
        # overlap guides (dashed) where the neighbouring tile starts
        c.setDash(2, 3)
        c.setStrokeColor(GRAY)
        if (col + 1, row) in self.tiles:
            c.line(x1 - OVERLAP_CM * CM, y0, x1 - OVERLAP_CM * CM, y1)
        if col > 0 and (col - 1, row) in self.tiles:
            c.line(x0 + OVERLAP_CM * CM, y0, x0 + OVERLAP_CM * CM, y1)
        if (col, row + 1) in self.tiles:
            c.line(x0, y0 + OVERLAP_CM * CM, x1, y0 + OVERLAP_CM * CM)
        if row > 0 and (col, row - 1) in self.tiles:
            c.line(x0, y1 - OVERLAP_CM * CM, x1, y1 - OVERLAP_CM * CM)
        c.setDash()
        # tile label + neighbours
        c.setFillColor(BLUE)
        c.setFont("Helvetica-Bold", 22)
        c.drawString(x0 + 0.4 * CM, y1 - 1.3 * CM, tile_label(col, row))
        c.setFont("Helvetica", 7)
        c.setFillColor(GRAY)
        hints = []
        if (col + 1, row) in self.tiles:
            hints.append(f"right -> {tile_label(col + 1, row)}")
        if (col, row + 1) in self.tiles:
            hints.append(f"below -> {tile_label(col, row + 1)}")
        if col > 0 and (col - 1, row) in self.tiles:
            hints.append(f"left <- {tile_label(col - 1, row)}")
        if row > 0 and (col, row - 1) in self.tiles:
            hints.append(f"above <- {tile_label(col, row - 1)}")
        c.drawString(x0 + 0.4 * CM, y1 - 1.8 * CM, "   ".join(hints) or "single tile")
        c.drawRightString(x1 - 0.4 * CM, y1 - 0.9 * CM, f"1:1  |  {OVERLAP_CM:g} cm overlap  |  Actual size")

    def _page_tile(self, col, row):
        c = self.c
        self._on_pattern_page = True
        c.saveState()
        clip = c.beginPath()
        clip.rect(MARGIN_CM * CM, MARGIN_CM * CM, TILE_W_CM * CM, TILE_H_CM * CM)
        c.clipPath(clip, stroke=0, fill=0)
        for pl in self.placements:
            if pl.get("calibration"):
                px, py = self._to_page(pl["x"], pl["y"] + CALIBRATION_CM, col, row)
                self._calibration_square(px, py)
            else:
                self._draw_piece(pl, col, row)
        c.restoreState()
        self._crop_marks(col, row)
        self._footer()
        c.showPage()

    def generate(self):
        for _, draw in self.plan:
            self._on_pattern_page = False
            draw()
        self.c.save()
        self.info = {"pages": self.page_no, "tiles": len(self.tiles) if self.part in ("all", "pattern") else 0,
                     "overview_scale": getattr(self, "overview_scale", None),
                     "grid": (self.cols, self.rows), "part": self.part, "report_pages": self.front_pages,
                     "sheet_cm": (round(self.sheet_w, 2), round(self.sheet_h, 2))}
        return self.out
