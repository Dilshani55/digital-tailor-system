// Measurement GUIDE: a front view and a back view of a dress-form outline. The measurement the user is entering is
// drawn bold, with its two end points marked; the other measurements fade. It is an illustration of where to
// measure, not a body model. The sleeve line follows the entered sleeve length (in canonical cm, so equal cm / inch
// values draw the same line).
import { MEASUREMENT_FIELDS } from '../utils/measurementSchema';

const VIEW_OF = Object.fromEntries(MEASUREMENT_FIELDS.map((f) => [f.key, f.view]));

// d: the line or arc; ends: the points the tape starts and stops at (marked when active)
const LINES = {
  bust_cm: { d: 'M34 70 C45 77 75 77 86 70', label: 'Bust around', ends: [[34, 70], [86, 70]] },
  waist_cm: { d: 'M40 104 C50 109 70 109 80 104', label: 'Waist around', ends: [[40, 104], [80, 104]] },
  hip_cm: { d: 'M32 138 C45 145 75 145 88 138', label: 'Hip around', ends: [[32, 138], [88, 138]] },
  shoulder_width_cm: { d: 'M32 35 L88 35', label: 'Shoulder to shoulder', ends: [[32, 35], [88, 35]] },
  back_waist_length_cm: { d: 'M60 24 L60 104', label: 'Back neck to waist', ends: [[60, 24], [60, 104]] },
  shoulder_to_bust_cm: { d: 'M69 27 L74 70', label: 'Shoulder to bust point', ends: [[69, 27], [74, 70]] },
  bust_point_distance_cm: { d: 'M46 70 L74 70', label: 'Between bust points', ends: [[46, 70], [74, 70]] },
  waist_to_hip_cm: { d: 'M83 104 L90 138', label: 'Waist to hip', ends: [[83, 104], [90, 138]] },
  garment_length_cm: { d: 'M66 27 L66 150', label: 'Garment length', ends: [[66, 27], [66, 150]] },
  bicep_cm: { d: 'M91 62 C96 66 102 66 105 60', label: 'Upper arm around', ends: [[91, 62], [105, 60]] },
  sleeve_cm: { label: 'Sleeve length' },
  sleeve_end_cm: { label: 'Sleeve end around' },
  neck_width_cm: { d: 'M51 27 L69 27', label: 'Neckline width', ends: [[51, 27], [69, 27]] },
  front_neck_depth_cm: { d: 'M60 27 L60 42', label: 'Front neck depth', ends: [[60, 27], [60, 42]] },
  back_neck_depth_cm: { d: 'M60 27 L60 33', label: 'Back neck depth', ends: [[60, 27], [60, 33]] },
  armhole_depth_cm: { d: 'M70 27 L70 62 M70 62 L86 62', label: 'Armhole depth', ends: [[70, 27], [70, 62]] },
};

// the arm on the drawing: shoulder tip -> wrist, drawn as ARM_CM centimetres of arm
const SHOULDER = [89, 36];
const WRIST = [108, 118];
const ARM_CM = 60;
const DEFAULT_SLEEVE_CM = 24;

/** End point of a sleeve of `cm` centimetres measured from the shoulder tip along the drawn arm. */
export function sleeveEnd(cm) {
  const t = Math.min(Math.max((cm > 0 ? cm : DEFAULT_SLEEVE_CM) / ARM_CM, 0.04), 1.2);
  return [SHOULDER[0] + (WRIST[0] - SHOULDER[0]) * t, SHOULDER[1] + (WRIST[1] - SHOULDER[1]) * t];
}

const BODY = 'M52 20 C52 26 48 28 34 34 C28 44 30 60 34 72 C36 86 40 96 40 104 C38 114 32 126 32 138 C32 150 38 158 46 160 L74 160 C82 158 88 150 88 138 C88 126 82 114 80 104 C80 96 84 86 86 72 C90 60 92 44 86 34 C72 28 68 26 68 20 Z';
const ARM = 'M86 34 C96 44 104 80 110 118 L104 120 C98 90 92 66 86 56';

