// Measurement schema for the React forms.
// MUST mirror backend/app/logic/measurement_schema.py (field keys and default cm ranges);
// backend test_measurement_contract checks the two files agree. The backend is always the
// authority: this module gives instant feedback, the server re-validates everything
// (including cross-field relationships) and returns field-level errors.

export const CANONICAL_UNIT = 'cm';
export const CM_PER_INCH = 2.54;
export const UNITS = ['cm', 'in'];

export const MEASUREMENT_FIELDS = [
  { key: 'bust_cm', label: 'Bust', min: 60, max: 160 },
  { key: 'waist_cm', label: 'Waist', min: 45, max: 150 },
  { key: 'hip_cm', label: 'Hip', min: 70, max: 170 },
  { key: 'height_cm', label: 'Height', min: 130, max: 210 },
  { key: 'neck_cm', label: 'Neck', min: 25, max: 55 },
  { key: 'shoulder_cm', label: 'Shoulder length', min: 8, max: 20 },
  { key: 'across_back_cm', label: 'Across-back width', min: 25, max: 50 },
  { key: 'back_waist_length_cm', label: 'Back waist length', min: 30, max: 55 },
  { key: 'armhole_depth_cm', label: 'Armhole depth', min: 15, max: 30 },
  { key: 'garment_length_cm', label: 'Garment length', min: 20, max: 110 },
  { key: 'bicep_cm', label: 'Bicep', min: 18, max: 50 },
  { key: 'sleeve_cm', label: 'Sleeve length (full arm)', min: 40, max: 75 },
  { key: 'wrist_cm', label: 'Wrist', min: 10, max: 25 },
];

export const FIELD_KEYS = MEASUREMENT_FIELDS.map((f) => f.key);
export const CORE_FIELDS = ['bust_cm', 'waist_cm', 'hip_cm', 'height_cm'];

const fmt = (n) => Number(n.toFixed(2)).toString();

/** Bounds text in the user's unit, e.g. "60–160 cm (23.6–63.0 in)". */
export function rangeText(field) {
  return `${field.min}–${field.max} cm (${(field.min / CM_PER_INCH).toFixed(1)}–${(field.max / CM_PER_INCH).toFixed(1)} in)`;
}

/** Parse what a user typed. Returns { value } | { error } | { missing: true }. */
export function parseEntry(raw) {
  if (raw === null || raw === undefined) return { missing: true };
  if (typeof raw === 'string' && raw.trim() === '') return { missing: true };
  if (typeof raw === 'boolean') return { error: 'Must be a number.' };
  const value = typeof raw === 'number' ? raw : Number(String(raw).trim());
  if (Number.isNaN(value)) return { error: `'${raw}' is not a number.` };
  if (!Number.isFinite(value)) return { error: 'Must be a finite number.' };
  if (value <= 0) return { error: 'Must be greater than 0.' };
  return { value };
}

export const toCm = (value, unit) => (unit === 'in' ? Math.round(value * CM_PER_INCH * 100) / 100 : value);

/**
 * Validate what the user typed (in `unit`) against required-ness, number-ness and the
 * plausible cm range. Returns { field: message } — empty object means valid.
 * `required` defaults to all 13 fields (needed to generate a pattern).
 */
export function validateMeasurements(values, unit = 'cm', required = FIELD_KEYS) {
  const errors = {};
  MEASUREMENT_FIELDS.forEach((field) => {
    const parsed = parseEntry(values?.[field.key]);
    if (parsed.missing) {
      if (required.includes(field.key)) errors[field.key] = `${field.label} is required.`;
      return;
    }
    if (parsed.error) {
      errors[field.key] = parsed.error;
      return;
    }
    const cm = toCm(parsed.value, unit);
    if (cm < field.min || cm > field.max) {
      errors[field.key] = `${field.label} ${fmt(parsed.value)} ${unit} is outside the plausible range ${rangeText(field)}.`;
    }
  });
  return errors;
}

/** Convert displayed numbers between units (used by the unit toggle). Blank stays blank. */
export function convertDisplayValues(values, from, to) {
  if (from === to) return { ...values };
  const factor = from === 'cm' ? 1 / CM_PER_INCH : CM_PER_INCH;
  const out = { ...values };
  FIELD_KEYS.forEach((key) => {
    const parsed = parseEntry(values?.[key]);
    if (parsed.value !== undefined) out[key] = Math.round(parsed.value * factor * 100) / 100;
  });
  return out;
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

/** Numbers-only payload of the fields that were actually entered (nothing invented). */
export function buildPayload(values, unit) {
  const payload = { unit };
  FIELD_KEYS.forEach((key) => {
    const parsed = parseEntry(values?.[key]);
    if (parsed.value !== undefined) payload[key] = parsed.value;
  });
  return payload;
}
