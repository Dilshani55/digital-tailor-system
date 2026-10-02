"""
MEASUREMENT SCHEMA - the body measurements the drafting engine can use, their canonical unit and the
validation rules. Which measurements a design NEEDS comes from backend/config/measurement_requirements.json, the
same file the frontend reads, so the form, this validation, the saved profile and the engine agree.

Units
-----
Canonical storage / calculation unit is CENTIMETRES. The API also accepts INCHES (unit="in", globally or
per field via "units": {field: unit}); 1 in = 2.54 cm exactly. The value the user entered and its unit are
stored next to the canonical cm value. No unit is ever guessed: a missing unit means "cm", an unknown one
is an error.

Validation
----------
A provided value must be a finite number greater than 0 (decimals are fine). Values are never clamped, changed
or rejected for being unusual: a value outside the usual range of a field only produces a WARNING
(measurement_warnings) so a typing or unit mistake can be noticed. Measurements that cannot be drawn into a
valid block are reported by the drafting engine itself (geometry feasibility), field by field.
Required fields depend on the confirmed design (required_for_design); missing values are never invented.

Kinds of field
--------------
measurement  taken on the body.
design       a design value with a calculated default from the drafting method (neck width, neck depths, armhole
             depth, bust-point distance). Empty = the calculated value is used, and shown as "calculated".
legacy       measurements earlier versions asked for and the drafting method does not use (neck around, height,
             one-shoulder length, across-back, wrist). They stay stored on old profiles and are never required.
"""

import json
import math
import os

SCHEMA_VERSION = 3
CANONICAL_UNIT = "cm"
UNITS = ("cm", "in")
CM_PER_INCH = 2.54

FABRIC_TYPES = ("woven", "knit", "stretch-knit")
FIT_PREFERENCES = ("close", "standard", "loose")

_REQ_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "config",
                                         "measurement_requirements.json"))
with open(_REQ_PATH, encoding="utf-8") as _f:
    REQUIREMENTS = json.load(_f)

_FIELDS = REQUIREMENTS["fields"]
DESCRIPTIONS = {f["key"]: f["guide"] for f in _FIELDS}           # how to measure
KIND = {f["key"]: f["kind"] for f in _FIELDS}                    # measurement | design
USUAL_CM = {f["key"]: tuple(f["usual_cm"]) for f in _FIELDS}     # only for warnings

LEGACY_KEYS = tuple(REQUIREMENTS["legacy_fields"])
_LEGACY_LABELS = {"neck_cm": "Neck around", "height_cm": "Height", "shoulder_cm": "Shoulder length",
                  "across_back_cm": "Across-back width", "wrist_cm": "Wrist around"}

ACTIVE_KEYS = tuple(f["key"] for f in _FIELDS)                   # what the drafting method can use
FIELD_KEYS = ACTIVE_KEYS + LEGACY_KEYS                           # everything a profile can store
LABELS = {**{f["key"]: f["label"] for f in _FIELDS}, **_LEGACY_LABELS}

# Accepted input aliases -> canonical key (older clients sent armhole_cm)
ALIASES = {"armhole_cm": "armhole_depth_cm"}


def required_for_design(attributes):
    """
    The measurement keys the confirmed design needs (order of FIELD_KEYS). `attributes` is the confirmed
    design {garment_type, neckline_type, sleeve_length, sleeve_style}. Without a design only the bodice
    fields (needed by every pattern) are returned.
    """
    attrs = attributes or {}
    need = set()
    for rule in REQUIREMENTS["rules"]:
        if all(attrs.get(k) in allowed for k, allowed in rule["when"].items()):
            need.update(rule["fields"])
    return [k for k in FIELD_KEYS if k in need]


def schema_payload():
    return {
        "schema_version": SCHEMA_VERSION,
        "canonical_unit": CANONICAL_UNIT,
        "accepted_units": list(UNITS),
        "cm_per_inch": CM_PER_INCH,
        "fields": [{"key": f["key"], "label": f["label"], "description": f["guide"], "group": f["group"],
                    "kind": f["kind"], "view": f["view"], "common_mistake": f["mistake"]} for f in _FIELDS],
        "groups": REQUIREMENTS["groups"],
        "legacy_fields": list(LEGACY_KEYS),
        "requirement_rules": REQUIREMENTS["rules"],
        "validation": "every provided value must be a finite number greater than 0; unusual values only warn",
        "fabric_types": list(FABRIC_TYPES),
        "fit_preferences": list(FIT_PREFERENCES),
    }


