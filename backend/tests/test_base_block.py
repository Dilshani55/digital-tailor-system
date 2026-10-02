"""
The drafting engine against its drafting method (app/logic/drafting/assumptions.py; docs/pattern-drafting-method.md).

GOLDEN TEST: the source works its draft through for a sample figure (bust 34 in, waist 26 in, back width 14 in,
back waist length 14 in, shoulder to bust 9 in, bust points 6 1/2 in apart, sleeve length 7 in) and prints the
resulting dimensions. Those printed values are the expected values here; the engine must reproduce them from the
same measurements. Tolerance: 1 mm for straight dimensions (the source rounds to 1/8 or 1/4 in); curve lengths are
not given by the source and are checked for consistency instead.

Geometry validation only; nothing here claims a fit validation.
"""
import math
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.logic.block_selection import select_drafting_block
from app.logic.drafting import bodice, geometry as g, sleeve
from app.logic.drafting.assumptions import (A, CONSTANTS, EASE_PRESETS, SEAM_ALLOWANCES, SOURCE,
                                            METHOD, FIGURE, DESIGN, EASE, EXTENSION, assumptions_payload)
from app.logic.drafting.base_block import draft_base_block
from app.logic.drafting.drafting_values import compute_drafting_values, method_armhole_depth
from app.logic.drafting.ease import DraftingError, ease_profile_for
from app.logic.drafting.validation import validate_base_block
from tests.fixtures import measurements, PROFILES, SOURCE_SAMPLE, IN

MM = 0.1


def base(profile="medium", garment="blouse", fabric="woven", fit="standard", **over):
    return draft_base_block(measurements(profile, fabric_type=fabric, **over), select_drafting_block(garment, fabric), fit)


def sample(**over):
    m = dict(SOURCE_SAMPLE, fabric_type="woven", fit_preference="standard", **over)
    return draft_base_block(m, select_drafting_block("blouse", "woven"), "standard")


