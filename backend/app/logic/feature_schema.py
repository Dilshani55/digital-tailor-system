"""
Canonical DESIGN FEATURE SCHEMA — the single backend source of truth for the
garment attributes that flow  image -> classifier -> user confirmation -> pattern engine.

What the deployed model actually predicts (verified against the checkpoint,
`ai_training/config/classes.json` and app/ai/multitask_classifier.py):
four independent classification heads of an image-level classifier
(YOLOv8n-cls-derived backbone; NOT an object detector):

    garment_type   3 classes    neckline_type 10 classes
    sleeve_length  6 classes    sleeve_style   9 classes        (28 labels total)

Feature provenance (kept explicit in `design_spec["provenance"]`):
    ml_prediction_confirmed  user accepted the classifier's top-1 label unchanged
    user_corrected           user changed the classifier's label
    manual_selection         no classifier output existed; user selected the value
    rule_based               darts / seams: derived from garment_type by fixed rules
                             (NOT predicted by any model)

SUPPORT LEVELS describe what the CURRENT drafting engine really does with a value.
They are deliberately conservative and are the only place to update when the
engine gains real geometry for a feature (Phase 4):

    implemented   engine geometry reflects the value
    approximated  accepted, but only part of the design is reflected (see note)
    unsupported   engine cannot represent it; pattern generation is REJECTED,
                  never silently replaced by a different design
"""

from datetime import datetime, timezone

SCHEMA_VERSION = 1

HEADS = ("garment_type", "neckline_type", "sleeve_length", "sleeve_style")

IMPLEMENTED = "implemented"
APPROXIMATED = "approximated"
UNSUPPORTED = "unsupported"

# value -> (support level, note). Order == classifier class order (classes.json).
_FEATURES = {
    "garment_type": {
        "blouse": (IMPLEMENTED, "Woven bodice block with bust/waist darts."),
        "t-shirt": (IMPLEMENTED, "Knit bodice block, no darts, neckband piece."),
        "crop-top": (APPROXIMATED, "Crop block selected, but the hem length still comes from the measured garment_length_cm."),
    },
    "neckline_type": {
        "round-neck": (IMPLEMENTED, ""),
        "v-neck": (APPROXIMATED, "Front neck is deepened, but the curve is not yet a true V shape."),
        "square-neck": (IMPLEMENTED, ""),
        "scoop-neck": (APPROXIMATED, "Currently drafted as a round neck (scoop depth not yet applied)."),
        "boat-neck": (APPROXIMATED, "Only the front neck depth is adjusted; no wide boat shape yet."),
        "sweetheart-neck": (APPROXIMATED, "Simplified sweetheart curve."),
        "halter-neck": (UNSUPPORTED, "Halter/strap construction is not implemented."),
        "high-neck": (APPROXIMATED, "Shallow neck only; no collar-stand piece is generated."),
        "collared-neck": (UNSUPPORTED, "No collar piece is generated."),
        "off-shoulder": (UNSUPPORTED, "Off-shoulder construction is not implemented."),
    },
    "sleeve_length": {
        "sleeveless": (IMPLEMENTED, "Armhole facing pieces are generated."),
        "cap-length": (APPROXIMATED, "Length is taken from the measured sleeve_cm, not from the design."),
        "short-sleeve": (APPROXIMATED, "Length is taken from the measured sleeve_cm, not from the design."),
        "elbow-length": (APPROXIMATED, "Length is taken from the measured sleeve_cm, not from the design."),
        "three-quarter-sleeve": (APPROXIMATED, "Length is taken from the measured sleeve_cm, not from the design."),
        "long-sleeve": (APPROXIMATED, "Length is taken from the measured sleeve_cm, not from the design."),
    },
    "sleeve_style": {
        "none": (IMPLEMENTED, "Plain set-in sleeve (or none if sleeveless)."),
        "regular-sleeve": (IMPLEMENTED, "Plain set-in sleeve."),
        "puff-sleeve": (UNSUPPORTED, "Style geometry is not connected to the confirmed-design flow yet."),
        "bell-sleeve": (UNSUPPORTED, "Style geometry is not connected to the confirmed-design flow yet."),
        "bishop-sleeve": (UNSUPPORTED, "Style geometry is not connected to the confirmed-design flow yet."),
        "flutter-sleeve": (UNSUPPORTED, "Style geometry is not connected to the confirmed-design flow yet."),
        "raglan-sleeve": (UNSUPPORTED, "Raglan construction is not implemented."),
        "dolman-sleeve": (UNSUPPORTED, "Style geometry is not connected to the confirmed-design flow yet."),
        "kimono-sleeve": (UNSUPPORTED, "Style geometry is not connected to the confirmed-design flow yet."),
    },
}

