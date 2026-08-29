export default function AuthLayout({ children, brandPanel }) {
  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      flexDirection: 'column',
      background: 'var(--surface-0)'
    }}>
      {/* SIMPLE COMPACT HEADER NAVIGATION */}
      <header style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        padding: '16px 40px',
        borderBottom: '1px solid var(--border)',
        background: 'var(--surface-0)'
      }}>
        <div style={{ fontSize: '20px', fontWeight: 'bold', fontFamily: "'Playfair Display', serif", display: 'flex', alignItems: 'center', gap: '6px' }}>
          <span style={{ color: 'var(--text-accent)' }}>✧</span> TailorAI
        </div>
        <a
          href="/"
          style={{
            fontSize: '13px',
            color: 'var(--text-secondary)',
            textDecoration: 'none',
            fontWeight: '600',
            border: '1px solid var(--border)',
            padding: '6px 16px',
            borderRadius: '20px',
            transition: 'all 0.15s ease'
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.borderColor = 'var(--text-accent)';
            e.currentTarget.style.color = 'var(--text-accent)';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.borderColor = 'var(--border)';
            e.currentTarget.style.color = 'var(--text-secondary)';
          }}
        >
          Back to Home
        </a>
      </header>

      {/* CORE SPLIT SCREEN AREA */}
      <div style={{
        flex: 1,
        display: 'grid',
        gridTemplateColumns: 'minmax(350px, 1fr) 1.2fr',
        maxWidth: '1200px',
        width: '100%',
        margin: '0 auto',
        padding: '30px 40px 60px',
        gap: '40px'
      }} className="auth-grid-container">
        {/* LEFT BRANDING PANEL */}
        <div style={{
          borderRadius: '16px',
          overflow: 'hidden',
          display: 'flex',
          boxShadow: '0 8px 30px rgba(92, 88, 80, 0.06)',
          border: '1px solid var(--border)',
          minHeight: '520px'
        }} className="auth-brand-wrapper">
          {brandPanel}
        </div>

        {/* RIGHT FORM CONTAINER */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center'
        }}>
          <div style={{
            background: '#FFFFFF',
            border: '1px solid var(--border)',
            borderRadius: '16px',
            padding: '40px',
            width: '100%',
            maxWidth: '480px',
            boxShadow: '0 20px 40px -10px rgba(92, 88, 80, 0.08)'
          }}>
            {children}
          </div>
        </div>
      </div>

      {/* Responsive mobile stack stylesheet injector */}
      <style>{`
        @media (max-width: 868px) {
          .auth-grid-container {
            grid-template-columns: 1fr !important;
            gap: 24px !important;
            padding: 20px 16px !important;
          }
          .auth-brand-wrapper {
            min-height: auto !important;
            padding: 24px !important;
          }
        }
      `}</style>
    </div>
  );
}
