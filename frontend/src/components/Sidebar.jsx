import { Link, useLocation, useNavigate } from 'react-router-dom';
import { BarChart3, FileClock, LogOut, Plus, Ruler, Settings, Sparkles, Users } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { confirmLeave } from '../utils/unsavedChanges';

const links = [
  { to: '/dashboard', label: 'Overview', icon: BarChart3 },
  { to: '/upload', label: 'Create pattern', icon: Plus },
  { to: '/history', label: 'Pattern library', icon: FileClock },
  { to: '/customers', label: 'Customers', icon: Users },
  { to: '/measurements', label: 'Measurements', icon: Ruler },
];

// Ask before leaving an unfinished pattern (the wizard marks it as unsaved).
const guard = (event) => { if (!confirmLeave()) event.preventDefault(); };

export default function Sidebar() {
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const { logout } = useAuth();
  const active = (to) => pathname === to || (to === '/history' && pathname.startsWith('/patterns/'));
  return (
    <aside className="sidebar" aria-label="Main navigation">
      <div className="sidebar-label">Workspace</div>
      <nav className="sidebar-nav">
        {links.map(({ to, label, icon: Icon }) => (
          <Link key={to} to={to} onClick={guard} className={'sidebar-item ' + (active(to) ? 'active' : '')}
                aria-current={active(to) ? 'page' : undefined} title={label}>
            <Icon size={19} strokeWidth={1.8}/><span>{label}</span>
          </Link>
        ))}
      </nav>
      <div className="sidebar-label account-label">Account</div>
      <Link to="/settings" onClick={guard} className={'sidebar-item ' + (pathname === '/settings' ? 'active' : '')}
            aria-current={pathname === '/settings' ? 'page' : undefined} title="Settings">
        <Settings size={19} strokeWidth={1.8}/><span>Settings</span>
      </Link>
      <div className="sidebar-research">
        <Sparkles size={17}/>
        <div><strong>Research prototype</strong><small>AI-assisted custom tailoring</small></div>
      </div>
      <button className="sidebar-item logout" title="Sign out"
              onClick={() => { if (confirmLeave()) { logout(); navigate('/auth'); } }}>
        <LogOut size={19}/><span>Sign out</span>
      </button>
    </aside>
  );
}
