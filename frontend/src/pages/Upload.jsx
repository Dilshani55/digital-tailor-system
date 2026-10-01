import { useState, useEffect, useMemo } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import {
  ArrowRight, Calendar, CheckCircle2, Download, FileText, FolderOpen, Grid3x3, ImageUp, PencilLine, Printer, Ruler, Scissors,
} from 'lucide-react';
import StepIndicator from '../components/StepIndicator';
import LoadingSpinner from '../components/LoadingSpinner';
import MeasureFigure from '../components/MeasureFigure';
import FabricRecommendation from '../components/FabricRecommendation';
import PredictionReview from '../components/PredictionReview';
import PatternPreview from '../components/PatternPreview';
import NestingLayout from '../components/NestingLayout';
import TilePreview from '../components/TilePreview';
import GarmentIllustration from '../components/GarmentIllustration';
import { supportReport, labelOf } from '../utils/designSchema';
import {
  MEASUREMENT_FIELDS, LABELS, requiredFor, validateMeasurements, displayValue, canonicalCm, parseFieldErrors, buildPayload,
} from '../utils/measurementSchema';
import { GUIDES } from '../utils/measurementGuides';
import { formatResult } from '../utils/results';
import { friendlyError, imageProblem } from '../utils/friendlyError';
import { getPreferences, widthLabel } from '../utils/preferences';
import { setUnsaved, beforeUnloadHandler } from '../utils/unsavedChanges';
import {
  imagesAPI, measurementsAPI, patternsAPI, exportAPI, researchAPI,
} from '../services/api';

// Step numbers (see StepIndicator.WIZARD_STEPS)
const S = { CUSTOMER: 1, UPLOAD: 2, REVIEW: 3, MEASURE: 4, FABRIC: 5, PREVIEW: 6, ESTIMATE: 7, EXPORT: 8 };

