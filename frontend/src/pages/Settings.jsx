import { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { Check, Database, Save, Sparkles, User } from 'lucide-react';

export default function Settings() {
  const { user } = useAuth();
  
  // Local state for settings form
  const [profile, setProfile] = useState({
    name: user?.full_name || 'Dilshani Vitharana',
    email: user?.email || 'dilshani@email.com',
    password: ''
  });

  const [presets, setPresets] = useState({
    seam_allowance: '1.5',
    default_ease: '2.0',
    default_unit: 'cm',
    fabric_layout_padding: '1.0'
  });

  const [subtheme, setSubtheme] = useState('light-sage');
  const [saveSuccess, setSaveSuccess] = useState(false);

  const handleProfileSave = (e) => {
    e.preventDefault();
    setSaveSuccess(true);
    setTimeout(() => setSaveSuccess(false), 3000);
  };

  return (
    <div style={{ padding: '24px', maxWidth: '1000px', margin: '0 auto' }}>
      
      {/* Header */}
      <div style={{ marginBottom: '24px' }}>
        <h1 style={{ fontSize: '22px', fontWeight: '700', color: 'var(--text-primary)', marginBottom: '4px' }}>
          Settings & Preferences
        </h1>
        <p style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>
          Configure drafting presets, tailoring defaults, subtheme palettes, and account settings.
        </p>
      </div>

      {saveSuccess && (
        <div style={{ padding: '12px 16px', background: 'rgba(21, 128, 61, 0.2)', border: '1px solid var(--text-accent)', borderRadius: '8px', color: 'var(--text-accent)', fontSize: '13px', marginBottom: '20px', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Check size={16}/> Settings saved and synchronized successfully!
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: '24px' }}>
        
        {/* Left Column: Preset Defaults & System Status */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
          
          {/* Preset Tailor Geometry Defaults Card */}
          <div className="ui-card" style={{ padding: '24px' }}>
            <h2 style={{ fontSize: '14px', fontWeight: '600', color: 'var(--text-primary)', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Sparkles size={16} /> Tailor drafting geometry defaults
            </h2>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px' }}>
              <div>
                <label className="form-label">Default Seam Allowance</label>
                <select 
                  className="form-input"
                  value={presets.seam_allowance}
                  onChange={(e) => setPresets({ ...presets, seam_allowance: e.target.value })}
                >
                  <option value="1.0">1.0 cm (Narrow seams)</option>
                  <option value="1.5">1.5 cm (Standard Winifred Aldrich)</option>
                  <option value="2.0">2.0 cm (Generous fit allowance)</option>
                </select>
              </div>

              <div>
                <label className="form-label">Default Wearing Ease</label>
                <select 
                  className="form-input"
                  value={presets.default_ease}
                  onChange={(e) => setPresets({ ...presets, default_ease: e.target.value })}
                >
                  <option value="0.0">0.0 cm (Skin-tight/Stretch knit)</option>
                  <option value="2.0">2.0 cm (Standard snug ease)</option>
                  <option value="4.0">4.0 cm (Loose casual ease)</option>
                </select>
              </div>

              <div>
                <label className="form-label">Preferred Measurement Unit</label>
                <div style={{ display: 'flex', gap: '8px', marginTop: '4px' }}>
                  <button 
                    type="button" 
                    className="btn" 
                    style={{ 
                      flex: 1, height: '36px', fontSize: '12px',
                      background: presets.default_unit === 'cm' ? 'var(--text-accent)' : 'var(--surface-2)',
                      color: presets.default_unit === 'cm' ? '#FFF' : 'var(--text-primary)',
                      border: presets.default_unit === 'cm' ? 'none' : '1px solid var(--border)'
                    }}
                    onClick={() => setPresets({ ...presets, default_unit: 'cm' })}
                  >
                    Centimeters (cm)
                  </button>
                  <button 
                    type="button" 
                    className="btn" 
                    style={{ 
                      flex: 1, height: '36px', fontSize: '12px',
                      background: presets.default_unit === 'in' ? 'var(--text-accent)' : 'var(--surface-2)',
                      color: presets.default_unit === 'in' ? '#FFF' : 'var(--text-primary)',
                      border: presets.default_unit === 'in' ? 'none' : '1px solid var(--border)'
                    }}
                    onClick={() => setPresets({ ...presets, default_unit: 'in' })}
                  >
                    Inches (in)
                  </button>
                </div>
              </div>

              <div>
                <label className="form-label">Nesting Piece Margin (Gap)</label>
                <input 
                  type="number" 
                  className="form-input" 
                  step="0.5"
                  value={presets.fabric_layout_padding}
                  onChange={(e) => setPresets({ ...presets, fabric_layout_padding: e.target.value })}
                />
              </div>
            </div>
          </div>

          {/* Database System Connection Status Card */}
          <div className="ui-card" style={{ padding: '24px' }}>
            <h2 style={{ fontSize: '14px', fontWeight: '600', color: 'var(--text-primary)', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Database size={16} /> Database connection status
            </h2>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', fontSize: '13px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border)', paddingBottom: '8px' }}>
                <span style={{ color: 'var(--text-secondary)' }}>MongoDB Host:</span>
                <span style={{ fontFamily: 'monospace', fontWeight: '600' }}>localhost:27017</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border)', paddingBottom: '8px' }}>
                <span style={{ color: 'var(--text-secondary)' }}>Database Name:</span>
                <span style={{ fontFamily: 'monospace', fontWeight: '600' }}>digital_tailor_db</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ color: 'var(--text-secondary)' }}>Status:</span>
                <span style={{ background: 'rgba(21, 128, 61, 0.2)', color: 'var(--text-accent)', fontWeight: 'bold', fontSize: '11px', padding: '3px 8px', borderRadius: '4px', border: '1px solid var(--text-accent)' }}>
                  ONLINE & CONNECTED
                </span>
              </div>
            </div>
          </div>

        </div>

        {/* Right Column: User Profile & Visual Subthemes */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
          
          {/* User Account Settings */}
          <div className="ui-card" style={{ padding: '24px' }}>
            <h2 style={{ fontSize: '14px', fontWeight: '600', color: 'var(--text-primary)', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <User size={16} /> User details
            </h2>

            <form onSubmit={handleProfileSave} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              <div>
                <label className="form-label">Full Name</label>
                <input 
                  type="text" 
                  className="form-input" 
                  value={profile.name}
                  onChange={(e) => setProfile({ ...profile, name: e.target.value })}
                />
              </div>

              <div>
                <label className="form-label">Email Address</label>
                <input 
                  type="email" 
                  className="form-input" 
                  value={profile.email}
                  disabled
                />
              </div>

              <div>
                <label className="form-label">Update Password</label>
                <input 
                  type="password" 
                  className="form-input" 
                  placeholder="Enter new password"
                  value={profile.password}
                  onChange={(e) => setProfile({ ...profile, password: e.target.value })}
                />
              </div>

              <button 
                type="submit" 
                className="btn btn-primary"
                style={{ background: 'var(--text-accent)', width: '100%', marginTop: '8px', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px' }}
              >
                <Save size={16}/> Save changes
              </button>
            </form>
          </div>

          {/* Subtheme customization */}
          <div className="ui-card" style={{ padding: '24px' }}>
            <h2 style={{ fontSize: '14px', fontWeight: '600', color: 'var(--text-primary)', marginBottom: '16px' }}>
              Workspace palette customization
            </h2>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              <div 
                style={{ 
                  display: 'flex', justify: 'space-between', alignItems: 'center', 
                  padding: '10px 12px', border: '1px solid var(--border)', borderRadius: '8px',
                  background: subtheme === 'light-sage' ? 'var(--surface-2)' : 'transparent',
                  cursor: 'pointer'
                }}
                onClick={() => setSubtheme('light-sage')}
              >
                <div>
                  <strong style={{ display: 'block', fontSize: '12px' }}>Light Sage (Default)</strong>
                  <span style={{ fontSize: '10px', color: 'var(--text-muted)' }}>Off-white base background and green accents</span>
                </div>
                <div style={{ display: 'flex', gap: '4px' }}>
                  <span style={{ width: '12px', height: '12px', borderRadius: '50%', background: '#F4F6F3' }}/>
                  <span style={{ width: '12px', height: '12px', borderRadius: '50%', background: '#2A6F4E' }}/>
                </div>
              </div>

              <div 
                style={{ 
                  display: 'flex', justify: 'space-between', alignItems: 'center', 
                  padding: '10px 12px', border: '1px solid var(--border)', borderRadius: '8px',
                  background: subtheme === 'emerald-forest' ? 'var(--surface-2)' : 'transparent',
                  cursor: 'pointer'
                }}
                onClick={() => setSubtheme('emerald-forest')}
              >
                <div>
                  <strong style={{ display: 'block', fontSize: '12px' }}>Emerald Forest</strong>
                  <span style={{ fontSize: '10px', color: 'var(--text-muted)' }}>Warm cream base background with deep emerald accents</span>
                </div>
                <div style={{ display: 'flex', gap: '4px' }}>
                  <span style={{ width: '12px', height: '12px', borderRadius: '50%', background: '#FAF9F6' }}/>
                  <span style={{ width: '12px', height: '12px', borderRadius: '50%', background: '#0F5132' }}/>
                </div>
              </div>
            </div>
          </div>

        </div>

      </div>

    </div>
  );
}
