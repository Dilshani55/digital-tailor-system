/**
 * Renders real parametric pattern outlines from the API (cm coordinates).
 * Screen view is fit-to-canvas; download SVG is true 1cm = 1cm scale.
 */
const PIECE_COLORS = [
  '#38BDF8',
  '#52B788',
  '#74C69D',
  '#F59E0B',
  '#A78BFA',
  '#F472B6',
];

function normalizeOutline(outline) {
  if (!Array.isArray(outline) || outline.length < 2) return [];
  return outline.map((pt) => {
    if (Array.isArray(pt)) return [Number(pt[0]), Number(pt[1])];
    if (pt && typeof pt === 'object') return [Number(pt.x ?? pt[0]), Number(pt.y ?? pt[1])];
    return [0, 0];
  });
}

function boundsOf(pieces) {
  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;
  pieces.forEach((piece) => {
    normalizeOutline(piece.outline).forEach(([x, y]) => {
      minX = Math.min(minX, x);
      minY = Math.min(minY, y);
      maxX = Math.max(maxX, x);
      maxY = Math.max(maxY, y);
    });
  });
  if (!Number.isFinite(minX)) {
    return { minX: 0, minY: 0, maxX: 40, maxY: 40, width: 40, height: 40 };
  }
  return {
    minX,
    minY,
    maxX,
    maxY,
    width: Math.max(1, maxX - minX),
    height: Math.max(1, maxY - minY),
  };
}

function toPath(outline) {
  const pts = normalizeOutline(outline);
  if (!pts.length) return '';
  const [x0, y0] = pts[0];
  let d = `M ${x0} ${y0}`;
  for (let i = 1; i < pts.length; i += 1) {
    d += ` L ${pts[i][0]} ${pts[i][1]}`;
  }
  d += ' Z';
  return d;
}