class TestGoldenSourceSample(unittest.TestCase):
    """Expected values are the numbers printed in the source for its own sample (inches)."""

    @classmethod
    def setUpClass(cls):
        cls.b = sample()
        cls.dv = cls.b.dv

    def inches(self, value_cm, expected_in, tol_cm=MM):
        self.assertAlmostEqual(value_cm, expected_in * IN, delta=tol_cm, msg=f"{value_cm / IN:.3f} in, expected {expected_in}")

    def test_block_width_is_half_bust_plus_one_and_three_quarters(self):
        # AB = 1/2 (bust + 3 1/2 in ease) = 18 3/4 in, the two half pieces together
        self.inches(self.dv.back_width + self.dv.front_width, 18.75)
        self.inches(self.dv.back_width, 18.75 / 2 - 0.5)          # AE = 1/2 AB - 1/2 in
        self.inches(self.dv.front_width, 18.75 / 2 + 0.5)
        self.inches(self.dv.front_width - self.dv.back_width, 1.0)  # "front width 2 in larger than the back" all round

    def test_block_length_is_back_waist_length_plus_half_an_inch(self):
        self.inches(self.dv.waist_y, 14.5)                         # BC = 14 1/2 in

    def test_back_neck_and_shoulder(self):
        self.inches(self.dv.neck_half_back, 2.75, tol_cm=0.25)     # AH: the source rounds 34/12 = 2.83 to 2 3/4
        self.assertAlmostEqual(self.dv.neck_half_back, 34 * IN / 12, places=9)
        self.inches(self.dv.back_neck_depth, 1.0)                  # AJ = 1 in
        self.inches(self.dv.shoulder_half, 7.0)                    # AG = 1/2 back width = 7 in
        self.inches(self.dv.shoulder_drop, 1.0)                    # GK = 1 in
        back = self.b.back
        self.assertEqual(back.points["NECK_POINT"], (self.dv.neck_half_back, 0.0))
        self.inches(back.points["SHOULDER_POINT"][0], 7.0)
        self.inches(back.points["SHOULDER_POINT"][1], 1.0)
        self.inches(back.points["CENTRE_NECK"][1], 1.0)

    def test_armhole_depth_is_a_quarter_bust_minus_one_inch(self):
        self.inches(self.dv.armhole_depth, 7.5)                    # EO = 7 1/2 in
        self.inches(self.b.back.points["UNDERARM"][1], 7.5)

    def test_back_armhole_runs_straight_for_a_third(self):
        line = self.b.back.segment("armhole_1")
        self.assertEqual(line.kind, "line")
        self.assertAlmostEqual(line.start[0], line.end[0])         # straight down from the shoulder tip
        self.inches(line.length(), 6.5 / 3, tol_cm=0.01)           # KX = 1/3 KL (the source: "2 1/4 in approximately")

    def test_front_neck_shoulder_and_armhole_points(self):
        dv, front = self.dv, self.b.front
        self.inches(dv.front_shoulder_x, 6.75)                     # BG1 = 6 3/4 in
        self.inches(dv.neck_half_front, 2.5, tol_cm=0.25)          # BH1 = AH - 1/4 = 2 1/2 in
        self.assertAlmostEqual(dv.neck_half_back - dv.neck_half_front, 0.25 * IN, places=9)
        self.assertAlmostEqual(dv.front_neck_depth, 34 * IN / 12 + 0.25 * IN, places=9)     # BJ1 = 1/12 bust + 1/4 in
        self.inches(dv.front_raise, 0.375)                         # H2: 1/4 to 1/2 in above H1 (bust above 31 in)
        top = front.meta["top_line_y_cm"]
        self.assertAlmostEqual(top, dv.front_raise)
        self.assertAlmostEqual(front.points["NECK_POINT"][1], 0.0)                 # the raised neck point is the top
        self.inches(front.points["SHOULDER_POINT"][1] - top, 1.0)  # G1K1 = 1 in
        # X2 and Y1: 1/2 in and 3/8 in inside the line G1-L1, at one and two thirds of K1-L1
        s1, s2 = front.segment("armhole_1"), front.segment("armhole_2")
        self.inches(dv.front_shoulder_x - s1.end[0], 0.5)
        self.inches(dv.front_shoulder_x - s2.end[0], 0.375)
        self.inches(s1.end[1] - top, 1 + 6.5 / 3, tol_cm=0.01)
        self.inches(s2.end[1] - top, 1 + 2 * 6.5 / 3, tol_cm=0.01)

    def test_waist_widths_and_darts(self):
        dv = self.dv
        self.inches(dv.back_waist_x, 7.5)                          # DM = 1/2 back waist (6 1/4) + 1 1/4 in
        self.inches(dv.front_waist_x, 8.5)                         # CM1 = 1/2 front waist (6 3/4) + 1 3/4 in
        self.inches(dv.back_dart, 1.0)
        self.inches(dv.front_dart, 1.5)
        back_dart = self.b.back.darts[0]
        self.inches(back_dart["apex"][0], 3.75)                    # N: midpoint of DM
        self.inches(self.dv.waist_y - back_dart["apex"][1], 7.0 - 1.0)   # NP = OF - 1 in, OF = 14 1/2 - 7 1/2

    def test_bust_point_and_front_darts(self):
        dv, front = self.dv, self.b.front
        self.inches(dv.bust_point[1], 9.25)                        # BS = 9 + 1/4 in
        self.inches(dv.bust_point[0], 3.25)                        # ST = half of 6 1/2 in
        top = front.meta["top_line_y_cm"]
        waist_dart = next(d for d in front.darts if d["id"] == "front_waist_dart")
        self.inches(waist_dart["apex"][1] - top, 9.25 + 0.75)      # P1: 3/4 in below T
        self.inches(waist_dart["leg_b"][0] - waist_dart["leg_a"][0], 1.5)
        side = next(d for d in front.darts if d["id"] == "front_side_dart")
        self.inches(side["intake_cm"], 1.0, tol_cm=0.15)           # V, W 1/2 in either side of U
        self.inches(g.dist(side["apex"], (dv.bust_point[0], dv.bust_point[1] + top)), 1.5)   # TU1 = 1 1/2 in
        self.inches(front.meta["front_extra_length_cm"], 1.0)      # M2 is 1 in below M1

    def test_sleeve_width_and_cap_height(self):
        self.inches(self.dv.sleeve_width, 14.0)                    # 1/2 bust - 3 in
        self.inches(self.dv.sleeve_width / 2.0, 7.5 - 0.5)         # AB = EO - 1/2 in
        self.inches(self.dv.sleeve_cap_height_method, 3.5)         # BE = 1/2 AB
        self.assertEqual(self.b.armhole["cap_fit"], "method")      # the source's own cap fits its own armhole
        self.inches(self.b.sleeve.meta["cap_height_cm"], 3.5)

    def test_sleeve_cap_points_lie_on_the_method_offsets(self):
        w, h = self.dv.sleeve_width, self.dv.sleeve_cap_height_method
        front, back = sleeve.cap_paths(w, h)
        a = w / 2.0
        length = math.hypot(a, h)
        for path, offsets, mirror in ((back, A["sleeve_cap_back_offsets_cm"], False),
                                      (list(reversed(front)), A["sleeve_cap_front_offsets_cm"], True)):
            knots = [s.end for s in path[:-1]] if not mirror else [s.start for s in path[:-1]]
            for t, off, knot in zip((0.25, 0.5, 0.75), offsets, knots):
                on_line = (a + a * t, h * t)
                x = knot[0] if not mirror else w - knot[0]         # the front half is the mirror image
                d = ((x - on_line[0]) * h - (knot[1] - on_line[1]) * a) / length   # signed distance, + = outside
                self.assertAlmostEqual(d, off, places=6)
        self.assertNotEqual(g.path_length(front), g.path_length(back))            # the two halves differ

    def test_method_cap_is_a_little_longer_than_the_method_armhole(self):
        arm = self.b.armhole
        self.assertGreater(arm["sleeve_cap_seam_cm"], arm["total_armhole_seam_cm"])
        self.assertTrue(arm["allowed_cap_ease_min_cm"] <= arm["cap_ease_cm"] <= arm["allowed_cap_ease_max_cm"])


