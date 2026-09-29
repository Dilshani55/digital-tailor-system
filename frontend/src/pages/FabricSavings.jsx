import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, Leaf } from 'lucide-react';
import { patternsAPI } from '../services/api';
import LoadingSpinner from '../components/LoadingSpinner';

export default function FabricSavings() {
  const navigate = useNavigate();
  const [patterns, setPatterns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    patternsAPI.getAll()
      .then((response) => setPatterns(response.data.patterns || []))
      .catch(() => setError('Fabric layout details could not be loaded. Please refresh and try again.'))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <LoadingSpinner message="Loading saved fabric layouts..." />;

  const layouts = patterns.filter((pattern) => Number.isFinite(Number(pattern.nesting_summary?.waste_cm2)));
  const totalAreaM2 = layouts.reduce((sum, pattern) => sum + Number(pattern.nesting_summary.waste_cm2), 0) / 10000;
  const pendingCount = patterns.length - layouts.length;

  return (
    <div className="history-page">
      <section className="page-heading">
        <div>
          <span className="section-kicker">Material reuse</span>
          <h1>Potential reusable offcuts</h1>
          <p>Estimated leftover fabric area from your saved pattern nesting layouts.</p>
        </div>
        <button className="btn btn-outline" onClick={() => navigate('/dashboard')}><ArrowLeft size={16}/> Dashboard</button>
      </section>

      {error ? <div role="alert" className="dashboard-error">{error}</div> : (
        <>
          <section className="offcut-total ui-card">
            <span className="stat-icon mint"><Leaf size={20}/></span>
            <div><span>Total estimated offcut area</span><strong>{totalAreaM2.toFixed(3)} m²</strong></div>
            <small>Area may be reusable; this estimate does not assess remnant shape or minimum usable piece size.</small>
          </section>

          <section className="ui-card offcut-details">
            <div className="card-head"><div><span className="section-kicker">Saved layout records</span><h2>Breakdown by pattern</h2></div><span>{layouts.length} layouts</span></div>
            {layouts.length ? <div className="offcut-list">{layouts.map((pattern) => {
              const summary = pattern.nesting_summary;
              return <article className="offcut-detail-row" key={pattern.pattern_id}>
                <div><strong className="capitalize">{pattern.garment_type || 'Pattern'}</strong><small>{pattern.selected_fabric_name || 'Fabric not recorded'} · {summary.fabric_width_cm} cm width · {summary.cutting_mode} cut</small></div>
                <div className="offcut-numbers"><strong>{(Number(summary.waste_cm2)/10000).toFixed(3)} m² potential offcut</strong><small>{Number(summary.waste_cm2).toLocaleString()} cm² · {summary.waste_percent}% layout remainder</small><small>{summary.fabric_length_cm} cm marker length · {summary.total_pieces} placed pieces</small></div>
              </article>;
            })}</div> : <div className="empty-state"><span><Leaf size={26}/></span><h2>No saved nesting data</h2><p>New patterns will appear here after their fabric layout is calculated.</p></div>}
            {pendingCount > 0 && <p className="offcut-pending">{pendingCount} older pattern{pendingCount === 1 ? '' : 's'} {pendingCount === 1 ? 'has' : 'have'} no saved nesting breakdown, so {pendingCount === 1 ? 'it is' : 'they are'} excluded from this total.</p>}
          </section>
        </>
      )}
    </div>
  );
}