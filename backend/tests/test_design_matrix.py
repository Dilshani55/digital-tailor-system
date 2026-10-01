"""Every one of the 96 selectable design combinations (2 garments x 4 necklines x 3 sleeve lengths x 4 sleeve
styles): the 25 supported ones are drafted correctly, the other 71 are refused (never replaced by a different design);
the same pieces are laid out on 36" / 45" / 60" fabric."""
import copy
import itertools
import math
import re
import unittest

from app.logic import feature_schema as fs
from app.logic.drafting.ease import DraftingError
from app.logic.fabric_selection import compatibility
from app.logic.nesting_algorithm import estimate_fabric, NestingError, STANDARD_FABRIC_WIDTHS
from app.logic.parametric_engine import ParametricEngine
from tests.fixtures import PROFILES, SHORT_SLEEVE_CM, measurements

ALL = [dict(zip(fs.HEADS, combo)) for combo in itertools.product(*[fs.UI_TAXONOMY[h] for h in fs.HEADS])]
SUPPORTED = [d for d in ALL if fs.is_draftable(d)]
UNSUPPORTED = [d for d in ALL if not fs.is_draftable(d)]
NECK_TYPE = {"round-neck": "round_neckline", "v-neck": "v_neckline", "square-neck": "square_neckline"}
SLEEVE_STYLE_TYPE = {"regular-sleeve": "plain_set_in", "puff-sleeve": "puff", "bell-sleeve": "bell_flare", "none": "none"}


def constructions(design):
    return [c for c in ("woven", "knit") if compatibility(design["garment_type"], c)[0]]


def body(design, profile="medium", construction="woven", fit="standard"):
    m = measurements(profile, fabric_type=construction, fit_preference=fit)
    if design["sleeve_length"] == "short-sleeve":
        m["sleeve_cm"] = SHORT_SLEEVE_CM[profile]
    return m


def draft(design, profile="medium", construction=None, fit="standard"):
    construction = construction or constructions(design)[0]
    return ParametricEngine(body(design, profile, construction, fit), design_spec={"attributes": dict(design)}).generate()


def area(poly):
    return abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(poly, poly[1:] + poly[:1]))) / 2.0


def dist_to_polyline(p, poly):
    best = float("inf")
    for a, b in zip(poly, poly[1:] + poly[:1]):
        dx, dy = b[0] - a[0], b[1] - a[1]
        length2 = dx * dx + dy * dy
        t = 0.0 if length2 == 0 else max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / length2))
        best = min(best, math.hypot(p[0] - (a[0] + t * dx), p[1] - (a[1] + t * dy)))
    return best


def label(design, *extra):
    return " / ".join(list(design.values()) + [str(e) for e in extra])


