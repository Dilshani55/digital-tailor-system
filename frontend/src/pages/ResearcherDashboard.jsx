import { useState, useEffect } from 'react';
import { Download, Users, Brain, Check, BarChart2, Star } from 'lucide-react';
import { researchAPI } from '../services/api';
import LoadingSpinner from '../components/LoadingSpinner';

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
      setError('Failed to load researcher metrics.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchMetrics();
  }, []);

  const handleExportCSV = () => {
    const token = localStorage.getItem('token');
    // Fetch directly using token authorization header
    fetch(researchAPI.getCSVUrl(), {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    })
    .then(res => res.blob())
    .then(blob => {
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'research_metrics_export.csv';
      document.body.appendChild(a);
      a.click();
      a.remove();
    })
    .catch(() => alert('Failed to download CSV export.'));
  };

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
            Track AI precision scores, dataset correction rates, average fabric waste reductions, and usability ratings.
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
        <div style={{ padding: '12px 16px', background: '#7F1D1D', border: '1px solid #991B1B', borderRadius: '8px', color: '#FECACA', fontSize: '13px', marginBottom: '20px' }}>
          {error}
        </div>
      )}

      {/* Fallback Display if no data available */}
      {(!metrics || !metrics.available) ? (
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
              <small style={{ display: 'block', marginTop: '4px', fontSize: '11px', color: 'var(--text-muted)' }}>Aldrich CAD files calculated</small>
            </div>

            <div className="ui-card" style={{ padding: '20px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>YOLOv8 Accuracy</span>
                <Brain size={16} style={{ color: 'var(--text-accent)' }} />
              </div>
              <strong style={{ fontSize: '28px', color: 'var(--text-primary)' }}>{metrics.ai_accuracy}%</strong>
              <small style={{ display: 'block', marginTop: '4px', fontSize: '11px', color: 'var(--text-muted)' }}>Average prediction confidence</small>
            </div>

            <div className="ui-card" style={{ padding: '20px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>Usability Score</span>
                <div style={{ display: 'flex', alignItems: 'center', gap: '2px', color: '#FBBF24' }}>
                  <Star size={14} fill="#FBBF24" />
                </div>
              </div>
              <strong style={{ fontSize: '28px', color: 'var(--text-primary)' }}>{metrics.usability_score} / 5</strong>
              <small style={{ display: 'block', marginTop: '4px', fontSize: '11px', color: 'var(--text-muted)' }}>Participant survey average</small>
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: '24px' }}>
            
            {/* Precision & Recall statistics card */}
            <div className="ui-card" style={{ padding: '24px' }}>
              <h2 style={{ fontSize: '14px', fontWeight: '600', color: 'var(--text-primary)', marginBottom: '16px' }}>
                AI Model Accuracy & Savings Benchmarks
              </h2>
              
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '16px', textAlign: 'center', borderBottom: '1px solid var(--border)', paddingBottom: '16px', marginBottom: '16px' }}>
                <div style={{ background: 'var(--surface-2)', padding: '12px', borderRadius: '8px' }}>
                  <span style={{ fontSize: '11px', color: 'var(--text-secondary)', display: 'block' }}>Precision</span>
                  <strong style={{ fontSize: '18px', color: 'var(--text-primary)' }}>{metrics.precision}</strong>
                </div>
                <div style={{ background: 'var(--surface-2)', padding: '12px', borderRadius: '8px' }}>
                  <span style={{ fontSize: '11px', color: 'var(--text-secondary)', display: 'block' }}>Recall</span>
                  <strong style={{ fontSize: '18px', color: 'var(--text-primary)' }}>{metrics.recall}</strong>
                </div>
                <div style={{ background: 'var(--surface-2)', padding: '12px', borderRadius: '8px' }}>
                  <span style={{ fontSize: '11px', color: 'var(--text-secondary)', display: 'block' }}>F1-Score</span>
                  <strong style={{ fontSize: '18px', color: 'var(--text-primary)' }}>{metrics.f1_score}</strong>
                </div>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', fontSize: '13px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border)', paddingBottom: '6px' }}>
                  <span style={{ color: 'var(--text-secondary)' }}>Avg. Manual Correction Rate:</span>
                  <strong style={{ color: 'var(--text-primary)' }}>{metrics.avg_correction_rate}%</strong>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border)', paddingBottom: '6px' }}>
                  <span style={{ color: 'var(--text-secondary)' }}>Avg. Fabric Savings per drafting:</span>
                  <strong style={{ color: 'var(--text-accent)' }}>{metrics.avg_fabric_savings} m</strong>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: 'var(--text-secondary)' }}>Avg. processing pipeline time:</span>
                  <strong style={{ color: 'var(--text-primary)' }}>{metrics.avg_processing_time} s</strong>
                </div>
              </div>
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
