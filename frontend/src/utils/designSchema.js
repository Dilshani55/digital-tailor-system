// Design-feature schema used by the confirmation UI.
// MUST stay identical to backend/app/logic/feature_schema.py (values, order and support
// levels). A backend test (test_feature_contract.py) fails if the two drift apart.
//
// Support levels describe what the CURRENT drafting engine really does with a value:
//   implemented   – geometry reflects the value
//   approximated  – accepted, but only part of the design is reflected
//   unsupported   – cannot be drafted; pattern generation is rejected (never substituted)

export const IMPLEMENTED = 'implemented';
export const APPROXIMATED = 'approximated';
export const UNSUPPORTED = 'unsupported';

export const HEADS = ['garment_type', 'neckline_type', 'sleeve_length', 'sleeve_style'];

export const HEAD_TITLES = {
  garment_type: 'Garment Type',
  neckline_type: 'Neckline Type',
  sleeve_length: 'Sleeve Length',
  sleeve_style: 'Sleeve Style',
};

const NOT_CONNECTED = 'No geometry for this sleeve style has been implemented.';

export const DESIGN_SCHEMA = {
  garment_type: [
    { value: 'blouse', label: 'Blouse', support: IMPLEMENTED, note: 'Woven bodice block with waist darts; hem must reach the waist line.' },
    { value: 't-shirt', label: 'T-Shirt', support: IMPLEMENTED, note: 'Knit bodice block, no darts, neckband piece; hem must reach the waist line.' },
    { value: 'crop-top', label: 'Crop-Top', support: IMPLEMENTED, note: 'Hem must be 2 cm or more above the waist line; a longer garment length is reported as a conflict.' },
  ],
  neckline_type: [
    { value: 'round-neck', label: 'Round Neck', support: IMPLEMENTED, note: 'Curved round neck.' },
    { value: 'v-neck', label: 'V-Neck', support: IMPLEMENTED, note: 'True V: straight edges to a centre-front point.' },
    { value: 'square-neck', label: 'Square Neck', support: IMPLEMENTED, note: 'Square front neck with straight edges.' },
    { value: 'scoop-neck', label: 'Scoop Neck', support: APPROXIMATED, note: 'Drafted as the base round neck; scoop depth is NOT applied.' },
    { value: 'boat-neck', label: 'Boat Neck', support: APPROXIMATED, note: 'Drafted as the base round neck; boat shape is NOT applied.' },
    { value: 'sweetheart-neck', label: 'Sweetheart Neck', support: APPROXIMATED, note: 'Drafted as the base round neck; sweetheart shape is NOT applied.' },
    { value: 'halter-neck', label: 'Halter Neck', support: UNSUPPORTED, note: 'Halter/strap construction is not implemented.' },
    { value: 'high-neck', label: 'High Neck', support: APPROXIMATED, note: 'Drafted as the base round neck; no stand/collar piece is generated.' },
    { value: 'collared-neck', label: 'Collared Neck', support: UNSUPPORTED, note: 'No collar piece is generated.' },
    { value: 'off-shoulder', label: 'Off-Shoulder', support: UNSUPPORTED, note: 'Off-shoulder construction is not implemented.' },
  ],
  sleeve_length: [
    { value: 'sleeveless', label: 'Sleeveless', support: IMPLEMENTED, note: 'No sleeve piece; armhole facing strips are generated.' },
    { value: 'cap-length', label: 'Cap Length', support: UNSUPPORTED, note: 'A cap-length sleeve is shorter than the sleeve cap; not implemented.' },
    { value: 'short-sleeve', label: 'Short Sleeve', support: IMPLEMENTED, note: '40% of the measured full-arm length (project assumption).' },
    { value: 'elbow-length', label: 'Elbow Length', support: IMPLEMENTED, note: '58% of the measured full-arm length (project assumption).' },
    { value: 'three-quarter-sleeve', label: 'Three-Quarter Sleeve', support: IMPLEMENTED, note: '75% of the measured full-arm length (project assumption).' },
    { value: 'long-sleeve', label: 'Long Sleeve', support: IMPLEMENTED, note: 'Full measured arm length, tapering to the wrist.' },
  ],
  sleeve_style: [
    { value: 'none', label: 'None (No Special Style)', support: IMPLEMENTED, note: 'Plain set-in sleeve (or none if sleeveless).' },
    { value: 'regular-sleeve', label: 'Regular Sleeve', support: IMPLEMENTED, note: 'Plain set-in sleeve.' },
    { value: 'puff-sleeve', label: 'Puff Sleeve', support: UNSUPPORTED, note: NOT_CONNECTED },
    { value: 'bell-sleeve', label: 'Bell Sleeve', support: UNSUPPORTED, note: NOT_CONNECTED },
    { value: 'bishop-sleeve', label: 'Bishop Sleeve', support: UNSUPPORTED, note: NOT_CONNECTED },
    { value: 'flutter-sleeve', label: 'Flutter Sleeve', support: UNSUPPORTED, note: NOT_CONNECTED },
    { value: 'raglan-sleeve', label: 'Raglan Sleeve', support: UNSUPPORTED, note: 'Raglan construction is not implemented.' },
    { value: 'dolman-sleeve', label: 'Dolman Sleeve', support: UNSUPPORTED, note: NOT_CONNECTED },
    { value: 'kimono-sleeve', label: 'Kimono Sleeve', support: UNSUPPORTED, note: NOT_CONNECTED },
  ],
};

