"""
Seam-allowance (cutting-line) geometry and balance marks (notches).

The drafted outline of a Piece is the SEAM (stitching) line. This module offsets it outward,
edge by edge, to produce the CUTTING line:

  * every edge gets its own allowance (side/shoulder/armhole seams, neckline, hem, ...);
  * a fold edge (the centre line of a piece cut on the fold) gets 0 - the cutting line runs
    exactly along the fold;
  * adjacent offset edges are joined by intersecting their offset lines (mitre); very sharp
    corners are bevelled so the cutting line can never spike.

Nothing here is a metadata-only value: `cut_outline` is real geometry that nesting, the SVG
preview and the printable PDF all use. Units: cm. Deterministic.
"""

import math

from app.logic.drafting import geometry as g

# Allowance table (cm). Project choice, documented in assumptions.py (sewing practice, not measured).
ALLOWANCES = {
    "woven_bodice": {"seam": 1.5, "neckline": 1.0, "hem": 2.5, "strip": 1.0},
    "knit_bodice": {"seam": 1.0, "neckline": 1.0, "hem": 2.0, "strip": 0.7},
}

MITRE_LIMIT = 2.0        # max mitre length as a multiple of the largest local allowance
PARALLEL_EPS = 1e-9
REMOVE_REVERSED_EDGES = True


def allowance_table(block_id):
    return dict(ALLOWANCES[block_id])


def edge_kind(piece, seg_id):
    """Classify a segment id into an allowance kind ('fold' for the centre line of a fold piece)."""
    if seg_id == "centre_line" and piece.cut_on_fold:
        return "fold"
    if seg_id.startswith("neckline"):
        return "neckline"
    if seg_id == "hem":
        return "hem"
    if piece.piece_type in ("neckband", "armhole_facing"):
        return "strip"
    return "seam"


def labelled_outline(piece):
    """Closed outline points (no repeated end point) and the segment id / kind of every edge."""
    pts, ids = [], []
    for seg in piece.segments:
        seg_pts = seg.flatten()
        for k in range(len(seg_pts) - 1):
            if not pts:
                pts.append(seg_pts[k])
            ids.append(seg.id)
            pts.append(seg_pts[k + 1])
    if len(pts) > 1 and g.dist(pts[0], pts[-1]) <= 1e-9:
        pts = pts[:-1]
    return pts, ids


def _signed_area(pts):
    return sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1]
               for i in range(len(pts))) / 2.0


