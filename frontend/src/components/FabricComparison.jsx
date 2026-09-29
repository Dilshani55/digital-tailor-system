import { useEffect, useState } from 'react';
import { Scale, Trash2 } from 'lucide-react';
import { researchAPI } from '../services/api';
import { friendlyError } from '../utils/friendlyError';
import { FABRIC_WIDTHS } from '../utils/preferences';

const SOURCES = [
  ['tailor', 'Tailor’s estimate'],
  ['manual_calculation', 'Manual calculation'],
  ['shop_rule_of_thumb', 'Shop rule of thumb'],
  ['other', 'Other'],
];
const MODES = [['auto', 'Best layout'], ['folded', 'Folded lengthwise'], ['open', 'Laid open']];
const sourceLabel = Object.fromEntries(SOURCES);
const signed = (v, unit) => `${v > 0 ? '+' : ''}${v}${unit}`;

/**
 * Evaluation instrument: record how much cloth a traditional method would buy for this pattern and
 * compare it with the system's recommendation for the SAME fabric width (recomputed by the server).
 * Only values a person enters are stored; nothing is pre-filled or estimated.
 */
export default function FabricComparison({ patternId, defaultWidth }) {
  const [items, setItems] = useState(null);
  const [form, setForm] = useState({
    fabric_width_cm: FABRIC_WIDTHS.includes(defaultWidth) ? defaultWidth : 114,
    cutting_mode: 'auto', traditional_estimate_m: '', estimate_source: 'tailor', estimator_label: '', notes: '',
  });
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const load = () => researchAPI.getComparisons(patternId)
    .then((r) => setItems(r.data.comparisons || []))
    .catch((e) => { setItems([]); setError(friendlyError(e, 'Saved comparisons could not be loaded.')); });

  useEffect(() => { load(); }, [patternId]); // eslint-disable-line react-hooks/exhaustive-deps

  const submit = async (e) => {
    e.preventDefault();
    setError('');
    const value = Number(form.traditional_estimate_m);
    if (form.traditional_estimate_m === '' || !Number.isFinite(value) || value < 0.1 || value > 20) {
      setError('Enter the traditional estimate in metres (between 0.1 and 20).');
      return;
    }
    setBusy(true);
    try {
      await researchAPI.addComparison({
        pattern_id: patternId, fabric_width_cm: Number(form.fabric_width_cm), cutting_mode: form.cutting_mode,
        traditional_estimate_m: value, estimate_source: form.estimate_source,
        estimator_label: form.estimator_label.trim() || undefined, notes: form.notes.trim() || undefined,
      });
      setForm((f) => ({ ...f, traditional_estimate_m: '', notes: '' }));
      await load();
    } catch (err) {
      setError(friendlyError(err, 'The comparison could not be saved.'));
    } finally {
      setBusy(false);
    }
  };

  const remove = async (id) => {
    try {
      await researchAPI.deleteComparison(id);
      setItems((list) => list.filter((c) => c.comparison_id !== id));
    } catch (err) {
      setError(friendlyError(err, 'The comparison could not be deleted.'));
    }
  };

  return (
    <section className="ui-card" style={{ padding: '18px', marginTop: '14px' }} data-testid="fabric-comparison" aria-labelledby="cmp-h">
      <h2 id="cmp-h" style={{ fontSize: '14px', marginBottom: '4px', display: 'flex', gap: '8px', alignItems: 'center' }}>
        <Scale size={16}/> Compare with a traditional fabric estimate
      </h2>
      <p style={{ fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '12px', lineHeight: 1.5 }}>
        For the evaluation study: enter how much fabric a tailor (or another traditional method) would buy for this garment.
        The system recalculates its own recommendation for the same fabric width so the two can be compared.
        Use a label such as “Tailor A” — do not enter real names.
      </p>

      {error && <div role="alert" style={{ color: '#991B1B', background: '#FEF2F2', border: '1px solid #FCA5A5', borderRadius: '8px', padding: '8px 12px', fontSize: '12px', marginBottom: '10px' }}>{error}</div>}

      <form onSubmit={submit} noValidate style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))', gap: '10px', alignItems: 'end' }}>
        <div className="form-field">
          <label className="form-label" htmlFor="cmp-width">Fabric width</label>
          <select id="cmp-width" className="form-select" value={form.fabric_width_cm} onChange={(e) => setForm({ ...form, fabric_width_cm: Number(e.target.value) })}>
            {FABRIC_WIDTHS.map((w) => <option key={w} value={w}>{w} cm</option>)}
          </select>
        </div>
        <div className="form-field">
          <label className="form-label" htmlFor="cmp-mode">System cutting layout</label>
          <select id="cmp-mode" className="form-select" value={form.cutting_mode} onChange={(e) => setForm({ ...form, cutting_mode: e.target.value })}>
            {MODES.map(([v, t]) => <option key={v} value={v}>{t}</option>)}
          </select>
        </div>
        <div className="form-field">
          <label className="form-label" htmlFor="cmp-trad">Traditional estimate (m)</label>
          <input id="cmp-trad" className="form-input" type="number" step="0.05" min="0.1" max="20" inputMode="decimal"
                 value={form.traditional_estimate_m} onChange={(e) => setForm({ ...form, traditional_estimate_m: e.target.value })} />
        </div>
        <div className="form-field">
          <label className="form-label" htmlFor="cmp-source">Source of the estimate</label>
          <select id="cmp-source" className="form-select" value={form.estimate_source} onChange={(e) => setForm({ ...form, estimate_source: e.target.value })}>
            {SOURCES.map(([v, t]) => <option key={v} value={v}>{t}</option>)}
          </select>
        </div>
        <div className="form-field">
          <label className="form-label" htmlFor="cmp-label">Estimator label (optional)</label>
          <input id="cmp-label" className="form-input" maxLength={40} placeholder="e.g. Tailor A"
                 value={form.estimator_label} onChange={(e) => setForm({ ...form, estimator_label: e.target.value })} />
        </div>
        <div className="form-field">
          <label className="form-label" htmlFor="cmp-notes">Notes (optional)</label>
          <input id="cmp-notes" className="form-input" maxLength={500}
                 value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
        </div>
        <button type="submit" className="btn btn-primary" disabled={busy}>{busy ? 'Calculating…' : 'Save comparison'}</button>
      </form>

      <div style={{ marginTop: '14px' }}>
        {items === null ? <p style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Loading…</p>
          : items.length === 0 ? <p style={{ fontSize: '12px', color: 'var(--text-muted)' }}>No comparison recorded for this pattern yet.</p>
            : (
              <div className="table-wrap">
                <table className="hist-table" data-testid="comparison-table">
                  <thead><tr><th>Width</th><th>Traditional</th><th>System (layout)</th><th>Difference</th><th>Source</th><th><span className="sr-only">Actions</span></th></tr></thead>
                  <tbody>
                    {items.map((c) => (
                      <tr key={c.comparison_id}>
                        <td>{c.fabric_width_cm} cm</td>
                        <td>{c.traditional_estimate_m} m</td>
                        <td>{c.system_purchase_m} m <small>({c.system_layout_length_cm} cm, {c.system_cutting_mode})</small></td>
                        <td><strong>{signed(c.difference_m, ' m')}</strong> <small>({signed(c.relative_difference_percent, '%')} of traditional)</small></td>
                        <td>{sourceLabel[c.estimate_source] || c.estimate_source}{c.estimator_label ? ` · ${c.estimator_label}` : ''}</td>
                        <td><div className="row-actions"><button type="button" className="delete" aria-label="Delete comparison" onClick={() => remove(c.comparison_id)}><Trash2 size={15}/></button></div></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
        <p style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '8px', lineHeight: 1.5 }}>
          Difference = traditional − system; positive means the system recommends buying less cloth.
          This compares purchase recommendations only — it does not show that the system amount was enough in an actual cut.
        </p>
      </div>
    </section>
  );
}
