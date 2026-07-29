import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { measurementsAPI } from '../services/api';

export default function Measurements() {
  const navigate = useNavigate();
  const [profiles, setProfiles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // Add new client modal state
  const [showAddModal, setShowAddModal] = useState(false);
  const [newClient, setNewClient] = useState({
    client_name: '',
    bust_cm: '',
    waist_cm: '',
    hip_cm: '',
    height_cm: '',
    fabric_type: 'woven'
  });

  // Edit client modal state
  const [showEditModal, setShowEditModal] = useState(false);
  const [editClient, setEditClient] = useState(null);

  const fetchProfiles = async () => {
    setLoading(true);
    try {
      const res = await measurementsAPI.getAll();
      setProfiles(res.data.measurements || []);
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to load client measurement profiles.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchProfiles();
  }, []);

  // Save new client profile
  const handleSaveNewClient = async (e) => {
    e.preventDefault();
    if (!newClient.client_name || !newClient.bust_cm || !newClient.waist_cm || !newClient.hip_cm || !newClient.height_cm) {
      setError('Please fill in all client measurement fields.');
      return;
    }

    try {
      await measurementsAPI.save({
        client_name: newClient.client_name,
        bust_cm: parseFloat(newClient.bust_cm),
        waist_cm: parseFloat(newClient.waist_cm),
        hip_cm: parseFloat(newClient.hip_cm),
        height_cm: parseFloat(newClient.height_cm),
        fabric_type: newClient.fabric_type
      });
      setShowAddModal(false);
      setNewClient({ client_name: '', bust_cm: '', waist_cm: '', hip_cm: '', height_cm: '', fabric_type: 'woven' });
      setError('');
      fetchProfiles();
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to save client profile.');
    }
  };

  // Update existing client profile
  const handleUpdateClient = async (e) => {
    e.preventDefault();
    if (!editClient || !editClient.measurement_id) return;

    try {
      await measurementsAPI.save({
        client_name: editClient.client_name,
        bust_cm: parseFloat(editClient.bust_cm),
        waist_cm: parseFloat(editClient.waist_cm),
        hip_cm: parseFloat(editClient.hip_cm),
        height_cm: parseFloat(editClient.height_cm),
        fabric_type: editClient.fabric_type
      });
      if (editClient.measurement_id) {
        await measurementsAPI.delete(editClient.measurement_id);
      }
      setShowEditModal(false);
      setEditClient(null);
      setError('');
      fetchProfiles();
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to update client profile.');
    }
  };

  const handleDeleteProfile = async (id) => {
    if (window.confirm('Are you sure you want to delete this customer measurement profile?')) {
      try {
        await measurementsAPI.delete(id);
        fetchProfiles();
      } catch (err) {
        alert('Failed to delete measurement profile.');
      }
    }
  };

  const handleUseForPattern = (profile) => {
    navigate('/upload', { state: { selectedProfile: profile } });
  };

  return (
    <div style={{ padding: '24px', maxWidth: '1200px', margin: '0 auto' }}>
      
      {/* Header Bar */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <h1 style={{ fontSize: '22px', fontWeight: '700', color: '#F8FAFC', marginBottom: '4px' }}>
            Customer Measurement Directory
          </h1>
          <p style={{ fontSize: '13px', color: '#94A3B8' }}>
            Dilshani Tailoring Studio — Manage customer profiles, body dimensions, and fabric preferences.
          </p>
        </div>

        <button
          className="btn btn-primary"
          onClick={() => setShowAddModal(true)}
          style={{ padding: '10px 18px', fontSize: '13px' }}
        >
          Add New Client Profile
        </button>
      </div>

      {error && (
        <div style={{ padding: '12px 16px', background: '#7F1D1D', border: '1px solid #991B1B', borderRadius: '8px', color: '#FECACA', fontSize: '13px', marginBottom: '20px' }}>
          {error}
        </div>
      )}

      {/* Summary KPI Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px', marginBottom: '24px' }}>
        <div style={{ background: '#0F172A', border: '1px solid #334155', borderRadius: '12px', padding: '16px' }}>
          <div style={{ fontSize: '12px', color: '#94A3B8', marginBottom: '6px' }}>Total Saved Clients</div>
          <div style={{ fontSize: '24px', fontWeight: '700', color: '#38BDF8' }}>{profiles.length}</div>
        </div>
        <div style={{ background: '#0F172A', border: '1px solid #334155', borderRadius: '12px', padding: '16px' }}>
          <div style={{ fontSize: '12px', color: '#94A3B8', marginBottom: '6px' }}>Fabric Types Managed</div>
          <div style={{ fontSize: '14px', fontWeight: '600', color: '#34D399', marginTop: '6px' }}>
            Woven · Knit · Stretch
          </div>
        </div>
        <div style={{ background: '#0F172A', border: '1px solid #334155', borderRadius: '12px', padding: '16px' }}>
          <div style={{ fontSize: '12px', color: '#94A3B8', marginBottom: '6px' }}>Drafting Standard</div>
          <div style={{ fontSize: '14px', fontWeight: '600', color: '#A78BFA', marginTop: '6px' }}>
            Winifred Aldrich Method
          </div>
        </div>
      </div>

      {/* Client Measurements Table */}
      <div style={{ background: '#0F172A', border: '1px solid #334155', borderRadius: '12px', overflow: 'hidden' }}>
        {loading ? (
          <div style={{ padding: '40px', textAlign: 'center', color: '#94A3B8', fontSize: '14px' }}>
            Loading customer measurement profiles...
          </div>
        ) : profiles.length === 0 ? (
          <div style={{ padding: '40px', textAlign: 'center', color: '#94A3B8', fontSize: '14px' }}>
            No customer measurement profiles found. Click <strong>"Add New Client Profile"</strong> above to register your first client!
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '13px' }}>
              <thead>
                <tr style={{ background: '#1E293B', borderBottom: '1px solid #334155', color: '#CBD5E1' }}>
                  <th style={{ padding: '14px 18px', fontWeight: '600' }}>Customer Name</th>
                  <th style={{ padding: '14px 18px', fontWeight: '600' }}>Bust (cm)</th>
                  <th style={{ padding: '14px 18px', fontWeight: '600' }}>Waist (cm)</th>
                  <th style={{ padding: '14px 18px', fontWeight: '600' }}>Hip (cm)</th>
                  <th style={{ padding: '14px 18px', fontWeight: '600' }}>Height (cm)</th>
                  <th style={{ padding: '14px 18px', fontWeight: '600' }}>Fabric Type</th>
                  <th style={{ padding: '14px 18px', fontWeight: '600' }}>Date Saved</th>
                  <th style={{ padding: '14px 18px', fontWeight: '600', textAlign: 'right' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {profiles.map((p, idx) => (
                  <tr key={p.measurement_id || idx} style={{ borderBottom: '1px solid #1E293B', color: '#F8FAFC' }}>
                    <td style={{ padding: '14px 18px', fontWeight: '600', color: '#38BDF8' }}>
                      {p.client_name || `Customer #${idx + 1}`}
                    </td>
                    <td style={{ padding: '14px 18px' }}>{p.bust_cm} cm</td>
                    <td style={{ padding: '14px 18px' }}>{p.waist_cm} cm</td>
                    <td style={{ padding: '14px 18px' }}>{p.hip_cm} cm</td>
                    <td style={{ padding: '14px 18px' }}>{p.height_cm} cm</td>
                    <td style={{ padding: '14px 18px' }}>
                      <span style={{ background: '#1E293B', border: '1px solid #334155', padding: '4px 10px', borderRadius: '4px', fontSize: '11px', textTransform: 'capitalize' }}>
                        {p.fabric_type}
                      </span>
                    </td>
                    <td style={{ padding: '14px 18px', color: '#94A3B8', fontSize: '12px' }}>
                      {p.created_at ? new Date(p.created_at).toLocaleDateString() : 'Recent'}
                    </td>
                    <td style={{ padding: '14px 18px', textAlign: 'right' }}>
                      <div style={{ display: 'flex', gap: '6px', justifyContent: 'flex-end' }}>
                        <button
                          className="btn btn-outline"
                          onClick={() => {
                            setEditClient({ ...p });
                            setShowEditModal(true);
                          }}
                          style={{ height: '30px', fontSize: '11px', padding: '0 10px', color: '#38BDF8', borderColor: '#38BDF8' }}
                        >
                          Edit Name
                        </button>
                        <button
                          className="btn btn-outline"
                          onClick={() => handleUseForPattern(p)}
                          style={{ height: '30px', fontSize: '11px', padding: '0 10px', color: '#34D399', borderColor: '#34D399' }}
                        >
                          Draft Pattern
                        </button>
                        <button
                          className="btn btn-outline"
                          onClick={() => handleDeleteProfile(p.measurement_id)}
                          style={{ height: '30px', fontSize: '11px', padding: '0 8px', color: '#EF4444', borderColor: '#EF4444' }}
                        >
                          Delete
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Add New Client Modal */}
      {showAddModal && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(9, 13, 22, 0.85)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000, padding: '20px' }}>
          <div style={{ background: '#0F172A', border: '1px solid #334155', borderRadius: '16px', width: '100%', maxWidth: '500px', padding: '24px', boxShadow: '0 20px 25px -5px rgba(0,0,0,0.5)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
              <h2 style={{ fontSize: '18px', fontWeight: '600', color: '#F8FAFC' }}>New Customer Profile</h2>
              <button onClick={() => setShowAddModal(false)} style={{ background: 'none', border: 'none', color: '#94A3B8', fontSize: '18px', cursor: 'pointer' }}>✕</button>
            </div>

            <form onSubmit={handleSaveNewClient}>
              <div style={{ marginBottom: '14px' }}>
                <label className="form-label" style={{ fontSize: '12px' }}>Customer Name</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="Enter customer name (e.g. Amara Silva)"
                  value={newClient.client_name}
                  onChange={(e) => setNewClient({ ...newClient, client_name: e.target.value })}
                  required
                />
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '14px' }}>
                <div>
                  <label className="form-label" style={{ fontSize: '12px' }}>Bust (cm)</label>
                  <input
                    type="number"
                    className="form-input"
                    placeholder="e.g. 88"
                    value={newClient.bust_cm}
                    onChange={(e) => setNewClient({ ...newClient, bust_cm: e.target.value })}
                    required
                  />
                </div>
                <div>
                  <label className="form-label" style={{ fontSize: '12px' }}>Waist (cm)</label>
                  <input
                    type="number"
                    className="form-input"
                    placeholder="e.g. 70"
                    value={newClient.waist_cm}
                    onChange={(e) => setNewClient({ ...newClient, waist_cm: e.target.value })}
                    required
                  />
                </div>
                <div>
                  <label className="form-label" style={{ fontSize: '12px' }}>Hip (cm)</label>
                  <input
                    type="number"
                    className="form-input"
                    placeholder="e.g. 94"
                    value={newClient.hip_cm}
                    onChange={(e) => setNewClient({ ...newClient, hip_cm: e.target.value })}
                    required
                  />
                </div>
                <div>
                  <label className="form-label" style={{ fontSize: '12px' }}>Height (cm)</label>
                  <input
                    type="number"
                    className="form-input"
                    placeholder="e.g. 162"
                    value={newClient.height_cm}
                    onChange={(e) => setNewClient({ ...newClient, height_cm: e.target.value })}
                    required
                  />
                </div>
              </div>

              <div style={{ marginBottom: '20px' }}>
                <label className="form-label" style={{ fontSize: '12px' }}>Fabric Type</label>
                <select
                  className="form-select"
                  value={newClient.fabric_type}
                  onChange={(e) => setNewClient({ ...newClient, fabric_type: e.target.value })}
                >
                  <option value="woven">woven</option>
                  <option value="knit">knit</option>
                  <option value="stretch-knit">stretch-knit</option>
                </select>
              </div>

              <div style={{ display: 'flex', gap: '10px', justifyContent: 'flex-end' }}>
                <button type="button" className="btn btn-outline" onClick={() => setShowAddModal(false)}>Cancel</button>
                <button type="submit" className="btn btn-primary">Save Profile</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Edit Client Profile Modal */}
      {showEditModal && editClient && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(9, 13, 22, 0.85)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000, padding: '20px' }}>
          <div style={{ background: '#0F172A', border: '1px solid #334155', borderRadius: '16px', width: '100%', maxWidth: '500px', padding: '24px', boxShadow: '0 20px 25px -5px rgba(0,0,0,0.5)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
              <h2 style={{ fontSize: '18px', fontWeight: '600', color: '#F8FAFC' }}>Edit Customer Name & Dimensions</h2>
              <button onClick={() => setShowEditModal(false)} style={{ background: 'none', border: 'none', color: '#94A3B8', fontSize: '18px', cursor: 'pointer' }}>✕</button>
            </div>

            <form onSubmit={handleUpdateClient}>
              <div style={{ marginBottom: '14px' }}>
                <label className="form-label" style={{ fontSize: '12px' }}>Customer Name</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="Enter customer name (e.g. Dilshani Vitharana)"
                  value={editClient.client_name}
                  onChange={(e) => setEditClient({ ...editClient, client_name: e.target.value })}
                  required
                />
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '14px' }}>
                <div>
                  <label className="form-label" style={{ fontSize: '12px' }}>Bust (cm)</label>
                  <input
                    type="number"
                    className="form-input"
                    value={editClient.bust_cm}
                    onChange={(e) => setEditClient({ ...editClient, bust_cm: e.target.value })}
                    required
                  />
                </div>
                <div>
                  <label className="form-label" style={{ fontSize: '12px' }}>Waist (cm)</label>
                  <input
                    type="number"
                    className="form-input"
                    value={editClient.waist_cm}
                    onChange={(e) => setEditClient({ ...editClient, waist_cm: e.target.value })}
                    required
                  />
                </div>
                <div>
                  <label className="form-label" style={{ fontSize: '12px' }}>Hip (cm)</label>
                  <input
                    type="number"
                    className="form-input"
                    value={editClient.hip_cm}
                    onChange={(e) => setEditClient({ ...editClient, hip_cm: e.target.value })}
                    required
                  />
                </div>
                <div>
                  <label className="form-label" style={{ fontSize: '12px' }}>Height (cm)</label>
                  <input
                    type="number"
                    className="form-input"
                    value={editClient.height_cm}
                    onChange={(e) => setEditClient({ ...editClient, height_cm: e.target.value })}
                    required
                  />
                </div>
              </div>

              <div style={{ marginBottom: '20px' }}>
                <label className="form-label" style={{ fontSize: '12px' }}>Fabric Type</label>
                <select
                  className="form-select"
                  value={editClient.fabric_type}
                  onChange={(e) => setEditClient({ ...editClient, fabric_type: e.target.value })}
                >
                  <option value="woven">woven</option>
                  <option value="knit">knit</option>
                  <option value="stretch-knit">stretch-knit</option>
                </select>
              </div>

              <div style={{ display: 'flex', gap: '10px', justifyContent: 'flex-end' }}>
                <button type="button" className="btn btn-outline" onClick={() => setShowEditModal(false)}>Cancel</button>
                <button type="submit" className="btn btn-primary">Save Changes</button>
              </div>
            </form>
          </div>
        </div>
      )}

    </div>
  );
}
