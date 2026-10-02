import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Download, Eye, FilePlus, FileText, FileX, Plus, RefreshCw, Search, Trash2 } from 'lucide-react';
import { exportAPI, patternsAPI } from '../services/api';
import { friendlyError } from '../utils/friendlyError';
import LoadingSpinner from '../components/LoadingSpinner';
import GarmentIllustration from '../components/GarmentIllustration';

const FILTERS = [
  { id: 'all', label: 'All patterns' },
  { id: 'blouse', label: 'Blouses' },
  { id: 't-shirt', label: 'T-shirts' },
];
const label = (v) => (v ? String(v).replace(/-/g, ' ').replace(/^./, (c) => c.toUpperCase()) : null);

/** The newest PDF of a pattern whose file is still on the server (undefined: none). */
const readyPdf = (p) => (p.exports || []).find((e) => e.file_available !== false);

/** PDF state of a saved pattern, from its stored PDF records only. */
function pdfState(p) {
  if (readyPdf(p)) return { id: 'ready', text: 'PDF ready' };
  if ((p.exports || []).length) return { id: 'missing', text: 'PDF file missing' };
  return { id: 'pending', text: 'PDF pending' };
}

/**
 * Pattern library: every saved pattern (the same records the dashboard and the customers page count),
 * whether or not a printable PDF has been created for it yet. Stored values only.
 */
