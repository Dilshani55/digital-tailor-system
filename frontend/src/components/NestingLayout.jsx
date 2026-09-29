const COLORS = ['#38BDF8', '#52B788', '#F59E0B', '#A78BFA', '#F472B6', '#74C69D', '#FB7185'];

/**
 * SVG of the fabric cutting layout returned by the nesting API (real polygon positions in cm).
 * Pieces are drawn exactly where the algorithm placed them; the fold edge is marked.
 */
export default function NestingLayout({ nesting }) {
  const pieces = nesting?.placed_pieces || [];
  if (!pieces.length) return null;
  const w = Number(nesting.usable_width_cm);
  const l = Number(nesting.fabric_length_cm);
  const pad = 3;
  return (
    <figure style={{ margin: 0 }} data-testid="nesting-layout">
      <svg viewBox={`${-pad} ${-pad - 4} ${w + pad * 2} ${l + pad * 2 + 4}`} role="img"
           aria-label={`Cutting layout on ${nesting.fabric_width_cm} cm wide fabric, ${nesting.fabric_length_cm} cm long`}
           style={{ width: '100%', maxHeight: '460px', background: '#F8FAF8', border: '1px solid var(--border)', borderRadius: '10px' }}>
        <rect x="0" y="0" width={w} height={l} fill="#fff" stroke="#94A3B8" strokeWidth="0.3" />
        {nesting.cutting_mode === 'folded' && (
          <>
            <line x1="0" y1="0" x2="0" y2={l} stroke="#B71C1C" strokeWidth="0.8" />
            <text x="1" y="-1" fontSize="2.2" fill="#B71C1C" fontWeight="700">FOLD</text>
          </>
        )}
        {pieces.map((p, i) => {
          const pts = p.polygon_coordinates.map((q) => q.join(',')).join(' ');
          const cx = p.x + p.width / 2;
          const cy = p.y + p.height / 2;
          return (
            <g key={`${p.name}-${i}`} data-testid={`placed-${i}`}>
              <polygon points={pts} fill={COLORS[i % COLORS.length]} fillOpacity="0.28" stroke={COLORS[i % COLORS.length]} strokeWidth="0.35" />
              <text x={cx} y={cy} fontSize="2.3" textAnchor="middle" fill="#17231e" fontWeight="600">{p.name}</text>
            </g>
          );
        })}
      </svg>
      <figcaption style={{ fontSize: '11px', color: 'var(--text-secondary)', marginTop: '6px' }}>
        Fabric {nesting.fabric_width_cm} cm wide ({nesting.cutting_method_simple?.toLowerCase()}); the drawing shows the usable
        width {nesting.usable_width_cm} cm × layout length {nesting.fabric_length_cm} cm.
      </figcaption>
    </figure>
  );
}
