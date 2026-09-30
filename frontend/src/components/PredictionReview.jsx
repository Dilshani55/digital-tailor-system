import { useState, useEffect } from 'react';
import { CheckCircle2, AlertTriangle, Sparkles, RefreshCw, HelpCircle, Shirt, Circle, Ruler, Scissors } from 'lucide-react';

import {
  ACTIVE_TAXONOMY_OPTIONS, HEAD_TITLES, supportOf, supportReport, consistencyError, UNSUPPORTED, APPROXIMATED,
  OUTSIDE_SCOPE_MESSAGE, LOW_CONFIDENCE_MESSAGE, predictionOutsideScope, optionBlockedReason, labelOf,
} from '../utils/designSchema';

// Re-exported for existing importers; the single frontend definition lives in utils/designSchema.js.
export { ACTIVE_TAXONOMY_OPTIONS };

const HEAD_ICONS = { garment_type: Shirt, neckline_type: Circle, sleeve_length: Ruler, sleeve_style: Scissors };

export default function PredictionReview({
  garmentAttributes,
  confirmedAttributes,
  onConfirm,
  isSubmitting = false,
  error = ''
}) {
  const predictions = garmentAttributes?.predictions || {};
  const lowConfidenceHeads = garmentAttributes?.low_confidence_heads || [];
  const hasPredictions = Boolean(garmentAttributes && Object.keys(predictions).length > 0);

  // A prediction is pre-selected ONLY if it is one of the user-selectable classes. Anything else stays
  // blank (never mapped to a "similar" class) and the user must choose manually.
  // A prediction is also NOT pre-selected when it cannot be drafted (e.g. collared neck, or a sleeve
  // style the predicted garment does not support): it stays visible and the user picks a supported option.
  const predictedSet = Object.fromEntries(Object.keys(HEAD_TITLES).map((h) => [h, predictions?.[h]?.label]));
  const draftBlock = (head) => {
    const label = predictions?.[head]?.label;
    if (!label || predictionOutsideScope(head, label)) return '';
    return optionBlockedReason(head, label, predictedSet);
  };
  // "Uncertain / please select": a guess the model itself flags as unreliable is shown but never pre-selected.
  const isUncertain = (head) => Boolean(predictions?.[head]?.uncertain ?? predictions?.[head]?.requires_user_confirmation);
  const suggest = (head) => {
    const label = predictions?.[head]?.label;
    return label && !predictionOutsideScope(head, label) && !draftBlock(head) && !isUncertain(head) ? label : '';
  };
  const outsideScopeHeads = Object.keys(HEAD_TITLES).filter((h) => predictionOutsideScope(h, predictions?.[h]?.label));

  // Initial state derived from confirmed values > selectable predictions > empty strings for manual mode
  const [selections, setSelections] = useState({
    garment_type: confirmedAttributes?.garment_type || suggest('garment_type'),
    neckline_type: confirmedAttributes?.neckline_type || suggest('neckline_type'),
    sleeve_length: confirmedAttributes?.sleeve_length || suggest('sleeve_length'),
    sleeve_style: confirmedAttributes?.sleeve_style || suggest('sleeve_style'),
  });

  const [isEditing, setIsEditing] = useState(!confirmedAttributes || Object.keys(confirmedAttributes).length === 0);

  useEffect(() => {
    if (confirmedAttributes && Object.keys(confirmedAttributes).length > 0) {
      setSelections({
        garment_type: confirmedAttributes.garment_type || '',
        neckline_type: confirmedAttributes.neckline_type || '',
        sleeve_length: confirmedAttributes.sleeve_length || '',
        sleeve_style: confirmedAttributes.sleeve_style || '',
      });
      setIsEditing(false);
    } else if (hasPredictions) {
      setSelections({
        garment_type: suggest('garment_type'),
        neckline_type: suggest('neckline_type'),
        sleeve_length: suggest('sleeve_length'),
        sleeve_style: suggest('sleeve_style'),
      });
    } else {
      setSelections({
        garment_type: '',
        neckline_type: '',
        sleeve_length: '',
        sleeve_style: '',
      });
    }
  }, [garmentAttributes, confirmedAttributes]);

  const handleChange = (head, value) => {
    setSelections((prev) => ({ ...prev, [head]: value }));
  };

  const handleConfirmSubmit = (e) => {
    e.preventDefault();
    if (onConfirm) {
      onConfirm(selections);
    }
  };

  const isComplete = Boolean(
    selections.garment_type &&
    selections.neckline_type &&
    selections.sleeve_length &&
    selections.sleeve_style
  );
  const report = supportReport(selections);
  const consistency = consistencyError(selections);

  return (
    <div data-testid="prediction-review-container">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8, flexWrap: 'wrap', marginBottom: 12 }}>
        <p className="form-hint" style={{ margin: 0 }}>
          {hasPredictions ? 'The AI suggestion is a starting point — check every feature and correct anything that is wrong. A model score is not proof that a prediction is correct.'
            : 'Choose each feature of the garment you want to make.'}
        </p>
        {!isEditing && confirmedAttributes && (
          <span className="pill good" data-testid="confirmed-badge"><CheckCircle2 size={13} /> Confirmed Design Features</span>
        )}
        {hasPredictions && isEditing && (
          <span className="pill warn" data-testid="suggestion-badge"><Sparkles size={12} /> AI Suggestion — Editable</span>
        )}
      </div>

      {hasPredictions && lowConfidenceHeads.length > 0 && isEditing && (
        <div role="alert" className="alert warn" data-testid="low-confidence-alert" style={{ marginBottom: 12 }}>
          <AlertTriangle size={16} style={{ flexShrink: 0 }} />
          <div><strong>Low confidence:</strong> please double-check <em>{lowConfidenceHeads.map((h) => HEAD_TITLES[h] || h).join(', ')}</em>.</div>
        </div>
      )}

      {isEditing && outsideScopeHeads.length > 0 && (
        <div role="alert" className="alert warn" data-testid="outside-scope-alert" style={{ marginBottom: 12, display: 'block' }}>
          <strong>{OUTSIDE_SCOPE_MESSAGE}</strong>
          <ul style={{ margin: '6px 0 0', paddingLeft: '18px' }}>
            {outsideScopeHeads.map((h) => (
              <li key={h} data-testid={`outside-scope-${h}`}>
                {HEAD_TITLES[h]}: detected “{predictions[h].label}”
                {predictions[h].confidence != null ? ` (${(predictions[h].confidence * 100).toFixed(0)}%)` : ''} — please choose from the list.
              </li>
            ))}
          </ul>
        </div>
      )}

      {!hasPredictions && (
        <div className="alert info" data-testid="fallback-notice" style={{ marginBottom: 12 }}>
          <HelpCircle size={16} style={{ flexShrink: 0 }} />
          <div>Manual feature selection — no AI prediction is available for this design. Select each feature below.</div>
        </div>
      )}

      {error && <div className="alert error" data-testid="error-message" style={{ marginBottom: 12 }}>{error}</div>}
      {consistency && <div role="alert" className="alert error" data-testid="consistency-error" style={{ marginBottom: 12 }}>{consistency}</div>}
      {report.unsupported.length > 0 && (
        <div role="alert" className="alert error" data-testid="unsupported-alert" style={{ marginBottom: 12, display: 'block' }}>
          <strong>Cannot be drafted yet:</strong>{' '}
          {report.unsupported.map((u) => `${HEAD_TITLES[u.head]}: ${u.label}`).join('; ')}.
          The system will not substitute a different design — please choose a supported option.
        </div>
      )}

      <div className="head-cards">
        {Object.keys(HEAD_TITLES).map((headKey) => {
          const title = HEAD_TITLES[headKey];
          const headPred = predictions[headKey];
          const options = ACTIVE_TAXONOMY_OPTIONS[headKey] || [];
          const rawConfPct = headPred?.confidence != null ? (headPred.confidence * 100).toFixed(1) : null;
          const isLowConf = isUncertain(headKey);
          const Icon = HEAD_ICONS[headKey];
          const opt = supportOf(headKey, selections[headKey]);
          return (
            <div key={headKey} className="head-card" data-testid={`head-card-${headKey}`}>
              <span className="head-card-icon" aria-hidden="true"><Icon size={22} /></span>
              <div>
                <div className="head-card-top">
                  <label htmlFor={`sel-${headKey}`}>{title}</label>
                  {rawConfPct !== null && (
                    <span className={`pill ${isLowConf ? 'warn' : 'good'}`} data-testid={`confidence-tag-${headKey}`}>
                      Model score {rawConfPct}%{isLowConf ? ' · uncertain' : ''}
                    </span>
                  )}
                </div>
                {isLowConf && isEditing && (
                  <div role="note" className="head-note warn" data-testid={`low-confidence-${headKey}`} style={{ marginTop: 0, marginBottom: 6 }}>
                    Uncertain — please select this feature yourself.
                    {headPred?.label ? ` AI best guess: “${labelOf(headKey, headPred.label)}” (${rawConfPct}%).` : ''}
                  </div>
                )}
                {isEditing && draftBlock(headKey) && (
                  <div role="note" className="head-note warn" data-testid={`not-draftable-${headKey}`} style={{ marginTop: 0, marginBottom: 6 }}>
                    AI suggested “{labelOf(headKey, headPred.label)}”, but this pattern cannot be drafted
                    ({draftBlock(headKey).toLowerCase()}). Please choose a supported option.
                  </div>
                )}
                {isEditing && headKey === 'garment_type' && (hasPredictions || selections.garment_type) && (
                  <div role="note" className="head-note info" data-testid="garment-length-note" style={{ marginTop: 0, marginBottom: 6 }}>
                    A crop top and a T-shirt can look alike in a photo. Choose the garment you want to make: a crop top ends
                    above the waist, a T-shirt reaches at least the waist. You set the finished length in the next step.
                  </div>
                )}
                <select id={`sel-${headKey}`} className="form-select" value={selections[headKey] || ''}
                        onChange={(e) => handleChange(headKey, e.target.value)} disabled={!isEditing}
                        data-testid={`select-${headKey}`}>
                  <option value="">-- Select {title} --</option>
                  {options.map((o) => {
                    const blocked = optionBlockedReason(headKey, o.value, selections);
                    return (
                      <option key={o.value} value={o.value} disabled={Boolean(blocked)}>
                        {o.label} ({o.value}){blocked ? ` — ${blocked}` : ''}
                      </option>
                    );
                  })}
                </select>
                {headPred?.top_3 && headPred.top_3.length > 0 && isEditing && (
                  <div className="head-note info" data-testid={`top-3-${headKey}`}>
                    AI top 3: {headPred.top_3.map((t) => `${t.class_name} (${(t.confidence * 100).toFixed(0)}%)`).join(', ')}
                  </div>
                )}
                {opt && (opt.support === UNSUPPORTED || opt.support === APPROXIMATED) && opt.note && (
                  <div className={`head-note ${opt.support === UNSUPPORTED ? 'bad' : 'warn'}`} data-testid={`support-note-${headKey}`}>
                    {opt.support === UNSUPPORTED ? 'Unsupported' : 'Approximated'}: {opt.note}
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {isEditing ? (
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
          <span className="form-hint">All 4 features must be selected and draftable to confirm.</span>
          <button className="btn btn-primary" onClick={handleConfirmSubmit}
                  disabled={!isComplete || Boolean(consistency) || !report.supported || isSubmitting} data-testid="confirm-btn">
            {isSubmitting ? 'Saving…' : <><CheckCircle2 size={16} /> Confirm Design Features</>}
          </button>
        </div>
      ) : (
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
          <span className="form-hint" style={{ color: 'var(--accent)', fontWeight: 600 }}>✓ Confirmed for fabric recommendation and pattern drafting.</span>
          <button className="btn btn-outline btn-sm" onClick={() => setIsEditing(true)} data-testid="edit-reconfirm-btn">
            <RefreshCw size={13} /> Edit & Re-confirm
          </button>
        </div>
      )}
    </div>
  );
}
