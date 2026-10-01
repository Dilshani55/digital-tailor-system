"""
Phase 3 — base block: drafting values, ease, front/back geometry, curves, armhole & sleeve cap,
validation. Geometry validation only; nothing here claims professional or fit validation.
"""

import copy
import math
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.logic.block_selection import select_drafting_block
from app.logic.drafting import geometry as g
from app.logic.drafting import sleeve as sleeve_mod
from app.logic.drafting.assumptions import A, ASSUMPTIONS, DERIVED, ASSUMPTION
from app.logic.drafting.base_block import draft_base_block
from app.logic.drafting.drafting_values import compute_drafting_values
from app.logic.drafting.ease import ease_profile_for, DraftingError, WOVEN_BLOCK, KNIT_BLOCK
from app.logic.drafting.pieces import Piece
from app.logic.drafting.validation import validate_piece, validate_base_block
from tests.fixtures import measurements, PROFILES

WOVEN = select_drafting_block("blouse", "woven")
KNIT = select_drafting_block("t-shirt", "knit")


def base(profile="medium", block=WOVEN, **over):
    fabric = "knit" if block is KNIT else "woven"
    return draft_base_block(measurements(profile, fabric_type=fabric, **over), block)


class TestEase(unittest.TestCase):
    def test_body_plus_ease_equals_garment_dimension(self):
        m = measurements("medium")
        dv, rows = compute_drafting_values(m, ease_profile_for(WOVEN_BLOCK))
        self.assertEqual(dv.garment_bust, 88 + 10)          # woven bust ease +10 (project assumption)
        self.assertEqual(dv.garment_waist, 70 + 8)
        self.assertEqual(dv.garment_hip, 94 + 10)
        self.assertEqual((dv.q_bust, dv.q_waist, dv.q_hip), (24.5, 19.5, 26.0))
        self.assertIn("bust 88 + ease 10", next(r for r in rows if r["name"] == "garment_bust")["formula"])

    def test_knit_block_uses_its_own_profile(self):
        w, k = ease_profile_for(WOVEN_BLOCK), ease_profile_for(KNIT_BLOCK)
        self.assertGreater(w.bust_cm, k.bust_cm)
        self.assertEqual((k.bust_cm, k.waist_cm, k.hip_cm), (6.0, 4.0, 6.0))
        self.assertNotEqual((w.bicep_cm, w.sleeve_cap_cm), (k.bicep_cm, k.sleeve_cap_cm))

    def test_fit_preference_shifts_circumference_ease_only(self):
        std, close, loose = (ease_profile_for(WOVEN_BLOCK, f) for f in ("standard", "close", "loose"))
        self.assertEqual(close.bust_cm, std.bust_cm - 2.0)
        self.assertEqual(loose.hip_cm, std.hip_cm + 3.0)
        self.assertEqual(close.bicep_cm, std.bicep_cm)

    def test_unknown_block_or_fit_is_an_error(self):
        with self.assertRaises(DraftingError):
            ease_profile_for("stretch_block")
        with self.assertRaises(DraftingError):
            ease_profile_for(WOVEN_BLOCK, "skin-tight")

    def test_stretch_knit_negative_ease_is_not_drafted(self):
        with self.assertRaises(DraftingError) as ctx:
            draft_base_block(measurements(fabric_type="stretch-knit"), KNIT)
        self.assertEqual(ctx.exception.code, "UNSUPPORTED_FABRIC_TYPE")

    def test_engine_can_explain_which_ease_was_used(self):
        b = base()
        self.assertEqual(b.ease.bust_cm, 10.0)
        self.assertIn("ease", b.to_dict())
        self.assertEqual(b.to_dict()["ease"]["status"], ASSUMPTION)


