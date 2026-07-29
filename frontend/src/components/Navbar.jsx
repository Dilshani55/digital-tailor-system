import { useState, useEffect, useRef } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { patternsAPI, exportAPI } from '../services/api';

export default function Navbar() {
  const { user, logout }       = useAuth();
  const navigate               = useNavigate();
  const location               = useLocation();
  const [showProfile, setShowProfile] = useState(false);
  const [stats, setStats]       = useState({ patterns: 0, exports: 0 });
  const dropdownRef            = useRef(null);

  const handleLogout = () => {
    logout();
    setShowProfile(false);
    navigate('/login');
  };

  const isActive = (path) => location.pathname === path;

  // Get user initials for avatar
  const initials = user?.full_name
    ? user.full_name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2)
    : 'DV';

  // Fetch quick stats for profile dropdown
  useEffect(() => {
    if (user) {
      Promise.all([
        patternsAPI.getAll().catch(() => ({ data: { total: 0 } })),
        exportAPI.getAll().catch(() => ({ data: { total: 0 } })),
      ]).then(([pRes, eRes]) => {
        setStats({
          patterns: pRes.data.total || pRes.data.patterns?.length || 0,
          exports:  eRes.data.total || eRes.data.exports?.length || 0,
        });
      });
    }
  }, [user]);

  // Close dropdown on outside click
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setShowProfile(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  return (
    <nav className="nav" style={{ position: 'relative', zIndex: 100 }}>
      <Link to="/dashboard" className="nav-logo">
        Digital Tailor System
      </Link>
      
      {user && (
        <div className="nav-links">
          <Link
            to="/dashboard"
            className={`nav-link ${isActive('/dashboard') ? 'active' : ''}`}
          >
            Dashboard
          </Link>
          <Link
            to="/upload"
            className={`nav-link ${isActive('/upload') ? 'active' : ''}`}
          >
            New pattern
          </Link>
          <Link
            to="/history"
            className={`nav-link ${isActive('/history') ? 'active' : ''}`}
          >
            History
          </Link>
        </div>
      )}

      <div className="nav-user" ref={dropdownRef} style={{ position: 'relative' }}>
        {user ? (
          <>
            {/* Clickable User Badge */}
            <div
              onClick={() => setShowProfile(!showProfile)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                cursor: 'pointer',
                padding: '4px 10px',
                borderRadius: '20px',
                background: showProfile ? '#1E293B' : 'transparent',
                transition: '.15s',
                userSelect: 'none'
              }}
            >
              <span className="nav-name">{user.full_name}</span>
              <div className="nav-avatar">{initials}</div>
            </div>

            {/* Profile Details Dropdown Card */}
            {showProfile && (
              <div
                style={{
                  position: 'absolute',
                  top: '44px',
                  right: '0',
                  width: '280px',
                  background: '#0F172A',
                  border: '1px solid #334155',
                  borderRadius: '12px',
                  boxShadow: '0 10px 25px -5px rgba(0, 0, 0, 0.5)',
                  padding: '16px',
                  zIndex: 200,
                  color: '#F8FAFC',
                  fontSize: '13px'
                }}
              >
                {/* Header */}
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px', paddingBottom: '12px', borderBottom: '1px solid #1E293B' }}>
                  <div
                    style={{
                      width: '42px',
                      height: '42px',
                      borderRadius: '50%',
                      background: '#2563EB',
                      color: '#FFFFFF',
                      fontSize: '15px',
                      fontWeight: '600',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      flexShrink: 0
                    }}
                  >
                    {initials}
                  </div>
                  <div style={{ overflow: 'hidden' }}>
                    <div style={{ fontWeight: '600', fontSize: '14px', color: '#F8FAFC', whiteSpace: 'nowrap', textOverflow: 'ellipsis', overflow: 'hidden' }}>
                      {user.full_name}
                    </div>
                    <div style={{ fontSize: '12px', color: '#94A3B8', whiteSpace: 'nowrap', textOverflow: 'ellipsis', overflow: 'hidden' }}>
                      {user.email}
                    </div>
                    <span style={{ display: 'inline-block', marginTop: '4px', fontSize: '10px', fontWeight: '600', background: '#064E3B', color: '#34D399', padding: '2px 8px', borderRadius: '10px' }}>
                      Tailor Member
                    </span>
                  </div>
                </div>

                {/* Account Details */}
                <div style={{ padding: '12px 0', borderBottom: '1px solid #1E293B', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  <div style={{ display: 'flex', justify: 'space-between', fontSize: '12px' }}>
                    <span style={{ color: '#94A3B8' }}>User ID:</span>
                    <span style={{ fontFamily: 'monospace', fontWeight: '500', color: '#CBD5E1' }}>
                      {user.id ? user.id.slice(-8) : 'usr_28404'}
                    </span>
                  </div>
                  <div style={{ display: 'flex', justify: 'space-between', fontSize: '12px' }}>
                    <span style={{ color: '#94A3B8' }}>Generated Patterns:</span>
                    <span style={{ fontWeight: '600', color: '#38BDF8' }}>{stats.patterns}</span>
                  </div>
                  <div style={{ display: 'flex', justify: 'space-between', fontSize: '12px' }}>
                    <span style={{ color: '#94A3B8' }}>PDF Exports:</span>
                    <span style={{ fontWeight: '600', color: '#34D399' }}>{stats.exports}</span>
                  </div>
                </div>

                {/* Quick Menu Actions */}
                <div style={{ paddingTop: '8px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                  <button
                    onClick={() => {
                      setShowProfile(false);
                      navigate('/measurements');
                    }}
                    style={{
                      width: '100%',
                      textAlign: 'left',
                      padding: '8px 10px',
                      borderRadius: '6px',
                      background: 'transparent',
                      border: 'none',
                      cursor: 'pointer',
                      fontSize: '12px',
                      color: '#CBD5E1',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px',
                      transition: '.15s'
                    }}
                    onMouseEnter={(e) => e.currentTarget.style.background = '#1E293B'}
                    onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
                  >
                    My Body Measurements
                  </button>

                  <button
                    onClick={() => {
                      setShowProfile(false);
                      navigate('/history');
                    }}
                    style={{
                      width: '100%',
                      textAlign: 'left',
                      padding: '8px 10px',
                      borderRadius: '6px',
                      background: 'transparent',
                      border: 'none',
                      cursor: 'pointer',
                      fontSize: '12px',
                      color: '#CBD5E1',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px',
                      transition: '.15s'
                    }}
                    onMouseEnter={(e) => e.currentTarget.style.background = '#1E293B'}
                    onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
                  >
                    Pattern Export History
                  </button>

                  <button
                    onClick={handleLogout}
                    style={{
                      width: '100%',
                      textAlign: 'left',
                      padding: '8px 10px',
                      borderRadius: '6px',
                      background: '#7F1D1D',
                      border: 'none',
                      cursor: 'pointer',
                      fontSize: '12px',
                      color: '#FECACA',
                      fontWeight: '500',
                      marginTop: '4px',
                      transition: '.15s'
                    }}
                  >
                    Sign Out
                  </button>
                </div>
              </div>
            )}
          </>
        ) : (
          <Link to="/login" className="nav-link">
            Login
          </Link>
        )}
      </div>
    </nav>
  );
}
