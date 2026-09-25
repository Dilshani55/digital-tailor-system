import React, { useState, useEffect } from 'react';
import MannequinViewer3D from './MannequinViewer3D';
import { RotateCcw, Eye, Play, Pause, Info, Award } from 'lucide-react';

export default function MeasurementGuide({ activeField, setActiveField, meas }) {
  const [showModal, setShowModal] = useState(true);
  const [rotationAngle, setRotationAngle] = useState(0);
  const [isAutoSpinning, setIsAutoSpinning] = useState(false);

  const guideData = {
    bust_cm: {
      title: 'Bust Circumference (Full Apex)',
      color: 'var(--text-accent, #2D5A43)',
      tip: 'Place the measuring tape around the fullest part of the bust (across apex points). Ensure the tape passes flat and parallel to the floor across your shoulder blades at the back.',
      dos: [
        'Keep 1 finger under the tape for breathing room',
        'Tape must be horizontal across back',
        'Wear a non-padded fitting bra'
      ],
    },
    waist_cm: {
      title: 'Waist Circumference (Natural Crease)',
      color: 'var(--text-accent, #2D5A43)',
      tip: 'Locate your natural waist by bending gently to one side. Wrap the tape snug around the narrowest crease point (approx. 2.5 cm above navel).',
      dos: [
        'Do not pull tape too tight or hold breath',
        'Breathe out naturally before taking reading',
        'Measure over thin undergarments'
      ],
    },
    hip_cm: {
      title: 'Hip Circumference (Fullest Buttocks)',
      color: 'var(--text-accent, #2D5A43)',
      tip: 'Stand with feet together. Measure around the fullest part of your hips and maximum projection of buttocks (approx. 20 cm below natural waist).',
      dos: [
        'Stand with feet completely touching',
        'Check mirror to confirm tape is horizontal',
        'Ensure tape slides easily over hip curves'
      ],
    },
    height_cm: {
      title: 'Total Body Height (Crown to Heel)',
      color: 'var(--text-accent, #2D5A43)',
      tip: 'Stand barefoot flat against a straight wall with heels, buttocks, and upper back touching the wall. Measure straight down from floor to crown.',
      dos: [
        'Remove shoes and thick hairstyles',
        'Place flat book/ruler on head crown',
        'Look straight ahead horizontally'
      ],
    },
  };

  const activeInfo = guideData[activeField] || guideData.bust_cm;

  // Auto 360° Spin animation loop
  useEffect(() => {
    let interval = null;
    if (isAutoSpinning) {
      interval = setInterval(() => {
        setRotationAngle((prev) => (prev + 1.5) % 360);
      }, 30);
    }
    return () => clearInterval(interval);
  }, [isAutoSpinning]);

  // Compute dynamic view label based on 3D rotation angle
  const getViewLabel = (angle) => {
    const norm = ((angle % 360) + 360) % 360;
    if (norm >= 315 || norm < 45) {
      return `FRONT VIEW (${Math.round(norm)}°)`;
    } else if (norm >= 45 && norm < 135) {
      return `RIGHT SIDE (${Math.round(norm)}°)`;
    } else if (norm >= 135 && norm < 225) {
      return `BACK VIEW (${Math.round(norm)}°)`;
    } else {
      return `LEFT SIDE (${Math.round(norm)}°)`;
    }
  };

  const handlePresetView = (angle) => {
    setIsAutoSpinning(false);
    setRotationAngle(angle);
  };

  return (
    <div style={{
      marginTop: '20px',
      background: 'var(--surface-1, #FFFFFF)',
      border: '1px solid var(--border, #E2E8F0)',
      borderRadius: '12px',
      padding: '20px'
    }}>
      
      {/* Header & Controls Toolbar */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        marginBottom: '16px',
        flexWrap: 'wrap',
        gap: '10px'
      }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ fontSize: '14px', fontWeight: '700', color: 'var(--text-primary, #0F172A)' }}>
              Interactive 3D Female Mannequin Viewer & Protocol
            </span>
            <span style={{
              fontSize: '10px',
              fontWeight: '700',
              padding: '2px 8px',
              borderRadius: '10px',
              background: 'rgba(45, 90, 67, 0.1)',
              color: 'var(--text-accent, #2D5A43)',
              border: '1px solid rgba(45, 90, 67, 0.2)'
            }}>
              Real Three.js WebGL 3D
            </span>
          </div>
          <span style={{ fontSize: '11px', color: 'var(--text-secondary, #64748B)' }}>
            Drag mouse/touch to orbit 3D model, or use presets below. Active measurement field glows in 3D.
          </span>
        </div>

        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
          <button
            type="button"
            onClick={() => setIsAutoSpinning(!isAutoSpinning)}
            className="btn btn-outline"
            style={{
              height: '32px',
              fontSize: '11px',
              padding: '0 12px',
              color: isAutoSpinning ? '#16A34A' : 'var(--text-primary, #0F172A)',
              borderColor: isAutoSpinning ? '#16A34A' : 'var(--border-strong, #CBD5E1)',
              display: 'flex',
              alignItems: 'center',
              gap: '4px'
            }}
          >
            {isAutoSpinning ? <Pause size={14} /> : <Play size={14} />}
            {isAutoSpinning ? 'Pause 360° Spin' : 'Auto 360° Spin'}
          </button>
          
          <button
            type="button"
            onClick={() => setShowModal(!showModal)}
            className="btn btn-outline"
            style={{
              height: '32px',
              fontSize: '11px',
              padding: '0 12px',
              color: showModal ? 'var(--text-accent, #2D5A43)' : 'var(--text-secondary, #64748B)'
            }}
          >
            {showModal ? 'Hide Protocol Guidelines' : 'Show Protocol Guidelines'}
          </button>
        </div>
      </div>

      {/* Main 3D Canvas Box + Live Field Protocol Panel */}
      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(260px, 300px) 1fr', gap: '20px', alignItems: 'stretch' }}>
        
        {/* Interactive 3D Mannequin Canvas Container */}
        <div style={{
          position: 'relative',
          width: '100%',
          height: '340px',
          background: 'radial-gradient(circle at center, #1E293B 0%, #0F172A 100%)',
          borderRadius: '12px',
          border: '1px solid var(--border-strong, #334155)',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '8px',
          overflow: 'hidden',
          boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.3)'
        }}>
          
          {/* Dynamic 360° Angle Status Badge */}
          <div style={{
            position: 'absolute',
            top: '10px',
            left: '10px',
            fontSize: '10px',
            fontFamily: 'monospace',
            fontWeight: '700',
            color: '#52B788',
            zIndex: 10,
            background: 'rgba(15, 23, 42, 0.85)',
            padding: '4px 10px',
            borderRadius: '6px',
            border: '1px solid #2D5A43',
            backdropFilter: 'blur(4px)',
            boxShadow: '0 2px 4px rgba(0,0,0,0.3)'
          }}>
            {getViewLabel(rotationAngle)}
          </div>

          {/* Preset Camera View Quick Buttons Overlay */}
          <div style={{
            position: 'absolute',
            top: '10px',
            right: '10px',
            display: 'flex',
            flexDirection: 'column',
            gap: '4px',
            zIndex: 10
          }}>
            <button
              title="Front View (0°)"
              onClick={() => handlePresetView(0)}
              style={{
                background: Math.abs(rotationAngle % 360) < 15 ? '#2D5A43' : 'rgba(15, 23, 42, 0.8)',
                color: '#FFFFFF',
                border: '1px solid #334155',
                borderRadius: '4px',
                padding: '2px 6px',
                fontSize: '9px',
                fontWeight: '600',
                cursor: 'pointer'
              }}
            >
              Front (0°)
            </button>
            <button
              title="Right Side (90°)"
              onClick={() => handlePresetView(90)}
              style={{
                background: Math.abs((rotationAngle - 90) % 360) < 15 ? '#2D5A43' : 'rgba(15, 23, 42, 0.8)',
                color: '#FFFFFF',
                border: '1px solid #334155',
                borderRadius: '4px',
                padding: '2px 6px',
                fontSize: '9px',
                fontWeight: '600',
                cursor: 'pointer'
              }}
            >
              Right (90°)
            </button>
            <button
              title="Back View (180°)"
              onClick={() => handlePresetView(180)}
              style={{
                background: Math.abs((rotationAngle - 180) % 360) < 15 ? '#2D5A43' : 'rgba(15, 23, 42, 0.8)',
                color: '#FFFFFF',
                border: '1px solid #334155',
                borderRadius: '4px',
                padding: '2px 6px',
                fontSize: '9px',
                fontWeight: '600',
                cursor: 'pointer'
              }}
            >
              Back (180°)
            </button>
            <button
              title="Left Side (270°)"
              onClick={() => handlePresetView(270)}
              style={{
                background: Math.abs((rotationAngle - 270) % 360) < 15 ? '#2D5A43' : 'rgba(15, 23, 42, 0.8)',
                color: '#FFFFFF',
                border: '1px solid #334155',
                borderRadius: '4px',
                padding: '2px 6px',
                fontSize: '9px',
                fontWeight: '600',
                cursor: 'pointer'
              }}
            >
              Left (270°)
            </button>
          </div>

          {/* Real 3D Mannequin R3F WebGL View Component */}
          <div style={{ width: '100%', height: '270px', position: 'relative' }}>
            <MannequinViewer3D
              activeField={activeField}
              rotationAngle={rotationAngle}
              onAngleChange={(newAngle) => setRotationAngle(newAngle)}
              isAutoSpinning={isAutoSpinning}
              modelPath="/models/female-mannequin.glb"
            />
          </div>

          {/* Controls Footer: 0-360 Slider & Reset View */}
          <div style={{
            width: '100%',
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
            padding: '4px 8px',
            background: 'rgba(15, 23, 42, 0.9)',
            borderRadius: '8px',
            border: '1px solid #334155'
          }}>
            <input
              type="range"
              min="0"
              max="360"
              value={rotationAngle % 360}
              onChange={(e) => {
                setIsAutoSpinning(false);
                setRotationAngle(parseFloat(e.target.value));
              }}
              style={{ flex: 1, height: '4px', accentColor: '#52B788', cursor: 'pointer' }}
              aria-label="3D Model Rotation Angle Slider"
            />

            <button
              type="button"
              onClick={() => {
                setIsAutoSpinning(false);
                setRotationAngle(0);
              }}
              title="Reset View to 0° Front"
              style={{
                background: 'transparent',
                border: '1px solid #475569',
                color: '#94A3B8',
                borderRadius: '4px',
                padding: '2px 6px',
                fontSize: '10px',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '2px'
              }}
            >
              <RotateCcw size={11} /> Reset
            </button>
          </div>

        </div>

        {/* Live Active Field Instruction Box + 3D Marker Metrics Dashboard */}
        <div style={{
          background: 'var(--surface-1, #FFFFFF)',
          borderRadius: '12px',
          padding: '18px',
          border: '1px solid var(--border, #E2E8F0)',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'space-between'
        }}>
          <div>
            {/* Live Anatomical 3D Marker Metrics Badges */}
            <div style={{ marginBottom: '16px' }}>
              <div style={{ fontSize: '12px', fontWeight: '700', color: 'var(--text-accent, #2D5A43)', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: '8px' }}>
                3D Model Marked Measurements
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '8px' }}>
                {[
                  { id: 'bust_cm', label: 'Bust', val: meas?.bust_cm, color: '#2D5A43' },
                  { id: 'waist_cm', label: 'Waist', val: meas?.waist_cm, color: '#15803D' },
                  { id: 'hip_cm', label: 'Hip', val: meas?.hip_cm, color: '#047857' },
                  { id: 'height_cm', label: 'Height', val: meas?.height_cm, color: '#1E3A2B' }
                ].map((item) => {
                  const isActive = activeField === item.id;
                  return (
                    <div
                      key={item.id}
                      onClick={() => setActiveField && setActiveField(item.id)}
                      style={{
                        padding: '8px 10px',
                        borderRadius: '8px',
                        border: isActive ? '2px solid #16A34A' : '1px solid var(--border, #E2E8F0)',
                        background: isActive ? '#F0FDF4' : 'var(--surface-2, #F8FAFC)',
                        cursor: 'pointer',
                        display: 'flex',
                        flexDirection: 'column',
                        gap: '2px',
                        transition: 'all 0.15s ease-in-out'
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <span style={{ fontSize: '11px', fontWeight: '600', color: isActive ? '#15803D' : 'var(--text-secondary, #64748B)' }}>
                          {item.label}
                        </span>
                        {isActive && <span style={{ fontSize: '9px', fontWeight: '700', color: '#16A34A', background: '#DCFCE7', padding: '1px 5px', borderRadius: '4px' }}>Active Ring</span>}
                      </div>
                      <strong style={{ fontSize: '13px', color: 'var(--text-primary, #0F172A)' }}>
                        {item.val ? `${item.val} cm` : 'Not entered'}
                      </strong>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Active Instruction Header & Protocol */}
            <div style={{ fontSize: '14px', fontWeight: '700', color: activeInfo.color, marginBottom: '6px' }}>
              {activeInfo.title}
            </div>
            <p style={{ fontSize: '12px', color: 'var(--text-secondary, #475569)', lineHeight: '1.5', margin: 0 }}>
              {activeInfo.tip}
            </p>
            <div style={{ marginTop: '12px', display: 'flex', flexDirection: 'column', gap: '5px' }}>
              {activeInfo.dos.map((doTip, i) => (
                <div key={i} style={{
                  fontSize: '11px',
                  background: 'var(--surface-2, #F8FAFC)',
                  color: 'var(--text-primary, #0F172A)',
                  padding: '5px 10px',
                  borderRadius: '6px',
                  border: '1px solid var(--border, #E2E8F0)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px'
                }}>
                  <span style={{ color: '#16A34A', fontWeight: 'bold' }}>✓</span> {doTip}
                </div>
              ))}
            </div>
          </div>

          {/* Model Asset Attribution Footer */}
          <div style={{
            marginTop: '16px',
            paddingTop: '10px',
            borderTop: '1px stroke #E2E8F0',
            fontSize: '10px',
            color: 'var(--text-secondary, #64748B)',
            display: 'flex',
            alignItems: 'center',
            gap: '6px'
          }}>
            <Award size={13} style={{ color: 'var(--text-accent, #2D5A43)' }} />
            <span>
              Licensed 3D Female Mannequin Model: <strong>CC-BY 4.0 Creative Commons Open Tailoring Asset</strong>
            </span>
          </div>

        </div>

      </div>

      {/* Standard Master Tailoring Protocol Cards & Ease Rules */}
      {showModal && (
        <div style={{ marginTop: '20px', paddingTop: '16px', borderTop: '1px solid var(--border, #E2E8F0)' }}>
          <div style={{
            fontSize: '13px',
            fontWeight: '700',
            color: 'var(--text-primary, #0F172A)',
            marginBottom: '12px',
            display: 'flex',
            justify: 'space-between',
            alignItems: 'center'
          }}>
            <span>Winifred Aldrich Standard Measurement Protocol</span>
            <span style={{ fontSize: '11px', color: 'var(--text-accent, #2D5A43)', fontWeight: '600' }}>
              Sri Lankan Master Tailoring Guidelines
            </span>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '12px', fontSize: '12px' }}>
            
            {/* Bust Protocol */}
            <div style={{ background: 'var(--surface-2, #F8FAFC)', border: '1px solid var(--border, #E2E8F0)', padding: '12px', borderRadius: '8px' }}>
              <div style={{ color: 'var(--text-accent, #2D5A43)', fontWeight: '700', marginBottom: '4px' }}>Bust Circumference</div>
              <p style={{ color: 'var(--text-secondary, #475569)', fontSize: '11px', lineHeight: '1.5', margin: 0 }}>
                Measure horizontally around the fullest part of bust across apex points. Keep measuring tape level and flat across shoulder blades.
              </p>
            </div>

            {/* Waist Protocol */}
            <div style={{ background: 'var(--surface-2, #F8FAFC)', border: '1px solid var(--border, #E2E8F0)', padding: '12px', borderRadius: '8px' }}>
              <div style={{ color: '#15803D', fontWeight: '700', marginBottom: '4px' }}>Waist Circumference</div>
              <p style={{ color: 'var(--text-secondary, #475569)', fontSize: '11px', lineHeight: '1.5', margin: 0 }}>
                Measure around natural waist crease (approx. 2.5 cm above navel). Keep tape comfortable with 1 finger allowance. Breathe out naturally.
              </p>
            </div>

            {/* Hip Protocol */}
            <div style={{ background: 'var(--surface-2, #F8FAFC)', border: '1px solid var(--border, #E2E8F0)', padding: '12px', borderRadius: '8px' }}>
              <div style={{ color: '#047857', fontWeight: '700', marginBottom: '4px' }}>Hip Circumference</div>
              <p style={{ color: 'var(--text-secondary, #475569)', fontSize: '11px', lineHeight: '1.5', margin: 0 }}>
                Stand with feet together. Wrap tape around maximum projection of buttocks (20 cm below natural waistline). Ensure tape is parallel to floor.
              </p>
            </div>

            {/* Height Protocol */}
            <div style={{ background: 'var(--surface-2, #F8FAFC)', border: '1px solid var(--border, #E2E8F0)', padding: '12px', borderRadius: '8px' }}>
              <div style={{ color: '#1E3A2B', fontWeight: '700', marginBottom: '4px' }}>Total Body Height</div>
              <p style={{ color: 'var(--text-secondary, #475569)', fontSize: '11px', lineHeight: '1.5', margin: 0 }}>
                Stand barefoot with heels against a flat wall. Measure vertically from floor to crown of head using a flat ruler guide.
              </p>
            </div>

          </div>

          {/* Ease Allowance Reference Note */}
          <div style={{
            marginTop: '12px',
            background: 'var(--surface-2, #F8FAFC)',
            border: '1px solid var(--border, #E2E8F0)',
            borderRadius: '8px',
            padding: '10px 14px',
            fontSize: '11px',
            color: 'var(--text-primary, #0F172A)',
            display: 'flex',
            justify: 'space-between',
            flexWrap: 'wrap',
            gap: '8px'
          }}>
            <span><strong>Automatic Ease Allowances (Aldrich Method):</strong></span>
            <span>Woven: +10cm Bust / +8cm Waist / +10cm Hip</span>
            <span>Knit: +6cm Bust / +4cm Waist / +6cm Hip</span>
            <span>Stretch: -2cm Ease</span>
          </div>

        </div>
      )}

    </div>
  );
}