# ── units ────────────────────────────────────────────────────────────────────
def normalize_unit(unit):
    """Return (unit, error). None/'' means cm; anything unknown is an error, never guessed."""
    if unit is None or (isinstance(unit, str) and unit.strip() == ""):
        return CANONICAL_UNIT, None
    if isinstance(unit, str) and unit.strip().lower() in UNITS:
        return unit.strip().lower(), None
    return None, {"code": "INVALID_UNIT",
                  "message": f"Unit must be one of {', '.join(UNITS)} (got '{unit}')."}


def to_cm(value, unit):
    """Exact conversion to canonical cm (1 in = 2.54 cm). Only float noise is rounded (9 decimals)."""
    return round(value * CM_PER_INCH, 9) if unit == "in" else float(value)


# ── parsing ──────────────────────────────────────────────────────────────────
def parse_number(raw):
    """
    Returns (value, error). Missing (None / blank string) -> (None, None).
    Rejects booleans, non-numeric text, NaN/Infinity, zero and negatives.
    """
    if raw is None or (isinstance(raw, str) and raw.strip() == ""):
        return None, None
    if isinstance(raw, bool) or not isinstance(raw, (int, float, str)):
        return None, {"code": "NOT_A_NUMBER", "message": "Must be a number."}
    try:
        value = float(raw.strip() if isinstance(raw, str) else raw)
    except ValueError:
        return None, {"code": "NOT_A_NUMBER", "message": f"'{raw}' is not a number."}
    if not math.isfinite(value):
        return None, {"code": "NOT_FINITE", "message": "Must be a finite number."}
    if value <= 0:
        return None, {"code": "NOT_POSITIVE", "message": "Must be greater than 0."}
    return value, None


def convert_input(data, unit, units=None):
    """
    Convert user input to canonical cm. `unit` applies to every field unless `units` ({field: unit}) names
    the unit a particular value was entered in.

    Returns (canonical, original, errors):
      canonical {field: cm_float}  only for fields that were provided and parsed
      original  {field: {"value": entered_number, "unit": unit}}
      errors    {field: [ {code, message} ]}
    """
    canonical, original, errors = {}, {}, {}
    data = data if isinstance(data, dict) else {}
    units = units if isinstance(units, dict) else {}
    for key in FIELD_KEYS:
        raw = data.get(key)
        if raw is None or (isinstance(raw, str) and raw.strip() == ""):
            for alias, target in ALIASES.items():
                if target == key and data.get(alias) not in (None, ""):
                    raw = data.get(alias)
        field_unit = unit
        if key in units:
            field_unit, uerr = normalize_unit(units.get(key))
            if uerr:
                errors.setdefault(key, []).append(uerr)
                continue
        value, err = parse_number(raw)
        if err:
            errors.setdefault(key, []).append(err)
        elif value is not None:
            canonical[key] = to_cm(value, field_unit)
            original[key] = {"value": value, "unit": field_unit}
    return canonical, original, errors


# ── warnings (never errors) ──────────────────────────────────────────────────
def measurement_warnings(canonical):
    """
    [{field, code, message}] for values that may be a typing or unit mistake. A warning never blocks saving or
    drafting and makes no judgement about the body: it only asks the user to look at the number again.
    """
    out = []

    def warn(field, code, message):
        out.append({"field": field, "code": code, "message": message})

    for key in ACTIVE_KEYS:
        v = canonical.get(key)
        if v is None:
            continue
        lo, hi = USUAL_CM[key]
        if v < lo or v > hi:
            warn(key, "UNUSUAL_VALUE",
                 f"{LABELS[key]} {v:g} cm is outside the usual range ({lo:g}-{hi:g} cm). "
                 f"Please check the number and the unit (cm / inch).")
    c = canonical.get
    if c("shoulder_width_cm") and c("bust_cm") and c("shoulder_width_cm") >= c("bust_cm") / 2.0:
        warn("shoulder_width_cm", "CHECK_PROPORTION",
             "Shoulder to shoulder is at least half of the bust around. It is measured straight across the back, "
             "from shoulder tip to shoulder tip.")
    if c("sleeve_end_cm") and c("bicep_cm") and c("sleeve_end_cm") > c("bicep_cm") + 1e-9:
        warn("sleeve_end_cm", "CHECK_PROPORTION",
             "Sleeve end around is larger than the upper arm around. Please check both numbers.")
    if c("shoulder_to_bust_cm") and c("back_waist_length_cm") and c("shoulder_to_bust_cm") >= c("back_waist_length_cm"):
        warn("shoulder_to_bust_cm", "CHECK_PROPORTION",
             "Shoulder to bust point is not shorter than back neck to waist. Please check both numbers.")
    if c("garment_length_cm") and c("back_waist_length_cm") and c("garment_length_cm") < c("back_waist_length_cm"):
        warn("garment_length_cm", "CHECK_PROPORTION",
             "Garment length is shorter than back neck to waist: the garment would end above the waist.")
    return out


