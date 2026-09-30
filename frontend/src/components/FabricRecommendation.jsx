import { useEffect, useState } from 'react';
import { AlertTriangle, Check, ChevronDown, Info, RefreshCw } from 'lucide-react';
import { fabricAPI } from '../services/api';
import FabricDetailsModal from './FabricDetailsModal';

const gsmText = (f) => (f.gsm_range ? `${f.gsm_range.min}–${f.gsm_range.max} GSM` : null);
const firstWord = (text) => String(text || '').split(/[ —-]/)[0];

/**
 * Rule-based fabric recommendation for the CONFIRMED design and fit (backend: fabric_selection.py).
 * Shows the 2–4 recommended fabrics, lets the user pick any other compatible fabric, and lists the
 * fabrics that cannot be used for this design with the reason. Nothing here is invented: no price,
 * stock or availability is shown because none is stored.
 */
export default function FabricRecommendation({ confirmedAttributes, fitPreference = 'standard', selectedFabricId, onSelectFabric, validationError }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [modalFabric, setModalFabric] = useState(null);
  const [showOthers, setShowOthers] = useState(false);
  const [failedImages, setFailedImages] = useState({});

  const pick = (f) => onSelectFabric(f.id, f.name, f.construction);

  const load = async () => {
    setLoading(true);
    setError('');
    try {
      const res = await fabricAPI.getRecommendations({ confirmed_attributes: confirmedAttributes, fit_preference: fitPreference });
      setData(res.data);
      const fabrics = res.data.fabrics || res.data.recommendations || [];
      const current = fabrics.find((f) => f.id === selectedFabricId);
      if (!current || !current.compatible) {                     // keep a compatible choice, else take the top recommendation
        const top = fabrics.find((f) => f.recommended);
        if (top) pick(top);
      }
    } catch {
      setError('Fabric recommendations could not be loaded. Please check the connection and try again.');
    } finally {
      setLoading(false);
    }
  };

  const designKey = JSON.stringify(confirmedAttributes || {});
  useEffect(() => { if (confirmedAttributes) load(); }, [designKey, fitPreference]); // eslint-disable-line react-hooks/exhaustive-deps

  const fabrics = data?.fabrics || data?.recommendations || [];
  const recommended = fabrics.filter((f) => f.recommended);
  const others = fabrics.filter((f) => f.compatible && !f.recommended);
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
            <small>{[gsmText(f), f.weight && `${f.weight} weight`].filter(Boolean).join(' · ')}</small>
            <span className="fabric-tags">
              <span className="tag">{f.stretch}</span>
              <span className="tag">{firstWord(f.breathability)} breathability</span>
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
          <h3 id="fabric-h">Recommended fabrics</h3>
          <p>Chosen by fixed, explainable rules from your confirmed design and fit — not by AI.</p>
        </div>
        <span className="method-badge">Rule-Based Fabric Recommendation</span>
      </div>

      {validationError && <div className="inline-alert error" role="alert"><AlertTriangle size={15} /> {validationError}</div>}
      {loading && !data && <p className="muted">Ranking fabrics for this design…</p>}
      {error && (
        <div className="inline-alert error" role="alert">
          {error}
          <button type="button" className="btn btn-outline btn-sm" onClick={load}><RefreshCw size={13} /> Retry</button>
        </div>
      )}

      {recommended.length > 0 && <div className="fabric-grid" data-testid="recommended-fabrics">{recommended.map(card)}</div>}

      {others.length > 0 && (
        <div className="fabric-more">
          <button type="button" className="text-btn" aria-expanded={showOthers} onClick={() => setShowOthers((v) => !v)}>
            <ChevronDown size={15} className={showOthers ? 'rotate' : ''} /> Other compatible fabrics ({others.length})
          </button>
          {showOthers && <div className="fabric-grid compact" data-testid="other-fabrics">{others.map(card)}</div>}
        </div>
      )}

      {incompatible.length > 0 && (
        <details className="fabric-incompatible" data-testid="incompatible-fabrics">
          <summary>Not suitable for this design ({incompatible.length})</summary>
          <ul>{incompatible.map((f) => <li key={f.id}><strong>{f.name}</strong> — {f.incompatible_reason}</li>)}</ul>
        </details>
      )}

      {modalFabric && (
        <FabricDetailsModal
          fabric={modalFabric}
          isSelected={selectedFabricId === modalFabric.id}
          onSelect={() => { if (modalFabric.compatible !== false) pick(modalFabric); }}
          onClose={() => setModalFabric(null)}
        />
      )}
    </section>
  );
}
