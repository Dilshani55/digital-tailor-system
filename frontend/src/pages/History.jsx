import { useState, useEffect } from 'react';
import { useNavigate }         from 'react-router-dom';
import { exportAPI }           from '../services/api';
import LoadingSpinner          from '../components/LoadingSpinner';

export default function History() {
  const navigate              = useNavigate();
  const [exports, setExports] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchExports = async () => {
    try {
      const res = await exportAPI.getAll();
      setExports(res.data.exports || []);
    } catch (err) {
      console.error(err);
      setExports([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchExports();
  }, []);

  const handleDownload = async (exportId) => {
    try {
      const res   = await exportAPI.download(exportId);
      const url   = window.URL.createObjectURL(new Blob([res.data]));
      const link  = document.createElement('a');
      link.href   = url;
      link.download = `drafting_guide_${exportId}.pdf`;
      link.click();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      alert('Download started.');
    }
  };

  const handleDelete = async (exportId) => {
    if (!window.confirm("Are you sure you want to delete this pattern export history?")) return;
    try {
      await exportAPI.delete(exportId);
      // Remove deleted item from state
      setExports(exports.filter(e => e.export_id !== exportId));
    } catch (err) {
      alert('Failed to delete export. Please try again.');
    }
  };

  if (loading) return <LoadingSpinner message="Loading pattern history..." />;

  return (
    <div className="view active" id="v-history">
      <div className="ui-card" style={{ padding: 0, overflow: 'hidden' }}>
        <div className="card-head" style={{ padding: '16px 20px', borderBottom: '1px solid var(--border)', marginBottom: 0 }}>
          <span className="card-title">Pattern history</span>
          <button
            className="btn btn-primary"
            style={{ height: '32px', fontSize: '12px' }}
            onClick={() => navigate('/upload')}
          >
            New pattern
          </button>
        </div>
        
        {exports.length === 0 ? (
          <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-secondary)', fontSize: '13px' }}>
            No pattern export history found. Click <strong>New pattern</strong> to generate your first PDF guide.
          </div>
        ) : (
          <table className="hist-table">
            <thead>
              <tr>
                <th>Garment</th>
                <th>Features</th>
                <th>Fabric</th>
                <th>Yardage</th>
                <th>Efficiency</th>
                <th>Date</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {exports.map((e) => (
                <tr key={e.export_id}>
                  <td><strong>{e.filename.includes('blouse') ? 'Blouse' : 'Pattern'}</strong></td>
                  <td>
                    <span className="chip">
                      v-neck · short sleeve
                    </span>
                  </td>
                  <td>Woven</td>
                  <td>1.83m</td>
                  <td><span style={{ color: '#34D399', fontWeight: 600 }}>71%</span></td>
                  <td style={{ color: 'var(--text-secondary)' }}>
                    {new Date(e.exported_at).toLocaleDateString('en-GB')}
                  </td>
                  <td>
                    <div style={{ display: 'flex', gap: '6px' }}>
                      <button
                        className="btn btn-success"
                        style={{ height: '28px', fontSize: '11px', padding: '0 12px' }}
                        onClick={() => handleDownload(e.export_id)}
                      >
                        Download
                      </button>
                      <button
                        className="btn"
                        style={{ height: '28px', fontSize: '11px', padding: '0 12px', background: '#7F1D1D', color: '#FECACA' }}
                        onClick={() => handleDelete(e.export_id)}
                      >
                        Delete
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
