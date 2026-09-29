"""
MEASUREMENT SCHEMA — the single definition of the 13 body measurements the drafting
engine needs, their canonical unit, plausible ranges and validation rules.

Units
-----
Canonical storage / calculation unit is CENTIMETRES. The API also accepts INCHES
(unit="in"); conversion happens exactly once, here (1 in = 2.54 cm), and both the
original entered value+unit and the canonical cm value are stored. No other unit is
accepted and no unit is ever guessed: a missing unit means "cm", an unknown one is an error.

Fields (all in cm)
------------------
Required to CREATE a customer profile: bust, waist, hip, height (the "core" four).
Required to GENERATE A PATTERN: all 13. Missing values are never invented.

Ranges are deliberately wide "is this physically plausible for an adult woman's
body?" bounds, NOT fit recommendations. Override with the environment variable
MEASUREMENT_RANGES_JSON, e.g. '{"bust_cm": [60, 170]}'.

Relationships (only where anatomically/technically justified AND able to fire within
the ranges — e.g. shoulder<across-back and bicep<bust are implied by the ranges alone):
  wrist < bicep, neck < waist, armhole depth < back-waist length,
  back-waist length 18-35 % of height, sleeve length <= 50 % of height,
  garment length <= 60 % of height.
"""

import json
import math
import os

SCHEMA_VERSION = 1
CANONICAL_UNIT = "cm"
UNITS = ("cm", "in")
CM_PER_INCH = 2.54

FABRIC_TYPES = ("woven", "knit", "stretch-knit")
FIT_PREFERENCES = ("close", "standard", "loose")

# key, label, how to measure (short), default (min, max) in cm
_FIELDS = (
    ("bust_cm", "Bust", "Fullest part of the bust, tape horizontal", (60.0, 160.0)),
    ("waist_cm", "Waist", "Natural waist, narrowest point", (45.0, 150.0)),
    ("hip_cm", "Hip", "Fullest part of hips/seat", (70.0, 170.0)),
    ("height_cm", "Height", "Total body height, barefoot", (130.0, 210.0)),
    ("neck_cm", "Neck", "Circumference at the base of the neck", (25.0, 55.0)),
    ("shoulder_cm", "Shoulder length", "Side-neck point to shoulder tip", (8.0, 20.0)),
    ("across_back_cm", "Across-back width", "Between the two back armhole creases", (25.0, 50.0)),
    ("back_waist_length_cm", "Back waist length", "Nape to natural waist along the spine", (30.0, 55.0)),
    ("armhole_depth_cm", "Armhole depth", "Shoulder line down to the underarm level", (15.0, 30.0)),
    ("garment_length_cm", "Garment length", "Desired finished length from the high shoulder", (20.0, 110.0)),
    ("bicep_cm", "Bicep", "Fullest part of the upper arm", (18.0, 50.0)),
    ("sleeve_cm", "Sleeve length (full arm)", "Shoulder tip down the arm to the wrist bone (FULL arm length; short/elbow sleeves are derived from it)", (40.0, 75.0)),
    ("wrist_cm", "Wrist", "Circumference at the wrist bone", (10.0, 25.0)),
)

FIELD_KEYS = tuple(f[0] for f in _FIELDS)
CORE_FIELDS = ("bust_cm", "waist_cm", "hip_cm", "height_cm")
LABELS = {f[0]: f[1] for f in _FIELDS}
DESCRIPTIONS = {f[0]: f[2] for f in _FIELDS}

# Accepted input aliases -> canonical key (older clients sent armhole_cm)
ALIASES = {"armhole_cm": "armhole_depth_cm"}


def get_ranges():
    """Plausible (min, max) cm per field, with optional validated env override."""
    ranges = {f[0]: f[3] for f in _FIELDS}
    raw = os.environ.get("MEASUREMENT_RANGES_JSON")
    if raw:
        try:
            override = json.loads(raw)
        except ValueError as exc:
            raise ValueError(f"MEASUREMENT_RANGES_JSON is not valid JSON: {exc}")
        for key, pair in override.items():
            if key not in ranges:
                raise ValueError(f"MEASUREMENT_RANGES_JSON: unknown field '{key}'")
            lo, hi = float(pair[0]), float(pair[1])
            if not (math.isfinite(lo) and math.isfinite(hi) and 0 < lo < hi):
                raise ValueError(f"MEASUREMENT_RANGES_JSON: invalid range for '{key}'")
            ranges[key] = (lo, hi)
    return ranges


