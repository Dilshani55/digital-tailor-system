import { useEffect, useRef, useState } from 'react';
import { AlertTriangle, Check, Info, RefreshCw } from 'lucide-react';
import { fabricAPI } from '../services/api';
import FabricDetailsModal from './FabricDetailsModal';
import FabricPreferences, { completePreferences } from './FabricPreferences';

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
  const currentPreferences = preferences === undefined ? localPreferences : preferences;
  const pending = !confirmedAttributes;                 // no confirmed design yet: plain catalogue, no ranking
  const requestVersion = useRef(0);
  const selectedRef = useRef(selectedFabricId);
  selectedRef.current = selectedFabricId;

  const pick = (f) => {
    setReplaced('');
    if (f.study_id) onSelectFabric(f.id, f.name, f.construction, data?.ranking_audit?.preferences || null);
    else onSelectFabric(f.id, f.name, f.construction);
  };

  const changePreferences = (next) => {
    requestVersion.current += 1;
    setLoading(false);
    setError('');
    if (onPreferencesChange) onPreferencesChange(next);
    else setLocalPreferences(next);
    if ((data?.fabrics || []).find((f) => f.id === selectedRef.current)?.study_id) onSelectFabric('', '', undefined);
    setModalFabric(null);
    setData((previous) => previous ? { ...previous, ranking_status: 'awaiting_preferences', ranking_audit: null,
      ranking_message: 'Preferences changed. Compare the samples to update the results.',
      fabrics: previous.fabrics.map((f) => f.study_id ? { ...f, rank: null, topsis_closeness: null, recommended: false,
        recommendation_status: 'Published sample — unranked', explanation: 'Compare the samples using your current preferences.' } : f) } : previous);
  };

  const load = async (preferenceInput = null, preflight = false) => {
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
  const publishedSamples = compatible.filter((f) => f.study_id);
  const catalogue = compatible.filter((f) => !f.study_id);
  const ranked = !pending && data?.ranking_status === 'ranked';
  const incompatible = fabrics.filter((f) => !f.compatible);

  const card = (f) => {
    const selected = selectedFabricId === f.id;
    return (
      <article key={f.id} className={`fabric-card${selected ? ' selected' : ''}`} data-testid={`fabric-${f.id}`}>
        <button type="button" className="fabric-card-main" onClick={() => pick(f)} aria-pressed={selected}>
          <span className="fabric-swatch">
            {!failedImages[f.id] && f.local_image
              ? <img src={f.local_image} alt={`Close-up fabric texture image of ${f.name}`} onError={() => setFailedImages((p) => ({ ...p, [f.id]: true }))} />
              : <span className="fabric-swatch-fallback">{f.name.charAt(0)}</span>}
            <span className={`fabric-radio${selected ? ' on' : ''}`} aria-hidden="true">{selected && <Check size={14} />}</span>
          </span>
          <span className="fabric-card-body">
            <strong>{f.name}</strong>
            {f.study_id
              ? <small>Measured weight: {f.research_sample.values.mass.value} g/m²</small>
              : <small>Catalogue guide: {[gsmText(f), f.weight && `${f.weight} weight`].filter(Boolean).join(' · ')}</small>}
            {f.research_sample && <small>Sample: {f.research_sample.label} ({f.research_sample.sample_id})</small>}
            <span className="fabric-tags">
              {f.stretch && <span className="tag">{f.stretch}</span>}
              {f.breathability && <span className="tag">{firstWord(f.breathability)} breathability</span>}
              <span className="tag">{f.construction === 'knit' ? 'Knit' : 'Woven'}</span>
            </span>
            <span className="fabric-why">{f.explanation}</span>
            {(f.warnings || []).map((w) => <span key={w} className="fabric-warning"><AlertTriangle size={12} /> {w}</span>)}
            <span className="sr-only">{selected ? 'Selected' : 'Select Material'}</span>
          </span>
        </button>
        <button type="button" className="fabric-details-btn" onClick={() => setModalFabric(f)}><Info size={13} /> View Details</button>
      </article>
    );
  };

  return (
    <section className="fabric-recommendation" aria-labelledby="fabric-h">
      <div className="section-head">
        <div>
          <h3 id="fabric-h">{pending ? 'Fabrics' : ranked ? 'Ranked fabric samples' : 'Compatible fabrics'}</h3>
          <p>{pending ? 'All fabrics in the catalogue. Recommendations for your design are worked out once the design is confirmed.'
            : ranked ? `Compared using recorded sample data and ${data?.ranking_audit?.weight_source === 'user_preferences' ? 'your' : 'recorded'} priorities. Choose a fabric; View Details shows the evidence.`
              : 'Choose a fabric supported by the drafting block for your confirmed design. Catalogue descriptions are general guides.'}</p>
        </div>
        <span className="method-badge">{ranked ? 'AHP / TOPSIS' : 'Fabric compatibility'}</span>
      </div>

      {pending && (
        <div role="status" className="inline-alert" data-testid="fabric-pending">
          <Info size={15} /> Recommendations pending: no design is confirmed yet. You can already pick a fabric; it is checked against the design when you confirm it.
        </div>
      )}
      {!pending && data?.ranking_message && <div role="status" className="inline-alert" data-testid="fabric-ranking-status"><Info size={15} /> {data.ranking_message}</div>}
      {replaced && <div className="inline-alert error" role="alert" data-testid="fabric-replaced"><AlertTriangle size={15} /> {replaced}</div>}
      {validationError && <div className="inline-alert error" role="alert"><AlertTriangle size={15} /> {validationError}</div>}
      {loading && !data && <p className="muted">{pending ? 'Loading the fabric list…' : 'Ranking fabrics for this design…'}</p>}
      {error && (
        <div className="inline-alert error" role="alert">
          {error}
          <button type="button" className="btn btn-outline btn-sm" onClick={() => load(currentPreferences, true)}><RefreshCw size={13} /> Retry</button>
        </div>
      )}

      {data?.published_study && <FabricPreferences study={data.published_study} value={currentPreferences}
        onChange={changePreferences} onCalculate={load} busy={loading} />}
      {publishedSamples.length > 0 && <>
        <h4 className="fabric-list-heading">{ranked ? 'Samples ranked for your preferences' : 'Published samples to compare'}</h4>
        <div className="fabric-grid" data-testid={ranked ? 'ranked-fabrics' : 'published-fabrics'}>{publishedSamples.map(card)}</div>
      </>}
      {catalogue.length > 0 && (publishedSamples.length > 0 ? (
        <details className="fabric-more">
          <summary>Choose another fabric type (general catalogue, unranked)</summary>
          <div className="fabric-grid" data-testid="compatible-fabrics">{catalogue.map(card)}</div>
        </details>
      ) : <div className="fabric-grid" data-testid={pending ? 'catalogue-fabrics' : ranked ? 'ranked-fabrics' : 'compatible-fabrics'}>{catalogue.map(card)}</div>)}

      {incompatible.length > 0 && (
        <details className="fabric-incompatible" data-testid="incompatible-fabrics">
          <summary>Not supported by this drafting block ({incompatible.length})</summary>
          <ul>{incompatible.map((f) => <li key={f.id}><strong>{f.name}</strong> — {f.incompatible_reason}</li>)}</ul>
        </details>
      )}

      {modalFabric && (
        <FabricDetailsModal
          fabric={modalFabric}
          rankingAudit={data?.ranking_audit}
          publishedStudy={data?.published_study}
          isSelected={selectedFabricId === modalFabric.id}
          onSelect={() => { if (modalFabric.compatible !== false) pick(modalFabric); }}
          onClose={() => setModalFabric(null)}
        />
      )}
    </section>
  );
}