/** { head: [{value,label}] } — the shape the review UI has always used. */
export const ACTIVE_TAXONOMY_OPTIONS = Object.fromEntries(
  HEADS.map((h) => [h, DESIGN_SCHEMA[h].map(({ value, label }) => ({ value, label }))]),
);

export function supportOf(head, value) {
  return (DESIGN_SCHEMA[head] || []).find((o) => o.value === value) || null;
}

/** Mirrors backend validate_attributes' relationship rule. Returns a message or ''. */
export function consistencyError(selections) {
  if (selections?.sleeve_length === 'sleeveless' && selections?.sleeve_style
      && selections.sleeve_style !== 'none') {
    return `A sleeveless garment cannot have sleeve style '${selections.sleeve_style}'. `
      + "Choose sleeve style 'none' or change the sleeve length.";
  }
  return '';
}

// PROJECT SCOPE — mirrors backend feature_schema.SCOPE.
export const SCOPE = {
  blouse: { neckline_type: ['round-neck', 'v-neck', 'square-neck'], sleeve_length: ['short-sleeve', 'long-sleeve'] },
  't-shirt': { neckline_type: ['round-neck', 'v-neck'], sleeve_length: ['short-sleeve', 'long-sleeve'] },
  'crop-top': { neckline_type: ['round-neck', 'v-neck', 'square-neck'], sleeve_length: ['sleeveless', 'short-sleeve'] },
};
const SCOPE_LABEL = { blouse: 'Blouse', 't-shirt': 'T-shirt', 'crop-top': 'Crop-top' };
const pretty = (vals) => vals.map((v) => v.replace('-neck', '').replace('-sleeve', '').replace(/-/g, ' ')).join(', ');

export function scopeViolations(sel) {
  const allowed = SCOPE[sel?.garment_type];
  if (!allowed || !sel.neckline_type || !sel.sleeve_length) return [];
  const out = [];
  [['neckline_type', 'necklines'], ['sleeve_length', 'sleeve lengths']].forEach(([head, what]) => {
    if (!allowed[head].includes(sel[head])) {
      const opt = supportOf(head, sel[head]);
      out.push({ head, value: sel[head], label: opt ? opt.label : sel[head],
        note: `Outside the supported scope: ${SCOPE_LABEL[sel.garment_type]} supports ${pretty(allowed[head])} ${what} only.` });
    }
  });
  if (sel.sleeve_style) {
    const want = sel.sleeve_length === 'sleeveless' ? 'none' : 'regular-sleeve';
    if (sel.sleeve_style !== want) {
      const opt = supportOf('sleeve_style', sel.sleeve_style);
      out.push({ head: 'sleeve_style', value: sel.sleeve_style, label: opt ? opt.label : sel.sleeve_style,
        note: `Outside the supported scope: only '${want}' sleeve style is supported with this sleeve length.` });
    }
  }
  return out;
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
