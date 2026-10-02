"""
Phase 4 — design transformations: BaseBlock + confirmed design_spec -> FinalPattern.

Geometry validation only; nothing here claims professional or fit validation.
"""

import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app
from flask_jwt_extended import create_access_token
from app.logic import feature_schema as fs
from app.logic.block_selection import select_drafting_block
from app.logic.drafting import geometry as g
from app.logic.drafting import sleeve as sleeve_mod
from app.logic.drafting.assumptions import A
from app.logic.drafting.base_block import draft_base_block
from app.logic.drafting.ease import DraftingError
from app.logic.drafting.transformations import apply_design
from app.logic.parametric_engine import ParametricEngine
from app.logic.taxonomy_map import confirmed_to_cad_features
from tests.fixtures import measurements, design, PROFILES


def make_base(profile="medium", garment="blouse", fabric="woven", **over):
    block = select_drafting_block(garment, fabric)
    return draft_base_block(measurements(profile, fabric_type=fabric, **over), block)


def final(profile="medium", fabric="woven", over=None, **attrs):
    d = design(**attrs)
    return apply_design(make_base(profile, d["garment_type"], fabric, **(over or {})), d)


def piece(fp, name_part):
    return next(p for p in fp.pieces if name_part in p.name)


class TestNecklineTransformations(unittest.TestCase):
    def setUp(self):
        self.round = final(neckline="round-neck")
        self.square = final(neckline="square-neck")
        self.v = final(neckline="v-neck")

    def test_round_square_and_v_produce_different_front_geometry(self):
        outlines = [f.front.to_dict()["outline"] for f in (self.round, self.square, self.v)]
        self.assertNotEqual(outlines[0], outlines[1])
        self.assertNotEqual(outlines[0], outlines[2])
        self.assertNotEqual(outlines[1], outlines[2])
        areas = [f.front.to_dict()["polygon_area_cm2"] for f in (self.round, self.square, self.v)]
        self.assertEqual(len(set(areas)), 3)

    def test_round_neck_is_a_smooth_curve(self):
        seg = self.round.front.segment("neckline")
        self.assertEqual(seg.kind, "cubic")
        dv = self.round.dv                                    # the front piece is moved down by its neck raise
        self.assertAlmostEqual(seg.start[0], 0.0)
        self.assertAlmostEqual(seg.start[1], dv.front_neck_depth + dv.front_raise)

    def test_square_neck_has_two_straight_edges_at_a_right_angle(self):
        bottom, side = self.square.front.segment("neckline_bottom"), self.square.front.segment("neckline_side")
        self.assertEqual((bottom.kind, side.kind), ("line", "line"))
        self.assertAlmostEqual(bottom.start[1], bottom.end[1])              # horizontal
        self.assertAlmostEqual(side.start[0], side.end[0])                  # vertical
        self.assertEqual(bottom.end, side.start)
        self.assertEqual(side.end, self.square.front.points["NECK_POINT"])
        self.assertEqual(self.square.front.segment("neckline"), None)

    def test_v_neck_is_a_straight_v_with_a_centre_front_point(self):
        seg = self.v.front.segment("neckline")
        self.assertEqual(seg.kind, "line")
        expected_depth = self.v.dv.front_neck_depth + A["v_neck_extra_depth_cm"] + self.v.dv.front_raise
        self.assertAlmostEqual(seg.start[1], expected_depth)
        self.assertAlmostEqual(seg.start[0], 0.0)                            # the V point is on the centre line
        self.assertEqual(seg.end, self.v.front.points["NECK_POINT"])
        self.assertAlmostEqual(self.v.front.points["CENTRE_NECK"][1], expected_depth)

    def test_v_is_deepest_and_square_matches_round_depth(self):
        d = lambda f: f.front.points["CENTRE_NECK"][1]
        self.assertGreater(d(self.v), d(self.round))
        self.assertAlmostEqual(d(self.square), d(self.round))

    def test_back_neckline_and_armholes_are_unchanged_by_the_front_design(self):
        base_back = self.round.back.to_dict()["outline"]
        self.assertEqual(self.square.back.to_dict()["outline"], base_back)
        self.assertEqual(self.v.back.to_dict()["outline"], base_back)
        for f in (self.round, self.square, self.v):
            self.assertAlmostEqual(f.front.meta["armhole_length_cm"], self.round.front.meta["armhole_length_cm"], places=9)

    def test_shoulder_seams_are_the_same_for_every_neckline(self):
        back = self.round.back.meta["shoulder_length_cm"]
        front = self.round.front.meta["shoulder_length_cm"]
        self.assertAlmostEqual(front, back, delta=0.6)       # the method raises the front neck point a little
        for f in (self.square, self.v):
            self.assertAlmostEqual(f.front.meta["shoulder_length_cm"], front, places=9)
            self.assertAlmostEqual(f.back.meta["shoulder_length_cm"], back, places=9)

    def test_neckline_transformation_is_recorded(self):
        for f, shape in ((self.round, "round"), (self.square, "square"), (self.v, "v")):
            t = next(t for t in f.transformations if t["id"] == "neckline")
            self.assertEqual(t["type"], f"{shape}_neckline")
            self.assertEqual(t["status"], "applied")

    def test_necklines_outside_the_taxonomy_are_refused_not_drawn_as_a_round_neck(self):
        # the engine used to draw a round neckline for these and mark it "fallback"; a different design is never drafted
        for style in ("scoop-neck", "boat-neck", "sweetheart-neck", "high-neck", "halter-neck", "off-shoulder"):
            with self.assertRaises(DraftingError) as ctx:
                final(neckline=style)
            self.assertEqual(ctx.exception.code, "INVALID_DESIGN_ATTRIBUTES", style)
            self.assertIn("neckline_type", ctx.exception.field_errors)

    def test_a_collared_neck_is_rejected_as_unsupported(self):
        with self.assertRaises(DraftingError) as ctx:
            final(neckline="collared-neck")
        self.assertEqual(ctx.exception.code, "UNSUPPORTED_DESIGN")
        self.assertIn("will not substitute", str(ctx.exception))


