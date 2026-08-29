import { Link, useLocation, useNavigate } from 'react-router-dom';
import { BarChart3, FileClock, LogOut, Plus, Ruler, Settings, Sparkles, Users, Database } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

const links = [
  { to: '/dashboard', label: 'Overview', icon: BarChart3 },
  { to: '/upload', label: 'Create pattern', icon: Plus },
  { to: '/history', label: 'Pattern library', icon: FileClock },
  { to: '/customers', label: 'Customers', icon: Users },
  { to: '/measurements', label: 'Measurements', icon: Ruler },
  { to: '/researcher', label: 'Researcher Metrics', icon: Database },
];

export default function Sidebar() {
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const { logout } = useAuth();
  return (
    <aside className="sidebar">
      <div className="sidebar-label">Workspace</div>
      <nav className="sidebar-nav">
        {links.map(({ to, label, icon: Icon }) => (
          <Link key={to} to={to} className={'sidebar-item ' + (pathname === to ? 'active' : '')}>
            <Icon size={18} strokeWidth={1.8}/><span>{label}</span>
          </Link>
        ))}
      </nav>
      <div className="sidebar-label account-label">Account</div>
      <Link to="/settings" className={'sidebar-item ' + (pathname === '/settings' ? 'active' : '')}>
        <Settings size={18}/><span>Settings</span>
      </Link>
      <div className="sidebar-research">
        <Sparkles size={17}/>
        <div><strong>Research prototype</strong><small>AI-assisted custom tailoring</small></div>
      </div>
      <button className="sidebar-item logout" onClick={() => { logout(); navigate('/auth'); }}>
        <LogOut size={18}/><span>Sign out</span>
      </button>
    </aside>
  );
}