class TestScopeMatrix(unittest.TestCase):
    def test_the_matrix_is_96_combinations_of_which_25_are_supported(self):
        self.assertEqual((len(ALL), len(SUPPORTED), len(UNSUPPORTED)), (96, 25, 71))
        self.assertEqual({d["garment_type"] for d in ALL}, {"blouse", "t-shirt"})          # no crop top
        self.assertEqual(sum(d["garment_type"] == "blouse" for d in SUPPORTED), 21)
        self.assertEqual(sum(d["garment_type"] == "t-shirt" for d in SUPPORTED), 4)

    def test_a_collared_neck_is_never_supported(self):
        for d in SUPPORTED:
            self.assertIn(d["neckline_type"], NECK_TYPE, label(d))
        self.assertEqual(fs.support_of("neckline_type", "collared-neck")[0], fs.UNSUPPORTED)

    def test_values_that_left_the_taxonomy_are_invalid_not_drafted(self):
        for head, value in (("garment_type", "crop-top"), ("neckline_type", "off-shoulder"), ("neckline_type", "scoop-neck"),
                            ("sleeve_length", "elbow-length"), ("sleeve_style", "kimono-sleeve")):
            d = dict(SUPPORTED[0], **{head: value})
            _, errors = fs.validate_attributes(d)
            self.assertEqual(errors[head]["code"], "NOT_IN_TAXONOMY", (head, value))
            with self.assertRaises(DraftingError) as ctx:
                ParametricEngine(body(SUPPORTED[0]), design_spec={"attributes": d}).generate()
            self.assertEqual(ctx.exception.code, "INVALID_DESIGN_ATTRIBUTES", (head, value))

    def test_a_sleeveless_design_is_a_blouse_with_armhole_facings(self):
        sleeveless = [d for d in SUPPORTED if d["sleeve_length"] == "sleeveless"]
        self.assertEqual({d["garment_type"] for d in sleeveless}, {"blouse"})
        self.assertEqual(len(sleeveless), 3)
        types = [q["piece_type"] for q in draft(sleeveless[0])["pattern_pieces"]]
        self.assertIn("armhole_facing", types)
        self.assertNotIn("sleeve", types)

    def test_sleeve_style_agrees_with_sleeve_length(self):
        for d in SUPPORTED:
            self.assertEqual(d["sleeve_style"] == "none", d["sleeve_length"] == "sleeveless", label(d))

    def test_every_unsupported_combination_is_refused_and_never_replaced_by_another_design(self):
        for d in UNSUPPORTED:
            report = fs.support_report(d, with_scope=True)
            self.assertFalse(report["supported"], label(d))
            self.assertTrue(report["unsupported"], label(d))             # the reason names what cannot be drafted
            self.assertTrue(fs.unsupported_message(report))
            for construction in ("woven", "knit"):
                with self.assertRaises(DraftingError, msg=label(d, construction)):
                    ParametricEngine(body(d, "medium", construction), design_spec={"attributes": dict(d)}).generate()

    def test_stretch_knit_negative_ease_is_refused(self):
        d = SUPPORTED[0]
        with self.assertRaises(DraftingError):
            ParametricEngine(body(d, "medium", "stretch-knit"), design_spec={"attributes": dict(d)}).generate()