class TestSleeveTransformations(unittest.TestCase):
    def test_short_and_long_sleeves_use_the_entered_lengths(self):
        short = final(length="short-sleeve", over=dict(sleeve_cm=24))
        long_ = final(length="long-sleeve", over=dict(sleeve_cm=55))
        s, l = piece(short, "Sleeve").to_dict(), piece(long_, "Sleeve").to_dict()
        self.assertNotEqual(s["outline"], l["outline"])
        self.assertAlmostEqual(s["bounding_box"]["height_cm"], 24.0, places=2)   # no fraction of a full arm
        self.assertAlmostEqual(l["bounding_box"]["height_cm"], 55.0, places=2)

    def test_sleeve_length_is_exactly_the_measured_value(self):
        for length, value in (("short-sleeve", 20.0), ("short-sleeve", 26.5), ("long-sleeve", 58.25)):
            f = final(length=length, over=dict(sleeve_cm=value))
            self.assertAlmostEqual(piece(f, "Sleeve").meta["length_cm"], value, places=6, msg=length)
            t = next(t for t in f.transformations if t["id"] == "sleeve_length")
            self.assertAlmostEqual(t["sleeve_length_cm"], value, places=3)
            self.assertNotIn("fraction", t)
        self.assertNotIn("sleeve_length_fraction", A)

    def test_a_sleeve_narrows_to_the_arm_measured_at_its_end(self):
        f = final(length="short-sleeve", over=dict(sleeve_cm=24, sleeve_end_cm=27))
        short = piece(f, "Sleeve").meta
        self.assertAlmostEqual(short["width_hem_cm"], 27 + f.base.ease.sleeve_end_cm)
        self.assertLess(short["width_hem_cm"], short["width_bicep_cm"])
        f = final(length="long-sleeve", over=dict(sleeve_cm=58, sleeve_end_cm=16))
        self.assertAlmostEqual(piece(f, "Sleeve").meta["width_hem_cm"], f.dv.sleeve_end_width)

    def test_a_sleeve_end_wider_than_the_sleeve_is_reported(self):
        with self.assertRaises(DraftingError) as ctx:
            final(length="short-sleeve", over=dict(sleeve_cm=24, sleeve_end_cm=45))
        self.assertIn("sleeve_end_cm", ctx.exception.field_errors)

    def test_a_sleeve_without_its_end_measurement_is_reported_not_guessed(self):
        with self.assertRaises(DraftingError) as ctx:
            final(length="long-sleeve", over=dict(sleeve_cm=58, sleeve_end_cm=None))
        self.assertIn("sleeve_end_cm", ctx.exception.field_errors)

    def test_sleeveless_design_needs_no_sleeve_measurements(self):
        f = final(length="sleeveless", style="none", over=dict(bicep_cm=None, sleeve_cm=None, sleeve_end_cm=None))
        self.assertIsNone(f.sleeve)
        self.assertTrue(f.validation["passed"], f.validation["errors"])

    def test_sleeve_cap_is_identical_for_every_length_and_matches_the_armhole(self):
        caps = set()
        for length in ("short-sleeve", "long-sleeve"):
            f = final(length=length)
            s = piece(f, "Sleeve")
            caps.add(round(s.meta["cap_length_cm"], 6))
            info = f.validation["armhole_sleeve"]
            self.assertGreaterEqual(info["cap_ease_cm"], f.dv.cap_ease_min - 1e-6)
            self.assertLessEqual(info["cap_ease_cm"], f.dv.cap_ease_max + 1e-6)
            self.assertAlmostEqual(info["sleeve_cap_seam_cm"] - info["total_armhole_seam_cm"], info["cap_ease_cm"], places=6)
        self.assertEqual(len(caps), 1)

    def test_sleeve_tapers_towards_the_wrist_with_length(self):
        widths = [piece(final(length=n), "Sleeve").meta["width_hem_cm"] for n in ("short-sleeve", "long-sleeve")]
        self.assertEqual(widths, sorted(widths, reverse=True))
        for length in ("elbow-length", "three-quarter-sleeve", "cap-length"):   # not in the taxonomy: refused, not approximated
            with self.assertRaises(DraftingError) as ctx:
                final(length=length)
            self.assertEqual(ctx.exception.code, "INVALID_DESIGN_ATTRIBUTES", length)
        self.assertAlmostEqual(widths[-1], 20.0, places=6)                      # sleeve end 16 + ease 4

    def test_sleeveless_has_no_sleeve_and_gets_armhole_facings(self):
        f = final(length="sleeveless", style="none")                        # a sleeveless blouse
        self.assertIsNone(f.sleeve)
        self.assertFalse([p for p in f.pieces if p.piece_type == "sleeve"])
        with self.assertRaises(DraftingError) as ctx:                       # a sleeveless T-shirt is outside the scope
            final(garment_type="t-shirt", fabric="knit", length="sleeveless", style="none")
        self.assertEqual(ctx.exception.code, "UNSUPPORTED_DESIGN")
        facing = piece(f, "Facing")
        self.assertEqual(facing.cut_count, 2)
        self.assertAlmostEqual(facing.meta["length_cm"], f.base.armhole["total_armhole_seam_cm"], places=6)
        t = next(t for t in f.transformations if t["id"] == "sleeve_length")
        self.assertEqual(t["type"], "sleeveless")

    def test_sleeveless_with_a_sleeve_style_is_a_contradiction(self):
        with self.assertRaises(DraftingError) as ctx:
            final(length="sleeveless", style="regular-sleeve")
        self.assertEqual(ctx.exception.code, "INVALID_DESIGN_ATTRIBUTES")
        self.assertIn("sleeve_style", ctx.exception.field_errors)

    def test_sleeve_styles_outside_the_taxonomy_are_rejected_not_ignored(self):
        for style in ("bishop-sleeve", "flutter-sleeve", "raglan-sleeve", "dolman-sleeve", "kimono-sleeve"):
            with self.assertRaises(DraftingError) as ctx:
                final(style=style)
            self.assertEqual(ctx.exception.code, "INVALID_DESIGN_ATTRIBUTES", style)

    def test_supported_styles_are_recorded_not_silently_ignored(self):
        f = final(style="regular-sleeve")
        t = next(t for t in f.transformations if t["id"] == "sleeve_style")
        self.assertEqual(t["design"], "regular-sleeve")
        self.assertEqual(t["status"], "applied")
        self.assertIn("sleeve_length", piece(f, "Sleeve").transformations)
        with self.assertRaises(DraftingError) as ctx:                       # a sleeve with style "none" is not drawn as a plain sleeve
            final(style="none")
        self.assertEqual(ctx.exception.code, "UNSUPPORTED_DESIGN")

    def test_too_short_a_sleeve_for_the_cap_is_a_structured_error(self):
        b = make_base()
        with self.assertRaises(DraftingError) as ctx:
            sleeve_mod.build_sleeve(b.dv, b.armhole["cap_height_cm"], b.armhole["cap_height_cm"] + 1.0)
        self.assertEqual(ctx.exception.code, "SLEEVE_TOO_SHORT_FOR_CAP")
        self.assertIn("sleeve_cm", ctx.exception.field_errors)


