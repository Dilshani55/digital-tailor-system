import { useState } from 'react';
import { AlertCircle } from 'lucide-react';
import PasswordInput from './PasswordInput';
import GoogleLoginButton from './GoogleLoginButton';

export default function LoginForm({ onSubmit, loading, error, onSwitchTab, onGoogleSuccess, onGoogleFailure }) {
  const [form, setForm] = useState({ email: '', password: '' });
  const [validationErrors, setValidationErrors] = useState({});
  const [rememberMe, setRememberMe] = useState(false);

  const handleChange = (e) => {
    setForm({ ...form, [e.target.name]: e.target.value });
    if (validationErrors[e.target.name]) {
      setValidationErrors({ ...validationErrors, [e.target.name]: '' });
    }
  };

  const handleFormSubmit = (e) => {
    e.preventDefault();
    const errors = {};

    if (!form.email) {
      errors.email = 'Please enter your email address.';
    } else if (!/\S+@\S+\.\S+/.test(form.email)) {
      errors.email = 'Please enter a valid email address.';
    }

    if (!form.password) {
      errors.password = 'Please enter your password.';
    } else if (form.password.length < 6) {
      errors.password = 'Password must be at least 6 characters.';
    }

    if (Object.keys(errors).length > 0) {
      setValidationErrors(errors);
      return;
    }

    onSubmit(form.email, form.password, rememberMe);
  };

  return (
    <div>
      <div style={{ marginBottom: '24px' }}>
        <h2 style={{ fontSize: '22px', fontWeight: '800', color: 'var(--text-primary)', fontFamily: "'Playfair Display', serif" }}>
          Welcome Back
        </h2>
        <p style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '4px' }}>
          Sign in to continue your digital tailoring journey.
        </p>
      </div>

      {error && (
        <div style={{
          padding: '12px 14px', background: '#FEF2F2', border: '1px solid #FCA5A5',
          borderRadius: '8px', color: '#991B1B', fontSize: '12px', marginBottom: '20px',
          display: 'flex', alignItems: 'center', gap: '8px'
        }}>
          <AlertCircle size={16}/> {error}
        </div>
      )}

      <form onSubmit={handleFormSubmit} className="space-y-4">
        <div>
          <label className="block text-xs font-semibold text-slate-700 mb-1.5" htmlFor="login-email">
            Email Address
          </label>
          <input
            id="login-email" type="email"
            name="email"
            value={form.email}
            onChange={handleChange}
            placeholder="Enter your email address"
            className="w-full glass-input rounded-xl px-4 py-3 text-sm focus:outline-none transition-all"
          />
          {validationErrors.email && (
            <div style={{ color: '#EF4444', fontSize: '11px', marginTop: '4px' }}>
              {validationErrors.email}
            </div>
          )}
        </div>

        <div>
          <label className="block text-xs font-semibold text-slate-700 mb-1.5" htmlFor="login-password">
            Password
          </label>
          <PasswordInput
            id="login-password" name="password"
            value={form.password}
            onChange={handleChange}
            placeholder="Enter your password"
          />
          {validationErrors.password && (
            <div style={{ color: '#EF4444', fontSize: '11px', marginTop: '4px' }}>
              {validationErrors.password}
            </div>
          )}
        </div>

        <div style={{ display: 'flex', alignItems: 'center', fontSize: '12px', paddingTop: '4px' }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--text-secondary)', cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={rememberMe}
              onChange={(e) => setRememberMe(e.target.checked)}
              style={{ accentColor: 'var(--text-accent)' }}
            />
            Remember me
          </label>
        </div>

        <button
          type="submit"
          disabled={loading}
          className="w-full py-3 rounded-xl font-semibold text-sm text-white bg-gradient-to-r from-brand-600 to-indigo-500 hover:from-brand-500 hover:to-indigo-400 shadow-glow-indigo transition-all duration-200 disabled:opacity-50 flex items-center justify-center gap-2"
          style={{ background: 'var(--text-accent)', cursor: 'pointer', height: '46px', marginTop: '16px' }}
        >
          {loading ? 'Signing in...' : 'Sign In'}
        </button>
      </form>

      {/* Separator line */}
      <div style={{
        display: 'flex', alignItems: 'center', margin: '20px 0',
        fontSize: '11px', color: 'var(--text-muted)', fontWeight: '500'
      }}>
        <div style={{ flex: 1, height: '1px', background: 'var(--border)' }} division-line=""></div>
        <span style={{ padding: '0 10px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>OR</span>
        <div style={{ flex: 1, height: '1px', background: 'var(--border)' }} division-line=""></div>
      </div>

      {/* Continue with Google button */}
      <div style={{ marginBottom: '16px' }}>
        <GoogleLoginButton
          onSuccess={onGoogleSuccess}
          onFailure={onGoogleFailure}
          parentLoading={loading}
        />
      </div>

      {/* Forgot Password link */}
      <div style={{ textAlign: 'center', marginBottom: '20px' }}>
        <button
          type="button"
          onClick={() => alert('Forgot password feature will be activated when mailing services are integrated.')}
          style={{ background: 'none', border: 'none', color: 'var(--text-accent)', cursor: 'pointer', fontWeight: '600', fontSize: '12px' }}
        >
          Forgot password?
        </button>
      </div>

      <p style={{ textAlign: 'center', fontSize: '12px', color: 'var(--text-secondary)', marginTop: '24px' }}>
        Don't have an account?{' '}
        <button
          type="button"
          onClick={onSwitchTab}
          style={{ background: 'none', border: 'none', color: 'var(--text-accent)', fontWeight: '700', cursor: 'pointer' }}
        >
          Create an account
        </button>
      </p>
    </div>
  );
}
