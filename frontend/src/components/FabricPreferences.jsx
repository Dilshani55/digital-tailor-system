import { useState } from 'react';

const pairsFor = (study) => study.criteria.flatMap((left, i) => study.criteria.slice(i + 1).map((right) => ({ left, right })));
const RATIOS = [1/9, 1/7, 1/5, 1/3, 1, 3, 5, 7, 9];
const validRatio = (ratio) => typeof ratio === 'number' && RATIOS.some((allowed) => Math.abs(ratio - allowed) < 1e-9);
export const completePreferences = (study, value) => Boolean(study && value?.study_id === study.id
  && study.criteria.every((c) => ['cost', 'benefit'].includes(value.goals?.[c.id]))
  && Array.isArray(value.comparisons) && value.comparisons.length === pairsFor(study).length
  && pairsFor(study).every(({ left, right }) => {
    const matches = value.comparisons.filter((c) => c.left === left.id && c.right === right.id);
    return matches.length === 1 && validRatio(matches[0].ratio);
  }));

const HELP = {
  mass: 'The weight of one square metre of cloth.',
  air_flow: 'Air passing through the sample in the published test.',
  thickness: 'How thick the cloth is.',
  thermal_resistance: 'How much the sample resists heat passing through.',
};

export default function FabricPreferences({ study, value, onChange, onCalculate, busy, correctionNeeded = false }) {
  const [customPriorities, setCustomPriorities] = useState(() => value?.comparisons?.some((c) => c.ratio !== 1) || false);
  const current = value?.study_id === study.id
    ? { ...value, goals: value.goals || {}, comparisons: Array.isArray(value.comparisons) ? value.comparisons : [] }
    : { study_id: study.id, goals: {}, comparisons: [] };
  const pairs = pairsFor(study);
  const goalCount = study.criteria.filter((c) => ['cost', 'benefit'].includes(current.goals[c.id])).length;
  const comparisonCount = pairs.filter(({ left, right }) => current.comparisons.some((c) => c.left === left.id && c.right === right.id && validRatio(c.ratio))).length;
  const equalPriorities = comparisonCount === pairs.length && current.comparisons.every((c) => c.ratio === 1);
  const ready = completePreferences(study, current);
  const compare = (left, right, ratio) => onChange({ ...current, comparisons: [
    ...current.comparisons.filter((c) => c.left !== left || c.right !== right),
    ...(ratio ? [{ left, right, ratio: Number(ratio) }] : []),
  ] });
  return (
    <div className="fabric-preferences" data-testid="fabric-preferences">
      <h4>Fabric goals</h4>
      <p>Choose what you want from your material.</p>
      <div className="fabric-preference-grid">
        {study.criteria.map((c) => (
          <label key={c.id} htmlFor={`fabric-goal-${c.id}`}>{c.label}
            <span className="preference-help" id={`fabric-help-${c.id}`}>{HELP[c.id]}</span>
            <select id={`fabric-goal-${c.id}`} value={current.goals[c.id] || ''}
              aria-describedby={`fabric-help-${c.id}`} disabled={busy}
              onChange={(e) => onChange({ ...current, goals: { ...current.goals, [c.id]: e.target.value } })}>
              <option value="">Choose your preference</option>
              {c.goal_options.map((g) => <option key={g.value} value={g.value}>{g.label}</option>)}
            </select>
          </label>
        ))}
      </div>
      <h4>Which properties matter most?</h4>
      <p>Give them equal importance, or set your own priorities.</p>
      <div className="fabric-priority-actions">
        <button type="button" className={`btn ${equalPriorities ? 'btn-primary' : 'btn-outline'}`} aria-pressed={equalPriorities}
          disabled={busy} onClick={() => {
            onChange({ ...current, comparisons: pairs.map(({ left, right }) => ({ left: left.id, right: right.id, ratio: 1 })) });
            setCustomPriorities(false);
          }}>Treat all properties equally</button>
        <button type="button" className="btn btn-outline" disabled={busy} aria-expanded={customPriorities || correctionNeeded}
          aria-controls="fabric-pairwise" onClick={() => setCustomPriorities((open) => !open)}>Set priorities individually</button>
      </div>
      {equalPriorities && !correctionNeeded && <p className="form-hint">You chose equal importance for all three properties.</p>}
      <div id="fabric-pairwise" className="fabric-preference-grid" hidden={!customPriorities && !correctionNeeded}>
        {pairs.map(({ left, right }) => (
          <label key={left.id + right.id} htmlFor={`fabric-pair-${left.id}-${right.id}`}>{left.label} compared with {right.label}
            <select id={`fabric-pair-${left.id}-${right.id}`}
              disabled={busy}
              value={current.comparisons.find((c) => c.left === left.id && c.right === right.id)?.ratio ?? ''}
              onChange={(e) => compare(left.id, right.id, e.target.value)}>
              <option value="">Choose importance</option>
              <option value="1">Both equally important</option>
              {[['Moderately', 3], ['Strongly', 5], ['Very strongly', 7], ['Extremely', 9]].map(([label, ratio]) => (
                <option key={ratio} value={ratio}>{left.label} {label.toLowerCase()} more important</option>
              ))}
              {[['Moderately', 3], ['Strongly', 5], ['Very strongly', 7], ['Extremely', 9]].map(([label, ratio]) => (
                <option key={1 / ratio} value={1 / ratio}>{right.label} {label.toLowerCase()} more important</option>
              ))}
            </select>
          </label>
        ))}
      </div>
      <div className="fabric-compare-actions">
        <div role="status" aria-live="polite" className="form-hint">
          {ready ? 'Ready to compare. Your choices will determine the recommendation.'
            : `Goals chosen: ${goalCount}/${study.criteria.length}. Priority comparisons: ${comparisonCount}/${pairs.length}. Complete both sections to continue.`}
        </div>
        <button type="button" className="btn btn-primary" disabled={busy || !ready} onClick={() => onCalculate(current)}>
          {busy ? 'Comparing samples…' : 'Find recommended fabrics'}
        </button>
      </div>
    </div>
  );
}
