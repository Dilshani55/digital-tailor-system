import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Filter, Pencil, Plus, Scissors, Search, Trash2, Users } from 'lucide-react';
import { measurementsAPI, patternsAPI } from '../services/api';
import { validateMeasurements, parseFieldErrors, buildPayload, MEASUREMENT_FIELDS, FIELD_KEYS } from '../utils/measurementSchema';

// quick-add fields on the customer form (all optional; the pattern wizard asks for what a design needs)
const QUICK_FIELDS = ['bust_cm', 'waist_cm', 'hip_cm', 'height_cm'];
import LoadingSpinner from '../components/LoadingSpinner';

const FIELD_LABEL = Object.fromEntries(MEASUREMENT_FIELDS.map((f) => [f.key, f.label]));
const PAGE_SIZE = 10;
const EMPTY = { client_name: '', email: '', notes: '', bust_cm: '', waist_cm: '', hip_cm: '', height_cm: '', fabric_type: 'woven' };
const initials = (name) => (name || '?').split(' ').filter(Boolean).map((n) => n[0]).join('').slice(0, 2).toUpperCase();
const measured = (p) => FIELD_KEYS.filter((k) => p[k] !== null && p[k] !== undefined && p[k] !== '').length;

export default function Customers() {
  const navigate = useNavigate();
  const [profiles, setProfiles] = useState([]);
  const [patternCounts, setPatternCounts] = useState(null);   // null = could not be loaded
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState('all');
  const [page, setPage] = useState(1);
  const [showAdd, setShowAdd] = useState(false);
  const [newClient, setNewClient] = useState(EMPTY);
  const [formError, setFormError] = useState('');

  const load = async () => {
    setLoading(true);
    setError('');
    try {
      const [res, pats] = await Promise.all([measurementsAPI.getAll(), patternsAPI.getAll().catch(() => null)]);
      setProfiles(res.data.measurements || []);
      if (pats) {
        const counts = {};
        (pats.data.patterns || []).forEach((p) => { if (p.measurement_id) counts[p.measurement_id] = (counts[p.measurement_id] || 0) + 1; });
        setPatternCounts(counts);
      } else {
        setPatternCounts(null);
      }
    } catch {
      setError('Failed to load customer profiles.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const addCustomer = async (e) => {
    e.preventDefault();
    setFormError('');
    if (!newClient.client_name.trim()) { setFormError('Please enter the customer name.'); return; }
    const errs = validateMeasurements(newClient, []);
    if (Object.keys(errs).length) {
      setFormError(QUICK_FIELDS.filter((k) => errs[k]).map((k) => `${FIELD_LABEL[k]}: ${errs[k]}`).join(' '));
      return;
    }
    try {
      await measurementsAPI.save({
        client_name: newClient.client_name.trim(),
        ...(newClient.email.trim() ? { email: newClient.email.trim() } : {}),
        ...(newClient.notes.trim() ? { notes: newClient.notes.trim() } : {}),
        ...buildPayload(newClient, {}, 'cm'),
        fabric_type: newClient.fabric_type,
      });
      setShowAdd(false);
      setNewClient(EMPTY);
      load();
    } catch (err) {
      setFormError(Object.values(parseFieldErrors(err)).join(' ') || 'Failed to save customer profile.');
    }
  };

  const remove = async (p) => {
    if (!window.confirm(`Delete the customer "${p.client_name}" and their measurements?`)) return;
    try {
      await measurementsAPI.delete(p.measurement_id);
      load();
    } catch {
      setError('Failed to delete the customer profile.');
    }
  };

  const count = (p) => (patternCounts ? (patternCounts[p.measurement_id] || 0) : null);
  const q = query.trim().toLowerCase();
  const filtered = profiles.filter((p) => ((p.client_name || '').toLowerCase().includes(q) || (p.email || '').toLowerCase().includes(q))
    && (filter === 'all' || (filter === 'with' ? count(p) > 0 : count(p) === 0)));
  const pages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const current = Math.min(page, pages);
  const shown = filtered.slice((current - 1) * PAGE_SIZE, current * PAGE_SIZE);

  return (
    <div className="page">
      <section className="page-heading">
        <div>
          <h1>Customers</h1>
          <p>Manage your customer profiles and measurements.</p>
        </div>
        <button className="btn btn-primary" onClick={() => { setShowAdd(true); setFormError(''); }}><Plus size={17} /> Add customer</button>
      </section>

      <div className="toolbar">
        <div className="search-field">
          <Search size={17} aria-hidden="true" />
          <input value={query} onChange={(e) => { setQuery(e.target.value); setPage(1); }} placeholder="Search customers…" aria-label="Search customers" />
        </div>
        <label className="search-field" style={{ flex: '0 0 auto', minWidth: 0 }}>
          <Filter size={16} aria-hidden="true" />
          <span className="sr-only">Filter customers</span>
          <select value={filter} onChange={(e) => { setFilter(e.target.value); setPage(1); }}
                  style={{ border: 0, background: 'transparent', outline: 0, fontSize: 14, color: 'var(--ink)' }}>
            <option value="all">All customers</option>
            <option value="with">With patterns</option>
            <option value="without">Without patterns</option>
          </select>
        </label>
      </div>

      <section className="ui-card">
        {loading ? <LoadingSpinner message="Loading customers…" />
          : error ? <div role="alert" className="alert error" style={{ margin: 20 }}>{error} Please refresh and try again.</div>
            : filtered.length === 0 ? (
              <div className="empty-state">
                <span><Users size={26} /></span>
                <h2>{profiles.length ? 'No matching customers' : 'No customers yet'}</h2>
                <p>{profiles.length ? 'Try another search or filter.' : 'Add a customer to save their measurements and patterns.'}</p>
              </div>
            ) : (
              <>
                <div className="table-wrap">
                  <table className="data-table">
                    <thead>
                      <tr><th>Name</th><th>Email / contact</th><th>Measurements</th><th>Patterns</th><th>Added</th><th><span className="sr-only">Actions</span></th></tr>
                    </thead>
                    <tbody>
                      {shown.map((p) => (
                        <tr key={p.measurement_id}>
                          <td><div className="name-cell"><span className="avatar">{initials(p.client_name)}</span><strong>{p.client_name}</strong></div></td>
                          <td>{p.email || <span className="muted">No e-mail recorded</span>}</td>
                          <td>{measured(p)} entered</td>
                          <td data-testid={`pattern-count-${p.measurement_id}`}>{count(p) ?? '—'}</td>
                          <td>{p.created_at ? new Date(p.created_at).toLocaleDateString('en-GB') : '—'}</td>
                          <td>
                            <div className="row-actions" style={{ justifyContent: 'flex-end' }}>
                              <button aria-label={`Edit measurements of ${p.client_name}`} title="Edit measurements"
                                      onClick={() => navigate('/measurements', { state: { profile: p } })}><Pencil size={15} /></button>
                              <button aria-label={`Create a pattern for ${p.client_name}`} title="Create pattern"
                                      onClick={() => navigate('/upload', { state: { selectedProfile: p } })}><Scissors size={15} /></button>
                              <button className="delete" aria-label={`Delete ${p.client_name}`} title="Delete customer"
                                      onClick={() => remove(p)}><Trash2 size={15} /></button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <div className="pagination">
                  <span>Showing {(current - 1) * PAGE_SIZE + 1}–{(current - 1) * PAGE_SIZE + shown.length} of {filtered.length} customers</span>
                  {pages > 1 && (
                    <div>
                      {Array.from({ length: pages }, (_, i) => i + 1).map((n) => (
                        <button key={n} type="button" aria-current={n === current ? 'page' : undefined} onClick={() => setPage(n)}>{n}</button>
                      ))}
                    </div>
                  )}
                </div>
              </>
            )}
      </section>

      {showAdd && (
        <div className="modal-backdrop">
          <div className="modal" role="dialog" aria-modal="true" aria-labelledby="add-customer-h">
            <h2 id="add-customer-h">Add customer</h2>
            <form onSubmit={addCustomer} noValidate style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              {formError && <div role="alert" data-testid="customer-form-error" className="alert error">{formError}</div>}
              <div className="form-field">
                <label className="form-label" htmlFor="new-client-name">Full Name</label>
                <input id="new-client-name" className="form-input" placeholder="e.g. Amara Silva" value={newClient.client_name}
                       onChange={(e) => setNewClient({ ...newClient, client_name: e.target.value })} />
              </div>
              <div className="form-field">
                <label className="form-label" htmlFor="new-client-email">Email Address (optional)</label>
                <input id="new-client-email" type="email" className="form-input" placeholder="e.g. amara@example.com" value={newClient.email}
                       onChange={(e) => setNewClient({ ...newClient, email: e.target.value })} />
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                {QUICK_FIELDS.map((key) => (
                  <div className="form-field" key={key}>
                    <label className="form-label" htmlFor={`new-client-${key}`}>{FIELD_LABEL[key]} (cm)</label>
                    <input id={`new-client-${key}`} type="number" step="any" inputMode="decimal" className="form-input"
                           value={newClient[key]} onChange={(e) => setNewClient({ ...newClient, [key]: e.target.value })} />
                  </div>
                ))}
              </div>
              <p className="form-hint">The other drafting measurements are added later in the pattern wizard or on the Measurements page.</p>
              <div className="form-field">
                <label className="form-label" htmlFor="new-client-notes">Notes & Fit Preferences (optional)</label>
                <textarea id="new-client-notes" className="form-input" placeholder="e.g. Prefers a looser fit." value={newClient.notes}
                          onChange={(e) => setNewClient({ ...newClient, notes: e.target.value })} />
              </div>
              <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
                <button type="button" className="btn btn-outline" onClick={() => { setShowAdd(false); setFormError(''); }}>Cancel</button>
                <button type="submit" className="btn btn-primary">Save Customer</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