class TestGarmentLengthTransformations(unittest.TestCase):
    def test_a_crop_top_is_no_longer_a_garment_type(self):
        with self.assertRaises(DraftingError) as ctx:
            final(garment_type="crop-top", over=dict(garment_length_cm=38))
        self.assertEqual(ctx.exception.code, "INVALID_DESIGN_ATTRIBUTES")
        self.assertIn("garment_type", ctx.exception.field_errors)

    def test_blouse_length_above_the_waist_contradicts_the_design(self):
        with self.assertRaises(DraftingError) as ctx:
            final(garment_type="blouse", over=dict(garment_length_cm=38))
        self.assertEqual(ctx.exception.code, "DESIGN_MEASUREMENT_CONFLICT")
        self.assertIn("garment_length_cm", ctx.exception.field_errors)
        with self.assertRaises(DraftingError):
            final(garment_type="t-shirt", fabric="knit", over=dict(garment_length_cm=38))

    def test_length_rule_boundaries(self):
        b = make_base()
        waist = b.dv.waist_y                                                    # back neck to waist + 1/2 in
        final(garment_type="blouse", over=dict(garment_length_cm=waist))               # exactly at the waist
        with self.assertRaises(DraftingError) as ctx:
            final(garment_type="blouse", over=dict(garment_length_cm=waist - 0.1))
        self.assertNotIn("crop", ctx.exception.message.lower())                  # the message no longer offers a crop top
        final(garment_type="t-shirt", fabric="knit", over=dict(garment_length_cm=waist))

    def test_hem_follows_the_measured_garment_length(self):
        for length in (50, 60, 75):
            f = final(over=dict(garment_length_cm=length))
            self.assertAlmostEqual(f.back.meta["hem_y_cm"], length)
            self.assertAlmostEqual(f.back.to_dict()["bounding_box"]["height_cm"], length, places=2)
            # the front is longer by the method's extra front length (taken up by the bust dart) and its neck raise
            self.assertAlmostEqual(f.front.meta["hem_y_cm"], length + f.dv.front_extra + f.dv.front_raise)
            self.assertAlmostEqual(f.front.meta["side_seam_sewn_length_cm"], f.back.meta["side_seam_sewn_length_cm"], places=6)

    def test_long_blouse_uses_closed_fish_darts_inside_the_outline(self):
        blouse = final()
        for p in (blouse.front, blouse.back):
            d = next(x for x in p.darts if "waist" in x["id"])
            self.assertEqual(d["type"], "fish")
            self.assertTrue(g.point_in_polygon(tuple(d["lower_apex"]), p.outline))
            self.assertLess(d["lower_apex"][1], p.meta["hem_y_cm"])
            self.assertEqual(g.self_intersections(p.outline), [])

    def test_side_seam_widens_towards_the_hip_below_the_waist(self):
        f = final(over=dict(garment_length_cm=70))
        x_waist = f.front.points["WAIST_SIDE"][0]
        x_hem = f.front.points["HEM_SIDE"][0]
        self.assertGreater(x_hem, x_waist)
        self.assertAlmostEqual(x_hem, f.front.points["HIP_SIDE"][0])             # straight down below the hip line
        both = f.front.points["HIP_SIDE"][0] + f.back.points["HIP_SIDE"][0]
        self.assertAlmostEqual(2 * both, f.dv.garment_hip, places=6)             # front + back = half of (hip + ease)

    def test_tshirt_is_knit_without_darts_and_has_a_neckband_derived_from_the_neckline(self):
        f = final(garment_type="t-shirt", fabric="knit")
        self.assertEqual(f.front.darts, [])
        band = piece(f, "Neckband")
        full_neck = 2 * (f.front.meta["neckline_length_cm"] + f.back.meta["neckline_length_cm"])
        self.assertAlmostEqual(band.meta["length_cm"], 0.85 * full_neck, places=6)
        self.assertNotIn("Neckband", [p.name for p in final().pieces])

    def test_garment_length_transformation_is_recorded(self):
        t = next(t for t in final().transformations if t["id"] == "garment_length")
        self.assertEqual(t["hem_level_cm"], 65.0)
        self.assertEqual(t["status"], "applied")


