import { useState, useEffect, useMemo } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import StepIndicator from '../components/StepIndicator';
import LoadingSpinner from '../components/LoadingSpinner';
import MeasurementGuide from '../components/MeasurementGuide';
import FabricRecommendation from '../components/FabricRecommendation';
import PredictionReview from '../components/PredictionReview';
import PatternPreview from '../components/PatternPreview';
import NestingLayout from '../components/NestingLayout';
import { supportReport } from '../utils/designSchema';
import {
  MEASUREMENT_FIELDS, validateMeasurements, convertDisplayValues, parseFieldErrors, buildPayload, rangeText,
} from '../utils/measurementSchema';
import { formatResult, CALCULATION_FAILED, NOT_CALCULATED as NOT_CALCULATED_LABEL } from '../utils/results';
import { friendlyError, imageProblem } from '../utils/friendlyError';
import { getPreferences, widthLabel } from '../utils/preferences';
import {
  imagesAPI, measurementsAPI, patternsAPI, exportAPI, researchAPI,
} from '../services/api';

const CUTTING_MODES = [
  { value: 'auto', label: 'Best layout (recommended)' },
  { value: 'folded', label: 'Fabric folded lengthwise' },
  { value: 'open', label: 'Fabric laid open' },
];

const emptyMeas = {
  client_name: '', bust_cm: '', waist_cm: '', hip_cm: '', height_cm: '', neck_cm: '', shoulder_cm: '',
  across_back_cm: '', back_waist_length_cm: '', armhole_depth_cm: '', garment_length_cm: '', bicep_cm: '',
  sleeve_cm: '', wrist_cm: '', fabric_type: 'woven', fit_preference: 'standard',
};

const profileToMeas = (p) => ({
  client_name: p.client_name || 'Customer Profile',
  ...Object.fromEntries(MEASUREMENT_FIELDS.map((f) => [f.key, p[f.key] ?? (f.key === 'armhole_depth_cm' ? p.armhole_cm : '') ?? ''])),
  fabric_type: p.fabric_type || 'woven',
  fit_preference: p.fit_preference || 'standard',
});

const heading = (title, help) => (
  <div style={{ marginBottom: '16px' }}>
    <h2 style={{ fontSize: '16px', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '4px' }}>{title}</h2>
    {help && <p style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>{help}</p>}
  </div>
);

const navRow = (children) => (
  <div className="wizard-nav" style={{ display: 'flex', gap: '8px', marginTop: '18px', justifyContent: 'flex-end', flexWrap: 'wrap' }}>
    {children}
  </div>
);

