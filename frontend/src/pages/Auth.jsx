import { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { LockKeyhole, Ruler } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import LoginForm from '../components/auth/LoginForm';
import RegisterForm from '../components/auth/RegisterForm';

// Pattern sheets + tape measure (decorative).
function PatternIllustration() {
  return (
    <svg viewBox="0 0 440 300" className="auth-illustration" aria-hidden="true">
      <rect x="60" y="40" width="210" height="250" rx="6" fill="#dfe8e1" opacity=".35" transform="rotate(-8 165 165)" />
      <rect x="95" y="30" width="220" height="260" rx="6" fill="#f3efe4" />
      <path d="M130 70 L175 60 C180 78 205 80 212 62 L262 72 L270 120 C258 150 262 190 268 250 L140 250 C146 190 150 150 138 120 Z"
            fill="none" stroke="#56625b" strokeWidth="2" />
      <path d="M140 80 L184 70 C189 88 202 89 205 72 L254 82 L260 124 C250 152 253 190 258 240 L150 240 C155 190 158 152 148 124 Z"
            fill="none" stroke="#8a948e" strokeWidth="1.3" strokeDasharray="5 4" />
      <line x1="200" y1="120" x2="200" y2="220" stroke="#56625b" strokeWidth="1.5" />
      <path d="M200 114 l-5 10 h10 z M200 226 l-5 -10 h10 z" fill="#56625b" />
      <path d="M300 90 C360 110 390 170 360 260 C350 290 330 300 310 296" fill="none" stroke="#e9e4d4" strokeWidth="22" strokeLinecap="round" />
      {Array.from({ length: 12 }).map((_, i) => {
        const t = i / 11;
        const x = 300 + 70 * Math.sin(t * 2.4) - 5 * t;
        const y = 90 + 205 * t;
        return <line key={i} x1={x - 6} y1={y} x2={x + 6} y2={y} stroke="#b8b09a" strokeWidth="1.5" />;
      })}
      <path d="M20 260 C40 200 70 170 110 150 M40 230 C30 215 18 212 8 214 M60 205 C52 188 40 184 28 186 M82 180 C78 163 68 157 56 158"
            fill="none" stroke="#6f9a7f" strokeWidth="3" strokeLinecap="round" />
    </svg>
  );
}

export default function Auth() {
  const { login, register, googleLogin, user } = useAuth();
  const navigate = useNavigate();
  const [mode, setMode] = useState('login');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  useEffect(() => { if (user) navigate('/dashboard'); }, [user, navigate]);

  const switchTo = (m) => { setMode(m); setError(''); setNotice(''); };

  const handleLogin = async (email, password) => {
    setError('');
    setLoading(true);
    try {
      await login(email, password);
      navigate('/dashboard');
    } catch (err) {
      setError(typeof err === 'string' ? err : 'Invalid email address or password.');
    } finally {
      setLoading(false);
    }
  };

  const handleRegister = async (fullName, email, password) => {
    setError('');
    setLoading(true);
    try {
      await register(fullName, email, password);
      setMode('login');
      setNotice('Account created. Please sign in.');
    } catch (err) {
      setError(typeof err === 'string' ? err : 'This email address is already registered.');
    } finally {
      setLoading(false);
    }
  };

  const handleGoogleSuccess = async (data) => {
    if (!data?.user) { setError('Unable to authenticate Google details.'); return; }
    try {
      await googleLogin(data.user.full_name, data.user.email);
      navigate('/dashboard');
    } catch {
      setError('Google sign-in could not be completed.');
    }
  };

  return (
    <div className="auth-page">
      <section className="auth-brand">
        <div className="auth-brand-logo">
          <span><Ruler size={22} /></span>
          <span><strong>TailorAI</strong><small>Digital pattern studio</small></span>
        </div>
        <div>
          <h2>Turn your designs into precise patterns</h2>
          <p style={{ marginTop: 14 }}>Upload a garment photo, confirm the design, add body measurements and get a printable,
            made-to-measure sewing pattern with the fabric you need.</p>
        </div>
        <PatternIllustration />
      </section>

      <section className="auth-form-side" style={{ position: 'relative' }}>
        <Link to="/" className="auth-back">← Back to home</Link>
        <div className="auth-form">
          {notice && <div className="alert success" role="status" style={{ marginBottom: 16 }}>{notice}</div>}
          {mode === 'login' ? (
            <LoginForm onSubmit={handleLogin} loading={loading} error={error} onSwitchTab={() => switchTo('register')}
                       onGoogleSuccess={handleGoogleSuccess} onGoogleFailure={setError} />
          ) : (
            <RegisterForm onSubmit={handleRegister} loading={loading} error={error} onSwitchTab={() => switchTo('login')}
                          onGoogleSuccess={handleGoogleSuccess} onGoogleFailure={setError} />
          )}
          <p className="auth-privacy"><LockKeyhole size={14} aria-hidden="true" /> Your measurements are used only to draft your patterns.</p>
        </div>
      </section>
    </div>
  );
}