class TestQuartersHalvesAndEase(unittest.TestCase):
    def test_bust_is_quartered_after_adding_ease(self):
        b = base()
        e = b.ease
        self.assertAlmostEqual(b.dv.garment_bust, 88 + e.bust_cm)
        self.assertAlmostEqual(b.dv.back_width + b.dv.front_width, (88 + e.bust_cm) / 2.0)
        self.assertAlmostEqual(2 * (b.back.points["UNDERARM"][0] + b.front.points["UNDERARM"][0]), 88 + e.bust_cm)

    def test_half_measurements_are_halves_not_quarters(self):
        b = base()
        self.assertAlmostEqual(b.dv.shoulder_half, 37 / 2.0)                       # shoulder to shoulder / 2
        self.assertAlmostEqual(b.back.points["SHOULDER_POINT"][0], 18.5)
        wide = base(neck_width_cm=18.0)
        self.assertAlmostEqual(wide.dv.neck_half_back, 9.0)                        # neckline width / 2
        self.assertAlmostEqual(b.sleeve.points["UNDERARM_RIGHT"][0] - b.sleeve.points["CROWN"][0], b.dv.sleeve_width / 2.0)
        self.assertAlmostEqual(b.sleeve.meta["width_hem_cm"], 16 + b.ease.sleeve_end_cm)   # whole sleeve end, + ease

    def test_fit_presets_change_the_ease_not_the_body(self):
        close, regular, relaxed = (base(fit=f) for f in ("close", "standard", "loose"))
        self.assertAlmostEqual(close.ease.bust_cm, 3.0 * IN)
        self.assertAlmostEqual(regular.ease.bust_cm, 3.5 * IN)
        self.assertAlmostEqual(relaxed.ease.bust_cm, 5.0 * IN)
        self.assertLess(close.dv.front_width, regular.dv.front_width)
        self.assertLess(regular.dv.front_width, relaxed.dv.front_width)
        self.assertEqual(close.dv.armhole_depth, relaxed.dv.armhole_depth)         # from the body bust, not the eased one
        self.assertEqual(close.ease.status, EASE)

    def test_woven_and_knit_ease_are_different_and_knit_is_marked_as_a_project_preset(self):
        woven, knit = ease_profile_for("woven_bodice"), ease_profile_for("knit_bodice")
        self.assertNotEqual(woven.bust_cm, knit.bust_cm)
        self.assertEqual(knit.status, EXTENSION)
        self.assertGreater(knit.bust_cm, 0)                                        # no negative ease anywhere
        with self.assertRaises(DraftingError):
            ease_profile_for("woven_bodice", "skin-tight")
        with self.assertRaises(DraftingError) as ctx:
            base(garment="t-shirt", fabric="stretch-knit")
        self.assertEqual(ctx.exception.code, "UNSUPPORTED_FABRIC_TYPE")

    def test_waist_and_hip_lines(self):
        b = base()
        self.assertAlmostEqual(b.dv.waist_y, 40 + 0.5 * IN)
        self.assertAlmostEqual(b.dv.hip_y, b.dv.waist_y + 20)                      # measured waist to hip, not a constant
        self.assertAlmostEqual(b.dv.garment_hip, 94 + b.ease.hip_cm)
        self.assertAlmostEqual(2 * (b.back.meta["waist_finished_cm"] + b.front.meta["waist_finished_cm"]), 70 + b.ease.waist_cm)

    def test_small_bust_uses_the_smaller_armhole_reduction_and_no_neck_raise(self):
        depth, less = method_armhole_depth(29 * IN)
        self.assertAlmostEqual(less, 0.5 * IN)
        self.assertAlmostEqual(depth, 29 * IN / 4 - 0.5 * IN)
        self.assertAlmostEqual(method_armhole_depth(34 * IN)[1], 1.0 * IN)
        small = base("small", bust_cm=76.0)
        self.assertEqual(small.dv.front_raise, 0.0)                                # bust not above 31 in
        self.assertGreater(base().dv.front_raise, 0.0)


