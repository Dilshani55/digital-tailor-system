import { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import AuthLayout from '../components/auth/AuthLayout';
import AuthBrandPanel from '../components/auth/AuthBrandPanel';
import AuthTabs from '../components/auth/AuthTabs';
import LoginForm from '../components/auth/LoginForm';
import RegisterForm from '../components/auth/RegisterForm';
import { LockKeyhole } from 'lucide-react';

export default function Auth() {
  const { login, register, googleLogin, user } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  // Active tab state: 'login' or 'register'
  const [activeTab, setActiveTab] = useState('login');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [successMessage, setSuccessMessage] = useState('');

  // Handle switching tabs
  const handleTabChange = (tab) => {
    setActiveTab(tab);
    setError('');
    setSuccessMessage('');
  };

  // Redirect if already authenticated
  useEffect(() => {
    if (user) {
      navigate('/dashboard');
    }
  }, [user, navigate]);

  // LOGIN FORM ACTIONS
  const handleLoginSubmit = async (email, password, rememberMe) => {
    setError('');
    setLoading(true);
    try {
      await login(email, password);
      setSuccessMessage('Welcome back!');
      setTimeout(() => {
        navigate('/dashboard');
      }, 1200);
    } catch (err) {
      setError(typeof err === 'string' ? err : 'Invalid email address or password.');
    } finally {
      setLoading(false);
    }
  };

  // REGISTER FORM ACTIONS
  const handleRegisterSubmit = async (fullName, email, password) => {
    setError('');
    setLoading(true);
    try {
      await register(fullName, email, password);
      setSuccessMessage('Account created successfully.');
      setTimeout(() => {
        // Switch to login tab so they can sign in cleanly
        handleTabChange('login');
      }, 2000);
    } catch (err) {
      setError(typeof err === 'string' ? err : 'This email address is already registered.');
    } finally {
      setLoading(false);
    }
  };

  // GOOGLE OAUTH SUCCESS CALLBACK
  const handleGoogleSuccess = async (data) => {
    if (data && data.user) {
      try {
        await googleLogin(data.user.full_name, data.user.email);
        setSuccessMessage('Welcome back!');
        setTimeout(() => {
          navigate('/dashboard');
        }, 1200);
      } catch (err) {
        setError("Failed to authenticate Google token on backend.");
      }
    } else {
      setError("Unable to authenticate Google details.");
    }
  };

  // GOOGLE OAUTH FAILURE CALLBACK
  const handleGoogleFailure = (errorMessage) => {
    setError(errorMessage);
  };

  return (
    <AuthLayout brandPanel={<AuthBrandPanel />}>
      {/* SUCCESS OVERLAY STATE */}
      {successMessage ? (
        <div style={{ textAlign: 'center', padding: '24px 0' }}>
          <div style={{ fontSize: '42px', marginBottom: '16px' }}>✨</div>
          <h2 style={{ fontSize: '20px', fontWeight: '800', color: 'var(--text-accent)', fontFamily: "'Playfair Display', serif", marginBottom: '8px' }}>
            {successMessage}
          </h2>
          <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginBottom: '24px' }}>
            Redirecting you to your digital tailoring workspace...
          </p>
          <div style={{ display: 'inline-block', width: '24px', height: '24px', border: '3px solid rgba(45, 90, 67, 0.2)', borderTopColor: 'var(--text-accent)', borderRadius: '50%', animation: 'spin 0.8s linear infinite' }}></div>
          <style>{`
            @keyframes spin {
              to { transform: rotate(360deg); }
            }
          `}</style>
        </div>
      ) : (
        <>
          <div style={{ textAlign: 'center', marginBottom: '24px' }}>
            <h1 style={{ fontSize: '18px', fontWeight: '700', color: 'var(--text-primary)', fontFamily: "'Playfair Display', serif" }}>
              Welcome to TailorAI
            </h1>
            <p style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '2px' }}>
              Your AI-assisted digital tailoring workspace.
            </p>
          </div>

          {/* TAB BAR */}
          <AuthTabs activeTab={activeTab} onTabChange={handleTabChange} />

          {/* DYNAMIC FORMS CONTROLS */}
          {activeTab === 'login' ? (
            <LoginForm
              onSubmit={handleLoginSubmit}
              loading={loading}
              error={error}
              onSwitchTab={() => handleTabChange('register')}
              onGoogleSuccess={handleGoogleSuccess}
              onGoogleFailure={handleGoogleFailure}
            />
          ) : (
            <RegisterForm
              onSubmit={handleRegisterSubmit}
              loading={loading}
              error={error}
              onSwitchTab={() => handleTabChange('login')}
              onGoogleSuccess={handleGoogleSuccess}
              onGoogleFailure={handleGoogleFailure}
            />
          )}

          {/* PRIVACY MESSAGE REQUIRED */}
          <div style={{ marginTop: '30px', borderTop: '1px solid var(--border)', paddingTop: '16px', fontSize: '11px', color: 'var(--text-muted)', lineHeight: '1.4', textAlign: 'center', display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '7px' }}>
            <LockKeyhole size={14} aria-hidden="true" />
            Your information is used to provide personalized tailoring features and is handled securely.
          </div>
        </>
      )}
    </AuthLayout>
  );
}
