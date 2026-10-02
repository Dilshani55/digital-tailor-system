"""
Every number the drafting engine uses that is not a customer measurement - with where it comes from.

DRAFTING METHOD (one method, used consistently)
    "Drafting the adult's bodice and sleeve pattern", in: Pattern Making and Grading - study material for
    B.Sc. Fashion Technology, Semester I, 2022-2023, Kamaraj College (pages 3-6: principles of drafting, bodice
    draft, sleeve draft, seam allowances).
    https://kamarajwomenscollege.ac.in/wp-content/uploads/Allied-1-Pattern-Making-and-Grading.pdf
    Read on 2 Oct 2026. The source works in inches; this engine converts with 1 in = 2.54 cm exactly.

    It is a direct-measurement draft: quarter widths, neck width from the bust, a fixed shoulder drop, front
    wider than the back, a deeper front armhole, fixed waist darts. No other drafting system is mixed in. This
    is NOT Winifred Aldrich's block: her book is not available in this project and none of its equations was
    checked, so nothing here may be called "Aldrich".

KIND of every entry
    method     a value or rule stated in the source (the page is given)
    figure     read from the source's figure because the text does not state it
    design     a design preset: sensible default, may be changed per garment
    ease       wearing ease (body measurement + ease = garment measurement)
    seam       seam allowance (sewing line -> cutting line); never part of the ease
    extension  needed for this project and NOT covered by the source (hip-length garments, knit T-shirts, checks
               against the customer's arm ...). Each one says so and must be confirmed by a fitting trial.
"""

IN = 2.54

SOURCE = {
    "title": "Pattern Making and Grading - study material for B.Sc. Fashion Technology (Semester I, 2022-2023): "
             "Drafting the adult's bodice and sleeve pattern, pp. 3-6",
    "publisher": "Kamaraj College, Department of Fashion Technology",
    "url": "https://kamarajwomenscollege.ac.in/wp-content/uploads/Allied-1-Pattern-Making-and-Grading.pdf",
    "accessed": "2026-10-02",
    "unit_of_source": "inch (1 in = 2.54 cm exactly)",
}

METHOD, FIGURE, DESIGN, EASE, SEAM, EXTENSION = "method", "figure", "design", "ease", "seam", "extension"


def _c(kind, value, note, page=None):
    return {"kind": kind, "value": value, "note": note, "source_page": page}


def _in(inches):
    return round(inches * IN, 6)


