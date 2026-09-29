"""
Printable sewing-pattern PDF (ReportLab).

Pages
    1        Cover: design, status, PRINTING INSTRUCTIONS (100 % / Actual Size) and a 5 cm calibration square
    2        Measurements, design summary, fabric estimate, piece list, seam allowances
    3        Fabric cutting layout (from the geometry-aware nesting; drawn to fit the page, NOT to scale)
    4..N     The pattern at TRUE 1:1 SCALE, tiled onto A4 sheets with an overlap, corner crop marks,
             tile labels (e.g. "A1"), neighbour hints and page numbers. Blank tiles are omitted.

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
                 design_spec=None, fabric_name=None, garment_title=None):
        self.pattern = pattern_data
        self.nesting = nesting_data or {}
        self.meas = measurements or {}
        self.features = features or {}
        self.design_spec = design_spec or {}
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
        self.total_pages = 3 + len(self.tiles)
        self.page_no = 0
        self.info = {}

    # ── helpers ─────────────────────────────────────────────────────────────
    def _footer(self):
        c = self.c
        self.page_no += 1
        c.setFont("Helvetica", 7.5)
        c.setFillColor(GRAY)
        c.drawCentredString(PAGE_W / 2, 0.45 * CM, f"Page {self.page_no} of {self.total_pages}   |   "
                            "Print at 100% - Actual Size   |   Prototype pattern - check fit with a muslin before cutting")

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

    # ── page 1 ──────────────────────────────────────────────────────────────
    def _page_cover(self):
        c = self.c
        self._title(self.title, "Printable sewing pattern - 1:1 scale, tiled A4")
        attrs = self.pattern.get("design_attributes", {})
        y = PAGE_H - 4.2 * CM
        for label, value in (("Garment", attrs.get("garment_type")), ("Neckline", attrs.get("neckline_type")),
                             ("Sleeve length", attrs.get("sleeve_length")), ("Sleeve style", attrs.get("sleeve_style")),
                             ("Construction block", self.pattern.get("drafting_block", {}).get("block_label")),
                             ("Fabric", self.fabric_name), ("Generated", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"))):
            self._text(2 * CM, y, f"{label}:", 9, True)
            self._text(6 * CM, y, str(value if value is not None else "-").replace("-", " ").title()
                       if label in ("Garment", "Neckline", "Sleeve length", "Sleeve style") else str(value or "-"), 9)
            y -= 0.55 * CM

        # printing instructions
        c.setFillColor(LIGHT)
        c.setStrokeColor(RED)
        c.setLineWidth(1.5)
        box_top = y - 0.3 * CM
        c.rect(2 * CM, box_top - 7.6 * CM, PAGE_W - 4 * CM, 7.6 * CM, fill=1, stroke=1)
        self._text(2.4 * CM, box_top - 0.7 * CM, "PRINTING INSTRUCTIONS  -  PRINT AT 100 % (ACTUAL SIZE)", 11, True, RED)
        yy = box_top - 1.4 * CM
        for i, line in enumerate(INSTRUCTIONS, 1):
            words, cur, lines = line.split(), "", []
            for w in words:
                if c.stringWidth(cur + " " + w, "Helvetica", 8.5) > PAGE_W - 5.4 * CM:
                    lines.append(cur)
                    cur = w
                else:
                    cur = (cur + " " + w).strip()
            lines.append(cur)
            for j, ln in enumerate(lines):
                self._text(2.4 * CM if j == 0 else 3.0 * CM, yy, (f"{i}. " if j == 0 else "") + ln, 8.5)
                yy -= 0.42 * CM
            yy -= 0.05 * CM
        self._calibration_square(2.4 * CM, 3.2 * CM)
        self._text(8.6 * CM, 6.0 * CM, f"Pattern sheet: {self.sheet_w:.0f} x {self.sheet_h:.0f} cm", 9, True)
        self._text(8.6 * CM, 5.4 * CM, f"Printed on {len(self.tiles)} A4 page(s), tiles {self.cols} x {self.rows} grid", 9)
        self._text(8.6 * CM, 4.8 * CM, "Status: mathematically generated, geometry-validated PROTOTYPE.", 8.5, False, RED)
        self._text(8.6 * CM, 4.3 * CM, "Not fit-tested. Make a muslin (toile) before cutting good fabric.", 8.5, False, RED)
        self._footer()
        c.showPage()

    # ── page 2 ──────────────────────────────────────────────────────────────
    def _page_summary(self):
        c = self.c
        self._title("Measurements, fabric and pieces")
        y = PAGE_H - 4.0 * CM
        self._text(2 * CM, y, "Body measurements used (cm)", 11, True, BLUE)
        y -= 0.6 * CM
        names = [("bust_cm", "Bust"), ("waist_cm", "Waist"), ("hip_cm", "Hip"), ("height_cm", "Height"),
                 ("neck_cm", "Neck"), ("shoulder_cm", "Shoulder"), ("across_back_cm", "Across back"),
                 ("back_waist_length_cm", "Back waist length"), ("armhole_depth_cm", "Armhole depth"),
                 ("garment_length_cm", "Garment length"), ("bicep_cm", "Bicep"), ("sleeve_cm", "Sleeve (full arm)"),
                 ("wrist_cm", "Wrist")]
        for i, (k, label) in enumerate(names):
            col, row = i % 2, i // 2
            v = self.meas.get(k)
            self._text(2 * CM + col * 8.5 * CM, y - row * 0.5 * CM, f"{label}: {_fmt(v)} cm" if v is not None else f"{label}: -", 9)
        y -= (len(names) // 2 + 1) * 0.5 * CM + 0.3 * CM
        eased = self.pattern.get("measurements_used", {}).get("ease_profile", {})
        self._text(2 * CM, y, f"Fabric type: {self.meas.get('fabric_type', '-')}   |   Fit: {self.meas.get('fit_preference', '-')}   |   "
                              f"Ease (bust/waist/hip): +{eased.get('bust_cm', '-')}/+{eased.get('waist_cm', '-')}/+{eased.get('hip_cm', '-')} cm", 9)
        y -= 0.9 * CM

        n = self.nesting
        self._text(2 * CM, y, "Fabric estimate", 11, True, BLUE)
        y -= 0.6 * CM
        if n:
            rows = [f"Fabric: {self.fabric_name or '-'}   |   width {n.get('fabric_width_cm', '-'):g} cm   |   cutting: {n.get('cutting_method_simple', '-')}",
                    f"Layout length {n.get('fabric_length_cm', '-')} cm   |   recommended purchase {n.get('purchasing_recommended_m', '-')} m "
                    f"({n.get('yardage_yards', '-')} yd)",
                    f"Utilisation {n.get('utilisation_percent', '-')} %   |   waste {n.get('waste_percent', '-')} %",
                    "Purchase allowance = layout + 3 % shrinkage + 10 cm cutting margin, rounded up to 10 cm."]
        else:
            rows = ["Fabric estimate not available."]
        for r in rows:
            self._text(2 * CM, y, r, 9)
            y -= 0.5 * CM
        y -= 0.5 * CM

        self._text(2 * CM, y, "Pattern pieces", 11, True, BLUE)
        y -= 0.6 * CM
        heads = ["Piece", "Cut", "On fold", "Seam allowance", "Size with SA (cm)"]
        xs = [2, 8.2, 10.2, 12.4, 16.0]
        for h, x in zip(heads, xs):
            self._text(x * CM, y, h, 8.5, True)
        y -= 0.5 * CM
        for p in self.pieces:
            box = p["cut_bounding_box"] or p["bounding_box"]
            sa = p.get("seam_allowances") or {}
            sa_txt = ", ".join(f"{k} {v:g}" for k, v in sa.items()) if sa else f"{p.get('seam_allowance_cm')}"
            for t, x in zip([p["name"], str(p["cut_count"]), "yes" if p["cut_on_fold"] else "no", sa_txt[:34],
                             f"{box['width_cm']:.1f} x {box['height_cm']:.1f}"], xs):
                self._text(x * CM, y, t, 8)
            y -= 0.45 * CM
        y -= 0.4 * CM
        self._text(2 * CM, y, "Sewing notes", 11, True, BLUE)
        y -= 0.55 * CM
        for note in self.pattern.get("construction_notes", [])[:8]:
            txt = note if len(note) < 118 else note[:115] + "..."
            self._text(2 * CM, y, "- " + txt, 7.5)
            y -= 0.4 * CM
        self._footer()
        c.showPage()

    # ── page 3 : cutting layout ────────────────────────────────────────────
    def _page_layout(self):
        c = self.c
        self._title("Fabric cutting layout", "Drawn to fit the page - NOT to scale (see the tiled pages for 1:1)")
        n = self.nesting
        placed = n.get("placed_pieces", []) if n else []
        if not placed:
            self._text(2 * CM, PAGE_H - 4.5 * CM, "No layout available.", 10)
        else:
            uw, length = n["usable_width_cm"], n["fabric_length_cm"]
            avail_w, avail_h = PAGE_W - 5 * CM, PAGE_H - 9 * CM
            scale = min(avail_w / uw, avail_h / max(length, 1))
            ox, oy = 2.5 * CM, PAGE_H - 4.2 * CM
            c.setStrokeColor(colors.black)
            c.setLineWidth(1)
            c.rect(ox, oy - length * scale, uw * scale, length * scale, fill=0)
            if n["cutting_mode"] == "folded":
                c.setLineWidth(2.5)
                c.line(ox, oy, ox, oy - length * scale)
                self._text(ox + 0.2 * CM, oy + 0.25 * CM, "FOLD", 8, True)
            for i, p in enumerate(placed):
                pts = [(ox + x * scale, oy - y * scale) for x, y in p["polygon_coordinates"]]
                path = c.beginPath()
                path.moveTo(*pts[0])
                for q in pts[1:]:
                    path.lineTo(*q)
                path.close()
                c.setFillColor(colors.Color(0.85, 0.9, 0.97))
                c.setStrokeColor(BLUE)
                c.setLineWidth(0.8)
                c.drawPath(path, fill=1, stroke=1)
                cx = sum(q[0] for q in pts) / len(pts)
                cy = sum(q[1] for q in pts) / len(pts)
                c.setFillColor(colors.black)
                c.setFont("Helvetica", 6.5)
                c.drawCentredString(cx, cy, p["name"])
            self._text(2 * CM, 2.8 * CM,
                       f"Fabric width {n['fabric_width_cm']:g} cm ({n['cutting_method_simple']}); layout length {n['fabric_length_cm']} cm; "
                       f"purchase {n['purchasing_recommended_m']} m; utilisation {n['utilisation_percent']} %", 8.5)
            self._text(2 * CM, 2.3 * CM, "Method: " + n.get("method", ""), 7)
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
        lines = [p["name"].upper(), f"CUT {p['cut_count']}" + ("  ON FOLD" if p["cut_on_fold"] else ""),
                 f"SA {(p.get('seam_allowances') or {}).get('seam', p.get('seam_allowance_cm'))} cm"]
        if p.get("side"):
            lines.insert(1, f"{p['side'].upper()} - {p.get('units', 'cm')}")
        for k, ln in enumerate(lines):
            c.setFont("Helvetica-Bold" if k == 0 else "Helvetica", 8 if k == 0 else 7)
            c.drawString(gmid[0], gmid[1] - k * 0.38 * CM, ln)

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
        self._page_summary()
        self._page_layout()
        for col, row in self.tiles:
            self._page_tile(col, row)
        self.c.save()
        self.info = {"pages": self.page_no, "tiles": len(self.tiles), "grid": (self.cols, self.rows),
                     "sheet_cm": (round(self.sheet_w, 2), round(self.sheet_h, 2))}
        return self.out
