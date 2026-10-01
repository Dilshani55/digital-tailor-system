import { useEffect, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { Check, Cpu, KeyRound, Ruler, Save, User } from 'lucide-react';
import { authAPI, imagesAPI } from '../services/api';
import { friendlyError } from '../utils/friendlyError';
import { FABRIC_WIDTHS, getPreferences, savePreferences, widthLabel } from '../utils/preferences';

// Fixed by the drafting engine (backend/app/logic/drafting/seam_allowance.py) — shown for
// information only; they are project sewing-practice choices, not user settings.
const ALLOWANCES = [
  ['Side, shoulder, armhole and sleeve seams', '1.5 cm', '1.0 cm'],
  ['Neckline', '1.0 cm', '1.0 cm'],
  ['Hem', '2.5 cm', '2.0 cm'],
  ['Neckband / facing strips', '1.0 cm', '0.7 cm'],
];

const MODEL_LABEL = { garment_type: 'Garment type', neckline_type: 'Neckline', sleeve_length: 'Sleeve length', sleeve_style: 'Sleeve style' };
const card = { padding: '24px' };
const h2 = { fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' };
const row = { display: 'flex', justifyContent: 'space-between', gap: '12px', fontSize: '13px', padding: '8px 0', borderBottom: '1px solid var(--border)' };

export default function Settings() {
  const { user } = useAuth();
  const [prefs, setPrefs] = useState(getPreferences);
  const [saved, setSaved] = useState('');
  const [model, setModel] = useState({ state: 'loading' });
  const [pw, setPw] = useState({ current: '', next: '', confirm: '' });
  const [pwError, setPwError] = useState('');
  const [pwDone, setPwDone] = useState('');
  const [pwBusy, setPwBusy] = useState(false);

  const changePassword = async (e) => {
    e.preventDefault();
    setPwError('');
    setPwDone('');
    if (!pw.current || !pw.next) { setPwError('Enter your current password and a new password.'); return; }
    if (pw.next.length < 8) { setPwError('The new password must be at least 8 characters.'); return; }
    if (pw.next !== pw.confirm) { setPwError('The two new passwords are not the same.'); return; }
    setPwBusy(true);
    try {
      await authAPI.changePassword({ current_password: pw.current, new_password: pw.next });
      setPw({ current: '', next: '', confirm: '' });
      setPwDone('Password changed. Use the new password the next time you sign in.');
    } catch (err) {
      setPwError(friendlyError(err, 'The password could not be changed. Please try again.'));
    } finally {
      setPwBusy(false);
    }
  };

  useEffect(() => {
    imagesAPI.modelStatus()
      .then((r) => setModel({ state: r.data.available ? 'available' : 'unavailable', ...r.data }))
      .catch(() => setModel({ state: 'unknown' }));
  }, []);

  const save = (e) => {
    e.preventDefault();
    setSaved(savePreferences(prefs) ? 'Preferences saved on this device.' : 'This browser blocked local storage, so the preferences could not be saved.');
    setTimeout(() => setSaved(''), 4000);
  };

  return (
    <div style={{ padding: '24px', maxWidth: '1000px', margin: '0 auto' }}>
      <div style={{ marginBottom: '24px' }}>
        <h1 style={{ fontSize: '22px', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '4px' }}>Settings</h1>
        <p style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>Your account, workspace defaults and the drafting constants the system uses.</p>
      </div>

      {saved && (
        <div role="status" style={{ padding: '12px 16px', background: 'rgba(21, 128, 61, 0.1)', border: '1px solid var(--text-accent)', borderRadius: '8px', color: 'var(--text-accent)', fontSize: '13px', marginBottom: '20px', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Check size={16}/> {saved}
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '24px', alignItems: 'start' }}>
        <section className="ui-card" style={card} aria-labelledby="account-h">
          <h2 id="account-h" style={h2}><User size={16}/> Account</h2>
          <div style={row}><span style={{ color: 'var(--text-secondary)' }}>Name</span><strong>{user?.full_name || '—'}</strong></div>
          <div style={row}><span style={{ color: 'var(--text-secondary)' }}>E-mail</span><strong>{user?.email || '—'}</strong></div>
          <p style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '12px', lineHeight: 1.5 }}>
            Changing the name or e-mail is not available in this prototype.
          </p>
        </section>

        <section className="ui-card" style={card} aria-labelledby="password-h">
          <h2 id="password-h" style={h2}><KeyRound size={16}/> Change password</h2>
          <form onSubmit={changePassword} noValidate style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {pwError && <div role="alert" className="alert error" data-testid="password-error">{pwError}</div>}
            {pwDone && <div role="status" className="alert success" data-testid="password-done">{pwDone}</div>}
            <div className="form-field">
              <label className="form-label" htmlFor="pw-current">Current password</label>
              <input id="pw-current" type="password" className="form-input" autoComplete="current-password" value={pw.current}
                     onChange={(e) => setPw({ ...pw, current: e.target.value })} />
            </div>
            <div className="form-field">
              <label className="form-label" htmlFor="pw-new">New password</label>
              <input id="pw-new" type="password" className="form-input" autoComplete="new-password" value={pw.next}
                     onChange={(e) => setPw({ ...pw, next: e.target.value })} />
              <span className="form-hint">At least 8 characters.</span>
            </div>
            <div className="form-field">
              <label className="form-label" htmlFor="pw-confirm">New password again</label>
              <input id="pw-confirm" type="password" className="form-input" autoComplete="new-password" value={pw.confirm}
                     onChange={(e) => setPw({ ...pw, confirm: e.target.value })} />
            </div>
            <button type="submit" className="btn btn-primary" disabled={pwBusy} style={{ alignSelf: 'flex-start' }}>
              {pwBusy ? 'Changing…' : 'Change password'}
            </button>
            <p style={{ fontSize: '11px', color: 'var(--text-muted)', lineHeight: 1.5 }}>
              There is no “forgot password” e-mail: this system has no e-mail service. A forgotten password can only be
              reset by the person who runs the server. Other devices stay signed in until their session ends (24 hours).
            </p>
          </form>
        </section>

        <form className="ui-card" style={card} onSubmit={save} aria-labelledby="prefs-h">
          <h2 id="prefs-h" style={h2}><Ruler size={16}/> Workspace defaults</h2>
          <div className="form-field">
            <span className="form-label" id="unit-pref">Measurement unit when starting a new pattern</span>
            <div role="group" aria-labelledby="unit-pref" style={{ display: 'flex', gap: '8px' }}>
              {[['cm', 'Centimetres (cm)'], ['in', 'Inches (in)']].map(([v, text]) => (
                <button key={v} type="button" aria-pressed={prefs.unit === v} className={prefs.unit === v ? 'btn btn-primary' : 'btn btn-outline'}
                        onClick={() => setPrefs({ ...prefs, unit: v })}>{text}</button>
              ))}
            </div>
          </div>
          <div className="form-field" style={{ marginTop: '14px' }}>
            <label className="form-label" htmlFor="width-pref">Fabric width for the first estimate</label>
            <select id="width-pref" className="form-select" value={prefs.fabricWidth}
                    onChange={(e) => setPrefs({ ...prefs, fabricWidth: Number(e.target.value) })}>
              {FABRIC_WIDTHS.map((w) => <option key={w} value={w}>{widthLabel(w)}</option>)}
            </select>
          </div>
          <p style={{ fontSize: '11px', color: 'var(--text-muted)', margin: '12px 0', lineHeight: 1.5 }}>
            Stored in this browser only. You can still change both in each pattern.
          </p>
          <button type="submit" className="btn btn-primary"><Save size={15}/> Save preferences</button>
        </form>

        <section className="ui-card" style={card} aria-labelledby="allow-h">
          <h2 id="allow-h" style={h2}>Seam allowances (set by the drafting engine)</h2>
          <table className="hist-table" style={{ fontSize: '12px' }}>
            <thead><tr><th>Edge</th><th>Woven</th><th>Knit</th></tr></thead>
            <tbody>{ALLOWANCES.map(([edge, w, k]) => <tr key={edge}><td>{edge}</td><td style={{ whiteSpace: 'nowrap' }}>{w}</td><td style={{ whiteSpace: 'nowrap' }}>{k}</td></tr>)}</tbody>
          </table>
          <p style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '12px', lineHeight: 1.5 }}>
            Fold edges have no allowance. The fabric estimate adds 3 % shrinkage and a 10 cm cutting margin.
            These are project assumptions, not measured values.
          </p>
        </section>

        <section className="ui-card" style={card} aria-labelledby="ai-h">
          <h2 id="ai-h" style={h2}><Cpu size={16}/> AI garment models</h2>
          <div data-testid="model-state" style={{ fontSize: '13px' }}>
            {model.state === 'loading' && 'Checking…'}
            {model.state === 'available' && (
              <>
                <div style={row}><span style={{ color: 'var(--text-secondary)' }}>Status</span><strong style={{ color: 'var(--text-accent)' }}>Available</strong></div>
                {Object.entries(model.models || {}).map(([head, m]) => (
                  <div style={row} key={head} data-testid={`model-${head}`}>
                    <span style={{ color: 'var(--text-secondary)' }}>{MODEL_LABEL[head] || head} · {m.architecture}</span>
                    <strong>{!m.available ? 'Not installed' : m.answers_automatically ? 'Fills in when confident' : 'Suggests only — you select'}</strong>
                  </div>
                ))}
                <div style={row}><span style={{ color: 'var(--text-secondary)' }}>Fingerprint (SHA-256)</span>
                  <code title={model.checkpoint_sha256}>{(model.checkpoint_sha256 || '').slice(0, 16)}…</code></div>
              </>
            )}
            {model.state === 'unavailable' && <p>Not available on this server — photos cannot be analysed; designs can still be chosen manually.</p>}
            {model.state === 'unknown' && <p>The server could not be reached.</p>}
          </div>
          <p style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '12px', lineHeight: 1.5 }}>
            Four separate models suggest the garment type, neckline, sleeve length and sleeve style. They only suggest: you confirm every feature, and the pattern itself is drafted by deterministic geometry.
          </p>
        </section>
      </div>
    </div>
  );
}
