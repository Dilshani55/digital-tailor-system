// Dress-form outline with the active measurement highlighted (front view; back measurements are drawn
// where they are taken on the body and labelled "back").
const LINES = {
  bust_cm: { d: 'M34 70 C45 76 75 76 86 70', label: 'Bust' },
  waist_cm: { d: 'M40 104 C50 108 70 108 80 104', label: 'Waist' },
  hip_cm: { d: 'M32 138 C45 144 75 144 88 138', label: 'Hip' },
  neck_cm: { d: 'M50 26 C54 31 66 31 70 26', label: 'Neck' },
  shoulder_cm: { d: 'M71 28 L88 36', label: 'Shoulder length' },
  across_back_cm: { d: 'M37 54 L83 54', label: 'Across back (back)' },
  back_waist_length_cm: { d: 'M60 24 L60 104', label: 'Back waist length (back)' },
  armhole_depth_cm: { d: 'M88 36 L88 62', label: 'Armhole depth' },
  garment_length_cm: { d: 'M66 28 L66 150', label: 'Garment length' },
  bicep_cm: { d: 'M93 64 C98 66 102 66 105 62', label: 'Bicep' },
  sleeve_cm: { d: 'M89 36 C97 60 103 90 108 118', label: 'Sleeve length' },
  wrist_cm: { d: 'M104 118 C107 121 111 121 113 117', label: 'Wrist' },
  height_cm: { d: 'M16 10 L16 170', label: 'Height' },
};

export default function MeasureFigure({ active }) {
  const line = LINES[active];
  return (
    <svg viewBox="0 0 120 176" role="img" aria-label={line ? `Where to measure: ${line.label}` : 'Dress form'}>
      <path d="M52 20 C52 26 48 28 34 34 C28 44 30 60 34 72 C36 86 40 96 40 104 C38 114 32 126 32 138 C32 150 38 158 46 160 L74 160 C82 158 88 150 88 138 C88 126 82 114 80 104 C80 96 84 86 86 72 C90 60 92 44 86 34 C72 28 68 26 68 20 Z"
            fill="#f7f4ec" stroke="#56625b" strokeWidth="1.3" />
      <path d="M86 34 C96 44 104 80 110 118 L104 120 C98 90 92 66 86 56" fill="#f7f4ec" stroke="#8a948e" strokeWidth="1" />
      <line x1="60" y1="160" x2="60" y2="172" stroke="#56625b" strokeWidth="2" />
      <path d="M48 172 L72 172" stroke="#56625b" strokeWidth="2" strokeLinecap="round" />
      {Object.entries(LINES).map(([k, l]) => (
        <path key={k} d={l.d} fill="none" stroke={k === active ? '#2c5b45' : '#c9d2cb'} strokeWidth={k === active ? 2.6 : 1}
              strokeDasharray={k === active ? undefined : '3 2'} strokeLinecap="round" />
      ))}
    </svg>
  );
}
