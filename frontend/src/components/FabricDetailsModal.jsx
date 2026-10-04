import { useState, useEffect, useRef } from 'react';
import { X, Check, ChevronDown, ChevronUp, Info, Sparkles } from 'lucide-react';

export default function FabricDetailsModal({ fabric, rankingAudit, publishedStudy, isSelected, onSelect, onClose }) {
  const [showTechDetails, setShowTechDetails] = useState(false);
  const [imgError, setImgError] = useState(false);
  const modalRef = useRef(null);

  // Close modal on Escape key press
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  if (!fabric) return null;

  const handleOverlayClick = (e) => {
    if (e.target === e.currentTarget) {
      onClose();
    }
  };

  if (fabric.study_id) {
    const audit = rankingAudit?.profile_id === fabric.study_id ? rankingAudit : null;
    const criteria = audit?.criteria || publishedStudy?.criteria || [];
    return (
      <div className="modal-overlay published-fabric-overlay" role="dialog" aria-modal="true" aria-labelledby="fabric-modal-title" onClick={handleOverlayClick}>
        <div className="published-fabric-modal">
          <div className="section-head">
            <h2 id="fabric-modal-title">{fabric.name}</h2>
            <button type="button" className="btn btn-outline btn-sm" aria-label="Close modal" onClick={onClose}><X size={20} /></button>
          </div>
          <p>{fabric.simple_description}</p>
          <p>{fabric.explanation}</p>
          <h4>Recorded sample evidence</h4>
          <p>Sample ID: {fabric.research_sample.sample_id}. Values apply to this sample.</p>
          <div style={{ overflowX: 'auto' }}>
            <table>
              <thead><tr><th>Property</th><th>Measured value</th><th>Your goal</th><th>Weight</th><th>Source table</th></tr></thead>
              <tbody>{criteria.map((c, i) => {
                const observation = fabric.research_sample.values[c.id];
                return <tr key={c.id}>
                  <td>{c.label}</td><td>{observation.value} {observation.unit}</td>
                  <td>{c.goal_options.find((g) => g.value === c.objective)?.label || 'Not set'}</td>
                  <td>{audit ? `${(audit.ahp.weights[i] * 100).toFixed(1)}%` : 'Not set'}</td>
                  <td>{observation.table}</td>
                </tr>;
              })}</tbody>
            </table>
          </div>
          {audit && <p>Your comparison consistency ratio: {audit.ahp.consistency_ratio.toFixed(3)} (accepted at 0.10 or below). TOPSIS closeness is a relative comparison, not a probability of fit.</p>}
          <p><a href={fabric.source_url} target="_blank" rel="noreferrer">{fabric.reference_source}</a></p>
          <details><summary>Measurement methods and scope</summary>
            <ul>{criteria.map((c) => <li key={c.id}><strong>{c.label}:</strong> {c.protocol}</li>)}</ul>
            <p>{audit?.scope_note || publishedStudy?.scope_note}</p>
          </details>
          <div className="form-actions">
            <button type="button" className="btn btn-outline" onClick={onClose}>Close</button>
            <button type="button" className="btn btn-primary" onClick={() => { onSelect(); onClose(); }}>
              {isSelected ? 'Selected' : 'Select this sample'}
            </button>
          </div>
        </div>
      </div>
    );
  }

  const getStatusBadgeStyle = (status) => {
    switch (status) {
      case 'Top ranked sample':
        return { background: '#2D5A43', color: '#FFFFFF', border: '1px solid #1E3A2B' };
      case 'Ranked sample':
        return { background: '#D97706', color: '#FFFFFF', border: '1px solid #B45309' };
      case 'Compatible — unranked':
        return { background: '#2563EB', color: '#FFFFFF', border: '1px solid #1D4ED8' };
      default:
        return { background: '#6B7280', color: '#FFFFFF', border: '1px solid #4B5563' };
    }
  };

  return (
    <div
      className="modal-overlay"
      onClick={handleOverlayClick}
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundColor: 'rgba(15, 23, 42, 0.75)',
        backdropFilter: 'blur(4px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 1000,
        padding: '16px'
      }}
      role="dialog"
      aria-modal="true"
      aria-labelledby="fabric-modal-title"
    >
      <div
        ref={modalRef}
        style={{
          background: 'var(--surface-1, #FFFFFF)',
          borderRadius: '16px',
          width: '100%',
          maxWidth: '680px',
          maxHeight: '90vh',
          overflowY: 'auto',
          boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.2), 0 10px 10px -5px rgba(0, 0, 0, 0.1)',
          border: '1px solid var(--border, #E2E8F0)',
          display: 'flex',
          flexDirection: 'column'
        }}
      >
        {/* Header */}
        <div style={{
          padding: '20px 24px',
          borderBottom: '1px solid var(--border, #E2E8F0)',
          display: 'flex',
          justify: 'space-between',
          alignItems: 'center',
          background: 'var(--surface-2, #F8FAFC)',
          borderTopLeftRadius: '16px',
          borderTopRightRadius: '16px'
        }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <h2 id="fabric-modal-title" style={{ margin: 0, fontSize: '20px', fontWeight: '700', color: 'var(--text-primary, #0F172A)' }}>
                {fabric.name}
              </h2>
              <span style={{
                fontSize: '11px',
                fontWeight: '700',
                padding: '4px 10px',
                borderRadius: '12px',
                ...getStatusBadgeStyle(fabric.recommendation_status)
              }}>
                {fabric.recommendation_status}
              </span>
            </div>
            <span style={{ fontSize: '12px', color: 'var(--text-accent, #2D5A43)', fontWeight: '600', display: 'flex', alignItems: 'center', gap: '4px', marginTop: '4px' }}>
              <Sparkles size={13} /> {fabric.rank ? 'AHP / TOPSIS sample comparison' : 'Catalogue fabric guide'}
            </span>
          </div>

          <button
            onClick={onClose}
            aria-label="Close modal"
            style={{
              background: 'transparent',
              border: 'none',
              cursor: 'pointer',
              color: 'var(--text-secondary, #64748B)',
              padding: '6px',
              borderRadius: '50%',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              transition: 'background 0.15s'
            }}
          >
            <X size={22} />
          </button>
        </div>

        {/* Modal Body */}
        <div style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '20px' }}>
          
          {/* Image & Key Attributes Row */}
          <div style={{ display: 'grid', gridTemplateColumns: 'minmax(180px, 240px) 1fr', gap: '20px', alignItems: 'start' }}>
            <div style={{
              width: '100%',
              height: '180px',
              borderRadius: '12px',
              overflow: 'hidden',
              border: '1px solid var(--border, #CBD5E1)',
              background: '#F1F5F9',
              position: 'relative'
            }}>
              {!imgError && fabric.local_image ? (
                <img
                  src={fabric.local_image}
                  alt={`Close-up fabric texture image of ${fabric.name}`}
                  onError={() => setImgError(true)}
                  style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                />
              ) : (
                <div style={{
                  width: '100%',
                  height: '100%',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  justifyContent: 'center',
                  background: 'linear-gradient(135deg, #2D5A43 0%, #1E3A2B 100%)',
                  color: '#FFFFFF',
                  padding: '12px',
                  textAlign: 'center'
                }}>
                  <span style={{ fontSize: '24px', fontWeight: 'bold', marginBottom: '4px' }}>{fabric.name.charAt(0)}</span>
                  <span style={{ fontSize: '13px', fontWeight: '600' }}>{fabric.name}</span>
                  <span style={{ fontSize: '10px', opacity: 0.8, marginTop: '4px' }}>Texture Swatch</span>
                </div>
              )}
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '13px' }}>
              <div style={{ background: '#F0FDF4', border: '1px solid #BBF7D0', padding: '10px 12px', borderRadius: '8px', color: '#166534' }}>
                <strong style={{ display: 'block', fontSize: '12px', color: '#14532D', marginBottom: '2px' }}>
                  {fabric.rank ? 'Why this sample ranks here:' : 'Fabric selection:'}
                </strong>
                <span>{fabric.explanation}</span>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', marginTop: '4px' }}>
                <div style={{ background: 'var(--surface-2, #F8FAFC)', padding: '8px 10px', borderRadius: '6px', border: '1px solid var(--border, #E2E8F0)' }}>
                  <span style={{ fontSize: '11px', color: 'var(--text-secondary, #64748B)', display: 'block' }}>Weight</span>
                  <strong style={{ color: 'var(--text-primary, #0F172A)' }}>{fabric.weight}</strong>
                </div>
                <div style={{ background: 'var(--surface-2, #F8FAFC)', padding: '8px 10px', borderRadius: '6px', border: '1px solid var(--border, #E2E8F0)' }}>
                  <span style={{ fontSize: '11px', color: 'var(--text-secondary, #64748B)', display: 'block' }}>Stretch</span>
                  <strong style={{ color: 'var(--text-primary, #0F172A)' }}>{fabric.stretch}</strong>
                </div>
                <div style={{ background: 'var(--surface-2, #F8FAFC)', padding: '8px 10px', borderRadius: '6px', border: '1px solid var(--border, #E2E8F0)' }}>
                  <span style={{ fontSize: '11px', color: 'var(--text-secondary, #64748B)', display: 'block' }}>Feel / Texture</span>
                  <span style={{ fontSize: '12px', color: 'var(--text-primary, #0F172A)', fontWeight: '500' }}>{fabric.feel}</span>
                </div>
                <div style={{ background: 'var(--surface-2, #F8FAFC)', padding: '8px 10px', borderRadius: '6px', border: '1px solid var(--border, #E2E8F0)' }}>
                  <span style={{ fontSize: '11px', color: 'var(--text-secondary, #64748B)', display: 'block' }}>Drape</span>
                  <span style={{ fontSize: '12px', color: 'var(--text-primary, #0F172A)', fontWeight: '500' }}>{fabric.drape}</span>
                </div>
              </div>
            </div>
          </div>

          {/* Suitable Garments & Climate */}
          {fabric.research_sample && rankingAudit?.criteria && (
            <div>
              <h4>Recorded sample evidence</h4>
              <p>Sample: {fabric.research_sample.label} ({fabric.research_sample.sample_id}). These measurements apply to this sample.</p>
              <table style={{ width: '100%', fontSize: '12px', textAlign: 'left' }}>
                <thead><tr><th>Criterion</th><th>Observed value</th><th>Weight</th><th>Source</th></tr></thead>
                <tbody>{rankingAudit.criteria.map((c, index) => {
                  const observation = fabric.research_sample.values[c.id];
                  return <tr key={c.id}><td>{c.label}</td><td>{observation.value} {observation.unit}</td><td>{(rankingAudit.ahp.weights[index] * 100).toFixed(1)}%</td><td>{observation.source}</td></tr>;
                })}</tbody>
              </table>
              <p>{rankingAudit.weight_source === 'user_preferences' ? 'Your' : 'Expert'} comparison consistency ratio: {rankingAudit.ahp.consistency_ratio.toFixed(3)}. TOPSIS closeness is a relative comparison, not a probability of fit.</p>
              <p>Profile source: {rankingAudit.profile_source}</p>
            </div>
          )}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
            <div style={{ background: 'var(--surface-2, #F8FAFC)', padding: '12px 14px', borderRadius: '8px', border: '1px solid var(--border, #E2E8F0)' }}>
              <h4 style={{ margin: '0 0 6px 0', fontSize: '13px', fontWeight: '600', color: 'var(--text-primary, #0F172A)' }}>
                Best Garment Uses
              </h4>
              <ul style={{ margin: 0, paddingLeft: '18px', fontSize: '12px', color: 'var(--text-secondary, #475569)' }}>
                {fabric.best_garment_uses?.map((use, i) => (
                  <li key={i} style={{ marginBottom: '2px' }}>{use}</li>
                ))}
              </ul>
            </div>

            <div style={{ background: 'var(--surface-2, #F8FAFC)', padding: '12px 14px', borderRadius: '8px', border: '1px solid var(--border, #E2E8F0)' }}>
              <h4 style={{ margin: '0 0 6px 0', fontSize: '13px', fontWeight: '600', color: 'var(--text-primary, #0F172A)' }}>
                Sri Lankan Climate Suitability
              </h4>
              <p style={{ margin: 0, fontSize: '12px', color: 'var(--text-secondary, #475569)', lineHeight: '1.4' }}>
                {fabric.climate_suitability}
              </p>
            </div>
          </div>

          {/* Advantages & Limitations */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
            <div>
              <h4 style={{ margin: '0 0 6px 0', fontSize: '13px', fontWeight: '600', color: '#15803D' }}>
                Main Advantages
              </h4>
              <ul style={{ margin: 0, paddingLeft: '18px', fontSize: '12px', color: 'var(--text-secondary, #475569)' }}>
                {fabric.advantages?.map((adv, i) => (
                  <li key={i} style={{ marginBottom: '3px' }}>{adv}</li>
                ))}
              </ul>
            </div>

            <div>
              <h4 style={{ margin: '0 0 6px 0', fontSize: '13px', fontWeight: '600', color: '#C2410C' }}>
                Things to Consider
              </h4>
              <ul style={{ margin: 0, paddingLeft: '18px', fontSize: '12px', color: 'var(--text-secondary, #475569)' }}>
                {fabric.limitations?.map((lim, i) => (
                  <li key={i} style={{ marginBottom: '3px' }}>{lim}</li>
                ))}
              </ul>
            </div>
          </div>

          {/* Care Instructions & Sewing Difficulty */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', fontSize: '12px' }}>
            <div>
              <strong style={{ color: 'var(--text-primary, #0F172A)', display: 'block', marginBottom: '2px' }}>Care Instructions:</strong>
              <span style={{ color: 'var(--text-secondary, #475569)' }}>{fabric.care_instructions}</span>
            </div>
            <div>
              <strong style={{ color: 'var(--text-primary, #0F172A)', display: 'block', marginBottom: '2px' }}>Sewing Difficulty:</strong>
              <span style={{ color: 'var(--text-secondary, #475569)' }}>{fabric.sewing_difficulty}</span>
            </div>
          </div>

          {/* Collapsible Technical Details */}
          <div style={{ border: '1px solid var(--border, #E2E8F0)', borderRadius: '8px', overflow: 'hidden' }}>
            <button
              onClick={() => setShowTechDetails(!showTechDetails)}
              style={{
                width: '100%',
                padding: '10px 14px',
                background: 'var(--surface-2, #F8FAFC)',
                border: 'none',
                display: 'flex',
                justify: 'space-between',
                alignItems: 'center',
                cursor: 'pointer',
                fontSize: '13px',
                fontWeight: '600',
                color: 'var(--text-primary, #0F172A)'
              }}
            >
              <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <Info size={16} /> Technical Details & Supplier Notes
              </span>
              {showTechDetails ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
            </button>

            {showTechDetails && (
              <div style={{ padding: '12px 14px', background: 'var(--surface-1, #FFFFFF)', fontSize: '12px', display: 'flex', flexDirection: 'column', gap: '8px', borderTop: '1px solid var(--border, #E2E8F0)' }}>
                <div>
                  <strong>Construction: </strong>
                  <span>{fabric.technical_details?.construction}</span>
                </div>
                <div>
                  <strong>GSM Specs: </strong>
                  <span>{fabric.technical_details?.typical_gsm_range}</span>
                </div>
                <div>Catalogue properties are general descriptions, not laboratory measurements of your sample.</div>
                <div>
                  <strong>Composition Note: </strong>
                  <span>{fabric.technical_details?.composition_note}</span>
                </div>
                <div>
                  <strong>Pricing Info: </strong>
                  <span style={{ color: 'var(--text-accent, #2D5A43)', fontWeight: '600' }}>
                    {fabric.technical_details?.price_note || 'Price varies by supplier'}
                  </span>
                </div>
                <div style={{ marginTop: '4px', paddingTop: '6px', borderTop: '1px stroke #E2E8F0', color: 'var(--text-secondary, #64748B)', fontSize: '11px' }}>
                  <div><strong>Reference Source: </strong>{fabric.reference_source}</div>
                  <div><strong>Image Attribution: </strong>{fabric.image_license}</div>
                </div>
              </div>
            )}
          </div>

        </div>

        {/* Footer */}
        <div style={{
          padding: '16px 24px',
          borderTop: '1px solid var(--border, #E2E8F0)',
          display: 'flex',
          justify: 'space-between',
          alignItems: 'center',
          background: 'var(--surface-2, #F8FAFC)',
          borderBottomLeftRadius: '16px',
          borderBottomRightRadius: '16px'
        }}>
          <button
            onClick={onClose}
            style={{
              padding: '8px 16px',
              borderRadius: '8px',
              border: '1px solid var(--border-strong, #CBD5E1)',
              background: '#FFFFFF',
              color: 'var(--text-primary, #0F172A)',
              fontSize: '13px',
              fontWeight: '500',
              cursor: 'pointer'
            }}
          >
            Close
          </button>

          <button
            onClick={() => {
              onSelect(fabric.id);
              onClose();
            }}
            style={{
              padding: '10px 20px',
              borderRadius: '8px',
              border: 'none',
              background: isSelected ? '#15803D' : 'var(--text-accent, #2D5A43)',
              color: '#FFFFFF',
              fontSize: '13px',
              fontWeight: '600',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px'
            }}
          >
            {isSelected ? (
              <>
                <Check size={16} /> Selected Material
              </>
            ) : (
              'Select This Material'
            )}
          </button>
        </div>

      </div>
    </div>
  );
}
