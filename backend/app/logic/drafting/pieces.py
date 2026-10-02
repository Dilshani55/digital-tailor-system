"""Pattern piece container: geometry first, presentation derived."""

from app.logic.drafting import geometry as g


def _pt(p):
    return [round(float(p[0]), 4), round(float(p[1]), 4)]


class Piece:
    def __init__(self, name, piece_type, segments, points, *, cut_count, cut_on_fold, grain,
                 fold_line=None, darts=None, meta=None, seam_allowance_cm=1.5):
        self.name = name
        self.piece_type = piece_type
        self.segments = list(segments)
        self.points = dict(points)
        self.cut_count = cut_count
        self.cut_on_fold = cut_on_fold
        self.grain = grain                  # ((x0, y0), (x1, y1))
        self.fold_line = fold_line          # ((x0, y0), (x1, y1)) or None
        self.darts = list(darts or [])
        self.meta = dict(meta or {})
        self.seam_allowance_cm = seam_allowance_cm   # main seam allowance; real geometry is in cut_outline
        self.transformations = []
        self.dimensions = []                # dimension annotations (builders fill them in)
        # cutting-line geometry, attached by seam_allowance.apply_seam_allowance()
        self.allowances = {}
        self.cut_outline = None
        self.edge_kinds = []
        self.edge_offsets = []
        self.seam_outline = None
        self.notches = []

    # geometry -----------------------------------------------------------------
    @property
    def outline(self):
        pts = g.flatten_path(self.segments)
        if len(pts) > 1 and g.dist(pts[0], pts[-1]) <= 1e-9:
            pts = pts[:-1]
        return pts

    def segment(self, seg_id):
        return next((s for s in self.segments if s.id == seg_id), None)

    def seam_length(self, seg_ids):
        return sum(self.segment(i).length() for i in seg_ids if self.segment(i) is not None)

    def to_dict(self):
        outline = self.outline
        if outline and g.all_finite(outline):
            min_x, min_y, max_x, max_y = g.bbox(outline)
            box = {"width_cm": round(max_x - min_x, 2), "height_cm": round(max_y - min_y, 2),
                   "min_x": round(min_x, 3), "min_y": round(min_y, 3)}
            area = round(g.polygon_area(outline), 2)
        else:
            box, area = {"width_cm": 0, "height_cm": 0, "min_x": 0, "min_y": 0}, 0.0
        cut = self.cut_outline
        if cut and g.all_finite(cut):
            cx0, cy0, cx1, cy1 = g.bbox(cut)
            cut_box = {"width_cm": round(cx1 - cx0, 2), "height_cm": round(cy1 - cy0, 2),
                       "min_x": round(cx0, 3), "min_y": round(cy0, 3)}
            cut_area = round(g.polygon_area(cut), 2)
        else:
            cut_box, cut_area = None, None
        return {
            "units": "cm",
            "side": {"front_bodice": "front", "back_bodice": "back"}.get(self.piece_type),
            "cutting_line": None if cut is None else [_pt(p) for p in cut],
            "cut_bounding_box": cut_box,
            "cut_polygon_area_cm2": cut_area,
            "seam_allowances": dict(self.allowances),
            "edge_allowances": [
                {"kind": k, "cm": o} for k, o in zip(self.edge_kinds, self.edge_offsets)
            ] if self.edge_kinds else [],
            "notches": list(self.notches),
            "name": self.name,
            "piece_type": self.piece_type,
            "cut_count": self.cut_count,
            "cut_on_fold": self.cut_on_fold,
            "fold_line": None if self.fold_line is None else {"start": _pt(self.fold_line[0]), "end": _pt(self.fold_line[1])},
            "grain_line": {"start": _pt(self.grain[0]), "end": _pt(self.grain[1])},
            "seam_allowance_cm": self.seam_allowance_cm,
            "points": {k: _pt(v) for k, v in self.points.items()},
            "segments": [s.to_dict() for s in self.segments],
            "outline": [_pt(p) for p in outline],
            "darts": self.darts,
            "bounding_box": box,
            "polygon_area_cm2": area,
            "measurements": {k: (round(v, 3) if isinstance(v, float) else v) for k, v in self.meta.items()},
            "transformations": list(self.transformations),
            "dimensions": [dict(d) for d in self.dimensions],
        }
