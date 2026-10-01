import { useState, useEffect, useRef } from 'react';
import { useLocation } from 'react-router-dom';
import { measurementsAPI } from '../services/api';
import LoadingSpinner from '../components/LoadingSpinner';
import {
  MEASUREMENT_FIELDS, FIELD_KEYS, validateMeasurements, displayValue, parseFieldErrors, buildPayload, storedEntries,
} from '../utils/measurementSchema';
import { GUIDES } from '../utils/measurementGuides';
import { friendlyError } from '../utils/friendlyError';

// Positions on the body diagram (only for the measurements it can show).
const DIAGRAM = {
  bust_cm: { n: 1, line: [28, 56, 72, 56], dot: [28, 56] },
  waist_cm: { n: 2, line: [34, 78, 66, 78], dot: [34, 78] },
  hip_cm: { n: 3, line: [30, 98, 70, 98], dot: [30, 98] },
  shoulder_cm: { n: 4, line: [54, 25, 63, 28], dot: [63, 28] },
  neck_cm: { n: 5, ellipse: [50, 25, 5, 2.5], dot: [50, 23] },
  armhole_depth_cm: { n: 6, line: [36, 28, 36, 56], dot: [36, 42] },
  sleeve_cm: { n: 7, path: 'M 63 28 C 65 35, 68 45, 68 55 C 68 62, 67 66, 65 72', dot: [68, 55] },
  garment_length_cm: { n: 8, line: [45, 28, 45, 92], dot: [45, 92] },
};

const EMPTY = { client_name: '', fabric_type: 'woven', ...Object.fromEntries(FIELD_KEYS.map((k) => [k, ''])) };

const fromProfile = (p) => ({
  client_name: p.client_name || '',
  fabric_type: p.fabric_type || 'woven',
  ...storedEntries(p).values,
});