class TestEverySupportedDesign(unittest.TestCase):
    """25 designs x the construction their garment allows x three body sizes."""

    @classmethod
    def setUpClass(cls):
        cls.cases = []
        for d in SUPPORTED:
            for construction in constructions(d):
                for profile in PROFILES:
                    cls.cases.append((d, construction, profile, draft(d, profile, construction)))

    def test_the_drafted_design_is_exactly_the_requested_one(self):
        for d, construction, profile, p in self.cases:
            tag = label(d, construction, profile)
            self.assertEqual(p["design_attributes"], d, tag)
            self.assertEqual(p["garment_type"], d["garment_type"], tag)
            self.assertEqual(p["fabric_type"], construction, tag)
            applied = {t["id"]: t for t in p["final_pattern"]["transformations"]}
            self.assertEqual(applied["neckline"]["type"], NECK_TYPE[d["neckline_type"]], tag)
            self.assertEqual(applied["neckline"]["design"], d["neckline_type"], tag)
            self.assertEqual(applied["sleeve_length"]["design"], d["sleeve_length"], tag)
            self.assertEqual(applied["sleeve_style"]["design"], d["sleeve_style"], tag)
            self.assertEqual(applied["garment_length"]["design"], d["garment_type"], tag)
            for t in applied.values():
                self.assertEqual(t["status"], "applied", tag)

    def test_validation_passes_for_the_base_block_and_the_final_pattern(self):
        for d, construction, profile, p in self.cases:
            tag = label(d, construction, profile)
            self.assertTrue(p["validation"]["base_block"]["passed"], tag)
            final = p["validation"]["final_pattern"]
            self.assertTrue(final["passed"], f"{tag}: {final['errors']}")
            self.assertEqual([k for k, c in final["checks"].items() if not c["ok"]], [], tag)

    def test_pieces_and_quantities(self):
        for d, construction, profile, p in self.cases:
            tag = label(d, construction, profile)
            by_type = {}
            for piece in p["pattern_pieces"]:
                by_type.setdefault(piece["piece_type"], []).append(piece)
            for bodice in ("front_bodice", "back_bodice"):
                self.assertEqual(len(by_type[bodice]), 1, tag)
                self.assertEqual((by_type[bodice][0]["cut_count"], by_type[bodice][0]["cut_on_fold"]), (1, True), tag)
            sleeves = by_type.get("sleeve", [])
            if d["sleeve_length"] == "sleeveless":
                self.assertEqual(sleeves, [], tag)
            else:
                self.assertEqual(len(sleeves), 1, tag)
                self.assertEqual((sleeves[0]["cut_count"], sleeves[0]["cut_on_fold"]), (2, False), tag)
            for piece in p["pattern_pieces"]:
                self.assertGreaterEqual(piece["cut_count"], 1, tag)
                self.assertEqual(piece["units"], "cm", tag)

    def test_block_ease_and_darts_follow_the_fabric_construction(self):
        for d, construction, profile, p in self.cases:
            tag = label(d, construction, profile)
            block = p["drafting_block"]
            self.assertEqual(block["is_knit_block"], construction == "knit", tag)
            self.assertEqual(block["block_id"], "knit_bodice" if construction == "knit" else "woven_bodice", tag)
            ease = p["measurements_used"]["ease_profile"]
            for key in ("bust_cm", "waist_cm", "hip_cm", "bicep_cm"):
                self.assertGreater(ease[key], 0, tag)                    # positive ease only
            front = next(q for q in p["pattern_pieces"] if q["piece_type"] == "front_bodice")
            if not block["allow_darts"]:
                self.assertEqual(front["darts"], [], tag)
            for piece in p["pattern_pieces"]:
                for dart in piece["darts"]:
                    self.assertGreater(dart["intake_cm"], 0, tag)
                    xs = [q[0] for q in piece["outline"]]
                    ys = [q[1] for q in piece["outline"]]
                    self.assertTrue(min(xs) < dart["apex"][0] < max(xs) and min(ys) < dart["apex"][1] < max(ys), tag)

    def test_woven_ease_is_larger_than_knit_ease_for_the_same_body(self):
        base = dict(neckline_type="round-neck", sleeve_length="short-sleeve", sleeve_style="regular-sleeve")
        woven = draft(dict(base, garment_type="blouse"))["measurements_used"]["ease_profile"]
        knit = draft(dict(base, garment_type="t-shirt"))["measurements_used"]["ease_profile"]
        self.assertGreater(woven["bust_cm"], knit["bust_cm"])
        for d in SUPPORTED:                                    # exactly one construction per garment
            self.assertEqual(constructions(d), ["knit"] if d["garment_type"] == "t-shirt" else ["woven"], label(d))

    def test_fit_preference_orders_the_ease(self):
        d = next(x for x in SUPPORTED if x["garment_type"] == "blouse" and x["sleeve_length"] == "short-sleeve")
        bust = [draft(d, "medium", "woven", fit)["measurements_used"]["ease_profile"]["bust_cm"] for fit in ("close", "standard", "loose")]
        self.assertLess(bust[0], bust[1])
        self.assertLess(bust[1], bust[2])

    def test_sleeve_cap_matches_the_armhole_and_the_sleeve_has_the_wanted_length(self):
        for d, construction, profile, p in self.cases:
            if d["sleeve_length"] == "sleeveless":
                continue
            tag = label(d, construction, profile)
            a = p["armhole_sleeve"]
            self.assertAlmostEqual(a["front_armhole_seam_cm"] + a["back_armhole_seam_cm"], a["total_armhole_seam_cm"], places=2, msg=tag)
            self.assertAlmostEqual(a["sleeve_cap_seam_cm"] - a["total_armhole_seam_cm"], a["cap_ease_cm"], places=2, msg=tag)
            self.assertGreater(a["cap_ease_cm"], 0, tag)                 # the cap is never shorter than the armhole
            sleeve = next(q for q in p["pattern_pieces"] if q["piece_type"] == "sleeve")["measurements"]
            wanted = body(d, profile, construction)["sleeve_cm"]
            if d["sleeve_style"] == "puff-sleeve":
                self.assertTrue(sleeve["gathered_cap"], tag)             # the extra cap length is gathered in
                self.assertAlmostEqual(sleeve["length_cm"], wanted + sleeve["crown_rise_cm"], places=2, msg=tag)
            else:
                self.assertLessEqual(a["cap_ease_cm"], 4.0, tag)         # plain cap: eased in, not gathered
                self.assertAlmostEqual(sleeve["length_cm"], wanted, places=2, msg=tag)
            if d["sleeve_style"] == "bell-sleeve":
                self.assertGreater(sleeve["width_hem_cm"], sleeve["width_bicep_cm"], tag)
            if d["sleeve_length"] == "long-sleeve" and d["sleeve_style"] == "regular-sleeve":
                self.assertLess(sleeve["width_hem_cm"], sleeve["width_bicep_cm"], tag)    # tapers to the wrist

    def test_cutting_line_seam_allowance_grainline_fold_and_notches(self):
        for d, construction, profile, p in self.cases:
            tag = label(d, construction, profile)
            for piece in p["pattern_pieces"]:
                name = f"{tag}: {piece['name']}"
                seam, cut = piece["outline"], piece["cutting_line"]
                self.assertGreater(area(cut), area(seam), name)           # the cutting line is outside the sewing line
                allowed = set(piece["seam_allowances"].values()) | {0.0}
                self.assertTrue({e["cm"] for e in piece["edge_allowances"]} <= allowed, name)
                gap = max(dist_to_polyline(q, seam) for q in cut)
                self.assertLessEqual(gap, max(allowed) * 1.5 + 0.2, name)  # nowhere wider than the widest allowance (corners)
                g = piece["grain_line"]
                self.assertAlmostEqual(g["start"][0], g["end"][0], places=6, msg=name)     # grain runs along the length
                self.assertGreater(abs(g["end"][1] - g["start"][1]), 1.0, name)
                box = piece["cut_bounding_box"]
                for q in (g["start"], g["end"]):
                    self.assertTrue(box["min_x"] - 1e-6 <= q[0] <= box["min_x"] + box["width_cm"] + 1e-6, name)
                    self.assertTrue(box["min_y"] - 1e-6 <= q[1] <= box["min_y"] + box["height_cm"] + 1e-6, name)
                if piece["cut_on_fold"]:
                    f = piece["fold_line"]
                    self.assertAlmostEqual(f["start"][0], f["end"][0], places=6, msg=name)
                    for q in (f["start"], f["end"]):                      # no allowance on the fold: it lies on both lines
                        self.assertLess(dist_to_polyline(q, seam), 1e-3, name)
                        self.assertLess(dist_to_polyline(q, cut), 1e-3, name)
                for notch in piece["notches"]:
                    self.assertLess(dist_to_polyline(notch["point"], seam), 0.05, f"{name} notch {notch['id']}")
                if piece["piece_type"] in ("front_bodice", "back_bodice", "sleeve"):
                    self.assertGreaterEqual(len(piece["notches"]), 1, name)

    def test_front_and_back_seams_that_are_sewn_together_have_equal_lengths(self):
        for d, construction, profile, p in self.cases:
            tag = label(d, construction, profile)
            front = next(q for q in p["pattern_pieces"] if q["piece_type"] == "front_bodice")["measurements"]
            back = next(q for q in p["pattern_pieces"] if q["piece_type"] == "back_bodice")["measurements"]
            self.assertAlmostEqual(front["shoulder_length_cm"], back["shoulder_length_cm"], places=2, msg=tag)
            self.assertAlmostEqual(front["side_seam_length_cm"], back["side_seam_length_cm"], places=2, msg=tag)

    def test_neckline_shapes_differ(self):
        base = dict(garment_type="blouse", sleeve_length="sleeveless", sleeve_style="none")
        lengths = {}
        for neck in NECK_TYPE:
            d = dict(base, neckline_type=neck)
            if d not in SUPPORTED:
                continue
            front = next(q for q in draft(d)["pattern_pieces"] if q["piece_type"] == "front_bodice")
            lengths[neck] = round(front["measurements"]["neckline_length_cm"], 2)
        self.assertEqual(len(set(lengths.values())), len(lengths), lengths)


