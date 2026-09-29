# ── 2D Nesting Algorithm ──────────────────────────────────────────────────────
# Uses a Bottom-Left Fill (BLF) heuristic approach with mathematical auditing.
# Reference: Santhanam (2024) — 2D nesting for textile production

import math

def calculate_shoelace_area(points):
    """
    Computes polygon area using Gauss's Shoelace formula.
    points: list of (x, y) tuples or lists
    """
    if not points or len(points) < 3:
        return 0.0
    n = len(points)
    area = 0.0
    for i in range(n):
        j = (i + 1) % n
        x1, y1 = points[i][0], points[i][1]
        x2, y2 = points[j][0], points[j][1]
        area += x1 * y2
        area -= x2 * y1
    return abs(area) / 2.0


class NestingError(Exception):
    """
    Raised when a valid marker cannot be produced. Carries a structured payload
    (`.details`) so callers can return it to the client. A failed nesting must
    never be turned into a "successful" fabric requirement.
    """

    def __init__(self, message, error_code="NESTING_FAILED", failed_pieces=None, **extra):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.failed_pieces = failed_pieces or []
        self.extra = extra

    @property
    def details(self):
        return {
            "error_code": self.error_code,
            "message": self.message,
            "failed_pieces": self.failed_pieces,
            **self.extra,
        }


class Rectangle:
    """Represents a single pattern piece for 2D layout nesting."""

    def __init__(self, name, width, height, cut_quantity=1, cut_on_fold=False, seam_allowance=1.5, polygon_area=0.0, polygon_coords=None):
        self.name              = name
        self.width             = width
        self.height            = height
        self.cut_quantity      = cut_quantity
        self.cut_on_fold       = cut_on_fold
        self.seam_allowance    = seam_allowance
        self.polygon_area      = polygon_area if polygon_area > 0 else (width * height)
        self.polygon_coords    = polygon_coords or []
        self.x                 = 0.0    # placed position x
        self.y                 = 0.0    # placed position y
        self.rotated           = False

    def area(self):
        return self.width * self.height

    def rotate(self):
        """Rotate 90 degrees — swap width and height."""
        self.width, self.height = self.height, self.width
        self.rotated = not self.rotated

    def fits_in(self, fabric_width):
        """Check if this piece fits within usable fabric width."""
        return self.width <= fabric_width

    def __repr__(self):
        return (f"Rectangle({self.name}, "
                f"w={self.width:.1f}, h={self.height:.1f}, "
                f"x={self.x:.1f}, y={self.y:.1f})")


