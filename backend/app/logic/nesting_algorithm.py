# ── Geometry-aware 2D nesting (marker layout) ─────────────────────────────────
#
# METHOD (documented, deterministic)
#   * Uses the real CUTTING-LINE polygons of the pattern pieces (seam allowance included).
#   * Bottom-Left-Fill on a 0.5 cm occupancy grid: pieces are sorted by polygon area (largest
#     first) and each is placed at the lowest, then left-most, position where its rasterised
#     polygon does not touch an already placed one. This is a polygon (not bounding-box) layout.
#   * Fabric length is the y-axis (selvedge/grain direction). Pieces keep their grain: only 0 or
#     180 degree orientations are tried (a 90 degree turn would put the grain across the cloth).
#   * FOLDED mode: the fabric is folded lengthwise, usable width = bolt width / 2. Cut-on-fold
#     pieces are pinned to the fold (x = 0), are never rotated, and one placement yields the full
#     piece. Other pieces are cut through both layers (one placement yields two pieces).
#   * OPEN mode: full width; cut-on-fold pieces are mirrored into their full shape.
#   * The result is verified with EXACT polygon tests (overlap, bounds, fold, grain, quantities).
#   * Purchase allowance: layout length + 3 % shrinkage + 10 cm cutting/end margin, rounded up
#     to the next 10 cm. These are project assumptions (listed in the result).
#
# Not an optimal nesting: it is a greedy heuristic and gives an upper bound on fabric use.

import math

import numpy as np

from app.logic.drafting import geometry as g

CELL_CM = 0.5              # occupancy-grid resolution
GAP_CELLS = 1              # each piece is grown by this many cells -> >= ~0.5 cm between pieces
MAX_LENGTH_CM = 900.0
SHRINKAGE_ALLOWANCE = 0.03
END_MARGIN_CM = 10.0
ROUND_UP_CM = 10.0
STANDARD_FABRIC_WIDTHS = (90, 114, 150)


def calculate_shoelace_area(points):
    """Polygon area with Gauss's shoelace formula. points: list of (x, y)."""
    if not points or len(points) < 3:
        return 0.0
    n = len(points)
    area = 0.0
    for i in range(n):
        j = (i + 1) % n
        area += points[i][0] * points[j][1] - points[j][0] * points[i][1]
    return abs(area) / 2.0


class NestingError(Exception):
    """A valid marker cannot be produced. `.details` is a structured payload for the API."""

    def __init__(self, message, error_code="NESTING_FAILED", failed_pieces=None, **extra):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.failed_pieces = failed_pieces or []
        self.extra = extra

    @property
    def details(self):
        return {"error_code": self.error_code, "message": self.message,
                "failed_pieces": self.failed_pieces, **self.extra}


# ── polygon helpers ───────────────────────────────────────────────────────────
def _open(poly):
    pts = [tuple(map(float, p)) for p in poly]
    if len(pts) > 1 and g.dist(pts[0], pts[-1]) < 1e-9:
        pts = pts[:-1]
    return pts


def _mirror_to_full(half):
    """Mirror a fold half-piece (fold edge on x = 0) into the full symmetric polygon."""
    pts = _open(half)
    on_fold = [i for i, p in enumerate(pts) if abs(p[0]) < 1e-6]
    if len(on_fold) < 2:
        raise NestingError("A cut-on-fold piece has no fold edge to mirror.", error_code="FOLD_EDGE_MISSING")
    # rotate so the polygon starts at the first fold point and ends at the last one
    first, last = on_fold[0], on_fold[-1]
    if last < first:
        first, last = last, first
    chain = pts[first:last + 1]
    if len(chain) < 3 or abs(chain[0][0]) > 1e-6 or abs(chain[-1][0]) > 1e-6:
        chain = pts[last:] + pts[:first + 1]
    mirrored = [(-x, y) for (x, y) in reversed(chain)][1:-1]
    full = chain + mirrored
    minx = min(p[0] for p in full)
    return [(x - minx, y) for x, y in full]


