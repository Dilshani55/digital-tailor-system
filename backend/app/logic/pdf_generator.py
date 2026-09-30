"""
Printable sewing-pattern PDF (ReportLab).

Pages (everything is drawn from STORED data: the validated pieces, the measurement snapshot and the saved
estimates - the pattern is never re-drafted here)
    1        Project summary: customer, design/project name, pattern ID, dates, the customer's design image,
             confirmed features with the AI prediction/confidence and any user correction, fabric, fit/ease,
             fabric requirement summary
    2        PRINTING INSTRUCTIONS (100 % / Actual Size) and a 5 cm calibration square
    3        Measurements (used cm values and what was entered) + derived values / assumptions, each marked
    4        Piece list with seam allowances and cut sizes; sewing notes
    5        Fabric requirement for 36", 45" and 60" with the layout for each (drawn to fit, NOT to scale)
    6..N     The pattern at TRUE 1:1 SCALE, tiled onto A4 sheets with an overlap, corner crop marks,
             tile labels (e.g. "A1"), neighbour hints and page numbers. Blank tiles are omitted.
Footer on every page: page x of N, pattern ID, customer, units/scale, creation timestamp.

Every piece shows: cutting line (solid), seam line (dashed), grainline, fold line, darts, notches,
name, cut quantity, "cut on fold" and the seam allowance. All coordinates are centimetres and are
converted with 1 cm = 72/2.54 pt, so a printer set to "Actual size" reproduces real dimensions.
"""

