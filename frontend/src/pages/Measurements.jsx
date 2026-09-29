import { useState, useEffect, useRef } from 'react';
import { useLocation } from 'react-router-dom';
import { measurementsAPI } from '../services/api';
import LoadingSpinner from '../components/LoadingSpinner';
import { validateMeasurements, parseFieldErrors, buildPayload, CORE_FIELDS } from '../utils/measurementSchema';

// The form's armhole field is keyed armhole_cm; the API field is armhole_depth_cm.
const toApiValues = (form) => ({ ...form, armhole_depth_cm: form.armhole_cm });

export default function Measurements() {
  const location = useLocation();
  const [profiles, setProfiles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedProfileId, setSelectedProfileId] = useState('');
  const [unit, setUnit] = useState('cm'); // cm / in
  const [activeField, setActiveField] = useState('bust_cm');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  // 8 Measurement Input Fields state
  // No prefilled example numbers: an empty field means "not measured", never a default.
  const [formData, setFormData] = useState({
    client_name: '',
    bust_cm: '',
    waist_cm: '',
    hip_cm: '',
    height_cm: '',
    shoulder_cm: '',
    neck_cm: '',
    armhole_cm: '',
    sleeve_cm: '',
    garment_length_cm: '',
    fabric_type: 'woven'
  });

  const refs = {
    bust_cm: useRef(null),
    waist_cm: useRef(null),
    hip_cm: useRef(null),
    shoulder_cm: useRef(null),
    neck_cm: useRef(null),
    armhole_cm: useRef(null),
    sleeve_cm: useRef(null),
    garment_length_cm: useRef(null)
  };

  const fetchCustomers = async () => {
    setLoading(true);
    try {
      const res = await measurementsAPI.getAll();
      const list = res.data.measurements || [];
      setProfiles(list);

      // Check if location state passed a profile to edit
      if (location.state?.profile) {
        const p = location.state.profile;
        setSelectedProfileId(p.measurement_id);
        loadProfileData(p);
      } else if (list.length > 0) {
        setSelectedProfileId(list[0].measurement_id);
        loadProfileData(list[0]);
      }
    } catch (err) {
      setError('Failed to fetch customers directory.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCustomers();
  }, []);

  const loadProfileData = (profile) => {
    setFormData({
      client_name: profile.client_name || 'Customer Profile',
      bust_cm: profile.bust_cm ?? '',
      waist_cm: profile.waist_cm ?? '',
      hip_cm: profile.hip_cm ?? '',
      height_cm: profile.height_cm ?? '',
      shoulder_cm: profile.shoulder_cm ?? '',
      neck_cm: profile.neck_cm ?? '',
      armhole_cm: profile.armhole_depth_cm ?? profile.armhole_cm ?? '',
      sleeve_cm: profile.sleeve_cm ?? '',
      garment_length_cm: profile.garment_length_cm ?? '',
      fabric_type: profile.fabric_type || 'woven'
    });
    setUnit('cm');   // stored profile values are canonical cm
  };

  const handleCustomerChange = (e) => {
    const id = e.target.value;
    setSelectedProfileId(id);
    const found = profiles.find(p => p.measurement_id === id);
    if (found) {
      loadProfileData(found);
    }
  };

  const handleInputChange = (field, val) => {
    setFormData(prev => ({
      ...prev,
      [field]: val === '' ? '' : parseFloat(val) || val
    }));
  };

  const handleUnitToggle = (newUnit) => {
    if (newUnit === unit) return;
    const factor = newUnit === 'in' ? 1 / 2.54 : 2.54;
    
    // Convert current numerical inputs
    const fieldsToConvert = [
      'bust_cm', 'waist_cm', 'hip_cm', 'height_cm', 
      'shoulder_cm', 'neck_cm', 'armhole_cm', 'sleeve_cm', 'garment_length_cm'
    ];
    
    const updated = { ...formData };
    fieldsToConvert.forEach(f => {
      if (updated[f]) {
        updated[f] = parseFloat((updated[f] * factor).toFixed(2));
      }
    });
    
    setFormData(updated);
    setUnit(newUnit);
  };

  const handleSave = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess('');

    // Validate what was typed (in the selected unit). Only the core four are required for a
    // profile; the server converts inches to canonical cm and re-validates everything.
    const localErrors = validateMeasurements(toApiValues(formData), unit, CORE_FIELDS);
    if (Object.keys(localErrors).length > 0) {
      setError(Object.values(localErrors).join(' '));
      return;
    }
    const payload = {
      client_name: formData.client_name,
      ...buildPayload(toApiValues(formData), unit),   // entered values only, in the selected unit
      fabric_type: formData.fabric_type,
    };

    try {
      if (selectedProfileId) {
        await measurementsAPI.update(selectedProfileId, payload);
        setSuccess('Measurements updated successfully!');
      } else {
        const res = await measurementsAPI.save(payload);
        setSuccess('New profile measurements saved successfully!');
        if (res.data?.measurement_id) {
          setSelectedProfileId(res.data.measurement_id);
        }
      }
      setTimeout(() => setSuccess(''), 3000);
      const updatedList = await measurementsAPI.getAll();
      setProfiles(updatedList.data.measurements || []);
    } catch (err) {
      const parsed = parseFieldErrors(err);
      setError(Object.values(parsed).join(' '));
    }
  };

  const handleReset = () => {
    if (selectedProfileId) {
      const found = profiles.find(p => p.measurement_id === selectedProfileId);
      if (found) loadProfileData(found);
    } else {
      setFormData({
        client_name: '',
        bust_cm: '',
        waist_cm: '',
        hip_cm: '',
        height_cm: '',
        shoulder_cm: '',
        neck_cm: '',
        armhole_cm: '',
        sleeve_cm: '',
        garment_length_cm: '',
        fabric_type: 'woven'
      });
    }
  };

  const focusInput = (field) => {
    setActiveField(field);
    refs[field]?.current?.focus();
  };

  // Human body guides for instructions
  const guides = {
    bust_cm: { title: 'Bust Circumference', desc: 'Measure around the fullest part of the chest horizontally, keeping the tape parallel to the floor.', number: 1 },
    waist_cm: { title: 'Waist Circumference', desc: 'Measure around the natural waist circumference line, narrowest area above your belly button.', number: 2 },
    hip_cm: { title: 'Hip Circumference', desc: 'Measure around the maximum projection points of the hips and seat with feet close together.', number: 3 },
    shoulder_cm: { title: 'Shoulder width', desc: 'Measure back shoulder tip to tip across the curvature of the neck base.', number: 4 },
    neck_cm: { title: 'Neck Circumference', desc: 'Measure around the neck collar seam point at the base of the throat.', number: 5 },
    armhole_cm: { title: 'Armhole Depth', desc: 'Measure vertically from top shoulder point down to the underarm pit line.', number: 6 },
    sleeve_cm: { title: 'Sleeve Length', desc: 'Measure shoulder tip down the side of the arm over the elbow crease to wrist.', number: 7 },
    garment_length_cm: { title: 'Garment Length', desc: 'Draft length from shoulder neck junction down to hemline boundary.', number: 8 }
  };

  if (loading) return <LoadingSpinner message="Loading measurements workspace..." />;

  return (
    <div style={{ padding: '24px', maxWidth: '1400px', margin: '0 auto' }}>
      
      {/* Header Info */}
      <div style={{ marginBottom: '24px' }}>
        <h1 style={{ fontSize: '22px', fontWeight: '700', color: 'var(--text-primary)', marginBottom: '4px' }}>
          Body measurements
        </h1>
        <p style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>
          Enter or update customer body measurements.
        </p>
      </div>

      {/* Select Customer / Unit Selector controls */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'var(--surface-1)', border: '1px solid var(--border)', borderRadius: '12px', padding: '16px', marginBottom: '24px', gap: '16px', flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flex: 1, maxWidth: '400px' }}>
          <label style={{ fontSize: '12px', fontWeight: '600', color: 'var(--text-secondary)', whiteSpace: 'nowrap' }}>Select customer</label>
          <select 
            className="form-input" 
            style={{ margin: 0, height: '38px', padding: '0 12px' }}
            value={selectedProfileId}
            onChange={handleCustomerChange}
          >
            <option value="">-- Create custom walk-in --</option>
            {profiles.map(p => (
              <option key={p.measurement_id} value={p.measurement_id}>
                {p.client_name} ({p.email || 'No email'})
              </option>
            ))}
          </select>
        </div>

        {/* Toggle units */}
        <div style={{ display: 'flex', background: 'var(--surface-2)', borderRadius: '8px', padding: '4px', border: '1px solid var(--border)' }}>
          <button 
            type="button"
            onClick={() => handleUnitToggle('cm')}
            style={{ 
              border: 'none', background: unit === 'cm' ? 'var(--text-accent)' : 'transparent', 
              color: unit === 'cm' ? '#FFFFFF' : 'var(--text-secondary)',
              padding: '6px 16px', borderRadius: '6px', fontSize: '12px', fontWeight: 'bold', cursor: 'pointer'
            }}
          >
            cm
          </button>
          <button 
            type="button"
            onClick={() => handleUnitToggle('in')}
            style={{ 
              border: 'none', background: unit === 'in' ? 'var(--text-accent)' : 'transparent', 
              color: unit === 'in' ? '#FFFFFF' : 'var(--text-secondary)',
              padding: '6px 16px', borderRadius: '6px', fontSize: '12px', fontWeight: 'bold', cursor: 'pointer'
            }}
          >
            in
          </button>
        </div>
      </div>

      {error && (
        <div style={{ padding: '12px 16px', background: '#7F1D1D', border: '1px solid #991B1B', borderRadius: '8px', color: '#FECACA', fontSize: '13px', marginBottom: '20px' }}>
          {error}
        </div>
      )}
      {success && (
        <div style={{ padding: '12px 16px', background: 'rgba(21, 128, 61, 0.2)', border: '1px solid var(--text-accent)', borderRadius: '8px', color: 'var(--text-accent)', fontSize: '13px', marginBottom: '20px' }}>
          {success}
        </div>
      )}

      {/* Grid container */}
      <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: '24px', alignItems: 'start' }}>
        
        {/* Left Card: Input fields form */}
        <div className="ui-card" style={{ padding: '24px' }}>
          <h2 style={{ fontSize: '14px', fontWeight: '600', color: 'var(--text-primary)', marginBottom: '18px', borderBottom: '1px solid var(--border)', paddingBottom: '12px' }}>
            Measurement details
          </h2>

          <form onSubmit={handleSave} style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px 20px' }}>
            
            {/* Walk-in Client Name (Editable only if no customer selected) */}
            <div style={{ gridColumn: 'span 2', marginBottom: '8px' }}>
              <label className="form-label" style={{ fontSize: '12px' }}>Customer Name</label>
              <input 
                type="text" 
                className="form-input" 
                value={formData.client_name}
                onChange={(e) => handleInputChange('client_name', e.target.value)}
                placeholder="e.g. Walk-in Customer"
                disabled={!!selectedProfileId}
              />
            </div>

            {/* Field 1: Bust */}
            <div 
              style={{ borderLeft: activeField === 'bust_cm' ? '3px solid var(--text-accent)' : '3px solid transparent', paddingLeft: '8px' }}
              onMouseEnter={() => setActiveField('bust_cm')}
            >
              <label className="form-label" style={{ display: 'flex', gap: '6px', fontSize: '12px', fontWeight: 'bold' }}>
                <span style={{ background: 'var(--text-accent)', color: '#FFF', width: '16px', height: '16px', borderRadius: '50%', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', fontSize: '10px' }}>1</span>
                Bust
              </label>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <input 
                  ref={refs.bust_cm}
                  type="number" step="0.1" 
                  className="form-input" style={{ margin: 0 }}
                  value={formData.bust_cm}
                  onChange={(e) => handleInputChange('bust_cm', e.target.value)}
                  onFocus={() => setActiveField('bust_cm')}
                  required
                />
                <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>{unit}</span>
              </div>
            </div>

            {/* Field 2: Waist */}
            <div 
              style={{ borderLeft: activeField === 'waist_cm' ? '3px solid var(--text-accent)' : '3px solid transparent', paddingLeft: '8px' }}
              onMouseEnter={() => setActiveField('waist_cm')}
            >
              <label className="form-label" style={{ display: 'flex', gap: '6px', fontSize: '12px', fontWeight: 'bold' }}>
                <span style={{ background: 'var(--text-accent)', color: '#FFF', width: '16px', height: '16px', borderRadius: '50%', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', fontSize: '10px' }}>2</span>
                Waist
              </label>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <input 
                  ref={refs.waist_cm}
                  type="number" step="0.1" 
                  className="form-input" style={{ margin: 0 }}
                  value={formData.waist_cm}
                  onChange={(e) => handleInputChange('waist_cm', e.target.value)}
                  onFocus={() => setActiveField('waist_cm')}
                  required
                />
                <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>{unit}</span>
              </div>
            </div>

            {/* Field 3: Hip */}
            <div 
              style={{ borderLeft: activeField === 'hip_cm' ? '3px solid var(--text-accent)' : '3px solid transparent', paddingLeft: '8px' }}
              onMouseEnter={() => setActiveField('hip_cm')}
            >
              <label className="form-label" style={{ display: 'flex', gap: '6px', fontSize: '12px', fontWeight: 'bold' }}>
                <span style={{ background: 'var(--text-accent)', color: '#FFF', width: '16px', height: '16px', borderRadius: '50%', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', fontSize: '10px' }}>3</span>
                Hip
              </label>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <input 
                  ref={refs.hip_cm}
                  type="number" step="0.1" 
                  className="form-input" style={{ margin: 0 }}
                  value={formData.hip_cm}
                  onChange={(e) => handleInputChange('hip_cm', e.target.value)}
                  onFocus={() => setActiveField('hip_cm')}
                  required
                />
                <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>{unit}</span>
              </div>
            </div>

            {/* Field 4: Shoulder Width */}
            <div 
              style={{ borderLeft: activeField === 'shoulder_cm' ? '3px solid var(--text-accent)' : '3px solid transparent', paddingLeft: '8px' }}
              onMouseEnter={() => setActiveField('shoulder_cm')}
            >
              <label className="form-label" style={{ display: 'flex', gap: '6px', fontSize: '12px', fontWeight: 'bold' }}>
                <span style={{ background: 'var(--text-accent)', color: '#FFF', width: '16px', height: '16px', borderRadius: '50%', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', fontSize: '10px' }}>4</span>
                Shoulder width
              </label>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <input 
                  ref={refs.shoulder_cm}
                  type="number" step="0.1" 
                  className="form-input" style={{ margin: 0 }}
                  value={formData.shoulder_cm}
                  onChange={(e) => handleInputChange('shoulder_cm', e.target.value)}
                  onFocus={() => setActiveField('shoulder_cm')}
                  required
                />
                <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>{unit}</span>
              </div>
            </div>

            {/* Field 5: Neck circumference */}
            <div 
              style={{ borderLeft: activeField === 'neck_cm' ? '3px solid var(--text-accent)' : '3px solid transparent', paddingLeft: '8px' }}
              onMouseEnter={() => setActiveField('neck_cm')}
            >
              <label className="form-label" style={{ display: 'flex', gap: '6px', fontSize: '12px', fontWeight: 'bold' }}>
                <span style={{ background: 'var(--text-accent)', color: '#FFF', width: '16px', height: '16px', borderRadius: '50%', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', fontSize: '10px' }}>5</span>
                Neck circumference
              </label>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <input 
                  ref={refs.neck_cm}
                  type="number" step="0.1" 
                  className="form-input" style={{ margin: 0 }}
                  value={formData.neck_cm}
                  onChange={(e) => handleInputChange('neck_cm', e.target.value)}
                  onFocus={() => setActiveField('neck_cm')}
                  required
                />
                <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>{unit}</span>
              </div>
            </div>

            {/* Field 6: Armhole depth */}
            <div 
              style={{ borderLeft: activeField === 'armhole_cm' ? '3px solid var(--text-accent)' : '3px solid transparent', paddingLeft: '8px' }}
              onMouseEnter={() => setActiveField('armhole_cm')}
            >
              <label className="form-label" style={{ display: 'flex', gap: '6px', fontSize: '12px', fontWeight: 'bold' }}>
                <span style={{ background: 'var(--text-accent)', color: '#FFF', width: '16px', height: '16px', borderRadius: '50%', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', fontSize: '10px' }}>6</span>
                Armhole depth
              </label>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <input 
                  ref={refs.armhole_cm}
                  type="number" step="0.1" 
                  className="form-input" style={{ margin: 0 }}
                  value={formData.armhole_cm}
                  onChange={(e) => handleInputChange('armhole_cm', e.target.value)}
                  onFocus={() => setActiveField('armhole_cm')}
                  required
                />
                <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>{unit}</span>
              </div>
            </div>

            {/* Field 7: Sleeve length */}
            <div 
              style={{ borderLeft: activeField === 'sleeve_cm' ? '3px solid var(--text-accent)' : '3px solid transparent', paddingLeft: '8px' }}
              onMouseEnter={() => setActiveField('sleeve_cm')}
            >
              <label className="form-label" style={{ display: 'flex', gap: '6px', fontSize: '12px', fontWeight: 'bold' }}>
                <span style={{ background: 'var(--text-accent)', color: '#FFF', width: '16px', height: '16px', borderRadius: '50%', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', fontSize: '10px' }}>7</span>
                Sleeve length
              </label>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <input 
                  ref={refs.sleeve_cm}
                  type="number" step="0.1" 
                  className="form-input" style={{ margin: 0 }}
                  value={formData.sleeve_cm}
                  onChange={(e) => handleInputChange('sleeve_cm', e.target.value)}
                  onFocus={() => setActiveField('sleeve_cm')}
                  required
                />
                <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>{unit}</span>
              </div>
            </div>

            {/* Field 8: Garment length */}
            <div 
              style={{ borderLeft: activeField === 'garment_length_cm' ? '3px solid var(--text-accent)' : '3px solid transparent', paddingLeft: '8px' }}
              onMouseEnter={() => setActiveField('garment_length_cm')}
            >
              <label className="form-label" style={{ display: 'flex', gap: '6px', fontSize: '12px', fontWeight: 'bold' }}>
                <span style={{ background: 'var(--text-accent)', color: '#FFF', width: '16px', height: '16px', borderRadius: '50%', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', fontSize: '10px' }}>8</span>
                Garment length
              </label>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <input 
                  ref={refs.garment_length_cm}
                  type="number" step="0.1" 
                  className="form-input" style={{ margin: 0 }}
                  value={formData.garment_length_cm}
                  onChange={(e) => handleInputChange('garment_length_cm', e.target.value)}
                  onFocus={() => setActiveField('garment_length_cm')}
                  required
                />
                <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>{unit}</span>
              </div>
            </div>

            {/* Height (validation only; not used by the drafting equations) */}
            <div style={{ gridColumn: 'span 2', marginTop: '8px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', background: 'var(--surface-2)', padding: '10px 14px', borderRadius: '8px', border: '1px solid var(--border)' }}>
              <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>Baseline Proportional Height:</span>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <input 
                  type="number" step="0.1" 
                  className="form-input" style={{ width: '80px', height: '28px', padding: '0 8px', margin: 0 }}
                  value={formData.height_cm}
                  onChange={(e) => handleInputChange('height_cm', e.target.value)}
                />
                <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>{unit}</span>
              </div>
            </div>

            {/* Actions */}
            <div style={{ gridColumn: 'span 2', display: 'flex', gap: '12px', justifyContent: 'flex-end', marginTop: '16px', borderTop: '1px solid var(--border)', paddingTop: '16px' }}>
              <button type="button" className="btn btn-outline animate-all" onClick={handleReset} style={{ height: '40px' }}>
                Reset
              </button>
              <button type="submit" className="btn btn-primary animate-all" style={{ height: '40px', background: 'var(--text-accent)' }}>
                Save measurements
              </button>
            </div>

          </form>
        </div>

        {/* Right Card: Interactive Measurement Guide Vector */}
        <div className="ui-card" style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '20px' }}>
          <h2 style={{ fontSize: '14px', fontWeight: '600', color: 'var(--text-primary)', margin: 0, borderBottom: '1px solid var(--border)', paddingBottom: '12px' }}>
            Measurement guide
          </h2>

          {/* High-fidelity Vector Model Box */}
          <div style={{ position: 'relative', width: '100%', height: '360px', background: 'radial-gradient(circle at center, #1C2E24 0%, #111111 100%)', borderRadius: '12px', border: '1px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'center', overflow: 'hidden' }}>
            
            {/* Outline Body Vector Drawing */}
            <svg viewBox="0 0 100 200" style={{ width: '100%', height: '90%', filter: 'drop-shadow(0 4px 8px rgba(0,0,0,0.5))' }}>
              {/* Human contour (Simplified schematic) */}
              <path 
                d="M 50 15 C 53 15, 54 22, 54 24 C 54 24, 62 26, 64 28 C 66 30, 68 44, 68 55 C 68 62, 65 65, 63 68 C 61 70, 58 74, 58 84 C 58 94, 61 104, 62 110 C 63 116, 61 125, 59 135 L 59 190 L 52 190 L 51 145 L 49 145 L 48 190 L 41 190 L 41 135 C 39 125, 37 116, 38 110 C 39 104, 42 94, 42 84 C 42 74, 39 70, 37 68 C 35 65, 32 62, 32 55 C 32 44, 34 30, 36 28 C 38 26, 46 24, 46 24 C 46 22, 47 15, 50 15 Z" 
                fill="none" 
                stroke="#6B7280" 
                strokeWidth="1.2" 
              />
              {/* Head outline */}
              <circle cx="50" cy="18" r="4.5" fill="none" stroke="#6B7280" strokeWidth="1.2" />

              {/* Numbered Dots overlaying coordinates */}
              {/* Dot 1: Bust line */}
              <g style={{ cursor: 'pointer' }} onClick={() => focusInput('bust_cm')}>
                <line x1="28" y1="56" x2="72" y2="56" stroke={activeField === 'bust_cm' ? 'var(--text-accent)' : '#4B5563'} strokeWidth={activeField === 'bust_cm' ? '2' : '1'} />
                <circle cx="28" cy="56" r={activeField === 'bust_cm' ? '5' : '4'} fill={activeField === 'bust_cm' ? 'var(--text-accent)' : '#374151'} stroke="var(--border)" strokeWidth="1" />
                <text x="28" y="59" fill="#FFF" fontSize="8" textAnchor="middle" fontWeight="bold">1</text>
              </g>

              {/* Dot 2: Waist line */}
              <g style={{ cursor: 'pointer' }} onClick={() => focusInput('waist_cm')}>
                <line x1="34" y1="78" x2="66" y2="78" stroke={activeField === 'waist_cm' ? 'var(--text-accent)' : '#4B5563'} strokeWidth={activeField === 'waist_cm' ? '2' : '1'} />
                <circle cx="34" cy="78" r={activeField === 'waist_cm' ? '5' : '4'} fill={activeField === 'waist_cm' ? 'var(--text-accent)' : '#374151'} stroke="var(--border)" strokeWidth="1" />
                <text x="34" y="81" fill="#FFF" fontSize="8" textAnchor="middle" fontWeight="bold">2</text>
              </g>

              {/* Dot 3: Hip line */}
              <g style={{ cursor: 'pointer' }} onClick={() => focusInput('hip_cm')}>
                <line x1="30" y1="98" x2="70" y2="98" stroke={activeField === 'hip_cm' ? 'var(--text-accent)' : '#4B5563'} strokeWidth={activeField === 'hip_cm' ? '2' : '1'} />
                <circle cx="30" cy="98" r={activeField === 'hip_cm' ? '5' : '4'} fill={activeField === 'hip_cm' ? 'var(--text-accent)' : '#374151'} stroke="var(--border)" strokeWidth="1" />
                <text x="30" y="101" fill="#FFF" fontSize="8" textAnchor="middle" fontWeight="bold">3</text>
              </g>

              {/* Dot 4: Shoulder width */}
              <g style={{ cursor: 'pointer' }} onClick={() => focusInput('shoulder_cm')}>
                <line x1="37" y1="28" x2="63" y2="28" stroke={activeField === 'shoulder_cm' ? 'var(--text-accent)' : '#4B5563'} strokeWidth={activeField === 'shoulder_cm' ? '2' : '1'} />
                <circle cx="63" cy="28" r={activeField === 'shoulder_cm' ? '5' : '4'} fill={activeField === 'shoulder_cm' ? 'var(--text-accent)' : '#374151'} stroke="var(--border)" strokeWidth="1" />
                <text x="63" y="31" fill="#FFF" fontSize="8" textAnchor="middle" fontWeight="bold">4</text>
              </g>

              {/* Dot 5: Neck circum */}
              <g style={{ cursor: 'pointer' }} onClick={() => focusInput('neck_cm')}>
                <ellipse cx="50" cy="25" rx="5" ry="2.5" fill="none" stroke={activeField === 'neck_cm' ? 'var(--text-accent)' : '#4B5563'} strokeWidth={activeField === 'neck_cm' ? '2' : '1'} />
                <circle cx="50" cy="23" r={activeField === 'neck_cm' ? '5' : '4'} fill={activeField === 'neck_cm' ? 'var(--text-accent)' : '#374151'} stroke="var(--border)" strokeWidth="1" />
                <text x="50" y="26" fill="#FFF" fontSize="8" textAnchor="middle" fontWeight="bold">5</text>
              </g>

              {/* Dot 6: Armhole depth */}
              <g style={{ cursor: 'pointer' }} onClick={() => focusInput('armhole_cm')}>
                <line x1="36" y1="28" x2="36" y2="56" stroke={activeField === 'armhole_cm' ? 'var(--text-accent)' : '#4B5563'} strokeWidth={activeField === 'armhole_cm' ? '2' : '1'} />
                <circle cx="36" cy="42" r={activeField === 'armhole_cm' ? '5' : '4'} fill={activeField === 'armhole_cm' ? 'var(--text-accent)' : '#374151'} stroke="var(--border)" strokeWidth="1" />
                <text x="36" y="45" fill="#FFF" fontSize="8" textAnchor="middle" fontWeight="bold">6</text>
              </g>

              {/* Dot 7: Sleeve length */}
              <g style={{ cursor: 'pointer' }} onClick={() => focusInput('sleeve_cm')}>
                <path d="M 63 28 C 65 35, 68 45, 68 55 C 68 62, 67 66, 65 72" fill="none" stroke={activeField === 'sleeve_cm' ? 'var(--text-accent)' : '#4B5563'} strokeWidth={activeField === 'sleeve_cm' ? '2' : '1'} />
                <circle cx="68" cy="55" r={activeField === 'sleeve_cm' ? '5' : '4'} fill={activeField === 'sleeve_cm' ? 'var(--text-accent)' : '#374151'} stroke="var(--border)" strokeWidth="1" />
                <text x="68" y="58" fill="#FFF" fontSize="8" textAnchor="middle" fontWeight="bold">7</text>
              </g>

              {/* Dot 8: Garment length */}
              <g style={{ cursor: 'pointer' }} onClick={() => focusInput('garment_length_cm')}>
                <line x1="45" y1="28" x2="45" y2="92" stroke={activeField === 'garment_length_cm' ? 'var(--text-accent)' : '#4B5563'} strokeWidth={activeField === 'garment_length_cm' ? '2' : '1'} />
                <circle cx="45" cy="92" r={activeField === 'garment_length_cm' ? '5' : '4'} fill={activeField === 'garment_length_cm' ? 'var(--text-accent)' : '#374151'} stroke="var(--border)" strokeWidth="1" />
                <text x="45" y="95" fill="#FFF" fontSize="8" textAnchor="middle" fontWeight="bold">8</text>
              </g>
            </svg>

            {/* Label inside vector */}
            <div style={{ position: 'absolute', bottom: '10px', right: '10px', fontSize: '9px', color: 'var(--text-muted)', fontFamily: 'monospace' }}>
              INTERACTIVE 2D SEGMENT HIGHLIGHT
            </div>
          </div>

          {/* Description Tip Box */}
          <div style={{ background: 'var(--surface-2)', padding: '14px 16px', borderRadius: '8px', border: '1px solid var(--border)' }}>
            <span style={{ fontSize: '11px', fontWeight: 'bold', color: 'var(--text-accent)', display: 'block', textTransform: 'uppercase', marginBottom: '4px' }}>
              {guides[activeField]?.number}. {guides[activeField]?.title} guide
            </span>
            <p style={{ margin: 0, fontSize: '12px', color: 'var(--text-secondary)', lineHeight: '1.4' }}>
              {guides[activeField]?.desc}
            </p>
          </div>

        </div>

      </div>

    </div>
  );
}
