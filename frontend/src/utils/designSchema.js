// Design-feature schema used by the confirmation UI: the 15 ACTIVE classes the user may choose
// (3 garment / 5 neckline / 3 sleeve length / 4 sleeve style), their drafting support and the
// draftable combinations. Everything comes from the single canonical file <repo>/config/garment_scope.json,
// which the backend (app/logic/feature_schema.py) reads too — there is no second, hand-copied list.
// The deployed classifier still predicts its original larger taxonomy (3/10/6/9); a prediction
// outside this list is never remapped - see `predictionOutsideScope` below.
//
// Support levels describe what the CURRENT drafting engine really does with a value:
//   implemented   – geometry reflects the value
//   approximated  – accepted, but only part of the design is reflected
//   unsupported   – cannot be drafted; pattern generation is rejected (never substituted)
import CANON from '../../../config/garment_scope.json';

export const IMPLEMENTED = 'implemented';
export const APPROXIMATED = 'approximated';
export const UNSUPPORTED = 'unsupported';

export const HEADS = CANON.heads;
export const HEAD_TITLES = CANON.head_titles;
export const DESIGN_SCHEMA = CANON.taxonomy;
export const OUTSIDE_SCOPE_MESSAGE = CANON.outside_scope_message;
export const LOW_CONFIDENCE_MESSAGE = CANON.low_confidence_message;

/** { head: [{value,label}] } — the shape the review UI has always used. */
export const ACTIVE_TAXONOMY_OPTIONS = Object.fromEntries(
  HEADS.map((h) => [h, DESIGN_SCHEMA[h].map(({ value, label }) => ({ value, label }))]),
);

export function supportOf(head, value) {
  return (DESIGN_SCHEMA[head] || []).find((o) => o.value === value) || null;
}

export const labelOf = (head, value) => supportOf(head, value)?.label || value;

/** Mirrors backend validate_attributes' relationship rule. Returns a message or ''. */
export function consistencyError(selections) {
  if (selections?.sleeve_length === 'sleeveless' && selections?.sleeve_style
      && selections.sleeve_style !== 'none') {
    return `A sleeveless garment cannot have sleeve style '${selections.sleeve_style}'. `
      + "Choose sleeve style 'none' or change the sleeve length.";
  }
  if (selections?.sleeve_style === 'none' && selections?.sleeve_length && selections.sleeve_length !== 'sleeveless') {
    return "Sleeve style 'none' is only for sleeveless garments. Choose a sleeve style or make the garment sleeveless.";
  }
  return '';
}

// PROJECT SCOPE: garment -> { neckline_type: [...], sleeves: { sleeve_length: [sleeve styles] } }
export const SCOPE = Object.fromEntries(Object.entries(CANON.scope).map(([g, d]) => [g, {
  label: d.label,
  neckline_type: d.neckline_type,
  sleeve_length: Object.keys(d.sleeves),
  sleeves: d.sleeves,
}]));

const pretty = (vals) => vals.map((v) => v.replace('-neck', '').replace('-sleeve', '').replace(/-/g, ' ')).join(', ');

export function scopeViolations(sel) {
  const allowed = SCOPE[sel?.garment_type];
  if (!allowed || !sel.neckline_type || !sel.sleeve_length) return [];
  const out = [];
  [['neckline_type', 'necklines'], ['sleeve_length', 'sleeve lengths']].forEach(([head, what]) => {
    if (!allowed[head].includes(sel[head])) {
      out.push({ head, value: sel[head], label: labelOf(head, sel[head]),
        note: `Outside the supported scope: ${allowed.label} supports ${pretty(allowed[head])} ${what} only.` });
    }
  });
  const styles = allowed.sleeves[sel.sleeve_length];
  if (sel.sleeve_style && styles && !styles.includes(sel.sleeve_style)) {
    out.push({ head: 'sleeve_style', value: sel.sleeve_style, label: labelOf('sleeve_style', sel.sleeve_style),
      note: `Outside the supported scope: ${allowed.label} with ${sel.sleeve_length} supports ${styles.map((s) => `'${s}'`).join(', ')} sleeve style only.` });
  }
  return out;
}

/**
 * Can `value` be chosen for `head` given the other current selections and still be draftable?
 * Returns '' when it can, otherwise a short reason (used to disable dropdown options).
 */
export function optionBlockedReason(head, value, sel = {}) {
  const opt = supportOf(head, value);
  if (!opt) return 'Not a supported class.';
  if (opt.support === UNSUPPORTED) return 'Pattern not available yet';
  const g = head === 'garment_type' ? value : sel.garment_type;
  const allowed = SCOPE[g];
  if (!allowed || head === 'garment_type') return '';   // any garment can be chosen; conflicts show on the other heads
  if (head === 'neckline_type' && !allowed.neckline_type.includes(value)) return `Not available for ${allowed.label}`;
  if (head === 'sleeve_length' && !allowed.sleeve_length.includes(value)) return `Not available for ${allowed.label}`;
  if (head === 'sleeve_style') {
    const styles = sel.sleeve_length ? allowed.sleeves[sel.sleeve_length] : [...new Set(Object.values(allowed.sleeves).flat())];
    if (styles && !styles.includes(value)) return `Not available for ${allowed.label}${sel.sleeve_length ? ` with ${labelOf('sleeve_length', sel.sleeve_length).toLowerCase()}` : ''}`;
  }
  return '';
}

/** Unsupported / approximated selections among the four heads (empty entries ignored). */
export function supportReport(selections) {
  const unsupported = [];
  const approximated = [];
  HEADS.forEach((head) => {
    const opt = supportOf(head, selections?.[head]);
    if (!opt) return;
    const item = { head, value: opt.value, label: opt.label, note: opt.note };
    if (opt.support === UNSUPPORTED) unsupported.push(item);
    else if (opt.support === APPROXIMATED) approximated.push(item);
  });
  const seen = new Set(unsupported.map((u) => `${u.head}:${u.value}`));
  scopeViolations(selections).forEach((v) => { if (!seen.has(`${v.head}:${v.value}`)) unsupported.push(v); });
  const bad = new Set(unsupported.map((u) => `${u.head}:${u.value}`));
  const approx = approximated.filter((a) => !bad.has(`${a.head}:${a.value}`));
  return { supported: unsupported.length === 0, unsupported, approximated: approx };
}

/** True if the model's top-1 label for `head` is not one of the user-selectable classes. */
export function predictionOutsideScope(head, label) {
  return Boolean(label) && !(DESIGN_SCHEMA[head] || []).some((o) => o.value === label);
}