class TestDraftingValues(unittest.TestCase):
    def setUp(self):
        self.dv, self.rows = compute_drafting_values(measurements("medium"), ease_profile_for(WOVEN_BLOCK))

    def test_explicit_values_for_the_medium_profile(self):
        dv = self.dv
        self.assertAlmostEqual(dv.neck_half_width, 6.0)                  # neck 36 / 6
        self.assertAlmostEqual(dv.front_neck_depth, 7.0)                 # 6 + 1
        self.assertAlmostEqual(dv.back_neck_depth, 2.0)
        self.assertAlmostEqual(dv.waist_y, 42.0)                         # 2 + back waist length 40
        self.assertAlmostEqual(dv.hip_y, 62.0)                           # + 20 (assumption)
        self.assertAlmostEqual(dv.across_back_half, 17.0)
        self.assertAlmostEqual(dv.suppression, 5.0)                      # 24.5 - 19.5
        self.assertAlmostEqual(dv.bicep_width, 33.0)                     # 28 + 5
        self.assertAlmostEqual(dv.wrist_width, 20.0)                     # 16 + 4
        self.assertEqual(dv.armhole_depth, 20.0)
        self.assertEqual(dv.shoulder_length, 12.0)

    def test_every_row_has_formula_and_status(self):
        for row in self.rows:
            self.assertIn(row["status"], (DERIVED, ASSUMPTION))
            self.assertTrue(row["formula"])

    def test_no_row_claims_aldrich_provenance(self):
        text = repr(self.rows) + repr(ASSUMPTIONS)
        self.assertNotIn("Aldrich", text)
        for meta in ASSUMPTIONS.values():
            self.assertIn(meta["status"], (DERIVED, ASSUMPTION))

    def test_missing_or_invalid_measurement_raises(self):
        for key in ("neck_cm", "armhole_depth_cm", "garment_length_cm"):      # bodice: always needed
            m = measurements()
            m[key] = None
            with self.assertRaises(DraftingError):
                compute_drafting_values(m, ease_profile_for(WOVEN_BLOCK))
        for bad in (float("nan"), -1, 0):
            with self.assertRaises(DraftingError):
                compute_drafting_values(measurements(neck_cm=bad), ease_profile_for(WOVEN_BLOCK))
            with self.assertRaises(DraftingError):                           # optional, but invalid if given
                compute_drafting_values(measurements(wrist_cm=bad), ease_profile_for(WOVEN_BLOCK))

    def test_design_specific_measurements_may_be_absent_and_are_not_invented(self):
        m = measurements(hip_cm=None, bicep_cm=None, sleeve_cm=None, wrist_cm=None, height_cm=None)
        dv, rows = compute_drafting_values(m, ease_profile_for(WOVEN_BLOCK))
        for value in (dv.garment_hip, dv.q_hip, dv.bicep_width, dv.sleeve_length, dv.wrist_width):
            self.assertIsNone(value)
        names = {r["name"] for r in rows}
        self.assertNotIn("garment_hip", names)
        self.assertNotIn("sleeve_width_bicep", names)

    def test_sleeveless_base_block_has_no_sleeve(self):
        b = base(bicep_cm=None, sleeve_cm=None, wrist_cm=None)
        self.assertIsNone(b.sleeve)
        self.assertEqual(len(b.pieces), 2)
        self.assertTrue(b.validation["passed"], b.validation["errors"])
        self.assertNotIn("cap_height_cm", b.armhole)

    def test_undraftable_combinations_are_reported_per_field(self):
        cases = [
            ("across_back_cm", dict(across_back_cm=50)),                       # wider than the garment
            ("armhole_depth_cm", dict(armhole_depth_cm=30, back_waist_length_cm=30)),
            ("bicep_cm", dict(bicep_cm=18, wrist_cm=24)),                      # wrist wider than bicep
        ]
        for field, over in cases:
            with self.assertRaises(DraftingError) as ctx:
                compute_drafting_values(measurements(**over), ease_profile_for(WOVEN_BLOCK))
            self.assertEqual(ctx.exception.code, "MEASUREMENTS_NOT_DRAFTABLE")
            self.assertIn(field, ctx.exception.field_errors)


