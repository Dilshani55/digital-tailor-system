import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AlertCircle, ArrowRight, Download, FileClock, Leaf, Plus, Scissors, Sparkles } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { patternsAPI, exportAPI } from '../services/api';
import LoadingSpinner from '../components/LoadingSpinner';

export default function Dashboard() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [patterns, setPatterns] = useState([]);
  const [exports, setExports] = useState([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    Promise.all([patternsAPI.getAll(), exportAPI.getAll()])
      .then(([p, e]) => { setPatterns(p.data.patterns || []); setExports(e.data.exports || []); })
      .catch(() => setError('Dashboard data could not be loaded. Please refresh and try again.'))
      .finally(() => setLoading(false));
  }, []);
  const nestingPatterns = patterns.filter((p) => Number.isFinite(Number(p.nesting_summary?.waste_cm2)));
  const reusableAreaM2 = nestingPatterns.reduce((sum, p) => sum + Number(p.nesting_summary.waste_cm2), 0) / 10000;
  const name = user?.full_name?.split(' ')[0] || 'Dilshani';
  if (loading) return <LoadingSpinner message="Preparing your workspace..." />;

  const metrics = [
    { label:'Patterns created', value:patterns.length, note:'Open your pattern library', icon:Scissors, tone:'green', onClick:()=>navigate('/history') },
    { label:'PDF guides', value:exports.length, note:'View and download guides', icon:Download, tone:'blue', onClick:()=>navigate('/history') },
    { label:'Potential reusable offcuts', value:`${reusableAreaM2.toFixed(2)} m²`, note:`From ${nestingPatterns.length} saved fabric layouts`, icon:Leaf, tone:'mint', onClick:()=>navigate('/fabric-savings') },
  ];

  return (
    <div className="dashboard-page">
      <section className="dashboard-hero">
        <div>
          <span className="eyebrow"><Sparkles size={14}/> TailorAI workspace</span>
          <h1>Welcome back, {name}</h1>
          <p>Create a new made-to-measure pattern or continue working with a recent design.</p>
        </div>
        <button className="btn btn-primary btn-lg" onClick={()=>navigate('/upload')}><Plus size={17}/> Create new pattern</button>
      </section>
      {error && <div role="alert" className="dashboard-error"><AlertCircle size={17}/>{error}</div>}
      <section className="stats-grid" style={{ gridTemplateColumns:'repeat(3, minmax(0, 1fr))' }}>
        {metrics.map(({label,value,note,icon:Icon,tone,onClick})=><button type="button" className="stat-card stat-card-button" style={{ display:'block', width:'100%', textAlign:'left', color:'inherit', cursor:'pointer' }} key={label} onClick={onClick}><div className={'stat-icon '+tone}><Icon size={19}/></div><span>{label}</span><strong>{value}</strong><small>{note}</small></button>)}
      </section>
      <section className="dashboard-grid">
        <article className="ui-card">
          <div className="card-head"><div><span className="section-kicker">Pattern activity</span><h2>Recent patterns</h2></div><button className="text-btn" onClick={()=>navigate('/history')}>View library <ArrowRight size={15}/></button></div>
          {patterns.length === 0 ? <EmptyState icon={Scissors} title="No patterns yet" text="Create your first pattern to see its measurements and fabric estimate here." action={()=>navigate('/upload')}/> :
            <div className="pattern-list">{patterns.slice(0,5).map((p,i)=><button type="button" className="pattern-row pattern-row-button" style={{ width:'100%', textAlign:'left', color:'inherit', background:'transparent', border:0, borderBottom:'1px solid var(--border)', cursor:'pointer' }} key={p.pattern_id || i} onClick={()=>navigate('/history')}><div className="pattern-thumb"><Scissors size={17}/></div><div><strong className="capitalize">{p.garment_type || 'Pattern'}</strong><small>{p.yardage_metres > 0 ? `${p.yardage_metres} m` : 'Fabric plan pending'} · {p.pieces_count ?? 0} pattern pieces</small></div><span className="status-badge">Ready</span><small className="date">{p.generated_at ? new Date(p.generated_at).toLocaleDateString('en-GB') : ''}</small></button>)}</div>}
        </article>
        <article className="ui-card">
          <div className="card-head"><div><span className="section-kicker">Material reuse</span><h2>Potential reusable offcuts</h2></div><button className="text-btn" onClick={()=>navigate('/fabric-savings')}>View details <ArrowRight size={15}/></button></div>
          <p className="offcut-explainer">Estimated leftover area from saved nesting layouts. Actual reuse depends on each offcut's shape and size.</p>
          {nestingPatterns.length ? <div className="offcut-list">{nestingPatterns.slice(0,4).map((p)=><button type="button" className="offcut-row" style={{ display:'flex', justifyContent:'space-between', alignItems:'center', gap:12, width:'100%', padding:'12px 0', textAlign:'left', color:'inherit', background:'transparent', border:0, borderBottom:'1px solid var(--border)', cursor:'pointer' }} key={p.pattern_id} onClick={()=>navigate('/fabric-savings')}><span><strong className="capitalize">{p.garment_type || 'Pattern'}</strong><small>{p.selected_fabric_name || 'Fabric not recorded'} · {p.nesting_summary.fabric_width_cm} cm wide</small></span><strong>{(Number(p.nesting_summary.waste_cm2)/10000).toFixed(3)} m²</strong></button>)}</div> : <p className="offcut-empty">No saved nesting breakdowns yet.</p>}
        </article>
      </section>
      <section className="quick-card"><div className="quick-icon"><FileClock size={22}/></div><div><strong>Need a previous drafting guide?</strong><p>Open your pattern library to download or manage completed PDF exports.</p></div><button className="btn btn-outline" onClick={()=>navigate('/history')}>Open library <ArrowRight size={15}/></button></section>
    </div>
  );
}

function EmptyState({icon:Icon,title,text,action}) {
  return <div className="empty-state compact"><span><Icon size={25}/></span><h3>{title}</h3><p>{text}</p><button className="btn btn-outline" onClick={action}><Plus size={15}/> Create pattern</button></div>;
}
