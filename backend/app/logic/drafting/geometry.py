"""
Deterministic 2-D geometry primitives for pattern drafting (all lengths in cm).

Curves are cubic Bezier segments. Their control points are KEPT in the API output
(`segments`) so the true curve can be reconstructed by any renderer; the flattened
`outline` is derived from them, never the other way round.

Coordinate convention for every piece: x to the right, y DOWN (screen style),
piece-local origin. Nothing here is random; identical input gives identical output.
"""

import math

FLATTEN_STEPS = 24          # polyline segments per curve for outlines / intersection tests
LENGTH_STEPS = 400          # polyline segments used for arc-length measurement
EPS = 1e-9


def dist(a, b):
    return math.hypot(b[0] - a[0], b[1] - a[1])


def lerp(a, b, t):
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


class Line:
    kind = "line"

    def __init__(self, seg_id, p0, p1):
        self.id, self.p = seg_id, (tuple(p0), tuple(p1))

    @property
    def start(self):
        return self.p[0]

    @property
    def end(self):
        return self.p[-1]

    def point(self, t):
        return lerp(self.p[0], self.p[1], t)

    def length(self):
        return dist(self.p[0], self.p[1])

    def flatten(self, steps=None):
        return [self.p[0], self.p[1]]

    def to_dict(self):
        return {"id": self.id, "type": "line", "p": [list(map(_r, q)) for q in self.p]}


class Cubic:
    kind = "cubic"

    def __init__(self, seg_id, p0, p1, p2, p3):
        self.id, self.p = seg_id, (tuple(p0), tuple(p1), tuple(p2), tuple(p3))

    @property
    def start(self):
        return self.p[0]

    @property
    def end(self):
        return self.p[3]

    def point(self, t):
        p0, p1, p2, p3 = self.p
        u = 1 - t
        return (
            u ** 3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t ** 3 * p3[0],
            u ** 3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t ** 3 * p3[1],
        )

    def flatten(self, steps=FLATTEN_STEPS):
        return [self.point(i / steps) for i in range(steps + 1)]

    def length(self):
        pts = self.flatten(LENGTH_STEPS)
        return sum(dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1))

    def to_dict(self):
        return {"id": self.id, "type": "cubic", "p": [list(map(_r, q)) for q in self.p]}


def _r(v):
    return round(float(v), 4)


def quarter_ellipse(seg_id, start, end, corner, *, first_axis):
    """
    Cubic approximation (kappa = 0.5523) of an elliptical quadrant from `start` to `end`.
    `corner` is the point the curve bulges towards (the rectangle corner opposite the
    ellipse centre). first_axis='vertical' leaves `start` vertically, arrives `end`
    horizontally; 'horizontal' is the reverse. Deterministic, derived geometry.
    """
    k = 0.5522847498
    if first_axis == "vertical":
        c1 = (start[0], start[1] + k * (corner[1] - start[1]))
        c2 = (end[0] + k * (corner[0] - end[0]), end[1])
    else:
        c1 = (start[0] + k * (corner[0] - start[0]), start[1])
        c2 = (end[0], end[1] + k * (corner[1] - end[1]))
    return Cubic(seg_id, start, c1, c2, end)


# ── paths / polygons ─────────────────────────────────────────────────────────
def path_is_connected(segments, tol=1e-6):
    return all(dist(segments[i].end, segments[i + 1].start) <= tol for i in range(len(segments) - 1))


def flatten_path(segments, steps=FLATTEN_STEPS):
    """Concatenate segment polylines into one point list (shared endpoints not repeated)."""
    pts = []
    for seg in segments:
        seg_pts = seg.flatten(steps)
        pts.extend(seg_pts if not pts else seg_pts[1:])
    return pts


def polygon_area(points):
    """Signed-magnitude shoelace area of a simple polygon (closing edge implied)."""
    n = len(points)
    if n < 3:
        return 0.0
    s = 0.0
    for i in range(n):
        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % n]
        s += x1 * y2 - x2 * y1
    return abs(s) / 2.0