class TestCurves(unittest.TestCase):
    def test_bezier_endpoints_and_control_points_are_kept(self):
        curve = g.Cubic("c", (0, 0), (0, 1), (1, 2), (3, 3))
        self.assertEqual(curve.point(0), (0, 0))
        self.assertEqual(curve.point(1), (3, 3))
        d = curve.to_dict()
        self.assertEqual(d["type"], "cubic")
        self.assertEqual(len(d["p"]), 4)

    def test_arc_length_of_a_quarter_circle(self):
        quarter = g.quarter_ellipse("q", (0, 1), (1, 0), (0, 0), first_axis="vertical")   # radius-1 quadrant
        self.assertAlmostEqual(quarter.length(), math.pi / 2, places=3)

    def test_straight_cubic_length_equals_distance(self):
        line_like = g.Cubic("l", (0, 0), (1, 0), (2, 0), (3, 0))
        self.assertAlmostEqual(line_like.length(), 3.0, places=6)

    def test_pieces_keep_real_curve_data_not_just_points(self):
        piece = base().front
        armhole = piece.segment("armhole")
        self.assertEqual(armhole.kind, "cubic")
        d = piece.to_dict()
        seg = next(s for s in d["segments"] if s["id"] == "armhole")
        self.assertEqual(seg["type"], "cubic")
        self.assertEqual(len(seg["p"]), 4)
        # the true curve is reconstructable from the API data and passes through the piece points
        self.assertEqual(seg["p"][0], d["points"]["SHOULDER_POINT"])
        self.assertEqual(seg["p"][3], d["points"]["UNDERARM"])

    def test_flattened_outline_is_derived_from_the_segments(self):
        piece = base().back
        outline = piece.outline
        for seg in piece.segments:
            self.assertTrue(any(g.dist(seg.start, p) < 1e-9 for p in outline))
            self.assertTrue(any(g.dist(seg.end, p) < 1e-9 for p in outline))
        self.assertGreater(len(outline), len(piece.segments) * 2)          # curves contributed extra points

    def test_armhole_is_not_the_old_three_point_polyline(self):
        armhole = base().front.segment("armhole")
        self.assertGreaterEqual(len(armhole.flatten()), g.FLATTEN_STEPS + 1)


class TestPolygonTools(unittest.TestCase):
    def test_simple_and_bowtie(self):
        square = [(0, 0), (2, 0), (2, 2), (0, 2)]
        bowtie = [(0, 0), (2, 2), (2, 0), (0, 2)]
        self.assertEqual(g.self_intersections(square), [])
        self.assertTrue(g.self_intersections(bowtie))
        self.assertAlmostEqual(g.polygon_area(square), 4.0)

    def test_touching_non_adjacent_edges_count(self):
        pinched = [(0, 0), (4, 0), (4, 4), (2, 0), (0, 4)]                  # vertex lies on another edge
        self.assertTrue(g.self_intersections(pinched))

    def test_point_in_polygon(self):
        sq = [(0, 0), (4, 0), (4, 4), (0, 4)]
        self.assertTrue(g.point_in_polygon((2, 2), sq))
        self.assertTrue(g.point_in_polygon((0, 2), sq))                     # boundary counts
        self.assertFalse(g.point_in_polygon((5, 2), sq))


class TestBaseBlockValidity(unittest.TestCase):
    def test_valid_for_three_profiles_and_both_blocks(self):
        for profile in PROFILES:
            for block in (WOVEN, KNIT):
                b = base(profile, block)
                self.assertTrue(b.validation["passed"], (profile, block["block_id"], b.validation["errors"]))
                for piece in b.pieces:
                    pts = piece.outline
                    self.assertEqual(g.self_intersections(pts), [], (profile, piece.name))
                    self.assertTrue(g.all_finite(pts))
                    self.assertGreater(g.polygon_area(pts), 100.0)

    def test_all_pieces_closed_connected_positive(self):
        for piece in base().pieces:
            self.assertTrue(g.path_is_connected(piece.segments))
            self.assertLess(g.dist(piece.segments[-1].end, piece.segments[0].start), 1e-9)
            x0, y0, x1, y1 = g.bbox(piece.outline)
            self.assertGreaterEqual(x0, -1e-9)
            self.assertGreaterEqual(y0, -1e-9)
            self.assertGreater(x1 - x0, 5)
            self.assertGreater(y1 - y0, 5)

    def test_base_block_is_waist_length_with_round_neck(self):
        b = base()
        self.assertAlmostEqual(b.front.meta["hem_y_cm"], b.dv.waist_y)
        self.assertEqual(b.front.segment("neckline").kind, "cubic")
        self.assertEqual(b.sleeve.meta["sleeve_kind"], "block")
        self.assertAlmostEqual(b.sleeve.meta["length_cm"], b.dv.sleeve_length)          # the wanted length

    def test_key_dimensions_derive_from_measurements(self):
        b = base("medium")
        self.assertAlmostEqual(b.front.points["UNDERARM"][0], 24.5)             # quarter garment bust
        self.assertAlmostEqual(b.front.points["UNDERARM"][1], 20.0)             # measured armhole depth
        self.assertAlmostEqual(b.back.meta["shoulder_length_cm"], 12.0, places=6)   # measured shoulder
        self.assertAlmostEqual(b.back.points["NECK_POINT"][0], 6.0)             # neck / 6
        big = base("large")
        self.assertGreater(big.front.points["UNDERARM"][0], b.front.points["UNDERARM"][0])

    def test_deterministic_output(self):
        a, b = base().to_dict(), base().to_dict()
        self.assertEqual(a, b)