export default function PatternPreview({
  pieces = [],
  fabricWidth = 114,
  validation = null,
  draftingBlock = null,
}) {
  const list = (pieces || []).filter((p) => p && (p.outline || p.bounding_box));

  if (!list.length) {
    return (
      <div style={{ padding: '24px', textAlign: 'center', color: 'var(--text-secondary)', fontSize: '13px' }}>
        No pattern piece coordinates available yet. Generate a pattern first.
      </div>
    );
  }

  // Lay pieces side-by-side for preview (not nesting layout)
  const laidOut = [];
  let cursorX = 0;
  const gap = 4;
  list.forEach((piece, idx) => {
    const outline = normalizeOutline(piece.outline);
    if (!outline.length) return;
    const xs = outline.map((p) => p[0]);
    const ys = outline.map((p) => p[1]);
    const localMinX = Math.min(...xs);
    const localMinY = Math.min(...ys);
    const w = (piece.bounding_box?.width_cm) || (Math.max(...xs) - localMinX);
    const h = (piece.bounding_box?.height_cm) || (Math.max(...ys) - localMinY);
    const dx = cursorX - localMinX;
    const dy = -localMinY;
    const shifted = outline.map(([x, y]) => [x + dx, y + dy]);
    let grain = null;
    if (piece.grain_line?.start && piece.grain_line?.end) {
      const s = piece.grain_line.start;
      const e = piece.grain_line.end;
      const sx = Array.isArray(s) ? s[0] : s.x;
      const sy = Array.isArray(s) ? s[1] : s.y;
      const ex = Array.isArray(e) ? e[0] : e.x;
      const ey = Array.isArray(e) ? e[1] : e.y;
      grain = {
        start: [sx + dx, sy + dy],
        end: [ex + dx, ey + dy],
      };
    }
    laidOut.push({
      ...piece,
      _outline: shifted,
      _grain: grain,
      _color: PIECE_COLORS[idx % PIECE_COLORS.length],
      _labelX: cursorX + w / 2,
      _labelY: 2,
      _width: w,
      _height: h,
    });
    cursorX += w + gap;
  });

  const b = boundsOf(laidOut.map((p) => ({ outline: p._outline })));
  const pad = 6;
  const viewW = b.width + pad * 2;
  const viewH = b.height + pad * 2 + 10;
  const vb = `${b.minX - pad} ${b.minY - pad - 4} ${viewW} ${viewH}`;

  const downloadSvg = () => {
    // True-scale SVG: 1 user unit = 1 cm
    const parts = list.map((piece, idx) => {
      const outline = normalizeOutline(piece.outline);
      if (!outline.length) return '';
      const xs = outline.map((p) => p[0]);
      const ys = outline.map((p) => p[1]);
      const minX = Math.min(...xs);
      const minY = Math.min(...ys);
      const shifted = outline.map(([x, y]) => [x - minX, y - minY]);
      const color = PIECE_COLORS[idx % PIECE_COLORS.length];
      const w = piece.bounding_box?.width_cm ?? (Math.max(...xs) - minX);
      const h = piece.bounding_box?.height_cm ?? (Math.max(...ys) - minY);
      return `
  <g id="piece-${idx}" transform="translate(0, ${(list.slice(0, idx).reduce((acc, p) => acc + (p.bounding_box?.height_cm || 20) + 3, 0))})">
    <path d="${toPath(shifted)}" fill="none" stroke="${color}" stroke-width="0.15" />
    <text x="0.5" y="-0.4" font-size="0.8" fill="#111">${piece.name || `Piece ${idx + 1}`} (${Number(w).toFixed(1)}×${Number(h).toFixed(1)} cm)</text>
  </g>`;
    }).join('\n');

    const totalH = list.reduce((acc, p) => acc + (p.bounding_box?.height_cm || 20) + 3, 2);
    const maxW = Math.max(...list.map((p) => p.bounding_box?.width_cm || 20), 10);
    const svg = `<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="${maxW}cm" height="${totalH}cm" viewBox="0 0 ${maxW} ${totalH}">
  <title>Digital Tailor — true-scale pattern pieces (1 unit = 1 cm)</title>
  <desc>Print at 100% scale. Seam allowance already included in outline where drafted.</desc>
  ${parts}
</svg>`;
    const blob = new Blob([svg], { type: 'image/svg+xml;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'pattern-pieces-true-scale.svg';
    a.click();
    URL.revokeObjectURL(url);
  };

  const validationPassed = validation?.passed !== false;
  const validationErrors = validation?.errors || [];
  const validationWarnings = validation?.warnings || [];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px', gap: '8px', flexWrap: 'wrap' }}>
        <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
          Live outlines from parametric engine · preview fit-to-view · fabric width ref {fabricWidth} cm
          {draftingBlock?.block_label ? ` · ${draftingBlock.block_label}` : ''}
        </div>
        <button
          type="button"
          className="btn btn-outline"
          onClick={downloadSvg}
          style={{ height: '32px', fontSize: '12px' }}
        >
          Download true-scale SVG
        </button>
      </div>

      {validation && (
        <div
          style={{
            marginBottom: '10px',
            padding: '10px 12px',
            borderRadius: '8px',
            border: `1px solid ${validationPassed ? '#52B788' : '#EF4444'}`,
            background: validationPassed ? 'rgba(82,183,136,0.08)' : 'rgba(239,68,68,0.08)',
            fontSize: '12px',
          }}
        >
          <div style={{ fontWeight: 600, marginBottom: '4px', color: validationPassed ? '#2D6A4F' : '#B91C1C' }}>
            {validationPassed ? 'Pattern validation passed' : 'Pattern validation failed — fabric estimate blocked'}
          </div>
          {validationErrors.map((e) => (
            <div key={e} style={{ color: '#B91C1C' }}>• {e}</div>
          ))}
          {validationWarnings.slice(0, 2).map((w) => (
            <div key={w} style={{ color: '#92400E' }}>• {w}</div>
          ))}
        </div>
      )}

      <div
        style={{
          width: '100%',
          height: '320px',
          background: '#0F172A',
          border: '1px solid var(--border)',
          borderRadius: '8px',
          overflow: 'hidden',
        }}
      >
        <svg viewBox={vb} style={{ width: '100%', height: '100%' }} preserveAspectRatio="xMidYMid meet">
          <defs>
            <pattern id="pattern-grid" width="2" height="2" patternUnits="userSpaceOnUse">
              <path d="M 2 0 L 0 0 0 2" fill="none" stroke="#1E293B" strokeWidth="0.08" />
            </pattern>
          </defs>
          <rect x={b.minX - pad} y={b.minY - pad - 4} width={viewW} height={viewH} fill="url(#pattern-grid)" />

          {laidOut.map((piece, idx) => (
            <g key={`${piece.name}-${idx}`}>
              <path
                d={toPath(piece._outline)}
                fill="rgba(15,23,42,0.85)"
                stroke={piece._color}
                strokeWidth="0.35"
              />
              {piece._grain && (
                <line
                  x1={piece._grain.start[0]}
                  y1={piece._grain.start[1]}
                  x2={piece._grain.end[0]}
                  y2={piece._grain.end[1]}
                  stroke="#F8FAFC"
                  strokeWidth="0.2"
                  strokeDasharray="1,0.6"
                  opacity="0.55"
                />
              )}
              <text
                x={piece._labelX}
                y={piece._labelY}
                fill="#F8FAFC"
                fontSize="2.2"
                textAnchor="middle"
                fontWeight="600"
              >
                {(piece.name || `Piece ${idx + 1}`).toUpperCase()}
              </text>
              <text
                x={piece._labelX}
                y={piece._labelY + 2.6}
                fill="#94A3B8"
                fontSize="1.8"
                textAnchor="middle"
              >
                {Number(piece._width).toFixed(1)} × {Number(piece._height).toFixed(1)} cm
                {piece.seam_allowance_cm != null ? ` · SA ${piece.seam_allowance_cm} cm` : ''}
              </text>
            </g>
          ))}
        </svg>
      </div>

      <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginTop: '12px' }}>
        {list.map((piece, idx) => (
          <span
            key={`${piece.name}-chip-${idx}`}
            className="chip"
            style={{ color: PIECE_COLORS[idx % PIECE_COLORS.length], borderColor: PIECE_COLORS[idx % PIECE_COLORS.length] }}
          >
            ✓ {piece.name}
            {piece.cut_count ? ` × ${piece.cut_count}` : ''}
            {piece.cut_on_fold ? ' (on fold)' : ''}
          </span>
        ))}
      </div>
    </div>
  );
}
