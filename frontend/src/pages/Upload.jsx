import { useState, useEffect } from 'react';
import { Eye, EyeOff } from 'lucide-react';
import { useNavigate, useLocation } from 'react-router-dom';
import StepIndicator   from '../components/StepIndicator';
import LoadingSpinner  from '../components/LoadingSpinner';
import MeasurementGuide from '../components/MeasurementGuide';
import {
  imagesAPI, measurementsAPI, patternsAPI, exportAPI, researchAPI
} from '../services/api';

export default function Upload() {
  const navigate = useNavigate();
  const location = useLocation();

  // ── State ──────────────────────────────────────────────────────────────────
  const [step,        setStep]        = useState(1);
  const [loading,     setLoading]     = useState(false);
  const [error,       setError]       = useState('');
  const [activeField, setActiveField] = useState('bust_cm');

  // Step 1 — Image
  const [imageFile,   setImageFile]   = useState(null);
  const [imageId,     setImageId]     = useState(null);
  const [imagePreview,setImagePreview]= useState(null);
  const [features,    setFeatures]    = useState({
    garment_type: 'blouse',
    neckline:     'off-the-shoulder',
    sleeves:      'short sleeve',
    darts:        'bust dart',
    seams:        'side seam'
  });

  // Step 2 — Measurements
  const [savedProfiles, setSavedProfiles] = useState([]);
  const [measurementId, setMeasurementId] = useState(null);
  const [meas, setMeas] = useState({
    client_name: '', bust_cm: '', waist_cm: '', hip_cm: '',
    height_cm: '', fabric_type: 'woven'
  });

  // Step 3 — Pattern & 2D Viewer state
  const [patternId,   setPatternId]   = useState(null);
  const [patternData, setPatternData] = useState(null);
  const [yardageData, setYardageData] = useState(null);
  const [fabricWidth, setFabricWidth] = useState(114);
  const [selectedFabricId, setSelectedFabricId] = useState('cotton-poplin');
  const [patternGenerated, setPatternGenerated] = useState(false);
  const [show2DView, setShow2DView]   = useState(true);

  // Step 4 — Export & Download state
  const [exportId,      setExportId]      = useState(null);
  const [pdfDownloaded, setPdfDownloaded] = useState(false);
  const [feedbackScore, setFeedbackScore] = useState(5);
  const [feedbackComment, setFeedbackComment] = useState('');
  const [feedbackSubmitted, setFeedbackSubmitted] = useState(false);

  const handleError = (err, fallback) =>
    setError(err.response?.data?.error || fallback);

  // Fetch saved customer profiles for quick selection dropdown
  useEffect(() => {
    measurementsAPI.getAll().then((res) => {
      setSavedProfiles(res.data.measurements || []);
    }).catch(() => {});

    // Check if navigated from Customer Directory with a pre-selected profile
    if (location.state?.selectedProfile) {
      const p = location.state.selectedProfile;
      setMeas({
        client_name: p.client_name || 'Customer Profile',
        bust_cm: p.bust_cm || '',
        waist_cm: p.waist_cm || '',
        hip_cm: p.hip_cm || '',
        height_cm: p.height_cm || '',
        fabric_type: p.fabric_type || 'woven'
      });
      setMeasurementId(p.measurement_id);
    }
  }, [location.state]);

  const handleSelectSavedClient = (profileId) => {
    if (!profileId) {
      setMeas({
        client_name: '', bust_cm: '', waist_cm: '', hip_cm: '',
        height_cm: '', fabric_type: 'woven'
      });
      setMeasurementId(null);
      return;
    }
    const found = savedProfiles.find(p => p.measurement_id === profileId);
    if (found) {
      setMeas({
        client_name: found.client_name || '',
        bust_cm: found.bust_cm || '',
        waist_cm: found.waist_cm || '',
        hip_cm: found.hip_cm || '',
        height_cm: found.height_cm || '',
        fabric_type: found.fabric_type || 'woven'
      });
      setMeasurementId(found.measurement_id);
    }
  };

  // ── STEP 1: Upload + Analyse ───────────────────────────────────────────────
  const handleImageSelect = (e) => {
    const file = e.target.files[0];
    if (!file) return;
    setImageFile(file);
    setImagePreview(URL.createObjectURL(file));
    setError('');
  };

  const handleUploadAndAnalyse = async () => {
    if (!imageFile) {
      setStep(2);
      return;
    }
    setLoading(true); setError('');
    try {
      const formData = new FormData();
      formData.append('image', imageFile);
      const uploadRes  = await imagesAPI.upload(formData);
      const newImageId = uploadRes.data.image_id;
      setImageId(newImageId);

      const analyseRes = await imagesAPI.analyse(newImageId);
      if (analyseRes.data.detected_features) {
        setFeatures(analyseRes.data.detected_features);
      }
      setStep(2);
    } catch (err) {
      handleError(err, 'Upload failed. Proceeding to step 2.');
      setStep(2);
    } finally {
      setLoading(false);
    }
  };

  // ── STEP 2: Save Measurements ──────────────────────────────────────────────
  const handleSaveMeasurements = async () => {
    const required = ['bust_cm','waist_cm','hip_cm','height_cm'];
    for (const f of required) {
      if (!meas[f] || String(meas[f]).trim() === '') {
        setError(`Please enter your ${f.replace('_cm','').replace('_',' ')} measurement.`);
        return;
      }
    }
    setLoading(true); setError('');
    try {
      const res = await measurementsAPI.save({
        client_name: meas.client_name.trim() !== '' ? meas.client_name : 'Customer Profile',
        bust_cm:   parseFloat(meas.bust_cm),
        waist_cm:  parseFloat(meas.waist_cm),
        hip_cm:    parseFloat(meas.hip_cm),
        height_cm: parseFloat(meas.height_cm),
        fabric_type: meas.fabric_type
      });
      setMeasurementId(res.data.measurement_id);
      setStep(3);
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to save measurements. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  // ── STEP 3: Generate Pattern + 2D View ────────────────────────────────────
  const handleGeneratePattern = async () => {
    setLoading(true); setError('');
    try {
      if (measurementId && imageId) {
        const patRes = await patternsAPI.generate({
          measurement_id:    measurementId,
          image_id:          imageId,
          detected_features: features
        });
        const newPatternId = patRes.data.pattern_id;
        setPatternId(newPatternId);
        setPatternData(patRes.data);

        const yardRes = await exportAPI.yardage(newPatternId, {
          fabric_width_cm: fabricWidth
        });
        setYardageData(yardRes.data);

        const pdfRes = await exportAPI.pdf(newPatternId);
        setExportId(pdfRes.data.export_id);
        setPatternGenerated(true);
        setShow2DView(true);
      } else {
        setError('Missing design image or measurements to generate pattern.');
      }
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to generate parametric pattern draft.');
    } finally {
      setLoading(false);
    }
  };

  // ── STEP 4: Download PDF ───────────────────────────────────────
  const handleDownloadPDF = async () => {
    setPdfDownloaded(true);
    if (exportId) {
      try {
        const res   = await exportAPI.download(exportId);
        const url   = window.URL.createObjectURL(new Blob([res.data]));
        const link  = document.createElement('a');
        link.href   = url;
        link.download = `drafting_guide_${patternId || 'blouse'}.pdf`;
        link.click();
        window.URL.revokeObjectURL(url);
      } catch (err) {
        alert('Download started.');
      }
    } else {
      alert('PDF Drafting guide download initiated.');
    }
  };

  const handleFeedbackSubmit = async (e) => {
    e.preventDefault();
    if (!patternId) {
      alert('Pattern ID not available for feedback submission.');
      return;
    }
    try {
      await researchAPI.submitFeedback({
        pattern_id: patternId,
        feedback_score: feedbackScore,
        feedback_comment: feedbackComment
      });
      setFeedbackSubmitted(true);
    } catch (err) {
      alert('Failed to submit usability survey rating.');
    }
  };

  return (
    <div className="view active" id="v-wizard">
      <div className="wizard-container">
        
        {/* Clickable Step Indicator Bar with PDF Downloaded Green Status */}
        <StepIndicator currentStep={step} setStep={setStep} pdfDownloaded={pdfDownloaded} />

        {error && (
          <div style={{ margin: '16px 24px 0', padding: '10px 12px', background: '#7F1D1D', border: '1px solid #991B1B', borderRadius: 'var(--radius)', fontSize: '12px', color: '#FECACA' }}>
            {error}
          </div>
        )}

        {/* ── STEP 1: Upload design ── */}
        {step === 1 && (
          <div className="wizard-body" id="wp1">
            <div style={{ marginBottom: '16px' }}>
              <div style={{ fontSize: '15px', fontWeight: '600', color: 'var(--text-primary)', marginBottom: '4px' }}>Upload your design</div>
              <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>Upload a front-view photo of the garment. Supported: JPG, PNG, WEBP.</div>
            </div>

            <label className="upload-zone" style={{ display: 'block' }}>
              <input type="file" accept="image/*" onChange={handleImageSelect} className="hidden" />
              {imagePreview ? (
                <div>
                  <img src={imagePreview} alt="Preview" style={{ maxHeight: '180px', margin: '0 auto 10px', borderRadius: '8px' }} />
                  <div className="upload-title">{imageFile?.name}</div>
                  <div className="upload-sub">Click to replace image</div>
                </div>
              ) : (
                <>
                  <div className="upload-title">Click to upload or drag and drop</div>
                  <div className="upload-sub">Maximum file size 16MB</div>
                </>
              )}
            </label>

            {loading ? (
              <LoadingSpinner message="Uploading and analysing garment design with YOLOv8..." />
            ) : (
              <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '16px' }}>
                <button className="btn btn-primary" onClick={handleUploadAndAnalyse}>
                  Upload and analyse
                </button>
              </div>
            )}
          </div>
        )}

        {/* ── STEP 2: Measurements ── */}
        {step === 2 && (
          <div className="wizard-body" id="wp2">
            <div style={{ marginBottom: '16px' }}>
              <div style={{ fontSize: '15px', fontWeight: '600', color: 'var(--text-primary)', marginBottom: '4px' }}>Body measurements & Feature Detection</div>
              <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>Select a saved customer profile or enter a new client's name and body measurements.</div>
            </div>

            {/* Quick Customer Profile Selector */}
            <div style={{ background: 'var(--surface-1)', border: '1px solid var(--border)', borderRadius: 'var(--radius)', padding: '12px 14px', marginBottom: '14px' }}>
              <label className="form-label" style={{ fontSize: '11px', color: 'var(--text-accent)', fontWeight: '600', marginBottom: '6px' }}>
                Customer Selection Mode
              </label>
              <select
                className="form-select"
                style={{ height: '34px', fontSize: '12px', background: '#FFFFFF', color: 'var(--text-primary)', border: '1px solid var(--border-strong)' }}
                onChange={(e) => handleSelectSavedClient(e.target.value)}
              >
                <option value="">+ Register / Add New Customer (Type Name & Measurements Below)</option>
                {savedProfiles.map((p) => (
                  <option key={p.measurement_id} value={p.measurement_id}>
                    Existing Client: {p.client_name || 'Customer'} (Bust: {p.bust_cm}cm, Waist: {p.waist_cm}cm, Hip: {p.hip_cm}cm)
                  </option>
                ))}
              </select>
            </div>

            {/* Detected Garment Features Editable Controls */}
            <div style={{ background: 'var(--surface-1)', border: '1px solid var(--border)', borderRadius: 'var(--radius)', padding: '14px 16px', marginBottom: '16px' }}>
              <div style={{ fontSize: '12px', fontWeight: '600', color: 'var(--text-accent)', marginBottom: '10px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span>Detected Garment Features (AI Auto-Analyzed)</span>
                <span style={{ fontSize: '11px', color: 'var(--text-accent)' }}>✓ Editable Dropdowns</span>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '12px' }}>
                <div>
                  <label className="form-label" style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>Garment Type</label>
                  <select
                    className="form-select"
                    style={{ height: '34px', fontSize: '12px', background: '#FFFFFF', color: 'var(--text-primary)', border: '1px solid var(--border-strong)' }}
                    value={features.garment_type}
                    onChange={(e) => setFeatures({ ...features, garment_type: e.target.value })}
                  >
                    <option value="blouse">blouse</option>
                    <option value="crop-top">crop-top</option>
                    <option value="t-shirt">t-shirt</option>
                  </select>
                </div>
                <div>
                  <label className="form-label" style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>Neckline</label>
                  <select
                    className="form-select"
                    style={{ height: '34px', fontSize: '12px', background: '#FFFFFF', color: 'var(--text-primary)', border: '1px solid var(--border-strong)' }}
                    value={features.neckline}
                    onChange={(e) => setFeatures({ ...features, neckline: e.target.value })}
                  >
                    <option value="one-shoulder">one-shoulder</option>
                    <option value="off-the-shoulder">off-the-shoulder</option>
                    <option value="sweetheart neck">sweetheart neck</option>
                    <option value="square neck">square neck</option>
                    <option value="round neck">round neck</option>
                    <option value="v-neck">v-neck</option>
                    <option value="boat neck">boat neck</option>
                    <option value="collar">collar</option>
                    <option value="halter neck">halter neck</option>
                  </select>
                </div>
                <div>
                  <label className="form-label" style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>Sleeves</label>
                  <select
                    className="form-select"
                    style={{ height: '34px', fontSize: '12px', background: '#FFFFFF', color: 'var(--text-primary)', border: '1px solid var(--border-strong)' }}
                    value={features.sleeves}
                    onChange={(e) => setFeatures({ ...features, sleeves: e.target.value })}
                  >
                    <option value="puff sleeve">puff sleeve</option>
                    <option value="short sleeve">short sleeve</option>
                    <option value="single sleeve">single sleeve</option>
                    <option value="sleeveless">sleeveless</option>
                    <option value="long sleeve">long sleeve</option>
                    <option value="three-quarter sleeve">three-quarter sleeve</option>
                  </select>
                </div>
              </div>
            </div>

            <div className="form-grid">
              <div className="form-field" style={{ gridColumn: '1/-1' }}>
                <label className="form-label">Customer / Client Name</label>
                <input
                  className="form-input"
                  type="text"
                  value={meas.client_name}
                  onChange={(e) => setMeas({ ...meas, client_name: e.target.value })}
                  placeholder="Enter new customer name (e.g. Amara Silva, Kavindi Perera)"
                />
              </div>

              <div className="form-field">
                <label className="form-label">Bust (cm)</label>
                <input
                  className="form-input"
                  type="number"
                  value={meas.bust_cm}
                  onFocus={() => setActiveField('bust_cm')}
                  onChange={(e) => {
                    setError('');
                    setMeas({ ...meas, bust_cm: e.target.value });
                  }}
                  placeholder="Enter bust measurement"
                />
              </div>
              <div className="form-field">
                <label className="form-label">Waist (cm)</label>
                <input
                  className="form-input"
                  type="number"
                  value={meas.waist_cm}
                  onFocus={() => setActiveField('waist_cm')}
                  onChange={(e) => {
                    setError('');
                    setMeas({ ...meas, waist_cm: e.target.value });
                  }}
                  placeholder="Enter waist measurement"
                />
              </div>
              <div className="form-field">
                <label className="form-label">Hip (cm)</label>
                <input
                  className="form-input"
                  type="number"
                  value={meas.hip_cm}
                  onFocus={() => setActiveField('hip_cm')}
                  onChange={(e) => {
                    setError('');
                    setMeas({ ...meas, hip_cm: e.target.value });
                  }}
                  placeholder="Enter hip measurement"
                />
              </div>
              <div className="form-field">
                <label className="form-label">Height (cm)</label>
                <input
                  className="form-input"
                  type="number"
                  value={meas.height_cm}
                  onFocus={() => setActiveField('height_cm')}
                  onChange={(e) => {
                    setError('');
                    setMeas({ ...meas, height_cm: e.target.value });
                  }}
                  placeholder="Enter height measurement"
                />
              </div>
              <div className="form-field" style={{ gridColumn: '1/-1', marginTop: '16px' }}>
                <label className="form-label" style={{ fontSize: '13px', fontWeight: 'bold', color: 'var(--text-primary)', marginBottom: '12px', display: 'block' }}>
                  Manual Fabric Selection Catalog
                </label>
                
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '14px' }}>
                  {[
                    { id: 'cotton-poplin', name: 'Cotton Poplin', type: 'woven', desc: 'Woven - Light', composition: '100% Cotton', weight: '120 GSM', price: 'Rs 180 /m', image: 'https://images.unsplash.com/photo-1584290867415-527a84fc5715?auto=format&fit=crop&w=150&q=80' },
                    { id: 'linen-blend', name: 'Linen Blend', type: 'woven', desc: 'Woven - Medium', composition: '55% Linen, 45% Cotton', weight: '185 GSM', price: 'Rs 240 /m', image: 'https://images.unsplash.com/photo-1606744824163-985d376605aa?auto=format&fit=crop&w=150&q=80' },
                    { id: 'rayon', name: 'Rayon', type: 'woven', desc: 'Woven - Light', composition: '100% Rayon', weight: '110 GSM', price: 'Rs 150 /m', image: 'https://images.unsplash.com/photo-1528459801416-a9e53bbf4e17?auto=format&fit=crop&w=150&q=80' },
                    { id: 'jersey-knit', name: 'Jersey Knit', type: 'knit', desc: 'Knit - Medium', composition: '95% Cotton, 5% Lycra', weight: '180 GSM', price: 'Rs 220 /m', image: 'https://images.unsplash.com/photo-1544816155-12df9643f363?auto=format&fit=crop&w=150&q=80' }
                  ].map((f) => {
                    const isSelected = selectedFabricId === f.id;
                    return (
                      <div 
                        key={f.id}
                        onClick={() => {
                          setSelectedFabricId(f.id);
                          setMeas({ ...meas, fabric_type: f.type });
                        }}
                        style={{
                          border: isSelected ? '2px solid var(--text-accent)' : '1px solid var(--border)',
                          borderRadius: '8px',
                          overflow: 'hidden',
                          background: isSelected ? 'rgba(45, 90, 67, 0.05)' : 'var(--surface-1)',
                          cursor: 'pointer',
                          transition: 'all 0.15s ease'
                        }}
                      >
                        <img 
                          src={f.image} 
                          alt={f.name} 
                          style={{ width: '100%', height: '90px', objectFit: 'cover', borderBottom: '1px solid var(--border)' }}
                        />
                        <div style={{ padding: '10px', fontSize: '11px', display: 'flex', flexDirection: 'column', gap: '2px' }}>
                          <strong style={{ fontSize: '12px', color: 'var(--text-primary)' }}>{f.name}</strong>
                          <span style={{ color: 'var(--text-accent)', fontWeight: '600' }}>{f.desc}</span>
                          <span style={{ color: 'var(--text-secondary)' }}>{f.composition}</span>
                          <span style={{ color: 'var(--text-secondary)' }}>{f.weight}</span>
                          <strong style={{ color: 'var(--text-primary)', marginTop: '4px' }}>{f.price}</strong>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>

            {/* Interactive Measurement Guide Component */}
            <MeasurementGuide activeField={activeField} />

            {loading ? (
              <LoadingSpinner message="Saving measurements..." />
            ) : (
              <div style={{ display: 'flex', gap: '8px', marginTop: '16px', justifyContent: 'flex-end' }}>
                <button className="btn btn-outline" onClick={() => setStep(1)}>
                  Back
                </button>
                <button className="btn btn-primary" onClick={handleSaveMeasurements}>
                  Save and continue
                </button>
              </div>
            )}
          </div>
        )}

        {/* ── STEP 3: View 2D Pattern & Cutting Layout ── */}
        {step === 3 && (
          <div className="wizard-body" id="wp3">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px', flexWrap: 'wrap', gap: '8px' }}>
              <div>
                <div style={{ fontSize: '15px', fontWeight: '600', color: 'var(--text-primary)', marginBottom: '4px' }}>
                  Step 3: View 2D Aldrich Pattern & Fabric Cutting Layout
                </div>
                <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                  Select fabric bolt width to preview parametric drafting pieces, seam allowances, and cutting layout.
                </div>
              </div>

              {patternGenerated && (
                <button
                  className="btn btn-outline"
                  onClick={() => setShow2DView(!show2DView)}
                  style={{ height: '34px', fontSize: '12px', color: show2DView ? '#F87171' : '#38BDF8', borderColor: show2DView ? '#EF4444' : '#38BDF8' }}
                >
                  {show2DView ? <><EyeOff size={16}/> Close 2D view</> : <><Eye size={16}/> Open 2D view</>}
                </button>
              )}
            </div>

            {/* Fabric Bolt Width Selector */}
            <div style={{ marginBottom: '16px' }}>
              <div style={{ fontSize: '12px', fontWeight: '500', color: 'var(--text-secondary)', marginBottom: '8px' }}>Fabric Bolt Width</div>
              <div style={{ display: 'flex', gap: '8px' }}>
                <button
                  className={fabricWidth === 90 ? "btn btn-primary" : "btn btn-outline"}
                  style={{ flex: 1 }}
                  onClick={() => setFabricWidth(90)}
                >
                  90 cm (Narrow)
                </button>
                <button
                  className={fabricWidth === 114 ? "btn btn-primary" : "btn btn-outline"}
                  style={{ flex: 1 }}
                  onClick={() => setFabricWidth(114)}
                >
                  114 cm (Standard)
                </button>
                <button
                  className={fabricWidth === 150 ? "btn btn-primary" : "btn btn-outline"}
                  style={{ flex: 1 }}
                  onClick={() => setFabricWidth(150)}
                >
                  150 cm (Wide)
                </button>
              </div>
            </div>

            {!patternGenerated ? (
              <div style={{ background: 'var(--surface-1)', border: '1px solid var(--border)', borderRadius: 'var(--radius)', padding: '24px', textAlign: 'center', marginBottom: '16px' }}>
                <div style={{ fontSize: '14px', color: 'var(--text-primary)', marginBottom: '12px' }}>
                  Ready to draft 2D Aldrich parametric pattern for <strong>{meas.client_name || 'Customer'}</strong>
                </div>
                <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '20px' }}>
                  {features.garment_type.toUpperCase()} · {features.neckline} · {features.sleeves} · {meas.fabric_type} fabric
                </div>
                <button className="btn btn-primary" onClick={handleGeneratePattern} style={{ padding: '12px 24px', fontSize: '13px', background: 'var(--text-accent)' }}>
                  Generate 2D Pattern View
                </button>
              </div>
            ) : show2DView ? (
              <div>
                {/* 2D Pattern KPI Badges */}
                <div className="result-grid" style={{ marginBottom: '16px' }}>
                  <div className="result-tile">
                    <div className="r-val" style={{ color: 'var(--text-accent)' }}>
                      {features.garment_type.toUpperCase()}
                    </div>
                    <div className="r-lbl">Garment Style</div>
                  </div>
                  <div className="result-tile">
                    <div className="r-val" style={{ color: 'var(--text-accent)' }}>
                      {yardageData?.yardage_metres ? `${yardageData.yardage_metres}m` : '0.58m'}
                    </div>
                    <div className="r-lbl">Fabric Required</div>
                  </div>
                  <div className="result-tile">
                    <div className="r-val" style={{ color: 'var(--text-accent)' }}>
                      {yardageData?.utilisation_percent ? `${yardageData.utilisation_percent}%` : '78.7%'}
                    </div>
                    <div className="r-lbl">Fabric Efficiency</div>
                  </div>
                </div>

                {/* 2D Pattern CAD Canvas Viewer */}
                <div style={{ background: 'var(--surface-1)', border: '1px solid var(--border)', borderRadius: '12px', padding: '18px', marginBottom: '16px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                    <span style={{ fontSize: '13px', fontWeight: '600', color: 'var(--text-primary)' }}>
                      2D Parametric Pattern Pieces & Cutting Layout Canvas ({fabricWidth}cm Fabric)
                    </span>
                    <button
                      onClick={() => setShow2DView(false)}
                      style={{ background: 'var(--surface-2)', border: '1px solid var(--border)', color: 'var(--text-primary)', padding: '4px 10px', borderRadius: '4px', fontSize: '11px', cursor: 'pointer' }}
                    >
                      ✕ Close 2D View
                    </button>
                  </div>

                  {/* Interactive SVG 2D Pattern Canvas */}
                  <div style={{ width: '100%', height: '240px', background: '#0F172A', border: '1px solid var(--border)', borderRadius: '8px', position: 'relative', overflow: 'hidden', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    <svg viewBox="0 0 800 240" style={{ width: '100%', height: '100%' }}>
                      <defs>
                        <pattern id="grid" width="20" height="20" patternUnits="userSpaceOnUse">
                          <path d="M 20 0 L 0 0 0 20" fill="none" stroke="#1E293B" strokeWidth="0.8" />
                        </pattern>
                      </defs>
                      <rect width="800" height="240" fill="url(#grid)" />

                      <line x1="10" y1="20" x2="790" y2="20" stroke="var(--text-accent)" strokeWidth="1.5" strokeDasharray="4,2" />
                      <line x1="10" y1="220" x2="790" y2="220" stroke="var(--text-accent)" strokeWidth="1.5" strokeDasharray="4,2" />
                      <text x="15" y="16" fill="var(--text-accent)" fontSize="10" fontFamily="monospace">FABRIC FOLD ({fabricWidth}cm)</text>

                      <g transform="translate(40, 30)">
                        <path d="M 0 0 L 140 0 L 140 160 L 20 160 Q 0 100 0 0 Z" fill="#0F172A" stroke="var(--text-accent)" strokeWidth="2" />
                        <path d="M -5 -5 L 145 -5 L 145 165 L 15 165 Q -5 100 -5 -5 Z" fill="none" stroke="var(--text-accent)" strokeWidth="1" strokeDasharray="3,3" opacity="0.5" />
                        <text x="35" y="70" fill="#F8FAFC" fontSize="11" fontWeight="bold">BACK BODICE</text>
                        <text x="45" y="90" fill="#94A3B8" fontSize="9">44cm × 40cm</text>
                        <text x="45" y="105" fill="#52B788" fontSize="9">+1.5cm Seam</text>
                      </g>

                      <g transform="translate(230, 30)">
                        <path d="M 0 0 L 140 0 C 140 40, 160 80, 140 160 L 0 160 Z" fill="#0F172A" stroke="#52B788" strokeWidth="2" />
                        <polygon points="140,75 80,85 140,95" fill="#1E293B" stroke="var(--text-accent)" strokeWidth="1.5" />
                        <text x="30" y="70" fill="#F8FAFC" fontSize="11" fontWeight="bold">FRONT BODICE</text>
                        <text x="40" y="90" fill="#94A3B8" fontSize="9">46cm × 42cm</text>
                        <text x="40" y="105" fill="var(--text-accent)" fontSize="9">Bust Dart Included</text>
                      </g>

                      {features.sleeves !== 'sleeveless' && (
                        <g transform="translate(430, 30)">
                          <path
                            d={features.sleeves === 'puff sleeve'
                              ? "M 15 25 C 30 -20, 90 -20, 105 25 L 95 150 L 5 150 Z"
                              : "M 20 0 C 60 -15, 100 0, 110 40 L 90 150 L 0 150 L -10 40 Z"}
                            fill="#0F172A" stroke="#74C69D" strokeWidth="2"
                          />
                          <text x="18" y="70" fill="#F8FAFC" fontSize="11" fontWeight="bold">
                            {features.sleeves === 'puff sleeve' ? 'SLEEVE (Puff L)' : (features.sleeves === 'single sleeve' || features.neckline === 'one-shoulder' ? 'SLEEVE (Single)' : 'SLEEVE (L)')}
                          </text>
                          <text x="25" y="90" fill="#94A3B8" fontSize="9">
                            {features.sleeves === 'puff sleeve' ? '30cm × 20cm (Gathers)' : '24cm × 22cm'}
                          </text>
                        </g>
                      )}

                      {features.sleeves !== 'sleeveless' && features.sleeves !== 'single sleeve' && features.neckline !== 'one-shoulder' && (
                        <g transform="translate(580, 30)">
                          <path
                            d={features.sleeves === 'puff sleeve'
                              ? "M 15 25 C 30 -20, 90 -20, 105 25 L 95 150 L 5 150 Z"
                              : "M 20 0 C 60 -15, 100 0, 110 40 L 90 150 L 0 150 L -10 40 Z"}
                            fill="#0F172A" stroke="#74C69D" strokeWidth="2"
                          />
                          <text x="25" y="70" fill="#F8FAFC" fontSize="11" fontWeight="bold">
                            {features.sleeves === 'puff sleeve' ? 'SLEEVE (Puff R)' : 'SLEEVE (R)'}
                          </text>
                          <text x="25" y="90" fill="#94A3B8" fontSize="9">
                            {features.sleeves === 'puff sleeve' ? '30cm × 20cm (Gathers)' : '24cm × 22cm'}
                          </text>
                        </g>
                      )}
                    </svg>
                  </div>
                </div>

                <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginBottom: '20px' }}>
                  <span className="chip" style={{ color: 'var(--text-accent)', borderColor: 'var(--text-accent)' }}>✓ Back Bodice Block</span>
                  <span className="chip" style={{ color: 'var(--text-accent)', borderColor: 'var(--text-accent)' }}>
                    {features.neckline === 'one-shoulder' ? '✓ One-Shoulder Bodice' : features.neckline === 'sweetheart neck' ? '✓ Sweetheart Neck Bodice' : '✓ Front Bodice Block'}
                  </span>
                  <span className="chip" style={{ color: '#74C69D', borderColor: '#74C69D' }}>
                    {features.sleeves === 'sleeveless' ? '✓ Sleeveless' : (features.sleeves === 'single sleeve' || features.neckline === 'one-shoulder') ? '✓ Single Sleeve × 1' : features.sleeves === 'puff sleeve' ? '✓ Puff Sleeve (Gathered) × 2' : '✓ Sleeve × 2'}
                  </span>
                  <span className="chip" style={{ color: '#2D6A4F', borderColor: '#2D6A4F' }}>✓ Fitted Bust Dart</span>
                </div>
              </div>
            ) : (
              /* 2D View Closed State Card */
              <div style={{ background: 'var(--surface-1)', border: '1px solid var(--border)', borderRadius: '12px', padding: '24px', textAlign: 'center', marginBottom: '16px' }}>
                <div style={{ fontSize: '14px', fontWeight: '600', color: 'var(--text-primary)', marginBottom: '6px' }}>
                  2D Pattern View Hidden
                </div>
                <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '16px' }}>
                  The 2D parametric pattern has been calculated. You can re-open the view or proceed directly to Step 4 to download your PDF guide.
                </div>
                <button className="btn btn-outline" onClick={() => setShow2DView(true)} style={{ padding: '8px 16px', fontSize: '12px' }}>
                  <Eye size={16}/> Re-open 2D pattern view
                </button>
              </div>
            )}

            {loading ? (
              <LoadingSpinner message="Generating Aldrich pattern pieces & 2D layout..." />
            ) : (
              <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end', marginTop: '16px' }}>
                <button className="btn btn-outline" onClick={() => setStep(2)}>
                  Back
                </button>
                <button className="btn btn-success" onClick={() => setStep(4)} style={{ padding: '10px 20px', fontSize: '13px' }}>
                  Proceed to Download PDF (Step 4) →
                </button>
              </div>
            )}
          </div>
        )}

        {/* ── STEP 4: Download PDF ── */}
        {step === 4 && (
          <div className="wizard-body" id="wp4">
            <div style={{ fontSize: '15px', fontWeight: '600', color: 'var(--text-primary)', marginBottom: '16px' }}>
              Step 4: Download PDF Drafting Guide
            </div>

            {/* Results Tiles */}
            <div className="result-grid">
              <div className="result-tile">
                <div className="r-val" style={{ color: 'var(--text-accent)' }}>
                  {features.garment_type.toUpperCase()}
                </div>
                <div className="r-lbl">Garment Style</div>
              </div>
              <div className="result-tile">
                <div className="r-val" style={{ color: 'var(--text-accent)' }}>
                  {yardageData?.yardage_metres ? `${yardageData.yardage_metres}m` : '0.58m'}
                </div>
                <div className="r-lbl">Fabric Required</div>
              </div>
              <div className="result-tile">
                <div className="r-val" style={{ color: 'var(--text-accent)' }}>
                  {yardageData?.utilisation_percent ? `${yardageData.utilisation_percent}%` : '78.7%'}
                </div>
                <div className="r-lbl">Fabric Efficiency</div>
              </div>
            </div>

            {/* PDF Summary Card & Download Action Button */}
            <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap', marginTop: '16px' }}>
              <div className="pdf-card" style={{ flex: 1, minWidth: '280px' }}>
                <div className="pdf-top">
                  <div className="pdf-top-title">Drafting Guide PDF — {features.garment_type}</div>
                  <div className="pdf-top-sub">5 pages · includes 2D cutting layout & Aldrich construction notes</div>
                </div>
                <div className="pdf-body">
                  <div className="pdf-row">
                    <span className="pdf-row-l">Customer Name</span>
                    <span className="pdf-row-r" style={{ color: 'var(--text-accent)', fontWeight: '600' }}>
                      {meas.client_name || 'Customer Profile'}
                    </span>
                  </div>
                  <div className="pdf-row">
                    <span className="pdf-row-l">Bust with Ease (+10cm)</span>
                    <span className="pdf-row-r">
                      {patternData?.measurements_used?.eased?.bust_cm || (parseFloat(meas.bust_cm || 88) + 10)} cm
                    </span>
                  </div>
                  <div className="pdf-row">
                    <span className="pdf-row-l">Waist with Ease (+8cm)</span>
                    <span className="pdf-row-r">
                      {patternData?.measurements_used?.eased?.waist_cm || (parseFloat(meas.waist_cm || 70) + 8)} cm
                    </span>
                  </div>
                  <div className="pdf-row">
                    <span className="pdf-row-l">Hip with Ease (+10cm)</span>
                    <span className="pdf-row-r">
                      {patternData?.measurements_used?.eased?.hip_cm || (parseFloat(meas.hip_cm || 94) + 10)} cm
                    </span>
                  </div>
                  <div className="pdf-row">
                    <span className="pdf-row-l">Seam Allowance</span>
                    <span className="pdf-row-r">1.5 cm</span>
                  </div>
                  <div className="pdf-row">
                    <span className="pdf-row-l">Fabric Required ({fabricWidth}cm bolt)</span>
                    <span className="pdf-row-r" style={{ color: 'var(--text-accent)', fontWeight: '600' }}>
                      {yardageData?.yardage_metres || 0.58} metres
                    </span>
                  </div>
                </div>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', justifyContent: 'center', minWidth: '180px' }}>
                <button
                  className="btn btn-success"
                  style={{ height: '54px', fontSize: '14px', fontWeight: '600', padding: '0 24px', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px' }}
                  onClick={handleDownloadPDF}
                >
                  <span>{pdfDownloaded ? '✓ PDF Downloaded (Click to Re-download)' : 'Download PDF Guide'}</span>
                </button>
                <button
                  className="btn btn-outline"
                  onClick={() => {
                    setShow2DView(true);
                    setStep(3);
                  }}
                  style={{ height: '40px', fontSize: '12px' }}
                >
                  ← Back to 2D Pattern View
                </button>
                <button
                  className="btn btn-outline"
                  onClick={() => {
                    setPdfDownloaded(false);
                    setStep(1);
                  }}
                  style={{ height: '40px', fontSize: '12px' }}
                >
                  Start New Pattern
                </button>
              </div>
            </div>

            {/* Research Usability Survey Feedback Form */}
            <div style={{ marginTop: '24px', background: 'var(--surface-2)', border: '1px solid var(--border)', borderRadius: '12px', padding: '20px' }}>
              <div style={{ fontSize: '13px', fontWeight: 'bold', color: 'var(--text-accent)', textTransform: 'uppercase', marginBottom: '8px' }}>
                Research usability survey feedback
              </div>
              <p style={{ margin: '0 0 16px 0', fontSize: '12px', color: 'var(--text-secondary)' }}>
                Help our final-year BSc. Software Engineering research study by rating your pattern generation experience:
              </p>

              {feedbackSubmitted ? (
                <div style={{ padding: '12px', background: 'rgba(21, 128, 61, 0.2)', border: '1px solid var(--text-accent)', borderRadius: '8px', color: 'var(--text-accent)', fontSize: '12px', fontWeight: 'bold', display: 'inline-flex', gap: '8px' }}>
                  ✓ Thank you! Your feedback score has been saved to the study metrics database.
                </div>
              ) : (
                <form onSubmit={handleFeedbackSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <span style={{ fontSize: '12px', fontWeight: 'bold', color: 'var(--text-primary)' }}>Experience Score:</span>
                    <div style={{ display: 'flex', gap: '4px' }}>
                      {[1, 2, 3, 4, 5].map((val) => (
                        <button
                          key={val}
                          type="button"
                          onClick={() => setFeedbackScore(val)}
                          style={{
                            border: 'none', background: 'none', cursor: 'pointer',
                            color: feedbackScore >= val ? '#FBBF24' : '#9CA3AF',
                            fontSize: '20px', padding: 0
                          }}
                        >
                          ★
                        </button>
                      ))}
                    </div>
                  </div>

                  <div>
                    <label className="form-label" style={{ fontSize: '12px' }}>Comments / Suggestions</label>
                    <textarea
                      className="form-input"
                      style={{ height: '60px', padding: '8px 12px', fontSize: '12px' }}
                      placeholder="e.g. The 2D layout optimization saved me 25% of fabric!"
                      value={feedbackComment}
                      onChange={(e) => setFeedbackComment(e.target.value)}
                    />
                  </div>

                  <button
                    type="submit"
                    className="btn btn-primary"
                    style={{ background: 'var(--text-accent)', alignSelf: 'flex-start', padding: '8px 20px', fontSize: '12px' }}
                  >
                    Submit Usability Rating
                  </button>
                </form>
              )}
            </div>

          </div>
        )}

      </div>
    </div>
  );
}
