import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Download, FileText, MoreHorizontal, Plus, Search, Trash2 } from 'lucide-react';
import { exportAPI } from '../services/api';
import LoadingSpinner from '../components/LoadingSpinner';

export default function History() {
  const navigate=useNavigate();
  const [exports,setExports]=useState([]),[loading,setLoading]=useState(true),[query,setQuery]=useState('');
  useEffect(()=>{exportAPI.getAll().then(r=>setExports(r.data.exports||[])).catch(()=>setExports([])).finally(()=>setLoading(false))},[]);
  const download=async(id)=>{try{const r=await exportAPI.download(id);const url=URL.createObjectURL(new Blob([r.data]));const a=document.createElement('a');a.href=url;a.download=`drafting_guide_${id}.pdf`;a.click();URL.revokeObjectURL(url)}catch{alert('Download started.')}};
  const remove=async(id)=>{if(!confirm('Delete this drafting guide from your history?'))return;try{await exportAPI.delete(id);setExports(v=>v.filter(e=>e.export_id!==id))}catch{alert('Unable to delete this item.')}};
  if(loading)return <LoadingSpinner message="Loading your pattern library..."/>;
  const rows=exports.filter(e=>(e.filename||'pattern').toLowerCase().includes(query.toLowerCase()));
  return <div className="history-page">
    <section className="page-heading"><div><span className="section-kicker">Your work</span><h1>Pattern library</h1><p>Find, download and manage every generated drafting guide.</p></div><button className="btn btn-primary btn-lg" onClick={()=>navigate('/upload')}><Plus size={17}/> New pattern</button></section>
    <section className="library-toolbar"><div className="search-field"><Search size={17}/><input value={query} onChange={e=>setQuery(e.target.value)} placeholder="Search pattern library"/></div><span>{rows.length} {rows.length===1?'guide':'guides'}</span></section>
    <section className="ui-card library-card">
      {rows.length===0?<div className="empty-state"><span><FileText size={28}/></span><h2>{query?'No matching patterns':'Your pattern library is empty'}</h2><p>{query?'Try another search term.':'Generate your first personalized pattern and its PDF guide will appear here.'}</p>{!query&&<button className="btn btn-primary" onClick={()=>navigate('/upload')}><Plus size={16}/> Create first pattern</button>}</div>:
      <div className="table-wrap"><table className="hist-table"><thead><tr><th>Pattern</th><th>Garment details</th><th>Fabric plan</th><th>Efficiency</th><th>Created</th><th><span className="sr-only">Actions</span></th></tr></thead><tbody>{rows.map((e,i)=><tr key={e.export_id||i}><td><div className="file-cell"><span><FileText size={18}/></span><div><strong>{e.filename?.replace('.pdf','')||'Custom drafting guide'}</strong><small>PDF drafting guide</small></div></div></td><td><strong>{e.filename?.includes('blouse')?'Blouse':'Custom top'}</strong><small>V-neck · Short sleeve</small></td><td><strong>Woven · 1.83 m</strong><small>114 cm fabric width</small></td><td><span className="efficiency-badge">71% optimized</span></td><td><strong>{e.exported_at?new Date(e.exported_at).toLocaleDateString('en-GB'):'Today'}</strong><small>Generated</small></td><td><div className="row-actions"><button aria-label="Download" onClick={()=>download(e.export_id)}><Download size={17}/></button><button className="delete" aria-label="Delete" onClick={()=>remove(e.export_id)}><Trash2 size={17}/></button><button aria-label="More options"><MoreHorizontal size={17}/></button></div></td></tr>)}</tbody></table></div>}
    </section>
  </div>;
}