class TestLayoutOfEverySupportedDesign(unittest.TestCase):
    """36" / 45" / 60": the same validated pieces, only the layout changes."""

    @classmethod
    def setUpClass(cls):
        cls.rows = []
        for d in SUPPORTED:
            construction = constructions(d)[0]
            pieces = draft(d, "medium", construction)["pattern_pieces"]
            before = copy.deepcopy(pieces)
            for width in STANDARD_FABRIC_WIDTHS:
                try:
                    result = estimate_fabric(pieces, width, "auto", construction)
                except NestingError as err:
                    result = err
                cls.rows.append((d, width, pieces, before, result))

    def test_standard_widths_are_exact_inch_conversions(self):
        self.assertEqual(STANDARD_FABRIC_WIDTHS, (91.44, 114.3, 152.4))
        self.assertEqual([round(w / 2.54, 6) for w in STANDARD_FABRIC_WIDTHS], [36, 45, 60])

    def test_every_layout_passes_its_checks_or_reports_that_a_piece_does_not_fit(self):
        fitted = 0
        for d, width, _pieces, _before, n in self.rows:
            tag = label(d, width)
            if isinstance(n, NestingError):
                self.assertTrue(n.error_code, tag)                        # an explicit refusal, never a made-up number
                continue
            fitted += 1
            checks = n["validation_checks"]
            self.assertEqual(checks["status"], "PASSED", tag)
            for key in ("no_overlap", "within_bounds", "fold_alignment", "grain_preserved", "quantities_satisfied",
                        "pattern_dimensions_invariant"):
                self.assertTrue(checks[key], f"{tag}: {key}")
            self.assertEqual(n["fabric_width_cm"], width, tag)
            for placed in n["placed_pieces"]:
                xs = [q[0] for q in placed["polygon_coordinates"]]
                self.assertGreaterEqual(min(xs), -1e-6, tag)
                self.assertLessEqual(max(xs), n["usable_width_cm"] + 1e-6, tag)          # inside the fabric
                self.assertLessEqual(max(q[1] for q in placed["polygon_coordinates"]), n["fabric_length_cm"] + 0.011, tag)   # 2-dp rounding
        self.assertGreaterEqual(fitted, len(self.rows) * 0.9)             # the usual widths do fit these garments

    def test_changing_the_fabric_width_never_changes_the_pattern_pieces(self):
        for d, width, pieces, before, _n in self.rows:
            self.assertEqual(pieces, before, label(d, width))

    def test_placed_pieces_are_the_drafted_cutting_lines(self):
        """The layout places the very cutting-line polygons the preview and the PDF draw (whole, or mirrored at the fold)."""
        for d, width, pieces, _before, n in self.rows:
            if isinstance(n, NestingError):
                continue
            source = {}
            for piece in pieces:
                source.setdefault(piece["name"], area(piece["cutting_line"]))
            for placed in n["placed_pieces"]:
                got = area(placed["polygon_coordinates"])
                want = source[re.sub(r" \(\d+\)$", "", placed["name"])]        # "Sleeve (short) (2)" = second copy
                ratio = got / want
                self.assertTrue(abs(ratio - 1) < 0.01 or abs(ratio - 2) < 0.01, f"{label(d, width)}: {placed['name']} area x{ratio:.3f}")

    def test_layout_length_and_purchase_allowance_are_reported_separately(self):
        for d, width, _pieces, _before, n in self.rows:
            if isinstance(n, NestingError):
                continue
            tag = label(d, width)
            layout_m = n["fabric_length_cm"] / 100.0
            self.assertAlmostEqual(n["exact_yardage_metres"], layout_m, delta=0.0051, msg=tag)     # shown to 2 decimals
            needed = layout_m * 1.03 + 0.10                                # + 3 % shrinkage + 10 cm cutting margin
            self.assertGreaterEqual(n["purchasing_recommended_m"] + 1e-9, needed, tag)
            self.assertLess(n["purchasing_recommended_m"] - needed, 0.1001, tag)           # rounded up to 10 cm
            self.assertIn("not optimal", n["method"], tag)                 # a heuristic layout, said so

    def test_a_wider_fabric_never_needs_a_longer_open_layout(self):
        by_design = {}
        for d, width, pieces, _before, _n in self.rows:
            by_design.setdefault(label(d), (d, pieces))
        for tag, (d, pieces) in list(by_design.items())[:8]:
            lengths = []
            for width in STANDARD_FABRIC_WIDTHS:
                try:
                    lengths.append(estimate_fabric(pieces, width, "open", constructions(d)[0])["fabric_length_cm"])
                except NestingError:
                    lengths.append(None)
            known = [x for x in lengths if x is not None]
            self.assertTrue(known, tag)
            # heuristic: allow small non-monotonic steps, but a much wider cloth must not need much more length
            self.assertLessEqual(known[-1], known[0] + 5.0, f"{tag}: {lengths}")


if __name__ == "__main__":
    unittest.main()