class TestFrontBackStructure(unittest.TestCase):
    def setUp(self):
        self.b = base()

    def test_shoulder_side_seam_and_waist_alignment(self):
        f, k = self.b.front, self.b.back
        self.assertAlmostEqual(f.meta["shoulder_length_cm"], k.meta["shoulder_length_cm"], places=6)
        self.assertAlmostEqual(f.meta["side_seam_length_cm"], k.meta["side_seam_length_cm"], places=6)
        self.assertAlmostEqual(f.meta["side_seam_x_at_waist_cm"], k.meta["side_seam_x_at_waist_cm"], places=6)
        self.assertEqual(f.points["UNDERARM"], k.points["UNDERARM"])

    def test_waist_circumference_adds_up(self):
        for piece in (self.b.front, self.b.back):
            net = 4 * (piece.meta["side_seam_x_at_waist_cm"] - piece.meta["dart_intake_cm"])
            self.assertAlmostEqual(net, self.b.dv.garment_waist, places=6)

    def test_back_is_not_a_copy_of_the_front(self):
        f, k = self.b.front.to_dict(), self.b.back.to_dict()
        self.assertNotEqual(f["outline"], k["outline"])
        self.assertGreater(f["points"]["CENTRE_NECK"][1], k["points"]["CENTRE_NECK"][1])   # deeper front neck
        self.assertNotEqual(f["darts"][0]["apex"], k["darts"][0]["apex"])                   # different dart
        self.assertIn("BUST_POINT", f["points"])
        self.assertNotIn("BUST_POINT", k["points"])
        self.assertNotAlmostEqual(self.b.front.meta["armhole_length_cm"], self.b.back.meta["armhole_length_cm"], places=2)

    def test_darts_are_internal_and_do_not_break_the_outline(self):
        for piece in (self.b.front, self.b.back):
            self.assertEqual(len(piece.darts), 1)
            self.assertEqual(piece.darts[0]["type"], "open")
            self.assertEqual(g.self_intersections(piece.outline), [])
            d = piece.darts[0]
            self.assertTrue(g.point_in_polygon(tuple(d["apex"]), piece.outline))
            self.assertAlmostEqual(g.dist(d["leg_a"], d["leg_b"]), d["intake_cm"], places=3)
            self.assertAlmostEqual(d["leg_a"][1], piece.meta["hem_y_cm"])        # open dart ends on the waist edge

    def test_knit_block_has_no_darts_and_side_seam_takes_all_suppression(self):
        k = base("medium", KNIT)
        self.assertEqual(k.front.darts, [])
        self.assertAlmostEqual(k.front.meta["side_seam_suppression_cm"], k.dv.suppression)

    def test_previous_self_intersecting_front_bodice_is_fixed(self):
        """Regression: the old front outline folded the dart into the outer polygon and crossed itself."""
        for profile in PROFILES:
            self.assertEqual(g.self_intersections(base(profile).front.outline), [], profile)

    def test_dart_intake_is_capped_and_excess_goes_to_the_side_seam(self):
        wide = base("medium", fit_preference="close")           # bust-waist difference stays 5
        self.assertLessEqual(wide.front.meta["dart_intake_cm"], A["max_dart_intake_cm"])
        big = draft_base_block(measurements("large", waist_cm=62, hip_cm=112), WOVEN)  # very large suppression
        self.assertLessEqual(big.front.meta["dart_intake_cm"], A["max_dart_intake_cm"])
        total = big.front.meta["dart_intake_cm"] + big.front.meta["side_seam_suppression_cm"]
        self.assertAlmostEqual(total, big.dv.suppression, places=6)


