import { useState, useEffect, useRef } from 'react';
import { useLocation } from 'react-router-dom';
import { measurementsAPI } from '../services/api';
import LoadingSpinner from '../components/LoadingSpinner';
import {
  MEASUREMENT_FIELDS, FIELD_KEYS, DESIGN_KEYS, validateMeasurements, parseFieldErrors, buildPayload, storedEntries, canonicalCm,
} from '../utils/measurementSchema';
import { GUIDES, MISTAKES } from '../utils/measurementGuides';
import { friendlyError } from '../utils/friendlyError';
import MeasureFigure from '../components/MeasureFigure';
import MeasurementFields from '../components/MeasurementFields';

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
  const [serverWarnings, setServerWarnings] = useState([]);
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
    // a design value that was emptied goes back to its calculated value
    const cleared = DESIGN_KEYS.filter((k) => formData[k] === '' || formData[k] === null || formData[k] === undefined);
    try {
      let res;
      if (selectedProfileId) {
        res = await measurementsAPI.update(selectedProfileId, { ...payload, clear: cleared });
        setSuccess('Measurements updated.');
      } else {
        res = await measurementsAPI.save(payload);
        if (res.data?.measurement_id) setSelectedProfileId(res.data.measurement_id);
        setSuccess('New measurement profile saved.');
      }
      setServerWarnings(res?.data?.warnings || []);
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

  if (loading) return <LoadingSpinner message="Loading measurement profiles..." />;

  const activeDef = MEASUREMENT_FIELDS.find((f) => f.key === activeField);
  const missing = MEASUREMENT_FIELDS.filter((f) => f.kind === 'measurement' && (formData[f.key] === '' || formData[f.key] === null)).length;
  const cmValues = canonicalCm(formData, typedUnits);

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

          </div>

          <MeasurementFields idPrefix="profile" keys={FIELD_KEYS} required={[]} values={formData} units={typedUnits} unit={unit}
                             errors={fieldErrors} active={activeField} onActive={setActiveField} onChange={setField}
                             errorTestId={(k) => `profile-error-${k}`} guideTestId={(k) => `profile-guide-${k}`}
                             inputRefs={inputs} serverWarnings={serverWarnings} />

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(150px, 100%), 1fr))', gap: '14px 18px' }}>
            <div className="form-field">
              <label className="form-label" htmlFor="profile-fabric">Usual fabric construction</label>
              <select id="profile-fabric" className="form-select" value={formData.fabric_type} onChange={(e) => setField('fabric_type', e.target.value)}>
                <option value="woven">Woven (no stretch)</option>
                <option value="knit">Knit (moderate stretch)</option>
              </select>
            </div>
          </div>

          <p style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '14px' }}>Every value must be a number greater than 0; decimals are fine. Inches are converted exactly (1 in = 2.54 cm). An unusual value is never refused: it only shows a &quot;please check&quot; note.</p>
          <div style={{ display: 'flex', gap: '12px', justifyContent: 'flex-end', marginTop: '16px', borderTop: '1px solid var(--border)', paddingTop: '16px' }}>
            <button type="button" className="btn btn-outline" onClick={reset}>Reset</button>
            <button type="submit" className="btn btn-primary">Save measurements</button>
          </div>
        </form>

        <div className="ui-card" style={{ padding: 'clamp(14px, 4vw, 24px)', minWidth: 0, display: 'flex', flexDirection: 'column', gap: '20px', position: 'sticky', top: 0 }}>
          <h2 style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)', margin: 0, borderBottom: '1px solid var(--border)', paddingBottom: '12px' }}>
            How to measure
          </h2>
          <MeasureFigure active={activeField} sleeveCm={cmValues.sleeve_cm} />
          <div style={{ background: 'var(--surface-2)', padding: '14px 16px', borderRadius: '8px', border: '1px solid var(--border)' }} data-testid="measure-guide">
            <span style={{ fontSize: '11px', fontWeight: 'bold', color: 'var(--text-accent)', display: 'block', textTransform: 'uppercase', marginBottom: '4px' }}>
              {activeDef?.label}
            </span>
            <p style={{ margin: 0, fontSize: '12px', color: 'var(--text-secondary)', lineHeight: 1.45 }}>{GUIDES[activeField]}</p>
            <p style={{ margin: '6px 0 0', fontSize: '12px', color: 'var(--text-secondary)', lineHeight: 1.45 }}>
              <strong>Common mistake:</strong> {MISTAKES[activeField]}
            </p>
          </div>
          <p style={{ margin: 0, fontSize: '11px', color: 'var(--text-muted)' }}>
            Select a measurement to see where it is taken on the front or back view. The drawing is a guide, not a body model.
          </p>
        </div>
      </div>
    </div>
  );
}
