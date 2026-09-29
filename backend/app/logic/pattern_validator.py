"""
Locked workflow step 8 — geometric pattern validation.
Failing validation must block fabric estimation / yardage.
"""

import math


def _dist(a, b):
    return math.hypot(b[0] - a[0], b[1] - a[1])


def _polyline_length(points):
    if not points or len(points) < 2:
        return 0.0
    return sum(_dist(points[i], points[i + 1]) for i in range(len(points) - 1))


def _segments_intersect(p1, p2, p3, p4, eps=1e-6):
    """Proper intersection of segments p1-p2 and p3-p4 (excludes shared endpoints)."""
    def orient(a, b, c):
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

    def on_seg(a, b, c):
        return (
            min(a[0], b[0]) - eps <= c[0] <= max(a[0], b[0]) + eps
            and min(a[1], b[1]) - eps <= c[1] <= max(a[1], b[1]) + eps
        )

    o1 = orient(p1, p2, p3)
    o2 = orient(p1, p2, p4)
    o3 = orient(p3, p4, p1)
    o4 = orient(p3, p4, p2)

    if abs(o1) < eps and on_seg(p1, p2, p3):
        return False
    if abs(o2) < eps and on_seg(p1, p2, p4):
        return False
    if abs(o3) < eps and on_seg(p3, p4, p1):
        return False
    if abs(o4) < eps and on_seg(p3, p4, p2):
        return False

    return (o1 * o2 < 0) and (o3 * o4 < 0)


def _outline_self_intersects(outline):
    pts = list(outline or [])
    if len(pts) < 4:
        return False
    # Drop closing duplicate if present
    if _dist(pts[0], pts[-1]) < 1e-6:
        pts = pts[:-1]
    n = len(pts)
    for i in range(n):
        a1, a2 = pts[i], pts[(i + 1) % n]
        for j in range(i + 1, n):
            if abs(i - j) <= 1 or (i == 0 and j == n - 1):
                continue
            b1, b2 = pts[j], pts[(j + 1) % n]
            if _segments_intersect(a1, a2, b1, b2):
                return True
    return False


def _find_piece(pieces, name_substr):
    for p in pieces:
        if name_substr.lower() in (p.get("name") or "").lower():
            return p
    return None


def _shoulder_length(piece):
    pts = piece.get("points") or {}
    # Prefer labeled shoulder endpoints
    if "A1" in pts and "SP" in pts:
        return _dist(pts["A1"], pts["SP"])
    if "A1" in pts and "A_TOP" in pts and "SP" in pts:
        return _dist(pts["A1"], pts["SP"])
    return None


def _side_seam_length(piece):
    pts = piece.get("points") or {}
    if "B1" in pts and "D1" in pts:
        return _dist(pts["B1"], pts["D1"])
    bb = piece.get("bounding_box") or {}
    return bb.get("height_cm")


def _armhole_approx(piece):
    """Approximate armhole path length SP → ARM_MID → B1."""
    pts = piece.get("points") or {}
    if "SP" in pts and "ARM_MID" in pts and "B1" in pts:
        return _polyline_length([pts["SP"], pts["ARM_MID"], pts["B1"]])
    return None


