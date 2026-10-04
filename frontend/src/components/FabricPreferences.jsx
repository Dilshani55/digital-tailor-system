export const completePreferences = (study, value) => Boolean(study && value?.study_id === study.id
  && study.criteria.every((c) => ['cost', 'benefit'].includes(value.goals?.[c.id]))
  && value.comparisons?.length === 3 && value.comparisons.every((c) => Number(c.ratio) > 0));

export default function FabricPreferences({ study, value, onChange, onCalculate, busy }) {
  const current = value?.study_id === study.id ? value : { study_id: study.id, goals: {}, comparisons: [] };
  const pairs = study.criteria.flatMap((left, i) => study.criteria.slice(i + 1).map((right) => ({ left, right })));
  const compare = (left, right, ratio) => onChange({ ...current, comparisons: [
    ...current.comparisons.filter((c) => c.left !== left || c.right !== right),
    ...(ratio ? [{ left, right, ratio: Number(ratio) }] : []),
  ] });
  return (
    <div className="fabric-preferences" data-testid="fabric-preferences">
      <h4>Your fabric preferences</h4>
      <p>Choose the properties you want, then tell us which matters more to you.</p>
      <div className="fabric-preference-grid">
        {study.criteria.map((c) => (
          <label key={c.id} htmlFor={`fabric-goal-${c.id}`}>{c.label}
            <select id={`fabric-goal-${c.id}`} value={current.goals[c.id] || ''}
              onChange={(e) => onChange({ ...current, goals: { ...current.goals, [c.id]: e.target.value } })}>
              <option value="">Choose your preference</option>
              {c.goal_options.map((g) => <option key={g.value} value={g.value}>{g.label}</option>)}
            </select>
          </label>
        ))}
      </div>
      <h4>Which matters more?</h4>
      <div className="fabric-preference-grid">
        {pairs.map(({ left, right }) => (
          <label key={left.id + right.id} htmlFor={`fabric-pair-${left.id}-${right.id}`}>{left.label} compared with {right.label}
            <select id={`fabric-pair-${left.id}-${right.id}`}
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
      <button type="button" className="btn btn-primary" disabled={busy || !completePreferences(study, current)} onClick={() => onCalculate(current)}>
        {busy ? 'Comparing samples…' : 'Compare fabric samples'}
      </button>
      <p className="form-hint">Your choices set the ranking priorities. Fit is set above and controls pattern ease.</p>
      <details className="fabric-source">
        <summary>Published data: {study.sample_count} {study.composition.toLowerCase()} samples</summary>
        <p><a href={study.url} target="_blank" rel="noreferrer">{study.title}</a></p>
        <p>{study.scope_note}</p>
      </details>
    </div>
  );
}
