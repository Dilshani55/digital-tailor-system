import { useRef, useState } from 'react';

/**
 * Pattern Preview — renders the geometry returned by the API. It contains NO piece dimensions of
 * its own: every outline comes from `piece.segments` (lines + cubic Bezier curves, cm) or, for
 * older records, from the flattened `piece.outline`.
 *
 * "Not to scale for printing": pieces are fit to the view and laid side by side. The printable 1:1
 * tiled PDF is produced by the export step. When a piece carries `cutting_line` (seam allowance
 * geometry) it is drawn solid, the sewing (seam) line dashed, and notches as triangles.
 */

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

const ZOOMS = [0.5, 0.75, 1, 1.5, 2, 3];

export default function PatternPreview({
  pieces = [],
  fabricWidth = null,
  validation = null,
  draftingBlock = null,
  armholeSleeve = null,
  transformations = null,
}) {
  const [zoomIdx, setZoomIdx] = useState(2);
  const scrollRef = useRef(null);
  const frameRef = useRef(null);
  const drag = useRef(null);
  const hasCut = (pieces || []).some((p) => Array.isArray(p?.cutting_line) && p.cutting_line.length > 2);
  const list = (pieces || []).filter((p) => p && (p.segments?.length || p.outline?.length));

  if (!list.length) {
    return <div className="empty-state compact"><p>No pattern geometry available yet. Generate a pattern first.</p></div>;
  }

  // Lay pieces side by side (a preview arrangement, not a marker/nesting layout).
  const gap = 6;
  let cursor = 0;
  const laidOut = list.map((piece, idx) => {
    const box = piece.cut_bounding_box || piece.bounding_box || {};
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
  const pad = 5;
  const viewBox = `${-pad} ${-pad} ${totalW + pad * 2} ${maxH + pad * 2}`;
  const zoom = ZOOMS[zoomIdx];

  const passed = validation?.passed !== false;
  const errors = validation?.errors || [];

  const onPointerDown = (e) => {
    const el = scrollRef.current;
    if (!el) return;
    drag.current = { x: e.clientX, y: e.clientY, left: el.scrollLeft, top: el.scrollTop };
  };
  const onPointerMove = (e) => {
    const el = scrollRef.current;
    if (!drag.current || !el) return;
    el.scrollLeft = drag.current.left - (e.clientX - drag.current.x);
    el.scrollTop = drag.current.top - (e.clientY - drag.current.y);
  };
  const endDrag = () => { drag.current = null; };
  const fullscreen = () => {
    const el = frameRef.current;
    if (!el) return;
    if (document.fullscreenElement) document.exitFullscreen?.();
    else el.requestFullscreen?.();
  };

  return (
    <div data-testid="pattern-preview">
      {validation && (
        <div className={`validation-banner${passed ? '' : ' fail'}`} data-testid="geometry-validation" role={passed ? 'status' : 'alert'}>
          <span className="vb-icon" aria-hidden="true">{passed ? '✓' : '!'}</span>
          <div>
            <strong>{passed ? 'Geometry validation passed' : 'Geometry validation failed'}</strong>
            <small>{passed
              ? 'All pieces are closed, non-intersecting shapes; seams, allowances, notches and sleeve-to-armhole checks pass.'
              : 'Pattern validation failed. Fabric estimation and PDF export are unavailable until the pattern is corrected.'}</small>
            {errors.map((e) => <small key={e} style={{ color: 'var(--danger)' }}>• {e}</small>)}
            {armholeSleeve && (
              <small data-testid="armhole-sleeve">
                Armhole seam: front {fmt(armholeSleeve.front_armhole_seam_cm)} + back {fmt(armholeSleeve.back_armhole_seam_cm)} ={' '}
                {fmt(armholeSleeve.total_armhole_seam_cm)} cm · sleeve cap seam {fmt(armholeSleeve.sleeve_cap_seam_cm)} cm ·
                ease {fmt(armholeSleeve.cap_ease_cm)} cm
              </small>
            )}
          </div>
        </div>
      )}

      <div className="pattern-canvas" ref={frameRef}>
        <div className="canvas-toolbar" role="group" aria-label="Zoom">
          <button type="button" aria-label="Zoom out" onClick={() => setZoomIdx((z) => Math.max(0, z - 1))} disabled={zoomIdx === 0}>−</button>
          <span aria-live="polite">{Math.round(zoom * 100)}%</span>
          <button type="button" aria-label="Zoom in" onClick={() => setZoomIdx((z) => Math.min(ZOOMS.length - 1, z + 1))} disabled={zoomIdx === ZOOMS.length - 1}>+</button>
          <button type="button" aria-label="Reset zoom" onClick={() => setZoomIdx(2)} style={{ width: 'auto', padding: '0 8px', fontSize: 12 }}>Fit</button>
        </div>
        <div className="canvas-toolbar canvas-full" style={{ left: 'auto' }}>
          <button type="button" aria-label="Full screen" onClick={fullscreen}>⤢</button>
        </div>
        <div className="canvas-scroll" ref={scrollRef} onPointerDown={onPointerDown} onPointerMove={onPointerMove}
             onPointerUp={endDrag} onPointerLeave={endDrag}>
          <svg viewBox={viewBox} style={{ width: `${zoom * 100}%`, minWidth: `${zoom * 100}%`, height: `${zoom * 100}%`, display: 'block' }}
               preserveAspectRatio="xMidYMid meet" role="img" aria-label="Pattern pieces preview, not to scale for printing">
            <defs>
              <marker id="grain-arrow" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="4" markerHeight="4" orient="auto-start-reverse">
                <path d="M0 0 L10 5 L0 10 z" fill="#1b2620" />
              </marker>
            </defs>
            {laidOut.map(({ piece, idx, dx, dy, w, h, x0 }) => {
              const grain = piece.grain_line;
              const fold = piece.fold_line;
              const box = piece.cut_bounding_box || piece.bounding_box;
              return (
                <g key={`${piece.name}-${idx}`} data-testid={`piece-${idx}`}>
                  {Array.isArray(piece.cutting_line) && piece.cutting_line.length > 2 && (
                    <polygon data-testid={`cutting-line-${idx}`}
                             points={piece.cutting_line.map((q) => `${q[0] + dx},${q[1] + dy}`).join(' ')}
                             fill="#f6f1e6" stroke="#1d3a2e" strokeWidth="0.35" />
                  )}
                  <path d={piecePath(piece, dx, dy)} fill={piece.cutting_line ? 'none' : '#f6f1e6'} stroke="#3f7d62"
                        strokeWidth="0.28" strokeDasharray={piece.cutting_line ? '1.2,0.8' : undefined} />
                  {(piece.darts || []).map((d) => {
                    const pts = d.lower_apex ? [d.apex, d.leg_a, d.lower_apex, d.leg_b, d.apex] : [d.leg_a, d.apex, d.leg_b];
                    return <polyline key={d.id} points={pts.map((q) => `${q[0] + dx},${q[1] + dy}`).join(' ')} fill="none" stroke="#7a4d9a" strokeWidth="0.25" />;
                  })}
                  {(piece.notches || []).map((n) => (
                    <polygon key={n.id} data-testid={`notch-${n.id}`}
                             points={`${n.point[0] + dx - 0.5},${n.point[1] + dy - 0.5} ${n.point[0] + dx + 0.5},${n.point[1] + dy - 0.5} ${n.point[0] + dx},${n.point[1] + dy + 0.7}`}
                             fill="#c58a13" />
                  ))}
                  {fold && (
                    <line x1={fold.start[0] + dx} y1={fold.start[1] + dy} x2={fold.end[0] + dx} y2={fold.end[1] + dy} stroke="#b71c1c" strokeWidth="0.6" />
                  )}
                  {grain && (
                    <line x1={grain.start[0] + dx} y1={grain.start[1] + dy} x2={grain.end[0] + dx} y2={grain.end[1] + dy}
                          stroke="#1b2620" strokeWidth="0.22" markerStart="url(#grain-arrow)" markerEnd="url(#grain-arrow)" />
                  )}
                  <text x={x0 + w / 2} y={Math.min(h * 0.35, 18)} fill="#1b2620" fontSize="2" textAnchor="middle" fontWeight="600">
                    {(piece.name || `Piece ${idx + 1}`).toUpperCase()}
                  </text>
                  <text x={x0 + w / 2} y={Math.min(h * 0.35, 18) + 2.4} fill="#56625b" fontSize="1.6" textAnchor="middle">
                    {fmt(w)} × {fmt(box?.height_cm)} cm
                  </text>
                </g>
              );
            })}
          </svg>
        </div>
      </div>

      <div className="legend" aria-label="Legend">
        <span><i /> Cutting line</span>
        <span><i className="dash" /> Seam (sewing) line</span>
        <span><i className="fold" /> Fold</span>
        <span><i className="notch" /> Notch</span>
        <span>↕ Grainline</span>
        <span>Seam allowance included between the lines</span>
      </div>

      <div className="fabric-tags" style={{ marginTop: 12 }}>
        {list.map((piece, idx) => (
          <span key={`${piece.name}-chip-${idx}`} className="chip">
            {piece.name}
            {piece.cut_count ? ` × ${piece.cut_count}` : ''}
            {piece.cut_on_fold ? ' (cut on fold)' : ''}
          </span>
        ))}
      </div>

      <p className="form-hint" style={{ marginTop: 10 }}>
        Pattern Preview — Not to Scale for Printing. Prototype custom pattern, mathematically generated from your measurements and
        the confirmed design; geometry validated only (not fit-tested or professionally validated).
        {hasCut ? ' Solid outline = cutting line (seam allowance included); dashed line = sewing line; triangles = notches.'
          : ' Seam allowance geometry is not part of this record.'}
        {draftingBlock?.block_label ? ` Block: ${draftingBlock.block_label}.` : ''}
        {fabricWidth ? ` Fabric width reference: ${fabricWidth} cm.` : ''}
      </p>

      {Array.isArray(transformations) && transformations.length > 0 && (
        <details style={{ marginTop: 8 }}>
          <summary className="form-hint" style={{ cursor: 'pointer', fontWeight: 600 }}>Applied design transformations</summary>
          <ul data-testid="transformations" style={{ margin: '8px 0 0', paddingLeft: '18px', fontSize: '13px', color: 'var(--ink-2)' }}>
            {transformations.map((t) => (
              <li key={t.id}>
                <strong>{t.id.replace(/_/g, ' ')}</strong>: {t.type?.replace(/_/g, ' ')}
                {t.status && t.status !== 'applied' ? ` — ${t.status.replace(/_/g, ' ')}` : ''}
                {t.note ? ` (${t.note})` : ''}
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}