class TestDesignValues(unittest.TestCase):
    def test_entered_neck_depths_width_and_armhole_depth_replace_the_calculated_ones(self):
        b = base(front_neck_depth_cm=12.0, back_neck_depth_cm=4.0, neck_width_cm=17.0, armhole_depth_cm=21.0)
        self.assertEqual((b.dv.front_neck_depth, b.dv.back_neck_depth, b.dv.neck_half_back, b.dv.armhole_depth),
                         (12.0, 4.0, 8.5, 21.0))
        self.assertAlmostEqual(b.back.points["CENTRE_NECK"][1], 4.0)
        self.assertAlmostEqual(b.front.points["CENTRE_NECK"][1] - b.front.meta["top_line_y_cm"], 12.0)
        rows = {r["id"]: r for r in b.explanation}
        self.assertEqual(rows["front_neck_depth"]["source"], "design")
        self.assertEqual(rows["armhole_depth"]["source"], "design")
        calc = {r["id"]: r for r in base().explanation}
        self.assertEqual(calc["armhole_depth"]["source"], "method")
        self.assertIn("/ 4", calc["armhole_depth"]["formula"])

    def test_bust_point_distance_defaults_to_the_method_value(self):
        self.assertAlmostEqual(base().dv.bust_point[0], 88 / 10.0)                 # "about one tenth bust"
        self.assertAlmostEqual(base(bust_point_distance_cm=18.0).dv.bust_point[0], 9.0)


class TestFrontAndBackAreDifferent(unittest.TestCase):
    def setUp(self):
        self.b = base()

    def test_front_is_wider_and_its_armhole_longer(self):
        f, k = self.b.front, self.b.back
        self.assertAlmostEqual(f.meta["bust_width_cm"] - k.meta["bust_width_cm"], 1.0 * IN)
        self.assertGreater(f.meta["armhole_length_cm"], k.meta["armhole_length_cm"] + 1.0)
        self.assertNotEqual([s.kind for s in f.segments if s.id.startswith("armhole")],
                            [s.kind for s in k.segments if s.id.startswith("armhole")])

    def test_front_neck_is_deeper_and_narrower(self):
        f, k = self.b.front, self.b.back
        self.assertGreater(f.points["CENTRE_NECK"][1] - f.meta["top_line_y_cm"], k.points["CENTRE_NECK"][1])
        self.assertLess(f.points["NECK_POINT"][0], k.points["NECK_POINT"][0])

    def test_the_front_armhole_is_hollowed_inside_the_shoulder_tip(self):
        f = self.b.front
        xs = [p[0] for s in f.segments if s.id.startswith("armhole") for p in s.flatten()]
        self.assertLess(min(xs), f.points["SHOULDER_POINT"][0] - 1.0)
        k = self.b.back
        back_xs = [p[0] for s in k.segments if s.id.startswith("armhole") for p in s.flatten()]
        self.assertAlmostEqual(min(back_xs), k.points["SHOULDER_POINT"][0])       # the back never goes inside it

    def test_seams_that_are_sewn_together_agree(self):
        f, k = self.b.front, self.b.back
        self.assertAlmostEqual(f.meta["side_seam_sewn_length_cm"], k.meta["side_seam_sewn_length_cm"], places=6)
        self.assertGreater(f.meta["side_seam_length_cm"], k.meta["side_seam_length_cm"])   # before the bust dart
        self.assertAlmostEqual(f.meta["shoulder_length_cm"], k.meta["shoulder_length_cm"], delta=0.6)

    def test_a_knit_block_has_no_bust_shaping(self):
        t = base(garment="t-shirt", fabric="knit")
        self.assertEqual(t.front.darts, [])
        self.assertEqual(t.back.darts, [])
        self.assertAlmostEqual(t.front.meta["bust_width_cm"], t.back.meta["bust_width_cm"])
        self.assertEqual((t.dv.front_raise, t.dv.front_extra), (0.0, 0.0))
        self.assertGreater(t.front.meta["armhole_length_cm"], t.back.meta["armhole_length_cm"])   # still its own curve
        self.assertNotIn("BUST_POINT", base(garment="t-shirt", fabric="knit", shoulder_to_bust_cm=None).front.points)

    def test_fixed_darts_are_reduced_when_the_waist_is_as_wide_as_the_block(self):
        b = base(waist_cm=96.0)                                                     # waist larger than the bust
        self.assertLess(b.dv.back_dart, A["back_dart_width_cm"])
        self.assertGreaterEqual(b.dv.back_dart, 0.0)
        rows = {r["id"]: r for r in b.explanation}
        self.assertEqual(rows["back_waist_dart"]["source"], "extension")
        self.assertTrue(b.validation["passed"], b.validation["errors"])