TAXONOMY = {head: tuple(values) for head, values in _FEATURES.items()}


def support_of(head, value):
    """(level, note) for a taxonomy value, or None if the value is not in the taxonomy."""
    return _FEATURES.get(head, {}).get(value)


def schema_payload():
    """JSON-serialisable schema for API clients."""
    return {
        "schema_version": SCHEMA_VERSION,
        "model_type": "image-level multi-task classifier (4 heads); not an object detector",
        "heads": {
            head: [
                {"value": v, "support": lvl, "note": note}
                for v, (lvl, note) in _FEATURES[head].items()
            ]
            for head in HEADS
        },
        "rule_based_features": {
            "darts": "derived from garment_type (blouse: bust dart; others: none)",
            "seams": "side seam",
        },
    }


def validate_attributes(attrs):
    """
    Validate a full set of confirmed attributes against the taxonomy.

    Returns (clean, errors). `clean` holds the 4 stripped values only when there
    are no errors; `errors` maps head -> {"code", "message"}.
    """
    attrs = attrs if isinstance(attrs, dict) else {}
    clean, errors = {}, {}
    for head in HEADS:
        raw = attrs.get(head)
        if not raw or not isinstance(raw, str):
            errors[head] = {"code": "REQUIRED", "message": f"Missing or invalid attribute '{head}'"}
            continue
        val = raw.strip()
        if val not in TAXONOMY[head]:
            errors[head] = {
                "code": "NOT_IN_TAXONOMY",
                "message": (
                    f"Invalid attribute value '{val}' for '{head}'. "
                    f"Must be one of the active taxonomy values: {', '.join(TAXONOMY[head])}."
                ),
            }
            continue
        clean[head] = val
    if errors:
        return {}, errors

    # Relationships that are contradictory by definition.
    if clean["sleeve_length"] == "sleeveless" and clean["sleeve_style"] != "none":
        errors["sleeve_style"] = {
            "code": "INCONSISTENT",
            "message": (
                f"A sleeveless garment cannot have sleeve style '{clean['sleeve_style']}'. "
                "Choose sleeve style 'none' or change the sleeve length."
            ),
        }
        return {}, errors
    return clean, {}


def support_report(clean):
    """Summarise how well the engine supports a validated attribute set."""
    unsupported, approximated = [], []
    for head in HEADS:
        level, note = support_of(head, clean[head])
        item = {"head": head, "value": clean[head], "note": note}
        if level == UNSUPPORTED:
            unsupported.append(item)
        elif level == APPROXIMATED:
            approximated.append(item)
    return {
        "supported": not unsupported,
        "unsupported": unsupported,
        "approximated": approximated,
    }


def unsupported_message(report):
    items = "; ".join(f"{u['head']}={u['value']} ({u['note']})" for u in report["unsupported"])
    return (
        f"This design cannot be drafted yet: {items} "
        "Correct the feature to a supported value; the system will not substitute a different design."
    )


def build_provenance(clean, garment_attributes):
    """Per-head provenance: model prediction + confidence vs. what the user confirmed."""
    preds = ((garment_attributes or {}).get("predictions")) or {}
    prov = {}
    for head in HEADS:
        p = preds.get(head) or {}
        label = p.get("label")
        if not label:
            prov[head] = {"source": "manual_selection"}
            continue
        prov[head] = {
            "source": "ml_prediction_confirmed" if label == clean[head] else "user_corrected",
            "predicted_label": label,
            "predicted_confidence": p.get("confidence"),
            "top_3": p.get("top_3"),
            "requires_user_confirmation": p.get("requires_user_confirmation"),
        }
    return prov


def build_design_spec(clean, garment_attributes, rule_based):
    """
    The canonical design specification: the USER-CONFIRMED attributes, their
    provenance, the rule-based derived features, model/checkpoint metadata and
    engine-support report. This — not the raw model output — drives the pattern engine.
    """
    ga = garment_attributes or {}
    model = None
    if ga.get("model_version") or ga.get("checkpoint_sha256"):
        model = {
            "model_version": ga.get("model_version"),
            "model_type": ga.get("model_type"),
            "checkpoint_sha256": ga.get("checkpoint_sha256"),
        }
    return {
        "schema_version": SCHEMA_VERSION,
        "attributes": dict(clean),
        "provenance": build_provenance(clean, ga),
        "rule_based_features": {
            "darts": rule_based.get("darts"),
            "seams": rule_based.get("seams"),
            "derived_from": "garment_type",
        },
        "model": model,
        "support": support_report(clean),
        "confirmed_at": datetime.now(timezone.utc).isoformat(),
    }
