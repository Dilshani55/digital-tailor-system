import { useState } from 'react';
import { AlertCircle, Mail, User } from 'lucide-react';
import PasswordInput from './PasswordInput';
import PasswordStrength from './PasswordStrength';
import GoogleLoginButton, { googleClientId } from './GoogleLoginButton';

export default function RegisterForm({ onSubmit, loading, error, onSwitchTab, onGoogleSuccess, onGoogleFailure }) {
  const [form, setForm] = useState({ fullName: '', email: '', password: '', confirmPassword: '' });
  const [agree, setAgree] = useState(false);
  const [errors, setErrors] = useState({});

  const change = (e) => {
    setForm({ ...form, [e.target.name]: e.target.value });
    if (errors[e.target.name]) setErrors({ ...errors, [e.target.name]: '' });
  };

  const submit = (e) => {
    e.preventDefault();
    const next = {};
    if (!form.fullName || form.fullName.trim().length < 2) next.fullName = 'Please enter your name (at least 2 characters).';
    if (!form.email) next.email = 'Please enter your email address.';
    else if (!/\S+@\S+\.\S+/.test(form.email)) next.email = 'Please enter a valid email address.';
    if (!form.password || form.password.length < 8) next.password = 'Use at least 8 characters.';
    if (form.password !== form.confirmPassword) next.confirmPassword = 'Passwords do not match.';
    if (!agree) next.terms = 'Please agree to the terms to create an account.';
    if (Object.keys(next).length) { setErrors(next); return; }
    onSubmit(form.fullName.trim(), form.email, form.password);
  };

  const err = (k) => errors[k] && <span className="field-error">{errors[k]}</span>;

  return (
    <div>
      <span className="eyebrow">Create account</span>
      <h1>Join TailorAI</h1>
      <p>Save your customers, measurements and patterns in one place.</p>

      {error && <div className="alert error" role="alert" style={{ marginBottom: 16 }}><AlertCircle size={17} /> {error}</div>}

      <form onSubmit={submit} noValidate>
        <div className="form-field">
          <label className="form-label" htmlFor="reg-fullName">Full Name</label>
          <div className="input-icon">
            <User size={17} aria-hidden="true" />
            <input id="reg-fullName" type="text" name="fullName" autoComplete="name" value={form.fullName} onChange={change}
                   placeholder="Your full name" className="glass-input" aria-invalid={errors.fullName ? 'true' : 'false'} />
          </div>
          {err('fullName')}
        </div>
        <div className="form-field">
          <label className="form-label" htmlFor="reg-email">Email Address</label>
          <div className="input-icon">
            <Mail size={17} aria-hidden="true" />
            <input id="reg-email" type="email" name="email" autoComplete="email" value={form.email} onChange={change}
                   placeholder="you@example.com" className="glass-input" aria-invalid={errors.email ? 'true' : 'false'} />
          </div>
          {err('email')}
        </div>
        <div className="form-field">
          <label className="form-label" htmlFor="reg-password">Password</label>
          <PasswordInput id="reg-password" name="password" value={form.password} onChange={change}
                         placeholder="At least 8 characters" autoComplete="new-password" invalid={Boolean(errors.password)} />
          <PasswordStrength password={form.password} />
          {err('password')}
        </div>
        <div className="form-field">
          <label className="form-label" htmlFor="reg-confirmPassword">Confirm Password</label>
          <PasswordInput id="reg-confirmPassword" name="confirmPassword" value={form.confirmPassword} onChange={change}
                         placeholder="Repeat the password" autoComplete="new-password" invalid={Boolean(errors.confirmPassword)} />
          {err('confirmPassword')}
        </div>
        <label style={{ display: 'flex', gap: 8, alignItems: 'flex-start', fontSize: 14, color: 'var(--ink-2)', margin: '4px 0 18px', cursor: 'pointer' }}>
          <input type="checkbox" checked={agree} onChange={(e) => { setAgree(e.target.checked); setErrors({ ...errors, terms: '' }); }}
                 style={{ accentColor: 'var(--accent)', marginTop: 3 }} />
          <span>I agree that my measurements and designs are stored to create my patterns.</span>
        </label>
        {err('terms')}
        <button type="submit" className="btn btn-primary btn-lg btn-block" disabled={loading} style={{ marginTop: 6 }}>
          {loading ? 'Creating account…' : 'Create account'}
        </button>
      </form>

      {googleClientId() && (
        <>
          <div className="auth-divider">or</div>
          <GoogleLoginButton onSuccess={onGoogleSuccess} onFailure={onGoogleFailure} parentLoading={loading} />
        </>
      )}

      <p className="auth-switch">Already have an account? <button type="button" onClick={onSwitchTab}>Sign in</button></p>
    </div>
  );
}
