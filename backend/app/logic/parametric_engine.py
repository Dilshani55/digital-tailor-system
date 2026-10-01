"""
ParametricEngine — facade over the drafting pipeline (app/logic/drafting/).

    ValidatedMeasurements -> EaseProfile -> DraftingValues -> BaseBlock -> validate
                          -> (+ confirmed design_spec) -> FinalPattern -> validate

Prototype custom-pattern generation: the geometry is mathematically generated from the
measurements and documented drafting rules/assumptions (drafting/assumptions.py) and is
geometry-validated only. It is NOT professionally validated and no fit/sewing validation has
been performed. Units: cm everywhere.

Any failure (invalid measurements, unsupported design, contradictory garment length, invalid
geometry) raises DraftingError; the engine never returns a pattern that failed validation.
"""

import math

from app.logic.block_selection import select_drafting_block
from app.logic.drafting.base_block import draft_base_block
from app.logic.drafting.ease import DraftingError
from app.logic.drafting.transformations import apply_design

ENGINE_VERSION = "2.0"

DISCLAIMER = ("Prototype custom pattern: mathematically generated from the measurements and documented "
              "drafting rules; geometry validated only — not professionally or fit validated.")

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
    def __init__(self, measurements, features=None, design_spec=None):
        self.raw = dict(measurements)
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
        return self._dv().q_bust

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
            self.final = apply_design(self.base, self.attributes)
        except DraftingError:
            raise
        except (KeyError, TypeError, ValueError, ZeroDivisionError) as exc:
            raise DraftingError(f"Pattern drafting failed: {exc}", code="DRAFTING_FAILED")

        base, final = self.base, self.final
        dv, ease = base.dv, base.ease
        pieces = [p.to_dict() for p in final.pieces]
        return {
            "engine_version": ENGINE_VERSION,
            "disclaimer": DISCLAIMER,
            "garment_type": self.garment_type,
            "fabric_type": self.fabric_type,
            "drafting_block": self.block,
            "design_attributes": dict(final.attributes),
            "base_block": base.to_dict(),
            "final_pattern": final.to_dict(),
            "pattern_pieces": pieces,                       # == final_pattern pieces (cutting geometry)
            "validation": {"base_block": base.validation, "final_pattern": final.validation},
            "armhole_sleeve": final.validation.get("armhole_sleeve") or base.validation.get("armhole_sleeve"),
            "measurements_used": {
                "raw": {k: self.raw[k] for k in self.raw},
                "ease_profile": ease.to_dict(),
                "eased": {
                    "bust_cm": round(dv.garment_bust, 2), "waist_cm": round(dv.garment_waist, 2),
                    "hip_cm": round(dv.garment_hip, 2) if dv.garment_hip is not None else None,
                    "height_cm": self.raw.get("height_cm"),
                    "fit_preference": ease.fit_preference,
                },
                "derived": {
                    "back_waist_length_cm": self.raw["back_waist_length_cm"],
                    "armhole_depth_cm": round(dv.armhole_depth, 2),
                    "shoulder_width_cm": round(dv.shoulder_length, 2),
                    "across_back_half_cm": round(dv.across_back_half, 2),
                    "garment_length_cm": round(dv.garment_length, 2),
                    "waist_level_cm": round(dv.waist_y, 2),
                    "neck_half_width_cm": round(dv.neck_half_width, 2),
                },
            },
            "construction_notes": self._notes(final, ease, dv),
        }

    def _notes(self, final, ease, dv):
        notes = [
            DISCLAIMER,
            f"Drafting block: {self.block['block_label']} (garment={self.garment_type}, fabric={self.fabric_type}).",
            f"Ease used (project assumption): bust +{ease.bust_cm:g}, waist +{ease.waist_cm:g}, hip +{ease.hip_cm:g} cm "
            f"(fit: {ease.fit_preference}); sleeve bicep +{ease.bicep_cm:g}, wrist +{ease.wrist_cm:g} cm.",
            "Cutting lines include seam allowances (the dashed line is the sewing line); allowances per edge type are in each piece's data.",
        ]
        for t in final.transformations:
            note = t.get("note") or t.get("rule") or t.get("type")
            notes.append(f"Design transformation [{t['id']}] {t.get('design', '')}: {note} ({t['status']}).")
        for piece in final.pieces:
            for d in piece.darts:
                notes.append(f"{piece.name}: {d['type']} waist dart, intake {d['intake_cm']:.1f} cm.")
        if final.sleeve is not None:
            a = final.validation.get("armhole_sleeve", {})
            notes.append(f"Sleeve cap seam {a.get('sleeve_cap_seam_cm', 0):.1f} cm vs armhole seam "
                         f"{a.get('total_armhole_seam_cm', 0):.1f} cm (ease {a.get('cap_ease_cm', 0):.1f} cm).")
        return notes
