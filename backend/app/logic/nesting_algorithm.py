# ── 2D Nesting Algorithm ──────────────────────────────────────────────────────
# Uses a Bottom-Left Fill (BLF) heuristic approach
# This is the standard algorithm used in garment CAD systems
# Reference: Santhanam (2024) — 2D nesting for textile production

class Rectangle:
    """Represents a single pattern piece as a bounding rectangle."""

    def __init__(self, name, width, height):
        self.name     = name
        self.width    = width
        self.height   = height
        self.x        = 0.0    # placed position x
        self.y        = 0.0    # placed position y
        self.rotated  = False

    def area(self):
        return self.width * self.height

    def rotate(self):
        """Rotate 90 degrees — swap width and height."""
        self.width, self.height = self.height, self.width
        self.rotated = not self.rotated

    def fits_in(self, fabric_width):
        """Check if this piece fits within fabric width."""
        return self.width <= fabric_width

    def __repr__(self):
        return (f"Rectangle({self.name}, "
                f"w={self.width:.1f}, h={self.height:.1f}, "
                f"x={self.x:.1f}, y={self.y:.1f})")


class NestingAlgorithm:
    """
    Bottom-Left Fill (BLF) nesting algorithm.

    Places pattern pieces on a virtual fabric strip of fixed width,
    extending the length as needed. Tries both orientations (0° and 90°)
    for each piece and picks whichever uses less fabric length.

    Standard fabric widths used in Sri Lankan tailoring:
        - 90 cm  (narrow — rare)
        - 114 cm (standard dress fabric)
        - 150 cm (wide fabric — most common)
    """

    STANDARD_FABRIC_WIDTHS = [90, 114, 150]   # cm
    SEAM_GAP = 1.0                             # cm gap between pieces

    def __init__(self, pattern_pieces, fabric_width_cm=114):
        """
        Args:
            pattern_pieces  (list): list of pattern piece dicts from engine
            fabric_width_cm (int):  fabric width in cm (default 114cm)
        """
        self.fabric_width = fabric_width_cm
        self.pieces       = self._parse_pieces(pattern_pieces)

    def _parse_pieces(self, pattern_pieces):
        """Convert pattern piece dicts to Rectangle objects."""
        rects = []
        for p in pattern_pieces:
            bbox = p.get("bounding_box", {})
            w    = bbox.get("width_cm",  20.0)
            h    = bbox.get("height_cm", 40.0)
            name = p.get("name", "Piece")

            count = 2

            for i in range(count):
                rects.append(Rectangle(
                    name  = f"{name} (cut {i + 1})",
                    width = w + self.SEAM_GAP,
                    height= h + self.SEAM_GAP
                ))

        rects.sort(key=lambda r: r.area(), reverse=True)
        return rects

    def _try_place(self, rect, placed, fabric_width):
        """
        Finds the bottom-left position for a rectangle
        that does not overlap any already-placed rectangle.

        Returns (x, y) position or None if no valid position found.
        """
        step = 0.5

        max_y = 0
        for p in placed:
            max_y = max(max_y, p.y + p.height)

        y = 0.0
        while y <= max_y + rect.height:
            x = 0.0
            while x + rect.width <= fabric_width:
                candidate_ok = True
                for p in placed:
                    if self._overlaps(x, y, rect.width, rect.height,
                                      p.x, p.y, p.width, p.height):
                        candidate_ok = False
                        break

                if candidate_ok:
                    return x, y

                x += step
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

    def _nest_with_width(self, fabric_width):
        """
        Runs BLF nesting for a given fabric width.
        Returns total fabric length needed.
        """
        for piece in self.pieces:
            piece.x       = 0.0
            piece.y       = 0.0
            if piece.rotated:
                piece.rotate()

        placed = []

        for piece in self.pieces:
            best_pos    = None
            best_length = float("inf")

            for rotation in range(2):
                if rotation == 1:
                    piece.rotate()

                if not piece.fits_in(fabric_width):
                    if rotation == 1:
                        piece.rotate()
                    continue

                x, y = self._try_place(piece, placed, fabric_width)
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

        if not placed:
            return float("inf"), []

        total_length = max(p.y + p.height for p in placed)
        return total_length, placed

    def run(self):
        """
        Runs nesting for all standard fabric widths and picks the best result.
        """
        best_result = None
        best_length = float("inf")
        best_width  = self.fabric_width
        best_placed = []

        widths_to_try = [self.fabric_width] + [
            w for w in self.STANDARD_FABRIC_WIDTHS
            if w != self.fabric_width
        ]

        for width in widths_to_try:
            length, placed = self._nest_with_width(width)
            if length < best_length:
                best_length = length
                best_width  = width
                best_placed = placed

        total_length = best_length + 10.0

        total_piece_area = sum(
            p.width * p.height for p in best_placed
        )
        fabric_area      = best_width * total_length
        utilisation      = (total_piece_area / fabric_area) * 100 if fabric_area > 0 else 0.0

        yardage_metres = round(total_length / 100, 2)
        yardage_yards  = round(yardage_metres * 1.094, 2)

        placements = []
        for p in best_placed:
            placements.append({
                "name":      p.name,
                "x":         round(p.x, 2),
                "y":         round(p.y, 2),
                "width":     round(p.width, 2),
                "height":    round(p.height, 2),
                "rotated":   p.rotated
            })

        return {
            "fabric_width_cm":      best_width,
            "fabric_length_cm":     round(total_length, 2),
            "yardage_metres":       yardage_metres,
            "yardage_yards":        yardage_yards,
            "utilisation_percent":  round(utilisation, 1),
            "waste_cm2":            round(fabric_area - total_piece_area, 1),
            "placed_pieces":        placements,
            "total_pieces":         len(best_placed)
        }