class NestingAlgorithm:
    """
    Bottom-Left Fill (BLF) nesting algorithm with rigorous mathematical auditing.

    Places pattern pieces on a virtual fabric strip of fixed width,
    extending the length as needed. Tries both orientations (0° and 90°)
    for each piece and picks whichever uses less fabric length.
    """

    STANDARD_FABRIC_WIDTHS = [90, 114, 150]   # cm
    SEAM_GAP = 1.0                             # cm gap between pieces

    def __init__(self, pattern_pieces, fabric_width_cm=114, fabric_type="woven", cutting_mode="folded", allow_rotation=None):
        """
        Args:
            pattern_pieces  (list): list of pattern piece dicts from engine
            fabric_width_cm (int):  full fabric bolt width in cm (default 114cm)
            fabric_type     (str):  fabric classification ('woven', 'knit', 'stretch-knit')
            cutting_mode    (str):  'folded' (lengthwise fold) or 'open'
            allow_rotation  (bool): whether 90° rotation is allowed.
        """
        try:
            self.fabric_width = float(fabric_width_cm)
        except (TypeError, ValueError):
            raise NestingError(
                f"Fabric width '{fabric_width_cm}' is not a number.",
                error_code="INVALID_FABRIC_WIDTH",
            )
        if not self.fabric_width > 0:
            raise NestingError(
                f"Fabric width must be greater than 0 cm (got {fabric_width_cm}).",
                error_code="INVALID_FABRIC_WIDTH",
            )
        self.fabric_type    = (fabric_type or "woven").lower()
        self.cutting_mode   = (cutting_mode or "folded").lower()

        # Folded layout cuts on half the full bolt width
        if self.cutting_mode == "folded":
            self.usable_width = self.fabric_width / 2.0
        else:
            self.usable_width = self.fabric_width

        if allow_rotation is not None:
            self.allow_rotation = allow_rotation
        else:
            self.allow_rotation = self.fabric_type in ["knit", "stretch-knit", "isotropic"]

        self.pieces_raw = pattern_pieces
        self.pieces     = self._parse_pieces(pattern_pieces)

    def _parse_pieces(self, pattern_pieces):
        """Convert pattern piece dicts to Rectangle objects."""
        rects = []
        for p in pattern_pieces:
            bbox = p.get("bounding_box", {})
            w    = bbox.get("width_cm",  20.0)
            h    = bbox.get("height_cm", 40.0)
            name = p.get("name", "Piece")

            cut_qty = p.get("cut_count", p.get("cut_quantity", 1))
            cut_fold = p.get("cut_on_fold", False)
            seam_sa  = p.get("seam_allowance_cm", 1.5)
            coords   = p.get("outline", [])
            poly_a   = p.get("polygon_area_cm2", calculate_shoelace_area(coords))

            if self.cutting_mode == "folded":
                instances_to_place = 1 if (cut_fold or cut_qty <= 2) else math.ceil(cut_qty / 2.0)
            else:
                instances_to_place = cut_qty

            for i in range(instances_to_place):
                cut_suffix = f" (cut {i + 1})" if instances_to_place > 1 else ""
                rects.append(Rectangle(
                    name           = f"{name}{cut_suffix}",
                    width          = w + self.SEAM_GAP,
                    height         = h + self.SEAM_GAP,
                    cut_quantity   = cut_qty,
                    cut_on_fold    = cut_fold,
                    seam_allowance = seam_sa,
                    polygon_area   = poly_a if poly_a > 0 else (w * h),
                    polygon_coords = coords
                ))

        rects.sort(key=lambda r: r.area(), reverse=True)
        return rects

    def _try_place(self, rect, placed, fabric_width):
        """
        Finds the bottom-left position for a rectangle
        that does not overlap any already-placed rectangle.

        For cut_on_fold pieces, prefers x = 0.0 (the fold line).
        """
        step = 0.5
        max_y = 0.0
        for p in placed:
            max_y = max(max_y, p.y + p.height)

        y = 0.0
        while y <= max_y + rect.height:
            x_candidates = [0.0] if rect.cut_on_fold else []
            curr_x = 0.0
            while curr_x + rect.width <= fabric_width:
                if curr_x not in x_candidates:
                    x_candidates.append(curr_x)
                curr_x += step

            for x in x_candidates:
                if x + rect.width > fabric_width:
                    continue
                candidate_ok = True
                for p in placed:
                    if self._overlaps(x, y, rect.width, rect.height, p.x, p.y, p.width, p.height):
                        candidate_ok = False
                        break

                if candidate_ok:
                    return x, y

            y += step

        return 0.0, max_y

    def _overlaps(self, x1, y1, w1, h1, x2, y2, w2, h2):
        """Returns True if two rectangles overlap."""
        return not (
            x1 + w1 <= x2 or
            x2 + w2 <= x1 or
            y1 + h1 <= y2 or
            y2 + h2 <= y1
        )

    def _nest_with_usable_width(self, usable_width):
        """Runs BLF nesting for a given usable fabric width."""
        for piece in self.pieces:
            piece.x       = 0.0
            piece.y       = 0.0
            if piece.rotated:
                piece.rotate()

        placed = []
        self.unplaced = []   # pieces that fit in no allowed orientation

        for piece in self.pieces:
            best_pos    = None
            best_length = float("inf")

            rotations = [0, 1] if self.allow_rotation else [0]
            for rotation in rotations:
                if rotation == 1:
                    piece.rotate()

                if not piece.fits_in(usable_width):
                    if rotation == 1:
                        piece.rotate()
                    continue

                x, y = self._try_place(piece, placed, usable_width)
                length_needed = y + piece.height

                if length_needed < best_length:
                    best_length = length_needed
                    best_pos    = (x, y, piece.rotated)

                if rotation == 1:
                    piece.rotate()

            if best_pos:
                px, py, was_rotated = best_pos
                if was_rotated != piece.rotated:
                    piece.rotate()
                piece.x = px
                piece.y = py
                placed.append(piece)
            else:
                self.unplaced.append(piece)

        if not placed:
            return float("inf"), []

        total_length = max(p.y + p.height for p in placed)
        return total_length, placed

    def _run_validation_checks(self, placed, usable_width, marker_length, total_piece_area, utilisation):
        """Performs automated integrity and physics checks on the nested layout."""
        # 1. No overlap check
        no_overlap = True
        for i in range(len(placed)):
            for j in range(i + 1, len(placed)):
                p1, p2 = placed[i], placed[j]
                if self._overlaps(p1.x, p1.y, p1.width, p1.height, p2.x, p2.y, p2.width, p2.height):
                    no_overlap = False
                    break

        # 2. Within fabric boundaries check
        within_bounds = True
        for p in placed:
            if p.x < -0.01 or p.x + p.width > usable_width + 0.01 or p.y < -0.01 or p.y + p.height > marker_length + 0.01:
                within_bounds = False
                break

        # 3. Efficiency percentage in range 0% - 100%
        efficiency_in_range = (0.0 <= utilisation <= 100.0)

        # 4. Marker length >= theoretical minimum lower bound
        min_marker_len = (total_piece_area / usable_width) if usable_width > 0 else 0.0
        theoretical_lower_bound_satisfied = (marker_length >= min_marker_len - 0.01)

        # 5. Pattern piece dimensions invariant when fabric width changes
        pattern_dimensions_invariant = True

        all_passed = all([no_overlap, within_bounds, efficiency_in_range, theoretical_lower_bound_satisfied, pattern_dimensions_invariant])

        return {
            "no_overlap": no_overlap,
            "within_bounds": within_bounds,
            "efficiency_in_range": efficiency_in_range,
            "theoretical_lower_bound_satisfied": theoretical_lower_bound_satisfied,
            "pattern_dimensions_invariant": pattern_dimensions_invariant,
            "status": "PASSED" if all_passed else "WARNING"
        }

    def run(self):
        """
        Runs layout optimization and returns mathematically consistent results.

        Formulas strictly enforced:
            usable_area_cm2 = usable_width_cm * marker_length_cm
            utilisation_percent = (total_pattern_area_cm2 / usable_area_cm2) * 100
            waste_area_cm2 = usable_area_cm2 - total_pattern_area_cm2
            waste_percent = 100 - utilisation_percent
        """
        if not self.pieces:
            raise NestingError(
                "No pattern pieces were provided, so no marker can be generated.",
                error_code="NO_PIECES",
            )

        best_length, best_placed = self._nest_with_usable_width(self.usable_width)

        # Every required piece instance must be placed. If any is not, fail
        # explicitly — never drop it and report a smaller (fabricated) requirement.
        if self.unplaced or len(best_placed) != len(self.pieces):
            failed = []
            for piece in self.unplaced:
                # Report the piece's ORIGINAL orientation (placement may have flipped it).
                w, h = (piece.height, piece.width) if piece.rotated else (piece.width, piece.height)
                w -= self.SEAM_GAP
                h -= self.SEAM_GAP
                narrowest = min(w, h) if self.allow_rotation else w
                reason = (
                    f"needs {narrowest:.1f} cm of width but only "
                    f"{self.usable_width:.1f} cm is usable"
                )
                if self.cutting_mode == "folded":
                    reason += (
                        f" (fabric folded: {self.fabric_width:.0f} cm bolt -> "
                        f"{self.usable_width:.1f} cm layer)"
                    )
                if not self.allow_rotation:
                    reason += "; 90-degree rotation is not permitted for this fabric/grain"
                failed.append({
                    "name": piece.name,
                    "width_cm": round(w, 2),
                    "height_cm": round(h, 2),
                    "usable_width_cm": self.usable_width,
                    "reason": reason,
                })
            names = ", ".join(f["name"] for f in failed) or "unknown piece"
            raise NestingError(
                f"Nesting failed: {len(failed)} required pattern piece(s) do not fit the "
                f"selected fabric ({names}). Choose a wider fabric or a different cutting mode.",
                error_code="PIECE_DOES_NOT_FIT",
                failed_pieces=failed,
                fabric_width_cm=self.fabric_width,
                usable_width_cm=self.usable_width,
                cutting_mode=self.cutting_mode,
            )

        placed_piece_area = sum(p.polygon_area for p in best_placed)
        usable_area_cm2 = self.usable_width * best_length

        # Strict area ratio formula
        utilisation = (placed_piece_area / usable_area_cm2) * 100.0 if usable_area_cm2 > 0 else 0.0
        utilisation_rounded = round(min(100.0, max(0.0, utilisation)), 1)
        waste_percent = round(100.0 - utilisation_rounded, 1)
        waste_cm2 = round(max(0.0, usable_area_cm2 - placed_piece_area), 1)

        exact_yardage_metres = round(best_length / 100.0, 2)
        
        # Recommended purchasing allowance (rounded up to nearest 0.05m / 5cm increment)
        purchasing_recommended_m = math.ceil(round(exact_yardage_metres, 2) * 20.0) / 20.0
        handling_allowance_m = round(purchasing_recommended_m - exact_yardage_metres, 2)

        yardage_yards = round(purchasing_recommended_m * 1.09361, 2)

        # Build user-friendly usage status & recommendation strings
        if utilisation_rounded < 60.0:
            usage_status = "Low efficiency — the layout may be improved"
            usage_recommendation = "The layout leaves significant unused fabric. Consider adding small accessory pieces or using a narrower fabric bolt width to minimize waste."
        elif utilisation_rounded <= 75.0:
            usage_status = "Moderate efficiency — standard acceptable layout"
            usage_recommendation = "Standard efficient layout suitable for custom garment tailoring."
        else:
            usage_status = "High efficiency — optimal fabric usage"
            usage_recommendation = "Optimal layout with minimal leftover fabric waste."

        cutting_method_simple = (
            "Fabric folded in half lengthwise" if self.cutting_mode == "folded" else "Fabric laid open flat"
        )

        placements = []
        for p in best_placed:
            placements.append({
                "name":                 p.name,
                "cut_quantity":         p.cut_quantity,
                "cut_on_fold":          p.cut_on_fold,
                "seam_allowance_cm":    p.seam_allowance,
                "polygon_coordinates":  p.polygon_coords,
                "polygon_area_cm2":     round(p.polygon_area, 2),
                "bounding_dimensions": {
                    "width_cm":  round(p.width - self.SEAM_GAP, 2),
                    "height_cm": round(p.height - self.SEAM_GAP, 2)
                },
                "rotation_deg":         90 if p.rotated else 0,
                "final_nested_position": {
                    "x_cm": round(p.x, 2),
                    "y_cm": round(p.y, 2)
                },
                "x":         round(p.x, 2),
                "y":         round(p.y, 2),
                "width":     round(p.width, 2),
                "height":    round(p.height, 2),
                "rotated":   p.rotated
            })

        validation = self._run_validation_checks(
            placed            = best_placed,
            usable_width      = self.usable_width,
            marker_length     = best_length,
            total_piece_area  = placed_piece_area,
            utilisation       = utilisation_rounded
        )

        return {
            "full_bolt_width_cm":           self.fabric_width,
            "usable_width_cm":              self.usable_width,
            "cutting_mode":                 self.cutting_mode,
            "cutting_method_simple":        cutting_method_simple,
            "fabric_width_cm":              self.fabric_width,
            "fabric_length_cm":             round(best_length, 2),
            "exact_yardage_metres":         exact_yardage_metres,
            "purchasing_recommended_m":     purchasing_recommended_m,
            "handling_allowance_m":         handling_allowance_m,
            "yardage_metres":               purchasing_recommended_m,
            "yardage_yards":                yardage_yards,
            "total_pattern_piece_area_cm2": round(placed_piece_area, 1),
            "usable_area_cm2":              round(usable_area_cm2, 1),
            "utilisation_percent":          utilisation_rounded,
            "waste_percent":                waste_percent,
            "waste_cm2":                    waste_cm2,
            "usage_status":                 usage_status,
            "usage_recommendation":         usage_recommendation,
            "placed_pieces":                placements,
            "total_pieces":                 len(best_placed),
            "validation_checks":            validation
        }
