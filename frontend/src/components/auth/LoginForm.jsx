import { useState } from 'react';
import { AlertCircle, Mail } from 'lucide-react';
import PasswordInput from './PasswordInput';
import GoogleLoginButton, { googleClientId } from './GoogleLoginButton';

export default function LoginForm({ onSubmit, loading, error, onSwitchTab, onGoogleSuccess, onGoogleFailure }) {
  const [form, setForm] = useState({ email: '', password: '' });
  const [errors, setErrors] = useState({});
  const [rememberMe, setRememberMe] = useState(false);
  const [forgot, setForgot] = useState(false);

  const change = (e) => {
    setForm({ ...form, [e.target.name]: e.target.value });
    if (errors[e.target.name]) setErrors({ ...errors, [e.target.name]: '' });
  };

  const submit = (e) => {
    e.preventDefault();
    const next = {};
    if (!form.email) next.email = 'Please enter your email address.';
    else if (!/\S+@\S+\.\S+/.test(form.email)) next.email = 'Please enter a valid email address.';
    if (!form.password) next.password = 'Please enter your password.';
    if (Object.keys(next).length) { setErrors(next); return; }
    onSubmit(form.email, form.password, rememberMe);
  };

  return (
    <div>
      <span className="eyebrow">Welcome back</span>
      <h1>Sign in to TailorAI</h1>
      <p>Continue to your digital pattern studio.</p>

      {error && <div className="alert error" role="alert" style={{ marginBottom: 16 }}><AlertCircle size={17} /> {error}</div>}

      <form onSubmit={submit} noValidate>
        <div className="form-field">
          <label className="form-label" htmlFor="login-email">Email address</label>
          <div className="input-icon">
            <Mail size={17} aria-hidden="true" />
            <input id="login-email" type="email" name="email" autoComplete="email" value={form.email} onChange={change}
                   placeholder="you@example.com" className="glass-input" aria-invalid={errors.email ? 'true' : 'false'}
                   aria-describedby={errors.email ? 'login-email-error' : undefined} />
          </div>
          {errors.email && <span className="field-error" id="login-email-error">{errors.email}</span>}
        </div>
        <div className="form-field">
          <label className="form-label" htmlFor="login-password">Password</label>
          <PasswordInput id="login-password" name="password" value={form.password} onChange={change}
                         placeholder="Enter your password" autoComplete="current-password" invalid={Boolean(errors.password)} />
          {errors.password && <span className="field-error">{errors.password}</span>}
        </div>
        <div className="auth-row">
          <label><input type="checkbox" checked={rememberMe} onChange={(e) => setRememberMe(e.target.checked)} style={{ accentColor: 'var(--accent)' }} /> Remember me</label>
          <button type="button" className="link-btn" onClick={() => setForgot(true)}>Forgot password?</button>
        </div>
        {forgot && (
          <div className="alert info" role="status" style={{ marginBottom: 14, fontSize: 13 }}>
            This system has no e-mail service, so it cannot send a password-reset link.
            If you are still signed in on another device, change your password there under Settings.
            Otherwise the person who runs the server can set a new password for your account.
          </div>
        )}
        <button type="submit" className="btn btn-primary btn-lg btn-block" disabled={loading}>
          {loading ? 'Signing in…' : 'Sign in'}
        </button>
      </form>

      {googleClientId() && (
        <>
          <div className="auth-divider">or</div>
          <GoogleLoginButton onSuccess={onGoogleSuccess} onFailure={onGoogleFailure} parentLoading={loading} />
        </>
      )}

      <p className="auth-switch">Don&apos;t have an account? <button type="button" onClick={onSwitchTab}>Sign up</button></p>
    </div>
  );
}