CONSTANTS = {
    # ── bodice: widths ──
    "front_back_balance_cm": _c(METHOD, _in(0.5),
        "AE = half the block width - 1/2 in: the back quarter is 1/2 in narrower and the front quarter 1/2 in wider "
        "than a quarter of (bust + ease), so the front is 2 in larger than the back all round.", 4),
    "neck_width_bust_fraction": _c(METHOD, 1.0 / 12.0,
        "Back neck width AH = 1/12 bust (the sample gives 2 3/4 in for a 34 in bust).", 5),
    "front_neck_narrower_cm": _c(METHOD, _in(0.25), "Front neck width BH1 = AH - 1/4 in.", 5),
    "back_neck_depth_cm": _c(DESIGN, _in(1.0), "Back neck depth AJ = 1 in (the source's value; a design value).", 4),
    "front_neck_depth_extra_cm": _c(METHOD, _in(0.25), "Front neck depth BJ1 = 1/12 bust + 1/4 in.", 5),
    "front_neck_raise_cm": _c(METHOD, _in(0.375),
        "Front neck point H2 is 1/4 to 1/2 in above H1 for bust sizes above 31 in (3/8 in is used).", 5),
    "front_neck_raise_min_bust_cm": _c(METHOD, _in(31.0), "The raise applies for bust sizes above 31 in.", 5),
    "shoulder_drop_cm": _c(DESIGN, _in(1.0),
        "Shoulder tip K is 1 in below the top line (GK = G1K1 = 1 in). A design value: sloping or square "
        "shoulders need another drop.", 4),
    "front_shoulder_tip_in_cm": _c(METHOD, _in(0.25), "Front shoulder tip BG1 = half back width - 1/4 in.", 5),
    # ── bodice: levels ──
    "armhole_depth_less_cm": _c(METHOD, _in(1.0), "Armhole depth EO = 1/4 bust - 1 in.", 5),
    "armhole_depth_less_small_bust_cm": _c(METHOD, _in(0.5), "For a bust under 30 in: EO = 1/4 bust - 1/2 in.", 5),
    "small_bust_limit_cm": _c(METHOD, _in(30.0), "Bust size below which the smaller reduction is used.", 5),
    "waist_line_extra_cm": _c(METHOD, _in(0.5), "Block length BC = back waist length + 1/2 in.", 4),
    # ── armhole curves ──
    "back_armscye_straight_share": _c(METHOD, 1.0 / 3.0, "KX = 1/3 KL: the back armhole runs straight for a third.", 5),
    "front_armscye_hollow_upper_cm": _c(METHOD, _in(0.5), "XX2 = 1/2 in: the front armhole is hollowed at one third.", 5),
    "front_armscye_hollow_lower_cm": _c(METHOD, _in(0.375), "YY1 = 3/8 in: the front armhole is hollowed at two thirds.", 5),
    # ── waist ──
    "waist_front_back_shift_cm": _c(METHOD, _in(0.25),
        "Back waist = 1/2 waist - 1/2 in, front waist = 1/2 waist + 1/2 in: a quarter of the waist -/+ 1/4 in.", 5),
    "back_dart_width_cm": _c(METHOD, _in(1.0), "Back waist dart: 1 in wide (NQ = NR = 1/2 in).", 5),
    "back_dart_short_of_underarm_cm": _c(METHOD, _in(1.0), "Back dart length NP = underarm-to-waist - 1 in.", 5),
    "front_dart_width_cm": _c(METHOD, _in(1.5), "Front waist dart: 1 1/2 in wide (3/4 in each side).", 5),
    "front_dart_below_bust_point_cm": _c(METHOD, _in(0.75), "Front dart point P1 is 3/4 in below the bust point T.", 5),
    "shoulder_to_bust_ease_cm": _c(METHOD, _in(0.25), "BS = shoulder to bust point + 1/4 in ease.", 5),
    "bust_point_half_distance_bust_fraction": _c(METHOD, 1.0 / 10.0,
        "ST = half the distance between the bust points; \"this will be about one tenth bust\" - used when the "
        "distance is not measured.", 5),
    "front_length_extra_cm": _c(FIGURE, _in(1.0),
        "The front hem line M2-C1 lies 1 in below the waist line (M2 is 1 in below M1; C1 is read from the figure): "
        "extra front length over the bust, taken up by the side-seam dart.", 5),
    "side_dart_below_bust_level_cm": _c(METHOD, _in(1.5), "Side-seam dart: U is about 1 1/2 in below the level of T.", 5),
    "side_dart_point_from_bust_point_cm": _c(METHOD, _in(1.5), "Side-seam dart point U1 is 1 1/2 in from T on UT.", 5),
    # ── sleeve ──
    "sleeve_half_width_less_than_armhole_depth_cm": _c(METHOD, _in(0.5),
        "Half sleeve width AB = 1/4 bust - 1 1/2 in = armhole depth EO - 1/2 in (whole sleeve = 1/2 bust - 3 in).", 5),
    "sleeve_cap_height_share": _c(METHOD, 0.5, "Cap height BE = 1/2 AB (half of the half sleeve width).", 5),
    "sleeve_cap_back_offsets_cm": _c(METHOD, (_in(0.5), _in(0.25), -_in(0.25)),
        "Back cap through g, f, e: 1/2 in and 1/4 in outside the diagonal A-E at 1/4 and 1/2 of it, 1/4 in inside at "
        "3/4 (directions read from the figure).", 5),
    "sleeve_cap_front_offsets_cm": _c(METHOD, (_in(0.5), 0.0, -_in(0.625)),
        "Front cap through g, b, d: 1/2 in outside at 1/4, on the diagonal at 1/2, 5/8 in inside at 3/4.", 5),
    # ── balance marks ──
    "back_notch": _c(METHOD, "one notch at Z", "Z is the midpoint of the curved part of the back armhole (OX).", 5),
    "front_notch": _c(METHOD, "two notches at Y1", "Y1 is two thirds down the front armhole.", 5),
    # ── design presets (sleeve styles, necklines) ──
    "v_neck_extra_depth_cm": _c(DESIGN, 3.0, "V-neck centre-front point = front neck depth + 3.0 cm."),
    "puff_spread_fraction": _c(DESIGN, 0.5, "Puff sleeve: the plain sleeve is spread to 1.5 x its width (slash and spread)."),
    "puff_crown_rise_cm": _c(DESIGN, 2.5, "Puff sleeve: crown raised by 2.5 cm so the gathered cap stands up."),
    "puff_gather_excess_range_cm": _c(DESIGN, (4.0, 30.0), "Accepted (puff cap seam - armhole seam), gathered between the notches."),
    "puff_band_height_cm": _c(DESIGN, 2.5, "Short puff sleeve: finished band height; the band is cut double."),
    "bell_flare_fraction": _c(DESIGN, {"short-sleeve": 0.6, "long-sleeve": 0.9},
        "Bell sleeve: hem width = sleeve width x (1 + fraction); the cap stays the fitted cap."),
    "facing_width_cm": _c(DESIGN, 4.0, "Armhole facing strip width (sleeveless)."),
    "neckband_stretch_factor": _c(DESIGN, 0.85, "Knit neckband length = 0.85 x neckline seam length."),
    "neckband_height_cm": _c(DESIGN, 3.0, "Neckband strip height."),
    # ── extensions: not in the source ──
    "hip_quarter_split": _c(EXTENSION, "front + back = (hip + ease) / 2; same run-out from the waist on both",
        "Below the waist the source gives no draft. The side seam runs from the waist edge to the hip line at the "
        "measured waist-to-hip depth, then straight down to the hem. Front and back together are half of (hip + "
        "ease); the front keeps the extra width it has at the waist, so both side seams are equally long."),
    "fish_dart_lower_share": _c(EXTENSION, 0.5,
        "In a garment longer than the waist a waist dart is closed below the waist too (fish dart); its lower half "
        "is 0.5 x its upper half, kept 2 cm above the hem."),
    "dart_reduced_for_large_waist": _c(EXTENSION, "min(method dart, block width - finished waist quarter)",
        "The source's fixed darts assume a waist clearly smaller than the bust. When the waist edge would be wider "
        "than the block, the dart is reduced (to zero if necessary) instead of adding width and darting it out."),
    "knit_block": _c(EXTENSION, "no darts, equal front and back widths, no front neck raise, no extra front length",
        "The source drafts a fitted woven bodice. A knit T-shirt is drafted with the same construction lines but "
        "without the bust shaping (stretch replaces it)."),
    "sleeve_width_check": _c(EXTENSION, "sleeve width = max(method width, upper arm + ease)",
        "The source derives the sleeve width from the bust only. When that is narrower than the customer's upper arm "
        "plus ease, the measured arm decides, and the change is reported."),
    "sleeve_end_width": _c(EXTENSION, "sleeve end around + ease",
        "The source narrows the sample short sleeve by 1/2 to 1 in at the hem (CF). Here the hem width is the measured "
        "arm at the sleeve end plus ease, so short and long sleeves follow the arm."),
    "sleeve_cap_fit": _c(EXTENSION, "cap height adjusted only when needed",
        "The source's cap (height = half the half-width) is kept when its seam length exceeds the armhole seam by an "
        "amount inside the accepted cap-ease range; otherwise only the cap height is changed until it does."),
    "sleeve_notch_distance": _c(EXTENSION, "same seam distance from the underarm as the bodice notch",
        "The source marks the sleeve notches at one third of the cap. Here they are placed at exactly the bodice "
        "notches' distance from the underarm, so the marks really meet when the sleeve is set in."),
}

