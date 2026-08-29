import { Sparkles } from 'lucide-react';

export default function AuthBrandPanel() {
  return (
    <div style={{
      background: 'linear-gradient(135deg, #111111 0%, #1C2E24 100%)',
      padding: '40px',
      color: '#FAF8F5',
      display: 'flex',
      flexDirection: 'column',
      justifyContent: 'space-between',
      position: 'relative',
      overflow: 'hidden'
    }}>
      {/* Background elegant abstract details */}
      <div style={{
        position: 'absolute', top: '-10%', left: '-10%', width: '40%', height: '40%',
        background: 'rgba(42, 111, 78, 0.15)', borderRadius: '50%', filter: 'blur(60px)',
        pointerEvents: 'none'
      }}></div>
      <div style={{
        position: 'absolute', bottom: '-15%', right: '-15%', width: '50%', height: '50%',
        background: 'rgba(45, 90, 67, 0.1)', borderRadius: '50%', filter: 'blur(80px)',
        pointerEvents: 'none'
      }}></div>

      <div>
        <div style={{
          display: 'inline-flex', alignItems: 'center', gap: '6px',
          background: 'rgba(42, 111, 78, 0.15)', border: '1px solid rgba(42, 111, 78, 0.3)',
          color: '#FAF8F5', fontSize: '11px', fontWeight: '700', padding: '6px 14px',
          borderRadius: '20px', marginBottom: '24px', letterSpacing: '0.06em', textTransform: 'uppercase'
        }}>
          <Sparkles size={14}/> TailorAI
        </div>

        <h1 style={{
          fontFamily: "'Playfair Display', serif", fontSize: '38px', fontWeight: '800',
          lineHeight: '1.2', color: '#FAF8F5', marginBottom: '16px', letterSpacing: '-0.02em'
        }}>
          Smart Tailoring, <br />
          <span style={{ color: '#A8C0AF', fontStyle: 'italic' }}>Powered by AI</span>
        </h1>
        <p style={{ fontSize: '14px', color: '#CDC7BD', lineHeight: '1.6', maxWidth: '420px' }}>
          Transform your garment design into personalized tailoring guidance with AI-assisted analysis.
        </p>
      </div>

      {/* Conceptual split visual concept flow diagram (Garment + Measurements -> AI -> Fit + Nesting) */}
      <div style={{ margin: '40px 0', display: 'flex', flexDirection: 'column', gap: '16px' }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr auto 1fr', alignItems: 'center', gap: '10px' }}>
          {/* Input Concept block */}
          <div style={{ background: 'rgba(255, 255, 255, 0.04)', border: '1px solid rgba(255, 255, 255, 0.1)', padding: '14px', borderRadius: '10px' }}>
            <div style={{ fontSize: '12px', fontWeight: '700', color: '#FAF8F5' }}>Garment Design</div>
            <p style={{ fontSize: '10px', color: '#CDC7BD', marginTop: '2px' }}>AI structure & styling curves</p>
          </div>
          <div style={{ fontSize: '14px', color: '#A8C0AF' }}>+</div>
          <div style={{ background: 'rgba(255, 255, 255, 0.04)', border: '1px solid rgba(255, 255, 255, 0.1)', padding: '14px', borderRadius: '10px' }}>
            <div style={{ fontSize: '12px', fontWeight: '700', color: '#FAF8F5' }}>Body Metrics</div>
            <p style={{ fontSize: '10px', color: '#CDC7BD', marginTop: '2px' }}>Centered cm dimensions</p>
          </div>
        </div>

        {/* Processing Indicator */}
        <div style={{ display: 'flex', justifyContent: 'center', padding: '4px 0' }}>
          <div style={{ fontSize: '14px', color: '#2A6F4E' }}>↓</div>
        </div>

        {/* Core AI engine block */}
        <div style={{ background: 'rgba(42, 111, 78, 0.1)', border: '1px solid rgba(42, 111, 78, 0.3)', padding: '14px', borderRadius: '10px', textAlign: 'center' }}>
          <div style={{ fontSize: '13px', fontWeight: '700', color: '#FAF8F5' }}>TailorAI Metric Engine</div>
          <p style={{ fontSize: '10px', color: '#CDC7BD', marginTop: '2px' }}>Aldrich calculations & piece scale formulas</p>
        </div>

        {/* Output processing Indicator */}
        <div style={{ display: 'flex', justifyContent: 'center', padding: '4px 0' }}>
          <div style={{ fontSize: '14px', color: '#2A6F4E' }}>↓</div>
        </div>

        {/* Output Concept block */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr auto 1fr', alignItems: 'center', gap: '10px' }}>
          <div style={{ background: 'rgba(255, 255, 255, 0.04)', border: '1px solid rgba(255, 255, 255, 0.1)', padding: '14px', borderRadius: '10px' }}>
            <div style={{ fontSize: '12px', fontWeight: '700', color: '#FAF8F5' }}>Personalized Fit</div>
            <p style={{ fontSize: '10px', color: '#CDC7BD', marginTop: '2px' }}>Custom bodice block draft</p>
          </div>
          <div style={{ fontSize: '14px', color: '#A8C0AF' }}>+</div>
          <div style={{ background: 'rgba(255, 255, 255, 0.04)', border: '1px solid rgba(255, 255, 255, 0.1)', padding: '14px', borderRadius: '10px' }}>
            <div style={{ fontSize: '12px', fontWeight: '700', color: '#FAF8F5' }}>Fabric Planning</div>
            <p style={{ fontSize: '10px', color: '#CDC7BD', marginTop: '2px' }}>Waste reduction nesting map</p>
          </div>
        </div>
      </div>

      <div style={{ fontSize: '11px', color: '#CDC7BD', paddingTop: '16px', borderTop: '1px solid rgba(255,255,255,0.08)' }}>
        Software Engineering Research Project · NSBM Green University
      </div>
    </div>
  );
}