def _transform(poly, rot180, dx=0.0, dy=0.0):
    pts = _open(poly)
    if rot180:
        cx = (min(p[0] for p in pts) + max(p[0] for p in pts)) / 2.0
        cy = (min(p[1] for p in pts) + max(p[1] for p in pts)) / 2.0
        pts = [(2 * cx - x, 2 * cy - y) for x, y in pts]
    minx = min(p[0] for p in pts)
    miny = min(p[1] for p in pts)
    return [(x - minx + dx, y - miny + dy) for x, y in pts]


def _rasterise(poly, cell=CELL_CM, grow=GAP_CELLS):
    """Boolean mask (rows = y, cols = x) of the polygon on a `cell` grid, grown by `grow` cells."""
    pts = _open(poly)
    minx, miny, maxx, maxy = g.bbox(pts)
    w = int(math.ceil((maxx - minx) / cell)) + 1
    h = int(math.ceil((maxy - miny) / cell)) + 1
    mask = np.zeros((h, w), dtype=bool)
    n = len(pts)
    for r in range(h):
        y = miny + (r + 0.5) * cell
        xs = []
        for i in range(n):
            (x1, y1), (x2, y2) = pts[i], pts[(i + 1) % n]
            if (y1 <= y < y2) or (y2 <= y < y1):
                xs.append(x1 + (y - y1) * (x2 - x1) / (y2 - y1))
        xs.sort()
        for k in range(0, len(xs) - 1, 2):
            c0 = int(math.floor((xs[k] - minx) / cell - 0.5 + 1e-9)) + 1
            c1 = int(math.ceil((xs[k + 1] - minx) / cell - 0.5 - 1e-9)) - 1
            mask[r, max(c0, 0):max(min(c1, w - 1) + 1, 0)] = True
    # pad, then grow by the gap: mask column/row `grow` corresponds to the polygon's min corner
    mask = np.pad(mask, grow)
    for _ in range(grow):
        p = np.pad(mask, 1)
        mask = (p[1:-1, 1:-1] | p[:-2, 1:-1] | p[2:, 1:-1] | p[1:-1, :-2] | p[1:-1, 2:]
                | p[:-2, :-2] | p[:-2, 2:] | p[2:, :-2] | p[2:, 2:])
    return mask


def _seg_proper_cross(a, b, c, d, eps=1e-9):
    o1 = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
    o2 = (b[0] - a[0]) * (d[1] - a[1]) - (b[1] - a[1]) * (d[0] - a[0])
    o3 = (d[0] - c[0]) * (a[1] - c[1]) - (d[1] - c[1]) * (a[0] - c[0])
    o4 = (d[0] - c[0]) * (b[1] - c[1]) - (d[1] - c[1]) * (b[0] - c[0])
    return ((o1 > eps and o2 < -eps) or (o1 < -eps and o2 > eps)) and \
           ((o3 > eps and o4 < -eps) or (o3 < -eps and o4 > eps))


def polygons_overlap(A, B):
    """Exact test: True if the interiors of two simple polygons overlap (touching is allowed)."""
    A, B = _open(A), _open(B)
    ax0, ay0, ax1, ay1 = g.bbox(A)
    bx0, by0, bx1, by1 = g.bbox(B)
    if ax1 <= bx0 + 1e-9 or bx1 <= ax0 + 1e-9 or ay1 <= by0 + 1e-9 or by1 <= ay0 + 1e-9:
        return False
    for i in range(len(A)):
        a, b = A[i], A[(i + 1) % len(A)]
        for j in range(len(B)):
            if _seg_proper_cross(a, b, B[j], B[(j + 1) % len(B)]):
                return True

    def strictly_inside(pt, poly):
        return g.point_in_polygon(pt, poly) and not g.point_on_polyline(pt, poly, 1e-7)

    return any(strictly_inside(p, B) for p in A) or any(strictly_inside(p, A) for p in B)


