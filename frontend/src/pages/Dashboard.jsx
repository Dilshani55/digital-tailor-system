import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AlertCircle, ArrowRight, Download, Leaf, Plus, RefreshCw, Scissors, Sparkles } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { patternsAPI } from '../services/api';
import LoadingSpinner from '../components/LoadingSpinner';
import GarmentIllustration from '../components/GarmentIllustration';

const label = (v) => (v ? String(v).replace(/-/g, ' ').replace(/^./, (c) => c.toUpperCase()) : 'Pattern');

export default function Dashboard() {
  const { user } = useAuth();
  const navigate = useNavigate();
  // The saved-pattern list is the single source for these numbers, the customers page and the pattern library.
  const [patterns, setPatterns] = useState([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  const load = () => {
    setLoading(true);
    patternsAPI.getAll()
      .then((p) => { setPatterns(p.data.patterns || []); setError(''); })
      .catch(() => setError('Dashboard data could not be loaded. The numbers below are unknown, not zero.'))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const nestingPatterns = patterns.filter((p) => Number.isFinite(Number(p.nesting_summary?.waste_cm2)));
  const reusableAreaM2 = nestingPatterns.reduce((sum, p) => sum + Number(p.nesting_summary.waste_cm2), 0) / 10000;
  const name = user?.full_name?.split(' ')[0] || 'there';
  if (loading) return <LoadingSpinner message="Preparing your workspace…" />;

  const withPdf = patterns.filter((p) => (p.exports || []).some((e) => e.file_available !== false)).length;
  const unknown = '—';                 // shown instead of a number when the data could not be loaded
  const metrics = [
    { label: 'Patterns created', value: error ? unknown : patterns.length, note: 'Open your pattern library', icon: Scissors, onClick: () => navigate('/history') },
    { label: 'PDF guides', value: error ? unknown : withPdf,
      note: error ? 'View and download guides' : `${patterns.length - withPdf} saved pattern${patterns.length - withPdf === 1 ? '' : 's'} with PDF pending`,
      icon: Download, onClick: () => navigate('/history') },
    { label: 'Potential reusable offcuts', value: error ? unknown : `${reusableAreaM2.toFixed(2)} m²`, note: `From ${nestingPatterns.length} saved fabric layouts`, icon: Leaf, onClick: () => navigate('/fabric-savings') },
  ];

  return (
    <div className="page">
      <section className="dashboard-hero">
        <div>
          <span className="eyebrow"><Sparkles size={14} /> TailorAI workspace</span>
          <h1>Welcome back, {name}</h1>
          <p>Create a new made-to-measure pattern or continue working with a recent design.</p>
        </div>
        <button className="btn btn-primary btn-lg" onClick={() => navigate('/upload')}><Plus size={18} /> Create new pattern</button>
      </section>

      {error && (
        <div role="alert" className="alert error dashboard-error">
          <AlertCircle size={17} />{error}
          <button type="button" className="btn btn-outline" style={{ marginLeft: 'auto' }} onClick={load}><RefreshCw size={14} /> Try again</button>
        </div>
      )}

      <section className="stats-grid">
        {metrics.map(({ label: l, value, note, icon: Icon, onClick }) => (
          <button type="button" className="stat-card" key={l} onClick={onClick}>
            <span className="stat-icon" aria-hidden="true"><Icon size={20} /></span>
            <span>{l}</span>
            <strong>{value}</strong>
            <small>{note}</small>
          </button>
        ))}
      </section>

      <section className="dashboard-grid">
        <article className="ui-card">
          <div className="card-head">
            <div><span className="section-kicker">Pattern activity</span><h2>Recent patterns</h2></div>
            <button className="text-btn" onClick={() => navigate('/history')}>View library <ArrowRight size={15} /></button>
          </div>
          {error ? (
            <p className="offcut-empty" data-testid="recent-unavailable">Recent patterns could not be loaded.</p>
          ) : patterns.length === 0 ? (
            <div className="empty-state compact">
              <span><Scissors size={24} /></span>
              <h3>No patterns yet</h3>
              <p>Create your first pattern to see its measurements and fabric estimate here.</p>
              <button className="btn btn-outline" onClick={() => navigate('/upload')}><Plus size={15} /> Create pattern</button>
            </div>
          ) : (
            <div className="recent-grid">
              {patterns.slice(0, 6).map((p, i) => (
                <button type="button" className="recent-card" key={p.pattern_id || i}
                        onClick={() => navigate(p.pattern_id ? `/patterns/${p.pattern_id}` : '/history')}>
                  <span className="garment-thumb"><GarmentIllustration type={p.garment_type} /></span>
                  <span className="recent-card-body">
                    <strong>{p.project_name || `${label(p.garment_type)} pattern`}</strong>
                    <small>{p.yardage_metres > 0 ? `${p.yardage_metres} m fabric` : 'Fabric plan pending'} · {p.pieces_count ?? 0} pieces{p.customer_name ? ` · ${p.customer_name}` : ''}</small>
                    <span className="fabric-tags">
                      <span className="tag">{label(p.garment_type)}</span>
                      {p.selected_fabric_name && <span className="tag">{p.selected_fabric_name}</span>}
                    </span>
                  </span>
                </button>
              ))}
            </div>
          )}
        </article>

        <article className="ui-card">
          <div className="card-head">
            <div><span className="section-kicker">Material reuse</span><h2>Potential reusable offcuts</h2></div>
            <button className="text-btn" onClick={() => navigate('/fabric-savings')}>View details <ArrowRight size={15} /></button>
          </div>
          <p className="offcut-explainer">Estimated leftover area from saved nesting layouts. Actual reuse depends on each offcut&apos;s shape and size.</p>
          {nestingPatterns.length ? (
            <div className="offcut-list">
              {nestingPatterns.slice(0, 4).map((p) => (
                <button type="button" className="offcut-row" key={p.pattern_id} onClick={() => navigate('/fabric-savings')}>
                  <span><strong className="capitalize">{label(p.garment_type)}</strong>
                    <small>{p.selected_fabric_name || 'Fabric not recorded'} · {p.nesting_summary.fabric_width_cm} cm wide</small></span>
                  <strong>{(Number(p.nesting_summary.waste_cm2) / 10000).toFixed(3)} m²</strong>
                </button>
              ))}
            </div>
          ) : <p className="offcut-empty">{error ? 'Saved fabric layouts could not be loaded.' : 'No saved nesting breakdowns yet.'}</p>}
        </article>
      </section>
    </div>
  );
}