function View({ view, active, visible, sleeveCm }) {
  const end = sleeveEnd(sleeveCm);
  const geometry = (k) => {
    if (k === 'sleeve_cm') {
      return { d: `M${SHOULDER[0]} ${SHOULDER[1]} L${end[0].toFixed(2)} ${end[1].toFixed(2)}`, ends: [SHOULDER, end] };
    }
    if (k === 'sleeve_end_cm') {                                    // around the arm where the sleeve ends
      const [x, y] = end;
      return { d: `M${(x - 7).toFixed(2)} ${(y + 2).toFixed(2)} C${(x - 3).toFixed(2)} ${(y + 5).toFixed(2)} ${(x + 3).toFixed(2)} ${(y + 3).toFixed(2)} ${(x + 5).toFixed(2)} ${(y - 2).toFixed(2)}`,
               ends: [[x - 7, y + 2], [x + 5, y - 2]] };
    }
    return LINES[k];
  };
  const mine = visible.filter((k) => VIEW_OF[k] === view);
  const here = mine.includes(active);
  const title = view === 'front' ? 'Front view' : 'Back view';
  return (
    <figure className={`measure-view${here ? ' current' : ''}`} data-testid={`measure-view-${view}`} data-current={here ? 'yes' : 'no'}
            style={{ margin: 0, opacity: here || !visible.includes(active) ? 1 : 0.45 }}>
      <svg viewBox="0 0 120 176" role="img"
           aria-label={here ? `${title}: where to measure ${LINES[active].label}` : `${title} of the measurement guide`}>
        <path d={BODY} fill="#f7f4ec" stroke="#56625b" strokeWidth="1.3" />
        <path d={ARM} fill="#f7f4ec" stroke="#8a948e" strokeWidth="1" />
        {view === 'front'
          ? <path d="M51 27 C55 40 65 40 69 27" fill="none" stroke="#8a948e" strokeWidth="0.9" />
          : <><path d="M51 27 C56 31 64 31 69 27" fill="none" stroke="#8a948e" strokeWidth="0.9" />
              <path d="M60 31 L60 158" stroke="#c9d2cb" strokeWidth="0.7" strokeDasharray="2 3" /></>}
        <line x1="60" y1="160" x2="60" y2="172" stroke="#56625b" strokeWidth="2" />
        <path d="M48 172 L72 172" stroke="#56625b" strokeWidth="2" strokeLinecap="round" />
        {mine.map((k) => {
          const g = geometry(k);
          const on = k === active;
          return (
            <g key={k} data-testid={`guide-line-${k}`} data-active={on ? 'yes' : 'no'}>
              <path d={g.d} fill="none" stroke={on ? '#2c5b45' : '#c9d2cb'} strokeWidth={on ? 2.8 : 1}
                    strokeDasharray={on ? undefined : '3 2'} strokeLinecap="round"
                    data-testid={k === 'sleeve_cm' ? 'sleeve-guide-line' : undefined}
                    data-end={k === 'sleeve_cm' ? `${end[0].toFixed(2)},${end[1].toFixed(2)}` : undefined} />
              {on && g.ends.map(([x, y], i) => (
                <circle key={i} cx={x} cy={y} r="2.6" fill="#fff" stroke="#2c5b45" strokeWidth="1.4" data-testid={`guide-point-${k}-${i}`} />
              ))}
            </g>
          );
        })}
      </svg>
      <figcaption style={{ textAlign: 'center', fontSize: 12, fontWeight: here ? 700 : 500, color: here ? 'var(--text-accent, #2c5b45)' : 'var(--text-muted, #6b7280)' }}>{title}</figcaption>
    </figure>
  );
}

export default function MeasureFigure({ active, fields, sleeveCm }) {
  const visible = Object.keys(LINES).filter((k) => !fields || fields.includes(k));
  return (
    <div className="measure-views" data-testid="measure-figure" data-active-view={VIEW_OF[active] || ''}
         style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
      <View view="front" active={active} visible={visible} sleeveCm={sleeveCm} />
      <View view="back" active={active} visible={visible} sleeveCm={sleeveCm} />
    </div>
  );
}
