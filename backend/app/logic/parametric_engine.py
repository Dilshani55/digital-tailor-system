"""
ParametricEngine — facade over the drafting pipeline (app/logic/drafting/).

    ValidatedMeasurements -> EaseProfile -> DraftingValues -> BaseBlock -> validate
                          -> (+ confirmed design_spec) -> FinalPattern -> validate

Prototype custom-pattern generation: the geometry is mathematically generated from the customer's
measurements with ONE documented drafting method (drafting/assumptions.py, docs/pattern-drafting-method.md)
and is geometry-validated only. It is NOT professionally validated and no fit/sewing validation has been
performed. Units: cm everywhere (1 in = 2.54 cm for display).

Any failure (invalid measurements, unsupported design, contradictory garment length, invalid
geometry) raises DraftingError; the engine never returns a pattern that failed validation.
"""

import math

from app.logic.block_selection import select_drafting_block
from app.logic.drafting.assumptions import SOURCE, CONSTANTS
from app.logic.drafting.base_block import draft_base_block
from app.logic.drafting.ease import DraftingError
from app.logic.drafting.transformations import apply_design

ENGINE_VERSION = "3.0"

DISCLAIMER = ("Prototype custom pattern: generated from the measurements with a documented drafting method; the "
              "calculation passed geometric validation only. Confirm the fit with a test garment (toile) before "
              "cutting the final fabric.")

DRAFTING_METHOD = {
    "name": "Direct-measurement bodice and sleeve draft (quarter widths, front wider than back)",
    "source": SOURCE,
    "note": "Front and back are drafted separately; the sleeve cap is fitted to the two armhole seams. Rules the "
            "source does not cover (hip-length garments, knit T-shirts, the check against the upper arm) are marked "
            "'extension' in the calculation list. This is not Winifred Aldrich's block.",
}

_NECKLINE = {"collar": "collared-neck"}
_SLEEVE_LENGTH = {"elbow sleeve": "elbow-length", "three-quarter sleeve": "three-quarter-sleeve",
                  "cap sleeve": "cap-length"}


def attributes_from_features(features):
    """Legacy CAD feature dict (spaced labels) -> confirmed-attribute taxonomy. Used only when no design_spec."""
    neck = features.get("neckline", "round neck")
    length = features.get("sleeves", "short sleeve")
    style = features.get("sleeve_style", "none" if length == "sleeveless" else "regular sleeve")
    return {
        "garment_type": features.get("garment_type", "blouse"),
        "neckline_type": _NECKLINE.get(neck, neck.replace(" ", "-")),
        "sleeve_length": _SLEEVE_LENGTH.get(length, length.replace(" ", "-")),
        "sleeve_style": style.replace(" ", "-"),
    }