def schema_payload():
    ranges = get_ranges()
    return {
        "schema_version": SCHEMA_VERSION,
        "canonical_unit": CANONICAL_UNIT,
        "accepted_units": list(UNITS),
        "required_for_profile": list(CORE_FIELDS),
        "required_for_pattern": list(FIELD_KEYS),
        "fields": [
            {"key": k, "label": LABELS[k], "description": DESCRIPTIONS[k],
             "min_cm": ranges[k][0], "max_cm": ranges[k][1]}
            for k in FIELD_KEYS
        ],
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
    """Convert a validated positive number to canonical cm (2 decimals)."""
    return round(value * CM_PER_INCH, 2) if unit == "in" else round(float(value), 2)


def _fmt(v):
    return f"{v:g}"


def _range_text(lo, hi):
    return f"{_fmt(lo)}–{_fmt(hi)} cm ({lo / CM_PER_INCH:.1f}–{hi / CM_PER_INCH:.1f} in)"


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


def convert_input(data, unit):
    """
    Convert user input (in `unit`) to canonical cm.

    Returns (canonical, original, errors):
      canonical {field: cm_float}  only for fields that were provided and parsed
      original  {field: {"value": entered_number, "unit": unit}}
      errors    {field: [ {code, message} ]}
    """
    canonical, original, errors = {}, {}, {}
    data = data if isinstance(data, dict) else {}
    for key in FIELD_KEYS:
        raw = data.get(key)
        if raw is None or (isinstance(raw, str) and raw.strip() == ""):
            for alias, target in ALIASES.items():
                if target == key and data.get(alias) not in (None, ""):
                    raw = data.get(alias)
        value, err = parse_number(raw)
        if err:
            errors.setdefault(key, []).append(err)
        elif value is not None:
            canonical[key] = to_cm(value, unit)
            original[key] = {"value": value, "unit": unit}
    return canonical, original, errors


# ── validation ───────────────────────────────────────────────────────────────
def _relations(c):
    """Yield (field, message) for every violated relationship among values present in `c`."""
    def has(*keys):
        return all(k in c for k in keys)

    if has("wrist_cm", "bicep_cm") and c["wrist_cm"] >= c["bicep_cm"]:
        yield "wrist_cm", f"Wrist ({c['wrist_cm']:g} cm) must be smaller than bicep ({c['bicep_cm']:g} cm)."
    if has("neck_cm", "waist_cm") and c["neck_cm"] >= c["waist_cm"]:
        yield "neck_cm", f"Neck ({c['neck_cm']:g} cm) must be smaller than waist ({c['waist_cm']:g} cm)."
    if has("armhole_depth_cm", "back_waist_length_cm") and c["armhole_depth_cm"] >= c["back_waist_length_cm"]:
        yield "armhole_depth_cm", (f"Armhole depth ({c['armhole_depth_cm']:g} cm) must be smaller than "
                                   f"back waist length ({c['back_waist_length_cm']:g} cm).")
    if has("back_waist_length_cm", "height_cm"):
        ratio = c["back_waist_length_cm"] / c["height_cm"]
        if not 0.18 <= ratio <= 0.35:
            yield "back_waist_length_cm", (
                f"Back waist length ({c['back_waist_length_cm']:g} cm) is {ratio * 100:.0f}% of height "
                f"({c['height_cm']:g} cm); expected 18–35%.")
    if has("sleeve_cm", "height_cm") and c["sleeve_cm"] > 0.5 * c["height_cm"]:
        yield "sleeve_cm", (f"Sleeve length ({c['sleeve_cm']:g} cm) cannot exceed half of height "
                            f"({c['height_cm']:g} cm).")
    if has("garment_length_cm", "height_cm") and c["garment_length_cm"] > 0.6 * c["height_cm"]:
        yield "garment_length_cm", (f"Garment length ({c['garment_length_cm']:g} cm) cannot exceed 60% of "
                                    f"height ({c['height_cm']:g} cm).")


def validate_canonical(canonical, only=None):
    """
    Validate canonical-cm values: plausible range per field + relationships.
    `only` (set of field keys) restricts REPORTING to those fields and to relations
    that involve one of them (used for partial updates so untouched legacy values do
    not block an unrelated edit). Returns {field: [ {code, message} ]}.
    """
    ranges = get_ranges()
    errors = {}
    scope = set(only) if only is not None else set(canonical)
    range_bad = set()
    for key in FIELD_KEYS:
        if key not in canonical or key not in scope:
            continue
        lo, hi = ranges[key]
        v = canonical[key]
        if not lo <= v <= hi:
            range_bad.add(key)
            errors.setdefault(key, []).append({
                "code": "OUT_OF_RANGE",
                "message": f"{LABELS[key]} {_fmt(v)} cm is outside the plausible range {_range_text(lo, hi)}.",
                "min_cm": lo, "max_cm": hi,
            })
    # relations only among values that are individually in range
    ok = {k: v for k, v in canonical.items() if k in FIELD_KEYS and
          not (k in range_bad or not (ranges[k][0] <= v <= ranges[k][1]))}
    for field, msg in _relations(ok):
        involved = _INVOLVED[field]
        if scope & involved or field in scope:
            errors.setdefault(field, []).append({"code": "RELATION", "message": msg})
    return errors


# fields each relation rule touches, so partial updates report relevant relations
_INVOLVED = {
    "wrist_cm": {"wrist_cm", "bicep_cm"},
    "neck_cm": {"neck_cm", "waist_cm"},
    "armhole_depth_cm": {"armhole_depth_cm", "back_waist_length_cm"},
    "back_waist_length_cm": {"back_waist_length_cm", "height_cm"},
    "sleeve_cm": {"sleeve_cm", "height_cm"},
    "garment_length_cm": {"garment_length_cm", "height_cm"},
}


def missing_fields(canonical, required=FIELD_KEYS):
    return [k for k in required if canonical.get(k) is None]


def missing_errors(canonical, required=FIELD_KEYS):
    return {k: [{"code": "REQUIRED", "message": f"{LABELS[k]} is required."}]
            for k in missing_fields(canonical, required)}


def summarise(errors):
    """One human-readable line from field errors (first message per field)."""
    parts = [f"{LABELS.get(k, k)}: {v[0]['message']}" for k, v in errors.items() if v]
    return "; ".join(parts) if parts else "Measurement validation failed."


def error_response_body(errors, code="MEASUREMENT_VALIDATION_FAILED"):
    return {"error": summarise(errors), "error_code": code, "field_errors": errors}


# ── the ONLY path to the drafting engine ────────────────────────────────────
def engine_measurements(profile):
    """
    Build the dict handed to ParametricEngine from a stored profile.

    Returns (measurements, error_code, field_errors); (dict, None, {}) on success. Nothing is defaulted:
    a missing measurement is an error, an implausible one is an error. This is the only
    function that should produce engine input.
    """
    canonical = {}
    for key in FIELD_KEYS:
        value = getattr(profile, key, None)
        if key == "armhole_depth_cm" and value is None:
            value = getattr(profile, "armhole_cm", None)
        canonical[key] = value

    errors = {}
    for key, value in canonical.items():
        if value is None:
            errors[key] = [{"code": "REQUIRED", "message": f"{LABELS[key]} is required."}]
        else:
            v, err = parse_number(value)
            if err:
                errors[key] = [err]
            else:
                canonical[key] = v
    if errors:
        return None, ("MEASUREMENTS_INCOMPLETE" if all(
            e[0]["code"] == "REQUIRED" for e in errors.values()) else "MEASUREMENTS_INVALID"), errors

    errors = validate_canonical(canonical)
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
    measurements["armhole_cm"] = canonical["armhole_depth_cm"]   # legacy alias read by the engine
    measurements["fabric_type"] = fabric
    measurements["fit_preference"] = fit
    return measurements, None, {}