class TestCurveLengths(unittest.TestCase):
    def test_armhole_length_is_the_arc_length_of_the_curve_not_the_depth(self):
        b = base()
        for piece in (b.front, b.back):
            segs = [s for s in piece.segments if s.id.startswith("armhole")]
            fine = sum(g.dist(p, q) for s in segs for p, q in zip(s.flatten(2000), s.flatten(2000)[1:]))
            self.assertAlmostEqual(piece.meta["armhole_length_cm"], fine, delta=0.01)
            straight = g.dist(piece.points["SHOULDER_POINT"], piece.points["UNDERARM"])
            depth = piece.points["UNDERARM"][1] - piece.points["SHOULDER_POINT"][1]
            self.assertGreater(piece.meta["armhole_length_cm"], straight)
            self.assertGreater(piece.meta["armhole_length_cm"], depth)

    def test_a_quarter_circle_measures_like_a_quarter_circle(self):
        r = 10.0
        seg = g.quarter_ellipse("q", (0, 0), (r, r), (0, r), first_axis="vertical")
        self.assertAlmostEqual(seg.length(), math.pi * r / 2.0, delta=0.01)

    def test_spline_passes_through_its_points_and_respects_end_directions(self):
        pts = [(0, 0), (3, 4), (8, 5), (12, 1)]
        segs = g.spline_through("s", pts, start_dir=(1, 0), end_dir=(0, -1))
        self.assertEqual([s.id for s in segs], ["s_1", "s_2", "s_3"])
        self.assertEqual([segs[0].start] + [s.end for s in segs], [tuple(p) for p in pts])
        self.assertAlmostEqual(segs[0].p[1][1], 0.0)                               # leaves horizontally
        self.assertAlmostEqual(segs[-1].p[2][0], 12.0)                             # arrives vertically
        self.assertTrue(g.path_is_connected(segs))
        mid = g.point_at_length(segs, g.path_length(segs) / 2.0)
        back_again, total = g.length_to_point(segs, mid)
        self.assertAlmostEqual(back_again, total / 2.0, delta=0.01)

    def test_notch_distances_follow_the_method(self):
        b = base()
        back_curve = b.back.segment("armhole_2")
        self.assertAlmostEqual(b.back.meta["armhole_notch_from_underarm_cm"], back_curve.length() / 2.0)   # Z: midpoint of OX
        last = b.front.segment("armhole_3")
        self.assertAlmostEqual(b.front.meta["armhole_notch_from_underarm_cm"], last.length())             # Y1


