import { useState, useEffect } from 'react';
import { Eye, EyeOff, Info, ChevronDown, ChevronUp } from 'lucide-react';
import { useNavigate, useLocation } from 'react-router-dom';
import StepIndicator   from '../components/StepIndicator';
import LoadingSpinner  from '../components/LoadingSpinner';
import MeasurementGuide from '../components/MeasurementGuide';
import FabricRecommendation from '../components/FabricRecommendation';
import PredictionReview from '../components/PredictionReview';
import PatternPreview from '../components/PatternPreview';
import { supportReport } from '../utils/designSchema';
import {
  MEASUREMENT_FIELDS, validateMeasurements, convertDisplayValues, parseFieldErrors, buildPayload, rangeText,
} from '../utils/measurementSchema';
import { formatResult, CALCULATION_FAILED, NOT_CALCULATED as NOT_CALCULATED_LABEL } from '../utils/results';
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

  // Step 1 — Image & Multi-Task AI Predictions (Milestone M14)
  const [imageFile,   setImageFile]   = useState(null);
  const [imageId,     setImageId]     = useState(null);
  const [imagePreview,setImagePreview]= useState(null);
  const [garmentAttributes, setGarmentAttributes] = useState(null);
  const [confirmedAttributes, setConfirmedAttributes] = useState(null);
  const [isAttributesConfirmed, setIsAttributesConfirmed] = useState(false);
  const [confirmLoading, setConfirmLoading] = useState(false);
  const [confirmError, setConfirmError] = useState('');
  const [features,    setFeatures]    = useState({
    garment_type: '',
    neckline:     '',
    sleeves:      '',
    darts:        '',
    seams:        ''
  });
  const [requiresUserVerification, setRequiresUserVerification] = useState(false);

  // Step 2 — Measurements (locked drafting set)
  const emptyMeas = {
    client_name: '',
    bust_cm: '',
    waist_cm: '',
    hip_cm: '',
    height_cm: '',
    neck_cm: '',
    shoulder_cm: '',
    across_back_cm: '',
    back_waist_length_cm: '',
    armhole_depth_cm: '',
    garment_length_cm: '',
    bicep_cm: '',
    sleeve_cm: '',
    wrist_cm: '',
    fabric_type: 'woven',
    fit_preference: 'standard',
  };
  const [savedProfiles, setSavedProfiles] = useState([]);
  const [measurementId, setMeasurementId] = useState(null);
  const [meas, setMeas] = useState({ ...emptyMeas });
  // Measurement input unit. Values typed are interpreted in this unit and converted to canonical cm by the server.
  const [unit, setUnit] = useState('cm');
  const [fieldErrors, setFieldErrors] = useState({});

  // Step 3 — Pattern & 2D Viewer state
  const [patternId,   setPatternId]   = useState(null);
  const [patternData, setPatternData] = useState(null);
  const [yardageData, setYardageData] = useState(null);
  const [fabricWidth, setFabricWidth] = useState(114);
  const [yardageError, setYardageError] = useState(false);
  const [selectedFabricId, setSelectedFabricId] = useState('cotton-poplin');
  const [selectedFabricName, setSelectedFabricName] = useState('Cotton Poplin');
  const [fabricValidationError, setFabricValidationError] = useState('');
  const [patternGenerated, setPatternGenerated] = useState(false);
  const [show2DView, setShow2DView]   = useState(true);
  const [showTechAudit, setShowTechAudit] = useState(false);

  // Step 4 — Export & Download state
  const [exportId,      setExportId]      = useState(null);
  const [pdfDownloaded, setPdfDownloaded] = useState(false);
  const [feedbackScore, setFeedbackScore] = useState(5);
  const [feedbackComment, setFeedbackComment] = useState('');
  const [feedbackSubmitted, setFeedbackSubmitted] = useState(false);

  const handleError = (err, fallback) =>
    setError(err.response?.data?.error || fallback);

  const profileToMeas = (p) => ({
    client_name: p.client_name || 'Customer Profile',
    bust_cm: p.bust_cm ?? '',
    waist_cm: p.waist_cm ?? '',
    hip_cm: p.hip_cm ?? '',
    height_cm: p.height_cm ?? '',
    neck_cm: p.neck_cm ?? '',
    shoulder_cm: p.shoulder_cm ?? '',
    across_back_cm: p.across_back_cm ?? '',
    back_waist_length_cm: p.back_waist_length_cm ?? '',
    armhole_depth_cm: p.armhole_depth_cm ?? p.armhole_cm ?? '',
    garment_length_cm: p.garment_length_cm ?? '',
    bicep_cm: p.bicep_cm ?? '',
    sleeve_cm: p.sleeve_cm ?? '',
    wrist_cm: p.wrist_cm ?? '',
    fabric_type: p.fabric_type || 'woven',
    fit_preference: p.fit_preference || 'standard',
  });

  // Fetch saved customer profiles for quick selection dropdown
  useEffect(() => {
    measurementsAPI.getAll().then((res) => {
      setSavedProfiles(res.data.measurements || []);
    }).catch(() => {});

    // Check if navigated from Customer Directory with a pre-selected profile
    if (location.state?.selectedProfile) {
      const p = location.state.selectedProfile;
      setMeas(profileToMeas(p));
      setUnit('cm');            // stored profile values are canonical cm
      setFieldErrors({});
      setMeasurementId(p.measurement_id);
    }
  }, [location.state]);

  // Deduplicate saved customer profiles so duplicate entries are not rendered repeatedly
  const uniqueProfiles = savedProfiles.reduce((acc, current) => {
    const rawName = (current.client_name || '').trim();
    const nameLower = rawName.toLowerCase();
    const exists = acc.some(item => {
      const itemRaw = (item.client_name || '').trim().toLowerCase();
      if (nameLower && nameLower !== 'customer profile' && nameLower !== 'customer') {
        return itemRaw === nameLower;
      }
      return itemRaw === nameLower &&
        item.bust_cm === current.bust_cm &&
        item.waist_cm === current.waist_cm &&
        item.hip_cm === current.hip_cm &&
        item.height_cm === current.height_cm;
    });
    if (!exists) {
      acc.push(current);
    }
    return acc;
  }, []);

  const handleSelectSavedClient = (profileId) => {
    if (!profileId) {
      setMeas({ ...emptyMeas });
      setFieldErrors({});
      setMeasurementId(null);
      return;
    }
    const found = savedProfiles.find(p => p.measurement_id === profileId);
    if (found) {
      setMeas(profileToMeas(found));
      setUnit('cm');            // stored profile values are canonical cm
      setFieldErrors({});
      setMeasurementId(found.measurement_id);
    }
  };

  const handleUnitToggle = (newUnit) => {
    if (newUnit === unit) return;
    setMeas((prev) => ({ ...prev, ...convertDisplayValues(prev, unit, newUnit) }));
    setUnit(newUnit);
    setFieldErrors({});
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
      if (analyseRes.data.garment_attributes) {
        setGarmentAttributes(analyseRes.data.garment_attributes);
      }
      if (analyseRes.data.confirmed_attributes && Object.keys(analyseRes.data.confirmed_attributes).length > 0) {
        setConfirmedAttributes(analyseRes.data.confirmed_attributes);
        setIsAttributesConfirmed(true);
      } else {
        setConfirmedAttributes(null);
        setIsAttributesConfirmed(false);
      }
      if (analyseRes.data.detected_features) {
        setFeatures(analyseRes.data.detected_features);
      }
      setRequiresUserVerification(Boolean(
        analyseRes.data.requires_user_confirmation
        ?? analyseRes.data.requires_user_verification
        ?? analyseRes.data.garment_attributes?.requires_user_confirmation
      ));
      setStep(2);
    } catch (err) {
      handleError(err, 'Image upload or AI analysis failed. Please check server logs and try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleConfirmGarmentAttributes = async (confirmedData) => {
    if (!imageId) {
      // Manual mode without uploaded image ID
      setConfirmedAttributes(confirmedData);
      setIsAttributesConfirmed(true);
      setFeatures((prev) => ({
        ...prev,
        garment_type: confirmedData.garment_type,
        neckline: confirmedData.neckline_type,
        sleeves: confirmedData.sleeve_length,
        sleeve_style: confirmedData.sleeve_style,
      }));
      return;
    }

    setConfirmLoading(true);
    setConfirmError('');
    try {
      const res = await imagesAPI.confirmAttributes(imageId, confirmedData);
      setConfirmedAttributes(res.data.confirmed_attributes);
      setIsAttributesConfirmed(true);
      setFeatures((prev) => ({
        ...prev,
        garment_type: confirmedData.garment_type,
        neckline: confirmedData.neckline_type,
        sleeves: confirmedData.sleeve_length,
        sleeve_style: confirmedData.sleeve_style,
      }));
    } catch (err) {
      setConfirmError(err.response?.data?.error || 'Failed to confirm garment features. Please try again.');
    } finally {
      setConfirmLoading(false);
    }
  };

  // ── STEP 2: Save Measurements ──────────────────────────────────────────────
  const handleSaveMeasurements = async () => {
    if (!isAttributesConfirmed) {
      setError('Please review and click "Confirm Design Features" before saving measurements and proceeding.');
      return;
    }
    const designSupport = supportReport(confirmedAttributes || {});
    if (!designSupport.supported) {
      setError(
        'This design cannot be drafted yet: '
        + designSupport.unsupported.map((u) => `${u.head.replace(/_/g, ' ')} = ${u.label}`).join('; ')
        + '. Edit & re-confirm with a supported option (the system will not substitute another design).'
      );
      return;
    }
    // Instant client-side checks (required, numeric, positive, plausible range). The server
    // re-validates everything, including cross-field relationships.
    const localErrors = validateMeasurements(meas, unit);
    if (Object.keys(localErrors).length > 0) {
      setFieldErrors(localErrors);
      setError('Please correct the highlighted measurements.');
      return;
    }
    if (!features.garment_type && !confirmedAttributes?.garment_type) {
      setError('Please select a Garment Type for your pattern design.');
      return;
    }
    if (!selectedFabricId) {
      setFabricValidationError('Please select a recommended fabric material for your garment design before proceeding.');
      setError('Please select a recommended fabric material for your garment design before proceeding.');
      return;
    }
    setLoading(true); setError(''); setFabricValidationError('');
    try {
      const res = await measurementsAPI.save({
        client_name: meas.client_name.trim() !== '' ? meas.client_name : 'Customer Profile',
        ...buildPayload(meas, unit),     // only what was entered, in the selected unit
        fabric_type: meas.fabric_type,
        fit_preference: meas.fit_preference || 'standard',
      });
      setFieldErrors({});
      setMeasurementId(res.data.measurement_id);
      setStep(3);
    } catch (err) {
      const parsed = parseFieldErrors(err);
      if (parsed._form) {
        setError(parsed._form);
      } else {
        setFieldErrors(parsed);
        setError('Please correct the highlighted measurements.');
      }
    } finally {
      setLoading(false);
    }
  };

  // Research integrity: results are shown only when the backend produced them.
  // Otherwise say so honestly — never substitute a plausible-looking number.
  const NOT_CALCULATED = yardageError ? CALCULATION_FAILED : NOT_CALCULATED_LABEL;
  const resultOrNA = (value, suffix = '') => formatResult(value, suffix, yardageError);

  // ── STEP 3: Generate Pattern + 2D View ────────────────────────────────────
  const handleGeneratePattern = async () => {
    setLoading(true); setError('');
    try {
      if (measurementId) {
        const patRes = await patternsAPI.generate({
          measurement_id:    measurementId,
          image_id:          imageId || 'manual',
          confirmed_attributes: confirmedAttributes || undefined,
          fabric_id:         selectedFabricId,
          fabric_name:       selectedFabricName
        });
        const newPatternId = patRes.data.pattern_id;
        setPatternId(newPatternId);
        setPatternData(patRes.data);

        if (patRes.data.validation_passed === false || patRes.data.fabric_estimate_blocked) {
          const errs = (patRes.data.validation?.errors || []).join(' ');
          setError(
            errs
              ? `Pattern validation failed: ${errs}`
              : 'Pattern validation failed. Fabric estimate is blocked until errors are fixed.'
          );
          setYardageData(null);
          setPatternGenerated(true);
          setShow2DView(true);
          return;
        }

        try {
          const yardRes = await exportAPI.yardage(newPatternId, {
            fabric_width_cm: fabricWidth
          });
          setYardageData(yardRes.data);
          setYardageError(false);
        } catch (yardErr) {
          // Nesting failed (e.g. a piece does not fit the selected fabric width).
          setYardageData(null);
          setYardageError(true);
          setError(yardErr.response?.data?.error || 'Fabric calculation failed.');
          setPatternGenerated(true);
          setShow2DView(true);
          return;
        }

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

  const handleFabricWidthChange = async (w) => {
    setFabricWidth(w);
    if (patternId) {
      try {
        const yardRes = await exportAPI.yardage(patternId, {
          fabric_width_cm: w,
          cutting_mode: 'folded'
        });
        setYardageData(yardRes.data);
        setYardageError(false);
        setError('');
      } catch (err) {
        // Never leave a previous width's result on screen after a failed recalculation.
        setYardageData(null);
        setYardageError(true);
        setError(err.response?.data?.error || 'Fabric calculation failed for this width.');
      }
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
                {uniqueProfiles.map((p) => (
                  <option key={p.measurement_id} value={p.measurement_id}>
                    Existing Client: {p.client_name || 'Customer'} (Bust: {p.bust_cm}cm, Waist: {p.waist_cm}cm, Hip: {p.hip_cm}cm)
                  </option>
                ))}
              </select>
            </div>

            {/* Multi-Task AI Feature Prediction Review & Confirmation (Milestone M14) */}
            <PredictionReview
              garmentAttributes={garmentAttributes}
              confirmedAttributes={confirmedAttributes}
              onConfirm={handleConfirmGarmentAttributes}
              isSubmitting={confirmLoading}
              error={confirmError}
            />

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

              <div className="form-field" style={{ gridColumn: '1/-1' }} data-testid="unit-toggle">
                <label className="form-label">Measurement unit</label>
                <div style={{ display: 'flex', gap: '8px' }}>
                  {['cm', 'in'].map((u) => (
                    <button
                      key={u}
                      type="button"
                      className={unit === u ? 'btn btn-primary' : 'btn btn-outline'}
                      style={{ height: '32px', fontSize: '12px' }}
                      onClick={() => handleUnitToggle(u)}
                      data-testid={`unit-${u}`}
                    >
                      {u === 'cm' ? 'Centimetres (cm)' : 'Inches (in)'}
                    </button>
                  ))}
                  <small style={{ alignSelf: 'center', color: 'var(--text-secondary)' }}>
                    Stored and calculated in cm; inches are converted (1 in = 2.54 cm).
                  </small>
                </div>
              </div>

              {MEASUREMENT_FIELDS.map((field) => {
                const key = field.key;
                const message = fieldErrors[key] || (key === 'armhole_depth_cm' ? fieldErrors.armhole_cm : undefined);
                return (
                  <div className="form-field" key={key}>
                    <label className="form-label" htmlFor={`meas-${key}`}>{field.label} ({unit})</label>
                    <input
                      id={`meas-${key}`}
                      className="form-input"
                      type="number"
                      step="any"
                      value={meas[key]}
                      aria-invalid={message ? 'true' : 'false'}
                      style={message ? { borderColor: '#EF4444' } : undefined}
                      onFocus={() => setActiveField(key)}
                      onChange={(e) => {
                        setError('');
                        setFieldErrors((prev) => {
                          if (!prev[key]) return prev;
                          const { [key]: _removed, ...rest } = prev;
                          return rest;
                        });
                        setMeas({ ...meas, [key]: e.target.value });
                      }}
                      placeholder={`Enter ${field.label.toLowerCase()}`}
                    />
                    <small style={{ color: 'var(--text-muted)', fontSize: '10px' }}>Plausible: {rangeText(field)}</small>
                    {message && (
                      <div role="alert" data-testid={`error-${key}`} style={{ color: '#B91C1C', fontSize: '11px', marginTop: '2px' }}>
                        {message}
                      </div>
                    )}
                  </div>
                );
              })}

              <div className="form-field">
                <label className="form-label">Required fit</label>
                <select
                  className="form-select"
                  value={meas.fit_preference}
                  onChange={(e) => setMeas({ ...meas, fit_preference: e.target.value })}
                >
                  <option value="close">Close fit</option>
                  <option value="standard">Standard fit</option>
                  <option value="loose">Loose fit</option>
                </select>
              </div>

              <div className="form-field">
                <label className="form-label">Fabric type / stretch</label>
                <select
                  className="form-select"
                  value={meas.fabric_type}
                  onChange={(e) => setMeas({ ...meas, fabric_type: e.target.value })}
                >
                  <option value="woven">Woven (no stretch)</option>
                  <option value="knit">Knit (moderate stretch)</option>
                  <option value="stretch-knit">Stretch-knit (high stretch)</option>
                </select>
              </div>

              <div className="form-field" style={{ gridColumn: '1/-1' }}>
                <FabricRecommendation
                  detectedFeatures={features}
                  selectedFabricId={selectedFabricId}
                  onSelectFabric={(id, name, type) => {
                    setSelectedFabricId(id);
                    setSelectedFabricName(name);
                    setMeas((prev) => ({ ...prev, fabric_type: type || prev.fabric_type }));
                    setFabricValidationError('');
                    setError('');
                  }}
                  validationError={fabricValidationError}
                />
              </div>
            </div>

            {/* Interactive Measurement Guide Component */}
            <MeasurementGuide activeField={activeField} setActiveField={setActiveField} meas={meas} />

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
              <div style={{ fontSize: '12px', fontWeight: '500', color: 'var(--text-secondary)', marginBottom: '8px' }}>Fabric Bolt Width (Click to dynamic re-calculate layout)</div>
              <div style={{ display: 'flex', gap: '8px' }}>
                <button
                  className={fabricWidth === 90 ? "btn btn-primary" : "btn btn-outline"}
                  style={{ flex: 1 }}
                  onClick={() => handleFabricWidthChange(90)}
                >
                  90 cm (Narrow)
                </button>
                <button
                  className={fabricWidth === 114 ? "btn btn-primary" : "btn btn-outline"}
                  style={{ flex: 1 }}
                  onClick={() => handleFabricWidthChange(114)}
                >
                  114 cm (Standard)
                </button>
                <button
                  className={fabricWidth === 150 ? "btn btn-primary" : "btn btn-outline"}
                  style={{ flex: 1 }}
                  onClick={() => handleFabricWidthChange(150)}
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
                  {(features.garment_type || 'GARMENT').toUpperCase()} · {features.neckline || 'Custom neckline'} · {features.sleeves || 'Custom sleeves'} · {meas.fabric_type} fabric
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
                      {(features.garment_type || 'GARMENT').toUpperCase()}
                    </div>
                    <div className="r-lbl">Garment Style</div>
                  </div>
                  <div className="result-tile">
                    <div className="r-val" style={{ color: 'var(--text-accent)' }}>
                      {resultOrNA(yardageData?.yardage_metres, 'm')}
                    </div>
                    <div className="r-lbl">Fabric Required</div>
                  </div>
                  <div className="result-tile">
                    <div className="r-val" style={{ color: 'var(--text-accent)' }}>
                      {resultOrNA(yardageData?.utilisation_percent, '%')}
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
                            d={
                              features.sleeves === 'puff sleeve'
                                ? "M 15 25 C 30 -20, 90 -20, 105 25 L 95 150 L 5 150 Z"
                                : (features.sleeves === 'bell sleeve' || features.sleeves === 'flared sleeve' || features.sleeves === 'ruffle sleeve' || features.sleeves === 'tiered sleeve')
                                  ? "M 20 0 C 60 -15, 100 0, 110 40 L 140 160 L -20 160 L 0 40 Z"
                                  : (features.sleeves === 'bishop sleeve' || features.sleeves === 'balloon sleeve' || features.sleeves === 'lantern sleeve')
                                    ? "M 15 0 C 55 -15, 95 0, 105 35 L 125 135 L -5 135 L 5 35 Z M 15 140 L 105 140 L 105 155 L 15 155 Z"
                                    : features.sleeves === 'leg-o\'-mutton sleeve'
                                      ? "M 15 20 C 25 -25, 95 -25, 110 20 L 75 160 L 45 160 L 0 40 Z"
                                      : (features.sleeves === 'cap sleeve' || features.sleeves === 'petal sleeve')
                                        ? "M 15 0 C 55 -15, 95 0, 105 30 L 95 70 C 60 85, 40 85, 10 70 Z"
                                        : (features.sleeves === 'cold shoulder sleeve' || features.sleeves === 'slit sleeve')
                                          ? "M 15 20 C 35 35, 85 35, 105 20 L 90 150 L 10 150 Z"
                                          : (features.sleeves === 'cape sleeve' || features.sleeves === 'butterfly sleeve')
                                            ? "M 20 0 C 60 -15, 100 0, 110 30 L 150 120 C 90 150, 40 150, -20 120 Z"
                                            : "M 20 0 C 60 -15, 100 0, 110 40 L 90 150 L 0 150 L -10 40 Z"
                            }
                            fill="#0F172A" stroke="#74C69D" strokeWidth="2"
                          />
                          <text x="18" y="70" fill="#F8FAFC" fontSize="11" fontWeight="bold">
                            {features.sleeves === 'single sleeve' || features.neckline === 'one-shoulder' ? 'SLEEVE (Single)' : `SLEEVE (L: ${features.sleeves.split(' ')[0]})`}
                          </text>
                          <text x="20" y="90" fill="#94A3B8" fontSize="9">
                            {features.sleeves === 'puff sleeve'
                              ? '30.5cm × 20cm (Gathers)'
                              : (features.sleeves === 'bell sleeve' || features.sleeves === 'flared sleeve')
                                ? '43.5cm × 56cm (Flared)'
                                : (features.sleeves === 'bishop sleeve' || features.sleeves === 'balloon sleeve')
                                  ? '40cm × 58cm (+ Cuff)'
                                  : features.sleeves === 'leg-o\'-mutton sleeve'
                                    ? '30.5cm × 58cm (Puff/Tight)'
                                    : features.sleeves === 'cap sleeve'
                                      ? '26cm × 10cm (Cap)'
                                      : features.sleeves === 'cold shoulder sleeve'
                                        ? '27.5cm × 50cm (Cutout)'
                                        : features.sleeves === 'cape sleeve'
                                          ? '47.5cm × 35cm (Drape)'
                                          : features.sleeves === 'long sleeve'
                                            ? '27.5cm × 58cm'
                                            : features.sleeves === 'three-quarter sleeve'
                                              ? '27.5cm × 45cm'
                                              : features.sleeves === 'elbow sleeve'
                                                ? '27.5cm × 32cm'
                                                : '27.5cm × 22cm'}
                          </text>
                        </g>
                      )}

                      {features.sleeves !== 'sleeveless' && features.sleeves !== 'single sleeve' && features.neckline !== 'one-shoulder' && (
                        <g transform="translate(580, 30)">
                          <path
                            d={
                              features.sleeves === 'puff sleeve'
                                ? "M 15 25 C 30 -20, 90 -20, 105 25 L 95 150 L 5 150 Z"
                                : (features.sleeves === 'bell sleeve' || features.sleeves === 'flared sleeve' || features.sleeves === 'ruffle sleeve' || features.sleeves === 'tiered sleeve')
                                  ? "M 20 0 C 60 -15, 100 0, 110 40 L 140 160 L -20 160 L 0 40 Z"
                                  : (features.sleeves === 'bishop sleeve' || features.sleeves === 'balloon sleeve' || features.sleeves === 'lantern sleeve')
                                    ? "M 15 0 C 55 -15, 95 0, 105 35 L 125 135 L -5 135 L 5 35 Z M 15 140 L 105 140 L 105 155 L 15 155 Z"
                                    : features.sleeves === 'leg-o\'-mutton sleeve'
                                      ? "M 15 20 C 25 -25, 95 -25, 110 20 L 75 160 L 45 160 L 0 40 Z"
                                      : (features.sleeves === 'cap sleeve' || features.sleeves === 'petal sleeve')
                                        ? "M 15 0 C 55 -15, 95 0, 105 30 L 95 70 C 60 85, 40 85, 10 70 Z"
                                        : (features.sleeves === 'cold shoulder sleeve' || features.sleeves === 'slit sleeve')
                                          ? "M 15 20 C 35 35, 85 35, 105 20 L 90 150 L 10 150 Z"
                                          : (features.sleeves === 'cape sleeve' || features.sleeves === 'butterfly sleeve')
                                            ? "M 20 0 C 60 -15, 100 0, 110 30 L 150 120 C 90 150, 40 150, -20 120 Z"
                                            : "M 20 0 C 60 -15, 100 0, 110 40 L 90 150 L 0 150 L -10 40 Z"
                            }
                            fill="#0F172A" stroke="#74C69D" strokeWidth="2"
                          />
                          <text x="18" y="70" fill="#F8FAFC" fontSize="11" fontWeight="bold">
                            {`SLEEVE (R: ${features.sleeves.split(' ')[0]})`}
                          </text>
                          <text x="20" y="90" fill="#94A3B8" fontSize="9">
                            {features.sleeves === 'puff sleeve'
                              ? '30.5cm × 20cm (Gathers)'
                              : (features.sleeves === 'bell sleeve' || features.sleeves === 'flared sleeve')
                                ? '43.5cm × 56cm (Flared)'
                                : (features.sleeves === 'bishop sleeve' || features.sleeves === 'balloon sleeve')
                                  ? '40cm × 58cm (+ Cuff)'
                                  : features.sleeves === 'leg-o\'-mutton sleeve'
                                    ? '30.5cm × 58cm (Puff/Tight)'
                                    : features.sleeves === 'cap sleeve'
                                      ? '26cm × 10cm (Cap)'
                                      : features.sleeves === 'cold shoulder sleeve'
                                        ? '27.5cm × 50cm (Cutout)'
                                        : features.sleeves === 'cape sleeve'
                                          ? '47.5cm × 35cm (Drape)'
                                          : features.sleeves === 'long sleeve'
                                            ? '27.5cm × 58cm'
                                            : features.sleeves === 'three-quarter sleeve'
                                              ? '27.5cm × 45cm'
                                              : features.sleeves === 'elbow sleeve'
                                                ? '27.5cm × 32cm'
                                                : '27.5cm × 22cm'}
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
                    {features.sleeves === 'sleeveless'
                      ? '✓ Sleeveless'
                      : (features.sleeves === 'single sleeve' || features.neckline === 'one-shoulder')
                        ? '✓ Single Sleeve × 1'
                        : ['bishop sleeve', 'balloon sleeve', 'lantern sleeve'].includes(features.sleeves)
                          ? `✓ ${features.sleeves.toUpperCase()} × 2 (+ Cuffs × 2)`
                          : `✓ ${features.sleeves.toUpperCase()} × 2`}
                  </span>
                  <span className="chip" style={{ color: '#2D6A4F', borderColor: '#2D6A4F' }}>✓ Fitted Bust Dart</span>
                </div>

                {/* Mathematical Pattern & Fabric Calculation Breakdown Card */}
                {yardageData && (
                  <div style={{ background: 'var(--surface-1)', border: '1px solid var(--border)', borderRadius: '12px', padding: '18px', marginBottom: '16px' }}>
                    <div style={{ fontSize: '14px', fontWeight: '700', color: 'var(--text-primary)', marginBottom: '14px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span>Fabric & Pattern Requirement Summary</span>
                      <span style={{ fontSize: '11px', background: 'rgba(37, 99, 235, 0.1)', color: '#2563EB', padding: '3px 10px', borderRadius: '12px', fontWeight: '600' }}>
                        Simple User View
                      </span>
                    </div>

                    {/* Level 1: Simple User Summary (Visible by Default) */}
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '10px', marginBottom: '12px' }}>
                      <div style={{ background: 'var(--surface-2)', padding: '12px', borderRadius: '8px' }}>
                        <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginBottom: '2px' }}>Selected Material</div>
                        <div style={{ fontSize: '13px', fontWeight: '700', color: 'var(--text-primary)' }}>{selectedFabricName}</div>
                      </div>
                      <div style={{ background: 'var(--surface-2)', padding: '12px', borderRadius: '8px' }}>
                        <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginBottom: '2px' }}>Fabric Width</div>
                        <div style={{ fontSize: '13px', fontWeight: '700', color: 'var(--text-primary)' }}>
                          {yardageData.full_bolt_width_cm || yardageData.fabric_width_cm || fabricWidth} cm
                        </div>
                      </div>
                      <div style={{ background: 'var(--surface-2)', padding: '12px', borderRadius: '8px' }}>
                        <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginBottom: '2px' }}>Fabric Required</div>
                        <div style={{ fontSize: '13px', fontWeight: '700', color: '#2563EB' }}>
                          {yardageData.purchasing_recommended_m != null || yardageData.yardage_metres != null
                            ? `Approximately ${yardageData.purchasing_recommended_m ?? yardageData.yardage_metres} metres`
                            : NOT_CALCULATED}
                        </div>
                        <div style={{ fontSize: '10px', color: 'var(--text-secondary)', marginTop: '2px' }}>
                          Exact marker: {resultOrNA(yardageData.exact_yardage_metres, 'm')} + {resultOrNA(yardageData.handling_allowance_m, 'm')} allowance
                        </div>
                      </div>
                      <div style={{ background: 'var(--surface-2)', padding: '12px', borderRadius: '8px' }}>
                        <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginBottom: '2px' }}>Cutting Method</div>
                        <div style={{ fontSize: '13px', fontWeight: '700', color: '#16A34A' }}>
                          {yardageData.cutting_method_simple || (yardageData.cutting_mode === 'folded' ? 'Fabric folded lengthwise' : 'Fabric laid open flat')}
                        </div>
                      </div>
                    </div>

                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '10px', marginBottom: '14px' }}>
                      <div style={{ background: 'var(--surface-2)', padding: '12px', borderRadius: '8px', gridColumn: 'span 2' }}>
                        <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginBottom: '2px' }}>Required Pattern Pieces & Quantities</div>
                        <div style={{ fontSize: '12px', fontWeight: '600', color: 'var(--text-primary)' }}>
                          {yardageData.placed_pieces && yardageData.placed_pieces.length > 0
                            ? yardageData.placed_pieces.map(p => `${p.name} ×${p.cut_quantity || 1}`).join(', ')
                            : NOT_CALCULATED}
                        </div>
                      </div>
                      <div style={{ background: 'var(--surface-2)', padding: '12px', borderRadius: '8px' }}>
                        <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginBottom: '2px', display: 'flex', alignItems: 'center', gap: '4px' }}>
                          <span>Fabric Usage</span>
                          <span
                            title="Fabric usage shows how much of the selected fabric area is occupied by pattern pieces. A higher value means less fabric waste."
                            style={{ cursor: 'help', display: 'inline-flex', alignItems: 'center', color: 'var(--text-accent)' }}
                          >
                            <Info size={12} />
                          </span>
                        </div>
                        <div style={{ fontSize: '13px', fontWeight: '700', color: yardageData.utilisation_percent >= 60 ? '#16A34A' : '#D97706' }}>
                          {yardageData.utilisation_percent}% (Waste: {yardageData.waste_percent}%)
                        </div>
                      </div>
                    </div>

                    {/* Usage Status & Recommendation Callout */}
                    <div style={{ background: 'rgba(217, 119, 6, 0.08)', borderLeft: '4px solid #D97706', padding: '12px', borderRadius: '6px', marginBottom: '14px' }}>
                      <div style={{ fontSize: '12px', fontWeight: '700', color: '#D97706', marginBottom: '2px' }}>
                        Fabric Usage Status: {yardageData.usage_status || NOT_CALCULATED}
                      </div>
                      <div style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
                        {yardageData.usage_recommendation || ''}
                      </div>
                    </div>

                    {/* Level 2: Technical Calculation Audit Toggle Button */}
                    <button
                      className="btn btn-outline"
                      onClick={() => setShowTechAudit(!showTechAudit)}
                      style={{
                        width: '100%',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        gap: '8px',
                        padding: '8px 14px',
                        fontSize: '12px',
                        fontWeight: '600',
                        borderRadius: '6px',
                        border: '1px solid var(--border)',
                        background: 'var(--surface-2)',
                        color: 'var(--text-primary)',
                        cursor: 'pointer'
                      }}
                    >
                      {showTechAudit ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                      <span>{showTechAudit ? 'Hide Technical Calculation Audit' : 'View Technical Calculation Audit (Researchers & Advanced Users)'}</span>
                    </button>

                    {/* Level 2: Collapsed Technical Calculation Audit Panel */}
                    {showTechAudit && (
                      <div style={{ marginTop: '14px', background: 'var(--surface-2)', border: '1px solid var(--border)', borderRadius: '10px', padding: '16px' }}>
                        <div style={{ fontSize: '13px', fontWeight: '700', color: 'var(--text-primary)', marginBottom: '10px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <span>Technical Calculation Audit (Thesis Evidence)</span>
                          <span style={{ fontSize: '10px', background: 'rgba(22, 163, 74, 0.1)', color: '#16A34A', padding: '2px 6px', borderRadius: '4px', fontWeight: '600' }}>
                            Mathematical Model Verified
                          </span>
                        </div>

                        {/* Audit Summary Grid */}
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '8px', marginBottom: '12px', fontSize: '11px' }}>
                          <div style={{ background: 'var(--surface-1)', padding: '8px', borderRadius: '6px' }}>
                            <div style={{ color: 'var(--text-secondary)', fontSize: '10px' }}>Folded Usable Width</div>
                            <div style={{ fontWeight: '700' }}>{resultOrNA(yardageData.usable_width_cm, ' cm')}</div>
                          </div>
                          <div style={{ background: 'var(--surface-1)', padding: '8px', borderRadius: '6px' }}>
                            <div style={{ color: 'var(--text-secondary)', fontSize: '10px' }}>Marker Length Needed</div>
                            <div style={{ fontWeight: '700' }}>{yardageData.fabric_length_cm} cm</div>
                          </div>
                          <div style={{ background: 'var(--surface-1)', padding: '8px', borderRadius: '6px' }}>
                            <div style={{ color: 'var(--text-secondary)', fontSize: '10px' }}>Total Pattern Area</div>
                            <div style={{ fontWeight: '700' }}>{resultOrNA(yardageData.total_pattern_piece_area_cm2 ?? yardageData.total_pattern_piece_area, ' cm²')}</div>
                          </div>
                          <div style={{ background: 'var(--surface-1)', padding: '8px', borderRadius: '6px' }}>
                            <div style={{ color: 'var(--text-secondary)', fontSize: '10px' }}>Usable Fabric Area</div>
                            <div style={{ fontWeight: '700' }}>{resultOrNA(yardageData.usable_area_cm2, ' cm²')}</div>
                          </div>
                        </div>

                        {/* Formulas & Calculation Details */}
                        <div style={{ fontSize: '10px', color: 'var(--text-secondary)', background: 'var(--surface-1)', padding: '10px', borderRadius: '6px', marginBottom: '12px', fontFamily: 'monospace' }}>
                          <div>usable_area = usable_folded_width_cm ({yardageData.usable_width_cm}cm) × marker_length_cm ({yardageData.fabric_length_cm}cm) = {yardageData.usable_area_cm2} cm²</div>
                          <div>efficiency_percentage = (total_pattern_area [{yardageData.total_pattern_piece_area_cm2}cm²] / usable_area [{yardageData.usable_area_cm2}cm²]) × 100 = {yardageData.utilisation_percent}%</div>
                          <div>waste_area_cm2 = usable_area ({yardageData.usable_area_cm2}cm²) - total_pattern_area ({yardageData.total_pattern_piece_area_cm2}cm²) = {yardageData.waste_cm2} cm²</div>
                        </div>

                        {/* Placed Pieces Table */}
                        {yardageData.placed_pieces && yardageData.placed_pieces.length > 0 && (
                          <div style={{ overflowX: 'auto', marginBottom: '12px' }}>
                            <table style={{ width: '100%', fontSize: '11px', borderCollapse: 'collapse', color: 'var(--text-primary)' }}>
                              <thead>
                                <tr style={{ background: 'var(--surface-1)', borderBottom: '1px solid var(--border)', textAlign: 'left' }}>
                                  <th style={{ padding: '6px 8px' }}>Piece Name</th>
                                  <th style={{ padding: '6px 8px' }}>Cut Quantity</th>
                                  <th style={{ padding: '6px 8px' }}>Cut on Fold</th>
                                  <th style={{ padding: '6px 8px' }}>Bounding Box (W × H)</th>
                                  <th style={{ padding: '6px 8px' }}>Polygon Area</th>
                                  <th style={{ padding: '6px 8px' }}>Position (X, Y)</th>
                                  <th style={{ padding: '6px 8px' }}>Rotation</th>
                                </tr>
                              </thead>
                              <tbody>
                                {yardageData.placed_pieces.map((p, idx) => (
                                  <tr key={idx} style={{ borderBottom: '1px solid var(--border)' }}>
                                    <td style={{ padding: '6px 8px', fontWeight: '600' }}>{p.name}</td>
                                    <td style={{ padding: '6px 8px' }}>{p.cut_quantity || 1}</td>
                                    <td style={{ padding: '6px 8px' }}>{p.cut_on_fold ? '✓ Yes (Fold Line)' : 'No'}</td>
                                    <td style={{ padding: '6px 8px' }}>
                                      {p.bounding_dimensions ? `${p.bounding_dimensions.width_cm} × ${p.bounding_dimensions.height_cm} cm` : `${p.width} × ${p.height} cm`}
                                    </td>
                                    <td style={{ padding: '6px 8px' }}>{p.polygon_area_cm2 ? `${p.polygon_area_cm2} cm²` : `${(p.width * p.height).toFixed(1)} cm²`}</td>
                                    <td style={{ padding: '6px 8px' }}>
                                      {p.final_nested_position ? `(${p.final_nested_position.x_cm}, ${p.final_nested_position.y_cm})` : `(${p.x}, ${p.y})`}
                                    </td>
                                    <td style={{ padding: '6px 8px' }}>{p.rotation_deg !== undefined ? `${p.rotation_deg}°` : (p.rotated ? '90°' : '0°')}</td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        )}

                        {/* Validation Checks */}
                        {yardageData.validation_checks && (
                          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', fontSize: '10px' }}>
                            <span style={{ padding: '3px 8px', borderRadius: '4px', background: yardageData.validation_checks.no_overlap ? '#DCFCE7' : '#FEE2E2', color: yardageData.validation_checks.no_overlap ? '#166534' : '#991B1B', fontWeight: '600' }}>
                              {yardageData.validation_checks.no_overlap ? '✓ No Overlap Pass' : '✕ Overlap Error'}
                            </span>
                            <span style={{ padding: '3px 8px', borderRadius: '4px', background: yardageData.validation_checks.within_bounds ? '#DCFCE7' : '#FEE2E2', color: yardageData.validation_checks.within_bounds ? '#166534' : '#991B1B', fontWeight: '600' }}>
                              {yardageData.validation_checks.within_bounds ? '✓ Fabric Boundary Pass' : '✕ Boundary Error'}
                            </span>
                            <span style={{ padding: '3px 8px', borderRadius: '4px', background: yardageData.validation_checks.efficiency_in_range ? '#DCFCE7' : '#FEE2E2', color: yardageData.validation_checks.efficiency_in_range ? '#166534' : '#991B1B', fontWeight: '600' }}>
                              {yardageData.validation_checks.efficiency_in_range ? '✓ Efficiency Range Pass (0-100%)' : '✕ Efficiency Error'}
                            </span>
                            <span style={{ padding: '3px 8px', borderRadius: '4px', background: yardageData.validation_checks.theoretical_lower_bound_satisfied ? '#DCFCE7' : '#FEE2E2', color: yardageData.validation_checks.theoretical_lower_bound_satisfied ? '#166534' : '#991B1B', fontWeight: '600' }}>
                              {yardageData.validation_checks.theoretical_lower_bound_satisfied ? '✓ Theoretical Length Bound Pass' : '✕ Length Bound Error'}
                            </span>
                            <span style={{ padding: '3px 8px', borderRadius: '4px', background: yardageData.validation_checks.pattern_dimensions_invariant ? '#DCFCE7' : '#FEE2E2', color: yardageData.validation_checks.pattern_dimensions_invariant ? '#166534' : '#991B1B', fontWeight: '600' }}>
                              {yardageData.validation_checks.pattern_dimensions_invariant ? '✓ Dimension Invariance Pass' : '✕ Dimension Error'}
                            </span>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )}
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
                  {(features.garment_type || 'GARMENT').toUpperCase()}
                </div>
                <div className="r-lbl">Garment Style</div>
              </div>
              <div className="result-tile">
                <div className="r-val" style={{ color: 'var(--text-accent)' }}>
                  {resultOrNA(yardageData?.yardage_metres, 'm')}
                </div>
                <div className="r-lbl">Fabric Required</div>
              </div>
              <div className="result-tile">
                <div className="r-val" style={{ color: 'var(--text-accent)' }}>
                  {resultOrNA(yardageData?.utilisation_percent, '%')}
                </div>
                <div className="r-lbl">Fabric Efficiency</div>
              </div>
            </div>

            {/* PDF Summary Card & Download Action Button */}
            <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap', marginTop: '16px' }}>
              <div className="pdf-card" style={{ flex: 1, minWidth: '280px' }}>
                <div className="pdf-top">
                  <div className="pdf-top-title">Drafting Guide PDF — {features.garment_type}</div>
                  <div className="pdf-top-sub">Includes cutting layout, pattern pieces & construction notes</div>
                </div>
                <div className="pdf-body">
                  <div className="pdf-row">
                    <span className="pdf-row-l">Customer Name</span>
                    <span className="pdf-row-r" style={{ color: 'var(--text-accent)', fontWeight: '600' }}>
                      {meas.client_name || 'Customer Profile'}
                    </span>
                  </div>
                  <div className="pdf-row">
                    <span className="pdf-row-l">Bust with Ease</span>
                    <span className="pdf-row-r">
                      {resultOrNA(patternData?.measurements_used?.eased?.bust_cm, ' cm')}
                    </span>
                  </div>
                  <div className="pdf-row">
                    <span className="pdf-row-l">Waist with Ease</span>
                    <span className="pdf-row-r">
                      {resultOrNA(patternData?.measurements_used?.eased?.waist_cm, ' cm')}
                    </span>
                  </div>
                  <div className="pdf-row">
                    <span className="pdf-row-l">Hip with Ease</span>
                    <span className="pdf-row-r">
                      {resultOrNA(patternData?.measurements_used?.eased?.hip_cm, ' cm')}
                    </span>
                  </div>
                  <div className="pdf-row">
                    <span className="pdf-row-l">Seam Allowance</span>
                    <span className="pdf-row-r">1.5 cm</span>
                  </div>
                  <div className="pdf-row">
                    <span className="pdf-row-l">Fabric Required ({fabricWidth}cm bolt)</span>
                    <span className="pdf-row-r" style={{ color: 'var(--text-accent)', fontWeight: '600' }}>
                      {resultOrNA(yardageData?.yardage_metres, ' metres')}
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
