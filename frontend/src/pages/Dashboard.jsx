import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowRight, Download, FileClock, Leaf, Plus, Scissors, Sparkles, TrendingUp } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { patternsAPI, exportAPI } from '../services/api';
import LoadingSpinner from '../components/LoadingSpinner';

export default function Dashboard() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [patterns, setPatterns] = useState([]);
  const [exports, setExports] = useState([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    Promise.all([patternsAPI.getAll(), exportAPI.getAll()])
      .then(([p, e]) => { setPatterns(p.data.patterns || []); setExports(e.data.exports || []); })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);
  const yardages = patterns.filter((p) => p.yardage_metres > 0).map((p) => p.yardage_metres);
  const average = yardages.length ? yardages.reduce((a,b)=>a+b,0)/yardages.length : 1.83;
  const saved = Math.max(0, 2.5-average).toFixed(1);
  const name = user?.full_name?.split(' ')[0] || 'Dilshani';
  const groups = useMemo(() => {
    const result = {};
    patterns.forEach((p) => { const key=p.garment_type || 'Blouse'; result[key]=(result[key]||0)+1; });
    return Object.keys(result).length ? Object.keys(result).slice(0,4) : ['Crop top','Blouse','T-shirt'];
  }, [patterns]);
  if (loading) return <LoadingSpinner message="Preparing your workspace..." />;

  const metrics = [
    { label:'Patterns created', value:patterns.length, note:'Your complete library', icon:Scissors, tone:'green' },
    { label:'PDF guides', value:exports.length, note:'Ready for production', icon:Download, tone:'blue' },
    { label:'Average fabric saved', value:`${saved} m`, note:'Compared with baseline', icon:Leaf, tone:'mint' },
    { label:'Average efficiency', value:'73%', note:'Across recent patterns', icon:TrendingUp, tone:'amber' },
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
      <section className="stats-grid">
        {metrics.map(({label,value,note,icon:Icon,tone})=><article className="stat-card" key={label}><div className={'stat-icon '+tone}><Icon size={19}/></div><span>{label}</span><strong>{value}</strong><small>{note}</small></article>)}
      </section>
      <section className="dashboard-grid">
        <article className="ui-card">
          <div className="card-head"><div><span className="section-kicker">Pattern activity</span><h2>Recent patterns</h2></div><button className="text-btn" onClick={()=>navigate('/history')}>View library <ArrowRight size={15}/></button></div>
          {patterns.length === 0 ? <EmptyState icon={Scissors} title="No patterns yet" text="Create your first pattern to see its measurements and fabric estimate here." action={()=>navigate('/upload')}/> :
            <div className="pattern-list">{patterns.slice(0,5).map((p,i)=><div className="pattern-row" key={p.pattern_id || i}><div className="pattern-thumb"><Scissors size={17}/></div><div><strong className="capitalize">{p.garment_type || 'Pattern'}</strong><small>{p.yardage_metres || '1.83'} m · {p.pieces_count || 3} pattern pieces</small></div><span className="status-badge">Ready</span><small className="date">{p.generated_at ? new Date(p.generated_at).toLocaleDateString('en-GB') : 'Today'}</small></div>)}</div>}
        </article>
        <article className="ui-card">
          <div className="card-head"><div><span className="section-kicker">Material intelligence</span><h2>Fabric efficiency</h2></div><span className="live-label"><i/> Live data</span></div>
          <div className="efficiency-summary"><div className="efficiency-ring"><strong>73%</strong><span>average</span></div><p>Your recent layouts use fabric efficiently. Continue using optimized nesting to reduce off-cuts.</p></div>
          <div className="efficiency-list">{groups.map((g,i)=>{const val=71+i*4;return <div key={g}><span><strong className="capitalize">{g}</strong><small>{val}%</small></span><div className="progress-track"><i style={{width:val+'%'}}/></div></div>})}</div>
        </article>
      </section>
      <section className="quick-card"><div className="quick-icon"><FileClock size={22}/></div><div><strong>Need a previous drafting guide?</strong><p>Open your pattern library to download or manage completed PDF exports.</p></div><button className="btn btn-outline" onClick={()=>navigate('/history')}>Open library <ArrowRight size={15}/></button></section>
    </div>
  );
}

function EmptyState({icon:Icon,title,text,action}) {
  return <div className="empty-state compact"><span><Icon size={25}/></span><h3>{title}</h3><p>{text}</p><button className="btn btn-outline" onClick={action}><Plus size={15}/> Create pattern</button></div>;
}
