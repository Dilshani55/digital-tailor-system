// The measurement inputs, grouped (body / arm and sleeve / neckline), shared by the Measurements page and the
// pattern wizard. Every field has a plain-English name, a "how to measure" card with a common mistake, and the
// unit next to the input. Design values (neckline width, neck depths, armhole depth, bust-point distance) are
// optional: left empty, the value the drafting method calculates is used and shown as "calculated".
// `conditional` = measurements that are not required yet but will be when the design uses them (hip, sleeve ...).
import { Info } from 'lucide-react';
import {
  MEASUREMENT_FIELDS, GROUPS, CM_PER_INCH, displayValue, calculatedValues, canonicalCm, softWarnings,
} from '../utils/measurementSchema';

const show = (cm, unit) => `${Number((unit === 'in' ? cm / CM_PER_INCH : cm).toFixed(unit === 'in' ? 2 : 1))} ${unit}`;

export default function MeasurementFields({
  idPrefix, keys, required = [], conditional = [], values, units = {}, unit, errors = {}, active, onActive, onChange,
  errorTestId = (k) => `error-${k}`, guideTestId = (k) => `guide-${k}`, inputRefs = null, serverWarnings = [],
}) {
  const cm = canonicalCm(values, units);
  const calculated = calculatedValues(cm);
  const warnings = Object.fromEntries([...softWarnings(cm), ...serverWarnings].map((w) => [w.field, w.message]));
  const fields = MEASUREMENT_FIELDS.filter((f) => keys.includes(f.key));

  return (
    <div className="meas-groups">
      {GROUPS.filter((g) => fields.some((f) => f.group === g.key)).map((group) => (
        <fieldset key={group.key} className="meas-group" data-testid={`meas-group-${group.key}`}
                  style={{ border: 0, padding: 0, margin: '0 0 18px', minWidth: 0 }}>
          <legend className="form-label" style={{ fontSize: 13, fontWeight: 700, marginBottom: 8 }}>{group.label}</legend>
          <div className="meas-grid">
            {fields.filter((f) => f.group === group.key).map((field) => {
              const key = field.key;
              const message = errors[key];
              const isActive = active === key;
              const optional = !required.includes(key);
              const empty = values[key] === '' || values[key] === null || values[key] === undefined;
              return (
                <div className={`meas-field${isActive ? ' active' : ''}`} key={key} data-kind={field.kind}>
                  <label className="form-label" htmlFor={`${idPrefix}-${key}`}>
                    {field.label}<span className="sr-only"> ({unit})</span>
                    {optional && (
                      <small style={{ fontWeight: 400, color: 'var(--text-muted, #6b7280)' }} data-testid={`${idPrefix}-need-${key}`}>
                        {conditional.includes(key) ? ' · needed for some designs' : ' · optional'}
                      </small>
                    )}
                  </label>
                  <div className="input-suffix">
                    <input id={`${idPrefix}-${key}`} className="form-input" type="text" inputMode="decimal" autoComplete="off"
                           ref={inputRefs ? (el) => { inputRefs.current[key] = el; } : undefined}
                           value={displayValue(values[key], units[key] || 'cm', unit)} aria-invalid={message ? 'true' : 'false'}
                           aria-describedby={isActive ? `${idPrefix}-guide-${key}` : undefined}
                           placeholder={field.kind === 'design' && calculated[key] ? `calculated ${show(calculated[key], unit)}` : undefined}
                           style={message ? { borderColor: '#B23B3B' } : undefined}
                           onFocus={() => onActive(key)} onChange={(e) => onChange(key, e.target.value)} />
                    <span aria-hidden="true">{unit}</span>
                    <button type="button" className="info-btn" aria-label={`How to measure ${field.label}`}
                            aria-expanded={isActive} onClick={() => onActive(key)}
                            style={{ border: 0, background: 'none', cursor: 'pointer', padding: '0 4px', color: 'var(--text-accent, #2c5b45)' }}>
                      <Info size={15} aria-hidden="true" />
                    </button>
                  </div>
                  {field.kind === 'design' && empty && calculated[key] && (
                    <small className="form-hint" data-testid={`calculated-${key}`}>
                      Calculated value: {show(calculated[key], unit)} (used when this is left empty)
                    </small>
                  )}
                  {isActive && (
                    <div id={`${idPrefix}-guide-${key}`} className="form-hint meas-guide" data-testid={guideTestId(key)}
                         style={{ background: 'var(--surface-2, #f4f6f4)', border: '1px solid var(--border, #dfe5e0)', borderRadius: 8, padding: '8px 10px', marginTop: 6 }}>
                      <strong style={{ display: 'block', marginBottom: 2 }}>How to measure</strong>
                      {field.guide}
                      <span style={{ display: 'block', marginTop: 4 }}><strong>Common mistake:</strong> {field.mistake}</span>
                    </div>
                  )}
                  {message && <div role="alert" className="field-error" data-testid={errorTestId(key)}>{message}</div>}
                  {!message && warnings[key] && (
                    <div role="status" className="form-hint" data-testid={`warning-${key}`} style={{ color: '#92400e' }}>
                      Please check: {warnings[key]}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </fieldset>
      ))}
    </div>
  );
}