export default function Upload() {
  const navigate = useNavigate();
  const location = useLocation();

  // ── wizard state ──────────────────────────────────────────────────────────
  const [step, setStep] = useState(1);
  const [maxStep, setMaxStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [loadingMessage, setLoadingMessage] = useState('');
  const [error, setError] = useState('');

  // step 1 / 2 — image, AI prediction, confirmation
  const [imageFile, setImageFile] = useState(null);
  const [imageId, setImageId] = useState(null);
  const [imagePreview, setImagePreview] = useState(null);
  const [garmentAttributes, setGarmentAttributes] = useState(null);
  const [confirmedAttributes, setConfirmedAttributes] = useState(null);
  const [isAttributesConfirmed, setIsAttributesConfirmed] = useState(false);
  const [confirmLoading, setConfirmLoading] = useState(false);
  const [confirmError, setConfirmError] = useState('');
  const [features, setFeatures] = useState({ garment_type: '', neckline: '', sleeves: '', darts: '', seams: '' });
  // null = unknown (status request failed), true/false = what the server reported
  const [modelAvailable, setModelAvailable] = useState(null);

  // step 3 — measurements
  const [savedProfiles, setSavedProfiles] = useState([]);
  const [measurementId, setMeasurementId] = useState(null);
  const [meas, setMeas] = useState({ ...emptyMeas });
  const [unit, setUnit] = useState(() => getPreferences().unit);
  const [fieldErrors, setFieldErrors] = useState({});
  const [activeField, setActiveField] = useState('bust_cm');

  // step 4 — fabric & fit
  const [selectedFabricId, setSelectedFabricId] = useState('');
  const [selectedFabricName, setSelectedFabricName] = useState('');
  const [fabricValidationError, setFabricValidationError] = useState('');

  // step 5 — pattern
  const [patternId, setPatternId] = useState(null);
  const [patternData, setPatternData] = useState(null);

  // step 6 — estimate
  const [fabricWidth, setFabricWidth] = useState(() => getPreferences().fabricWidth);
  const [cuttingMode, setCuttingMode] = useState('auto');
  const [yardageData, setYardageData] = useState(null);     // the selected width's layout
  const [estimates, setEstimates] = useState(null);         // 36" / 45" / 60" comparison rows
  const [yardageError, setYardageError] = useState(false);

  // step 7 — export
  const [exportId, setExportId] = useState(null);
  const [pdfInfo, setPdfInfo] = useState(null);
  const [pdfDownloaded, setPdfDownloaded] = useState(false);
  const [feedbackScore, setFeedbackScore] = useState(5);
  const [feedbackComment, setFeedbackComment] = useState('');
  const [feedbackSubmitted, setFeedbackSubmitted] = useState(false);
  const [notice, setNotice] = useState('');

  const go = (n) => {
    setError('');
    setStep(n);
    setMaxStep((m) => Math.max(m, n));
  };

  useEffect(() => {
    Promise.resolve(imagesAPI.modelStatus?.())
      .then((res) => { if (res?.data) setModelAvailable(Boolean(res.data.available)); })
      .catch(() => setModelAvailable(null));
  }, []);

  useEffect(() => {
    measurementsAPI.getAll().then((res) => setSavedProfiles(res.data.measurements || [])).catch(() => {});
    if (location.state?.selectedProfile) {
      const p = location.state.selectedProfile;
      setMeas(profileToMeas(p));
      setUnit('cm');
      setFieldErrors({});
      setMeasurementId(p.measurement_id);
    }
  }, [location.state]);

  const uniqueProfiles = useMemo(() => savedProfiles.reduce((acc, cur) => {
    const name = (cur.client_name || '').trim().toLowerCase();
    const dup = acc.some((it) => (it.client_name || '').trim().toLowerCase() === name
      && (name !== '' && name !== 'customer profile' && name !== 'customer'
        ? true
        : it.bust_cm === cur.bust_cm && it.waist_cm === cur.waist_cm && it.hip_cm === cur.hip_cm && it.height_cm === cur.height_cm));
    if (!dup) acc.push(cur);
    return acc;
  }, []), [savedProfiles]);

  const design = supportReport(confirmedAttributes || {});
  const designReady = isAttributesConfirmed && !!confirmedAttributes && design.supported;

  // ── step 1: upload + analyse ──────────────────────────────────────────────
  const handleImageSelect = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const problem = imageProblem(file);
    if (problem) {
      setError(problem);
      return;
    }
    setImageFile(file);
    setImagePreview(URL.createObjectURL(file));
    setError('');
  };

  const handleUploadAndAnalyse = async () => {
    const problem = imageProblem(imageFile);
    if (problem) {
      setError(problem);
      return;
    }
    setLoading(true);
    setLoadingMessage('Uploading and analysing your garment photo…');
    setError('');
    try {
      const formData = new FormData();
      formData.append('image', imageFile);
      const uploadRes = await imagesAPI.upload(formData);
      const newImageId = uploadRes.data.image_id;
      setImageId(newImageId);
      const analyseRes = await imagesAPI.analyse(newImageId);
      setGarmentAttributes(analyseRes.data.garment_attributes || null);
      const ca = analyseRes.data.confirmed_attributes;
      if (ca && Object.keys(ca).length > 0) {
        setConfirmedAttributes(ca);
        setIsAttributesConfirmed(true);
      } else {
        setConfirmedAttributes(null);
        setIsAttributesConfirmed(false);
      }
      if (analyseRes.data.detected_features) setFeatures(analyseRes.data.detected_features);
      go(2);
    } catch (err) {
      setError(friendlyError(err, 'We could not analyse that photo. Please try another photo or choose the design manually.'));
    } finally {
      setLoading(false);
    }
  };

  const chooseManually = () => {
    setImageId(null);
    setGarmentAttributes(null);
    go(2);
  };

  // ── step 2: confirm the design ────────────────────────────────────────────
  const applyConfirmed = (attrs) => {
    setConfirmedAttributes(attrs);
    setIsAttributesConfirmed(true);
    setFeatures((prev) => ({
      ...prev,
      garment_type: attrs.garment_type,
      neckline: attrs.neckline_type,
      sleeves: attrs.sleeve_length,
      sleeve_style: attrs.sleeve_style,
    }));
    // a knit garment defaults to knit fabric; the user can still change it in the fabric step
    setMeas((m) => (attrs.garment_type === 't-shirt' && m.fabric_type === 'woven' ? { ...m, fabric_type: 'knit' } : m));
  };

  const handleConfirmGarmentAttributes = async (confirmedData) => {
    if (!imageId) {
      applyConfirmed(confirmedData);
      return;
    }
    setConfirmLoading(true);
    setConfirmError('');
    try {
      const res = await imagesAPI.confirmAttributes(imageId, confirmedData);
      applyConfirmed(res.data.confirmed_attributes || confirmedData);
    } catch (err) {
      setConfirmError(friendlyError(err, 'We could not save your design choices. Please try again.'));
    } finally {
      setConfirmLoading(false);
    }
  };

  const continueFromReview = () => {
    if (!isAttributesConfirmed) {
      setError('Please review the garment features and press “Confirm design features” first.');
      return;
    }
    if (!design.supported) {
      setError('This design cannot be drafted yet: '
        + design.unsupported.map((u) => `${u.head.replace(/_/g, ' ')} = ${u.label || u.value}`).join('; ')
        + '. Edit the design and confirm a supported option.');
      return;
    }
    go(3);
  };

  // ── step 3: measurements ──────────────────────────────────────────────────
  const handleSelectSavedClient = (profileId) => {
    if (!profileId) {
      setMeas({ ...emptyMeas, fabric_type: meas.fabric_type });
      setFieldErrors({});
      setMeasurementId(null);
      return;
    }
    const found = savedProfiles.find((p) => p.measurement_id === profileId);
    if (found) {
      setMeas(profileToMeas(found));
      setUnit('cm');
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

  const handleSaveMeasurements = async () => {
    if (!designReady) {
      setError('Please confirm a supported design in the AI review step before saving measurements.');
      return;
    }
    const localErrors = validateMeasurements(meas, unit);
    if (Object.keys(localErrors).length > 0) {
      setFieldErrors(localErrors);
      setError('Please correct the highlighted measurements.');
      return;
    }
    setLoading(true);
    setLoadingMessage('Saving measurements…');
    setError('');
    try {
      const payload = {
        client_name: meas.client_name.trim() !== '' ? meas.client_name : 'Customer Profile',
        ...buildPayload(meas, unit),
        fabric_type: meas.fabric_type,
        fit_preference: meas.fit_preference || 'standard',
      };
      const res = measurementId
        ? await measurementsAPI.update(measurementId, payload)
        : await measurementsAPI.save(payload);
      setFieldErrors({});
      setMeasurementId(res.data.measurement_id || res.data.profile_id || measurementId);
      go(4);
    } catch (err) {
      const parsed = parseFieldErrors(err);
      if (parsed._form) {
        setError(friendlyError(err, parsed._form));
      } else {
        setFieldErrors(parsed);
        setError('Please correct the highlighted measurements.');
      }
    } finally {
      setLoading(false);
    }
  };

  // ── step 4: fabric & fit → generate the pattern ───────────────────────────
  const handleGeneratePattern = async () => {
    if (!selectedFabricId) {
      setFabricValidationError('Please choose one of the recommended fabrics to continue.');
      setError('Please choose a fabric before generating the pattern.');
      return;
    }
    setLoading(true);
    setLoadingMessage('Drafting and checking your pattern…');
    setError('');
    setPatternData(null);
    setYardageData(null);
    setExportId(null);
    setPdfInfo(null);
    try {
      await measurementsAPI.update(measurementId, { fabric_type: meas.fabric_type, fit_preference: meas.fit_preference || 'standard' });
      const patRes = await patternsAPI.generate({
        measurement_id: measurementId,
        image_id: imageId || 'manual',
        confirmed_attributes: confirmedAttributes || undefined,
        fabric_id: selectedFabricId,
        fabric_name: selectedFabricName,
      });
      setPatternId(patRes.data.pattern_id);
      setPatternData(patRes.data);
      go(5);
      if (patRes.data.validation_passed === false || patRes.data.fabric_estimate_blocked) {
        const errs = (patRes.data.validation?.errors || []).join(' ');
        setError(errs ? `The pattern failed its automatic checks: ${errs}` : 'The pattern failed its automatic checks, so the fabric estimate is blocked.');
      }
    } catch (err) {
      const code = err.response?.data?.error_code;
      if (code === 'UNSUPPORTED_DESIGN' || code === 'DESIGN_NOT_CONFIRMED' || code === 'CONFIRMED_DESIGN_MISMATCH') {
        go(2);
        setError(friendlyError(err));
      } else if (err.response?.data?.field_errors && Object.keys(err.response.data.field_errors).some((k) => k.endsWith('_cm'))) {
        setFieldErrors(parseFieldErrors(err));
        go(3);
        setError(friendlyError(err, 'Some measurements need attention.') + ' The measurements to check are highlighted.');
      } else {
        setError(friendlyError(err, 'We could not create the pattern. Please check your inputs and try again.'));
      }
    } finally {
      setLoading(false);
    }
  };

  // ── step 6: fabric estimate ───────────────────────────────────────────────
  const NOT_CALCULATED = yardageError ? CALCULATION_FAILED : NOT_CALCULATED_LABEL;
  const resultOrNA = (value, suffix = '') => formatResult(value, suffix, yardageError);

  const runEstimate = async (width = fabricWidth, mode = cuttingMode) => {
    if (!patternId) return;
    setLoading(true);
    setLoadingMessage('Laying out the pattern pieces on your fabric…');
    setError('');
    try {
      // all three standard widths are calculated together; `width` is the one highlighted / used for the PDF
      const res = await exportAPI.estimates(patternId, { selected_width_cm: width, cutting_mode: mode });
      const rows = res.data.estimates || [];
      const sel = rows.find((r) => r.selected);
      setEstimates(rows);
      setFabricWidth(res.data.selected_width_cm ?? width);
      if (sel && sel.fits) {
        setYardageData({
          ...sel,
          fabric_length_cm: sel.base_layout_length_cm,
          purchasing_recommended_m: sel.recommended_purchase_m,
          yardage_yards: sel.recommended_purchase_yd,
          method: res.data.method,
          purchase_rule: res.data.purchase_rule,
        });
        setYardageError(false);
      } else {
        setYardageData(null);
        setYardageError(true);
        setError(sel?.error ? `${widthLabel(sel.fabric_width_cm)}: ${sel.error}` : 'The fabric estimate could not be calculated.');
      }
      setExportId(null);          // a new layout means the previous PDF is out of date
      setPdfInfo(null);
    } catch (err) {
      setYardageData(null);
      setEstimates(null);
      setYardageError(true);
      setError(friendlyError(err, 'The fabric estimate could not be calculated.'));
    } finally {
      setLoading(false);
    }
  };

  const openEstimateStep = () => {
    if (patternData?.validation_passed === false) return;
    go(6);
    if (!yardageData) runEstimate();
  };

  // ── step 7: PDF ───────────────────────────────────────────────────────────
  const handleCreatePdf = async () => {
    setLoading(true);
    setLoadingMessage('Building your printable pattern…');
    setError('');
    try {
      const res = await exportAPI.pdf(patternId);
      setExportId(res.data.export_id);
      setPdfInfo(res.data);
    } catch (err) {
      setError(friendlyError(err, 'The printable pattern could not be created.'));
    } finally {
      setLoading(false);
    }
  };

  const handleDownloadPDF = async () => {
    try {
      const res = await exportAPI.download(exportId);
      const url = window.URL.createObjectURL(new Blob([res.data], { type: 'application/pdf' }));
      const link = document.createElement('a');
      link.href = url;
      link.download = `sewing_pattern_${patternId}.pdf`;
      link.click();
      window.URL.revokeObjectURL(url);
      setPdfDownloaded(true);
      setNotice('Your pattern has downloaded. Print it at 100% (Actual size) and check the 5 cm square.');
    } catch (err) {
      setError(friendlyError(err, 'The download failed. Please try again.'));
    }
  };

  const handleFeedbackSubmit = async (e) => {
    e.preventDefault();
    try {
      await researchAPI.submitFeedback({ pattern_id: patternId, feedback_score: feedbackScore, feedback_comment: feedbackComment });
      setFeedbackSubmitted(true);
    } catch (err) {
      setError(friendlyError(err, 'Your feedback could not be sent. Please try again.'));
    }
  };

  const validationBlocked = patternData?.validation_passed === false;

  // ── render ────────────────────────────────────────────────────────────────
  return (
    <div className="view active" id="v-wizard">
      <div className="wizard-container">
        <StepIndicator currentStep={step} setStep={(n) => { setError(''); setStep(n); }} maxStep={maxStep} pdfDownloaded={pdfDownloaded} />

        {error && (
          <div role="alert" className="wizard-alert" style={{ margin: '16px 24px 0', padding: '10px 14px', background: '#FDECEA', border: '1px solid #E4A19B', borderRadius: 'var(--radius)', fontSize: '12px', color: '#7A1F17' }}>
            {error}
          </div>
        )}
        {notice && !error && (
          <div role="status" style={{ margin: '16px 24px 0', padding: '10px 14px', background: '#E7F2EC', border: '1px solid #A8D2BC', borderRadius: 'var(--radius)', fontSize: '12px', color: '#0D503A' }}>
            {notice}
          </div>
        )}

        {loading && <div className="wizard-body"><LoadingSpinner message={loadingMessage} /></div>}

        {/* ── 1 UPLOAD ── */}
        {!loading && step === 1 && (
          <div className="wizard-body" id="wp1">
            {heading('Upload a garment photo', 'Use a clear front-view photo of a blouse, T-shirt or crop-top (JPG, PNG or WEBP, up to 16 MB). The AI suggests the design; you stay in control and confirm it.')}
            {modelAvailable === false && (
              <div role="status" data-testid="model-unavailable" style={{ marginBottom: '14px', padding: '10px 14px', background: '#FEF3C7', border: '1px solid #F59E0B', borderRadius: 'var(--radius)', fontSize: '12px', color: '#92400E' }}>
                The AI garment model is not available on this server, so photos cannot be analysed right now.
                Please choose the design manually — the pattern is drafted the same way.
              </div>
            )}
            <label className="upload-zone" style={{ display: 'block' }}>
              <span className="sr-only">Choose garment photo</span>
              <input type="file" accept="image/jpeg,image/png,image/webp" onChange={handleImageSelect} className="hidden" data-testid="image-input" />
              {imagePreview ? (
                <div>
                  <img src={imagePreview} alt="Selected garment preview" style={{ maxHeight: '200px', maxWidth: '100%', margin: '0 auto 10px', borderRadius: '8px' }} />
                  <div className="upload-title">{imageFile?.name}</div>
                  <div className="upload-sub">Click to choose a different photo</div>
                </div>
              ) : (
                <>
                  <div className="upload-title">Click to choose a photo, or drop it here</div>
                  <div className="upload-sub">JPG, PNG or WEBP · maximum 16 MB</div>
                </>
              )}
            </label>
            {navRow(<>
              <button type="button" className="btn btn-outline" onClick={chooseManually}>No photo — choose the design manually</button>
              <button type="button" className="btn btn-primary" onClick={handleUploadAndAnalyse} disabled={!imageFile || modelAvailable === false}>Upload and analyse</button>
            </>)}
          </div>
        )}

        {/* ── 2 AI REVIEW ── */}
        {!loading && step === 2 && (
          <div className="wizard-body" id="wp2">
            {heading('Review the AI suggestion', 'The AI can make mistakes, especially on necklines and sleeve styles. Check each item, change anything that is wrong, then confirm.')}
            <PredictionReview
              garmentAttributes={garmentAttributes}
              confirmedAttributes={confirmedAttributes}
              onConfirm={handleConfirmGarmentAttributes}
              isSubmitting={confirmLoading}
              error={confirmError}
            />
            {navRow(<>
              <button type="button" className="btn btn-outline" onClick={() => go(1)}>Back</button>
              <button type="button" className="btn btn-primary" onClick={continueFromReview} disabled={!designReady}>Continue to measurements</button>
            </>)}
          </div>
        )}

        {/* ── 3 MEASUREMENTS ── */}
        {!loading && step === 3 && (
          <div className="wizard-body" id="wp3">
            {heading('Body measurements', 'Every measurement is needed to draft a pattern that fits. Use the guide beside the form for how to measure each one.')}
            <div style={{ background: 'var(--surface-1)', border: '1px solid var(--border)', borderRadius: 'var(--radius)', padding: '12px 14px', marginBottom: '14px' }}>
              <label className="form-label" htmlFor="saved-client">Customer</label>
              <select id="saved-client" className="form-select" value={measurementId || ''} onChange={(e) => handleSelectSavedClient(e.target.value)}>
                <option value="">New customer — type the name and measurements below</option>
                {uniqueProfiles.map((p) => (
                  <option key={p.measurement_id} value={p.measurement_id}>
                    {p.client_name || 'Customer'} (bust {p.bust_cm} cm, waist {p.waist_cm} cm, hip {p.hip_cm} cm)
                  </option>
                ))}
              </select>
            </div>

            <div className="form-grid">
              <div className="form-field" style={{ gridColumn: '1/-1' }}>
                <label className="form-label" htmlFor="client-name">Customer name</label>
                <input id="client-name" className="form-input" type="text" value={meas.client_name}
                       onChange={(e) => setMeas({ ...meas, client_name: e.target.value })} placeholder="e.g. Amara Silva" />
              </div>

              <div className="form-field" style={{ gridColumn: '1/-1' }} data-testid="unit-toggle">
                <span className="form-label" id="unit-label">Measurement unit</span>
                <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }} role="group" aria-labelledby="unit-label">
                  {['cm', 'in'].map((u) => (
                    <button key={u} type="button" className={unit === u ? 'btn btn-primary' : 'btn btn-outline'} aria-pressed={unit === u}
                            style={{ height: '34px' }} onClick={() => handleUnitToggle(u)} data-testid={`unit-${u}`}>
                      {u === 'cm' ? 'Centimetres (cm)' : 'Inches (in)'}
                    </button>
                  ))}
                  <small style={{ alignSelf: 'center', color: 'var(--text-secondary)' }}>Inches are converted exactly (1 in = 2.54 cm).</small>
                </div>
              </div>

              {MEASUREMENT_FIELDS.map((field) => {
                const key = field.key;
                const message = fieldErrors[key] || (key === 'armhole_depth_cm' ? fieldErrors.armhole_cm : undefined);
                return (
                  <div className="form-field" key={key}>
                    <label className="form-label" htmlFor={`meas-${key}`}>{field.label} ({unit})</label>
                    <input id={`meas-${key}`} className="form-input" type="number" step="any" inputMode="decimal"
                           value={meas[key]} aria-invalid={message ? 'true' : 'false'}
                           aria-describedby={`hint-${key}`}
                           style={message ? { borderColor: '#B23B3B' } : undefined}
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
                           placeholder={`Enter ${field.label.toLowerCase()}`} />
                    <small id={`hint-${key}`} style={{ color: 'var(--text-secondary)', fontSize: '11px' }}>Typical range: {rangeText(field)}</small>
                    {message && (
                      <div role="alert" data-testid={`error-${key}`} style={{ color: '#9B2C2C', fontSize: '12px', marginTop: '2px' }}>{message}</div>
                    )}
                  </div>
                );
              })}
            </div>

            <MeasurementGuide activeField={activeField} setActiveField={setActiveField} meas={meas} />

            {navRow(<>
              <button type="button" className="btn btn-outline" onClick={() => go(2)}>Back</button>
              <button type="button" className="btn btn-primary" onClick={handleSaveMeasurements}>Save and continue</button>
            </>)}
          </div>
        )}

        {/* ── 4 FABRIC & FIT ── */}
        {!loading && step === 4 && (
          <div className="wizard-body" id="wp4">
            {heading('Fabric and fit', 'Choose how loose you want the garment and pick a fabric. The system explains why each fabric suits your design.')}
            <div className="form-grid">
              <div className="form-field">
                <label className="form-label" htmlFor="fit-pref">Fit</label>
                <select id="fit-pref" className="form-select" value={meas.fit_preference} onChange={(e) => setMeas({ ...meas, fit_preference: e.target.value })}>
                  <option value="close">Close fit</option>
                  <option value="standard">Standard fit</option>
                  <option value="loose">Loose fit</option>
                </select>
              </div>
              <div className="form-field">
                <span className="form-label">Fabric construction</span>
                <p className="muted small" data-testid="fabric-construction">
                  {meas.fabric_type === 'knit' ? 'Knit' : 'Woven'} — set by the chosen fabric (it decides the drafting block).
                </p>
              </div>
              <div className="form-field" style={{ gridColumn: '1/-1' }}>
                <FabricRecommendation
                  confirmedAttributes={confirmedAttributes}
                  fitPreference={meas.fit_preference}
                  selectedFabricId={selectedFabricId}
                  onSelectFabric={(id, name, type) => {
                    setSelectedFabricId(id);
                    setSelectedFabricName(name);
                    setMeas((prev) => ({ ...prev, fabric_type: type === 'knit' || type === 'stretch-knit' ? 'knit' : (type || prev.fabric_type) }));
                    setFabricValidationError('');
                    setError('');
                  }}
                  validationError={fabricValidationError}
                />
              </div>
            </div>
            <div style={{ marginTop: '14px', padding: '10px 14px', background: 'var(--surface-2)', borderRadius: 'var(--radius)', fontSize: '12px', color: 'var(--text-secondary)' }}>
              Summary: {(confirmedAttributes?.garment_type || '').replace(/-/g, ' ')}, {(confirmedAttributes?.neckline_type || '').replace(/-/g, ' ')},
              {' '}{(confirmedAttributes?.sleeve_length || '').replace(/-/g, ' ')} · {meas.fit_preference} fit · {selectedFabricName || 'no fabric chosen yet'}
            </div>
            {navRow(<>
              <button type="button" className="btn btn-outline" onClick={() => go(3)}>Back</button>
              <button type="button" className="btn btn-primary" onClick={handleGeneratePattern}>Confirm and generate pattern</button>
            </>)}
          </div>
        )}

        {/* ── 5 PATTERN PREVIEW ── */}
        {!loading && step === 5 && patternData && (
          <div className="wizard-body" id="wp5">
            {heading('Your pattern', 'Drafted from your measurements and confirmed design, then checked automatically.')}
            <PatternPreview
              pieces={patternData?.pattern_pieces}
              fabricWidth={fabricWidth}
              validation={patternData?.validation}
              draftingBlock={patternData?.drafting_block}
              armholeSleeve={patternData?.armhole_sleeve}
              transformations={patternData?.final_pattern?.transformations}
            />
            {navRow(<>
              <button type="button" className="btn btn-outline" onClick={() => go(4)}>Back</button>
              <button type="button" className="btn btn-primary" onClick={openEstimateStep} disabled={validationBlocked}>Continue to fabric estimate</button>
            </>)}
          </div>
        )}

        {/* ── 6 FABRIC ESTIMATE ── */}
        {!loading && step === 6 && (
          <div className="wizard-body" id="wp6">
            {heading('Fabric estimate', 'The pattern pieces (with seam allowance) are laid out on the fabric to find how much cloth to buy.')}
            <div className="form-field" style={{ maxWidth: '360px' }}>
              <label className="form-label" htmlFor="cut-mode">Cutting layout</label>
              <select id="cut-mode" className="form-select" value={cuttingMode} onChange={(e) => { setCuttingMode(e.target.value); runEstimate(fabricWidth, e.target.value); }}>
                {CUTTING_MODES.map((m) => <option key={m.value} value={m.value}>{m.label}</option>)}
              </select>
            </div>

            {estimates && (
              <div className="table-wrap width-compare" data-testid="width-comparison">
                <table className="hist-table">
                  <caption className="sr-only">Fabric requirement for the three standard widths</caption>
                  <thead><tr><th>Fabric width</th><th>Base layout length</th><th>Purchasing allowance</th><th>Recommended purchase</th><th>Utilisation</th><th>Waste</th><th><span className="sr-only">Select</span></th></tr></thead>
                  <tbody>
                    {estimates.map((e) => (
                      <tr key={e.fabric_width_cm} className={e.selected ? 'row-selected' : ''} data-testid={`estimate-row-${e.fabric_width_in}`}>
                        <td><strong>{e.fabric_width_in}"</strong><small>{e.fabric_width_cm} cm</small></td>
                        {e.fits ? (
                          <>
                            <td>{e.base_layout_length_cm} cm<small>{e.cutting_mode === 'folded' ? 'folded' : 'open'}</small></td>
                            <td>{e.purchasing_allowance_cm} cm</td>
                            <td><strong>{e.recommended_purchase_m} m</strong><small>{e.recommended_purchase_yd} yd</small></td>
                            <td>{e.utilisation_percent}%</td>
                            <td>{e.waste_percent}%</td>
                          </>
                        ) : (
                          <td colSpan={5} className="cell-warning">Does not fit: {e.error}</td>
                        )}
                        <td>
                          <button type="button" className={e.selected ? 'btn btn-primary btn-sm' : 'btn btn-outline btn-sm'} aria-pressed={e.selected}
                                  data-testid={`width-${e.fabric_width_in}`} disabled={!e.fits}
                                  onClick={() => runEstimate(e.fabric_width_cm, cuttingMode)}>{e.selected ? 'Selected' : 'Use'}</button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {estimates.flatMap((e) => (e.warnings || []).map((w) => `${e.fabric_width_in}": ${w}`)).map((w) => <p key={w} className="muted small">{w}</p>)}
              </div>
            )}

            <div className="result-grid" style={{ marginTop: '16px' }} data-testid="estimate-results">
              <div className="result-tile"><div className="r-val">{resultOrNA(yardageData?.purchasing_recommended_m, ' m')}</div><div className="r-lbl">Recommended purchase</div></div>
              <div className="result-tile"><div className="r-val">{resultOrNA(yardageData?.fabric_length_cm, ' cm')}</div><div className="r-lbl">Layout length</div></div>
              <div className="result-tile"><div className="r-val">{resultOrNA(yardageData?.utilisation_percent, '%')}</div><div className="r-lbl">Fabric used by pieces</div></div>
            </div>

            {yardageData && (
              <>
                <p style={{ fontSize: '12px', color: 'var(--text-secondary)', margin: '12px 0' }}>
                  Layout for {widthLabel(yardageData.fabric_width_cm)}: {yardageData.cutting_method_simple} · {yardageData.recommended_purchase_yd} yd.
                </p>
                <NestingLayout nesting={yardageData} />
                <details style={{ marginTop: '12px', fontSize: '12px', color: 'var(--text-secondary)' }}>
                  <summary style={{ cursor: 'pointer', fontWeight: 600 }}>How this was calculated</summary>
                  <ul style={{ paddingLeft: '18px', marginTop: '6px' }}>
                    <li>{yardageData.method}</li>
                    <li>{yardageData.purchase_rule}</li>
                  </ul>
                </details>
              </>
            )}
            {navRow(<>
              <button type="button" className="btn btn-outline" onClick={() => go(5)}>Back</button>
              <button type="button" className="btn btn-primary" onClick={() => go(7)} disabled={!yardageData}>Continue to PDF export</button>
            </>)}
          </div>
        )}

        {/* ── 7 PDF EXPORT ── */}
        {!loading && step === 7 && (
          <div className="wizard-body" id="wp7">
            {heading('Printable pattern (PDF)', 'A full-size pattern that prints on ordinary A4 paper and is taped together from tiles.')}
            <ol style={{ paddingLeft: '18px', fontSize: '12px', color: 'var(--text-secondary)', lineHeight: 1.7, marginBottom: '14px' }}>
              <li>Print with the scale set to <strong>100% / Actual size</strong>. Never “fit to page”.</li>
              <li>Measure the 5 cm calibration square on the first page before you tape the pages together.</li>
              <li>Make a test garment (muslin) first — this is a prototype pattern, not a fit-tested one.</li>
            </ol>
            {!exportId ? (
              <button type="button" className="btn btn-primary btn-lg" onClick={handleCreatePdf} disabled={!yardageData}>Create printable PDF</button>
            ) : (
              <div className="pdf-card" data-testid="pdf-ready">
                <div className="pdf-top"><div className="pdf-top-title">Your pattern is ready</div>
                  <div className="pdf-top-sub">{pdfInfo?.pages} pages · A4 · 1:1 scale</div></div>
                <div className="pdf-body">
                  <button type="button" className="btn btn-primary" onClick={handleDownloadPDF}>Download PDF</button>
                </div>
              </div>
            )}
            {pdfDownloaded && !feedbackSubmitted && (
              <form onSubmit={handleFeedbackSubmit} style={{ marginTop: '20px' }} aria-label="Feedback">
                <div className="form-field">
                  <label className="form-label" htmlFor="fb-score">How easy was it to create this pattern?</label>
                  <select id="fb-score" className="form-select" value={feedbackScore} onChange={(e) => setFeedbackScore(Number(e.target.value))}>
                    {[5, 4, 3, 2, 1].map((n) => <option key={n} value={n}>{n} — {['', 'very hard', 'hard', 'okay', 'easy', 'very easy'][n]}</option>)}
                  </select>
                </div>
                <div className="form-field" style={{ marginTop: '8px' }}>
                  <label className="form-label" htmlFor="fb-comment">Comments (optional)</label>
                  <textarea id="fb-comment" className="form-input" style={{ height: '70px', padding: '8px 12px' }} value={feedbackComment} onChange={(e) => setFeedbackComment(e.target.value)} />
                </div>
                <button type="submit" className="btn btn-outline" style={{ marginTop: '8px' }}>Send feedback</button>
              </form>
            )}
            {feedbackSubmitted && <p role="status" style={{ marginTop: '14px', fontSize: '12px', color: 'var(--text-accent)' }}>Thank you — your feedback was saved.</p>}
            {navRow(<>
              <button type="button" className="btn btn-outline" onClick={() => go(6)}>Back</button>
              <button type="button" className="btn btn-outline" onClick={() => navigate('/history')}>Open pattern library</button>
              <button type="button" className="btn btn-primary" onClick={() => navigate('/dashboard')}>Finish</button>
            </>)}
          </div>
        )}
      </div>
    </div>
  );
}