class TestArmholeAndSleeveCap(unittest.TestCase):
    def test_armhole_seam_lengths_are_measured_from_the_curves(self):
        b = base()
        for piece in (b.front, b.back):
            armhole = piece.segment("armhole")
            polyline = armhole.flatten(g.LENGTH_STEPS)
            manual = sum(g.dist(polyline[i], polyline[i + 1]) for i in range(len(polyline) - 1))
            self.assertAlmostEqual(piece.meta["armhole_length_cm"], manual, places=6)
        self.assertAlmostEqual(b.armhole["total_armhole_seam_cm"],
                               b.front.meta["armhole_length_cm"] + b.back.meta["armhole_length_cm"], places=6)
        self.assertGreater(b.armhole["total_armhole_seam_cm"], 30)
        self.assertLess(b.armhole["total_armhole_seam_cm"], 60)

    def test_sleeve_cap_equals_armhole_plus_target_ease(self):
        for profile in PROFILES:
            for block in (WOVEN, KNIT):
                b = base(profile, block)
                cap = b.sleeve.meta["cap_length_cm"]
                self.assertAlmostEqual(cap, b.armhole["total_armhole_seam_cm"] + b.dv.sleeve_cap_ease, delta=0.01)
                self.assertAlmostEqual(b.armhole["cap_ease_cm"], b.dv.sleeve_cap_ease, delta=0.01)

    def test_cap_height_is_solved_not_a_fixed_fraction_of_armhole_depth(self):
        """Regression for the old `sleeve_head = 0.75 * armhole_depth`."""
        b = base()
        old_rule = 0.75 * b.dv.armhole_depth
        self.assertNotAlmostEqual(b.sleeve.meta["cap_height_cm"], old_rule, delta=1.0)
        heights = {round(base(p).sleeve.meta["cap_height_cm"], 3) for p in PROFILES}
        self.assertEqual(len(heights), 3)                       # depends on the actual armhole geometry

    def test_cap_length_grows_with_cap_height_monotonically(self):
        lengths = [sleeve_mod.cap_length(33, h) for h in (2, 5, 8, 12, 16)]
        self.assertEqual(lengths, sorted(lengths))

    def test_sleeve_too_wide_for_armhole_is_a_structured_failure(self):
        with self.assertRaises(DraftingError) as ctx:
            draft_base_block(measurements("small", bicep_cm=50, wrist_cm=14.5), WOVEN)
        self.assertEqual(ctx.exception.code, "SLEEVE_TOO_WIDE_FOR_ARMHOLE")
        self.assertIn("bicep_cm", ctx.exception.field_errors)

    def test_validation_reports_armhole_and_cap_numbers(self):
        info = base().validation["armhole_sleeve"]
        for key in ("front_armhole_seam_cm", "back_armhole_seam_cm", "total_armhole_seam_cm",
                    "sleeve_cap_seam_cm", "cap_ease_cm"):
            self.assertIn(key, info)
        self.assertAlmostEqual(info["cap_ease_cm"], info["sleeve_cap_seam_cm"] - info["total_armhole_seam_cm"], places=2)

    def test_sleeve_piece_geometry(self):
        s = base().sleeve
        d = s.to_dict()
        self.assertEqual(d["cut_count"], 2)
        self.assertFalse(d["cut_on_fold"])
        self.assertEqual(g.self_intersections(s.outline), [])
        self.assertGreater(s.meta["width_bicep_cm"], s.meta["width_hem_cm"])          # tapers to the wrist
        self.assertAlmostEqual(s.meta["width_hem_cm"], base().dv.wrist_width, places=6)   # full length = wrist width


