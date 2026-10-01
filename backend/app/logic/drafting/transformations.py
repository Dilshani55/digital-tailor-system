"""
DESIGN TRANSFORMATION stage:   BaseBlock + confirmed design attributes -> FinalPattern.

Only the USER-CONFIRMED design specification (hyphenated taxonomy attributes) is used here — never
raw classifier output. The base block is not modified; transformed pieces are rebuilt from the
same drafting values with the design parameters, and every change is recorded.

Supported transformations (see feature_schema.py for the support table):
  neckline      round-neck, square-neck, v-neck  (sweetheart/scoop/boat/high-neck are drafted as
                the base round neck and recorded as "not applied"; others rejected)
  garment length blouse / t-shirt hem rule against the measured garment length
  sleeve length sleeveless (armhole facings), short, elbow, three-quarter, long
  sleeve style  none / regular-sleeve (plain set-in). Other styles are rejected.
"""

from app.logic import feature_schema as fs
from app.logic.drafting import bodice, sleeve as sleeve_mod, geometry as g, seam_allowance as sa
from app.logic.drafting.assumptions import A
from app.logic.drafting.ease import DraftingError
from app.logic.drafting.pieces import Piece
from app.logic.drafting.validation import validate_final_pattern

ROUND_FALLBACK_NECKLINES = ("scoop-neck", "boat-neck", "sweetheart-neck", "high-neck")

LENGTH_LABEL = {"short-sleeve": "short", "elbow-length": "elbow", "three-quarter-sleeve": "three-quarter",
                "long-sleeve": "long"}


class FinalPattern:
    def __init__(self, base, attributes, front, back, sleeve, extras, transformations):
        self.base, self.attributes = base, attributes
        self.front, self.back, self.sleeve, self.extras = front, back, sleeve, extras
        self.transformations = transformations
        self.dv = base.dv

    @property
    def pieces(self):
        return [self.front, self.back] + ([self.sleeve] if self.sleeve else []) + list(self.extras)

    def to_dict(self):
        return {
            "stage": "final_pattern",
            "description": "Base block transformed by the confirmed design specification. "
                           "Prototype, mathematically generated, geometry-validated; cutting lines include seam allowances.",
            "design_attributes": dict(self.attributes),
            "transformations": self.transformations,
            "pieces": [p.to_dict() for p in self.pieces],
        }


def _conflict(field, message):
    return DraftingError(message, code="DESIGN_MEASUREMENT_CONFLICT",
                         field_errors={field: [{"code": "DESIGN_CONFLICT", "message": message}]})


def resolve_hem(dv, garment_type):
    """
    Garment-length rule (project rule, documented):
      hem level y = measured garment_length_cm, measured down from the neck/shoulder-point level;
      a blouse or T-shirt hem must reach the waist line.
    A measurement that contradicts this is reported, never silently changed.
    """
    hem = dv.garment_length
    if hem < dv.waist_y:
        raise _conflict("garment_length_cm",
                        f"Garment length {hem:g} cm is shorter than the waist line ({dv.waist_y:.1f} cm). "
                        f"Enter a length of at least {dv.waist_y:.1f} cm: a blouse or T-shirt hem must reach the waist.")
    return hem


def _neck_params(attr, dv):
    if attr == "round-neck":
        return {"shape": "round"}, "round", "Round neckline (base neck)."
    if attr == "square-neck":
        return {"shape": "square", "depth": dv.front_neck_depth}, "square", \
            "Square neckline: base neck width and depth, straight edges."
    if attr == "v-neck":
        depth = dv.front_neck_depth + A["v_neck_extra_depth_cm"]
        return {"shape": "v", "depth": depth}, "v", f"V neckline to a centre-front point {depth:.1f} cm deep."
    if attr in ROUND_FALLBACK_NECKLINES:
        return {"shape": "round"}, "round", f"'{attr}' style is NOT applied; drafted as the base round neck."
    raise DraftingError(f"Neckline '{attr}' cannot be drafted.", code="UNSUPPORTED_DESIGN")


