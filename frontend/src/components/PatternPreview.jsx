/**
 * Pattern Preview — renders the geometry returned by the API. It contains NO piece dimensions of
 * its own: every outline comes from `piece.segments` (lines + cubic Bezier curves, cm) or, for
 * older records, from the flattened `piece.outline`.
 *
 * "Not to scale for printing": pieces are fit to the view and laid side by side. A 1:1 printable
 * pattern (with seam allowance) is a later stage.
 */
const PIECE_COLORS = ['#38BDF8', '#52B788', '#F59E0B', '#A78BFA', '#F472B6', '#74C69D'];

const pt = (p) => (Array.isArray(p) ? [Number(p[0]), Number(p[1])] : [Number(p?.x ?? 0), Number(p?.y ?? 0)]);

export function outlinePoints(piece) {
  return (piece?.outline || []).map(pt);
}

/** SVG path data from the API segments (real curves), shifted by (dx, dy). Falls back to the polyline outline. */
export function piecePath(piece, dx = 0, dy = 0) {
  const shift = ([x, y]) => `${x + dx} ${y + dy}`;
  const segs = piece?.segments;
  if (Array.isArray(segs) && segs.length) {
    let d = '';
    segs.forEach((s, i) => {
      const p = (s.p || []).map(pt);
      if (i === 0) d += `M ${shift(p[0])}`;
      if (s.type === 'cubic' && p.length === 4) d += ` C ${shift(p[1])}, ${shift(p[2])}, ${shift(p[3])}`;
      else d += ` L ${shift(p[p.length - 1])}`;
    });
    return `${d} Z`;
  }
  const pts = outlinePoints(piece);
  if (!pts.length) return '';
  return `M ${shift(pts[0])}${pts.slice(1).map((q) => ` L ${shift(q)}`).join('')} Z`;
}

const fmt = (v, d = 1) => (Number.isFinite(Number(v)) ? Number(v).toFixed(d) : '—');