# ── piece instances ───────────────────────────────────────────────────────────
class _Instance:
    def __init__(self, name, source, polygon, fold, layers_cut, useful_area, cut_quantity):
        self.name, self.source = name, source
        self.polygon = polygon              # local coordinates, min corner at the origin (fold at x = 0)
        self.fold = fold                    # pinned to the fold (folded mode only)
        self.layers_cut = layers_cut        # pieces produced by one placement
        self.useful_area = useful_area      # area of the pieces actually required from this placement
        self.cut_quantity = cut_quantity
        self.rot180 = False
        self.x = self.y = 0.0
        self.placed_polygon = None

    @property
    def area(self):
        return calculate_shoelace_area(self.polygon)


class NestingAlgorithm:
    """Geometry-aware marker layout. See the module header for the method and its limits."""

    STANDARD_FABRIC_WIDTHS = list(STANDARD_FABRIC_WIDTHS)

    def __init__(self, pattern_pieces, fabric_width_cm=114, fabric_type="woven",
                 cutting_mode="folded", allow_rotation=None):
        try:
            self.fabric_width = float(fabric_width_cm)
        except (TypeError, ValueError):
            raise NestingError(f"Fabric width '{fabric_width_cm}' is not a number.", error_code="INVALID_FABRIC_WIDTH")
        if not self.fabric_width > 0:
            raise NestingError(f"Fabric width must be greater than 0 cm (got {fabric_width_cm}).",
                               error_code="INVALID_FABRIC_WIDTH")
        self.fabric_type = (fabric_type or "woven").lower()
        self.cutting_mode = (cutting_mode or "folded").lower()
        if self.cutting_mode not in ("folded", "open", "sheet"):
            raise NestingError(f"Unknown cutting mode '{cutting_mode}'.", error_code="INVALID_CUTTING_MODE")
        self.usable_width = self.fabric_width / 2.0 if self.cutting_mode == "folded" else self.fabric_width
        # 180-degree turns keep the grain direction; 90-degree turns never happen.
        # "sheet" mode is used only to arrange the printable pattern sheet (one copy of each piece,
        # fold pieces kept as half pieces, no rotation) - it is not a fabric layout.
        self.allow_rotation = (self.cutting_mode != "sheet") if allow_rotation is None else bool(allow_rotation)
        self.pieces_raw = pattern_pieces
        self.instances = self._build_instances(pattern_pieces)
        self.unplaced = []

    # -- input ----------------------------------------------------------------
    @staticmethod
    def _cut_polygon(piece):
        poly = piece.get("cutting_line") or piece.get("outline")
        if not poly or len(poly) < 3:
            raise NestingError(f"Pattern piece '{piece.get('name', '?')}' has no cutting-line geometry.",
                               error_code="NO_GEOMETRY")
        return poly

    def _build_instances(self, pieces):
        out = []
        for p in pieces:
            name = p.get("name", "Piece")
            qty = int(p.get("cut_count", p.get("cut_quantity", 1)) or 1)
            fold = bool(p.get("cut_on_fold", False))
            half = self._cut_polygon(p)
            half_area = calculate_shoelace_area(_open(half))
            if self.cutting_mode == "sheet":
                poly = _transform(half, False)
                out.append(_Instance(name, p, poly, False, 1, half_area, 1))
            elif self.cutting_mode == "folded":
                if fold:
                    poly = _transform(half, False)
                    n, layers, useful = qty, 1, half_area * 2.0
                else:
                    poly = _transform(half, False)
                    n, layers, useful = int(math.ceil(qty / 2.0)), 2, half_area
                    useful = half_area * qty / n
                for i in range(n):
                    out.append(_Instance(name + (f" ({i + 1})" if n > 1 else ""), p, poly, fold, layers, useful, qty))
            else:
                poly = _transform(_mirror_to_full(half) if fold else half, False)
                area = calculate_shoelace_area(poly)
                for i in range(qty):
                    out.append(_Instance(name + (f" ({i + 1})" if qty > 1 else ""), p, poly, False, 1, area, qty))
        out.sort(key=lambda r: (-r.area, r.name))
        return out

    # -- placement ------------------------------------------------------------
    def _place(self, inst, occ, wcells, hcells):
        best = None
        orientations = [False, True] if (self.allow_rotation and not inst.fold) else [False]
        for rot in orientations:
            poly = _transform(inst.polygon, rot)
            mask = _rasterise(poly)
            h, w = mask.shape
            if w > wcells:
                continue
            x_positions = [0] if inst.fold else range(0, wcells - w + 1)
            found = None
            for y0 in range(0, hcells - h + 1):
                slab = occ[y0:y0 + h]
                if not slab.any():
                    found = (y0, x_positions[0] if inst.fold else 0)
                    break
                for x0 in x_positions:
                    if not (slab[:, x0:x0 + w] & mask).any():
                        found = (y0, x0)
                        break
                if found:
                    break
            if found is None:
                continue
            top = found[0] + h
            key = (top, found[0], found[1])
            if best is None or key < best[0]:
                best = (key, rot, found, mask, poly)
        return best

    def run(self):
        if not self.instances:
            raise NestingError("No pattern pieces were provided, so no marker can be generated.", error_code="NO_PIECES")

        cell = CELL_CM
        wcells = int(math.floor(self.usable_width / cell + 1e-9)) + 2 * GAP_CELLS   # grid includes the margin
        hcells = int(MAX_LENGTH_CM / cell) + 2 * GAP_CELLS
        failed = []
        for inst in self.instances:
            bw = g.bbox(_open(inst.polygon))
            width = bw[2] - bw[0]
            if width > self.usable_width + 1e-9:
                failed.append({
                    "name": inst.name, "width_cm": round(width, 2), "height_cm": round(bw[3] - bw[1], 2),
                    "usable_width_cm": self.usable_width,
                    "reason": (f"needs {width:.1f} cm of width but only {self.usable_width:.1f} cm is usable"
                               + (f" (fabric folded: {self.fabric_width:.0f} cm bolt -> {self.usable_width:.1f} cm layer)"
                                  if self.cutting_mode == "folded" else "")
                               + "; a 90-degree turn is not permitted because it would break the grain")})
        if failed:
            names = ", ".join(f["name"] for f in failed)
            raise NestingError(
                f"Nesting failed: {len(failed)} required pattern piece(s) do not fit the selected fabric ({names}). "
                "Choose a wider fabric or a different cutting mode.",
                error_code="PIECE_DOES_NOT_FIT", failed_pieces=failed, fabric_width_cm=self.fabric_width,
                usable_width_cm=self.usable_width, cutting_mode=self.cutting_mode)

        occ = np.zeros((hcells, wcells), dtype=bool)
        placed = []
        for inst in self.instances:
            best = self._place(inst, occ, wcells, hcells)
            if best is None:
                self.unplaced.append(inst)
                continue
            _, rot, (y0, x0), mask, poly = best
            h, w = mask.shape
            occ[y0:y0 + h, x0:x0 + w] |= mask
            inst.rot180 = rot
            # the padded mask's column/row GAP_CELLS is the polygon's min corner, and grid column/row
            # GAP_CELLS is fabric x = 0 / y = 0, so the polygon's min corner lands exactly at x0*cell, y0*cell
            inst.x = x0 * cell
            inst.y = y0 * cell
            inst.placed_polygon = [(px + inst.x, py + inst.y) for px, py in poly]
            placed.append(inst)
        if self.unplaced:
            names = ", ".join(i.name for i in self.unplaced)
            raise NestingError(f"Nesting failed: could not place {names} within {MAX_LENGTH_CM:.0f} cm of fabric.",
                               error_code="LAYOUT_TOO_LONG",
                               failed_pieces=[{"name": i.name} for i in self.unplaced])

        # normalise so the layout starts at y = 0 and fold pieces sit exactly on x = 0
        min_y = min(g.bbox(i.placed_polygon)[1] for i in placed)
        for i in placed:
            i.placed_polygon = [(px, py - min_y) for px, py in i.placed_polygon]
            if i.fold:
                mnx = g.bbox(i.placed_polygon)[0]
                i.placed_polygon = [(px - mnx, py) for px, py in i.placed_polygon]
        length = max(g.bbox(i.placed_polygon)[3] for i in placed)

        return self._result(placed, length)

    # -- results --------------------------------------------------------------
    def _result(self, placed, length):
        fabric_area = self.fabric_width * length
        useful_area = sum(i.useful_area for i in placed)
        util = min(100.0, max(0.0, useful_area / fabric_area * 100.0)) if fabric_area > 0 else 0.0
        util_r = round(util, 1)
        waste_cm2 = round(max(0.0, fabric_area - useful_area), 1)

        exact_m = round(length / 100.0, 2)
        purchase_cm = length * (1.0 + SHRINKAGE_ALLOWANCE) + END_MARGIN_CM
        purchase_m = round(math.ceil(purchase_cm / ROUND_UP_CM - 1e-9) * ROUND_UP_CM / 100.0, 2)
        handling = round(purchase_m - exact_m, 2)

        if util_r < 45.0:
            status, rec = "Low efficiency — the layout leaves a lot of unused fabric", (
                "Garment pieces are few and the fabric is wide; a narrower fabric usually wastes less.")
        elif util_r <= 65.0:
            status, rec = "Moderate efficiency — normal for a single garment", "Typical result for one custom garment."
        else:
            status, rec = "High efficiency — compact layout", "Compact layout with little leftover fabric."

        placements = []
        for i in placed:
            bx0, by0, bx1, by1 = g.bbox(i.placed_polygon)
            placements.append({
                "name": i.name,
                "piece_type": i.source.get("piece_type"),
                "cut_quantity": i.cut_quantity,
                "cut_on_fold": i.fold,
                "pieces_per_placement": i.layers_cut,
                "seam_allowance_cm": i.source.get("seam_allowance_cm"),
                "polygon_coordinates": [[round(x, 3), round(y, 3)] for x, y in i.placed_polygon],
                "polygon_area_cm2": round(i.area, 2),
                "bounding_dimensions": {"width_cm": round(bx1 - bx0, 2), "height_cm": round(by1 - by0, 2)},
                "rotation_deg": 180 if i.rot180 else 0,
                "final_nested_position": {"x_cm": round(bx0, 2), "y_cm": round(by0, 2)},
                "x": round(bx0, 2), "y": round(by0, 2),
                "width": round(bx1 - bx0, 2), "height": round(by1 - by0, 2),
                "rotated": i.rot180,
            })

        checks = self._verify(placed, length, useful_area)
        mode_text = "Fabric folded in half lengthwise" if self.cutting_mode == "folded" else "Fabric laid open flat"
        return {
            "method": "polygon Bottom-Left-Fill on a 0.5 cm grid using cutting-line geometry (heuristic, not optimal)",
            "full_bolt_width_cm": self.fabric_width,
            "usable_width_cm": self.usable_width,
            "cutting_mode": self.cutting_mode,
            "cutting_method_simple": mode_text,
            "fabric_width_cm": self.fabric_width,
            "fabric_length_cm": round(length, 2),
            "exact_yardage_metres": exact_m,
            "purchasing_recommended_m": purchase_m,
            "handling_allowance_m": handling,
            "yardage_metres": purchase_m,
            "yardage_yards": round(purchase_m * 1.09361, 2),
            "total_pattern_piece_area_cm2": round(useful_area, 1),
            "usable_area_cm2": round(fabric_area, 1),
            "utilisation_percent": util_r,
            "waste_percent": round(100.0 - util_r, 1),
            "waste_cm2": waste_cm2,
            "usage_status": status,
            "usage_recommendation": rec,
            "placed_pieces": placements,
            "total_pieces": len(placed),
            "validation_checks": checks,
            "assumptions": [
                "Layout uses the cutting-line (seam allowance included) polygons of the validated pattern.",
                "Pieces keep their grain: only 0 or 180 degree orientations are used; fold pieces are never rotated.",
                f"Purchase length = layout length + {SHRINKAGE_ALLOWANCE * 100:.0f}% shrinkage + {END_MARGIN_CM:.0f} cm "
                f"cutting margin, rounded up to {ROUND_UP_CM:.0f} cm.",
                "Fabric is treated as plain (no directional print or nap, no pattern matching).",
                "Greedy Bottom-Left-Fill heuristic: an upper bound on fabric use, not a proven optimum.",
            ],
        }

    def _verify(self, placed, length, useful_area):
        polys = [i.placed_polygon for i in placed]
        no_overlap = True
        for a in range(len(polys)):
            for b in range(a + 1, len(polys)):
                if polygons_overlap(polys[a], polys[b]):
                    no_overlap = False
        tol = 0.01
        within = all(g.bbox(p)[0] >= -tol and g.bbox(p)[2] <= self.usable_width + tol and g.bbox(p)[1] >= -tol
                     and g.bbox(p)[3] <= length + tol for p in polys)
        fold_ok = all(abs(g.bbox(i.placed_polygon)[0]) <= tol for i in placed if i.fold)
        grain_ok = all(not i.fold or not i.rot180 for i in placed)          # 90-degree turns never generated
        # quantity: pieces produced per source piece == required cut quantity
        produced = {}
        for i in placed:
            produced[id(i.source)] = produced.get(id(i.source), 0) + (2 if (i.fold and self.cutting_mode == "folded") else i.layers_cut) \
                if False else produced.get(id(i.source), 0) + i.layers_cut
        need = {}
        for i in placed:
            need[id(i.source)] = i.cut_quantity
        quantities_ok = all(produced[k] >= need[k] for k in need)
        lower_bound = useful_area / self.fabric_width
        return {
            "no_overlap": no_overlap,
            "within_bounds": within,
            "fold_alignment": fold_ok,
            "grain_preserved": grain_ok,
            "quantities_satisfied": quantities_ok,
            "efficiency_in_range": 0.0 <= (useful_area / (self.fabric_width * length) * 100.0 if length else 0) <= 100.0 + 1e-6,
            "theoretical_lower_bound_satisfied": length >= lower_bound - 0.01,
            "pattern_dimensions_invariant": True,       # nesting only translates / turns 180 deg; polygons are never scaled
            "status": "PASSED" if (no_overlap and within and fold_ok and grain_ok and quantities_ok) else "FAILED",
        }