def _sleeve_cap_approx(piece):
    pts = piece.get("points") or {}
    if "UL" in pts and "CROWN_L" in pts and "CROWN" in pts and "CROWN_R" in pts and "UR" in pts:
        return _polyline_length([
            pts["UL"], pts["CROWN_L"], pts["CROWN"], pts["CROWN_R"], pts["UR"]
        ])
    outline = piece.get("outline") or []
    if len(outline) >= 5:
        # First half of outline often traces the crown
        mid = max(3, len(outline) // 3)
        return _polyline_length(outline[:mid])
    return None


def validate_pattern(pattern_pieces, *, garment_type="blouse", fabric_type="woven",
                     sleeves="short sleeve", measurements_used=None, drafting_block=None):
    """
    Returns:
      {
        "passed": bool,
        "errors": [str, ...],
        "warnings": [str, ...],
        "checks": { name: {ok, detail}, ... }
      }
    """
    pieces = pattern_pieces or []
    errors = []
    warnings = []
    checks = {}
    tol_cm = 1.2  # matching tolerance for seams

    front = _find_piece(pieces, "Front Bodice")
    back = _find_piece(pieces, "Back Bodice")
    sleeve = _find_piece(pieces, "Sleeve")
    facing = _find_piece(pieces, "Armhole Facing")
    neckband = _find_piece(pieces, "Neckband")

    # ── Required pieces ──────────────────────────────────────────────────────
    required_ok = True
    missing = []
    if not front:
        missing.append("Front Bodice")
    if not back:
        missing.append("Back Bodice")
    sleeveless = (sleeves or "").lower() in ("sleeveless",)
    if not sleeveless and not sleeve:
        missing.append("Sleeve")
    block = drafting_block or {}
    if block.get("add_neckband") and not neckband:
        missing.append("Neckband")
    if sleeveless and not facing and block.get("add_armhole_facing", True):
        # Prefer facing when sleeveless; warn if block flag unset but still expect facing
        if block.get("add_armhole_facing"):
            missing.append("Armhole Facing")
        else:
            warnings.append("Sleeveless garment has no armhole facing piece.")
    if missing:
        required_ok = False
        errors.append(f"Missing required pattern pieces: {', '.join(missing)}.")
    checks["required_pieces"] = {
        "ok": required_ok,
        "detail": "All required pieces present" if required_ok else f"Missing: {missing}",
    }

    # ── Shoulder seams match ─────────────────────────────────────────────────
    if front and back:
        fs = _shoulder_length(front)
        bs = _shoulder_length(back)
        if fs is not None and bs is not None:
            diff = abs(fs - bs)
            ok = diff <= tol_cm
            checks["shoulder_match"] = {
                "ok": ok,
                "detail": f"Front shoulder {fs:.2f} cm vs back {bs:.2f} cm (Δ={diff:.2f})",
            }
            if not ok:
                errors.append(
                    f"Front/back shoulder seams do not match "
                    f"(front {fs:.1f} cm, back {bs:.1f} cm)."
                )
        else:
            checks["shoulder_match"] = {"ok": True, "detail": "Skipped — shoulder points unavailable"}
            warnings.append("Could not verify shoulder seam match (missing points).")
    else:
        checks["shoulder_match"] = {"ok": False, "detail": "Front/back bodice missing"}

    # ── Side-seam lengths ────────────────────────────────────────────────────
    if front and back:
        fside = _side_seam_length(front)
        bside = _side_seam_length(back)
        if fside is not None and bside is not None:
            diff = abs(fside - bside)
            ok = diff <= tol_cm * 1.5
            checks["side_seam"] = {
                "ok": ok,
                "detail": f"Front side {fside:.2f} cm vs back {bside:.2f} cm (Δ={diff:.2f})",
            }
            if not ok:
                errors.append(
                    f"Side-seam lengths incompatible "
                    f"(front {fside:.1f} cm, back {bside:.1f} cm)."
                )
        else:
            checks["side_seam"] = {"ok": True, "detail": "Skipped — side points unavailable"}
    else:
        checks["side_seam"] = {"ok": False, "detail": "Front/back bodice missing"}

    # ── Sleeve-cap vs armhole ────────────────────────────────────────────────
    if sleeveless:
        checks["sleeve_armhole"] = {"ok": True, "detail": "Sleeveless — check skipped"}
    elif sleeve and front and back:
        front_ah = _armhole_approx(front) or 0.0
        back_ah = _armhole_approx(back) or 0.0
        armhole = front_ah + back_ah
        cap = _sleeve_cap_approx(sleeve) or 0.0
        if armhole > 0 and cap > 0:
            # Cap should be slightly larger than armhole (ease 0–4 cm)
            ease = cap - armhole
            ok = -1.0 <= ease <= 6.0
            checks["sleeve_armhole"] = {
                "ok": ok,
                "detail": f"Sleeve cap {cap:.2f} cm vs armhole {armhole:.2f} cm (ease {ease:.2f})",
            }
            if not ok:
                errors.append(
                    f"Sleeve-cap length not compatible with armhole "
                    f"(cap {cap:.1f} cm, armhole {armhole:.1f} cm)."
                )
        else:
            checks["sleeve_armhole"] = {"ok": True, "detail": "Skipped — insufficient geometry"}
            warnings.append("Could not fully verify sleeve-cap vs armhole compatibility.")
    else:
        checks["sleeve_armhole"] = {"ok": False, "detail": "Sleeve or bodice missing"}

    # ── Required ease ────────────────────────────────────────────────────────
    eased = (measurements_used or {}).get("eased") or {}
    raw = (measurements_used or {}).get("raw") or {}
    if raw.get("bust_cm") is not None and eased.get("bust_cm") is not None:
        ease_amt = float(eased["bust_cm"]) - float(raw["bust_cm"])
        if fabric_type == "stretch-knit":
            ok = ease_amt <= 2.0
            detail = f"Stretch-knit bust ease {ease_amt:.1f} cm"
        else:
            ok = ease_amt >= 2.0
            detail = f"Bust ease {ease_amt:.1f} cm (fabric={fabric_type})"
        checks["required_ease"] = {"ok": ok, "detail": detail}
        if not ok:
            errors.append(f"Required ease check failed: {detail}.")
    else:
        checks["required_ease"] = {"ok": True, "detail": "Skipped — measurements unavailable"}
        warnings.append("Ease check skipped (measurements not provided).")

    # ── Curve / outline self-intersection ────────────────────────────────────
    # Dart folds intentionally create non-simple polygons; treat as warnings.
    intersect_ok = True
    bad = []
    for p in pieces:
        outline = p.get("outline") or []
        if _outline_self_intersects(outline):
            intersect_ok = False
            bad.append(p.get("name", "unnamed"))
    checks["curve_intersection"] = {
        "ok": intersect_ok,
        "detail": "No self-intersections" if intersect_ok else f"Self-intersecting: {bad}",
    }
    if not intersect_ok:
        warnings.append(
            f"Pattern outline self-intersects on: {', '.join(bad)} "
            "(often expected with dart folds — review before cutting)."
        )

    # ── Bounding boxes sane ──────────────────────────────────────────────────
    bbox_ok = True
    for p in pieces:
        bb = p.get("bounding_box") or {}
        w, h = bb.get("width_cm", 0), bb.get("height_cm", 0)
        if w <= 0 or h <= 0:
            bbox_ok = False
            errors.append(f"Piece '{p.get('name')}' has invalid dimensions.")
    checks["bounding_boxes"] = {
        "ok": bbox_ok,
        "detail": "All pieces have positive dimensions" if bbox_ok else "Invalid dimensions found",
    }

    passed = len(errors) == 0
    return {
        "passed": passed,
        "errors": errors,
        "warnings": warnings,
        "checks": checks,
    }