class TestContradictoryOrInvalidDesigns(unittest.TestCase):
    def test_invalid_taxonomy_values_are_rejected(self):
        b = make_base()
        for bad in (dict(design(), neckline_type="cowl-neck"), dict(design(), garment_type="dress"),
                    dict(design(), neckline_type="halter-neck"), dict(design(), sleeve_style="bishop-sleeve"), {}, None):
            with self.assertRaises(DraftingError) as ctx:
                apply_design(b, bad)
            self.assertEqual(ctx.exception.code, "INVALID_DESIGN_ATTRIBUTES")

    def test_unsupported_design_error_lists_the_features(self):
        with self.assertRaises(DraftingError) as ctx:
            final(garment_type="t-shirt", fabric="knit", neckline="collared-neck", style="puff-sleeve")
        values = {u["value"] for u in ctx.exception.extra["unsupported_features"]}
        self.assertEqual(values, {"collared-neck", "puff-sleeve"})

    def test_engine_never_returns_a_pattern_for_a_rejected_design(self):
        with self.assertRaises(DraftingError):
            ParametricEngine(measurements(), None, design_spec={"attributes": design(neckline="collared-neck")}).generate()


class TestDeterminismAndMultiProfile(unittest.TestCase):
    def test_same_input_same_output(self):
        for attrs in (design(), design(neckline="v-neck", length="long-sleeve")):
            a = ParametricEngine(measurements(), None, design_spec={"attributes": attrs}).generate()
            b = ParametricEngine(measurements(), None, design_spec={"attributes": attrs}).generate()
            self.assertEqual(a["final_pattern"], b["final_pattern"])
            self.assertEqual(a["base_block"], b["base_block"])

    def test_three_realistic_profiles_all_designs_valid_and_simple(self):
        for profile in PROFILES:
            designs = [
                (design(), {}),
                (design(neckline="v-neck", length="long-sleeve"), {}),
                (design(neckline="square-neck", length="sleeveless", style="none"), {}),
                (design(neckline="square-neck", length="long-sleeve"), {}),
                (design(garment_type="t-shirt", length="long-sleeve"), {}),
            ]
            for attrs, over in designs:
                fabric = "knit" if attrs["garment_type"] == "t-shirt" else "woven"
                out = ParametricEngine(measurements(profile, fabric_type=fabric, **over), None,
                                       design_spec={"attributes": attrs}).generate()
                self.assertTrue(out["validation"]["final_pattern"]["passed"], (profile, attrs))
                for p in out["pattern_pieces"]:
                    self.assertEqual(g.self_intersections([tuple(q) for q in p["outline"]]), [], (profile, p["name"]))

    def test_larger_measurements_give_larger_pieces(self):
        widths = {p: ParametricEngine(measurements(p), None, design_spec={"attributes": design()}).generate()
                  ["pattern_pieces"][0]["bounding_box"]["width_cm"] for p in PROFILES}
        self.assertLess(widths["small"], widths["medium"])
        self.assertLess(widths["medium"], widths["large"])


