import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Bell, ChevronDown, LogOut, Ruler, UserRound } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { patternsAPI, exportAPI } from '../services/api';
import { confirmLeave } from '../utils/unsavedChanges';

const label = (v) => (v ? String(v).replace(/-/g, ' ').replace(/^./, (c) => c.toUpperCase()) : 'Pattern');
const when = (iso) => (iso ? new Date(iso).toLocaleString('en-GB', { dateStyle: 'medium', timeStyle: 'short' }) : '');

export default function Navbar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [showNotifications, setShowNotifications] = useState(false);
  // Real activity only (the user's own saved patterns and PDFs); null = not loaded yet
  const [activity, setActivity] = useState(null);
  const ref = useRef(null);
  const notifRef = useRef(null);
  
  const initials = user?.full_name
    ? user.full_name.split(' ').map((part) => part[0]).join('').slice(0, 2).toUpperCase()
    : '?';

  const loadActivity = () => {
    Promise.all([patternsAPI.getAll(), exportAPI.getAll()])
      .then(([p, e]) => {
        const items = [
          ...(p.data.patterns || []).map((x) => ({
            id: `p-${x.pattern_id}`, at: x.generated_at,
            text: `${label(x.garment_type)} pattern generated${x.yardage_metres > 0 ? ` · ${x.yardage_metres} m fabric` : ''}`,
          })),
          ...(e.data.exports || []).map((x) => ({ id: `e-${x.export_id}`, at: x.exported_at, text: 'Printable PDF created' })),
        ].sort((a, b) => String(b.at).localeCompare(String(a.at))).slice(0, 5);
        setActivity(items);
      })
      .catch(() => setActivity([]));
  };

  useEffect(() => {
    const close = (event) => {
      if (ref.current && !ref.current.contains(event.target)) {
        setOpen(false);
      }
      if (notifRef.current && !notifRef.current.contains(event.target)) {
        setShowNotifications(false);
      }
    };
    document.addEventListener('mousedown', close);
    return () => document.removeEventListener('mousedown', close);
  }, []);

  const signOut = () => {
    if (!confirmLeave()) return;
    logout();
    setOpen(false);
    navigate('/auth');
  };

  const handleNotificationClick = () => {
    if (!showNotifications) loadActivity();
    setShowNotifications(!showNotifications);
  };

  return (
    <header className="app-header">
      <Link to="/dashboard" className="app-brand" aria-label="TailorAI overview" onClick={(e) => { if (!confirmLeave()) e.preventDefault(); }}>
        <span className="app-brand-mark"><Ruler size={20} strokeWidth={1.8}/></span>
        <span><strong>TailorAI</strong><small>Digital pattern studio</small></span>
      </Link>

      <div className="app-header-actions">
        <div className="profile-menu" ref={notifRef}>
          <button 
            className="icon-btn notification-btn" 
            aria-label="Recent activity"
            aria-expanded={showNotifications}
            onClick={handleNotificationClick}
            style={{ position: 'relative' }}
          >
            <Bell size={18}/>
          </button>
          {showNotifications && (
            <div className="profile-dropdown" style={{ right: '0', width: '280px', padding: '12px', zIndex: 100 }}>
              <div style={{ paddingBottom: '8px', fontWeight: 'bold', borderBottom: '1px solid var(--border)', fontSize: '12px', color: 'var(--text-primary)' }}>
                Recent activity
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginTop: '8px' }} data-testid="activity-list">
                {activity === null && <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Loading…</div>}
                {activity?.length === 0 && <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>No activity yet. Patterns and PDFs you create appear here.</div>}
                {activity?.map(n => (
                  <div key={n.id} style={{ paddingBottom: '8px', borderBottom: '1px solid var(--border)', fontSize: '11px', lineHeight: '1.4' }}>
                    <div style={{ color: 'var(--text-primary)' }}>{n.text}</div>
                    <small style={{ color: 'var(--text-muted)', display: 'block', marginTop: '2px' }}>{when(n.at)}</small>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
        <div className="profile-menu" ref={ref}>
          <button className="profile-trigger" onClick={() => setOpen(!open)} aria-expanded={open}>
            <span className="nav-avatar">{initials}</span>
            <span className="profile-copy">
              <strong>{user?.full_name || 'My account'}</strong>
              <small>Tailor member</small>
            </span>
            <ChevronDown size={15} className={open ? 'rotate' : ''}/>
          </button>
          {open && (
            <div className="profile-dropdown">
              <div className="profile-dropdown-head">
                <span className="nav-avatar large">{initials}</span>
                <div><strong>{user?.full_name || 'My account'}</strong><small>{user?.email || ''}</small></div>
              </div>
              <button onClick={() => { if (!confirmLeave()) return; setOpen(false); navigate('/measurements'); }}><UserRound size={16}/> My measurements</button>
              <button className="danger" onClick={signOut}><LogOut size={16}/> Sign out</button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
