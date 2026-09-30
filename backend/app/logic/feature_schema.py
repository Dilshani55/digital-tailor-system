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

import json
import os
from datetime import datetime, timezone

# The user-selectable taxonomy, its support levels and the draftable combinations live in ONE file shared
# with the frontend: <repo>/config/garment_scope.json (override with GARMENT_SCOPE_FILE).
SCOPE_FILE = os.environ.get("GARMENT_SCOPE_FILE") or os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "config", "garment_scope.json"))
with open(SCOPE_FILE, encoding="utf-8") as _f:
    _CANON = json.load(_f)

SCHEMA_VERSION = _CANON["schema_version"]

HEADS = tuple(_CANON["heads"])

IMPLEMENTED = "implemented"
APPROXIMATED = "approximated"
UNSUPPORTED = "unsupported"

# Classes the deployed M13 checkpoint can predict but the user can NOT select (never remapped).
# (level, note) describe what the engine internals would do; the API rejects them as OUTSIDE_SCOPE.
_MODEL_ONLY = {
    "neckline_type": {
        "scoop-neck": (APPROXIMATED, "Drafted as the base round neck; scoop depth is NOT applied."),
        "boat-neck": (APPROXIMATED, "Drafted as the base round neck; boat shape is NOT applied."),
        "sweetheart-neck": (APPROXIMATED, "Drafted as the base round neck; sweetheart shape is NOT applied."),
        "halter-neck": (UNSUPPORTED, "Halter/strap construction is not implemented."),
        "high-neck": (APPROXIMATED, "Drafted as the base round neck; no stand/collar piece is generated."),
    },
    "sleeve_length": {
        "cap-length": (UNSUPPORTED, "A cap-length sleeve is shorter than the sleeve cap; not implemented."),
        "elbow-length": (IMPLEMENTED, "58% of the measured full-arm length (project assumption)."),
        "three-quarter-sleeve": (IMPLEMENTED, "75% of the measured full-arm length (project assumption)."),
    },
    "sleeve_style": {
        "bishop-sleeve": (UNSUPPORTED, "No geometry for this sleeve style has been implemented."),
        "flutter-sleeve": (UNSUPPORTED, "No geometry for this sleeve style has been implemented."),
        "raglan-sleeve": (UNSUPPORTED, "Raglan construction is not implemented."),
        "dolman-sleeve": (UNSUPPORTED, "No geometry for this sleeve style has been implemented."),
        "kimono-sleeve": (UNSUPPORTED, "No geometry for this sleeve style has been implemented."),
    },
}

# Class order of the deployed checkpoint (ai_training/config/classes.json; checked by tests).
_MODEL_ORDER = {
    "garment_type": ("blouse", "t-shirt", "crop-top"),
    "neckline_type": ("round-neck", "v-neck", "square-neck", "scoop-neck", "boat-neck", "sweetheart-neck",
                      "halter-neck", "high-neck", "collared-neck", "off-shoulder"),
    "sleeve_length": ("sleeveless", "cap-length", "short-sleeve", "elbow-length", "three-quarter-sleeve",
                      "long-sleeve"),
    "sleeve_style": ("none", "regular-sleeve", "puff-sleeve", "bell-sleeve", "bishop-sleeve", "flutter-sleeve",
                     "raglan-sleeve", "dolman-sleeve", "kimono-sleeve"),
}

_ACTIVE = {h: {o["value"]: (o["support"], o["note"]) for o in _CANON["taxonomy"][h]} for h in HEADS}
LABELS = {h: {o["value"]: o["label"] for o in _CANON["taxonomy"][h]} for h in HEADS}

# value -> (support level, note), in the classifier's class order.
_FEATURES = {h: {v: (_ACTIVE[h].get(v) or _MODEL_ONLY[h][v]) for v in _MODEL_ORDER[h]} for h in HEADS}

# PROJECT SCOPE: garment -> allowed necklines and {sleeve_length: [allowed sleeve styles]}.
SCOPE = {g: {"neckline_type": tuple(d["neckline_type"]),
             "sleeve_length": tuple(d["sleeves"]),
             "sleeves": {length: tuple(styles) for length, styles in d["sleeves"].items()}}
         for g, d in _CANON["scope"].items()}
SCOPE_GARMENT_LABEL = {g: d["label"] for g, d in _CANON["scope"].items()}


def _pretty(values):
    return ", ".join(v.replace("-neck", "").replace("-sleeve", "").replace("-", " ") for v in values)


def scope_violations(clean):
    """Items outside the draftable garment x neckline x sleeve length x sleeve style combinations."""
    out = []
    allowed = SCOPE.get(clean.get("garment_type"))
    if not allowed:
        return out
    g = SCOPE_GARMENT_LABEL[clean["garment_type"]]
    for head in ("neckline_type", "sleeve_length"):
        if clean[head] not in allowed[head]:
            what = "necklines" if head == "neckline_type" else "sleeve lengths"
            out.append({"head": head, "value": clean[head],
                        "note": f"Outside the supported scope: {g} supports {_pretty(allowed[head])} {what} only."})
    styles = allowed["sleeves"].get(clean["sleeve_length"])
    if styles is not None and clean["sleeve_style"] not in styles:
        out.append({"head": "sleeve_style", "value": clean["sleeve_style"],
                    "note": f"Outside the supported scope: {g} with {clean['sleeve_length']} supports "
                            f"{', '.join(repr(s) for s in styles)} sleeve style only."})
    return out


