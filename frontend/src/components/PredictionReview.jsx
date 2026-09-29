import { useState, useEffect } from 'react';
import { CheckCircle2, AlertTriangle, Sparkles, RefreshCw, HelpCircle } from 'lucide-react';

import {
  ACTIVE_TAXONOMY_OPTIONS, HEAD_TITLES, supportOf, supportReport, consistencyError, UNSUPPORTED, APPROXIMATED,
  OUTSIDE_SCOPE_MESSAGE, predictionOutsideScope,
} from '../utils/designSchema';

// Re-exported for existing importers; the single frontend definition lives in utils/designSchema.js.
export { ACTIVE_TAXONOMY_OPTIONS };

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
  const suggest = (head) => {
    const label = predictions?.[head]?.label;
    return label && !predictionOutsideScope(head, label) ? label : '';
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
    <div
      style={{
        background: 'var(--surface-1, #FFFFFF)',
        border: '1px solid var(--border, #E2E8F0)',
        borderRadius: '12px',
        padding: '16px 18px',
        marginBottom: '20px',
        boxShadow: '0 1px 3px rgba(0,0,0,0.05)',
      }}
      data-testid="prediction-review-container"
    >
      {/* Header Bar */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px', flexWrap: 'wrap', gap: '8px' }}>
        <div>
          <div style={{ fontSize: '14px', fontWeight: '700', color: 'var(--text-primary, #0F172A)', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Sparkles size={16} style={{ color: '#2563EB' }} />
            <span>AI Feature Prediction & Confirmation</span>
          </div>
          <div style={{ fontSize: '12px', color: 'var(--text-secondary, #64748B)', marginTop: '2px' }}>
            Review AI suggestions and explicitly confirm design features before continuing.
          </div>
        </div>

        <div>
          {!isEditing && confirmedAttributes && (
            <span
              style={{
                fontSize: '11px',
                fontWeight: '600',
                color: '#166534',
                background: '#DCFCE7',
                padding: '4px 10px',
                borderRadius: '20px',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '4px',
              }}
              data-testid="confirmed-badge"
            >
              <CheckCircle2 size={13} />
              Confirmed Design Features
            </span>
          )}
          {hasPredictions && isEditing && (
            <span
              style={{
                fontSize: '11px',
                fontWeight: '600',
                color: '#1E40AF',
                background: '#DBEAFE',
                padding: '4px 10px',
                borderRadius: '20px',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '4px',
              }}
              data-testid="suggestion-badge"
            >
              <Sparkles size={12} />
              AI Suggestion — Editable
            </span>
          )}
        </div>
      </div>

      {/* Warning Notice for Low Confidence or Missing Attributes */}
      {hasPredictions && lowConfidenceHeads.length > 0 && isEditing && (
        <div
          role="alert"
          style={{
            background: '#FEF3C7',
            border: '1px solid #F59E0B',
            borderRadius: '8px',
            padding: '10px 12px',
            fontSize: '12px',
            color: '#92400E',
            marginBottom: '14px',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
          }}
          data-testid="low-confidence-alert"
        >
          <AlertTriangle size={16} style={{ color: '#D97706', flexShrink: 0 }} />
          <div>
            <strong>Low Confidence Detected:</strong> Low prediction confidence on{' '}
            <em>{lowConfidenceHeads.map((h) => HEAD_TITLES[h] || h).join(', ')}</em>. Please double-check and select the intended features.
          </div>
        </div>
      )}

      {isEditing && outsideScopeHeads.length > 0 && (
        <div
          role="alert"
          style={{ background: '#FEF3C7', border: '1px solid #F59E0B', borderRadius: '8px', padding: '10px 12px', fontSize: '12px', color: '#92400E', marginBottom: '14px' }}
          data-testid="outside-scope-alert"
        >
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
        <div
          style={{
            background: '#F1F5F9',
            border: '1px solid #CBD5E1',
            borderRadius: '8px',
            padding: '10px 12px',
            fontSize: '12px',
            color: '#475569',
            marginBottom: '14px',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
          }}
          data-testid="fallback-notice"
        >
          <HelpCircle size={16} style={{ color: '#64748B', flexShrink: 0 }} />
          <div>
            Manual Feature Selection Mode (Multi-task predictions unavailable). Select features below manually.
          </div>
        </div>
      )}

      {error && (
        <div
          style={{
            background: '#FEE2E2',
            border: '1px solid #EF4444',
            borderRadius: '8px',
            padding: '8px 12px',
            fontSize: '12px',
            color: '#991B1B',
            marginBottom: '12px',
          }}
          data-testid="error-message"
        >
          {error}
        </div>
      )}

      {consistency && (
        <div
          role="alert"
          style={{ background: '#FEE2E2', border: '1px solid #EF4444', borderRadius: '8px', padding: '8px 12px', fontSize: '12px', color: '#991B1B', marginBottom: '12px' }}
          data-testid="consistency-error"
        >
          {consistency}
        </div>
      )}

      {report.unsupported.length > 0 && (
        <div
          role="alert"
          style={{ background: '#FEE2E2', border: '1px solid #EF4444', borderRadius: '8px', padding: '8px 12px', fontSize: '12px', color: '#991B1B', marginBottom: '12px' }}
          data-testid="unsupported-alert"
        >
          <strong>Cannot be drafted yet:</strong>{' '}
          {report.unsupported.map((u) => `${HEAD_TITLES[u.head]}: ${u.label}`).join('; ')}.
          The system will not substitute a different design — please choose a supported option.
        </div>
      )}

      {/* 4 Classification Heads Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '12px', marginBottom: '16px' }}>
        {Object.keys(HEAD_TITLES).map((headKey) => {
          const title = HEAD_TITLES[headKey];
          const headPred = predictions[headKey];
          const options = ACTIVE_TAXONOMY_OPTIONS[headKey] || [];
          const rawConfPct = headPred?.confidence != null ? (headPred.confidence * 100).toFixed(1) : null;
          const isLowConf = headPred?.requires_user_confirmation || false;

          return (
            <div
              key={headKey}
              style={{
                background: 'var(--surface-2, #F8FAFC)',
                border: '1px solid var(--border-subtle, #E2E8F0)',
                borderRadius: '8px',
                padding: '10px 12px',
              }}
              data-testid={`head-card-${headKey}`}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                <label style={{ fontSize: '12px', fontWeight: '600', color: 'var(--text-primary, #1E293B)' }}>
                  {title}
                </label>
                {rawConfPct !== null && (
                  <span
                    style={{
                      fontSize: '10px',
                      fontWeight: '600',
                      padding: '2px 6px',
                      borderRadius: '4px',
                      background: isLowConf ? '#FEF3C7' : '#DCFCE7',
                      color: isLowConf ? '#92400E' : '#166534',
                    }}
                    data-testid={`confidence-tag-${headKey}`}
                  >
                    {rawConfPct}% {isLowConf ? 'Low' : 'High'}
                  </span>
                )}
              </div>

              {/* Top 3 Predictions Pill Summary if available */}
              {headPred?.top_3 && headPred.top_3.length > 0 && isEditing && (
                <div style={{ fontSize: '10px', color: 'var(--text-tertiary, #64748B)', marginBottom: '6px' }} data-testid={`top-3-${headKey}`}>
                  Top: {headPred.top_3.map((t) => `${t.class_name} (${(t.confidence * 100).toFixed(0)}%)`).join(', ')}
                </div>
              )}

              {/* Select Control */}
              <select
                className="form-select"
                style={{
                  width: '100%',
                  height: '34px',
                  fontSize: '12px',
                  background: isEditing ? '#FFFFFF' : '#F1F5F9',
                  color: 'var(--text-primary, #0F172A)',
                  border: '1px solid var(--border-strong, #CBD5E1)',
                  borderRadius: '6px',
                }}
                value={selections[headKey] || ''}
                onChange={(e) => handleChange(headKey, e.target.value)}
                disabled={!isEditing}
                data-testid={`select-${headKey}`}
              >
                <option value="">-- Select {title} --</option>
                {options.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label} ({opt.value})
                  </option>
                ))}
              </select>
              {(() => {
                const opt = supportOf(headKey, selections[headKey]);
                if (!opt || (opt.support !== UNSUPPORTED && opt.support !== APPROXIMATED) || !opt.note) return null;
                const bad = opt.support === UNSUPPORTED;
                return (
                  <div
                    style={{ fontSize: '10px', marginTop: '6px', color: bad ? '#991B1B' : '#92400E' }}
                    data-testid={`support-note-${headKey}`}
                  >
                    {bad ? 'Unsupported' : 'Approximated'}: {opt.note}
                  </div>
                );
              })()}
            </div>
          );
        })}
      </div>

      {/* Confirmation Action Buttons */}
      {isEditing ? (
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ fontSize: '11px', color: 'var(--text-secondary, #64748B)' }}>
            All 4 features must be selected to enable confirmation.
          </div>
          <button
            className="btn btn-primary"
            style={{
              padding: '8px 18px',
              fontSize: '12px',
              fontWeight: '600',
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
            }}
            onClick={handleConfirmSubmit}
            disabled={!isComplete || Boolean(consistency) || isSubmitting}
            data-testid="confirm-btn"
          >
            {isSubmitting ? (
              <>Saving...</>
            ) : (
              <>
                <CheckCircle2 size={15} /> Confirm Design Features
              </>
            )}
          </button>
        </div>
      ) : (
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ fontSize: '11px', color: '#166534', fontWeight: '500' }}>
            ✓ Confirmed for fabric recommendation & pattern generation.
          </div>
          <button
            className="btn btn-outline"
            style={{
              height: '32px',
              fontSize: '11px',
              padding: '0 12px',
              display: 'inline-flex',
              alignItems: 'center',
              gap: '4px',
            }}
            onClick={() => setIsEditing(true)}
            data-testid="edit-reconfirm-btn"
          >
            <RefreshCw size={13} /> Edit & Re-confirm
          </button>
        </div>
      )}
    </div>
  );
}