def _strip(name, ptype, length, width, count, meta):
    segs = [g.Line("top", (0, 0), (length, 0)), g.Line("right", (length, 0), (length, width)),
            g.Line("bottom", (length, width), (0, width)), g.Line("left", (0, width), (0, 0))]
    pts = {"TOP_LEFT": (0, 0), "TOP_RIGHT": (length, 0), "BOTTOM_RIGHT": (length, width), "BOTTOM_LEFT": (0, width)}
    return Piece(name, ptype, segs, pts, cut_count=count, cut_on_fold=False,
                 grain=((length / 2.0, 0), (length / 2.0, width)), meta=meta, seam_allowance_cm=0.7)


def apply_design(base, attributes):
    """Apply confirmed design attributes to a valid base block. Raises DraftingError on any problem."""
    clean, errors = fs.validate_attributes(attributes, scope="model")
    if errors:
        first = next(iter(errors.values()))
        raise DraftingError(first["message"], code="INVALID_DESIGN_ATTRIBUTES",
                            field_errors={k: [v] for k, v in errors.items()})
    # The same scope the API and the UI use: a combination outside it is refused here too, so the engine can
    # never draft "something similar" (for example a plain sleeve for a sleeve style of "none").
    report = fs.support_report(clean, with_scope=True)
    if not report["supported"]:
        raise DraftingError(fs.unsupported_message(report), code="UNSUPPORTED_DESIGN",
                            unsupported_features=report["unsupported"])

    dv, block = base.dv, base.block
    allow_darts = bool(block.get("allow_darts"))
    transformations = []

    # 1. garment length
    hem_y = resolve_hem(dv, clean["garment_type"])
    transformations.append({
        "id": "garment_length", "type": "hem_level", "design": clean["garment_type"],
        "measured_garment_length_cm": dv.garment_length, "waist_level_cm": round(dv.waist_y, 3),
        "hem_level_cm": round(hem_y, 3),
        "rule": "hem = measured garment length from the neck/shoulder-point level; "
                "regular hem >= waist (project rule)",
        "status": "applied"})

    # 2. neckline (front only; back neck stays the base back neck)
    neck, shape, note = _neck_params(clean["neckline_type"], dv)
    applied = clean["neckline_type"] not in ROUND_FALLBACK_NECKLINES
    transformations.append({
        "id": "neckline", "type": f"{shape}_neckline", "design": clean["neckline_type"], "note": note,
        "front_neck_depth_cm": round(neck.get("depth", dv.front_neck_depth), 3),
        "status": "applied" if applied else "not_applied_fallback_round"})

    front = bodice.build_bodice(dv, "front", neck=neck, hem_y=hem_y, block_allows_darts=allow_darts)
    back = bodice.build_bodice(dv, "back", hem_y=hem_y, block_allows_darts=allow_darts)
    front.transformations = [t["id"] for t in transformations]
    back.transformations = ["garment_length"]

    # 3. sleeve
    sleeve_piece, extras = None, []
    length_attr, style_attr = clean["sleeve_length"], clean["sleeve_style"]
    if length_attr == "sleeveless":
        facing_len = base.armhole["total_armhole_seam_cm"]
        extras.append(_strip("Armhole Facing", "armhole_facing", facing_len, A["facing_width_cm"], 2,
                             {"length_cm": facing_len, "width_cm": A["facing_width_cm"]}))
        transformations.append({
            "id": "sleeve_length", "type": "sleeveless", "design": length_attr, "status": "applied",
            "note": "No sleeve piece; armhole facing strips (length = front + back armhole seam, "
                    "drafted straight — shaped facing not implemented)."})
        transformations.append({"id": "sleeve_style", "type": "none", "design": style_attr, "status": "applied"})
    else:
        if dv.sleeve_length is None or dv.bicep_width is None or base.sleeve is None:
            raise DraftingError("This design has sleeves, so the bicep and sleeve length measurements are needed.",
                                code="MEASUREMENTS_INCOMPLETE",
                                field_errors={k: [{"code": "REQUIRED", "message": "Required for this design."}]
                                              for k in ("bicep_cm", "sleeve_cm")
                                              if (dv.bicep_width if k == "bicep_cm" else dv.sleeve_length) is None})
        sleeve_hem = dv.sleeve_length                 # the measured, wanted sleeve length (no fraction)
        cap_h = base.armhole["cap_height_cm"]
        label = LENGTH_LABEL[length_attr]
        if style_attr == "puff-sleeve":
            gathered_hem = length_attr != "long-sleeve"
            sleeve_piece = sleeve_mod.build_puff_sleeve(
                dv, cap_h, sleeve_hem, spread=A["puff_spread_fraction"], rise=A["puff_crown_rise_cm"],
                gathered_hem=gathered_hem, name=f"Puff Sleeve ({label})", sleeve_kind=label)
            style_record = {
                "id": "sleeve_style", "type": "puff_slash_and_spread", "design": style_attr, "status": "applied",
                "spread_fraction": A["puff_spread_fraction"], "crown_rise_cm": A["puff_crown_rise_cm"],
                "gathered_hem": gathered_hem,
                "note": "Plain solved sleeve widened and crown raised; the extra cap length is gathered between "
                        "the front and back notches" + ("; the hem is gathered into a sleeve band." if gathered_hem
                                                        else "; the lower sleeve tapers to the wrist.")}
            if gathered_hem:
                band_len = dv.bicep_width
                extras.append(_strip("Sleeve Band", "sleeve_band", band_len, 2.0 * A["puff_band_height_cm"], 2,
                                     {"length_cm": band_len, "finished_height_cm": A["puff_band_height_cm"],
                                      "rule": "length = eased bicep width; cut double and folded"}))
        elif style_attr == "bell-sleeve":
            flare = A["bell_flare_fraction"][length_attr]
            sleeve_piece = sleeve_mod.build_bell_sleeve(dv, cap_h, sleeve_hem, flare=flare,
                                                        name=f"Bell Sleeve ({label})", sleeve_kind=label)
            style_record = {
                "id": "sleeve_style", "type": "bell_flare", "design": style_attr, "status": "applied",
                "flare_fraction": flare, "hem_width_cm": round(sleeve_piece.meta["width_hem_cm"], 3),
                "note": "Fitted solved cap; flares from the underarm to a curved hem meeting both seams at 90 degrees."}
        else:
            sleeve_piece = sleeve_mod.build_sleeve(dv, cap_h, sleeve_hem, name=f"Sleeve ({label})", sleeve_kind=label,
                                                   taper_to_wrist=length_attr == "long-sleeve")
            style_record = {
                "id": "sleeve_style", "type": "plain_set_in", "design": style_attr, "status": "applied",
                "note": "Plain set-in sleeve; cap solved from the bodice armhole seam lengths."}
        sleeve_piece.transformations = ["sleeve_length", "sleeve_style"]
        transformations.append({
            "id": "sleeve_length", "type": f"{label}_sleeve", "design": length_attr,
            "sleeve_length_cm": round(sleeve_hem, 3),
            "rule": "sleeve length = the measured sleeve_cm (shoulder tip to where the sleeve should end); "
                    "long sleeves taper to the wrist, short sleeves stay at the bicep width",
            "status": "applied"})
        transformations.append(style_record)

    # 4. accessory pieces required by the block
    if block.get("add_neckband"):
        neck_len = 2.0 * (front.meta["neckline_length_cm"] + back.meta["neckline_length_cm"])
        band_len = A["neckband_stretch_factor"] * neck_len
        extras.append(_strip("Neckband", "neckband", band_len, A["neckband_height_cm"], 1,
                             {"length_cm": band_len, "neckline_seam_cm": neck_len}))
        transformations.append({"id": "neckband", "type": "knit_neckband", "length_cm": round(band_len, 3),
                                "rule": "0.85 x full neckline seam length (project assumption)", "status": "applied"})

    final = FinalPattern(base, clean, front, back, sleeve_piece, extras, transformations)

    # 5. seam allowance: real cutting-line geometry + balance marks on every piece
    block_id = block["block_id"]
    for piece in final.pieces:
        sa.apply_seam_allowance(piece, block_id)
    front.notches = sa.bodice_notches(front)
    back.notches = sa.bodice_notches(back)
    if sleeve_piece is not None:
        sleeve_piece.notches = sa.sleeve_notches(
            sleeve_piece, front.meta["armhole_length_cm"], back.meta["armhole_length_cm"])
    transformations.append({
        "id": "seam_allowance", "type": "offset_cutting_line", "status": "applied",
        "allowances_cm": sa.allowance_table(block_id),
        "rule": "cutting line = seam line offset per edge (fold edge 0); project sewing-practice values"})
    result = validate_final_pattern(final)
    final.validation = result
    if not result["passed"]:
        raise DraftingError("Final pattern failed geometry validation: " + "; ".join(result["errors"]),
                            code="FINAL_PATTERN_INVALID", validation=result)
    return final