class TestApiOutputStructure(unittest.TestCase):
    def setUp(self):
        self.out = ParametricEngine(measurements(), None, design_spec={"attributes": design(neckline="v-neck")}).generate()

    def test_base_block_and_final_pattern_are_distinct_stages(self):
        base, fin = self.out["base_block"], self.out["final_pattern"]
        self.assertEqual(base["stage"], "base_block")
        self.assertEqual(fin["stage"], "final_pattern")
        base_back = next(p for p in base["pieces"] if p["name"] == "Back Bodice")
        fin_back = next(p for p in fin["pieces"] if p["name"] == "Back Bodice")
        self.assertNotEqual(base_back["outline"], fin_back["outline"])
        self.assertAlmostEqual(base_back["measurements"]["hem_y_cm"], 40 + 1.27)  # waist line: back neck to waist + 1/2 in
        self.assertAlmostEqual(fin_back["measurements"]["hem_y_cm"], 65.0)        # design length
        self.assertTrue(any(p["name"] == "Sleeve Block" for p in base["pieces"]))
        self.assertTrue(any(p["name"].startswith("Sleeve (") for p in fin["pieces"]))

    def test_pattern_pieces_are_the_final_pattern_pieces(self):
        self.assertEqual(self.out["pattern_pieces"], self.out["final_pattern"]["pieces"])

    def test_pieces_expose_the_required_metadata(self):
        for p in self.out["pattern_pieces"]:
            for key in ("name", "piece_type", "cut_count", "cut_on_fold", "grain_line", "segments", "outline",
                        "points", "bounding_box", "polygon_area_cm2", "transformations", "measurements"):
                self.assertIn(key, p, (p["name"], key))
            self.assertIn("start", p["grain_line"])
        bodice = next(p for p in self.out["pattern_pieces"] if p["piece_type"] == "front_bodice")
        self.assertTrue(bodice["cut_on_fold"])
        self.assertIsNotNone(bodice["fold_line"])
        self.assertIn("neckline", bodice["transformations"])
        self.assertTrue(bodice["darts"])

    def test_base_block_output_carries_assumptions_ease_and_drafting_values(self):
        base = self.out["base_block"]
        self.assertIn("assumptions", base)
        self.assertAlmostEqual(base["ease"]["bust_cm"], 3.5 * 2.54)             # regular fit: the source's 3 1/2 in
        self.assertIn("drafting_method", base["assumptions"])
        self.assertTrue(base["drafting_values"])
        self.assertIn("total_armhole_seam_cm", base["armhole"])

    def test_research_language(self):
        text = repr(self.out).lower()
        for claim in ("professionally validated", "industry standard", "perfect fit", "100% accurate", "aldrich-based"):
            self.assertNotIn(claim, text)
        self.assertIn("prototype", self.out["disclaimer"].lower())
        self.assertIn("geometric validation only", self.out["disclaimer"].lower())
        self.assertIn("toile", self.out["disclaimer"].lower())
        self.assertIn("not winifred aldrich", self.out["drafting_method"]["note"].lower())

    def test_armhole_sleeve_report_is_returned(self):
        info = self.out["armhole_sleeve"]
        self.assertGreater(info["total_armhole_seam_cm"], 30)
        cap = self.out["sleeve_cap"]
        self.assertEqual(cap["status"], "PASS")
        self.assertAlmostEqual(cap["difference_cm"], cap["sleeve_cap_seam_cm"] - cap["bodice_armhole_seam_cm"], delta=0.011)
        self.assertTrue(cap["allowed_cm"][0] <= cap["difference_cm"] <= cap["allowed_cm"][1])
        lengths = self.out["armhole_lengths"]
        self.assertAlmostEqual(lengths["front_armhole_curve_cm"] + lengths["back_armhole_curve_cm"],
                               lengths["total_armhole_cm"], delta=0.011)
        self.assertGreater(lengths["front_armhole_curve_cm"], lengths["back_armhole_curve_cm"])