def bbox(points):
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return min(xs), min(ys), max(xs), max(ys)


def _orient(a, b, c):
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _on_segment(a, b, c, tol=1e-9):
    return (min(a[0], b[0]) - tol <= c[0] <= max(a[0], b[0]) + tol
            and min(a[1], b[1]) - tol <= c[1] <= max(a[1], b[1]) + tol)


def segments_intersect(p1, p2, p3, p4, tol=1e-9):
    """True if closed segments p1p2 and p3p4 share ANY point (touching counts)."""
    o1, o2 = _orient(p1, p2, p3), _orient(p1, p2, p4)
    o3, o4 = _orient(p3, p4, p1), _orient(p3, p4, p2)
    if ((o1 > tol and o2 < -tol) or (o1 < -tol and o2 > tol)) and \
       ((o3 > tol and o4 < -tol) or (o3 < -tol and o4 > tol)):
        return True
    if abs(o1) <= tol and _on_segment(p1, p2, p3):
        return True
    if abs(o2) <= tol and _on_segment(p1, p2, p4):
        return True
    if abs(o3) <= tol and _on_segment(p3, p4, p1):
        return True
    if abs(o4) <= tol and _on_segment(p3, p4, p2):
        return True
    return False


def self_intersections(points, tol=1e-9):
    """
    Return [(i, j), ...] for every pair of NON-ADJACENT edges of the closed polygon that
    touch or cross. A simple polygon returns []. Adjacent edges share exactly one vertex
    and are excluded; collinear overlap of adjacent edges is reported separately.
    """
    pts = list(points)
    if len(pts) > 1 and dist(pts[0], pts[-1]) <= tol:
        pts = pts[:-1]
    n = len(pts)
    found = []
    for i in range(n):
        a1, a2 = pts[i], pts[(i + 1) % n]
        for j in range(i + 1, n):
            if j == i + 1 or (i == 0 and j == n - 1):
                continue
            b1, b2 = pts[j], pts[(j + 1) % n]
            if segments_intersect(a1, a2, b1, b2, tol):
                found.append((i, j))
    # adjacent edges that fold back onto each other (zero-angle spike)
    for i in range(n):
        a, b, c = pts[i], pts[(i + 1) % n], pts[(i + 2) % n]
        if abs(_orient(a, b, c)) <= tol and \
                ((b[0] - a[0]) * (c[0] - b[0]) + (b[1] - a[1]) * (c[1] - b[1])) < -tol:
            found.append((i, (i + 1) % n))
    return found


def point_in_polygon(pt, points):
    """Ray casting; boundary points count as inside."""
    x, y = pt
    inside = False
    n = len(points)
    for i in range(n):
        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % n]
        if _on_segment((x1, y1), (x2, y2), pt) and abs(_orient((x1, y1), (x2, y2), pt)) <= 1e-9:
            return True
        if (y1 > y) != (y2 > y):
            xin = (x2 - x1) * (y - y1) / (y2 - y1) + x1
            if x < xin:
                inside = not inside
    return inside


def point_on_polyline(pt, points, tol=1e-6):
    for i in range(len(points)):
        a, b = points[i], points[(i + 1) % len(points)]
        if abs(_orient(a, b, pt)) <= tol * max(1.0, dist(a, b)) and _on_segment(a, b, pt, tol):
            return True
    return False


def all_finite(points):
    return all(math.isfinite(c) for p in points for c in p)


def solve_monotone(fn, lo, hi, target, iters=80):
    """Bisection for an increasing fn(x) == target on [lo, hi]. Returns None if not bracketed."""
    flo, fhi = fn(lo), fn(hi)
    if not (flo <= target <= fhi):
        return None
    for _ in range(iters):
        mid = (lo + hi) / 2.0
        if fn(mid) < target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0