export default function PatternPreview({
  pieces = [],
  fabricWidth = null,
  validation = null,
  draftingBlock = null,
  armholeSleeve = null,
  transformations = null,
}) {
  const list = (pieces || []).filter((p) => p && (p.segments?.length || p.outline?.length));

  if (!list.length) {
    return (
      <div style={{ padding: '24px', textAlign: 'center', color: 'var(--text-secondary)', fontSize: '13px' }}>
        No pattern geometry available yet. Generate a pattern first.
      </div>
    );
  }

  // Lay pieces side by side (a preview arrangement, not a marker/nesting layout).
  const gap = 5;
  let cursor = 0;
  const laidOut = list.map((piece, idx) => {
    const box = piece.bounding_box || {};
    const pts = outlinePoints(piece);
    const minX = box.min_x ?? Math.min(...pts.map((p) => p[0]));
    const minY = box.min_y ?? Math.min(...pts.map((p) => p[1]));
    const w = box.width_cm ?? Math.max(...pts.map((p) => p[0])) - minX;
    const h = box.height_cm ?? Math.max(...pts.map((p) => p[1])) - minY;
    const dx = cursor - minX;
    const dy = -minY;
    cursor += w + gap;
    return { piece, idx, dx, dy, w, h, x0: cursor - w - gap };
  });

  const totalW = Math.max(cursor - gap, 10);
  const maxH = Math.max(...laidOut.map((l) => l.h), 10);
  const pad = 6;
  const viewBox = `${-pad} ${-pad - 6} ${totalW + pad * 2} ${maxH + pad * 2 + 10}`;

  const passed = validation?.passed !== false;
  const errors = validation?.errors || [];

  return (
    <div data-testid="pattern-preview">
      <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '2px' }}>
        Pattern Preview — Not to Scale for Printing
      </div>
      <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginBottom: '10px' }}>
        Prototype custom pattern, mathematically generated from your measurements and the confirmed design;
        geometry validated only (not fit-tested or professionally validated). No seam allowance is included yet.
        {draftingBlock?.block_label ? ` Block: ${draftingBlock.block_label}.` : ''}
        {fabricWidth ? ` Fabric width reference: ${fabricWidth} cm.` : ''}
      </div>

      {validation && (
        <div
          data-testid="geometry-validation"
          style={{
            marginBottom: '10px', padding: '8px 12px', borderRadius: '8px', fontSize: '12px',
            border: `1px solid ${passed ? '#52B788' : '#EF4444'}`,
            background: passed ? 'rgba(82,183,136,0.08)' : 'rgba(239,68,68,0.08)',
          }}
        >
          <div style={{ fontWeight: 600, color: passed ? '#2D6A4F' : '#B91C1C' }}>
            {passed ? 'Geometry validation passed' : 'Geometry validation failed'}
          </div>
          {errors.map((e) => <div key={e} style={{ color: '#B91C1C' }}>• {e}</div>)}
          {armholeSleeve && (
            <div data-testid="armhole-sleeve" style={{ color: 'var(--text-secondary)', marginTop: '4px' }}>
              Armhole seam: front {fmt(armholeSleeve.front_armhole_seam_cm)} + back {fmt(armholeSleeve.back_armhole_seam_cm)} ={' '}
              {fmt(armholeSleeve.total_armhole_seam_cm)} cm · sleeve cap seam {fmt(armholeSleeve.sleeve_cap_seam_cm)} cm ·
              ease {fmt(armholeSleeve.cap_ease_cm)} cm
            </div>
          )}
        </div>
      )}

      <div style={{ width: '100%', background: '#0F172A', border: '1px solid var(--border)', borderRadius: '8px', overflow: 'hidden' }}>
        <svg viewBox={viewBox} style={{ width: '100%', height: '340px' }} preserveAspectRatio="xMidYMid meet" role="img"
             aria-label="Pattern pieces preview, not to scale for printing">
          {laidOut.map(({ piece, idx, dx, dy, w, x0 }) => {
            const color = PIECE_COLORS[idx % PIECE_COLORS.length];
            const grain = piece.grain_line;
            const fold = piece.fold_line;
            return (
              <g key={`${piece.name}-${idx}`} data-testid={`piece-${idx}`}>
                <path d={piecePath(piece, dx, dy)} fill="rgba(15,23,42,0.85)" stroke={color} strokeWidth="0.35" />
                {(piece.darts || []).map((d) => {
                  const pts = d.lower_apex ? [d.apex, d.leg_a, d.lower_apex, d.leg_b, d.apex] : [d.leg_a, d.apex, d.leg_b];
                  return (
                    <polyline
                      key={d.id}
                      points={pts.map((q) => `${q[0] + dx},${q[1] + dy}`).join(' ')}
                      fill="none" stroke="#FB923C" strokeWidth="0.25"
                    />
                  );
                })}
                {fold && (
                  <line x1={fold.start[0] + dx} y1={fold.start[1] + dy} x2={fold.end[0] + dx} y2={fold.end[1] + dy}
                        stroke="#34D399" strokeWidth="0.6" />
                )}
                {grain && (
                  <line x1={grain.start[0] + dx} y1={grain.start[1] + dy} x2={grain.end[0] + dx} y2={grain.end[1] + dy}
                        stroke="#F8FAFC" strokeWidth="0.2" strokeDasharray="1,0.6" opacity="0.6" />
                )}
                <text x={x0 + w / 2} y={-2.2} fill="#F8FAFC" fontSize="2.1" textAnchor="middle" fontWeight="600">
                  {(piece.name || `Piece ${idx + 1}`).toUpperCase()}
                </text>
                <text x={x0 + w / 2} y={-0.1} fill="#94A3B8" fontSize="1.7" textAnchor="middle">
                  {fmt(w)} × {fmt(piece.bounding_box?.height_cm)} cm
                </text>
              </g>
            );
          })}
        </svg>
      </div>

      <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginTop: '12px' }}>
        {list.map((piece, idx) => (
          <span key={`${piece.name}-chip-${idx}`} className="chip"
                style={{ color: PIECE_COLORS[idx % PIECE_COLORS.length], borderColor: PIECE_COLORS[idx % PIECE_COLORS.length] }}>
            {piece.name}
            {piece.cut_count ? ` × ${piece.cut_count}` : ''}
            {piece.cut_on_fold ? ' (cut on fold)' : ''}
          </span>
        ))}
      </div>

      {Array.isArray(transformations) && transformations.length > 0 && (
        <ul data-testid="transformations" style={{ margin: '12px 0 0', paddingLeft: '18px', fontSize: '11px', color: 'var(--text-secondary)' }}>
          {transformations.map((t) => (
            <li key={t.id}>
              <strong>{t.id.replace(/_/g, ' ')}</strong>: {t.type?.replace(/_/g, ' ')}
              {t.status && t.status !== 'applied' ? ` — ${t.status.replace(/_/g, ' ')}` : ''}
              {t.note ? ` (${t.note})` : ''}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