def offset_polygon(points, offsets):
    """
    Offset a closed polygon outward, edge i (points[i] -> points[i+1]) by offsets[i].
    Returns the new closed polygon (list of points, no repeated end).
    """
    n = len(points)
    if n < 3 or len(offsets) != n:
        raise ValueError("offset_polygon needs a closed polygon with one offset per edge")
    sign = 1.0 if _signed_area(points) > 0 else -1.0
    lines = []                       # (point on offset line, unit direction)
    for i in range(n):
        a, b = points[i], points[(i + 1) % n]
        length = g.dist(a, b)
        if length < 1e-12:
            lines.append(None)
            continue
        ex, ey = (b[0] - a[0]) / length, (b[1] - a[1]) / length
        nx, ny = sign * ey, -sign * ex          # outward normal
        d = offsets[i]
        lines.append(((a[0] + nx * d, a[1] + ny * d), (ex, ey), (nx, ny), d))

    active = [i for i in range(n) if lines[i] is not None]

    def join(prev, cur, vertex):
        """Vertices joining two consecutive offset lines (1 mitre point, or 2 for bevel / step)."""
        (p0, e0, n0, d0), (p1, e1, n1, d1) = prev, cur
        cross = e0[0] * e1[1] - e0[1] * e1[0]
        if abs(cross) < PARALLEL_EPS:
            q0 = (vertex[0] + n0[0] * d0, vertex[1] + n0[1] * d0)
            q1 = (vertex[0] + n1[0] * d1, vertex[1] + n1[1] * d1)
            return [q0] if g.dist(q0, q1) <= 1e-9 else [q0, q1]
        dx, dy = p1[0] - p0[0], p1[1] - p0[1]
        s_ = (dx * e1[1] - dy * e1[0]) / cross
        q = (p0[0] + e0[0] * s_, p0[1] + e0[1] * s_)
        if g.dist(q, vertex) > MITRE_LIMIT * max(d0, d1, 1e-9):
            return [(vertex[0] + n0[0] * d0, vertex[1] + n0[1] * d0), (vertex[0] + n1[0] * d1, vertex[1] + n1[1] * d1)]
        return [q]

    # Raw offset edges that come out REVERSED (a concave curve tighter than the allowance) are
    # removed and their neighbours re-joined - the standard offset-curve clean-up.
    for _ in range(n if REMOVE_REVERSED_EDGES else 1):
        joins = [join(lines[active[k - 1]], lines[active[k]], points[active[k]]) for k in range(len(active))]
        bad = None
        for k in range(len(active)):
            i = active[k]
            if lines[i][3] <= 0 or len(active) <= 3:
                continue
            start, end = joins[k][-1], joins[(k + 1) % len(active)][0]
            e = lines[i][1]
            if (end[0] - start[0]) * e[0] + (end[1] - start[1]) * e[1] < -1e-9:
                bad = k
                break
        if bad is None:
            break
        del active[bad]
    out = [q for js in joins for q in js]
    return remove_offset_loops(out)


def _seg_intersection(a, b, c, d):
    """Intersection point of segments ab and cd (proper crossing only), else None."""
    r = (b[0] - a[0], b[1] - a[1])
    q = (d[0] - c[0], d[1] - c[1])
    den = r[0] * q[1] - r[1] * q[0]
    if abs(den) < 1e-12:
        return None
    t = ((c[0] - a[0]) * q[1] - (c[1] - a[1]) * q[0]) / den
    u = ((c[0] - a[0]) * r[1] - (c[1] - a[1]) * r[0]) / den
    if 1e-9 < t < 1 - 1e-9 and 1e-9 < u < 1 - 1e-9:
        return (a[0] + t * r[0], a[1] + t * r[1])
    return None


def remove_offset_loops(pts, max_passes=200):
    """
    Trim the inverted loops that an offset creates where a concave curve is tighter than the
    allowance (standard offset-curve clean-up). Loops whose orientation is opposite to the
    polygon are cut out at their crossing point. Deterministic.
    """
    pts = list(pts)
    for _ in range(max_passes):
        n = len(pts)
        overall = _signed_area(pts)
        changed = False
        for i in range(n):
            a, b = pts[i], pts[(i + 1) % n]
            for j in range(i + 2, n):
                if i == 0 and j == n - 1:
                    continue
                x = _seg_intersection(a, b, pts[j], pts[(j + 1) % n])
                if x is None:
                    continue
                loop = [x] + pts[i + 1:j + 1]
                if _signed_area(loop) * overall < 0:          # inverted loop: cut it out
                    pts = pts[:i + 1] + [x] + pts[j + 1:]
                    changed = True
                    break
            if changed:
                break
        if not changed:
            break
    return pts


def point_polyline_distance(pt, poly, fold_line=None):
    """
    Shortest distance from pt to the closed polyline `poly`. Edges lying on `fold_line`
    ((x0,y0),(x1,y1)) are skipped: a fold is not a cut edge.
    """
    best = float("inf")
    n = len(poly)
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        if fold_line is not None and _on_line(a, fold_line) and _on_line(b, fold_line):
            continue
        vx, vy = b[0] - a[0], b[1] - a[1]
        L2 = vx * vx + vy * vy
        t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((pt[0] - a[0]) * vx + (pt[1] - a[1]) * vy) / L2))
        best = min(best, math.hypot(pt[0] - (a[0] + t * vx), pt[1] - (a[1] + t * vy)))
    return best


