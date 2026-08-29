import { useState } from 'react';
import { AlertCircle } from 'lucide-react';
import PasswordInput from './PasswordInput';
import PasswordStrength from './PasswordStrength';
import GoogleLoginButton from './GoogleLoginButton';

export default function RegisterForm({ onSubmit, loading, error, onSwitchTab, onGoogleSuccess, onGoogleFailure }) {
  const [form, setForm] = useState({
    fullName: '',
    email: '',
    password: '',
    confirmPassword: ''
  });
  const [agreeTerms, setAgreeTerms] = useState(false);
  const [validationErrors, setValidationErrors] = useState({});

  const handleChange = (e) => {
    setForm({ ...form, [e.target.name]: e.target.value });
    if (validationErrors[e.target.name]) {
      setValidationErrors({ ...validationErrors, [e.target.name]: '' });
    }
  };

  const handleFormSubmit = (e) => {
    e.preventDefault();
    const errors = {};

    if (!form.fullName) {
      errors.fullName = 'Please enter your name.';
    } else if (form.fullName.length < 2) {
      errors.fullName = 'Name must be at least 2 characters.';
    }

    if (!form.email) {
      errors.email = 'Please enter your email address.';
    } else if (!/\S+@\S+\.\S+/.test(form.email)) {
      errors.email = 'Please enter a valid email address.';
    }

    if (!form.password) {
      errors.password = 'Please enter a password.';
    } else if (form.password.length < 8) {
      errors.password = 'Password must meet the minimum requirements (at least 8 characters).';
    }

    if (!form.confirmPassword) {
      errors.confirmPassword = 'Please confirm your password.';
    } else if (form.password !== form.confirmPassword) {
      errors.confirmPassword = 'Passwords do not match.';
    }

    if (!agreeTerms) {
      errors.terms = 'You must agree to the Terms of Use and Privacy Policy.';
    }

    if (Object.keys(errors).length > 0) {
      setValidationErrors(errors);
      return;
    }

    onSubmit(form.fullName, form.email, form.password);
  };

  return (
    <div>
      <div style={{ marginBottom: '24px' }}>
        <h2 style={{ fontSize: '22px', fontWeight: '800', color: 'var(--text-primary)', fontFamily: "'Playfair Display', serif" }}>
          Create Your Account
        </h2>
        <p style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '4px' }}>
          Save your measurements and tailoring analyses in one place.
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
          <label className="block text-xs font-semibold text-slate-700 mb-1.5">
            Full Name
          </label>
          <input
            type="text"
            name="fullName"
            value={form.fullName}
            onChange={handleChange}
            placeholder="Enter your full name"
            className="w-full glass-input rounded-xl px-4 py-3 text-sm focus:outline-none transition-all"
          />
          {validationErrors.fullName && (
            <div style={{ color: '#EF4444', fontSize: '11px', marginTop: '4px' }}>
              {validationErrors.fullName}
            </div>
          )}
        </div>

        <div>
          <label className="block text-xs font-semibold text-slate-700 mb-1.5">
            Email Address
          </label>
          <input
            type="email"
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
          <label className="block text-xs font-semibold text-slate-700 mb-1.5">
            Password
          </label>
          <PasswordInput
            name="password"
            value={form.password}
            onChange={handleChange}
            placeholder="Create a password"
          />
          <span style={{ display: 'block', fontSize: '11px', color: '#928B7F', marginTop: '4px' }}>
            Use at least 8 characters.
          </span>
          <PasswordStrength password={form.password} />
          {validationErrors.password && (
            <div style={{ color: '#EF4444', fontSize: '11px', marginTop: '4px' }}>
              {validationErrors.password}
            </div>
          )}
        </div>

        <div>
          <label className="block text-xs font-semibold text-slate-700 mb-1.5">
            Confirm Password
          </label>
          <PasswordInput
            name="confirmPassword"
            value={form.confirmPassword}
            onChange={handleChange}
            placeholder="Confirm your password"
          />
          {validationErrors.confirmPassword && (
            <div style={{ color: '#EF4444', fontSize: '11px', marginTop: '4px' }}>
              {validationErrors.confirmPassword}
            </div>
          )}
        </div>

        <div style={{ paddingTop: '4px' }}>
          <label style={{ display: 'flex', alignItems: 'flex-start', gap: '8px', fontSize: '12px', color: 'var(--text-secondary)', cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={agreeTerms}
              onChange={(e) => {
                setAgreeTerms(e.target.checked);
                if (validationErrors.terms) {
                  setValidationErrors({ ...validationErrors, terms: '' });
                }
              }}
              style={{ accentColor: 'var(--text-accent)', marginTop: '2px' }}
            />
            <span>
              I agree to the{' '}
              <button type="button" onClick={() => alert('Terms of Use')} style={{ background: 'none', border: 'none', color: 'var(--text-accent)', cursor: 'pointer', padding: 0, textDecoration: 'underline' }}>
                Terms of Use
              </button>{' '}
              and{' '}
              <button type="button" onClick={() => alert('Privacy Policy')} style={{ background: 'none', border: 'none', color: 'var(--text-accent)', cursor: 'pointer', padding: 0, textDecoration: 'underline' }}>
                Privacy Policy
              </button>.
            </span>
          </label>
          {validationErrors.terms && (
            <div style={{ color: '#EF4444', fontSize: '11px', marginTop: '4px' }}>
              {validationErrors.terms}
            </div>
          )}
        </div>

        <button
          type="submit"
          disabled={loading}
          className="w-full py-3 rounded-xl font-semibold text-sm text-white bg-gradient-to-r from-brand-600 to-indigo-500 hover:from-brand-500 hover:to-indigo-400 shadow-glow-indigo transition-all duration-200 disabled:opacity-50 flex items-center justify-center gap-2"
          style={{ background: 'var(--text-accent)', cursor: 'pointer', height: '46px', marginTop: '16px' }}
        >
          {loading ? 'Creating account...' : 'Create Account'}
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

      <p style={{ textAlign: 'center', fontSize: '12px', color: 'var(--text-secondary)', marginTop: '24px' }}>
        Already have an account?{' '}
        <button
          type="button"
          onClick={onSwitchTab}
          style={{ background: 'none', border: 'none', color: 'var(--text-accent)', fontWeight: '700', cursor: 'pointer' }}
        >
          Sign In
        </button>
      </p>
    </div>
  );
}
