import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, Plus, Filter, Edit2, Play, Trash2 } from 'lucide-react';
import { measurementsAPI } from '../services/api';
import { validateMeasurements, parseFieldErrors, buildPayload, CORE_FIELDS } from '../utils/measurementSchema';
import LoadingSpinner from '../components/LoadingSpinner';

export default function Customers() {
  const navigate = useNavigate();
  const [profiles, setProfiles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedProfile, setSelectedProfile] = useState(null);

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
    try {
      const res = await measurementsAPI.getAll();
      const list = res.data.measurements || [];
      setProfiles(list);
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
    if (!newClient.client_name) return;
    const localErrors = validateMeasurements(newClient, 'cm', CORE_FIELDS);
    if (Object.keys(localErrors).length > 0) {
      setError(Object.values(localErrors).join(' '));
      return;
    }

    try {
      await measurementsAPI.save({
        client_name: newClient.client_name,
        email: newClient.email || `${newClient.client_name.toLowerCase().replace(/\s+/g, '.')}@email.com`,
        notes: newClient.notes || 'No notes added.',
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
      setError(Object.values(parsed).join(' ') || 'Failed to save customer profile.');
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
                              <small>{p.email || `${p.client_name.toLowerCase().replace(/\s+/g, '')}@email.com`}</small>
                            </div>
                          </div>
                        </td>
                        <td>
                          <span className="chip" style={{ fontSize: '9px' }}>
                            {p.fabric_type ? p.fabric_type.toUpperCase() : 'WOVEN'} Block
                          </span>
                        </td>
                        <td>
                          <small>{p.created_at ? new Date(p.created_at).toLocaleDateString() : 'Recent'}</small>
                        </td>
                        <td>
                          <strong>{p.patterns_count || '2'}</strong>
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
              <div style={{ display: 'flex', justify: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--border)', paddingBottom: '16px' }}>
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
                    {selectedProfile.email || `${selectedProfile.client_name.toLowerCase().replace(/\s+/g, '')}@email.com`}
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
                    {selectedProfile.patterns_count || '2'}
                  </div>
                </div>
                <div>
                  <span style={{ color: 'var(--text-muted)' }}>Height:</span>
                  <div style={{ fontWeight: '600', color: 'var(--text-primary)', marginTop: '2px' }}>
                    {selectedProfile.height_cm} cm
                  </div>
                </div>
                <div>
                  <span style={{ color: 'var(--text-muted)' }}>Bust:</span>
                  <div style={{ fontWeight: '600', color: 'var(--text-primary)', marginTop: '2px' }}>
                    {selectedProfile.bust_cm} cm
                  </div>
                </div>
              </div>

              {/* Notes */}
              <div style={{ background: 'var(--surface-2)', padding: '12px 14px', borderRadius: '8px', fontSize: '12px' }}>
                <strong style={{ display: 'block', marginBottom: '4px', color: 'var(--text-primary)' }}>Notes</strong>
                <p style={{ margin: 0, color: 'var(--text-secondary)', lineHeight: '1.5' }}>
                  {selectedProfile.notes || 'No design notes or fit alerts recorded. Tap Edit to add constraints.'}
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
          <div style={{ background: '#FFFFFF', borderRadius: '12px', width: '100%', maxWidth: '480px', padding: '24px', boxShadow: 'var(--shadow)' }}>
            <h2 style={{ fontSize: '16px', fontWeight: '600', marginBottom: '16px' }}>Add Customer Profile</h2>
            <form onSubmit={handleAddSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {error && (
                <div role="alert" data-testid="customer-form-error" style={{ background: '#FEE2E2', border: '1px solid #EF4444', color: '#991B1B', borderRadius: '6px', padding: '8px 10px', fontSize: '12px' }}>
                  {error}
                </div>
              )}
              <div>
                <label className="form-label">Full Name</label>
                <input 
                  type="text" 
                  className="form-input" 
                  placeholder="e.g. William Parker"
                  value={newClient.client_name}
                  onChange={(e) => setNewClient({ ...newClient, client_name: e.target.value })}
                  required
                />
              </div>
              <div>
                <label className="form-label">Email Address</label>
                <input 
                  type="email" 
                  className="form-input" 
                  placeholder="e.g. william@email.com"
                  value={newClient.email}
                  onChange={(e) => setNewClient({ ...newClient, email: e.target.value })}
                />
              </div>
              <div>
                <label className="form-label">Notes & Fit Preferences</label>
                <textarea 
                  className="form-input"
                  style={{ height: '70px', padding: '8px 12px' }}
                  placeholder="e.g. Sensitive to tight collars."
                  value={newClient.notes}
                  onChange={(e) => setNewClient({ ...newClient, notes: e.target.value })}
                />
              </div>
              <div style={{ display: 'flex', gap: '10px', justifyContent: 'flex-end', marginTop: '10px' }}>
                <button type="button" className="btn btn-outline" onClick={() => setShowAddModal(false)}>Cancel</button>
                <button type="submit" className="btn btn-primary" style={{ background: 'var(--text-accent)' }}>Save Customer</button>
              </div>
            </form>
          </div>
        </div>
      )}

    </div>
  );
}
