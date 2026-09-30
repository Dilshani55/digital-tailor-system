import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Download, Eye, FileText, Plus, Search, Trash2 } from 'lucide-react';
import { exportAPI } from '../services/api';
import LoadingSpinner from '../components/LoadingSpinner';
import GarmentIllustration from '../components/GarmentIllustration';

const FILTERS = [
  { id: 'all', label: 'All patterns' },
  { id: 'blouse', label: 'Blouses' },
  { id: 't-shirt', label: 'T-shirts' },
  { id: 'crop-top', label: 'Crop tops' },
];
const label = (v) => (v ? String(v).replace(/-/g, ' ').replace(/^./, (c) => c.toUpperCase()) : null);

/** Pattern library: every saved pattern that has a printable PDF, shown with stored values only. */
export default function History() {
  const navigate = useNavigate();
  const [exports, setExports] = useState([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState('all');
  const [loadError, setLoadError] = useState('');
  const [actionError, setActionError] = useState('');

  useEffect(() => {
    exportAPI.getAll()
      .then((r) => setExports(r.data.exports || []))
      .catch(() => { setExports([]); setLoadError('Could not load your pattern library. Please refresh and try again.'); })
      .finally(() => setLoading(false));
  }, []);

  const download = async (e) => {
    setActionError('');
    try {
      const r = await exportAPI.download(e.export_id);
      const url = URL.createObjectURL(new Blob([r.data], { type: 'application/pdf' }));
      const a = document.createElement('a');
      a.href = url;
      a.download = `sewing_pattern_${e.pattern_id || e.export_id}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      setActionError('Download failed. Please try again.');
    }
  };

  const remove = async (id) => {
    if (!window.confirm('Delete this PDF guide from your library? The saved pattern itself is kept.')) return;
    setActionError('');
    try {
      await exportAPI.delete(id);
      setExports((v) => v.filter((e) => e.export_id !== id));
    } catch {
      setActionError('Unable to delete this item.');
    }
  };

  if (loading) return <LoadingSpinner message="Loading your pattern library…" />;

  const q = query.trim().toLowerCase();
  const rows = exports.filter((e) => (filter === 'all' || e.garment_type === filter)
    && [e.filename, e.garment_type, e.fabric_name, e.neckline_type, e.sleeve_length].filter(Boolean).join(' ').toLowerCase().includes(q));

  return (
    <div className="page">
      <section className="page-heading">
        <div>
          <h1>Pattern library</h1>
          <p>Browse, download and manage your printable pattern guides.</p>
        </div>
        <button className="btn btn-primary" onClick={() => navigate('/upload')}><Plus size={17} /> Create pattern</button>
      </section>

      {loadError && <div role="alert" className="alert error dashboard-error">{loadError}</div>}
      {actionError && <div role="alert" className="alert error dashboard-error">{actionError}</div>}

      <div className="toolbar">
        <div className="filter-chips" role="group" aria-label="Filter by garment">
          {FILTERS.map((f) => (
            <button key={f.id} type="button" aria-pressed={filter === f.id} onClick={() => setFilter(f.id)}>{f.label}</button>
          ))}
        </div>
        <div className="search-field" style={{ maxWidth: 360, marginLeft: 'auto' }}>
          <Search size={17} aria-hidden="true" />
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search patterns…" aria-label="Search patterns" />
        </div>
      </div>

      {rows.length === 0 ? (
        <div className="ui-card empty-state">
          <span><FileText size={26} /></span>
          <h2>{query || filter !== 'all' ? 'No matching patterns' : 'Your pattern library is empty'}</h2>
          <p>{query || filter !== 'all' ? 'Try another search term or filter.' : 'Generate your first personalised pattern and its PDF guide will appear here.'}</p>
          {!query && filter === 'all' && <button className="btn btn-primary" onClick={() => navigate('/upload')}><Plus size={16} /> Create first pattern</button>}
        </div>
      ) : (
        <div className="library-grid" data-testid="library-grid">
          {rows.map((e, i) => (
            <article className="library-item" key={e.export_id || i}>
              <span className="garment-thumb"><GarmentIllustration type={e.garment_type} /></span>
              <div className="library-item-body">
                <h3>{label(e.garment_type) || 'Garment unavailable'}</h3>
                <small>{[label(e.neckline_type), label(e.sleeve_length)].filter(Boolean).join(' · ') || 'Design details unavailable'}</small>
                <small>{e.fabric_name || 'Fabric unavailable'} · {e.yardage_metres != null ? `${e.yardage_metres} m` : 'length not calculated'}</small>
                <div className="library-item-tags">
                  <span className="tag">{e.fabric_width_cm != null ? `${e.fabric_width_cm} cm fabric width` : 'Fabric width unavailable'}</span>
                  {e.utilisation_percent != null
                    ? <span className="tag">{e.utilisation_percent}% utilisation</span>
                    : <span className="tag">Not calculated</span>}
                </div>
              </div>
              <div className="library-item-foot">
                <small>{e.exported_at ? `Created ${new Date(e.exported_at).toLocaleDateString('en-GB')}` : 'Date unavailable'}</small>
                <div className="row-actions">
                  <button aria-label="View pattern" title="View pattern" onClick={() => navigate(`/patterns/${e.pattern_id}`)}><Eye size={16} /></button>
                  <button aria-label="Download" title="Download PDF" onClick={() => download(e)}><Download size={16} /></button>
                  <button className="delete" aria-label="Delete" title="Delete PDF" onClick={() => remove(e.export_id)}><Trash2 size={16} /></button>
                </div>
              </div>
            </article>
          ))}
        </div>
      )}
    </div>
  );
}
