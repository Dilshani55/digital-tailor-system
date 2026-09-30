"""Seam-allowance geometry, notches, construction validation and product-scope enforcement."""
import unittest

from app.logic import feature_schema as fs
from app.logic.drafting import geometry as g, seam_allowance as sa
from app.logic.drafting.validation import validate_final_pattern
from app.logic.parametric_engine import ParametricEngine
from tests.fixtures import measurements, design

SUPPORTED = (
    [("blouse", n, s) for n in ("round-neck", "v-neck", "square-neck") for s in ("short-sleeve", "long-sleeve")]
    + [("t-shirt", n, s) for n in ("round-neck", "v-neck") for s in ("short-sleeve", "long-sleeve")]
    + [("crop-top", n, s) for n in ("round-neck", "v-neck", "square-neck") for s in ("sleeveless", "short-sleeve")]
)


def _gen(garment, neck, sleeve, profile="medium", fabric=None):
    fabric = fabric or ("knit" if garment == "t-shirt" else "woven")
    style = "none" if sleeve == "sleeveless" else "regular-sleeve"
    over = {"garment_length_cm": 36} if garment == "crop-top" else {}
    m = measurements(profile, fabric_type=fabric, **over)
    return ParametricEngine(m, design_spec={"attributes": design(garment, neck, sleeve, style)}).generate()


class TestOffsetPolygon(unittest.TestCase):
    def test_square_offset_is_exact(self):
        sq = [(0, 0), (10, 0), (10, 10), (0, 10)]
        out = sa.offset_polygon(sq, [1.5] * 4)
        self.assertAlmostEqual(g.polygon_area(out), 13 * 13, places=6)

    def test_per_edge_allowances_and_zero_fold_edge(self):
        sq = [(0, 0), (10, 0), (10, 10), (0, 10)]          # last edge (0,10)->(0,0) is the "fold"
        out = sa.offset_polygon(sq, [1.0, 2.0, 3.0, 0.0])
        xs = [p[0] for p in out]
        ys = [p[1] for p in out]
        self.assertAlmostEqual(min(xs), 0.0)
        self.assertAlmostEqual(max(xs), 12.0)
        self.assertAlmostEqual(min(ys), -1.0)
        self.assertAlmostEqual(max(ys), 13.0)

    def test_orientation_independent(self):
        sq = [(0, 0), (10, 0), (10, 10), (0, 10)]
        a = sa.offset_polygon(sq, [1.0] * 4)
        b = sa.offset_polygon(list(reversed(sq)), [1.0] * 4)
        self.assertAlmostEqual(g.polygon_area(a), g.polygon_area(b), places=6)


class TestFinalPatternSeamAllowance(unittest.TestCase):
    def test_every_supported_design_has_real_valid_cutting_geometry(self):
        for garment, neck, sleeve in SUPPORTED:
            for profile in ("small", "medium", "large"):
                with self.subTest(garment=garment, neck=neck, sleeve=sleeve, profile=profile):
                    out = _gen(garment, neck, sleeve, profile)
                    self.assertTrue(out["validation"]["final_pattern"]["passed"])
                    for p in out["pattern_pieces"]:
                        cut = p["cutting_line"]
                        self.assertGreater(len(cut), 3)
                        self.assertGreater(p["cut_polygon_area_cm2"], p["polygon_area_cm2"])
                        self.assertFalse(g.self_intersections([tuple(q) for q in cut]))
                        self.assertEqual(p["units"], "cm")
                        self.assertTrue(p["notches"] or p["piece_type"] in ("neckband", "armhole_facing"))

    def test_allowance_is_geometric_not_metadata(self):
        out = _gen("blouse", "round-neck", "short-sleeve")
        front = next(p for p in out["pattern_pieces"] if p["piece_type"] == "front_bodice")
        self.assertAlmostEqual(front["cut_bounding_box"]["min_x"], 0.0, places=2)   # fold edge: no allowance
        grow = front["cut_bounding_box"]["width_cm"] - front["bounding_box"]["width_cm"]
        self.assertGreater(grow, 1.0)
        self.assertEqual(front["seam_allowances"]["seam"], 1.5)

    def test_woven_and_knit_use_different_allowances(self):
        woven = _gen("blouse", "round-neck", "short-sleeve")["pattern_pieces"][0]["seam_allowances"]
        knit = _gen("t-shirt", "round-neck", "short-sleeve")["pattern_pieces"][0]["seam_allowances"]
        self.assertNotEqual(woven, knit)
        self.assertGreater(woven["seam"], knit["seam"])

    def test_measured_allowance_matches_specified(self):
        out = _gen("blouse", "v-neck", "long-sleeve")
        sleeve = next(p for p in out["pattern_pieces"] if p["piece_type"] == "sleeve")
        seam = [tuple(q) for q in sleeve["outline"]]
        cut = [tuple(q) for q in sleeve["cutting_line"]]
        checked = 0
        for i in range(len(seam)):
            a, b = seam[i], seam[(i + 1) % len(seam)]
            if g.dist(a, b) > 5 and abs(a[1] - b[1]) > 5:          # long straight underarm seams
                mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
                self.assertAlmostEqual(sa.point_polyline_distance(mid, cut), 1.5, delta=0.06)
                checked += 1
        self.assertGreaterEqual(checked, 2)

    def test_required_pieces_by_design(self):
        def types(out):
            return [p["piece_type"] for p in out["pattern_pieces"]]
        self.assertIn("neckband", types(_gen("t-shirt", "round-neck", "short-sleeve")))
        self.assertIn("armhole_facing", types(_gen("crop-top", "round-neck", "sleeveless")))
        self.assertNotIn("sleeve", types(_gen("crop-top", "round-neck", "sleeveless")))
        self.assertIn("sleeve", types(_gen("blouse", "round-neck", "long-sleeve")))

    def test_engine_notes_do_not_claim_missing_seam_allowance(self):
        notes = " ".join(_gen("blouse", "round-neck", "short-sleeve")["construction_notes"])
        self.assertNotIn("NOT yet included", notes)
        self.assertIn("include seam allowances", notes)

    def test_deterministic(self):
        a, b = _gen("blouse", "round-neck", "short-sleeve"), _gen("blouse", "round-neck", "short-sleeve")
        self.assertEqual(a["pattern_pieces"][0]["cutting_line"], b["pattern_pieces"][0]["cutting_line"])


