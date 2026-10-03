"""
Canonical DESIGN FEATURE SCHEMA - the single backend source of truth for the garment attributes that flow
image -> AI suggestion -> user confirmation -> pattern engine.

The values a user can select, their support level and the draftable combinations all come from one file shared
with the frontend: backend/config/garment_scope.json. The four AI models (app/ai/garment_models.py) suggest values
from the same lists; a value outside them is rejected, never replaced by a similar one.

Feature provenance (kept explicit in `design_spec["provenance"]`):
    ml_prediction_confirmed  user accepted the model's suggestion unchanged
    user_corrected           user changed the model's suggestion
    manual_selection         no model output existed; user selected the value
    rule_based               darts / seams: derived from garment_type by fixed rules (NOT predicted by any model)

SUPPORT LEVELS describe what the drafting engine really does with a value:
    implemented   engine geometry reflects the value
    approximated  accepted, but only part of the design is reflected (see note)
    unsupported   engine cannot represent it; pattern generation is REJECTED,
                  never silently replaced by a different design
"""

import json
import os
from datetime import datetime, timezone

# The user-selectable taxonomy, its support levels and the draftable combinations live in ONE file shared
# with the frontend: backend/config/garment_scope.json (override with GARMENT_SCOPE_FILE).
SCOPE_FILE = os.environ.get("GARMENT_SCOPE_FILE") or os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "config", "garment_scope.json"))
with open(SCOPE_FILE, encoding="utf-8") as _f:
    _CANON = json.load(_f)

SCHEMA_VERSION = _CANON["schema_version"]

HEADS = tuple(_CANON["heads"])

IMPLEMENTED = "implemented"
APPROXIMATED = "approximated"
UNSUPPORTED = "unsupported"

# value -> (support level, note), in the order of the shared file.
_FEATURES = {h: {o["value"]: (o["support"], o["note"]) for o in _CANON["taxonomy"][h]} for h in HEADS}
LABELS = {h: {o["value"]: o["label"] for o in _CANON["taxonomy"][h]} for h in HEADS}

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


# What the user may choose and confirm, and what the AI models may suggest: one taxonomy.
UI_TAXONOMY = {h: tuple(o["value"] for o in _CANON["taxonomy"][h]) for h in HEADS}
TAXONOMY = UI_TAXONOMY          # the API / frontend contract
MODEL_TAXONOMY = UI_TAXONOMY    # kept as a name for older imports

OUTSIDE_SCOPE_MESSAGE = _CANON["outside_scope_message"]
LOW_CONFIDENCE_MESSAGE = _CANON["low_confidence_message"]


def support_of(head, value):
    """(level, note) for a taxonomy value, or None if the value is not in the taxonomy."""
    return _FEATURES.get(head, {}).get(value)


def schema_payload():
    """JSON-serialisable schema for API clients."""
    return {
        "schema_version": SCHEMA_VERSION,
        "model_type": "four image classifiers (garment type, neckline, sleeve length, sleeve style); not an object detector",
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

    `scope` is kept for older callers; there is one taxonomy, so both values behave the same.

    Returns (clean, errors). `clean` holds the 4 stripped values only when there
    are no errors; `errors` maps head -> {"code", "message"}.
    """
    attrs = attrs if isinstance(attrs, dict) else {}
    allowed = UI_TAXONOMY
    clean, errors = {}, {}
    for head in HEADS:
        raw = attrs.get(head)
        if not raw or not isinstance(raw, str):
            errors[head] = {"code": "REQUIRED", "message": f"Missing or invalid attribute '{head}'"}
            continue
        val = raw.strip()
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

    with_scope=True additionally rejects a combination outside the PROJECT scope (SCOPE); the API and the
    drafting engine both use it."""
    unsupported, approximated = [], []
    for head in HEADS:
        # a value that is no longer selectable (e.g. a bell sleeve saved before 3 Oct 2026) cannot be drafted:
        # it is reported as unsupported with a reason, never a crash and never swapped for another value
        level, note = support_of(head, clean.get(head)) or (
            UNSUPPORTED, f"'{clean.get(head)}' is not one of the selectable {head.replace('_', ' ')} values any more.")
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
