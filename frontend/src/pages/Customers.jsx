import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, Plus, Filter, Edit2, Play, Trash2 } from 'lucide-react';
import { measurementsAPI, patternsAPI } from '../services/api';
import { validateMeasurements, parseFieldErrors, buildPayload, CORE_FIELDS, MEASUREMENT_FIELDS } from '../utils/measurementSchema';

const FIELD_LABEL = Object.fromEntries(MEASUREMENT_FIELDS.map((f) => [f.key, f.label]));
import LoadingSpinner from '../components/LoadingSpinner';

export default function Customers() {
  const navigate = useNavigate();
  const [profiles, setProfiles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedProfile, setSelectedProfile] = useState(null);
  // real number of saved patterns per measurement profile (null = could not be loaded)
  const [patternCounts, setPatternCounts] = useState(null);
  const [formError, setFormError] = useState('');

  // Modal State for adding customer
  const [showAddModal, setShowAddModal] = useState(false);
  const [newClient, setNewClient] = useState({
    client_name: '',
    email: '',
    notes: '',
    bust_cm: '',
    waist_cm: '',
    hip_cm: '',
    height_cm: '',
    fabric_type: 'woven'
  });

  const fetchProfiles = async () => {
    setLoading(true);
    setError('');
    try {
      const [res, pats] = await Promise.all([
        measurementsAPI.getAll(),
        patternsAPI.getAll().catch(() => null),
      ]);
      const list = res.data.measurements || [];
      setProfiles(list);
      if (pats) {
        const counts = {};
        (pats.data.patterns || []).forEach((p) => {
          if (p.measurement_id) counts[p.measurement_id] = (counts[p.measurement_id] || 0) + 1;
        });
        setPatternCounts(counts);
      } else {
        setPatternCounts(null);
      }
      if (list.length > 0 && !selectedProfile) {
        setSelectedProfile(list[0]);
      }
    } catch (err) {
      setError('Failed to load customer profiles.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchProfiles();
  }, []);

  const handleAddSubmit = async (e) => {
    e.preventDefault();
    setFormError('');
    if (!newClient.client_name.trim()) {
      setFormError('Please enter the customer name.');
      return;
    }
    const localErrors = validateMeasurements(newClient, 'cm', CORE_FIELDS);
    if (Object.keys(localErrors).length > 0) {
      setFormError(CORE_FIELDS.filter((k) => localErrors[k]).map((k) => `${FIELD_LABEL[k]}: ${localErrors[k]}`).join(' '));
      return;
    }

    try {
      await measurementsAPI.save({
        client_name: newClient.client_name.trim(),
        ...(newClient.email.trim() ? { email: newClient.email.trim() } : {}),
        ...(newClient.notes.trim() ? { notes: newClient.notes.trim() } : {}),
        ...buildPayload(newClient, 'cm'),   // entered core measurements only (cm)
        fabric_type: newClient.fabric_type
      });
      setShowAddModal(false);
      setNewClient({
        client_name: '', email: '', notes: '',
        bust_cm: '', waist_cm: '', hip_cm: '', height_cm: '',
        fabric_type: 'woven'
      });
      fetchProfiles();
    } catch (err) {
      const parsed = parseFieldErrors(err);
      setFormError(Object.values(parsed).join(' ') || 'Failed to save customer profile.');
    }
  };

  const handleDelete = async (id) => {
    if (window.confirm('Are you sure you want to delete this customer?')) {
      try {
        await measurementsAPI.delete(id);
        if (selectedProfile?.measurement_id === id) {
          setSelectedProfile(null);
        }
        fetchProfiles();
      } catch (err) {
        alert('Failed to delete profile.');
      }
    }
  };

  const filteredProfiles = profiles.filter(p => 
    p.client_name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
    p.email?.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="customers-page" style={{ padding: '24px', maxWidth: '1400px', margin: '0 auto' }}>
      
      {/* Top Search & Action Bar */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px', flexWrap: 'wrap', gap: '16px' }}>
        <div style={{ display: 'flex', gap: '12px', flex: 1, maxWidth: '500px' }}>
          <div className="search-field" style={{ flex: 1 }}>
            <Search size={16} />
            <input 
              type="text" 
              placeholder="Search customers..." 
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>
          <button className="icon-btn" title="Filter list"><Filter size={16}/></button>
        </div>
        <button className="btn btn-primary" onClick={() => setShowAddModal(true)} style={{ background: 'var(--text-accent)' }}>
          <Plus size={16} /> Add customer
        </button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1.4fr 0.8fr', gap: '24px' }}>
        
        {/* Left Side: Customers list Table */}
        <div className="ui-card" style={{ padding: '0px', overflow: 'hidden' }}>
          <div className="card-head">
            <div>
              <span className="section-kicker">Tailor studio</span>
              <h2>Customer profiles</h2>
            </div>
            <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
              Showing {filteredProfiles.length} customer profiles
            </span>
          </div>

          {loading ? (
            <div style={{ padding: '60px', textAlign: 'center' }}>
              <LoadingSpinner message="Loading customer directory..." />
            </div>
          ) : error ? (
            <div role="alert" style={{ padding: '40px', textAlign: 'center', color: 'var(--danger)' }}>
              {error} Please refresh and try again.
            </div>
          ) : filteredProfiles.length === 0 ? (
            <div style={{ padding: '60px', textAlign: 'center', color: 'var(--text-secondary)' }}>
              No customer profiles found. Click "Add customer" to create one.
            </div>
          ) : (
            <div className="table-wrap">
              <table className="hist-table">
                <thead>
                  <tr>
                    <th>Customer Name</th>
                    <th>Measurement Profile</th>
                    <th>Last Updated</th>
                    <th>Patterns</th>
                    <th style={{ textAlign: 'right' }}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredProfiles.map((p) => {
                    const initials = p.client_name ? p.client_name.split(' ').map(n=>n[0]).join('').slice(0,2).toUpperCase() : 'C';
                    const isSelected = selectedProfile?.measurement_id === p.measurement_id;
                    return (
                      <tr 
                        key={p.measurement_id} 
                        onClick={() => setSelectedProfile(p)}
                        style={{ 
                          cursor: 'pointer',
                          background: isSelected ? 'var(--surface-2)' : 'transparent',
                          transition: 'background 0.12s'
                        }}
                      >
                        <td style={{ padding: '14px 15px' }}>
                          <div className="file-cell">
                            <span style={{ 
                              background: isSelected ? 'var(--text-accent)' : 'var(--border-strong)', 
                              color: isSelected ? '#FFFFFF' : 'var(--text-primary)',
                              fontSize: '11px',
                              fontWeight: 'bold'
                            }}>
                              {initials}
                            </span>
                            <div>
                              <strong>{p.client_name}</strong>
                              <small>{p.email || 'No e-mail recorded'}</small>
                            </div>
                          </div>
                        </td>
                        <td>
                          <span className="chip" style={{ fontSize: '9px' }}>
                            {p.fabric_type ? p.fabric_type.toUpperCase() : 'WOVEN'} Block
                          </span>
                        </td>
                        <td>
                          <small>{p.created_at ? new Date(p.created_at).toLocaleDateString('en-GB') : '—'}</small>
                        </td>
                        <td>
                          <strong data-testid={`pattern-count-${p.measurement_id}`}>{patternCounts ? (patternCounts[p.measurement_id] || 0) : '—'}</strong>
                        </td>
                        <td style={{ textAlign: 'right' }} onClick={(e) => e.stopPropagation()}>
                          <div className="row-actions" style={{ justifyContent: 'flex-end' }}>
                            <button 
                              onClick={() => navigate('/measurements', { state: { profile: p } })} 
                              title="Edit measurements"
                            >
                              <Edit2 size={13} />
                            </button>
                            <button 
                              onClick={() => navigate('/upload', { state: { selectedProfile: p } })} 
                              title="Draft Pattern"
                              style={{ color: 'var(--text-accent)', borderColor: 'var(--text-accent)' }}
                            >
                              <Play size={13} />
                            </button>
                            <button 
                              className="delete" 
                              onClick={() => handleDelete(p.measurement_id)} 
                              title="Delete customer"
                            >
                              <Trash2 size={13} />
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Right Side: Profile Overview Panel */}
        <div>
          {selectedProfile ? (
            <div className="ui-card" style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '20px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--border)', paddingBottom: '16px' }}>
                <span className="section-kicker">Profile overview</span>
                <button 
                  onClick={() => navigate('/measurements', { state: { profile: selectedProfile } })}
                  className="btn btn-outline" 
                  style={{ height: '30px', fontSize: '11px', padding: '0 10px' }}
                >
                  <Edit2 size={12}/> Edit profile
                </button>
              </div>

              {/* Avatar section */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
                <div style={{ 
                  width: '54px', height: '54px', borderRadius: '50%', 
                  background: 'var(--text-accent)', color: '#FFF', 
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: '18px', fontWeight: 'bold'
                }}>
                  {selectedProfile.client_name ? selectedProfile.client_name.split(' ').map(n=>n[0]).join('').slice(0,2).toUpperCase() : 'C'}
                </div>
                <div>
                  <h3 style={{ fontSize: '16px', fontWeight: '600', margin: '0' }}>{selectedProfile.client_name}</h3>
                  <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                    {selectedProfile.email || 'No e-mail recorded'}
                  </span>
                </div>
              </div>

              {/* Detail fields */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', fontSize: '12px', borderTop: '1px solid var(--border)', paddingTop: '16px' }}>
                <div>
                  <span style={{ color: 'var(--text-muted)' }}>Measurement block:</span>
                  <div style={{ fontWeight: '600', color: 'var(--text-primary)', marginTop: '2px' }}>
                    {selectedProfile.fabric_type ? selectedProfile.fabric_type.toUpperCase() : 'WOVEN'}
                  </div>
                </div>
                <div>
                  <span style={{ color: 'var(--text-muted)' }}>Total patterns:</span>
                  <div style={{ fontWeight: '600', color: 'var(--text-primary)', marginTop: '2px' }}>
                    {patternCounts ? (patternCounts[selectedProfile.measurement_id] || 0) : '—'}
                  </div>
                </div>
                <div>
                  <span style={{ color: 'var(--text-muted)' }}>Height:</span>
                  <div style={{ fontWeight: '600', color: 'var(--text-primary)', marginTop: '2px' }}>
                    {selectedProfile.height_cm != null ? `${selectedProfile.height_cm} cm` : 'Not measured'}
                  </div>
                </div>
                <div>
                  <span style={{ color: 'var(--text-muted)' }}>Bust:</span>
                  <div style={{ fontWeight: '600', color: 'var(--text-primary)', marginTop: '2px' }}>
                    {selectedProfile.bust_cm != null ? `${selectedProfile.bust_cm} cm` : 'Not measured'}
                  </div>
                </div>
              </div>

              {/* Notes */}
              <div style={{ background: 'var(--surface-2)', padding: '12px 14px', borderRadius: '8px', fontSize: '12px' }}>
                <strong style={{ display: 'block', marginBottom: '4px', color: 'var(--text-primary)' }}>Notes</strong>
                <p style={{ margin: 0, color: 'var(--text-secondary)', lineHeight: '1.5' }}>
                  {selectedProfile.notes && selectedProfile.notes !== 'No notes.' ? selectedProfile.notes : 'No notes recorded.'}
                </p>
              </div>

              {/* Action */}
              <button 
                className="btn btn-primary"
                onClick={() => navigate('/upload', { state: { selectedProfile } })}
                style={{ width: '100%', height: '42px', background: 'var(--text-accent)', color: '#FFFFFF', fontWeight: 'bold' }}
              >
                Draft custom pattern
              </button>

            </div>
          ) : (
            <div className="ui-card" style={{ padding: '24px', textAlign: 'center', color: 'var(--text-secondary)' }}>
              Select a customer to view profile overview.
            </div>
          )}
        </div>

      </div>

      {/* Add Customer Modal */}
      {showAddModal && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(17, 26, 19, 0.6)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
          <div role="dialog" aria-modal="true" aria-labelledby="add-customer-h" style={{ background: '#FFFFFF', borderRadius: '12px', width: '100%', maxWidth: '480px', maxHeight: '92vh', overflowY: 'auto', padding: '24px', boxShadow: 'var(--shadow)' }}>
            <h2 id="add-customer-h" style={{ fontSize: '16px', fontWeight: '600', marginBottom: '16px' }}>Add Customer Profile</h2>
            <form onSubmit={handleAddSubmit} noValidate style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {formError && (
                <div role="alert" data-testid="customer-form-error" style={{ background: '#FEE2E2', border: '1px solid #EF4444', color: '#991B1B', borderRadius: '6px', padding: '8px 10px', fontSize: '12px' }}>
                  {formError}
                </div>
              )}
              <div>
                <label className="form-label" htmlFor="new-client-name">Full Name</label>
                <input
                  id="new-client-name"
                  type="text"
                  className="form-input" 
                  placeholder="e.g. Amara Silva"
                  value={newClient.client_name}
                  onChange={(e) => setNewClient({ ...newClient, client_name: e.target.value })}
                  required
                />
              </div>
              <div>
                <label className="form-label" htmlFor="new-client-email">Email Address (optional)</label>
                <input
                  id="new-client-email"
                  type="email"
                  className="form-input"
                  placeholder="e.g. amara@example.com"
                  value={newClient.email}
                  onChange={(e) => setNewClient({ ...newClient, email: e.target.value })}
                />
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
                {CORE_FIELDS.map((key) => (
                  <div key={key}>
                    <label className="form-label" htmlFor={`new-client-${key}`}>{FIELD_LABEL[key]} (cm)</label>
                    <input id={`new-client-${key}`} type="number" step="any" inputMode="decimal" className="form-input"
                           value={newClient[key]} onChange={(e) => setNewClient({ ...newClient, [key]: e.target.value })} />
                  </div>
                ))}
              </div>
              <p style={{ fontSize: '11px', color: 'var(--text-muted)', margin: 0 }}>
                The other drafting measurements are added later in the pattern wizard or on the Measurements page.
              </p>
              <div>
                <label className="form-label" htmlFor="new-client-notes">Notes & Fit Preferences (optional)</label>
                <textarea
                  id="new-client-notes"
                  className="form-input"
                  style={{ height: '70px', padding: '8px 12px' }}
                  placeholder="e.g. Sensitive to tight collars."
                  value={newClient.notes}
                  onChange={(e) => setNewClient({ ...newClient, notes: e.target.value })}
                />
              </div>
              <div style={{ display: 'flex', gap: '10px', justifyContent: 'flex-end', marginTop: '10px' }}>
                <button type="button" className="btn btn-outline" onClick={() => { setShowAddModal(false); setFormError(''); }}>Cancel</button>
                <button type="submit" className="btn btn-primary" style={{ background: 'var(--text-accent)' }}>Save Customer</button>
              </div>
            </form>
          </div>
        </div>
      )}

    </div>
  );
}
