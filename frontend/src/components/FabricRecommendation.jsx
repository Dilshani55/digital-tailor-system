import { useEffect, useRef, useState } from 'react';
import { AlertTriangle, Check, Info, RefreshCw } from 'lucide-react';
import { fabricAPI } from '../services/api';
import FabricDetailsModal from './FabricDetailsModal';
import FabricPreferences, { completePreferences } from './FabricPreferences';
import { fabricGoal, fabricObservation, fabricDescription } from '../utils/fabricDisplay';

const gsmText = (f) => (f.gsm_range ? `${f.gsm_range.min}–${f.gsm_range.max} GSM` : null);
const firstWord = (text) => String(text || '').split(/[ —-]/)[0];

/**
 * Shows compatible catalogue fabrics, or ranks identified samples when research data is available.
 * Users explicitly choose a fabric; missing data never produces an automatic recommendation.
 */
export default function FabricRecommendation({ confirmedAttributes, fitPreference = 'standard', selectedFabricId, onSelectFabric, validationError,
  preferences, onPreferencesChange }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [modalFabric, setModalFabric] = useState(null);
  const [failedImages, setFailedImages] = useState({});
  const [replaced, setReplaced] = useState('');         // a chosen fabric the confirmed design cannot use
  const [localPreferences, setLocalPreferences] = useState(null);
  const [editingPreferences, setEditingPreferences] = useState(false);
  const currentPreferences = preferences === undefined ? localPreferences : preferences;
  const pending = !confirmedAttributes;                 // no confirmed design yet: plain catalogue, no ranking
  const requestVersion = useRef(0);
  const selectedRef = useRef(selectedFabricId);
  const resultsRef = useRef(null);
  const focusResults = useRef(false);
  selectedRef.current = selectedFabricId;

  const pick = (f) => {
    if (f.compatible === false || (f.study_id && (loading || error || data?.ranking_status !== 'ranked'))) return;
    setReplaced('');
    if (f.study_id) onSelectFabric(f.id, f.name, f.construction, data?.ranking_audit?.preferences || null);
    else onSelectFabric(f.id, f.name, f.construction);
  };

  const changePreferences = (next) => {
    if (JSON.stringify(next) === JSON.stringify(currentPreferences)) return;
    requestVersion.current += 1;
    setLoading(false);
    setError('');
    if (onPreferencesChange) onPreferencesChange(next);
    else setLocalPreferences(next);
    if ((data?.fabrics || []).find((f) => f.id === selectedRef.current)?.study_id) onSelectFabric('', '', undefined);
    setModalFabric(null);
    setData((previous) => previous ? { ...previous, ranking_status: 'awaiting_preferences', ranking_audit: null, error_code: null, error: null,
      ranking_message: 'Preferences changed. Compare the samples to update the results.',
      fabrics: previous.fabrics.map((f) => f.study_id ? { ...f, rank: null, topsis_closeness: null, recommended: false,
        recommendation_status: 'Published sample — unranked', explanation: 'Compare the samples using your current preferences.' } : f) } : previous);
  };

  const load = async (preferenceInput = null, preflight = false, fromCompare = false) => {
    const version = ++requestVersion.current;
    setLoading(true);
    if (!preferenceInput) setData(null);
    setModalFabric(null);
    setReplaced('');
    setError('');
    try {
      if (pending) {
        const res = await fabricAPI.getCatalog();
        if (version !== requestVersion.current) return;
        setData({ fabrics: (res.data.fabrics || []).map((f) => ({ ...f, compatible: true, recommended: false, explanation: f.simple_description })) });
        return;
      }
      const payload = { confirmed_attributes: confirmedAttributes, fit_preference: fitPreference };
      let res = await fabricAPI.getRecommendations({ ...payload, ...(!preflight && preferenceInput ? { user_preferences: preferenceInput } : {}) });
      if (version !== requestVersion.current) return;
      if (preflight && completePreferences(res.data.published_study, preferenceInput)) {
        res = await fabricAPI.getRecommendations({ ...payload, user_preferences: preferenceInput });
        if (version !== requestVersion.current) return;
      }
      setData(res.data);
      if (res.data.ranking_status === 'ranked') {
        setEditingPreferences(false);
        focusResults.current = fromCompare;
      }
      const fabrics = res.data.fabrics || res.data.recommendations || [];
      const current = fabrics.find((f) => f.id === selectedRef.current);
      if (selectedRef.current && (!current || !current.compatible)) {
        // never swap the user's fabric silently: clear it and say why
        setReplaced(`${current?.name || 'The selected fabric'} cannot be used for this design${current?.incompatible_reason ? ` (${current.incompatible_reason})` : ''}. Please choose another fabric.`);
        onSelectFabric('', '', undefined);
      }
    } catch (err) {
      if (version !== requestVersion.current) return;
      if (err.response?.data?.error_code === 'INVALID_FABRIC_PREFERENCES') {
        setData(err.response.data);
        setError(err.response.data.error);
        return;
      }
      setError(pending ? 'The fabric list could not be loaded. Please check the connection and try again.'
        : 'Fabric recommendations could not be loaded. Please check the connection and try again.');
    } finally {
      if (version === requestVersion.current) setLoading(false);
    }
  };

  const designKey = JSON.stringify(confirmedAttributes || {});
  useEffect(() => {
    load(currentPreferences, true);
    return () => { requestVersion.current += 1; };
  }, [designKey, fitPreference]); // eslint-disable-line react-hooks/exhaustive-deps

  const fabrics = data?.fabrics || data?.recommendations || [];
  const compatible = fabrics.filter((f) => f.compatible);
  const ranked = !pending && data?.ranking_status === 'ranked';
  const selectedFabric = compatible.find((f) => f.id === selectedFabricId);
  const isRecommended = (f) => Boolean(ranked && f.compatible && (f.recommended || f.rank === 1));
  const recommended = fabrics.filter(isRecommended);
  const other = fabrics.filter((f) => !isRecommended(f));
  const study = data?.published_study;
  const showMaterials = !study || ranked || ['awaiting_data', 'invalid_data', 'indistinguishable'].includes(data?.ranking_status);
  const weights = data?.ranking_audit?.ahp?.weights || [];
  const priorities = study?.criteria.filter((_, i) => Math.abs(weights[i] - Math.max(...weights)) < 1e-9).map((c) => c.label) || [];
  const invalidPreferences = data?.error_code === 'INVALID_FABRIC_PREFERENCES';
  const canSelect = (f) => f.compatible !== false && (!f.study_id || (ranked && !loading && !error));

  useEffect(() => {
    if (ranked && !loading && focusResults.current) {
      focusResults.current = false;
      resultsRef.current?.focus();
      resultsRef.current?.scrollIntoView?.({ block: 'nearest', behavior: 'smooth' });
    }
  }, [ranked, loading]);

  const card = (f) => {
    const selected = selectedFabricId === f.id;
    return (
      <article key={f.id} className={`fabric-card${selected ? ' selected' : ''}${isRecommended(f) ? ' fabric-top-choice' : ''}${f.study_id ? ' fabric-sample-card' : ''}`} data-testid={`fabric-${f.id}`}>
        {f.study_id && <div className="fabric-sample-header">
          <span>{f.construction === 'knit' ? 'Knit' : 'Woven'}</span>
          {isRecommended(f) && <span className="tag fabric-best">Recommended</span>}
        </div>}
        <button type="button" className="fabric-card-main" onClick={() => pick(f)} aria-pressed={selected}
          disabled={!canSelect(f)} aria-label={`${selected ? 'Selected fabric' : 'Select fabric'}: ${f.name}`}>
          {!f.study_id && <span className="fabric-swatch">
            {!failedImages[f.id] && f.local_image
              ? <img src={f.local_image} alt={`Close-up fabric texture image of ${f.name}`} onError={() => setFailedImages((p) => ({ ...p, [f.id]: true }))} />
              : <span className="fabric-swatch-fallback">{f.name.charAt(0)}</span>}
            <span className={`fabric-radio${selected ? ' on' : ''}`} aria-hidden="true">{selected && <Check size={14} />}</span>
          </span>}
          <span className="fabric-card-body">
            <strong>{f.name}</strong>
            <span className="fabric-why">{fabricDescription(f, study)}</span>
            {f.study_id
              ? <small>Weight: {fabricObservation(f.research_sample.values.mass)}</small>
              : <small>{[gsmText(f), f.weight && `${f.weight} weight`].filter(Boolean).join(' · ')}</small>}
            <span className="fabric-tags">
              {f.stretch && <span className="tag">{f.stretch}</span>}
              {f.breathability && <span className="tag">{firstWord(f.breathability)} breathability</span>}
              <span className="tag">{f.construction === 'knit' ? 'Knit' : 'Woven'}</span>
            </span>
            {f.compatible === false && <span className="fabric-warning">Not suitable for this design</span>}
            <span className="sr-only">{selected ? 'Selected' : 'Select Material'}</span>
          </span>
        </button>
        <button type="button" className={`btn ${selected ? 'btn-primary' : 'btn-outline'} fabric-select-btn`}
          disabled={!canSelect(f)} onClick={() => pick(f)} aria-pressed={selected}>
          {selected && <Check size={16} />} {selected ? 'Selected' : f.compatible === false ? 'Not available' : 'Select fabric'}
        </button>
        <button type="button" className="fabric-details-btn" onClick={() => setModalFabric(f)}><Info size={13} /> View Details</button>
      </article>
    );
  };

  return (
    <section className="fabric-recommendation" aria-labelledby="fabric-h" aria-busy={loading}>
      <div className="section-head">
        <div>
          <h3 id="fabric-h">Choose your material</h3>
          <p>{study && !ranked ? 'Choose your fabric goals to see recommended materials.' : 'Choose a material or open View Details to learn more about it.'}</p>
        </div>
      </div>

      {pending && (
        <div role="status" className="inline-alert" data-testid="fabric-pending">
          <Info size={15} /> Confirm your design to see material recommendations.
        </div>
      )}
      {!pending && data?.ranking_message && !ranked && <p role="status" className="form-hint" data-testid="fabric-ranking-status">
        {data.ranking_status === 'awaiting_preferences' ? 'Complete your fabric goals to see recommendations.' : 'Recommendations are not available yet. Review your choices or choose another material.'}
      </p>}
      {replaced && <div className="inline-alert error" role="alert" data-testid="fabric-replaced"><AlertTriangle size={15} /> {replaced}</div>}
      {validationError && <div className="inline-alert error" role="alert"><AlertTriangle size={15} /> {validationError}</div>}
      {loading && !data && <p className="muted">{pending ? 'Loading the fabric list…' : 'Ranking fabrics for this design…'}</p>}
      {error && (
        <div className="inline-alert error" role="alert">
          {error}
          {!invalidPreferences && <button type="button" className="btn btn-outline btn-sm" disabled={loading} onClick={() => load(currentPreferences, true)}><RefreshCw size={13} /> Retry</button>}
        </div>
      )}

      {study && (ranked && !editingPreferences ? <div className="fabric-preference-summary" data-testid="fabric-preference-summary">
        <div><h4>Your fabric goals</h4><div className="fabric-tags">{study.criteria.map((c) => <span className="tag" key={c.id}>
          {fabricGoal(c, data.ranking_audit?.preferences?.goals?.[c.id])}
        </span>)}</div>{priorities.length > 0 && <p className="form-hint">
          {priorities.length === study.criteria.length ? 'All properties equally important' : `Most important: ${priorities.join(' and ')}`}
        </p>}</div>
        <button type="button" className="btn btn-outline btn-sm" disabled={loading} onClick={() => setEditingPreferences(true)}>Edit preferences</button>
      </div> : <FabricPreferences study={study} value={currentPreferences}
        onChange={changePreferences} onCalculate={(input) => load(input, false, true)} busy={loading} correctionNeeded={invalidPreferences} />)}
      {loading && data && <p role="status" className="form-hint">Updating the comparison…</p>}
      {selectedFabric && <div className="fabric-selection-summary" role="status" data-testid="fabric-selection-summary">
        <Check size={20} /><div><strong>Selected fabric: {selectedFabric.name}</strong><span>
          {canSelect(selectedFabric) ? 'Ready for pattern generation' : 'Complete your fabric goals to use this material'}
        </span></div>
      </div>}
      {showMaterials && recommended.length > 0 && <div className="fabric-material-group">
        <h4 className="fabric-list-heading" ref={resultsRef} tabIndex={-1}>Recommended materials</h4>
        <p className="form-hint">The closest match to your fabric goals.</p>
        <div className="fabric-grid" data-testid="ranked-fabrics">{recommended.map(card)}</div>
      </div>}
      {showMaterials && other.length > 0 && <div className="fabric-material-group">
        <h4 className="fabric-list-heading">Other materials</h4>
        <div className="fabric-grid" data-testid="other-fabrics">{other.map(card)}</div>
      </div>}

      {modalFabric && (
        <FabricDetailsModal
          fabric={modalFabric}
          rankingAudit={data?.ranking_audit}
          publishedStudy={data?.published_study}
          isSelected={selectedFabricId === modalFabric.id}
          canSelect={canSelect(modalFabric)}
          isRecommended={isRecommended(modalFabric)}
          onSelect={() => { if (modalFabric.compatible !== false) pick(modalFabric); }}
          onClose={() => setModalFabric(null)}
        />
      )}
    </section>
  );
}