export default function Measurements() {
  const location = useLocation();
  const [profiles, setProfiles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');
  const [selectedProfileId, setSelectedProfileId] = useState('');
  const [unit, setUnit] = useState('cm');
  const [activeField, setActiveField] = useState('bust_cm');
  const [formData, setFormData] = useState(EMPTY);
  const [typedUnits, setTypedUnits] = useState({});     // unit each value was typed in (stored values: cm)
  const [fieldErrors, setFieldErrors] = useState({});
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const inputs = useRef({});

  const loadProfile = (p) => {
    setFormData(p ? fromProfile(p) : EMPTY);
    setTypedUnits(p ? storedEntries(p).units : {});   // each value keeps the unit it was entered in
    setUnit('cm');
    setFieldErrors({});
    setError('');
  };

  useEffect(() => {
    measurementsAPI.getAll()
      .then((res) => {
        const list = res.data.measurements || [];
        setProfiles(list);
        const wanted = location.state?.profile;
        const first = wanted || list[0];
        if (first) {
          setSelectedProfileId(first.measurement_id);
          loadProfile(first);
        }
      })
      .catch(() => setLoadError('The saved measurement profiles could not be loaded. Please refresh and try again.'))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const selectProfile = (id) => {
    setSelectedProfileId(id);
    loadProfile(profiles.find((p) => p.measurement_id === id));
  };

  const setField = (key, value) => {
    setFormData((prev) => ({ ...prev, [key]: value }));
    if (FIELD_KEYS.includes(key)) setTypedUnits((prev) => ({ ...prev, [key]: unit }));
    setFieldErrors((prev) => {
      if (!prev[key]) return prev;
      const { [key]: _removed, ...rest } = prev;
      return rest;
    });
    setError('');
  };

  // the unit only changes how values are shown; typed values keep their own unit (no double conversion)
  const toggleUnit = (next) => {
    if (next === unit) return;
    setUnit(next);
    setFieldErrors({});
  };

  const handleSave = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess('');
    if (!formData.client_name.trim()) {
      setError('Please enter the customer name.');
      return;
    }
    // No measurement is required to keep a profile: which ones a pattern needs depends on the design, and the
    // pattern wizard asks for exactly those. Every entered value must be a number > 0 (server re-validates).
    const localErrors = validateMeasurements(formData, []);
    if (Object.keys(localErrors).length) {
      setFieldErrors(localErrors);
      setError('Please correct the highlighted measurements.');
      return;
    }
    const payload = { client_name: formData.client_name.trim(), ...buildPayload(formData, typedUnits, 'cm'), fabric_type: formData.fabric_type };
    try {
      if (selectedProfileId) {
        await measurementsAPI.update(selectedProfileId, payload);
        setSuccess('Measurements updated.');
      } else {
        const res = await measurementsAPI.save(payload);
        if (res.data?.measurement_id) setSelectedProfileId(res.data.measurement_id);
        setSuccess('New measurement profile saved.');
      }
      try {
        const updated = await measurementsAPI.getAll();
        setProfiles(updated.data.measurements || []);
      } catch {
        // the save itself succeeded; the list is refreshed the next time the page opens
      }
      setTimeout(() => setSuccess(''), 3000);
    } catch (err) {
      const parsed = parseFieldErrors(err);
      if (parsed._form) {
        setError(friendlyError(err, parsed._form));
      } else {
        setFieldErrors(parsed);
        setError('Please correct the highlighted measurements.');
      }
    }
  };

  const reset = () => (selectedProfileId ? selectProfile(selectedProfileId) : loadProfile(null));

  const focusField = (key) => {
    setActiveField(key);
    inputs.current[key]?.focus();
  };

  if (loading) return <LoadingSpinner message="Loading measurement profiles..." />;

  const activeDef = MEASUREMENT_FIELDS.find((f) => f.key === activeField);
  const missing = MEASUREMENT_FIELDS.filter((f) => formData[f.key] === '' || formData[f.key] === null).length;

  return (
    <div style={{ padding: 'clamp(12px, 3vw, 24px)', maxWidth: '1400px', margin: '0 auto' }}>
      <div style={{ marginBottom: '24px' }}>
        <h1 style={{ fontSize: '22px', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '4px' }}>Body measurements</h1>
        <p style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>
          Create or update a customer&apos;s measurement profile. Which measurements a pattern needs depends on the design
          (for example, a sleeveless top needs no sleeve measurements); the pattern wizard asks for exactly those.
        </p>
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'var(--surface-1)', border: '1px solid var(--border)', borderRadius: '12px', padding: '16px', marginBottom: '24px', gap: '16px', flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flex: 1, maxWidth: '460px' }}>
          <label htmlFor="profile-select" style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)', whiteSpace: 'nowrap' }}>Profile</label>
          <select id="profile-select" className="form-select" value={selectedProfileId} onChange={(e) => selectProfile(e.target.value)}>
            <option value="">+ New customer profile</option>
            {profiles.map((p) => (
              <option key={p.measurement_id} value={p.measurement_id}>
                {p.client_name}
              </option>
            ))}
          </select>
        </div>
        <div role="group" aria-label="Measurement unit" style={{ display: 'flex', gap: '6px' }}>
          {['cm', 'in'].map((u) => (
            <button key={u} type="button" aria-pressed={unit === u} data-testid={`page-unit-${u}`}
                    className={unit === u ? 'btn btn-primary' : 'btn btn-outline'} onClick={() => toggleUnit(u)}>{u}</button>
          ))}
        </div>
      </div>

      {loadError && <div role="alert" className="dashboard-error" style={{ marginBottom: '20px', color: 'var(--danger)' }}>{loadError}</div>}
      {error && (
        <div role="alert" style={{ padding: '12px 16px', background: '#FEF2F2', border: '1px solid #FCA5A5', borderRadius: '8px', color: '#991B1B', fontSize: '13px', marginBottom: '20px' }}>{error}</div>
      )}
      {success && (
        <div role="status" style={{ padding: '12px 16px', background: 'rgba(21, 128, 61, 0.1)', border: '1px solid var(--text-accent)', borderRadius: '8px', color: 'var(--text-accent)', fontSize: '13px', marginBottom: '20px' }}>{success}</div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(340px, 100%), 1fr))', gap: '24px', alignItems: 'start' }}>
        <form className="ui-card" style={{ padding: 'clamp(14px, 4vw, 24px)', minWidth: 0 }} onSubmit={handleSave} noValidate>
          <h2 style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '18px', borderBottom: '1px solid var(--border)', paddingBottom: '12px' }}>
            Measurement details {missing > 0 && <small style={{ fontWeight: 400, color: 'var(--text-muted)' }}>· {missing} not measured yet</small>}
          </h2>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(150px, 100%), 1fr))', gap: '14px 18px' }}>
            <div className="form-field" style={{ gridColumn: '1 / -1' }}>
              <label className="form-label" htmlFor="profile-name">Customer name</label>
              <input id="profile-name" type="text" className="form-input" value={formData.client_name}
                     onChange={(e) => setField('client_name', e.target.value)} placeholder="e.g. Amara Silva" />
            </div>

            {MEASUREMENT_FIELDS.map((field) => {
              const key = field.key;
              const message = fieldErrors[key];
              return (
                <div key={key} className="form-field" onMouseEnter={() => setActiveField(key)}
                     style={{ borderLeft: `3px solid ${activeField === key ? 'var(--text-accent)' : 'transparent'}`, paddingLeft: '8px' }}>
                  <label className="form-label" htmlFor={`profile-${key}`}>
                    {DIAGRAM[key] ? `${DIAGRAM[key].n}. ` : ''}{field.label} ({unit})
                  </label>
                  <input
                    id={`profile-${key}`} ref={(el) => { inputs.current[key] = el; }}
                    type="text" inputMode="decimal" autoComplete="off" className="form-input"
                    value={displayValue(formData[key], typedUnits[key] || 'cm', unit)} aria-invalid={message ? 'true' : 'false'}
                    style={message ? { borderColor: '#B23B3B' } : undefined}
                    onFocus={() => setActiveField(key)} onChange={(e) => setField(key, e.target.value)}
                  />
                  {message && <div role="alert" data-testid={`profile-error-${key}`} style={{ color: '#9B2C2C', fontSize: '12px' }}>{message}</div>}
                </div>
              );
            })}

            <div className="form-field">
              <label className="form-label" htmlFor="profile-fabric">Usual fabric construction</label>
              <select id="profile-fabric" className="form-select" value={formData.fabric_type} onChange={(e) => setField('fabric_type', e.target.value)}>
                <option value="woven">Woven (no stretch)</option>
                <option value="knit">Knit (moderate stretch)</option>
              </select>
            </div>
          </div>

          <p style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '14px' }}>Every value must be a number greater than 0; decimals are fine. Inches are converted exactly (1 in = 2.54 cm).</p>
          <div style={{ display: 'flex', gap: '12px', justifyContent: 'flex-end', marginTop: '16px', borderTop: '1px solid var(--border)', paddingTop: '16px' }}>
            <button type="button" className="btn btn-outline" onClick={reset}>Reset</button>
            <button type="submit" className="btn btn-primary">Save measurements</button>
          </div>
        </form>

        <div className="ui-card" style={{ padding: 'clamp(14px, 4vw, 24px)', minWidth: 0, display: 'flex', flexDirection: 'column', gap: '20px', position: 'sticky', top: 0 }}>
          <h2 style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)', margin: 0, borderBottom: '1px solid var(--border)', paddingBottom: '12px' }}>
            How to measure
          </h2>
          <div style={{ width: '100%', height: '340px', background: 'radial-gradient(circle at center, #1C2E24 0%, #111111 100%)', borderRadius: '12px', display: 'flex', alignItems: 'center', justifyContent: 'center', overflow: 'hidden' }}>
            <svg viewBox="0 0 100 200" style={{ width: '100%', height: '92%' }} role="img" aria-label="Body diagram with numbered measurement positions">
              <path d="M 50 15 C 53 15, 54 22, 54 24 C 54 24, 62 26, 64 28 C 66 30, 68 44, 68 55 C 68 62, 65 65, 63 68 C 61 70, 58 74, 58 84 C 58 94, 61 104, 62 110 C 63 116, 61 125, 59 135 L 59 190 L 52 190 L 51 145 L 49 145 L 48 190 L 41 190 L 41 135 C 39 125, 37 116, 38 110 C 39 104, 42 94, 42 84 C 42 74, 39 70, 37 68 C 35 65, 32 62, 32 55 C 32 44, 34 30, 36 28 C 38 26, 46 24, 46 24 C 46 22, 47 15, 50 15 Z"
                    fill="none" stroke="#6B7280" strokeWidth="1.2" />
              <circle cx="50" cy="18" r="4.5" fill="none" stroke="#6B7280" strokeWidth="1.2" />
              {Object.entries(DIAGRAM).map(([key, d]) => {
                const on = activeField === key;
                const stroke = on ? '#7fd1a8' : '#4B5563';
                return (
                  <g key={key} style={{ cursor: 'pointer' }} onClick={() => focusField(key)}>
                    {d.line && <line x1={d.line[0]} y1={d.line[1]} x2={d.line[2]} y2={d.line[3]} stroke={stroke} strokeWidth={on ? 2 : 1} />}
                    {d.ellipse && <ellipse cx={d.ellipse[0]} cy={d.ellipse[1]} rx={d.ellipse[2]} ry={d.ellipse[3]} fill="none" stroke={stroke} strokeWidth={on ? 2 : 1} />}
                    {d.path && <path d={d.path} fill="none" stroke={stroke} strokeWidth={on ? 2 : 1} />}
                    <circle cx={d.dot[0]} cy={d.dot[1]} r={on ? 5 : 4} fill={on ? '#2d7a55' : '#374151'} />
                    <text x={d.dot[0]} y={d.dot[1] + 3} fill="#FFF" fontSize="8" textAnchor="middle" fontWeight="bold">{d.n}</text>
                  </g>
                );
              })}
            </svg>
          </div>
          <div style={{ background: 'var(--surface-2)', padding: '14px 16px', borderRadius: '8px', border: '1px solid var(--border)' }} data-testid="measure-guide">
            <span style={{ fontSize: '11px', fontWeight: 'bold', color: 'var(--text-accent)', display: 'block', textTransform: 'uppercase', marginBottom: '4px' }}>
              {DIAGRAM[activeField] ? `${DIAGRAM[activeField].n}. ` : ''}{activeDef?.label}
            </span>
            <p style={{ margin: 0, fontSize: '12px', color: 'var(--text-secondary)', lineHeight: 1.45 }}>{GUIDES[activeField]}</p>
          </div>
        </div>
      </div>
    </div>
  );
}