class TestSleeve(unittest.TestCase):
    def test_cap_seam_is_measured_and_compared_with_the_armhole(self):
        for profile in PROFILES:
            b = base(profile)
            arm = b.armhole
            self.assertAlmostEqual(arm["total_armhole_seam_cm"], arm["front_armhole_seam_cm"] + arm["back_armhole_seam_cm"])
            self.assertAlmostEqual(arm["sleeve_cap_seam_cm"], b.sleeve.meta["cap_length_cm"], places=6)
            self.assertAlmostEqual(arm["cap_ease_cm"], arm["sleeve_cap_seam_cm"] - arm["total_armhole_seam_cm"])
            self.assertTrue(b.dv.cap_ease_min - 1e-6 <= arm["cap_ease_cm"] <= b.dv.cap_ease_max + 1e-6, profile)

    def test_cap_height_is_changed_only_when_the_method_cap_does_not_fit(self):
        kept = base("medium")
        self.assertEqual(kept.armhole["cap_fit"], "method")
        self.assertAlmostEqual(kept.armhole["cap_height_cm"], kept.dv.sleeve_width / 4.0)
        changed = base("large")
        self.assertEqual(changed.armhole["cap_fit"], "adjusted")
        self.assertNotAlmostEqual(changed.armhole["cap_height_cm"], changed.armhole["method_cap_height_cm"], places=2)
        self.assertAlmostEqual(changed.armhole["cap_ease_cm"], changed.dv.sleeve_cap_ease, delta=0.1)
        row = next(r for r in changed.explanation if r["id"] == "sleeve_cap_height")
        self.assertEqual(row["source"], "extension")
        self.assertIn("changed from the method", row["formula"])

    def test_sleeve_width_follows_the_arm_when_the_method_width_is_too_narrow(self):
        normal = base("medium")
        self.assertAlmostEqual(normal.dv.sleeve_width, normal.dv.sleeve_width_method)
        big_arm = base("medium", bicep_cm=30.0)
        self.assertAlmostEqual(big_arm.dv.sleeve_width, 30.0 + big_arm.ease.upper_arm_cm)
        self.assertGreater(big_arm.dv.sleeve_width, big_arm.dv.sleeve_width_method)
        row = next(r for r in big_arm.explanation if r["id"] == "sleeve_width")
        self.assertEqual(row["source"], "extension")

    def test_a_sleeve_too_wide_for_the_armhole_is_an_error_and_a_deeper_armhole_solves_it(self):
        with self.assertRaises(DraftingError) as ctx:
            base("medium", bicep_cm=36.0)
        self.assertEqual(ctx.exception.code, "SLEEVE_TOO_WIDE_FOR_ARMHOLE")
        self.assertIn("armhole depth", ctx.exception.field_errors["bicep_cm"][0]["message"])
        deeper = base("medium", bicep_cm=36.0, armhole_depth_cm=23.0)               # the remedy the message names
        self.assertTrue(deeper.validation["passed"])

    def test_solver_hits_its_target_and_refuses_the_impossible(self):
        h = sleeve.solve_cap_height(36.0, 45.0)
        self.assertAlmostEqual(sleeve.cap_length(36.0, h), 45.0, places=4)
        with self.assertRaises(DraftingError):
            sleeve.solve_cap_height(36.0, 30.0)

    def test_cap_is_smooth_at_the_crown_and_never_above_it(self):
        for profile in PROFILES:
            s = base(profile).sleeve
            front = [x for x in s.segments if x.id.startswith("cap_front")]
            back = [x for x in s.segments if x.id.startswith("cap_back")]
            self.assertAlmostEqual(front[-1].p[2][1], 0.0)                         # arrives at the crown horizontally
            self.assertAlmostEqual(back[0].p[1][1], 0.0)                           # and leaves it horizontally
            self.assertGreaterEqual(min(p[1] for x in front + back for p in x.flatten(100)), -1e-9)
            self.assertEqual(g.self_intersections(s.outline), [])

    def test_sleeveless_design_has_no_sleeve_block(self):
        b = base(bicep_cm=None, sleeve_cm=None, sleeve_end_cm=None)
        self.assertIsNone(b.sleeve)
        self.assertNotIn("sleeve_cap_seam_cm", b.armhole)
        self.assertTrue(b.validation["passed"])


