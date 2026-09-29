import { useState, useEffect } from 'react';
import { Download, Users, Brain, Check, BarChart2, Star } from 'lucide-react';
import { researchAPI } from '../services/api';
import LoadingSpinner from '../components/LoadingSpinner';

// Research integrity: a missing value is shown as "Not measured", never a substitute number.
const NOT_MEASURED = 'Not measured';
const fmtNum = (v, digits = 1, suffix = '') =>
  (v === null || v === undefined || Number.isNaN(Number(v))) ? NOT_MEASURED : `${Number(v).toFixed(digits)}${suffix}`;
const fmtPct = (v) => fmtNum(v === null || v === undefined ? v : Number(v) * 100, 1, '%');

export default function ResearcherDashboard() {
  const [metrics, setMetrics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const fetchMetrics = async () => {
    setLoading(true);
    try {
      const res = await researchAPI.getMetrics();
      setMetrics(res.data);
    } catch (err) {
      setError(err.response?.status === 403
        ? 'Study-wide research data is only available to researcher accounts. Ask the administrator to add your e-mail to RESEARCHER_EMAILS.'
        : 'Failed to load researcher metrics.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchMetrics();
  }, []);

  const downloadCsv = (csvUrl, filename) => {
    const token = localStorage.getItem('token');
    fetch(csvUrl, { headers: { Authorization: `Bearer ${token}` } })
      .then((res) => {
        // fetch does not reject on HTTP errors: never save an error body as the "CSV"
        if (!res.ok) throw Object.assign(new Error('http'), { status: res.status });
        return res.blob();
      })
      .then((blob) => {
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        a.remove();
        window.URL.revokeObjectURL(url);
      })
      .catch((e) => alert(e.status === 403 ? 'Only researcher accounts can export study data.' : 'Failed to download the CSV export.'));
  };
  const handleExportCSV = () => downloadCsv(researchAPI.getCSVUrl(), 'research_metrics_export.csv');

  if (loading) return <LoadingSpinner message="Querying study datasets..." />;

  return (
    <div style={{ padding: '24px', maxWidth: '1200px', margin: '0 auto' }}>
      
      {/* Header Info */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <h1 style={{ fontSize: '22px', fontWeight: '700', color: 'var(--text-primary)', marginBottom: '4px' }}>
            Researcher & Admin Dashboard
          </h1>
          <p style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>
            Classifier test metrics, AI correction rates, measured processing times, traditional-vs-system fabric comparisons and usability ratings — only values that were actually measured.
          </p>
        </div>
        
        {metrics?.available && (
          <button 
            onClick={handleExportCSV} 
            className="btn btn-primary"
            style={{ background: 'var(--text-accent)', display: 'flex', alignItems: 'center', gap: '6px' }}
          >
            <Download size={16}/> Export study data (CSV)
          </button>
        )}
      </div>

      {error && (
        <div role="alert" style={{ padding: '12px 16px', background: '#FEF2F2', border: '1px solid #FCA5A5', borderRadius: '8px', color: '#991B1B', fontSize: '13px', marginBottom: '20px' }}>
          {error}
        </div>
      )}

      {/* Fallback Display if no data available */}
      {error ? null : (!metrics || !metrics.available) ? (
        <div style={{ 
          background: 'var(--surface-1)', border: '1px dashed var(--border-strong)', 
          borderRadius: '12px', padding: '60px 40px', textAlign: 'center', 
          marginTop: '20px', maxWidth: '600px', margin: '40px auto' 
        }}>
          <Users size={48} style={{ color: 'var(--text-muted)', marginBottom: '16px' }} />
          <h2 style={{ fontSize: '18px', fontWeight: '600', color: 'var(--text-primary)', marginBottom: '8px' }}>
            No research data available
          </h2>
          <p style={{ fontSize: '13px', color: 'var(--text-secondary)', lineHeight: '1.5', margin: 0 }}>
            There are currently no usability records or participant metrics stored in the system. 
            Once study participants generate pattern drafting layouts and submit feedback scores, 
            aggregated statistical analytics will populate here.
          </p>
        </div>
      ) : (
        /* Research Metrics populating */
        <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
          
          {/* Summary Cards Row */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '16px' }}>
            <div className="ui-card" style={{ padding: '20px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>Total Participants</span>
                <Users size={16} style={{ color: 'var(--text-accent)' }} />
              </div>
              <strong style={{ fontSize: '28px', color: 'var(--text-primary)' }}>{metrics.total_participants}</strong>
              <small style={{ display: 'block', marginTop: '4px', fontSize: '11px', color: 'var(--text-muted)' }}>Registered study profiles</small>
            </div>

            <div className="ui-card" style={{ padding: '20px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>Generated Patterns</span>
                <BarChart2 size={16} style={{ color: 'var(--text-accent)' }} />
              </div>
              <strong style={{ fontSize: '28px', color: 'var(--text-primary)' }}>{metrics.total_patterns}</strong>
              <small style={{ display: 'block', marginTop: '4px', fontSize: '11px', color: 'var(--text-muted)' }}>Patterns generated</small>
            </div>

            <div className="ui-card" style={{ padding: '20px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>Garment-type accuracy (test split)</span>
                <Brain size={16} style={{ color: 'var(--text-accent)' }} />
              </div>
              <strong style={{ fontSize: '28px', color: 'var(--text-primary)' }}>{fmtPct(metrics.model_evaluation?.per_head?.garment_type?.accuracy)}</strong>
              <small style={{ display: 'block', marginTop: '4px', fontSize: '11px', color: 'var(--text-muted)' }}>Image-level classifier, held-out test split (training log)</small>
            </div>

            <div className="ui-card" style={{ padding: '20px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>Usability Score</span>
                <div style={{ display: 'flex', alignItems: 'center', gap: '2px', color: '#FBBF24' }}>
                  <Star size={14} fill="#FBBF24" />
                </div>
              </div>
              <strong style={{ fontSize: '28px', color: 'var(--text-primary)' }}>{metrics.usability_score == null ? NOT_MEASURED : `${metrics.usability_score} / 5`}</strong>
              <small style={{ display: 'block', marginTop: '4px', fontSize: '11px', color: 'var(--text-muted)' }}>Participant survey average</small>
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: '24px' }}>
            
            {/* Precision & Recall statistics card */}
            <div className="ui-card" style={{ padding: '24px' }}>
              <h2 style={{ fontSize: '14px', fontWeight: '600', color: 'var(--text-primary)', marginBottom: '16px' }}>
                Classifier test metrics (garment type) & measured study values
              </h2>
              
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '16px', textAlign: 'center', borderBottom: '1px solid var(--border)', paddingBottom: '16px', marginBottom: '16px' }}>
                <div style={{ background: 'var(--surface-2)', padding: '12px', borderRadius: '8px' }}>
                  <span style={{ fontSize: '11px', color: 'var(--text-secondary)', display: 'block' }}>Macro precision</span>
                  <strong style={{ fontSize: '18px', color: 'var(--text-primary)' }}>{fmtNum(metrics.model_evaluation?.per_head?.garment_type?.macro_precision, 3)}</strong>
                </div>
                <div style={{ background: 'var(--surface-2)', padding: '12px', borderRadius: '8px' }}>
                  <span style={{ fontSize: '11px', color: 'var(--text-secondary)', display: 'block' }}>Macro recall</span>
                  <strong style={{ fontSize: '18px', color: 'var(--text-primary)' }}>{fmtNum(metrics.model_evaluation?.per_head?.garment_type?.macro_recall, 3)}</strong>
                </div>
                <div style={{ background: 'var(--surface-2)', padding: '12px', borderRadius: '8px' }}>
                  <span style={{ fontSize: '11px', color: 'var(--text-secondary)', display: 'block' }}>Macro F1</span>
                  <strong style={{ fontSize: '18px', color: 'var(--text-primary)' }}>{fmtNum(metrics.model_evaluation?.per_head?.garment_type?.macro_f1, 3)}</strong>
                </div>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', fontSize: '13px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border)', paddingBottom: '6px' }}>
                  <span style={{ color: 'var(--text-secondary)' }}>Avg. Manual Correction Rate:</span>
                  <strong style={{ color: 'var(--text-primary)' }}>{fmtNum(metrics.avg_correction_rate, 1, '%')}</strong>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border)', paddingBottom: '6px' }}>
                  <span style={{ color: 'var(--text-secondary)' }}>Avg. Fabric Savings per drafting:</span>
                  <strong style={{ color: 'var(--text-accent)' }}>{fmtNum(metrics.avg_fabric_savings, 2, ' m')}</strong>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: 'var(--text-secondary)' }}>Avg. processing pipeline time:</span>
                  <strong style={{ color: 'var(--text-primary)' }}>{fmtNum(metrics.avg_processing_time, 2, ' s')}</strong>
                </div>
              </div>
            </div>

            {/* Traditional vs system fabric estimate (entered comparisons only) */}
            <div className="ui-card" style={{ padding: '24px', gridColumn: '1 / -1' }} data-testid="fabric-comparison-summary">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '12px', flexWrap: 'wrap', marginBottom: '12px' }}>
                <h2 style={{ fontSize: '14px', fontWeight: '600', color: 'var(--text-primary)', margin: 0 }}>
                  Traditional vs system fabric estimate
                </h2>
                {metrics.fabric_comparison && (
                  <button type="button" className="btn btn-outline" onClick={() => downloadCsv(researchAPI.getComparisonCSVUrl(), 'fabric_comparisons.csv')}>
                    <Download size={15}/> Comparison data (CSV)
                  </button>
                )}
              </div>
              {!metrics.fabric_comparison ? (
                <p style={{ fontSize: '13px', color: 'var(--text-secondary)', margin: 0 }}>
                  {NOT_MEASURED} — no traditional estimate has been recorded yet. Estimates are entered on a saved pattern’s page.
                </p>
              ) : (
                <>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '12px', textAlign: 'center' }}>
                    {[
                      ['Comparisons (patterns)', `${metrics.fabric_comparison.n} (${metrics.fabric_comparison.patterns})`],
                      ['Mean difference', fmtNum(metrics.fabric_comparison.mean_difference_m, 3, ' m')],
                      ['Median difference', fmtNum(metrics.fabric_comparison.median_difference_m, 3, ' m')],
                      ['SD of difference', fmtNum(metrics.fabric_comparison.sd_difference_m, 3, ' m')],
                      ['Mean relative difference', fmtNum(metrics.fabric_comparison.mean_relative_difference_percent, 1, '%')],
                      ['System lower / higher / equal', `${metrics.fabric_comparison.system_lower_count} / ${metrics.fabric_comparison.system_higher_count} / ${metrics.fabric_comparison.equal_count}`],
                    ].map(([label, value]) => (
                      <div key={label} style={{ background: 'var(--surface-2)', padding: '12px', borderRadius: '8px' }}>
                        <span style={{ fontSize: '11px', color: 'var(--text-secondary)', display: 'block' }}>{label}</span>
                        <strong style={{ fontSize: '16px', color: 'var(--text-primary)' }}>{value}</strong>
                      </div>
                    ))}
                  </div>
                  <p style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '10px', lineHeight: 1.5 }}>
                    {metrics.fabric_comparison.definition}. {metrics.fabric_comparison.note}
                  </p>
                </>
              )}
            </div>

            {/* Participant Usability Feedback card */}
            <div className="ui-card" style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '14px' }}>
              <h2 style={{ fontSize: '14px', fontWeight: '600', color: 'var(--text-primary)', margin: 0 }}>
                Participant feedback comments
              </h2>
              
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', maxHeight: '250px', overflowY: 'auto', paddingRight: '4px' }}>
                {metrics.feedbacks?.map((f, idx) => (
                  <div key={idx} style={{ borderBottom: '1px solid var(--border)', paddingBottom: '10px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                      <strong style={{ fontSize: '12px', color: 'var(--text-primary)' }}>{f.participant}</strong>
                      <div style={{ display: 'flex', gap: '2px', color: '#FBBF24' }}>
                        {[...Array(f.score)].map((_, i) => <Star key={i} size={10} fill="#FBBF24" stroke="none" />)}
                      </div>
                    </div>
                    <p style={{ margin: 0, fontSize: '11px', color: 'var(--text-secondary)', lineHeight: '1.4' }}>
                      "{f.comment}"
                    </p>
                    <small style={{ fontSize: '9px', color: 'var(--text-muted)', display: 'block', marginTop: '2px' }}>{f.date}</small>
                  </div>
                ))}
              </div>
            </div>

          </div>
        </div>
      )}

    </div>
  );
}