# ── route integration: validated measurements + confirmed design_spec -> API ──
_APP = None


def _client():
    global _APP
    if _APP is None:
        _APP = create_app()
        _APP.config["TESTING"] = True
    return _APP.test_client()


def _headers():
    with _APP.app_context():
        return {"Authorization": f"Bearer {create_access_token(identity='user-1')}"}


def _profile(profile="medium", **over):
    base = dict(PROFILES[profile], fabric_type="woven",
                fit_preference="standard", original_values={}, id="m1", unit="cm")
    base.update(over)
    return SimpleNamespace(**base)


def _image(attrs):
    clean, _ = fs.validate_attributes(attrs)
    return SimpleNamespace(
        id="img1", user_id=SimpleNamespace(id="user-1"), file_path="x.jpg", garment_attributes={},
        confirmed_attributes=clean, design_spec=fs.build_design_spec(clean, None, confirmed_to_cad_features(clean)),
        detected_features={}, confidence_score=0.0, confirmed_at=None, save=MagicMock())


class TestGenerateRouteIntegration(unittest.TestCase):
    def _post(self, profile, attrs, fabric_id="cotton-poplin"):
        client = _client()
        with patch("app.routes.patterns.User") as u, patch("app.routes.patterns.MeasurementProfile") as mp, \
             patch("app.routes.patterns.DesignImage") as di, patch("app.routes.patterns.Session") as sess, \
             patch("app.routes.patterns.PatternResult") as pr:
            u.objects.return_value.first.return_value = object()
            mp.objects.return_value.first.return_value = profile
            di.objects.return_value.first.return_value = _image(attrs)
            pr.return_value.id, sess.return_value.id = "p1", "s1"
            resp = client.post("/api/patterns/generate", headers=_headers(),
                               json={"measurement_id": "m1", "image_id": "img1", "fabric_id": fabric_id})
            return resp, pr

    def test_multiple_profiles_and_designs_return_valid_final_patterns(self):
        cases = [
            ("small", design(), {}),
            ("medium", design(neckline="v-neck", length="long-sleeve"), {}),
            ("large", design(neckline="square-neck", length="long-sleeve"), {}),
            ("medium", design(neckline="square-neck", length="sleeveless", style="none"), {}),
        ]
        for profile, attrs, over in cases:
            resp, pr = self._post(_profile(profile, **over), attrs)
            self.assertEqual(resp.status_code, 201, (profile, attrs, resp.get_json()))
            body = resp.get_json()
            self.assertTrue(body["validation_passed"])
            self.assertEqual(body["final_pattern"]["stage"], "final_pattern")
            self.assertEqual(body["base_block"]["stage"], "base_block")
            self.assertEqual(body["design_attributes"] if "design_attributes" in body else attrs, attrs)
            self.assertIn("armhole_sleeve", body)
            saved = pr.call_args.kwargs
            self.assertEqual(saved["base_block"]["stage"], "base_block")
            self.assertEqual(saved["design_spec"]["attributes"], attrs)

    def test_a_length_above_the_waist_returns_422_with_field_error(self):
        resp, pr = self._post(_profile("medium", garment_length_cm=36), design())
        self.assertEqual(resp.status_code, 422)
        body = resp.get_json()
        self.assertEqual(body["error_code"], "DESIGN_MEASUREMENT_CONFLICT")
        self.assertIn("garment_length_cm", body["field_errors"])
        pr.assert_not_called()

    def test_undraftable_measurements_return_422_not_a_pattern(self):
        resp, pr = self._post(_profile("medium", shoulder_width_cm=60.0), design())
        self.assertEqual(resp.status_code, 422)
        self.assertEqual(resp.get_json()["error_code"], "MEASUREMENTS_NOT_DRAFTABLE")
        pr.assert_not_called()

    def test_stretch_knit_is_rejected_by_the_route(self):
        resp, pr = self._post(_profile("medium", fabric_type="stretch-knit"), design(garment_type="t-shirt"),
                              fabric_id="cotton-jersey-knit")
        self.assertEqual(resp.status_code, 422)
        self.assertEqual(resp.get_json()["error_code"], "UNSUPPORTED_FABRIC_TYPE")
        pr.assert_not_called()


    def test_incompatible_fabric_is_rejected_not_redrafted(self):
        resp, pr = self._post(_profile("medium", fabric_type="knit"), design(garment_type="t-shirt"),
                              fabric_id="cotton-poplin")
        self.assertEqual(resp.status_code, 422)
        self.assertEqual(resp.get_json()["error_code"], "FABRIC_NOT_COMPATIBLE")
        pr.assert_not_called()

    def test_the_selected_fabric_not_the_profile_decides_the_construction(self):
        """A profile that still says knit drafts a woven blouse when a woven fabric is selected."""
        resp, pr = self._post(_profile("medium", fabric_type="knit"), design(), fabric_id="cotton-poplin")
        self.assertEqual(resp.status_code, 201, resp.get_json())
        self.assertEqual(pr.call_args.kwargs["measurements_snapshot"]["fabric_type"], "woven")