class TestValidatorFailsBadGeometry(unittest.TestCase):
    def _piece(self, segments, ptype="strip"):
        return Piece("Test", ptype, segments, {"A": (0, 0)}, cut_count=1, cut_on_fold=False,
                     grain=((0, 0), (0, 1)))

    def test_self_intersecting_outline_is_an_error_not_a_warning(self):
        bowtie = [g.Line("a", (0, 0), (10, 10)), g.Line("b", (10, 10), (10, 0)),
                  g.Line("c", (10, 0), (0, 10)), g.Line("d", (0, 10), (0, 0))]
        res = validate_piece(self._piece(bowtie))
        out = res.dump()
        self.assertFalse(out["passed"])
        self.assertTrue(any("self-intersects" in e for e in out["errors"]))
        self.assertEqual(out["warnings"], [])

    def test_non_finite_coordinates_fail(self):
        segs = [g.Line("a", (0, 0), (float("nan"), 5)), g.Line("b", (float("nan"), 5), (0, 5)), g.Line("c", (0, 5), (0, 0))]
        self.assertFalse(validate_piece(self._piece(segs)).dump()["passed"])

    def test_unclosed_and_disconnected_outlines_fail(self):
        unclosed = [g.Line("a", (0, 0), (10, 0)), g.Line("b", (10, 0), (10, 10)), g.Line("c", (10, 10), (0, 10))]
        self.assertFalse(validate_piece(self._piece(unclosed)).dump()["passed"])
        gap = [g.Line("a", (0, 0), (10, 0)), g.Line("b", (11, 0), (10, 10)), g.Line("c", (10, 10), (0, 0))]
        self.assertFalse(validate_piece(self._piece(gap)).dump()["passed"])

    def test_degenerate_and_negative_geometry_fail(self):
        sliver = [g.Line("a", (0, 0), (10, 0)), g.Line("b", (10, 0), (10, 0.1)), g.Line("c", (10, 0.1), (0, 0))]
        self.assertFalse(validate_piece(self._piece(sliver)).dump()["passed"])
        negative = [g.Line("a", (-5, 0), (10, 0)), g.Line("b", (10, 0), (10, 10)),
                    g.Line("c", (10, 10), (-5, 10)), g.Line("d", (-5, 10), (-5, 0))]
        out = validate_piece(self._piece(negative)).dump()
        self.assertFalse(out["passed"])
        self.assertTrue(any("negative" in e for e in out["errors"]))

    def test_missing_required_points_fail(self):
        b = base()
        broken = copy.copy(b.front)
        broken.points = {k: v for k, v in b.front.points.items() if k != "BUST_POINT"}
        out = validate_piece(broken).dump()
        self.assertFalse(out["passed"])
        self.assertTrue(any("missing required points" in e for e in out["errors"]))

    def test_dart_outside_the_piece_fails(self):
        b = base()
        broken = copy.copy(b.front)
        broken.darts = [dict(b.front.darts[0], apex=[200.0, 300.0])]
        self.assertFalse(validate_piece(broken).dump()["passed"])

    def test_base_block_validation_catches_a_tampered_piece(self):
        b = base()
        good = validate_base_block(b)
        self.assertTrue(good["passed"])
        b.front.segments[3] = g.Line("side_seam_1", b.front.segments[3].start, (0.0, 5.0))   # wreck the side seam
        bad = validate_base_block(b)
        self.assertFalse(bad["passed"])
        self.assertTrue(bad["errors"])

    def test_broken_sleeve_cap_ease_fails(self):
        b = base()
        b.sleeve.meta = dict(b.sleeve.meta, cap_length_cm=b.armhole["total_armhole_seam_cm"] + 9.0)
        out = validate_base_block(b)
        self.assertFalse(out["passed"])
        self.assertTrue(any("Sleeve cap" in e for e in out["errors"]))

    def test_generation_stops_when_validation_fails(self):
        import app.logic.drafting.base_block as bb
        original = bb.validate_base_block
        bb.validate_base_block = lambda _b: {"passed": False, "errors": ["forced failure"], "warnings": [], "checks": {}}
        try:
            with self.assertRaises(DraftingError) as ctx:
                base()
            self.assertEqual(ctx.exception.code, "BASE_BLOCK_INVALID")
            self.assertIn("forced failure", ctx.exception.message)
        finally:
            bb.validate_base_block = original


class TestSolver(unittest.TestCase):
    def test_bisection(self):
        self.assertAlmostEqual(g.solve_monotone(lambda x: x * x, 0, 10, 49), 7.0, places=6)
        self.assertIsNone(g.solve_monotone(lambda x: x, 0, 1, 5))


if __name__ == "__main__":
    unittest.main()
