import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Bell, ChevronDown, LogOut, Ruler, UserRound } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

export default function Navbar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [showNotifications, setShowNotifications] = useState(false);
  const [hasUnread, setHasUnread] = useState(true);
  const ref = useRef(null);
  const notifRef = useRef(null);
  
  const initials = user?.full_name
    ? user.full_name.split(' ').map((part) => part[0]).join('').slice(0, 2).toUpperCase()
    : 'DV';

  const notifications = [
    { id: 1, text: "YOLOv8 Garment features detected successfully.", time: "2 mins ago" },
    { id: 2, text: "Parametric Nesting: 78.7% fabric efficiency achieved.", time: "1 hour ago" },
    { id: 3, text: "ReportLab PDF guide compiled and ready.", time: "3 hours ago" }
  ];

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
    logout();
    setOpen(false);
    navigate('/auth');
  };

  const handleNotificationClick = () => {
    setShowNotifications(!showNotifications);
    setHasUnread(false);
  };

  return (
    <header className="app-header">
      <Link to="/" className="app-brand" aria-label="TailorAI dashboard">
        <span className="app-brand-mark"><Ruler size={20} strokeWidth={1.8}/></span>
        <span><strong>TailorAI</strong><small>Digital pattern studio</small></span>
      </Link>

      <div className="app-header-actions">
        <div className="profile-menu" ref={notifRef}>
          <button 
            className="icon-btn notification-btn" 
            aria-label="Notifications"
            onClick={handleNotificationClick}
            style={{ position: 'relative' }}
          >
            <Bell size={18}/>
            {hasUnread && <span className="notification-dot" style={{ position: 'absolute', top: '2px', right: '2px', width: '8px', height: '8px', borderRadius: '50%', background: '#EF4444' }}/>}
          </button>
          {showNotifications && (
            <div className="profile-dropdown" style={{ right: '0', width: '280px', padding: '12px', zIndex: 100 }}>
              <div style={{ paddingBottom: '8px', fontWeight: 'bold', borderBottom: '1px solid var(--border)', fontSize: '12px', color: 'var(--text-primary)' }}>
                Notifications
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginTop: '8px' }}>
                {notifications.map(n => (
                  <div key={n.id} style={{ paddingBottom: '8px', borderBottom: '1px solid var(--border)', fontSize: '11px', lineHeight: '1.4' }}>
                    <div style={{ color: 'var(--text-primary)' }}>{n.text}</div>
                    <small style={{ color: 'var(--text-muted)', display: 'block', marginTop: '2px' }}>{n.time}</small>
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
              <strong>{user?.full_name || 'Dilshani Vitharana'}</strong>
              <small>Tailor member</small>
            </span>
            <ChevronDown size={15} className={open ? 'rotate' : ''}/>
          </button>
          {open && (
            <div className="profile-dropdown">
              <div className="profile-dropdown-head">
                <span className="nav-avatar large">{initials}</span>
                <div><strong>{user?.full_name || 'Dilshani Vitharana'}</strong><small>{user?.email || 'member@tailorai.lk'}</small></div>
              </div>
              <button onClick={() => { setOpen(false); navigate('/measurements'); }}><UserRound size={16}/> My measurements</button>
              <button className="danger" onClick={signOut}><LogOut size={16}/> Sign out</button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