# ── ease (wearing ease, added to the BODY measurement) ───────────────────────
# woven: the source, principles of drafting (p. 3): bust 3-5 in (3 tight, 5 loose; the sample draft uses 3 1/2),
#        waist 1/4-1/2 in per quarter pattern, hip 3-5 in, upper arm 3-4 in.
# knit:  project presets (EXTENSION) - the source does not cover knit fabric.
EASE_PRESETS = {
    "woven_bodice": {
        "kind": EASE, "source_page": 3,
        "close":    {"bust": _in(3.0), "waist_quarter": _in(0.25), "hip": _in(3.0), "upper_arm": _in(3.0)},
        "standard": {"bust": _in(3.5), "waist_quarter": _in(0.25), "hip": _in(4.0), "upper_arm": _in(3.0)},
        "loose":    {"bust": _in(5.0), "waist_quarter": _in(0.5), "hip": _in(5.0), "upper_arm": _in(4.0)},
        "sleeve_end": 4.0, "cap_ease_range": (0.5, 4.5), "cap_ease_target": 2.0,
    },
    "knit_bodice": {
        "kind": EXTENSION, "source_page": None,
        "close":    {"bust": 4.0, "waist_quarter": 0.5, "hip": 4.0, "upper_arm": 3.0},
        "standard": {"bust": 6.0, "waist_quarter": 1.0, "hip": 6.0, "upper_arm": 4.0},
        "loose":    {"bust": 9.0, "waist_quarter": 1.75, "hip": 9.0, "upper_arm": 6.0},
        "sleeve_end": 2.0, "cap_ease_range": (0.0, 3.0), "cap_ease_target": 1.0,
    },
}
FIT_LABELS = {"close": "Close fit", "standard": "Regular fit", "loose": "Relaxed fit"}

