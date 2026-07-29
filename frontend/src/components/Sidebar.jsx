import { useState, useEffect } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { exportAPI, measurementsAPI } from '../services/api';

export default function Sidebar() {
  const location = useLocation();
  const navigate = useNavigate();
  const { logout, user } = useAuth();
  const [historyCount, setHistoryCount] = useState(0);
  const [measurementsCount, setMeasurementsCount] = useState(0);

  const isActive = (path) => location.pathname === path;

  // Fetch dynamic history count and measurements count from API
  useEffect(() => {
    if (user) {
      exportAPI.getAll()
        .then((res) => {
          setHistoryCount(res.data.total || res.data.exports?.length || 0);
        })
        .catch(() => setHistoryCount(0));

      measurementsAPI.getAll()
        .then((res) => {
          setMeasurementsCount(res.data.total || res.data.measurements?.length || 0);
        })
        .catch(() => setMeasurementsCount(0));
    }
  }, [user, location.pathname]);

  return (
    <aside className="sidebar">
      <div className="sidebar-section">Main</div>
      
      <Link
        to="/dashboard"
        className={`sidebar-item ${isActive('/dashboard') ? 'active' : ''}`}
      >
        Dashboard
      </Link>

      <Link
        to="/upload"
        className={`sidebar-item ${isActive('/upload') ? 'active' : ''}`}
      >
        New pattern
      </Link>

      <Link
        to="/history"
        className={`sidebar-item ${isActive('/history') ? 'active' : ''}`}
      >
        History
        <span className="sidebar-badge">{historyCount}</span>
      </Link>

      <div className="sidebar-section">Account</div>

      <Link
        to="/measurements"
        className={`sidebar-item ${isActive('/measurements') ? 'active' : ''}`}
      >
        Measurements
        <span className="sidebar-badge" style={{ background: '#1E293B', color: '#38BDF8', border: '1px solid #334155' }}>
          {measurementsCount}
        </span>
      </Link>

      <div className="sidebar-item">
        Settings
      </div>

      <div
        className="sidebar-item"
        onClick={() => {
          logout();
          navigate('/login');
        }}
      >
        Logout
      </div>
    </aside>
  );
}
