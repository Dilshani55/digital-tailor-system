/**
 * SVG of the fabric cutting layout returned by the nesting API (real polygon positions in cm).
 * Pieces are drawn exactly where the algorithm placed them; the fold edge is marked.
 */
export default function NestingLayout({ nesting }) {
  const pieces = nesting?.placed_pieces || [];
  if (!pieces.length) return null;
  const w = Number(nesting.usable_width_cm);
  const l = Number(nesting.fabric_length_cm);
  const pad = 6;
  return (
    <figure style={{ margin: 0 }} data-testid="nesting-layout">
      <svg viewBox={`${-pad - 4} ${-pad - 4} ${w + pad * 2 + 4} ${l + pad * 2 + 4}`} role="img"
           aria-label={`Cutting layout on ${nesting.fabric_width_cm} cm wide fabric, ${nesting.fabric_length_cm} cm long`}
           style={{ width: '100%', maxHeight: '520px', background: '#fbfcfa', border: '1px solid var(--line)', borderRadius: '12px' }}>
        <rect x="0" y="0" width={w} height={l} fill="#7d9a80" stroke="#4d6b52" strokeWidth="0.4" />
        <line x1="0" y1="-3" x2={w} y2="-3" stroke="#1b2620" strokeWidth="0.25" />
        <text x={w / 2} y="-4.4" fontSize="2.6" textAnchor="middle" fill="#1b2620">{nesting.usable_width_cm} cm {nesting.cutting_mode === 'folded' ? '(folded)' : 'wide'}</text>
        <line x1="-3" y1="0" x2="-3" y2={l} stroke="#1b2620" strokeWidth="0.25" />
        <text x="-4.4" y={l / 2} fontSize="2.6" textAnchor="middle" fill="#1b2620" transform={`rotate(-90 -4.4 ${l / 2})`}>{nesting.fabric_length_cm} cm</text>
        {nesting.cutting_mode === 'folded' && (
          <>
            <line x1="0" y1="0" x2="0" y2={l} stroke="#b71c1c" strokeWidth="0.9" />
            <text x="1" y="3" fontSize="2.2" fill="#fff" fontWeight="700">FOLD</text>
          </>
        )}
        {pieces.map((p, i) => {
          const pts = p.polygon_coordinates.map((q) => q.join(',')).join(' ');
          return (
            <g key={`${p.name}-${i}`} data-testid={`placed-${i}`}>
              <polygon points={pts} fill="#f6f1e6" stroke="#1d3a2e" strokeWidth="0.35" />
              <text x={p.x + p.width / 2} y={p.y + p.height / 2} fontSize="2.3" textAnchor="middle" fill="#1b2620" fontWeight="600">{p.name}</text>
            </g>
          );
        })}
      </svg>
      <figcaption className="form-hint" style={{ marginTop: 6 }}>
        Fabric {nesting.fabric_width_cm} cm wide ({nesting.cutting_method_simple?.toLowerCase()}); the drawing shows the usable
        width {nesting.usable_width_cm} cm × layout length {nesting.fabric_length_cm} cm.
      </figcaption>
    </figure>
  );
}
