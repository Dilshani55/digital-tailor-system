import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Download } from 'lucide-react';
import PatternPreview from '../components/PatternPreview';
import LoadingSpinner from '../components/LoadingSpinner';
import { patternsAPI, exportAPI } from '../services/api';
import { friendlyError } from '../utils/friendlyError';
import { formatResult } from '../utils/results';

const label = (v) => (v ? String(v).replace(/-/g, ' ').replace(/^./, (c) => c.toUpperCase()) : 'Not available');

/** A saved pattern, opened again from the pattern library: geometry, fabric estimate and PDFs. */
export default function PatternDetail() {
  const { patternId } = useParams();
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    patternsAPI.getOne(patternId)
      .then((r) => setData(r.data))
      .catch((e) => setError(friendlyError(e, 'This pattern could not be loaded.')))
      .finally(() => setLoading(false));
  }, [patternId]);

  const download = async (exportId) => {
    try {
      const r = await exportAPI.download(exportId);
      const url = URL.createObjectURL(new Blob([r.data], { type: 'application/pdf' }));
      const a = document.createElement('a');
      a.href = url;
      a.download = `sewing_pattern_${patternId}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError(friendlyError(e, 'The download failed. Please try again.'));
    }
  };

  if (loading) return <LoadingSpinner message="Loading your pattern…" />;
  const n = data?.nesting_summary || {};
  const a = data?.design_attributes || {};
  return (
    <div className="page">
      <section className="page-heading">
        <div>
          <span className="section-kicker">Saved pattern</span>
          <h1>{label(data?.garment_type)} pattern</h1>
          <p>
            {[a.neckline_type, a.sleeve_length].filter(Boolean).map(label).join(' · ') || 'Design details not available'}
            {' · '}{data?.selected_fabric_name || 'Fabric not available'}
          </p>
        </div>
        <button type="button" className="btn btn-outline" onClick={() => navigate('/history')}>Back to library</button>
      </section>
      {error && <div role="alert" className="alert error dashboard-error">{error}</div>}
      {data && (
        <>
          <div className="result-grid" style={{ marginBottom: '16px' }}>
            <div className="result-tile"><div className="r-val">{formatResult(n.purchasing_recommended_m, ' m')}</div><div className="r-lbl">Recommended purchase</div></div>
            <div className="result-tile"><div className="r-val">{formatResult(n.fabric_width_cm, ' cm')}</div><div className="r-lbl">Fabric width</div></div>
            <div className="result-tile"><div className="r-val">{formatResult(n.utilisation_percent, '%')}</div><div className="r-lbl">Fabric used by pieces</div></div>
          </div>
          <section className="ui-card" style={{ padding: '18px' }}>
            <PatternPreview pieces={data.pattern_pieces} validation={data.validation} />
          </section>
          <section className="ui-card" style={{ padding: '18px', marginTop: '14px' }}>
            <h2 style={{ fontSize: '14px', marginBottom: '8px' }}>Printable PDFs</h2>
            {(data.exports || []).length === 0
              ? <p style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>No PDF has been created for this pattern yet.</p>
              : data.exports.map((e) => (
                <button type="button" key={e.export_id} className="btn btn-outline" style={{ marginRight: '8px' }} onClick={() => download(e.export_id)}>
                  <Download size={15} /> Download {new Date(e.exported_at).toLocaleDateString('en-GB')}
                </button>
              ))}
          </section>
        </>
      )}
    </div>
  );
}
