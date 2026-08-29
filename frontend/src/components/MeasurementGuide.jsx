import { useState, useEffect } from 'react';

export default function MeasurementGuide({ activeField }) {
  const [showModal, setShowModal] = useState(true);
  const [rotationAngle, setRotationAngle] = useState(0);
  const [isAutoSpinning, setIsAutoSpinning] = useState(true);

  const guideData = {
    bust_cm: {
      title: 'Bust Circumference (Full Apex)',
      color: 'var(--text-accent)',
      tip: 'Place the measuring tape around the fullest part of the bust (across apex points). Ensure the tape passes flat and parallel to the floor across your shoulder blades at the back.',
      dos: [
        'Keep 1 finger under the tape for breathing room',
        'Tape must be horizontal across back',
        'Wear a non-padded fitting bra'
      ],
    },
    waist_cm: {
      title: 'Waist Circumference (Natural Crease)',
      color: 'var(--text-accent)',
      tip: 'Locate your natural waist by bending gently to one side. Wrap the tape snug around the narrowest crease point (approx. 2.5 cm above navel).',
      dos: [
        'Do not pull tape too tight or hold breath',
        'Breathe out naturally before taking reading',
        'Measure over thin undergarments'
      ],
    },
    hip_cm: {
      title: 'Hip Circumference (Fullest Buttocks)',
      color: 'var(--text-accent)',
      tip: 'Stand with feet together. Measure around the fullest part of your hips and maximum projection of buttocks (approx. 20 cm below natural waist).',
      dos: [
        'Stand with feet completely touching',
        'Check mirror to confirm tape is horizontal',
        'Ensure tape slides easily over hip curves'
      ],
    },
    height_cm: {
      title: 'Total Body Height (Crown to Heel)',
      color: 'var(--text-accent)',
      tip: 'Stand barefoot flat against a straight wall with heels, buttocks, and upper back touching the wall. Measure straight down from floor to crown.',
      dos: [
        'Remove shoes and thick hairstyles',
        'Place flat book/ruler on head crown',
        'Look straight ahead horizontally'
      ],
    },
  };

  const activeInfo = guideData[activeField] || guideData.bust_cm;

  // Continuous Auto-Spin Loop
  useEffect(() => {
    let interval = null;
    if (isAutoSpinning) {
      interval = setInterval(() => {
        setRotationAngle((prev) => (prev + 2) % 360);
      }, 35);
    }
    return () => clearInterval(interval);
  }, [isAutoSpinning]);

  const isBackView = rotationAngle > 90 && rotationAngle < 270;
  const viewAngle = isBackView ? rotationAngle - 180 : rotationAngle;
  const perspectiveScaleX = Math.cos((viewAngle * Math.PI) / 180);

  return (
    <div style={{ marginTop: '20px', background: 'var(--surface-1)', border: '1px solid var(--border)', borderRadius: '12px', padding: '18px' }}>
      
      {/* Laser & Glowing Keyframe Animations */}
      <style>{`
        @keyframes laserScanner {
          0% { top: 10px; opacity: 0.15; }
          50% { top: 220px; opacity: 0.85; }
          100% { top: 10px; opacity: 0.15; }
        }
        .laser-line {
          position: absolute;
          left: 10px;
          right: 10px;
          height: 2px;
          background: linear-gradient(90deg, transparent, var(--text-accent), transparent);
          box-shadow: 0 0 10px var(--text-accent);
          animation: laserScanner 3.5s linear infinite;
          z-index: 10;
          pointer-events: none;
        }
      `}</style>

      {/* Header & Controls */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '14px', flexWrap: 'wrap', gap: '10px' }}>
        <div>
          <span style={{ fontSize: '13px', fontWeight: '600', color: 'var(--text-primary)' }}>
            Interactive 360° Fashion Model & Measurement Protocol
          </span>
        </div>
        <div style={{ display: 'flex', gap: '8px' }}>
          <button
            type="button"
            onClick={() => setIsAutoSpinning(!isAutoSpinning)}
            className="btn btn-outline"
            style={{ height: '30px', fontSize: '11px', padding: '0 12px', color: isAutoSpinning ? 'var(--text-accent)' : 'var(--text-muted)', borderColor: isAutoSpinning ? 'var(--text-accent)' : 'var(--border)' }}
          >
            {isAutoSpinning ? 'Pause 360° Spin' : 'Auto 360° Spin'}
          </button>
          <button
            type="button"
            onClick={() => setShowModal(!showModal)}
            className="btn btn-outline"
            style={{ height: '30px', fontSize: '11px', padding: '0 12px', color: showModal ? 'var(--text-accent)' : 'var(--text-muted)' }}
          >
            {showModal ? 'Hide Tips Protocol' : 'Show Tips Protocol'}
          </button>
        </div>
      </div>

      {/* Barefoot Female Model Container + Active Field Instruction Box */}
      <div style={{ display: 'grid', gridTemplateColumns: '220px 1fr', gap: '20px', alignItems: 'center' }}>
        
        {/* Barefoot Model Box Canvas */}
        <div style={{ position: 'relative', width: '220px', height: '270px', margin: '0 auto', background: 'radial-gradient(circle at center, #1C2E24 0%, #111111 100%)', borderRadius: '12px', border: '1px solid var(--border)', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '6px', overflow: 'hidden', perspective: '800px' }}>
          
          {/* Laser Scanner Beam */}
          <div className="laser-line"></div>

          {/* 360° View Indicator Label */}
          <div style={{ position: 'absolute', top: '8px', left: '10px', fontSize: '10px', fontFamily: 'monospace', fontWeight: '600', color: 'var(--text-accent)', zIndex: 12, background: 'rgba(15, 23, 42, 0.85)', padding: '2px 8px', borderRadius: '4px', border: '1px solid var(--border)' }}>
            {isBackView ? 'BACK VIEW' : 'FRONT VIEW'} ({Math.round(rotationAngle)}°)
          </div>

          {/* Barefoot Girl 3D Model Display with Smooth 3D Perspective Rotation */}
          <div
            style={{
              position: 'relative',
              width: '100%',
              height: '220px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              transform: `scaleX(${perspectiveScaleX * 0.88 + 0.12})`,
              transition: isAutoSpinning ? 'none' : 'transform 0.1s ease-out',
            }}
          >
            {/* Real Barefoot Female Model Image */}
            <img
              src={isBackView ? "/images/model_back.png" : "/images/model_front.png"}
              alt="Barefoot 3D Female Fashion Model"
              style={{
                height: '210px',
                objectFit: 'contain',
                filter: 'drop-shadow(0px 8px 16px rgba(0,0,0,0.85))',
                userSelect: 'none',
                pointerEvents: 'none',
              }}
            />

            {/* Overlaid Clean Anatomical Measurement Lines (No Text Labels) */}
            <svg
              viewBox="0 0 100 200"
              style={{
                position: 'absolute',
                top: 0,
                left: 0,
                width: '100%',
                height: '100%',
                pointerEvents: 'none',
              }}
            >
              {/* 1. BUST LINE (Y=56) */}
              <g opacity={activeField === 'bust_cm' ? '1' : '0.35'}>
                <ellipse cx="50" cy="56" rx="28" ry="5.5" fill="none" stroke="var(--text-accent)" strokeWidth="3" strokeDasharray="3,2" />
                {activeField === 'bust_cm' && (
                  <ellipse cx="50" cy="56" rx="28" ry="5.5" fill="none" stroke="var(--text-accent)" strokeWidth="2">
                    <animate attributeName="rx" values="26;31;26" dur="1.2s" repeatCount="indefinite" />
                    <animate attributeName="ry" values="4.5;7.5;4.5" dur="1.2s" repeatCount="indefinite" />
                  </ellipse>
                )}
              </g>

              {/* 2. WAIST LINE (Y=78) */}
              <g opacity={activeField === 'waist_cm' ? '1' : '0.35'}>
                <ellipse cx="50" cy="78" rx="21" ry="4" fill="none" stroke="#52B788" strokeWidth="3" strokeDasharray="3,2" />
                {activeField === 'waist_cm' && (
                  <ellipse cx="50" cy="78" rx="21" ry="4" fill="none" stroke="#52B788" strokeWidth="2">
                    <animate attributeName="rx" values="19;24;19" dur="1.2s" repeatCount="indefinite" />
                    <animate attributeName="ry" values="3;6;3" dur="1.2s" repeatCount="indefinite" />
                  </ellipse>
                )}
              </g>

              {/* 3. HIP LINE (Y=98) */}
              <g opacity={activeField === 'hip_cm' ? '1' : '0.35'}>
                <ellipse cx="50" cy="98" rx="27" ry="5.5" fill="none" stroke="#74C69D" strokeWidth="3" strokeDasharray="3,2" />
                {activeField === 'hip_cm' && (
                  <ellipse cx="50" cy="98" rx="27" ry="5.5" fill="none" stroke="#74C69D" strokeWidth="2">
                    <animate attributeName="rx" values="25;30;25" dur="1.2s" repeatCount="indefinite" />
                    <animate attributeName="ry" values="4.5;7.5;4.5" dur="1.2s" repeatCount="indefinite" />
                  </ellipse>
                )}
              </g>

              {/* 4. HEIGHT LINE */}
              <g opacity={activeField === 'height_cm' ? '1' : '0.35'}>
                <line x1="24" y1="28" x2="24" y2="175" stroke="#2D6A4F" strokeWidth="2" strokeDasharray="3,2" />
                <line x1="20" y1="28" x2="52" y2="28" stroke="#2D6A4F" strokeWidth="1.5" />
                <line x1="20" y1="175" x2="52" y2="175" stroke="#2D6A4F" strokeWidth="1.5" />
              </g>
            </svg>
          </div>

          {/* Manual 360 Rotation Slider */}
          <div style={{ width: '90%', marginTop: '6px' }}>
            <input
              type="range"
              min="0"
              max="360"
              value={rotationAngle}
              onChange={(e) => {
                setIsAutoSpinning(false);
                setRotationAngle(parseFloat(e.target.value));
              }}
              style={{ width: '100%', height: '4px', accentColor: 'var(--text-accent)', cursor: 'pointer' }}
            />
          </div>

        </div>

        {/* Live Active Field Instruction Box */}
        <div style={{ background: 'var(--surface-1)', borderRadius: '10px', padding: '16px', border: '1px solid var(--border)' }}>
          <div style={{ fontSize: '14px', fontWeight: '600', color: activeInfo.color, marginBottom: '8px' }}>
            {activeInfo.title}
          </div>
          <p style={{ fontSize: '12px', color: 'var(--text-secondary)', lineHeight: '1.6' }}>
            {activeInfo.tip}
          </p>
          <div style={{ marginTop: '12px', display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
            {activeInfo.dos.map((doTip, i) => (
              <span key={i} style={{ fontSize: '11px', background: 'var(--surface-2)', color: 'var(--text-secondary)', padding: '4px 10px', borderRadius: '4px', border: '1px solid var(--border)' }}>
                ✓ {doTip}
              </span>
            ))}
          </div>
        </div>

      </div>

      {/* Standard Master Tailoring Protocol Cards & Ease Rules */}
      {showModal && (
        <div style={{ marginTop: '18px', paddingTop: '16px', borderTop: '1px solid var(--border)' }}>
          <div style={{ fontSize: '13px', fontWeight: '600', color: 'var(--text-primary)', marginBottom: '12px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span>Winifred Aldrich Standard Measurement Protocol</span>
            <span style={{ fontSize: '11px', color: 'var(--text-accent)' }}>Sri Lankan Master Tailoring Guidelines</span>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', fontSize: '12px' }}>
            
            {/* Bust Protocol */}
            <div style={{ background: 'var(--surface-1)', border: '1px solid var(--border)', padding: '12px', borderRadius: '8px' }}>
              <div style={{ color: 'var(--text-accent)', fontWeight: '600', marginBottom: '4px' }}>Bust Circumference</div>
              <p style={{ color: 'var(--text-secondary)', fontSize: '11px', lineHeight: '1.5' }}>
                Measure horizontally around the fullest part of bust across apex points. Keep measuring tape level and flat across shoulder blades.
              </p>
            </div>

            {/* Waist Protocol */}
            <div style={{ background: 'var(--surface-1)', border: '1px solid var(--border)', padding: '12px', borderRadius: '8px' }}>
              <div style={{ color: '#52B788', fontWeight: '600', marginBottom: '4px' }}>Waist Circumference</div>
              <p style={{ color: 'var(--text-secondary)', fontSize: '11px', lineHeight: '1.5' }}>
                Measure around natural waist crease (approx. 2.5 cm above navel). Keep tape comfortable with 1 finger allowance. Breathe out naturally.
              </p>
            </div>

            {/* Hip Protocol */}
            <div style={{ background: 'var(--surface-1)', border: '1px solid var(--border)', padding: '12px', borderRadius: '8px' }}>
              <div style={{ color: '#74C69D', fontWeight: '600', marginBottom: '4px' }}>Hip Circumference</div>
              <p style={{ color: 'var(--text-secondary)', fontSize: '11px', lineHeight: '1.5' }}>
                Stand with feet together. Wrap tape around maximum projection of buttocks (20 cm below natural waistline). Ensure tape is parallel to floor.
              </p>
            </div>

            {/* Height Protocol */}
            <div style={{ background: 'var(--surface-1)', border: '1px solid var(--border)', padding: '12px', borderRadius: '8px' }}>
              <div style={{ color: '#2D6A4F', fontWeight: '600', marginBottom: '4px' }}>Total Body Height</div>
              <p style={{ color: 'var(--text-secondary)', fontSize: '11px', lineHeight: '1.5' }}>
                Stand barefoot with heels against a flat wall. Measure vertically from floor to crown of head using a flat ruler guide.
              </p>
            </div>

          </div>

          {/* Ease Allowance Reference Note */}
          <div style={{ marginTop: '12px', background: 'var(--surface-2)', border: '1px solid var(--border)', borderRadius: '8px', padding: '10px 14px', fontSize: '11px', color: 'var(--text-primary)', display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px' }}>
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
