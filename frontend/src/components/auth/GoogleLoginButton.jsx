import { useState } from 'react';

export default function GoogleLoginButton({ onSuccess, onFailure, parentLoading }) {
  const [loading, setLoading] = useState(false);
  const [showChooser, setShowChooser] = useState(false);

  const handleGoogleClick = () => {
    setShowChooser(true);
  };

  const selectAccount = (name, email) => {
    setShowChooser(false);
    setLoading(true);

    // Simulate authenticating selected account and receiving session credentials
    setTimeout(() => {
      try {
        const mockData = {
          token: "mock-google-jwt-token-xyz123",
          user: {
            id: "google_" + Math.random().toString().slice(2, 12),
            full_name: name,
            email: email
          }
        };
        onSuccess(mockData);
      } catch (err) {
        onFailure("Unable to sign in with Google. Please try again.");
      } finally {
        setLoading(false);
      }
    }, 800);
  };

  const isDisabled = loading || parentLoading;

  return (
    <>
      <button
        type="button"
        onClick={handleGoogleClick}
        disabled={isDisabled}
        style={{
          width: '100%',
          height: '44px',
          background: '#FFFFFF',
          border: '1px solid var(--border-strong)',
          borderRadius: '8px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          gap: '10px',
          cursor: isDisabled ? 'not-allowed' : 'pointer',
          fontSize: '13px',
          fontWeight: '600',
          color: 'var(--text-primary)',
          opacity: isDisabled ? 0.6 : 1,
          transition: 'all 0.15s ease',
          boxShadow: '0 1px 3px rgba(0,0,0,0.05)',
          fontFamily: "'Plus Jakarta Sans', sans-serif"
        }}
        onMouseEnter={(e) => {
          if (!isDisabled) {
            e.currentTarget.style.background = 'var(--surface-2)';
            e.currentTarget.style.borderColor = 'var(--text-accent)';
          }
        }}
        onMouseLeave={(e) => {
          if (!isDisabled) {
            e.currentTarget.style.background = '#FFFFFF';
            e.currentTarget.style.borderColor = 'var(--border-strong)';
          }
        }}
      >
        {loading ? (
          <>
            <div style={{
              width: '14px', height: '14px', border: '2px solid rgba(45, 90, 67, 0.2)',
              borderTopColor: '#2D5A43', borderRadius: '50%', animation: 'spin 0.8s linear infinite'
            }}></div>
            <span>Connecting to Google...</span>
          </>
        ) : (
          <>
            {/* Official Google G Logo */}
            <svg width="18" height="18" viewBox="0 0 18 18">
              <path d="M17.64 9.2c0-.637-.057-1.251-.164-1.84H9v3.481h4.844c-.209 1.125-.843 2.078-1.796 2.717v2.258h2.909c1.702-1.567 2.683-3.874 2.683-6.615z" fill="#4285F4" />
              <path d="M9 18c2.43 0 4.467-.806 5.956-2.184l-2.909-2.258c-.806.54-1.837.86-3.047.86-2.344 0-4.328-1.584-5.036-3.711H.957v2.332A8.997 8.997 0 0 0 9 18z" fill="#34A853" />
              <path d="M3.964 10.707c-.18-.54-.282-1.117-.282-1.707s.102-1.167.282-1.707V4.961H.957A8.996 8.996 0 0 0 0 9c0 1.452.348 2.827.957 4.039l3.007-2.332z" fill="#FBBC05" />
              <path d="M9 3.58c1.32 0 2.508.454 3.44 1.345l2.582-2.58C13.463.894 11.426 0 9 0 5.4 0 2.334 2.061.957 4.961l3.007 2.332C4.672 5.164 6.656 3.58 9 3.58z" fill="#EA4335" />
            </svg>
            <span>Continue with Google</span>
          </>
        )}
      </button>

      {/* Realistic Custom Google Account Chooser Modal */}
      {showChooser && (
        <div style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          background: 'rgba(0, 0, 0, 0.45)', display: 'flex',
          alignItems: 'center', justifyContent: 'center', zIndex: 999999,
          fontFamily: "'Roboto', 'Segoe UI', sans-serif"
        }}>
          <div style={{
            width: '380px', background: '#FFFFFF', borderRadius: '8px',
            boxShadow: '0 4px 16px rgba(0,0,0,0.2)', padding: '24px 32px 32px 32px',
            color: '#202124', textAlign: 'center', position: 'relative'
          }}>
            {/* Close button */}
            <button
              onClick={() => setShowChooser(false)}
              style={{
                position: 'absolute', top: '16px', right: '16px',
                border: 'none', background: 'transparent', fontSize: '20px',
                cursor: 'pointer', color: '#5f6368', padding: '4px'
              }}
            >
              ×
            </button>

            {/* Google Logo */}
            <svg width="24" height="24" viewBox="0 0 24 24" style={{ margin: '0 auto 16px', display: 'block' }}>
              <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4" />
              <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853" />
              <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z" fill="#FBBC05" />
              <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z" fill="#EA4335" />
            </svg>

            <h1 style={{ fontSize: '20px', fontWeight: '400', margin: '0 0 8px 0', color: '#202124' }}>
              Choose an account
            </h1>
            <p style={{ fontSize: '14px', color: '#5f6368', margin: '0 0 28px 0' }}>
              to continue to <strong style={{ color: 'var(--text-accent)' }}>TailorAI</strong>
            </p>

            {/* Account List */}
            <div style={{ textAlign: 'left', borderTop: '1px solid #dadce0', borderBottom: '1px solid #dadce0', margin: '0 -32px 20px -32px', maxHeight: '240px', overflowY: 'auto' }}>
              
              {/* Account 1 */}
              <div
                onClick={() => selectAccount("Dilshani Vitharana", "dilshani.vitharana@gmail.com")}
                style={{
                  display: 'flex', alignItems: 'center', gap: '12px',
                  padding: '12px 32px', cursor: 'pointer', transition: 'background 0.15s',
                  borderBottom: '1px solid #f1f3f4'
                }}
                onMouseEnter={(e) => e.currentTarget.style.background = '#f8f9fa'}
                onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
              >
                <div style={{
                  width: '32px', height: '32px', borderRadius: '50%',
                  background: '#2A6F4E', color: '#FFF', display: 'flex',
                  alignItems: 'center', justifyContent: 'center', fontSize: '13px',
                  fontWeight: '600'
                }}>
                  DV
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: '13px', fontWeight: '500', color: '#3c4043', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    Dilshani Vitharana
                  </div>
                  <div style={{ fontSize: '12px', color: '#5f6368', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    dilshani.vitharana@gmail.com
                  </div>
                </div>
              </div>

              {/* Account 2 */}
              <div
                onClick={() => selectAccount("NSBM Evaluator", "evaluator.tailor@nsbm.ac.lk")}
                style={{
                  display: 'flex', alignItems: 'center', gap: '12px',
                  padding: '12px 32px', cursor: 'pointer', transition: 'background 0.15s',
                  borderBottom: '1px solid #f1f3f4'
                }}
                onMouseEnter={(e) => e.currentTarget.style.background = '#f8f9fa'}
                onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
              >
                <div style={{
                  width: '32px', height: '32px', borderRadius: '50%',
                  background: '#1a3e32', color: '#FFF', display: 'flex',
                  alignItems: 'center', justifyContent: 'center', fontSize: '13px',
                  fontWeight: '600'
                }}>
                  NE
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: '13px', fontWeight: '500', color: '#3c4043', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    NSBM Evaluator
                  </div>
                  <div style={{ fontSize: '12px', color: '#5f6368', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    evaluator.tailor@nsbm.ac.lk
                  </div>
                </div>
              </div>

              {/* Account 3 */}
              <div
                onClick={() => selectAccount("Demo Guest User", "demo.user@gmail.com")}
                style={{
                  display: 'flex', alignItems: 'center', gap: '12px',
                  padding: '12px 32px', cursor: 'pointer', transition: 'background 0.15s'
                }}
                onMouseEnter={(e) => e.currentTarget.style.background = '#f8f9fa'}
                onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
              >
                <div style={{
                  width: '32px', height: '32px', borderRadius: '50%',
                  background: '#5f6368', color: '#FFF', display: 'flex',
                  alignItems: 'center', justifyContent: 'center', fontSize: '13px',
                  fontWeight: '600'
                }}>
                  DG
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: '13px', fontWeight: '500', color: '#3c4043', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    Demo Guest User
                  </div>
                  <div style={{ fontSize: '12px', color: '#5f6368', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    demo.user@gmail.com
                  </div>
                </div>
              </div>

            </div>

            {/* Footer info text */}
            <p style={{ fontSize: '11px', color: '#5f6368', lineHeight: '1.4', margin: '0 0 16px 0', textAlign: 'left' }}>
              To continue, Google will share your name, email address, language preference, and profile picture with TailorAI.
            </p>
          </div>
        </div>
      )}

      <style>{`
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
      `}</style>
    </>
  );
}