# ── required fields ──────────────────────────────────────────────────────────
def missing_fields(canonical, required):
    return [k for k in required if canonical.get(k) is None]


def missing_errors(canonical, required):
    return {k: [{"code": "REQUIRED", "message": f"{LABELS[k]} is required for this design."}]
            for k in missing_fields(canonical, required)}


def summarise(errors):
    """One human-readable line from field errors (first message per field)."""
    parts = [f"{LABELS.get(k, k)}: {v[0]['message']}" for k, v in errors.items() if v]
    return "; ".join(parts) if parts else "Measurement validation failed."


def error_response_body(errors, code="MEASUREMENT_VALIDATION_FAILED"):
    return {"error": summarise(errors), "error_code": code, "field_errors": errors}


# ── the ONLY path to the drafting engine ────────────────────────────────────
def engine_measurements(profile, attributes):
    """
    Build the dict handed to the drafting engine from a stored profile and the CONFIRMED design.

    Returns (measurements, error_code, field_errors); (dict, None, {}) on success. Nothing is defaulted:
    a measurement the design needs but the profile lacks is an error (MEASUREMENTS_INCOMPLETE); a value
    that is not a positive finite number is an error (MEASUREMENTS_INVALID). Measurements the design does
    not need are passed through only if present (None otherwise). This is the only function that should
    produce engine input.
    """
    required = required_for_design(attributes)
    canonical, errors = {}, {}
    long_sleeve = (attributes or {}).get("sleeve_length") == "long-sleeve"
    for key in FIELD_KEYS:
        value = getattr(profile, key, None)
        if key == "sleeve_end_cm" and value is None and long_sleeve:
            # a long sleeve ends at the wrist: an older profile's wrist measurement IS its sleeve-end measurement
            value = getattr(profile, "wrist_cm", None)
        if key == "armhole_depth_cm" and value is None:
            value = getattr(profile, "armhole_cm", None)          # oldest profiles stored it under this name
        if value is None:
            canonical[key] = None
            if key in required:
                errors[key] = [{"code": "REQUIRED", "message": f"{LABELS[key]} is required for this design."}]
            continue
        v, err = parse_number(value)
        if err:
            errors[key] = [err]
        else:
            canonical[key] = v
    if errors:
        return None, ("MEASUREMENTS_INCOMPLETE" if all(
            e[0]["code"] == "REQUIRED" for e in errors.values()) else "MEASUREMENTS_INVALID"), errors

    fabric = getattr(profile, "fabric_type", None)
    fit = getattr(profile, "fit_preference", None)
    if fabric not in FABRIC_TYPES:
        errors["fabric_type"] = [{"code": "INVALID_CHOICE",
                                  "message": f"fabric_type must be one of {', '.join(FABRIC_TYPES)}."}]
    if fit not in FIT_PREFERENCES:
        errors["fit_preference"] = [{"code": "INVALID_CHOICE",
                                     "message": f"fit_preference must be one of {', '.join(FIT_PREFERENCES)}."}]
    if errors:
        return None, "MEASUREMENTS_INVALID", errors

    measurements = dict(canonical)
    measurements["fabric_type"] = fabric
    measurements["fit_preference"] = fit
    measurements["required_fields"] = required
    return measurements, None, {}