def is_draftable(clean):
    """True if the confirmed design can actually be drafted (supported values inside the scope)."""
    return support_report(clean, with_scope=True)["supported"]


# The deployed M13 classifier keeps its ORIGINAL output taxonomy (3 / 10 / 6 / 9 classes, order fixed by
# the checkpoint and ai_training/config/classes.json). It is never changed or remapped.
MODEL_TAXONOMY = {head: tuple(values) for head, values in _FEATURES.items()}

# What the USER may choose and confirm (active production taxonomy, 3 / 5 / 3 / 4 = 15 classes).
# Values the model can predict but that are not listed here are NOT remapped to a similar class:
# the prediction is kept as evidence and the user must confirm the design manually.
UI_TAXONOMY = {h: tuple(o["value"] for o in _CANON["taxonomy"][h]) for h in HEADS}
TAXONOMY = UI_TAXONOMY          # the API / frontend contract

OUTSIDE_SCOPE_MESSAGE = _CANON["outside_scope_message"]
LOW_CONFIDENCE_MESSAGE = _CANON["low_confidence_message"]


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
                for v, (lvl, note) in _FEATURES[head].items() if v in UI_TAXONOMY[head]
            ]
            for head in HEADS
        },
        "active_class_count": sum(len(v) for v in UI_TAXONOMY.values()),
        "model_class_counts": {h: len(v) for h, v in MODEL_TAXONOMY.items()},
        "outside_scope_message": OUTSIDE_SCOPE_MESSAGE,
        "scope": {g: {"neckline_type": list(d["neckline_type"]), "sleeve_length": list(d["sleeve_length"]),
                      "sleeves": {k: list(v) for k, v in d["sleeves"].items()}} for g, d in SCOPE.items()},
        "labels": LABELS,
        "low_confidence_message": LOW_CONFIDENCE_MESSAGE,
        "rule_based_features": {
            "darts": "derived from garment_type (blouse: bust dart; others: none)",
            "seams": "side seam",
        },
    }


def annotate_predictions(garment_attributes):
    """
    Adds scope information to the classifier output WITHOUT changing any prediction.
    Every head keeps its genuine label / confidence / top_3 (research evidence). Additionally:
      predictions[head]["supported_in_ui"]  True if the predicted label is a selectable class
      predictions[head]["suggested_label"]  the label if selectable, else None (never a substitute)
      unsupported_heads / unsupported_message  set when any head predicted a class outside the UI taxonomy
    """
    ga = dict(garment_attributes or {})
    preds = {h: dict(p) for h, p in ((ga.get("predictions")) or {}).items()}
    unsupported = []
    for head in HEADS:
        p = preds.get(head)
        if not p:
            continue
        ok = p.get("label") in UI_TAXONOMY[head]
        p["supported_in_ui"] = ok
        p["suggested_label"] = p.get("label") if ok else None
        if not ok:
            unsupported.append(head)
    ga["predictions"] = preds
    ga["unsupported_heads"] = unsupported
    ga["unsupported_message"] = OUTSIDE_SCOPE_MESSAGE if unsupported else None
    if unsupported:
        ga["requires_user_confirmation"] = True
    return ga


def validate_attributes(attrs, scope="ui"):
    """
    Validate a full set of confirmed attributes against the taxonomy.

    scope="ui"    (API, default): only the 15 active user-selectable classes are accepted.
    scope="model" (drafting engine internals): the full classifier taxonomy.

    Returns (clean, errors). `clean` holds the 4 stripped values only when there
    are no errors; `errors` maps head -> {"code", "message"}.
    """
    attrs = attrs if isinstance(attrs, dict) else {}
    allowed = MODEL_TAXONOMY if scope == "model" else UI_TAXONOMY
    clean, errors = {}, {}
    for head in HEADS:
        raw = attrs.get(head)
        if not raw or not isinstance(raw, str):
            errors[head] = {"code": "REQUIRED", "message": f"Missing or invalid attribute '{head}'"}
            continue
        val = raw.strip()
        if val not in allowed[head] and val in MODEL_TAXONOMY[head]:
            errors[head] = {"code": "OUTSIDE_SCOPE",
                            "message": f"'{val}' is outside the supported pattern scope. Please choose one of: "
                                       f"{', '.join(allowed[head])}."}
            continue
        if val not in allowed[head]:
            errors[head] = {
                "code": "NOT_IN_TAXONOMY",
                "message": (
                    f"Invalid attribute value '{val}' for '{head}'. "
                    f"Must be one of the active taxonomy values: {', '.join(allowed[head])}."
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


def support_report(clean, with_scope=False):
    """Summarise how well the engine supports a validated attribute set.

    with_scope=True additionally rejects anything outside the PROJECT scope (SCOPE); the API uses it.
    The drafting engine itself stays a superset (e.g. it can still draft elbow-length sleeves)."""
    unsupported, approximated = [], []
    for head in HEADS:
        level, note = support_of(head, clean[head])
        item = {"head": head, "value": clean[head], "note": note}
        if level == UNSUPPORTED:
            unsupported.append(item)
        elif level == APPROXIMATED:
            approximated.append(item)
    seen = {(u["head"], u["value"]) for u in unsupported}
    for item in (scope_violations(clean) if with_scope else []):
        if (item["head"], item["value"]) not in seen:
            unsupported.append(item)
    approximated = [a for a in approximated if (a["head"], a["value"]) not in {(u["head"], u["value"]) for u in unsupported}]
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
        "support": support_report(clean, with_scope=True),
        "confirmed_at": datetime.now(timezone.utc).isoformat(),
    }