class TestDifferentPeopleGetDifferentBlocks(unittest.TestCase):
    def test_every_piece_changes_with_the_measurements(self):
        blocks = {p: base(p) for p in PROFILES}
        for attr in ("front", "back", "sleeve"):
            outlines = [getattr(b, attr).to_dict()["outline"] for b in blocks.values()]
            self.assertEqual(len({str(o) for o in outlines}), 3, attr)
        for key in ("armhole_depth", "back_width", "front_width", "shoulder_half", "waist_y", "sleeve_width"):
            values = [getattr(b.dv, key) for b in blocks.values()]
            self.assertEqual(len(set(values)), 3, key)

    def test_one_measurement_changes_only_what_depends_on_it(self):
        a, b = base(), base(shoulder_width_cm=39.0)
        self.assertNotEqual(a.back.points["SHOULDER_POINT"], b.back.points["SHOULDER_POINT"])
        self.assertEqual(a.back.points["UNDERARM"], b.back.points["UNDERARM"])
        self.assertEqual(a.dv.sleeve_width, b.dv.sleeve_width)
        self.assertNotEqual(a.armhole["total_armhole_seam_cm"], b.armhole["total_armhole_seam_cm"])

    def test_same_input_same_output(self):
        self.assertEqual(base().to_dict(), base().to_dict())

    def test_no_sample_value_is_built_in(self):
        m = measurements("medium")
        for field in ("bust_cm", "waist_cm", "shoulder_width_cm", "back_waist_length_cm", "garment_length_cm"):
            with self.assertRaises(DraftingError) as ctx:
                draft_base_block(dict(m, **{field: None}), select_drafting_block("blouse", "woven"))
            self.assertIn(field, ctx.exception.field_errors)
        with self.assertRaises(DraftingError) as ctx:                               # a woven blouse needs the bust point
            base(shoulder_to_bust_cm=None)
        self.assertIn("shoulder_to_bust_cm", ctx.exception.field_errors)


class TestMeasurementsThatCannotBeDrafted(unittest.TestCase):
    def check(self, field, **over):
        with self.assertRaises(DraftingError) as ctx:
            base(**over)
        self.assertEqual(ctx.exception.code, "MEASUREMENTS_NOT_DRAFTABLE")
        self.assertIn(field, ctx.exception.field_errors)

    def test_shoulders_wider_than_the_block(self):
        self.check("shoulder_width_cm", shoulder_width_cm=60.0)

    def test_shoulders_narrower_than_the_neckline(self):
        self.check("shoulder_width_cm", shoulder_width_cm=15.0)

    def test_waist_above_the_underarm(self):
        self.check("back_waist_length_cm", back_waist_length_cm=18.0)

    def test_bust_point_at_the_waist(self):
        self.check("shoulder_to_bust_cm", shoulder_to_bust_cm=40.0)

    def test_values_are_never_clamped(self):
        b = base(shoulder_width_cm=39.3, back_waist_length_cm=41.7)
        self.assertAlmostEqual(b.dv.shoulder_half, 19.65)
        self.assertAlmostEqual(b.dv.waist_y, 41.7 + 0.5 * IN)


class TestTraceability(unittest.TestCase):
    def test_every_row_has_a_value_a_formula_and_a_known_source(self):
        rows = base().explanation
        self.assertGreater(len(rows), 25)
        for r in rows:
            self.assertIn(r["source"], ("measurement", METHOD, FIGURE, DESIGN, EASE, EXTENSION), r["id"])
            self.assertTrue(r["formula"], r["id"])
            self.assertTrue(math.isfinite(r["value_cm"]), r["id"])
            self.assertTrue(r["label"])
        self.assertEqual(len({r["id"] for r in rows}), len(rows))                  # ids are unique

    def test_the_bust_row_shows_the_customers_own_numbers(self):
        rows = {r["id"]: r for r in base().explanation}
        self.assertIn("88", rows["front_bust_width"]["formula"])
        self.assertIn("/ 4", rows["front_bust_width"]["formula"])
        self.assertAlmostEqual(rows["front_bust_width"]["value_cm"], (88 + 3.5 * IN) / 4 + 0.5 * IN, places=3)
        other = {r["id"]: r for r in base("large").explanation}
        self.assertIn("104", other["front_bust_width"]["formula"])

    def test_dimension_annotations_point_at_trace_rows(self):
        b = base()
        ids = {r["id"] for r in b.explanation}
        for piece in b.pieces:
            dims = piece.to_dict()["dimensions"]
            self.assertGreater(len(dims), 5, piece.name)
            for d in dims:
                self.assertTrue(math.isfinite(d["value_cm"]) and d["value_cm"] > 0, (piece.name, d["id"]))
                if d["trace"]:
                    self.assertIn(d["trace"], ids, (piece.name, d["id"]))
        back = {d["id"]: d for d in b.back.to_dict()["dimensions"]}
        self.assertAlmostEqual(back["bust_width"]["value_cm"], b.dv.back_width, places=2)
        self.assertAlmostEqual(back["armhole_curve"]["value_cm"], b.back.meta["armhole_length_cm"], places=2)
        self.assertEqual(back["armhole_curve"]["kind"], "curve")