def _on_line(pt, line, tol=1e-6):
    (x0, y0), (x1, y1) = line
    L = math.hypot(x1 - x0, y1 - y0)
    if L == 0:
        return False
    return abs((x1 - x0) * (pt[1] - y0) - (y1 - y0) * (pt[0] - x0)) / L <= tol


def _point_at_arc(segment, distance_from_start):
    """Point on a segment at a given arc length from its start (Line or Cubic)."""
    pts = segment.flatten(200)
    acc = 0.0
    for i in range(len(pts) - 1):
        d = g.dist(pts[i], pts[i + 1])
        if acc + d >= distance_from_start and d > 0:
            return g.lerp(pts[i], pts[i + 1], (distance_from_start - acc) / d)
        acc += d
    return pts[-1]


def _notch(nid, point, label, kind="single"):
    return {"id": nid, "point": [round(point[0], 4), round(point[1], 4)], "label": label, "kind": kind}


def bodice_notches(piece):
    """Balance marks on a bodice: armhole (front 1, back 2), waist on the side seam."""
    notches = []
    arm = piece.segment("armhole")
    if arm is not None:
        total = arm.length()
        # measured from the underarm (end of the armhole curve) going up
        if piece.piece_type == "front_bodice":
            notches.append(_notch("front_armhole_1", _point_at_arc(arm, total - 0.30 * total), "single notch"))
        else:
            notches.append(_notch("back_armhole_1", _point_at_arc(arm, total - 0.30 * total), "double notch", "double"))
            notches.append(_notch("back_armhole_2", _point_at_arc(arm, total - 0.36 * total), "double notch", "double"))
    if "WAIST_SIDE" in piece.points:
        notches.append(_notch(f"{piece.piece_type}_waist", piece.points["WAIST_SIDE"], "waist"))
    return notches


def sleeve_notches(piece, front_armhole_len, back_armhole_len):
    """Sleeve cap balance marks mirroring the bodice: crown, front (1) and back (2)."""
    left, right = piece.segment("cap_left"), piece.segment("cap_right")
    cap_total = left.length() + right.length()
    armhole_total = front_armhole_len + back_armhole_len
    scale = cap_total / armhole_total if armhole_total else 1.0
    # front = left quadrant (x = 0 side); its notch is 30 % of the front armhole above the underarm
    df = 0.30 * front_armhole_len * scale
    db = 0.30 * back_armhole_len * scale
    notches = [_notch("sleeve_crown", piece.points["CROWN"], "crown", "crown")]
    notches.append(_notch("sleeve_front_1", _point_at_arc(left, df), "single notch"))
    # back = right quadrant, measured from the underarm end (x = width) upward
    rlen = right.length()
    notches.append(_notch("sleeve_back_1", _point_at_arc(right, rlen - db), "double notch", "double"))
    notches.append(_notch("sleeve_back_2", _point_at_arc(right, rlen - db - 0.06 * cap_total), "double notch", "double"))
    return notches


def apply_seam_allowance(piece, block_id):
    """
    Attach real cutting-line geometry to a Piece. Sets:
        piece.allowances   {'seam','neckline','hem','strip'} used (cm)
        piece.cut_outline  closed polygon of the cutting line
        piece.edge_kinds   allowance kind per seam-line edge (parallel to piece.seam_outline)
    """
    table = ALLOWANCES[block_id]
    pts, ids = labelled_outline(piece)
    kinds = [edge_kind(piece, sid) for sid in ids]
    offsets = [0.0 if k == "fold" else table[k] for k in kinds]
    piece.allowances = dict(table)
    piece.seam_allowance_cm = table["seam"] if piece.piece_type not in ("neckband", "armhole_facing") else table["strip"]
    piece.seam_outline = pts
    piece.edge_kinds = kinds
    piece.edge_offsets = offsets
    piece.cut_outline = offset_polygon(pts, offsets)
    return piece
