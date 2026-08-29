export default function AuthTabs({ activeTab, onTabChange }) {
  return (
    <div style={{
      display: 'flex',
      background: 'var(--surface-2)',
      padding: '4px',
      borderRadius: '8px',
      marginBottom: '24px'
    }}>
      <button
        type="button"
        onClick={() => onTabChange('login')}
        style={{
          flex: 1,
          padding: '10px 0',
          fontSize: '13px',
          fontWeight: '600',
          borderRadius: '6px',
          border: 'none',
          cursor: 'pointer',
          background: activeTab === 'login' ? '#FFFFFF' : 'transparent',
          color: activeTab === 'login' ? 'var(--text-primary)' : 'var(--text-secondary)',
          transition: 'all 0.2s ease',
          fontFamily: "'Plus Jakarta Sans', sans-serif"
        }}
      >
        Login
      </button>
      <button
        type="button"
        onClick={() => onTabChange('register')}
        style={{
          flex: 1,
          padding: '10px 0',
          fontSize: '13px',
          fontWeight: '600',
          borderRadius: '6px',
          border: 'none',
          cursor: 'pointer',
          background: activeTab === 'register' ? '#FFFFFF' : 'transparent',
          color: activeTab === 'register' ? 'var(--text-primary)' : 'var(--text-secondary)',
          transition: 'all 0.2s ease',
          fontFamily: "'Plus Jakarta Sans', sans-serif"
        }}
      >
        Create Account
      </button>
    </div>
  );
}