import math
from datetime import datetime, timezone

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

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
              "BUST_POINT": "BP (derived)", "CROWN": "CROWN", "UNDERARM_LEFT": "UA", "UNDERARM_RIGHT": "UA"}


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
                 design_spec=None, fabric_name=None, garment_title=None, context=None):
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
        self.c.setSubject("Printable 1:1 sewing pattern - tiled A4 - print at Actual Size (100%)")
        self.c.setKeywords("sewing pattern, 1:1, A4 tiled, actual size")
        self.placements, self.sheet_w, self.sheet_h = layout_sheet(self.pieces)
        self.cols, self.rows = tile_grid(self.sheet_w, self.sheet_h)
        self.tiles = [(cx, ry) for ry in range(self.rows) for cx in range(self.cols) if self._tile_has_content(cx, ry)]
        self.front_pages = 5
        self.total_pages = self.front_pages + len(self.tiles)
        self.page_no = 0
        self.info = {}

    # ── helpers ─────────────────────────────────────────────────────────────
    def _footer(self):
        c = self.c
        self.page_no += 1
        c.setFont("Helvetica", 7.5)
        c.setFillColor(GRAY)
        parts = [f"Page {self.page_no} of {self.total_pages}", f"Pattern {self.ctx.get('pattern_id') or '-'}",
                 f"Customer {self.ctx.get('customer_name') or '-'}", "Units cm - scale 1:1 - print at 100% Actual size",
                 f"Created {self.created_at}"]
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
        self._title(self.title, "Printable sewing pattern - 1:1 scale, tiled A4")
        y = PAGE_H - 4.0 * CM
        y = self._kv(2 * CM, y, "Customer", ctx.get("customer_name"))
        y = self._kv(2 * CM, y, "Contact / reference", ctx.get("customer_contact"))
        y = self._kv(2 * CM, y, "Design / project", ctx.get("project_name"))
        y = self._kv(2 * CM, y, "Pattern ID", ctx.get("pattern_id"))
        y = self._kv(2 * CM, y, "Pattern generated", ctx.get("generated_at"))
        y = self._kv(2 * CM, y, "Fabric", self.fabric_name)
        ease = (self.pattern.get("measurements_used") or {}).get("ease_profile") or {}
        fit = ease.get("fit_preference") or self.meas.get("fit_preference")
        y = self._kv(2 * CM, y, "Fit / ease", f"{fit or '-'} fit; bust +{ease.get('bust_cm', '-')}, waist "
                                                 f"+{ease.get('waist_cm', '-')}, hip +{ease.get('hip_cm', '-')} cm" if ease else fit)
        y = self._kv(2 * CM, y, "Drafting block", (self.pattern.get("drafting_block") or {}).get("block_label"))

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
                       f"  (layout {r['base_layout_length_cm']} cm, utilisation {r['utilisation_percent']} %)"
                       if r.get("fits") else f"{r['fabric_width_in']}\" ({r['fabric_width_cm']} cm): does not fit - {r.get('error', '')}")
                self._text(2.2 * CM, y, ("> " if r.get("selected") else "  ") + txt, 8.5, bool(r.get("selected")))
                y -= 0.45 * CM
        self._text(2 * CM, 2.0 * CM, "Status: mathematically generated, geometry-validated PROTOTYPE - not fit-tested. "
                                     "Make a muslin (toile) before cutting good fabric.", 8, False, RED)
        self._footer()
        c.showPage()

    # ── page 2: printing ────────────────────────────────────────────────────
    def _page_print(self):
        c = self.c
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

    # ── page 3: measurements ────────────────────────────────────────────────
    def _page_measurements(self):
        self._title("Measurements", "All values in centimetres (cm); the pattern is drafted from the canonical cm values")
        y = PAGE_H - 4.0 * CM
        names = [("bust_cm", "Bust"), ("waist_cm", "Waist"), ("hip_cm", "Hip"), ("height_cm", "Height"),
                 ("neck_cm", "Neck"), ("shoulder_cm", "Shoulder length"), ("across_back_cm", "Across-back width"),
                 ("back_waist_length_cm", "Back waist length"), ("armhole_depth_cm", "Armhole depth"),
                 ("garment_length_cm", "Garment length"), ("bicep_cm", "Bicep"), ("sleeve_cm", "Sleeve (full arm)"),
                 ("wrist_cm", "Wrist")]
        entered = self.ctx.get("original_values") or {}
        for h, xcm in zip(("Measurement", "Used (cm)", "As entered", "Source"), (2.0, 7.2, 10.2, 13.6)):
            self._text(xcm * CM, y, h, 8.5, True)
        y -= 0.45 * CM
        for key, label in names:
            v = self.meas.get(key)
            e = entered.get(key) or {}
            as_entered = f"{e['value']:g} {e.get('unit', '')}".strip() if isinstance(e.get("value"), (int, float)) else "-"
            for txt, xcm in zip((label, _fmt(v), as_entered, "measured" if v is not None else "not measured"),
                                (2.0, 7.2, 10.2, 13.6)):
                self._text(xcm * CM, y, txt, 8.5)
            y -= 0.42 * CM
        y -= 0.4 * CM
        self._text(2 * CM, y, "Derived drafting values (from the measurements) and project assumptions", 11, True, BLUE)
        y -= 0.5 * CM
        self._text(2 * CM, y, "DERIVED = calculated from the measurements; ASSUMPTION = a documented project constant "
                              "(e.g. ease, bust-point position) - not measured on the body.", 7.5, False, GRAY)
        y -= 0.5 * CM
        for row in (self.ctx.get("drafting_values") or [])[:28]:
            status = "ASSUMPTION" if row.get("status") == "project_assumption" else "DERIVED"
            self._text(2 * CM, y, str(row.get("name", "")).replace("_", " "), 7.8)
            self._text(7.2 * CM, y, _fmt(row.get("value_cm"), 2) + " cm", 7.8)
            self._text(9.6 * CM, y, str(row.get("formula", ""))[:52], 7.3)
            self._text(17.0 * CM, y, status, 7.3, True, RED if status == "ASSUMPTION" else BLUE)
            y -= 0.36 * CM
            if y < 2.2 * CM:
                break
        self._footer()
        self.c.showPage()

    # ── page 4: pieces and sewing notes ─────────────────────────────────────
    def _page_pieces(self):
        self._title("Pattern pieces and sewing notes")
        y = PAGE_H - 4.0 * CM
        heads = ["Piece", "Cut", "On fold", "Seam / neck / hem SA (cm)", "Size with SA (cm)"]
        xs = [2, 7.4, 9.0, 11.2, 16.2]
        for h, x in zip(heads, xs):
            self._text(x * CM, y, h, 8.5, True)
        y -= 0.5 * CM
        for p in self.pieces:
            box = p.get("cut_bounding_box") or p.get("bounding_box") or {}
            sa = p.get("seam_allowances") or {}
            if sa and all(k in sa for k in ("seam", "neckline", "hem")) and p.get("piece_type") not in ("neckband", "armhole_facing", "sleeve_band"):
                sa_txt = f"{sa['seam']:g} / {sa['neckline']:g} / {sa['hem']:g}"
            else:
                sa_txt = f"{sa.get('strip', p.get('seam_allowance_cm'))} (all edges)" if sa else f"{p.get('seam_allowance_cm')}"
            for t, x in zip([p["name"], str(p["cut_count"]), "yes" if p["cut_on_fold"] else "no", sa_txt[:34],
                             f"{box.get('width_cm', 0):.1f} x {box.get('height_cm', 0):.1f}"], xs):
                self._text(x * CM, y, t, 8)
            y -= 0.45 * CM
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
        heads = ["Fabric width", "Base layout length", "Allowance", "Recommended purchase", "Utilisation", "Waste"]
        xs = [2.0, 5.6, 9.2, 11.6, 15.4, 17.6]
        for h, x in zip(heads, xs):
            self._text(x * CM, y, h, 8, True)
        y -= 0.45 * CM
        for r in rows:
            sel = bool(r.get("selected"))
            self._text(xs[0] * CM, y, f"{r['fabric_width_in']}\" / {r['fabric_width_cm']} cm" + ("  (selected)" if sel else ""), 8, sel)
            if r.get("fits"):
                vals = [f"{r['base_layout_length_cm']} cm", f"{r['purchasing_allowance_cm']} cm", f"{r['recommended_purchase_m']} m",
                        f"{r['utilisation_percent']} %", f"{r['waste_percent']} %"]
                for t, x in zip(vals, xs[1:]):
                    self._text(x * CM, y, t, 8, sel)
            else:
                self._text(xs[1] * CM, y, f"Does not fit: {r.get('error', '')}"[:90], 8, False, RED)
            y -= 0.45 * CM
        if not rows and self.nesting:                    # older pattern: only the saved single estimate exists
            n = self.nesting
            self._text(2 * CM, y, f"Fabric width {n['fabric_width_cm']:g} cm: layout {n['fabric_length_cm']} cm, purchase "
                                  f"{n['purchasing_recommended_m']} m, utilisation {n['utilisation_percent']} %", 8)
            y -= 0.45 * CM
            layouts = {n["fabric_width_cm"]: n}
        y -= 0.4 * CM
        y = self._para(2 * CM, y, "Purchase = layout length + 3 % shrinkage + 10 cm cutting margin, rounded up to 10 cm. "
                                  "Heuristic (Bottom-Left-Fill) layout: feasible and checked, not proven minimal.",
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
            reach = 0.6 + (p.get("seam_allowances") or {}).get("seam", 1.0)
            tip = self._to_page(nx + ux * min(reach, 1.0) + dx, ny + uy * min(reach, 1.0) + dy, col, row)
            base_l = self._to_page(nx - uy * 0.25 + dx, ny + ux * 0.25 + dy, col, row)
            base_r = self._to_page(nx + uy * 0.25 + dx, ny - ux * 0.25 + dy, col, row)
            tri = c.beginPath()
            tri.moveTo(*base_l)
            tri.lineTo(*tip)
            tri.lineTo(*base_r)
            tri.close()
            c.drawPath(tri, fill=1, stroke=1)
        # label
        gmid = self._to_page((gl["start"][0] + gl["end"][0]) / 2 + dx + 0.5, (gl["start"][1] + gl["end"][1]) / 2 + dy, col, row)
        c.setFillColor(colors.black)
        box = p.get("cut_bounding_box") or p.get("bounding_box") or {}
        lines = [p["name"].upper(), f"CUT {p['cut_count']}" + ("  ON FOLD" if p["cut_on_fold"] else ""),
                 f"SA {(p.get('seam_allowances') or {}).get('seam', p.get('seam_allowance_cm'))} cm",
                 f"{box.get('width_cm', 0):.1f} x {box.get('height_cm', 0):.1f} cm incl. SA",
                 f"GRAIN = selvedge   |   {self.ctx.get('pattern_id') or ''}".strip(" |")]
        if p.get("side"):
            lines.insert(1, f"{p['side'].upper()} - {p.get('units', 'cm')}")
        for k, ln in enumerate(lines):
            c.setFont("Helvetica-Bold" if k == 0 else "Helvetica", 8 if k == 0 else 7)
            c.drawString(gmid[0], gmid[1] - k * 0.38 * CM, ln)
        # key points (small circles with a code); the bust point is an assumption and is marked as derived
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
        self._page_cover()
        self._page_print()
        self._page_measurements()
        self._page_pieces()
        self._page_layout()
        for col, row in self.tiles:
            self._page_tile(col, row)
        self.c.save()
        self.info = {"pages": self.page_no, "tiles": len(self.tiles), "grid": (self.cols, self.rows),
                     "sheet_cm": (round(self.sheet_w, 2), round(self.sheet_h, 2))}
        return self.out