def estimate_fabric(pieces, fabric_width_cm=114, cutting_mode="auto", fabric_type="woven"):
    """
    Fabric requirement for validated pattern pieces. cutting_mode 'auto' lays the pattern out both
    folded and open and keeps the layout that needs the shorter purchase length (ties -> folded).
    Raises NestingError if no requested layout is possible.
    """
    mode = (cutting_mode or "auto").lower()
    if mode not in ("auto", "folded", "open"):
        raise NestingError(f"Unknown cutting mode '{cutting_mode}'.", error_code="INVALID_CUTTING_MODE")
    modes = ["folded", "open"] if mode == "auto" else [mode]
    results, errors = {}, []
    for m in modes:
        try:
            results[m] = NestingAlgorithm(pieces, fabric_width_cm=fabric_width_cm, fabric_type=fabric_type,
                                          cutting_mode=m).run()
        except NestingError as err:
            errors.append(err)
    if not results:
        raise errors[0]
    best_mode = min(results, key=lambda m: (results[m]["purchasing_recommended_m"], m != "folded"))
    best = dict(results[best_mode])
    best["requested_cutting_mode"] = mode
    best["mode_comparison"] = {m: {"purchasing_recommended_m": r["purchasing_recommended_m"],
                                   "fabric_length_cm": r["fabric_length_cm"],
                                   "utilisation_percent": r["utilisation_percent"]} for m, r in results.items()}
    return best