class TestConstantsRegistry(unittest.TestCase):
    def test_every_constant_is_classified_and_method_values_name_their_page(self):
        for name, c in CONSTANTS.items():
            self.assertIn(c["kind"], (METHOD, FIGURE, DESIGN, EASE, EXTENSION), name)
            self.assertTrue(c["note"], name)
            if c["kind"] in (METHOD, FIGURE):
                self.assertIsNotNone(c["source_page"], name)
        self.assertTrue(SOURCE["url"].startswith("https://"))
        self.assertEqual(A["shoulder_drop_cm"], 2.54)
        self.assertEqual(CONSTANTS["shoulder_drop_cm"]["kind"], DESIGN)             # configurable, not universal

    def test_nothing_is_called_aldrich(self):
        text = repr(assumptions_payload()).lower()
        self.assertNotIn("aldrich-based", text)
        self.assertNotIn("verified aldrich", text)

    def test_ease_and_seam_allowance_are_separate_tables(self):
        self.assertEqual(set(EASE_PRESETS), {"woven_bodice", "knit_bodice"})
        self.assertEqual(set(SEAM_ALLOWANCES), {"woven_bodice", "knit_bodice"})
        for table in SEAM_ALLOWANCES.values():
            self.assertEqual(set(table), {"shoulder", "side", "armhole", "neckline", "sleeve_seam", "sleeve_hem", "hem", "strip"})
        b = base()
        seam_free = 2 * (b.back.points["UNDERARM"][0] + b.front.points["UNDERARM"][0])
        self.assertAlmostEqual(seam_free, 88 + b.ease.bust_cm)                     # the block holds ease but no seam allowance


class TestValidatorCatchesBrokenBlocks(unittest.TestCase):
    def test_valid_blocks_pass_for_every_profile_and_block(self):
        for profile in PROFILES:
            for garment, fabric in (("blouse", "woven"), ("t-shirt", "knit")):
                b = base(profile, garment, fabric)
                self.assertTrue(b.validation["passed"], (profile, garment, b.validation["errors"]))
                self.assertEqual(b.validation["scope"], "geometry validation only; not a fit or sewing validation")

    def test_a_moved_point_is_caught(self):
        b = base()
        b.front.segments[-1] = g.Line("centre_line", (5.0, 30.0), b.front.segments[-1].end)   # outline no longer closes
        self.assertFalse(validate_base_block(b)["passed"])

    def test_a_sleeve_that_does_not_fit_the_armhole_is_caught(self):
        b = base()
        b.sleeve.meta["cap_length_cm"] += 12.0
        out = validate_base_block(b)
        self.assertFalse(out["passed"])
        self.assertTrue(any("Sleeve cap" in e for e in out["errors"]))

    def test_unequal_side_seams_are_caught(self):
        b = base()
        b.front.meta["side_seam_sewn_length_cm"] += 1.0
        self.assertTrue(any("side seams" in e for e in validate_base_block(b)["errors"]))

    def test_a_missing_bust_dart_piece_width_is_caught(self):
        b = base()
        b.front.meta["bust_width_cm"] -= 2.0
        self.assertTrue(any("bust plus ease" in e for e in validate_base_block(b)["errors"]))


class TestComputeDraftingValuesDirectly(unittest.TestCase):
    def test_values_and_trace_come_back_together(self):
        dv, rows = compute_drafting_values(measurements(), ease_profile_for("woven_bodice"))
        self.assertTrue(dv.darts)
        self.assertEqual(rows[0]["id"], "garment_bust")
        self.assertIsNone(bodice.side_nodes(compute_drafting_values(
            measurements(hip_cm=None, waist_to_hip_cm=None), ease_profile_for("woven_bodice"))[0], "back")[2])


if __name__ == "__main__":
    unittest.main()