const CUTTING_MODES = [
  { value: 'auto', label: 'Best layout (recommended)' },
  { value: 'folded', label: 'Fabric folded lengthwise' },
  { value: 'open', label: 'Fabric laid open' },
];
const FITS = [
  { value: 'close', label: 'Fitted', note: 'Close to the body' },
  { value: 'standard', label: 'Regular', note: 'Standard ease' },
  { value: 'loose', label: 'Relaxed', note: 'More ease' },
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

const EmptyState = ({ title, children, action, onAction }) => (
  <div className="section-card empty-step" role="status" data-testid="step-empty">
    <h3>{title}</h3>
    <p className="form-hint">{children}</p>
    {action && <button type="button" className="btn btn-outline" onClick={onAction}>{action}</button>}
  </div>
);

const Title = ({ title, help }) => (
  <div className="wizard-title">
    <h2>{title}</h2>
    {help && <p>{help}</p>}
  </div>
);

const NavRow = ({ children }) => <div className="wizard-nav">{children}</div>;

export default function Upload() {
  const navigate = useNavigate();
  const location = useLocation();

  // ── wizard state ──────────────────────────────────────────────────────────
  const [step, setStep] = useState(S.CUSTOMER);
  const [started, setStarted] = useState(false);          // the user has begun (drives the unsaved-changes guard)
  const [loading, setLoading] = useState(false);
  const [loadingMessage, setLoadingMessage] = useState('');
  const [error, setError] = useState('');

  // customer & design
  const [customerContact, setCustomerContact] = useState('');
  const [projectName, setProjectName] = useState('');

  // image, AI prediction, confirmation
  const [imageFile, setImageFile] = useState(null);
  const [imageId, setImageId] = useState(null);
  const [imagePreview, setImagePreview] = useState(null);
  const [garmentAttributes, setGarmentAttributes] = useState(null);
  const [confirmedAttributes, setConfirmedAttributes] = useState(null);
  const [isAttributesConfirmed, setIsAttributesConfirmed] = useState(false);
  const [confirmLoading, setConfirmLoading] = useState(false);
  const [confirmError, setConfirmError] = useState('');
  // null = unknown (status request failed), true/false = what the server reported
  const [modelAvailable, setModelAvailable] = useState(null);

  // measurements
  const [savedProfiles, setSavedProfiles] = useState([]);
  const [measurementId, setMeasurementId] = useState(null);
  const [meas, setMeas] = useState({ ...emptyMeas });
  const [unit, setUnit] = useState(() => getPreferences().unit);
  const [fieldErrors, setFieldErrors] = useState({});
  const [measUnits, setMeasUnits] = useState({});         // unit each value was typed in (missing = cm)
  const [savedMeasKey, setSavedMeasKey] = useState(null); // measurement values as last saved for this design
  const [activeField, setActiveField] = useState('bust_cm');
  const [manualDesign, setManualDesign] = useState(false);

  // fabric & fit
  const [selectedFabricId, setSelectedFabricId] = useState('');
  const [selectedFabricName, setSelectedFabricName] = useState('');
  const [fabricValidationError, setFabricValidationError] = useState('');

  // pattern
  const [patternId, setPatternId] = useState(null);
  const [patternData, setPatternData] = useState(null);
  const [patternKey, setPatternKey] = useState(null);     // inputs the current pattern was generated from

  // estimate
  const [fabricWidth, setFabricWidth] = useState(() => getPreferences().fabricWidth);
  const [cuttingMode, setCuttingMode] = useState('auto');
  const [yardageData, setYardageData] = useState(null);     // the selected width's layout
  const [estimates, setEstimates] = useState(null);         // 36" / 45" / 60" comparison rows
  const [yardageError, setYardageError] = useState(false);

  // export
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
    if (n !== S.CUSTOMER) setStarted(true);
  };

  // unsaved-changes guard: active once the user has started, cleared when the PDF has been downloaded
  useEffect(() => {
    setUnsaved(started && !pdfDownloaded);
  }, [started, pdfDownloaded]);
  useEffect(() => {
    window.addEventListener('beforeunload', beforeUnloadHandler);
    return () => { window.removeEventListener('beforeunload', beforeUnloadHandler); setUnsaved(false); };
  }, []);

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
      setMeasUnits({});
      setCustomerContact(p.email || '');
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

  // which measurements the confirmed design needs (same rules as the backend and the drafting engine)
  const requiredKeys = useMemo(() => (confirmedAttributes ? requiredFor(confirmedAttributes) : []), [confirmedAttributes]);
  const cmValues = useMemo(() => canonicalCm(meas, measUnits), [meas, measUnits]);
  const measKey = useMemo(() => JSON.stringify(requiredKeys.map((k) => [k, cmValues[k] ?? null])), [requiredKeys, cmValues]);
  const measurementsSaved = Boolean(measurementId) && savedMeasKey !== null && savedMeasKey === measKey;
  // everything the pattern depends on: when any of it changes, the old pattern, estimate and PDF are out of date
  const inputsKey = JSON.stringify([confirmedAttributes, measKey, selectedFabricId, meas.fit_preference, imageId]);
  const patternStale = Boolean(patternData) && patternKey !== inputsKey;
  const patternCurrent = Boolean(patternData) && !patternStale;
  useEffect(() => {
    if (requiredKeys.length && !requiredKeys.includes(activeField)) setActiveField(requiredKeys[0]);
  }, [requiredKeys, activeField]);

  // ── 1: customer & design ──────────────────────────────────────────────────
  const handleSelectSavedClient = (profileId) => {
    if (!profileId) {
      setMeas({ ...emptyMeas, fabric_type: meas.fabric_type, fit_preference: meas.fit_preference });
      setMeasUnits({});
      setSavedMeasKey(null);
      setCustomerContact('');
      setFieldErrors({});
      setMeasurementId(null);
      return;
    }
    const found = savedProfiles.find((p) => p.measurement_id === profileId);
    if (found) {
      setMeas(profileToMeas(found));
      setMeasUnits({});
      setSavedMeasKey(null);
      setCustomerContact(found.email || '');
      setUnit('cm');
      setFieldErrors({});
      setMeasurementId(found.measurement_id);
    }
  };

  const continueFromCustomer = () => {
    if (customerContact.trim().length > 120 || projectName.trim().length > 80) {
      setError('The contact is limited to 120 characters and the project name to 80.');
      return;
    }
    go(S.UPLOAD);
  };

  // ── 2: upload + analyse ───────────────────────────────────────────────────
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
      setManualDesign(false);
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
      go(S.REVIEW);
    } catch (err) {
      setError(friendlyError(err, 'We could not analyse that photo. Please try another photo or choose the design manually.'));
    } finally {
      setLoading(false);
    }
  };

  const chooseManually = () => {
    setImageId(null);
    setGarmentAttributes(null);
    setManualDesign(true);
    go(S.REVIEW);
  };

  // ── 3: confirm the design ─────────────────────────────────────────────────
  const applyConfirmed = (attrs) => {
    setConfirmedAttributes(attrs);
    setIsAttributesConfirmed(true);
    // a knit garment defaults to knit fabric; the chosen fabric decides in the fabric step
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

  const continueFromReview = () => go(S.MEASURE);

  // ── 4: measurements ───────────────────────────────────────────────────────
  // switching the unit only changes how values are SHOWN; what was typed (and its unit) is kept and saved
  const handleUnitToggle = (newUnit) => {
    if (newUnit === unit) return;
    setUnit(newUnit);
    setFieldErrors({});
  };

  const handleSaveMeasurements = async () => {
    if (!designReady) {
      setError('Please confirm a supported design in the AI review step before saving measurements.');
      return;
    }
    if (!measurementId && !meas.client_name.trim()) {
      setError('Please enter the customer name (step 1) or choose a saved customer before saving.');
      return;
    }
    const localErrors = validateMeasurements(meas, requiredKeys);
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
        client_name: meas.client_name.trim() !== '' ? meas.client_name.trim() : 'Customer Profile',
        ...(customerContact.trim() ? { email: customerContact.trim() } : {}),
        ...buildPayload(meas, measUnits, 'cm', requiredKeys),
        design: confirmedAttributes,
        fabric_type: meas.fabric_type,
        fit_preference: meas.fit_preference || 'standard',
      };
      const res = measurementId
        ? await measurementsAPI.update(measurementId, payload)
        : await measurementsAPI.save(payload);
      setFieldErrors({});
      setMeasurementId(res.data.measurement_id || res.data.profile_id || measurementId);
      setSavedMeasKey(measKey);
      go(S.FABRIC);
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

  // ── 5: fabric & fit → generate the pattern ────────────────────────────────
  const handleGeneratePattern = async () => {
    if (!designReady) {
      setError('Please confirm a supported design in the AI review step first.');
      return;
    }
    if (!measurementsSaved) {
      setError('Please save the measurements for this design (step 4) before generating the pattern.');
      return;
    }
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
    setEstimates(null);
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
        ...(projectName.trim() ? { project_name: projectName.trim() } : {}),
      });
      setPatternId(patRes.data.pattern_id);
      setPatternData(patRes.data);
      setPatternKey(inputsKey);
      go(S.PREVIEW);
      if (patRes.data.validation_passed === false || patRes.data.fabric_estimate_blocked) {
        const errs = (patRes.data.validation?.errors || []).join(' ');
        setError(errs ? `The pattern failed its automatic checks: ${errs}` : 'The pattern failed its automatic checks, so the fabric estimate is blocked.');
      }
    } catch (err) {
      const code = err.response?.data?.error_code;
      if (code === 'UNSUPPORTED_DESIGN' || code === 'DESIGN_NOT_CONFIRMED' || code === 'CONFIRMED_DESIGN_MISMATCH') {
        go(S.REVIEW);
        setError(friendlyError(err));
      } else if (err.response?.data?.field_errors && Object.keys(err.response.data.field_errors).some((k) => k.endsWith('_cm'))) {
        setFieldErrors(parseFieldErrors(err));
        go(S.MEASURE);
        setError(friendlyError(err, 'Some measurements need attention.') + ' The measurements to check are highlighted.');
      } else {
        setError(friendlyError(err, 'We could not create the pattern. Please check your inputs and try again.'));
      }
    } finally {
      setLoading(false);
    }
  };

  // ── 7: fabric estimate (36" / 45" / 60") ──────────────────────────────────
  const resultOrNA = (value, suffix = '') => formatResult(value, suffix, yardageError);

  const runEstimate = async (width = fabricWidth, mode = cuttingMode) => {
    if (!patternId) return;
    setLoading(true);
    setLoadingMessage('Laying out the pattern pieces on 36", 45" and 60" fabric…');
    setError('');
    try {
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

  const openEstimateStep = () => go(S.ESTIMATE);

  // opening the estimate step (by button or the step bar) calculates the estimate for the CURRENT pattern
  useEffect(() => {
    if (step === S.ESTIMATE && patternCurrent && patternData?.validation_passed !== false && !estimates && !yardageError && !loading) {
      runEstimate();
    }
  }, [step, patternCurrent]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── 8: PDF ────────────────────────────────────────────────────────────────
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
  const stale = (has) => (has ? (patternStale ? 'stale' : 'done') : 'pending');
  const stepStatus = {
    [S.CUSTOMER]: measurementId || meas.client_name.trim() ? 'done' : 'pending',
    [S.UPLOAD]: imageId || manualDesign ? 'done' : 'pending',
    [S.REVIEW]: designReady ? 'done' : 'pending',
    [S.MEASURE]: measurementsSaved ? 'done' : (measurementId && savedMeasKey !== null ? 'stale' : 'pending'),
    [S.FABRIC]: selectedFabricId ? 'done' : 'pending',
    [S.PREVIEW]: stale(Boolean(patternData)),
    [S.ESTIMATE]: stale(Boolean(yardageData)),
    [S.EXPORT]: stale(Boolean(exportId && pdfDownloaded)),
  };
  const leave = (to) => { setUnsaved(false); navigate(to); };

  // ── render ────────────────────────────────────────────────────────────────
  return (
    <div className="view active" id="v-wizard">
      <div className="wizard-container">
        <StepIndicator currentStep={step} setStep={go} status={stepStatus} />

        {error && <div role="alert" className="alert error wizard-alert">{error}</div>}
        {notice && !error && <div role="status" className="alert success wizard-alert">{notice}</div>}

        {loading && <div className="wizard-body"><LoadingSpinner message={loadingMessage} /></div>}

        {/* ── 1 CUSTOMER & DESIGN ── */}
        {!loading && step === S.CUSTOMER && (
          <div className="wizard-body" id="wp1">
            <Title title="Customer and design" help="Who is this pattern for? Choose a saved customer or add a new one. The design photo comes next." />
            <div className="section-card">
              <div className="form-grid" style={{ marginTop: 0 }}>
                <div className="form-field" style={{ gridColumn: '1/-1' }}>
                  <label className="form-label" htmlFor="saved-client">Customer</label>
                  <select id="saved-client" className="form-select" value={measurementId || ''} onChange={(e) => handleSelectSavedClient(e.target.value)}>
                    <option value="">+ New customer</option>
                    {uniqueProfiles.map((p) => (
                      <option key={p.measurement_id} value={p.measurement_id}>
                        {p.client_name || 'Customer'}{p.email ? ` — ${p.email}` : ''}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="form-field">
                  <label className="form-label" htmlFor="client-name">Customer name</label>
                  <input id="client-name" className="form-input" type="text" value={meas.client_name} disabled={Boolean(measurementId)}
                         onChange={(e) => setMeas({ ...meas, client_name: e.target.value })} placeholder="e.g. Amara Silva" />
                </div>
                <div className="form-field">
                  <label className="form-label" htmlFor="client-contact">Contact / reference (optional)</label>
                  <input id="client-contact" className="form-input" type="text" maxLength={120} value={customerContact}
                         onChange={(e) => setCustomerContact(e.target.value)} placeholder="e-mail, phone or order number" />
                </div>
                <div className="form-field" style={{ gridColumn: '1/-1' }}>
                  <label className="form-label" htmlFor="project-name">Design / project name (optional)</label>
                  <input id="project-name" className="form-input" type="text" maxLength={80} value={projectName}
                         onChange={(e) => setProjectName(e.target.value)} placeholder="e.g. Wedding blouse" />
                  <span className="form-hint">Printed on the PDF and shown in the pattern library.</span>
                </div>
              </div>
            </div>
            <NavRow>
              <button type="button" className="btn btn-primary btn-lg" onClick={continueFromCustomer}>Continue to upload <ArrowRight size={17} /></button>
            </NavRow>
          </div>
        )}

        {/* ── 2 UPLOAD ── */}
        {!loading && step === S.UPLOAD && (
          <div className="wizard-body" id="wp2">
            <Title title="Upload a garment photo"
                   help="Use a clear front-view photo of a blouse, T-shirt or crop-top. The AI suggests the design; you stay in control and confirm it." />
            {modelAvailable === false && (
              <div role="status" data-testid="model-unavailable" className="alert warn" style={{ marginBottom: 14 }}>
                The AI garment model is not available on this server, so photos cannot be analysed right now.
                Please choose the design manually — the pattern is drafted the same way.
              </div>
            )}
            <div className="upload-card">
              <label className="upload-zone">
                <span className="sr-only">Choose garment photo</span>
                <input type="file" accept="image/jpeg,image/png,image/webp" onChange={handleImageSelect} className="sr-only" data-testid="image-input" />
                <span className="upload-preview">
                  {imagePreview
                    ? <img src={imagePreview} alt="Selected garment preview" />
                    : <GarmentIllustration type="t-shirt" label="Garment photo placeholder" />}
                </span>
              </label>
              <div className="upload-cta">
                <span className="upload-icon" aria-hidden="true"><ImageUp size={22} /></span>
                <span className="upload-title">{imageFile ? imageFile.name : 'Choose a photo'}</span>
                <span className="upload-sub">PNG, JPG or WEBP (max 16 MB){imageFile ? ' · click the image to choose another' : ' · click the image area'}</span>
              </div>
              <button type="button" className="btn btn-primary btn-lg" onClick={handleUploadAndAnalyse} disabled={!imageFile || modelAvailable === false}>
                Upload and analyse
              </button>
            </div>
            <button type="button" className="btn btn-soft btn-lg btn-block" style={{ marginTop: 14 }} onClick={chooseManually}>
              <PencilLine size={17} /> Choose the design manually
            </button>
            <NavRow><button type="button" className="btn btn-outline" onClick={() => go(S.CUSTOMER)}>Back</button></NavRow>
          </div>
        )}

        {/* ── 3 AI REVIEW ── */}
        {!loading && step === S.REVIEW && (
          <div className="wizard-body" id="wp3">
            <Title title="Review the AI suggestions"
                   help="Confirm or correct each feature before continuing. The AI can make mistakes, especially on necklines and sleeve styles." />
            {!imageId && !manualDesign && !confirmedAttributes ? (
              <EmptyState title="No design yet" action="Go to upload" onAction={() => go(S.UPLOAD)}>
                Upload a garment photo for AI suggestions, or choose the design manually in the upload step.
              </EmptyState>
            ) : (
            <div className="review-layout">
              <div className={`review-photo${imagePreview && imageId ? '' : ' empty'}`}>
                {imagePreview && imageId ? <img src={imagePreview} alt="Uploaded garment" /> : <p>No photo — design chosen manually.</p>}
                {garmentAttributes?.garment_region && (
                  <p className={`region-note${garmentAttributes.garment_region.supported_garment === false ? ' warn' : ''}`}
                     data-testid="garment-region" role={garmentAttributes.garment_region.supported_garment === false ? 'alert' : undefined}>
                    {garmentAttributes.garment_region.supported_garment === false
                      ? garmentAttributes.garment_region.note
                      : garmentAttributes.garment_region.used === 'garment_crop'
                        ? 'The AI looked at the garment area it found in this photo.'
                        : 'The AI looked at the whole photo (no garment area was found), so its suggestions are less reliable.'}
                  </p>
                )}
              </div>
              <PredictionReview garmentAttributes={garmentAttributes} confirmedAttributes={confirmedAttributes}
                                onConfirm={handleConfirmGarmentAttributes} isSubmitting={confirmLoading} error={confirmError} />
            </div>
            )}
            <NavRow>
              <button type="button" className="btn btn-outline" onClick={() => go(S.UPLOAD)}>Back</button>
              <button type="button" className="btn btn-primary btn-lg" onClick={continueFromReview}>Continue to measurements</button>
            </NavRow>
          </div>
        )}

        {/* ── 4 MEASUREMENTS ── */}
        {!loading && step === S.MEASURE && (
          <div className="wizard-body" id="wp4">
            <Title title="Body measurements"
                   help={designReady
                     ? `This design needs ${requiredKeys.length} measurements${meas.client_name ? ` for ${meas.client_name}` : ''}. Select a field to see how to measure it.`
                     : 'The measurements needed depend on the confirmed design.'} />
            {!designReady ? (
              <EmptyState title="Confirm the design first" action="Go to AI review" onAction={() => go(S.REVIEW)}>
                Which measurements are needed depends on the garment, neckline and sleeves you confirm in the AI review step.
              </EmptyState>
            ) : (
            <>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, flexWrap: 'wrap', marginBottom: 14 }}
                 data-testid="unit-toggle">
              <span className="form-label" id="unit-label">Measurement unit</span>
              <div className="segmented" role="group" aria-labelledby="unit-label">
                {['cm', 'in'].map((u) => (
                  <button key={u} type="button" aria-pressed={unit === u} onClick={() => handleUnitToggle(u)} data-testid={`unit-${u}`}>
                    {u === 'cm' ? 'Centimetres (cm)' : 'Inches (in)'}
                  </button>
                ))}
              </div>
            </div>
            {measurementId && savedMeasKey !== null && !measurementsSaved && (
              <div role="status" className="alert warn" style={{ marginBottom: 12 }} data-testid="meas-unsaved">
                The measurements changed since they were saved. Save them again before generating the pattern.
              </div>
            )}
            <div className="meas-layout">
              <aside className="meas-figure" aria-label="Measurement guide">
                <h3>Measurement guide</h3>
                <MeasureFigure active={activeField} fields={requiredKeys} sleeveCm={cmValues.sleeve_cm} />
                <p className="form-hint" style={{ marginTop: 6 }}>
                  Shows where to measure {LABELS[activeField] ? <strong>{LABELS[activeField].toLowerCase()}</strong> : 'each field'}; it is a guide, not a body model.
                  Inches are converted exactly (1 in = 2.54 cm).
                </p>
              </aside>
              <div className="meas-grid">
                {MEASUREMENT_FIELDS.filter((f) => requiredKeys.includes(f.key)).map((field) => {
                  const key = field.key;
                  const message = fieldErrors[key] || (key === 'armhole_depth_cm' ? fieldErrors.armhole_cm : undefined);
                  return (
                    <div className={`meas-field${activeField === key ? ' active' : ''}`} key={key}>
                      <label className="form-label" htmlFor={`meas-${key}`}>{field.label}<span className="sr-only"> ({unit})</span></label>
                      <div className="input-suffix">
                        <input id={`meas-${key}`} className="form-input" type="number" step="any" inputMode="decimal" min="0"
                               value={displayValue(meas[key], measUnits[key] || 'cm', unit)} aria-invalid={message ? 'true' : 'false'}
                               aria-describedby={activeField === key ? `guide-${key}` : undefined}
                               onFocus={() => setActiveField(key)}
                               onChange={(e) => {
                                 setError('');
                                 setFieldErrors((prev) => {
                                   if (!prev[key]) return prev;
                                   const { [key]: _removed, ...rest } = prev;
                                   return rest;
                                 });
                                 setMeas({ ...meas, [key]: e.target.value });
                                 setMeasUnits({ ...measUnits, [key]: unit });
                               }} />
                        <span aria-hidden="true">{unit}</span>
                      </div>
                      {activeField === key && <small id={`guide-${key}`} className="form-hint meas-guide" data-testid={`guide-${key}`}>{GUIDES[key]}</small>}
                      {message && <div role="alert" className="field-error" data-testid={`error-${key}`}>{message}</div>}
                    </div>
                  );
                })}
              </div>
            </div>
            </>
            )}
            <NavRow>
              <button type="button" className="btn btn-outline" onClick={() => go(S.REVIEW)}>Back</button>
              <button type="button" className="btn btn-primary btn-lg" onClick={handleSaveMeasurements} disabled={!designReady}>Save and continue</button>
            </NavRow>
          </div>
        )}

        {/* ── 5 FABRIC & FIT ── */}
        {!loading && step === S.FABRIC && (
          <div className="wizard-body" id="wp5">
            <Title title="Choose fabric and fit" help="Pick how loose the garment should be and a fabric. The chosen fabric decides woven or knit drafting." />
            {!designReady ? (
              <EmptyState title="Confirm the design first" action="Go to AI review" onAction={() => go(S.REVIEW)}>
                Fabric recommendations depend on the confirmed garment, neckline and sleeves.
              </EmptyState>
            ) : (
            <>
            <section className="section-card">
              <h3 id="fit-h">Fit preference</h3>
              <div className="choice-grid" role="group" aria-labelledby="fit-h">
                {FITS.map((f) => (
                  <button key={f.value} type="button" className="choice-card" aria-pressed={meas.fit_preference === f.value}
                          data-testid={`fit-${f.value}`} onClick={() => setMeas({ ...meas, fit_preference: f.value })}>
                    <GarmentIllustration type={confirmedAttributes?.garment_type} className="garment" label={`${f.label} fit`} />
                    {f.label}<small>{f.note}</small>
                  </button>
                ))}
              </div>
            </section>
            <section className="section-card">
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
              <p className="form-hint" data-testid="fabric-construction" style={{ marginTop: 10 }}>
                Construction: {meas.fabric_type === 'knit' ? 'Knit' : 'Woven'} — set by the chosen fabric (it decides the drafting block).
              </p>
            </section>
            <div className="summary-strip">
              <strong>Summary:</strong>
              {['garment_type', 'neckline_type', 'sleeve_length', 'sleeve_style'].map((h) => (
                <span key={h} className="chip">{labelOf(h, confirmedAttributes?.[h]) || '—'}</span>
              ))}
              <span className="chip">{FITS.find((f) => f.value === meas.fit_preference)?.label} fit</span>
              <span className="chip accent">{selectedFabricName || 'no fabric chosen yet'}</span>
            </div>
            {!measurementsSaved && (
              <p className="form-hint" data-testid="needs-measurements">Save the measurements for this design (step 4) before generating the pattern.</p>
            )}
            </>
            )}
            <NavRow>
              <button type="button" className="btn btn-outline" onClick={() => go(S.MEASURE)}>Back</button>
              <button type="button" className="btn btn-primary btn-lg" onClick={handleGeneratePattern} disabled={!designReady}>
                {patternStale ? 'Regenerate pattern' : 'Confirm and generate pattern'}
              </button>
            </NavRow>
          </div>
        )}

        {/* ── 6 PATTERN PREVIEW ── */}
        {!loading && step === S.PREVIEW && (
          <div className="wizard-body" id="wp6">
            <Title title="Pattern preview" help="Drafted from your measurements and confirmed design, then checked automatically. Zoom and drag to inspect the pieces." />
            {patternStale && (
              <EmptyState title="The pattern needs to be generated again" action="Regenerate pattern" onAction={handleGeneratePattern}>
                The design, measurements, fit or fabric changed after this pattern was made, so it is no longer shown as current.
              </EmptyState>
            )}
            {!patternData && (
              <EmptyState title="No pattern yet" action="Go to fabric & fit" onAction={() => go(S.FABRIC)}>
                Confirm the design, save the measurements and choose a fabric, then generate the pattern.
              </EmptyState>
            )}
            {patternCurrent && (
              <PatternPreview pieces={patternData?.pattern_pieces} fabricWidth={fabricWidth} validation={patternData?.validation}
                              draftingBlock={patternData?.drafting_block} armholeSleeve={patternData?.armhole_sleeve}
                              transformations={patternData?.final_pattern?.transformations} />
            )}
            <NavRow>
              <button type="button" className="btn btn-outline" onClick={() => go(S.FABRIC)}>Back</button>
              <button type="button" className="btn btn-primary btn-lg" onClick={openEstimateStep}>Continue to fabric estimate</button>
            </NavRow>
          </div>
        )}

        {/* ── 7 FABRIC ESTIMATE ── */}
        {!loading && step === S.ESTIMATE && (
          <div className="wizard-body" id="wp7">
            <Title title="Fabric estimate"
                   help='The pattern pieces (with seam allowance) are laid out on 36", 45" and 60" fabric. The pieces stay the same; only the layout and the length change.' />
            {!patternCurrent || validationBlocked ? (
              <EmptyState title={validationBlocked && patternCurrent ? 'Estimate blocked' : 'No current pattern'}
                          action={patternStale ? 'Regenerate pattern' : 'Go to pattern preview'}
                          onAction={patternStale ? handleGeneratePattern : () => go(S.PREVIEW)}>
                {validationBlocked && patternCurrent
                  ? 'The pattern failed its automatic checks, so no fabric estimate is calculated.'
                  : patternStale ? 'The inputs changed after the pattern was made; generate it again to get a current estimate.'
                    : 'Generate the pattern first; the estimate is laid out from its validated pieces.'}
              </EmptyState>
            ) : (
            <>
            <div className="form-field" style={{ maxWidth: 360 }}>
              <label className="form-label" htmlFor="cut-mode">Cutting layout</label>
              <select id="cut-mode" className="form-select" value={cuttingMode} onChange={(e) => { setCuttingMode(e.target.value); runEstimate(fabricWidth, e.target.value); }}>
                {CUTTING_MODES.map((m) => <option key={m.value} value={m.value}>{m.label}</option>)}
              </select>
            </div>

            {estimates && (
              <div className="width-cards" aria-hidden="true">
                {estimates.map((e) => (
                  <div key={e.fabric_width_cm} className={`width-card${e.selected ? ' selected' : ''}${e.fits ? '' : ' nofit'}`}>
                    <span className="wc-width">{e.fabric_width_in}" · {e.fabric_width_cm} cm{e.selected ? ' · selected' : ''}</span>
                    <span className="wc-buy">{e.fits ? `${e.recommended_purchase_m} m` : 'Does not fit'}</span>
                    <span className="wc-meta">{e.fits ? `layout ${e.base_layout_length_cm} cm · ${e.utilisation_percent}% used` : e.error}</span>
                  </div>
                ))}
              </div>
            )}

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
                {estimates.flatMap((e) => (e.warnings || []).map((w) => `${e.fabric_width_in}": ${w}`)).map((w) => <p key={w} className="form-hint" style={{ padding: '0 16px 10px' }}>{w}</p>)}
              </div>
            )}

            <div className="result-grid" style={{ marginTop: 16 }} data-testid="estimate-results">
              <div className="result-tile"><div className="r-val">{resultOrNA(yardageData?.purchasing_recommended_m, ' m')}</div><div className="r-lbl">Recommended purchase</div></div>
              <div className="result-tile"><div className="r-val">{resultOrNA(yardageData?.fabric_length_cm, ' cm')}</div><div className="r-lbl">Layout length</div></div>
              <div className="result-tile"><div className="r-val">{resultOrNA(yardageData?.utilisation_percent, '%')}</div><div className="r-lbl">Fabric used by pieces</div></div>
            </div>

            {yardageData && (
              <div className="layout-card">
                <div className="layout-card-head">
                  <h3><Grid3x3 size={16} style={{ verticalAlign: '-2px' }} /> Cutting layout</h3>
                  <span className="chip">{widthLabel(yardageData.fabric_width_cm)} · {yardageData.cutting_method_simple}</span>
                </div>
                <NestingLayout nesting={yardageData} />
                <details style={{ marginTop: 10 }}>
                  <summary className="form-hint" style={{ cursor: 'pointer', fontWeight: 600 }}>How this was calculated</summary>
                  <ul style={{ paddingLeft: 18, marginTop: 6, fontSize: 13, color: 'var(--ink-2)' }}>
                    <li>{yardageData.method}</li>
                    <li>{yardageData.purchase_rule}</li>
                  </ul>
                </details>
              </div>
            )}
            </>
            )}
            <NavRow>
              <button type="button" className="btn btn-outline" onClick={() => go(S.PREVIEW)}>Back</button>
              <button type="button" className="btn btn-primary btn-lg" onClick={() => go(S.EXPORT)}>Continue to PDF export</button>
            </NavRow>
          </div>
        )}

        {/* ── 8 PDF EXPORT ── */}
        {!loading && step === S.EXPORT && (
          <div className="wizard-body" id="wp8">
            <div className="export-head">
              <span className="eh-icon" aria-hidden="true"><FileText size={22} /></span>
              <div>
                <h2 style={{ fontSize: 22 }}>{exportId ? 'Pattern ready to export' : 'Printable pattern (PDF)'}</h2>
                <p className="form-hint" style={{ fontSize: 14 }}>
                  {exportId ? 'Download and print your pattern with the correct settings.' : 'A full-size pattern that prints on ordinary A4 paper and is taped together from tiles.'}
                </p>
                {exportId && <span className="sr-only">Printable pattern (PDF)</span>}
              </div>
            </div>
            {!patternCurrent ? (
              <EmptyState title={patternStale ? 'The PDF would be out of date' : 'No pattern to export yet'}
                          action={patternStale ? 'Regenerate pattern' : 'Go to pattern preview'}
                          onAction={patternStale ? handleGeneratePattern : () => go(S.PREVIEW)}>
                {patternStale
                  ? 'The design, measurements or fabric changed after the pattern was made. Generate it again, then create the PDF.'
                  : 'Generate the pattern and calculate the fabric estimate, then create the printable PDF here.'}
              </EmptyState>
            ) : (
            <div className="export-layout">
              <section className="section-card" style={{ marginBottom: 0 }}>
                <ul className="export-list">
                  <li><span><Printer size={18} /></span><div><strong>A4 tiled pattern</strong><small>Print with the scale set to 100% / Actual size — never “fit to page”.</small></div></li>
                  <li><span><Ruler size={18} /></span><div><strong>Calibration square 5 × 5 cm</strong><small>Measure it before you tape the pages together.</small></div></li>
                  <li><span><Scissors size={18} /></span><div><strong>Fabric required {yardageData ? `${yardageData.purchasing_recommended_m} m` : '—'}</strong>
                    <small>{yardageData ? `For ${widthLabel(yardageData.fabric_width_cm)}; all three widths are in the PDF.` : 'Calculate the fabric estimate first.'}</small></div></li>
                  <li><span><Calendar size={18} /></span><div><strong>Test garment first</strong><small>Make a muslin — this is a prototype pattern, not a fit-tested one.</small></div></li>
                </ul>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginTop: 18 }}>
                  {!exportId ? (
                    <button type="button" className="btn btn-primary btn-lg btn-block" onClick={handleCreatePdf} disabled={!yardageData}>Create printable PDF</button>
                  ) : (
                    <div data-testid="pdf-ready" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                      <span className="pill good" style={{ alignSelf: 'flex-start' }}><CheckCircle2 size={13} /> {pdfInfo?.pages} pages · A4 · 1:1 scale</span>
                      <button type="button" className="btn btn-primary btn-lg btn-block" onClick={handleDownloadPDF}><Download size={18} /> Download PDF</button>
                    </div>
                  )}
                  <button type="button" className="btn btn-outline btn-block" onClick={() => leave('/history')}><FolderOpen size={16} /> Open pattern library</button>
                </div>
              </section>
              <section className="pdf-preview">
                <h3 style={{ marginBottom: 10 }}>PDF preview (A4 tiled pattern)</h3>
                <TilePreview pieces={patternData?.pattern_pieces} pages={pdfInfo?.pages} />
              </section>
            </div>
            )}

            {pdfDownloaded && !feedbackSubmitted && (
              <form onSubmit={handleFeedbackSubmit} className="section-card" style={{ marginTop: 16 }} aria-label="Feedback">
                <div className="form-field">
                  <label className="form-label" htmlFor="fb-score">How easy was it to create this pattern?</label>
                  <select id="fb-score" className="form-select" value={feedbackScore} onChange={(e) => setFeedbackScore(Number(e.target.value))}>
                    {[5, 4, 3, 2, 1].map((n) => <option key={n} value={n}>{n} — {['', 'very hard', 'hard', 'okay', 'easy', 'very easy'][n]}</option>)}
                  </select>
                </div>
                <div className="form-field" style={{ marginTop: 10 }}>
                  <label className="form-label" htmlFor="fb-comment">Comments (optional)</label>
                  <textarea id="fb-comment" className="form-input" value={feedbackComment} onChange={(e) => setFeedbackComment(e.target.value)} />
                </div>
                <button type="submit" className="btn btn-outline" style={{ marginTop: 10 }}>Send feedback</button>
              </form>
            )}
            {feedbackSubmitted && <p role="status" className="alert success" style={{ marginTop: 14 }}>Thank you — your feedback was saved.</p>}
            <NavRow>
              <button type="button" className="btn btn-outline" onClick={() => go(S.ESTIMATE)}>Back</button>
              <button type="button" className="btn btn-primary" onClick={() => leave('/dashboard')}>Finish</button>
            </NavRow>
          </div>
        )}
      </div>
    </div>
  );
}
