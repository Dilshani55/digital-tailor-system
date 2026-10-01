// Measurement rules for the React forms. The list of fields and WHICH ONES A DESIGN NEEDS come from
// config/measurement_requirements.json - the same file the backend validation, the saved profile and the
// drafting engine use (backend/app/logic/measurement_schema.py). The backend re-validates everything.
//
// Values are kept exactly as the user typed them, together with the unit they were typed in. Switching the
// display unit never rewrites a typed value, so nothing is converted twice or rounded away.
import REQ from '../../../config/measurement_requirements.json';

export const CANONICAL_UNIT = 'cm';
export const CM_PER_INCH = 2.54;
export const UNITS = ['cm', 'in'];

export const MEASUREMENT_FIELDS = REQ.fields.map(({ key, label }) => ({ key, label }));
export const FIELD_KEYS = MEASUREMENT_FIELDS.map((f) => f.key);
export const LABELS = Object.fromEntries(MEASUREMENT_FIELDS.map((f) => [f.key, f.label]));

/** Measurement keys the confirmed design needs (FIELD_KEYS order). Same algorithm as the backend. */
export function requiredFor(design) {
  const attrs = design || {};
  const need = new Set();
  REQ.rules.forEach((rule) => {
    const matches = Object.entries(rule.when).every(([head, allowed]) => allowed.includes(attrs[head]));
    if (matches) rule.fields.forEach((f) => need.add(f));
  });
  return FIELD_KEYS.filter((k) => need.has(k));
}

// What may be typed: digits with at most one decimal point ("88", "88.5", ".5", "12."). A decimal comma
// ("88,5", as phone keypads in some languages type it) means the same as a point. Anything else - a minus
// sign, "1e2", "1,234.5", letters - is reported, never guessed at or silently changed.
const PLAIN_DECIMAL = /^(\d+[.,]?\d*|[.,]\d+)$/;

/** Parse what a user typed. Returns { value } | { error } | { missing: true }. Decimals are fine. */
export function parseEntry(raw) {
  if (raw === null || raw === undefined) return { missing: true };
  if (typeof raw === 'string' && raw.trim() === '') return { missing: true };
  if (typeof raw === 'boolean') return { error: 'Must be a number.' };
  let value = raw;
  if (typeof raw !== 'number') {
    const text = String(raw).trim();
    if (/^-/.test(text) && PLAIN_DECIMAL.test(text.slice(1))) return { error: 'Must be greater than 0.' };
    if (!PLAIN_DECIMAL.test(text)) return { error: `'${text}' is not a number. Use digits only, for example 88.5.` };
    value = Number(text.replace(',', '.'));
  }
  if (Number.isNaN(value)) return { error: `'${raw}' is not a number.` };
  if (!Number.isFinite(value)) return { error: 'Must be a finite number.' };
  if (value <= 0) return { error: 'Must be greater than 0.' };
  return { value };
}

/**
 * A saved profile as form values: each measurement exactly as the user entered it, in the unit it was
 * entered in (`original_values`), so that opening and saving a profile never rewrites a value. Falls back to
 * the stored centimetres when no original is recorded (or it no longer matches the stored value).
 * Returns { values: {key: text}, units: {key: 'cm'|'in'} }.
 */
export function storedEntries(profile) {
  const values = {};
  const units = {};
  const originals = profile?.original_values || {};
  FIELD_KEYS.forEach((key) => {
    const cm = profile?.[key] ?? (key === 'armhole_depth_cm' ? profile?.armhole_cm : null);
    if (cm === null || cm === undefined || cm === '') { values[key] = ''; return; }
    const o = originals[key];
    const same = o && UNITS.includes(o.unit) && Number.isFinite(Number(o.value))
      && Math.abs(toCm(Number(o.value), o.unit) - Number(cm)) < 1e-6;
    if (same && o.unit !== CANONICAL_UNIT) {
      values[key] = String(o.value);
      units[key] = o.unit;
    } else {
      values[key] = String(cm);
    }
  });
  return { values, units };
}

/** Exact conversion to cm (1 in = 2.54 cm), no rounding. */
export function toCm(value, unit) {
  return unit === 'in' ? value * CM_PER_INCH : value;
}

/**
 * What to show in an input for a value typed in `typedUnit` while the page shows `unit`.
 * Same unit -> exactly what was typed. Other unit -> the converted number for display only (the typed value
 * and its unit are what is saved).
 */
export function displayValue(raw, typedUnit, unit) {
  const parsed = parseEntry(raw);
  if (parsed.value === undefined || (typedUnit || unit) === unit) return raw === null || raw === undefined ? '' : String(raw);
  const cm = toCm(parsed.value, typedUnit);
  const shown = unit === 'in' ? cm / CM_PER_INCH : cm;
  return String(Number(shown.toFixed(2)));
}

/** Canonical cm of every valid entered value: { key: cm }. */
export function canonicalCm(values, typedUnits = {}, fallbackUnit = 'cm') {
  const out = {};
  FIELD_KEYS.forEach((key) => {
    const parsed = parseEntry(values?.[key]);
    if (parsed.value !== undefined) out[key] = toCm(parsed.value, typedUnits[key] || fallbackUnit);
  });
  return out;
}

/**
 * Validate what the user typed: every REQUIRED field must be present, every entered value must be a
 * finite number greater than 0. No plausibility ranges. Returns { field: message }.
 */
export function validateMeasurements(values, required = []) {
  const errors = {};
  MEASUREMENT_FIELDS.forEach((field) => {
    const parsed = parseEntry(values?.[field.key]);
    if (parsed.missing) {
      if (required.includes(field.key)) errors[field.key] = `${field.label} is required for this design.`;
      return;
    }
    if (parsed.error) errors[field.key] = parsed.error;
  });
  return errors;
}

/**
 * Flatten a backend error response into { field: message }.
 * Handles structured `field_errors` (first message per field) and falls back to `{ _form }`.
 */
export function parseFieldErrors(err) {
  const data = err?.response?.data;
  const fieldErrors = data?.field_errors;
  if (fieldErrors && typeof fieldErrors === 'object') {
    const out = {};
    Object.entries(fieldErrors).forEach(([field, list]) => {
      const first = Array.isArray(list) ? list[0] : list;
      out[field] = first?.message || String(first);
    });
    return out;
  }
  return { _form: data?.error || 'Request failed. Please try again.' };
}

/**
 * Payload of the fields that were actually entered (nothing invented), each with the unit it was typed in:
 * { unit, units: {key: unit}, key: number }. `onlyKeys` limits it to the fields shown for the design.
 */
export function buildPayload(values, typedUnits = {}, fallbackUnit = 'cm', onlyKeys = FIELD_KEYS) {
  const payload = { unit: fallbackUnit, units: {} };
  onlyKeys.forEach((key) => {
    const parsed = parseEntry(values?.[key]);
    if (parsed.value !== undefined) {
      payload[key] = parsed.value;
      payload.units[key] = typedUnits[key] || fallbackUnit;
    }
  });
  return payload;
}