class TestConstructionValidationFailures(unittest.TestCase):
    def _final(self):
        e = ParametricEngine(measurements(), design_spec={"attributes": design()})
        e.generate()
        return e.final

    def test_missing_cutting_line_fails(self):
        f = self._final()
        f.front.cut_outline = None
        self.assertFalse(validate_final_pattern(f)["passed"])

    def test_self_intersecting_cutting_line_fails(self):
        f = self._final()
        c = f.back.cut_outline
        f.back.cut_outline = c[:5] + [c[20], c[8]] + c[5:]
        self.assertFalse(validate_final_pattern(f)["passed"])

    def test_missing_grainline_fails(self):
        f = self._final()
        f.sleeve.grain = None
        self.assertFalse(validate_final_pattern(f)["passed"])

    def test_fold_piece_without_fold_line_fails(self):
        f = self._final()
        f.front.fold_line = None
        self.assertFalse(validate_final_pattern(f)["passed"])

    def test_notch_off_seam_line_fails(self):
        f = self._final()
        f.front.notches = [dict(f.front.notches[0], point=[999.0, 999.0])]
        self.assertFalse(validate_final_pattern(f)["passed"])

    def test_invalid_cut_quantity_fails(self):
        f = self._final()
        f.sleeve.cut_count = 0
        self.assertFalse(validate_final_pattern(f)["passed"])


class TestProductScope(unittest.TestCase):
    def _report(self, garment, neck, sleeve, style=None):
        style = style or ("none" if sleeve == "sleeveless" else "regular-sleeve")
        clean = {"garment_type": garment, "neckline_type": neck, "sleeve_length": sleeve, "sleeve_style": style}
        return fs.support_report(clean, with_scope=True)

    def test_all_supported_combinations_accepted(self):
        for garment, neck, sleeve in SUPPORTED:
            self.assertTrue(self._report(garment, neck, sleeve)["supported"], (garment, neck, sleeve))

    def test_out_of_scope_combinations_rejected_with_reason(self):
        cases = [("t-shirt", "square-neck", "short-sleeve"), ("blouse", "round-neck", "sleeveless"),
                 ("crop-top", "round-neck", "long-sleeve"), ("blouse", "scoop-neck", "short-sleeve"),
                 ("blouse", "round-neck", "elbow-length"), ("t-shirt", "round-neck", "three-quarter-sleeve")]
        for garment, neck, sleeve in cases:
            r = self._report(garment, neck, sleeve)
            self.assertFalse(r["supported"], (garment, neck, sleeve))
            self.assertTrue(all(u["note"] for u in r["unsupported"]))

    def test_non_regular_sleeve_style_rejected(self):
        self.assertFalse(self._report("t-shirt", "round-neck", "short-sleeve", "puff-sleeve")["supported"])
        self.assertFalse(self._report("t-shirt", "round-neck", "long-sleeve", "bell-sleeve")["supported"])
        self.assertTrue(self._report("blouse", "round-neck", "short-sleeve", "puff-sleeve")["supported"])
        self.assertTrue(self._report("crop-top", "square-neck", "short-sleeve", "bell-sleeve")["supported"])
        self.assertFalse(self._report("blouse", "round-neck", "short-sleeve", "none")["supported"])

    def test_scope_matrix_is_exactly_the_specified_one(self):
        self.assertEqual(set(fs.SCOPE), {"blouse", "t-shirt", "crop-top"})
        self.assertEqual(fs.SCOPE["t-shirt"]["neckline_type"], ("round-neck", "v-neck"))
        self.assertEqual(fs.SCOPE["crop-top"]["sleeve_length"], ("sleeveless", "short-sleeve"))
        s3 = ("regular-sleeve", "puff-sleeve", "bell-sleeve")
        self.assertEqual({g: {n: d["neckline_type"], "sleeves": d["sleeves"]} for g, d in fs.SCOPE.items() for n in ["n"]}, {
            "blouse": {"n": ("round-neck", "v-neck", "square-neck"), "sleeves": {"short-sleeve": s3, "long-sleeve": s3}},
            "t-shirt": {"n": ("round-neck", "v-neck"),
                        "sleeves": {"short-sleeve": ("regular-sleeve",), "long-sleeve": ("regular-sleeve",)}},
            "crop-top": {"n": ("round-neck", "v-neck", "square-neck"),
                         "sleeves": {"sleeveless": ("none",), "short-sleeve": s3}},
        })


if __name__ == "__main__":
    unittest.main()