class TestSupportTableMatchesImplementation(unittest.TestCase):
    def test_support_levels_of_the_taxonomy(self):
        self.assertEqual(fs.support_of("neckline_type", "v-neck")[0], fs.IMPLEMENTED)
        self.assertEqual(fs.support_of("neckline_type", "collared-neck")[0], fs.UNSUPPORTED)
        self.assertIsNone(fs.support_of("garment_type", "crop-top"))             # no longer in the taxonomy
        self.assertIsNone(fs.support_of("neckline_type", "off-shoulder"))

    def test_every_implemented_design_actually_drafts(self):
        b = {n: make_base(garment=n, fabric="knit" if n == "t-shirt" else "woven") for n in ("blouse", "t-shirt")}
        for head in ("neckline_type", "sleeve_length", "sleeve_style"):
            for value in fs.TAXONOMY[head]:
                if fs.support_of(head, value)[0] == fs.UNSUPPORTED:
                    continue
                drafted = 0
                for garment in b:                                     # every garment whose scope includes the value
                    attrs = design(garment_type=garment)
                    attrs[head] = value
                    if attrs["sleeve_length"] == "sleeveless" or value == "none":
                        attrs.update(sleeve_length="sleeveless", sleeve_style="none")
                    if fs.is_draftable(attrs):
                        apply_design(b[garment], attrs)               # must not raise
                        drafted += 1
                self.assertGreater(drafted, 0, f"{head}={value} is marked implemented but no garment can use it")

    def test_every_unsupported_value_is_actually_rejected(self):
        b = make_base()
        for head in ("neckline_type", "sleeve_length", "sleeve_style"):
            for value in fs.TAXONOMY[head]:
                if fs.support_of(head, value)[0] != fs.UNSUPPORTED:
                    continue
                attrs = design()
                attrs[head] = value
                with self.assertRaises(DraftingError, msg=f"{head}={value}"):
                    apply_design(b, attrs)


if __name__ == "__main__":
    unittest.main()