export default function History() {
  const navigate = useNavigate();
  const [patterns, setPatterns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState('all');
  const [loadError, setLoadError] = useState('');
  const [actionError, setActionError] = useState('');
  const [busy, setBusy] = useState('');                 // pattern id an action is running for

  const load = () => patternsAPI.getAll()
    .then((r) => { setPatterns(r.data.patterns || []); setLoadError(''); })
    .catch(() => setLoadError('Could not load your pattern library. This is a loading problem, not an empty library.'))
    .finally(() => setLoading(false));

  useEffect(() => { load(); }, []);

  const retry = () => { setLoading(true); load(); };

  const run = async (p, fallback, action) => {
    setActionError('');
    setBusy(p.pattern_id);
    try {
      await action();
    } catch (e) {
      setActionError(friendlyError(e, fallback));
    } finally {
      setBusy('');
    }
  };

  const download = (p) => run(p, 'Download failed. Please try again.', async () => {
    const r = await exportAPI.download(readyPdf(p).export_id);
    const url = URL.createObjectURL(new Blob([r.data], { type: 'application/pdf' }));
    const a = document.createElement('a');
    a.href = url;
    a.download = `sewing_pattern_${p.pattern_id}.pdf`;
    a.click();
    URL.revokeObjectURL(url);
  });

  const createPdf = (p) => run(p, 'The PDF could not be created. Please try again.', async () => {
    await exportAPI.pdf(p.pattern_id, { part: 'overview' });       // one page at a reduced scale; real size is chosen in the wizard
    await load();
  });

  const removePdf = (p) => {
    if (!window.confirm('Delete the PDF of this pattern? The saved pattern itself is kept and a new PDF can be created later.')) return;
    run(p, 'Unable to delete this PDF.', async () => {
      try {
        for (const e of p.exports || []) await exportAPI.delete(e.export_id);
      } finally {
        await load();
      }
    });
  };

  const removePattern = (p) => {
    if (!window.confirm('Delete this saved pattern and its PDF? The customer and their measurements are kept. This cannot be undone.')) return;
    run(p, 'Unable to delete this pattern.', async () => {
      await patternsAPI.delete(p.pattern_id);
      await load();
    });
  };

  if (loading) return <LoadingSpinner message="Loading your pattern library…" />;

  const q = query.trim().toLowerCase();
  const rows = patterns.filter((p) => (filter === 'all' || p.garment_type === filter)
    && [p.project_name, p.customer_name, p.garment_type, p.selected_fabric_name, p.neckline_type, p.sleeve_length]
      .filter(Boolean).join(' ').toLowerCase().includes(q));

  return (
    <div className="page">
      <section className="page-heading">
        <div>
          <h1>Pattern library</h1>
          <p>Every saved pattern, with its printable PDF guide when one has been created.</p>
        </div>
        <button className="btn btn-primary" onClick={() => navigate('/upload')}><Plus size={17} /> Create pattern</button>
      </section>

      {actionError && <div role="alert" className="alert error dashboard-error">{actionError}</div>}

      {loadError ? (
        <div className="ui-card empty-state" data-testid="library-error">
          <span><RefreshCw size={26} /></span>
          <h2>The pattern library could not be loaded</h2>
          <p role="alert">{loadError}</p>
          <button className="btn btn-primary" onClick={retry}><RefreshCw size={16} /> Try again</button>
        </div>
      ) : (
        <>
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
              <h2>{patterns.length ? 'No matching patterns' : 'Your pattern library is empty'}</h2>
              <p>{patterns.length ? 'Try another search term or filter.' : 'Generate your first personalised pattern and it will appear here.'}</p>
              {!patterns.length && <button className="btn btn-primary" onClick={() => navigate('/upload')}><Plus size={16} /> Create first pattern</button>}
            </div>
          ) : (
            <div className="library-grid" data-testid="library-grid">
              {rows.map((p) => {
                const state = pdfState(p);
                const n = p.nesting_summary || {};
                const working = busy === p.pattern_id;
                return (
                  <article className="library-item" key={p.pattern_id} data-testid={`library-item-${p.pattern_id}`}>
                    <span className="garment-thumb"><GarmentIllustration type={p.garment_type} /></span>
                    <div className="library-item-body">
                      <h3>{p.project_name || label(p.garment_type) || 'Garment unavailable'}</h3>
                      <small>{[p.project_name ? label(p.garment_type) : null, label(p.neckline_type), label(p.sleeve_length)].filter(Boolean).join(' · ') || 'Design details unavailable'}</small>
                      <small>{p.customer_name ? `For ${p.customer_name}` : 'Customer not recorded'}</small>
                      <small>{p.selected_fabric_name || 'Fabric unavailable'} · {p.yardage_metres > 0 ? `${p.yardage_metres} m` : 'length not calculated'}</small>
                      <div className="library-item-tags">
                        <span className={`tag pdf-${state.id}`} data-testid={`pdf-status-${p.pattern_id}`}>{state.text}</span>
                        <span className="tag">{n.fabric_width_cm != null ? `${n.fabric_width_cm} cm fabric width` : 'Fabric width unavailable'}</span>
                        {n.utilisation_percent != null
                          ? <span className="tag">{n.utilisation_percent}% utilisation</span>
                          : <span className="tag">Not calculated</span>}
                      </div>
                    </div>
                    <div className="library-item-foot">
                      <small>{p.generated_at ? `Created ${new Date(p.generated_at).toLocaleDateString('en-GB')}` : 'Date unavailable'}</small>
                      <div className="row-actions">
                        <button aria-label="View pattern" title="View pattern" onClick={() => navigate(`/patterns/${p.pattern_id}`)}><Eye size={16} /></button>
                        {state.id === 'ready' ? (
                          <>
                            <button aria-label="Download PDF" title="Download PDF" disabled={working} onClick={() => download(p)}><Download size={16} /></button>
                            <button className="delete" aria-label="Delete PDF only" title="Delete PDF only (keeps the pattern)" disabled={working} onClick={() => removePdf(p)}><FileX size={16} /></button>
                          </>
                        ) : p.validation_passed !== false && (
                          <button aria-label="Create PDF" title="Create the printable PDF" disabled={working} onClick={() => createPdf(p)}><FilePlus size={16} /></button>
                        )}
                        <button className="delete" aria-label="Delete pattern" title="Delete pattern (and its PDF)" disabled={working} onClick={() => removePattern(p)}><Trash2 size={16} /></button>
                      </div>
                    </div>
                  </article>
                );
              })}
            </div>
          )}
        </>
      )}
    </div>
  );
}
