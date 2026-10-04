import { useEffect, useRef, useState } from 'react';
import { Check, X } from 'lucide-react';
import { fabricDescription, fabricGoal, fabricObservation } from '../utils/fabricDisplay';

export default function FabricDetailsModal({ fabric, rankingAudit, publishedStudy, isSelected, onSelect, onClose,
  canSelect = true, isRecommended = false }) {
  const [imgError, setImgError] = useState(false);
  const modalRef = useRef(null);
  const closeRef = useRef(onClose);
  closeRef.current = onClose;

  useEffect(() => {
    if (!fabric) return;
    const opener = document.activeElement;
    const oldOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    const focusable = () => Array.from(modalRef.current?.querySelectorAll('button:not([disabled]), a[href], summary') || [])
      .filter((node) => {
        const closedDetails = node.closest('details:not([open])');
        return !closedDetails || node === closedDetails.querySelector('summary');
      });
    focusable()[0]?.focus();
    const handleKeyDown = (event) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        closeRef.current();
      } else if (event.key === 'Tab') {
        const nodes = focusable();
        const first = nodes[0];
        const last = nodes.at(-1);
        if ((first && (event.shiftKey ? document.activeElement === first : document.activeElement === last))
          || !modalRef.current?.contains(document.activeElement)) {
          event.preventDefault();
          (event.shiftKey ? last : first)?.focus();
        }
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      document.body.style.overflow = oldOverflow;
      if (opener?.isConnected) opener.focus();
    };
  }, [fabric?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!fabric) return null;
  const published = Boolean(fabric.study_id);
  const audit = published ? rankingAudit?.profile_id === fabric.study_id ? rankingAudit : null : rankingAudit;
  const criteria = audit?.criteria || publishedStudy?.criteria || [];
  const sample = fabric.research_sample;
  const properties = published ? [
    ['Composition', publishedStudy?.composition || fabric.technical_details?.composition_note],
    ['Material type', fabric.construction === 'knit' ? 'Knit' : 'Woven'],
    ['Structure', sample?.structure || fabric.technical_details?.construction],
    ['Weight', fabricObservation(sample?.values.mass)],
  ] : [['Weight', fabric.weight], ['Stretch', fabric.stretch], ['Feel / texture', fabric.feel], ['Drape', fabric.drape]];
  const goals = criteria.filter((c) => c.objective).map((c) => fabricGoal(c, c.objective));
  const explanation = fabric.compatible === false ? 'This material cannot be selected for the current design.'
    : isRecommended ? 'This material is the closest match to your fabric goals' + (goals.length ? ': ' + goals.join(', ').toLowerCase() : '') + '.'
      : published ? 'Another material you can choose for your design.' : fabric.explanation;

  return (
    <div className="modal-overlay published-fabric-overlay" role="dialog" aria-modal="true" aria-labelledby="fabric-modal-title"
      onClick={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <div className="published-fabric-modal" ref={modalRef}>
        <div className="section-head">
          <div><h2 id="fabric-modal-title">{fabric.name}</h2>
            <span className="tag">{fabric.compatible === false ? 'Not available for this design' : isRecommended ? 'Recommended' : 'Other material'}</span>
          </div>
          <button type="button" className="btn btn-outline btn-sm" aria-label="Close modal" onClick={onClose}><X size={20} /></button>
        </div>
        {!published && fabric.local_image && <div className="fabric-modal-image">
          {!imgError ? <img src={fabric.local_image} alt={'Close-up fabric texture image of ' + fabric.name} onError={() => setImgError(true)} />
            : <span>Image unavailable</span>}
        </div>}
        <h3 className="fabric-list-heading">About this material</h3>
        <p>{fabricDescription(fabric, publishedStudy)}</p>
        <dl className="fabric-property-grid">{properties.filter(([, value]) => value).map(([label, value]) => <div key={label}>
          <dt>{label}</dt><dd>{value}</dd>
        </div>)}</dl>
        {published && criteria.filter((c) => c.id !== 'mass').map((c) => <p key={c.id}>
          <strong>{c.label}: </strong>{fabricObservation(sample?.values[c.id])}
        </p>)}
        <p className="fabric-modal-explanation">{explanation}</p>
        {fabric.best_garment_uses?.length > 0 && <div><h4>Suitable uses</h4><p>{fabric.best_garment_uses.join(', ')}</p></div>}
        {fabric.climate_suitability && <div><h4>Climate suitability</h4><p>{fabric.climate_suitability}</p></div>}
        <div className="fabric-info-columns">
          {fabric.advantages?.length > 0 && <div><h4>Advantages</h4><ul>{fabric.advantages.map((item) => <li key={item}>{item}</li>)}</ul></div>}
          {fabric.limitations?.length > 0 && <div><h4>Things to consider</h4><ul>{fabric.limitations.map((item) => <li key={item}>{item}</li>)}</ul></div>}
        </div>
        {fabric.care_instructions && <div><h4>Care instructions</h4><p>{fabric.care_instructions}</p></div>}
        {fabric.sewing_difficulty && <div><h4>Sewing</h4><p>{fabric.sewing_difficulty}</p></div>}
        {published && <p className="form-hint">These properties describe the measured sample. Check the actual cloth you intend to use.</p>}
        {sample && criteria.length > 0 && <details className="fabric-modal-evidence">
          <summary>Measurement references</summary>
          <h4>Recorded sample evidence</h4>
          <p>Sample ID: {sample.sample_id}.</p>
          <div className="fabric-evidence-table"><table>
            <thead><tr><th>Property</th><th>Measured value</th><th>Your goal</th><th>Weight</th><th>Source</th></tr></thead>
            <tbody>{criteria.map((c, index) => {
              const observation = sample.values[c.id];
              return <tr key={c.id}>
                <td>{c.label}</td><td>{fabricObservation(observation)}</td>
                <td>{fabricGoal(c, c.objective)}</td>
                <td>{audit ? (audit.ahp.weights[index] * 100).toFixed(1) + '%' : 'Not set'}</td>
                <td>{observation?.table || observation?.source}</td>
              </tr>;
            })}</tbody>
          </table></div>
          {audit && <p>Your comparison consistency ratio: {audit.ahp.consistency_ratio.toFixed(3)} (accepted at 0.10 or below).
            TOPSIS closeness is a relative comparison, not a probability of fit.</p>}
          {fabric.source_url ? <p><a href={fabric.source_url} target="_blank" rel="noreferrer">{fabric.reference_source}</a></p>
            : audit?.profile_source && <p>{audit.profile_source}</p>}
          <ul>{criteria.filter((c) => c.protocol).map((c) => <li key={c.id}><strong>{c.label}: </strong>{c.protocol}</li>)}</ul>
          <p>{audit?.scope_note || publishedStudy?.scope_note}</p>
        </details>}
        {!published && fabric.technical_details && <details className="fabric-modal-evidence">
          <summary>Material notes</summary>
          {Object.entries(fabric.technical_details).map(([key, value]) => value && <p key={key}>{value}</p>)}
          {fabric.reference_source && <p>{fabric.reference_source}</p>}
          {fabric.image_license && <p>{fabric.image_license}</p>}
        </details>}
        {!canSelect && fabric.compatible !== false && <p className="form-hint">Complete your fabric goals before selecting this material.</p>}
        <div className="form-actions">
          <button type="button" className="btn btn-outline" onClick={onClose}>Close</button>
          <button type="button" className="btn btn-primary" disabled={!canSelect} onClick={() => { onSelect(fabric.id); onClose(); }}>
            {isSelected && <Check size={16} />} {isSelected ? 'Selected material' : 'Select material'}
          </button>
        </div>
      </div>
    </div>
  );
}