# ── seam allowances (cm), per kind of edge ───────────────────────────────────
# Source (p. 6): armscye and sleeve cap 3/8-1/2 in; side seam or underarm seam 1/2-1 in; sleeve hem 1 in.
# Shoulder, neckline and garment hem are not given there: design presets of common sewing practice.
SEAM_ALLOWANCES = {
    "woven_bodice": {"shoulder": 1.5, "side": 1.5, "armhole": 1.0, "neckline": 1.0, "sleeve_seam": 1.5,
                     "sleeve_hem": 2.5, "hem": 2.5, "strip": 1.0},
    "knit_bodice": {"shoulder": 1.0, "side": 1.0, "armhole": 1.0, "neckline": 1.0, "sleeve_seam": 1.0,
                    "sleeve_hem": 2.0, "hem": 2.0, "strip": 0.7},
}
SEAM_ALLOWANCE_SOURCE = {
    "armhole": METHOD, "side": METHOD, "sleeve_seam": METHOD, "sleeve_hem": METHOD,
    "shoulder": DESIGN, "neckline": DESIGN, "hem": DESIGN, "strip": DESIGN,
}

A = {k: v["value"] for k, v in CONSTANTS.items()}


def assumptions_payload():
    """The registry for the API / PDF / documentation (kept under its earlier name)."""
    return {
        "drafting_method": dict(SOURCE),
        "constants": {k: dict(v) for k, v in CONSTANTS.items()},
        "ease_presets": {b: {k: (dict(v) if isinstance(v, dict) else v) for k, v in p.items()} for b, p in EASE_PRESETS.items()},
        "seam_allowances_cm": {b: dict(t) for b, t in SEAM_ALLOWANCES.items()},
        "seam_allowance_source": dict(SEAM_ALLOWANCE_SOURCE),
    }