class ParametricEngine:
    def __init__(self, measurements, features=None, design_spec=None, seam_allowances=None):
        self.raw = dict(measurements)
        self.seam_allowances = seam_allowances
        self.features = features or {}
        self.attributes = dict((design_spec or {}).get("attributes") or attributes_from_features(self.features))
        self.design_spec = design_spec
        self.garment_type = self.attributes.get("garment_type", "blouse")
        self.fabric_type = self.raw.get("fabric_type", "woven")
        self.fit_preference = self.raw.get("fit_preference", "standard")
        self.block = select_drafting_block(self.garment_type, self.fabric_type)
        self.base = None
        self.final = None

    # ── convenient read-only views (after generate) ─────────────────────────
    @property
    def quarter_bust(self):
        return self._dv().garment_bust / 4.0

    @property
    def armhole_depth(self):
        return self._dv().armhole_depth

    @property
    def back_neck_to_waist(self):
        return self.raw["back_waist_length_cm"]

    def _dv(self):
        if self.base is None:
            self.base = draft_base_block(self.raw, self.block, self.fit_preference)
        return self.base.dv

    # ── main entry ──────────────────────────────────────────────────────────
    def generate(self):
        try:
            if self.base is None:
                self.base = draft_base_block(self.raw, self.block, self.fit_preference)
            self.final = apply_design(self.base, self.attributes, self.seam_allowances)
        except DraftingError:
            raise
        except (KeyError, TypeError, ValueError, ZeroDivisionError) as exc:
            raise DraftingError(f"Pattern drafting failed: {exc}", code="DRAFTING_FAILED")

        base, final = self.base, self.final
        dv, ease = base.dv, base.ease
        pieces = [p.to_dict() for p in final.pieces]
        arm = dict(final.validation.get("armhole_sleeve") or {})
        armhole_lengths = {
            "front_armhole_curve_cm": round(final.front.meta["armhole_length_cm"], 2),
            "back_armhole_curve_cm": round(final.back.meta["armhole_length_cm"], 2),
            "total_armhole_cm": round(final.front.meta["armhole_length_cm"] + final.back.meta["armhole_length_cm"], 2),
        }
        return {
            "engine_version": ENGINE_VERSION,
            "disclaimer": DISCLAIMER,
            "units": {"canonical": "cm", "cm_per_inch": 2.54},
            "drafting_method": DRAFTING_METHOD,
            "garment_type": self.garment_type,
            "fabric_type": self.fabric_type,
            "drafting_block": self.block,
            "design_attributes": dict(final.attributes),
            "base_block": base.to_dict(),
            "final_pattern": final.to_dict(),
            "pattern_pieces": pieces,                       # == final_pattern pieces (cutting geometry)
            "validation": {"base_block": base.validation, "final_pattern": final.validation},
            "armhole_sleeve": final.validation.get("armhole_sleeve") or base.validation.get("armhole_sleeve"),
            "armhole_lengths": armhole_lengths,
            "sleeve_cap": self._sleeve_cap_report(base, final, arm, armhole_lengths),
            "ease": ease.to_dict(),
            "why_this_size": self._trace(base, final),
            "seam_allowances_cm": next((t["allowances_cm"] for t in final.transformations if t["id"] == "seam_allowance"), {}),
            "measurements_used": {
                "raw": {k: self.raw[k] for k in self.raw},
                "ease_profile": ease.to_dict(),
                "eased": {
                    "bust_cm": round(dv.garment_bust, 2), "waist_cm": round(dv.garment_waist, 2),
                    "hip_cm": round(dv.garment_hip, 2) if dv.garment_hip is not None else None,
                    "fit_preference": ease.fit_preference,
                },
                "derived": {
                    "back_waist_length_cm": self.raw["back_waist_length_cm"],
                    "armhole_depth_cm": round(dv.armhole_depth, 2),
                    "neck_width_cm": round(2.0 * dv.neck_half_back, 2),
                    "front_neck_depth_cm": round(dv.front_neck_depth, 2),
                    "back_neck_depth_cm": round(dv.back_neck_depth, 2),
                    "shoulder_seam_cm": round(final.back.meta["shoulder_length_cm"], 2),
                    "bust_point_distance_cm": round(2.0 * dv.bust_point[0], 2) if dv.bust_point else None,
                    "garment_length_cm": round(dv.garment_length, 2),
                    "waist_level_cm": round(dv.waist_y, 2),
                },
            },
            "construction_notes": self._notes(final, ease, dv),
        }

    @staticmethod
    def _trace(base, final):
        """'Why this size?': every drafting value with its calculation and source, plus the seam allowances."""
        rows = [dict(r) for r in base.explanation]
        style = final.sleeve.meta.get("sleeve_style") if final.sleeve is not None else None
        if style in ("puff", "bell"):
            m = final.sleeve.meta
            rows.append({"id": "sleeve_style_width", "name": "sleeve_style_width", "piece": "sleeve", "source": "design",
                         "status": "design", "label": f"{style.capitalize()} sleeve width at its end",
                         "value_cm": round(m["width_hem_cm"], 3),
                         "formula": (f"plain sleeve {m['plain_width_bicep_cm']:.2f} x (1 + {m['spread_fraction']:g})"
                                     if style == "puff" else
                                     f"sleeve width {m['width_bicep_cm']:.2f} x (1 + {m['flare_fraction']:g})")})
        table = next((t["allowances_cm"] for t in final.transformations if t["id"] == "seam_allowance"), {})
        for kind, value in table.items():
            rows.append({"id": f"seam_allowance_{kind}", "name": f"seam_allowance_{kind}", "piece": "all", "source": "seam",
                         "status": "seam", "label": f"Seam allowance: {kind.replace('_', ' ')}", "value_cm": value,
                         "formula": "outside the sewing line; not part of the garment size"})
        return rows

    @staticmethod
    def _sleeve_cap_report(base, final, arm, armhole_lengths):
        """Bodice armhole against the sleeve cap, in the words of the validation report."""
        if final.sleeve is None:
            return {"has_sleeve": False, "status": "NOT APPLICABLE",
                    "bodice_armhole_seam_cm": armhole_lengths["total_armhole_cm"]}
        cap, total = arm["sleeve_cap_seam_cm"], arm["total_armhole_seam_cm"]
        gathered = bool(arm.get("gathered"))
        within = arm["allowed_cap_ease_min_cm"] - 1e-6 <= cap - total <= arm["allowed_cap_ease_max_cm"] + 1e-6
        changed = base.armhole.get("cap_fit") == "adjusted"
        h0, h = base.armhole.get("method_cap_height_cm"), base.armhole.get("cap_height_cm")
        review = (not within) or (changed and h0 and abs(h - h0) > 0.25 * h0)
        return {
            "has_sleeve": True,
            "bodice_armhole_seam_cm": round(total, 2),
            "front_armhole_curve_cm": armhole_lengths["front_armhole_curve_cm"],
            "back_armhole_curve_cm": armhole_lengths["back_armhole_curve_cm"],
            "sleeve_cap_seam_cm": round(cap, 2),
            "sleeve_cap_front_cm": round(arm["sleeve_cap_front_cm"], 2),
            "sleeve_cap_back_cm": round(arm["sleeve_cap_back_cm"], 2),
            "difference_cm": round(cap - total, 2),
            "allowed_cm": [arm["allowed_cap_ease_min_cm"], arm["allowed_cap_ease_max_cm"]],
            "difference_is": "gathering between the notches" if gathered else "sleeve-cap ease",
            "cap_height_cm": round(final.sleeve.meta["cap_height_cm"], 2),
            "method_cap_height_cm": round(h0, 2) if h0 else None,
            "cap_fit": base.armhole.get("cap_fit"),
            "status": "REVIEW" if review else "PASS",
            "note": ("The cap height was changed a lot from the method's value to fit this armhole: check upper arm, "
                     "shoulder to shoulder and bust, and test the sleeve in a toile." if review and within else
                     "Outside the accepted range." if review else
                     "The sleeve cap fits the armhole."),
        }

    def _notes(self, final, ease, dv):
        notes = [
            DISCLAIMER,
            f"Drafting method: {DRAFTING_METHOD['name']} - {SOURCE['title']}.",
            f"Drafting block: {self.block['block_label']} (garment={self.garment_type}, fabric={self.fabric_type}).",
            f"Ease ({ease.fit_label}): bust +{ease.bust_cm:g}, waist +{ease.waist_cm:g}, hip +{ease.hip_cm:g} cm; "
            f"sleeve at least +{ease.upper_arm_cm:g} cm over the upper arm, +{ease.sleeve_end_cm:g} cm at the sleeve end.",
            "Cutting lines include seam allowances (the dashed line is the sewing line); seam allowance is not ease.",
        ]
        for t in final.transformations:
            note = t.get("note") or t.get("rule") or t.get("type")
            notes.append(f"Design transformation [{t['id']}] {t.get('design', '')}: {note} ({t['status']}).")
        for piece in final.pieces:
            for d in piece.darts:
                kind = "side-seam bust dart" if d["type"] == "side" else f"{d['type']} waist dart"
                notes.append(f"{piece.name}: {kind}, intake {d['intake_cm']:.1f} cm.")
        if final.sleeve is not None:
            a = final.validation.get("armhole_sleeve", {})
            notes.append(f"Sleeve cap seam {a.get('sleeve_cap_seam_cm', 0):.1f} cm vs armhole seam "
                         f"{a.get('total_armhole_seam_cm', 0):.1f} cm (difference {a.get('cap_ease_cm', 0):.1f} cm).")
        return notes


__all__ = ["ParametricEngine", "attributes_from_features", "DraftingError", "DISCLAIMER", "DRAFTING_METHOD",
           "ENGINE_VERSION", "CONSTANTS", "math"]
