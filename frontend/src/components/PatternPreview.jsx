import { useRef, useState } from 'react';

/**
 * Pattern Preview — renders the geometry returned by the API. It contains NO piece dimensions of
 * its own: every outline comes from `piece.segments` (lines + cubic Bezier curves, cm) or, for
 * older records, from the flattened `piece.outline`; every dimension shown comes from `piece.dimensions`
 * and every calculation from the engine's "why this size" list.
 *
 * "Not to scale for printing": pieces are fit to the view. The printable 1:1 tiled PDF is produced by the
 * export step. Tabs: all pieces side by side, or one block (Front / Back / Sleeve) with its dimensions drawn on
 * it as numbered lines and listed beside it.
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

/** A length in the selected unit first, the other unit in brackets (1 in = 2.54 cm). */
export function lengthText(cm, unit = 'cm') {
  if (!Number.isFinite(Number(cm))) return '—';
  const c = `${Number(cm).toFixed(1)} cm`;
  const i = `${(Number(cm) / 2.54).toFixed(2)} in`;
  return unit === 'in' ? `${i} (${c})` : `${c} (${i})`;
}

const SOURCE_WORDS = {
  measurement: 'your measurement', method: 'drafting method', figure: 'drafting method (figure)',
  design: 'design value', ease: 'ease', seam: 'seam allowance', extension: 'project rule',
};
const TABS = [
  { id: 'all', label: 'All pieces' },
  { id: 'front_bodice', label: 'Front' },
  { id: 'back_bodice', label: 'Back' },
  { id: 'sleeve', label: 'Sleeve' },
];
const ZOOMS = [0.5, 0.75, 1, 1.5, 2, 3];

function PieceShapes({ piece, idx, dx, dy, showSeam, showCut }) {
  const grain = piece.grain_line;
  const fold = piece.fold_line;
  const hasCut = Array.isArray(piece.cutting_line) && piece.cutting_line.length > 2;
  return (
    <>
      {hasCut && showCut && (
        <polygon data-testid={`cutting-line-${idx}`}
                 points={piece.cutting_line.map((q) => `${q[0] + dx},${q[1] + dy}`).join(' ')}
                 fill="#f6f1e6" stroke="#1d3a2e" strokeWidth="0.35" />
      )}
      {(showSeam || !hasCut) && (
        <path data-testid={`seam-line-${idx}`} d={piecePath(piece, dx, dy)} fill={hasCut && showCut ? 'none' : '#f6f1e6'} stroke="#3f7d62"
              strokeWidth="0.28" strokeDasharray={hasCut && showCut ? '1.2,0.8' : undefined} />
      )}
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
    </>
  );
}

function boxOf(piece) {
  const box = piece.cut_bounding_box || piece.bounding_box || {};
  const pts = outlinePoints(piece);
  const minX = box.min_x ?? Math.min(...pts.map((p) => p[0]));
  const minY = box.min_y ?? Math.min(...pts.map((p) => p[1]));
  const w = box.width_cm ?? Math.max(...pts.map((p) => p[0])) - minX;
  const h = box.height_cm ?? Math.max(...pts.map((p) => p[1])) - minY;
  return { minX, minY, w, h };
}

/** One block with its dimensions: numbered lines on the drawing, the same numbers in the list. */
function BlockView({ piece, idx, unit, trace, zoom, showSeam, showCut, sleeveCap }) {
  const [hot, setHot] = useState(null);
  const { minX, minY, w, h } = boxOf(piece);
  const pad = 4;
  const dx = -minX;
  const dy = -minY;
  const dims = piece.dimensions || [];
  const title = { front_bodice: 'Front', back_bodice: 'Back', sleeve: 'Sleeve' }[piece.piece_type] || piece.name;
  const cut = piece.cut_on_fold ? `Cut ${piece.cut_count} on fold` : `Cut ${piece.cut_count}`;
  return (
    <div className="block-view" data-testid={`block-${piece.piece_type}`}
         style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(280px, 100%), 1fr))', gap: 16, alignItems: 'start' }}>
      <div className="pattern-canvas" style={{ minWidth: 0 }}>
        <div className="canvas-scroll">
          <svg viewBox={`${-pad} ${-pad} ${w + pad * 2} ${h + pad * 2}`} style={{ width: `${zoom * 100}%`, minWidth: `${zoom * 100}%`, display: 'block' }}
               preserveAspectRatio="xMidYMid meet" role="img" aria-label={`${title} block with its dimensions, not to scale for printing`}>
            <PieceShapes piece={piece} idx={idx} dx={dx} dy={dy} showSeam={showSeam} showCut={showCut} />
            {dims.map((d, n) => {
              const a = [d.a[0] + dx, d.a[1] + dy];
              const b = [d.b[0] + dx, d.b[1] + dy];
              const on = hot === d.id;
              const mid = [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2];
              return (
                <g key={d.id} data-testid={`dim-${d.id}`} data-active={on ? 'yes' : 'no'} style={{ cursor: 'pointer' }}
                   onMouseEnter={() => setHot(d.id)} onMouseLeave={() => setHot(null)} onClick={() => setHot(on ? null : d.id)}>
                  {d.kind !== 'curve' && <line x1={a[0]} y1={a[1]} x2={b[0]} y2={b[1]} stroke={on ? '#b91c1c' : '#b45309'} strokeWidth={on ? 0.7 : 0.35} />}
                  <circle cx={mid[0]} cy={mid[1]} r={on ? 1.9 : 1.5} fill="#fff" stroke={on ? '#b91c1c' : '#b45309'} strokeWidth="0.3" />
                  <text x={mid[0]} y={mid[1] + 0.6} fontSize="1.7" textAnchor="middle" fontWeight="700" fill={on ? '#b91c1c' : '#b45309'}>{n + 1}</text>
                </g>
              );
            })}
          </svg>
        </div>
      </div>
      <div style={{ minWidth: 0 }}>
        <h3 style={{ margin: '0 0 4px' }}>{title} <small className="form-hint" style={{ fontWeight: 400 }}>· {cut}</small></h3>
        <p className="form-hint" style={{ marginTop: 0 }}>Sewing-line dimensions, without seam allowance. Point at a row to see it on the drawing.</p>
        <ol className="dim-list" data-testid={`dims-${piece.piece_type}`} style={{ margin: 0, paddingLeft: 22, fontSize: 13 }}>
          {dims.map((d) => {
            const row = trace[d.trace];
            const on = hot === d.id;
            return (
              <li key={d.id} data-testid={`dim-row-${d.id}`} tabIndex={0} onMouseEnter={() => setHot(d.id)} onMouseLeave={() => setHot(null)}
                  onFocus={() => setHot(d.id)} onBlur={() => setHot(null)}
                  style={{ padding: '3px 6px', borderRadius: 6, background: on ? 'rgba(180, 83, 9, 0.12)' : 'transparent' }}>
                <strong>{d.label}</strong>: {lengthText(d.value_cm, unit)}
                {row && <small className="form-hint" style={{ display: 'block' }}>{row.formula} — {SOURCE_WORDS[row.source] || row.source}</small>}
              </li>
            );
          })}
        </ol>
        {piece.piece_type === 'sleeve' && sleeveCap?.has_sleeve && (
          <table className="hist-table" data-testid="sleeve-cap-report" style={{ marginTop: 12, fontSize: 13 }}>
            <caption style={{ textAlign: 'left', fontWeight: 700, paddingBottom: 4 }}>Does the sleeve fit the armhole?</caption>
            <tbody>
              <tr><th scope="row">Bodice armhole seam</th><td>{lengthText(sleeveCap.bodice_armhole_seam_cm, unit)}</td></tr>
              <tr><th scope="row">Sleeve cap seam</th><td>{lengthText(sleeveCap.sleeve_cap_seam_cm, unit)}</td></tr>
              <tr><th scope="row">Difference</th><td>{lengthText(sleeveCap.difference_cm, unit)}</td></tr>
              <tr><th scope="row">Allowed {sleeveCap.difference_is}</th><td>{fmt(sleeveCap.allowed_cm?.[0])} to {fmt(sleeveCap.allowed_cm?.[1])} cm</td></tr>
              <tr><th scope="row">Status</th><td data-testid="sleeve-cap-status"><strong style={{ color: sleeveCap.status === 'REVIEW' ? '#b91c1c' : '#166534' }}>{sleeveCap.status}</strong> — {sleeveCap.note}</td></tr>
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

export default function PatternPreview({
  pieces = [],
  fabricWidth = null,
  validation = null,
  draftingBlock = null,
  armholeSleeve = null,
  transformations = null,
  whyThisSize = null,
  sleeveCap = null,
  draftingMethod = null,
  ease = null,
  warnings = null,
  unit = 'cm',
}) {
  const [zoomIdx, setZoomIdx] = useState(2);
  const [tab, setTab] = useState('all');
  const [showSeam, setShowSeam] = useState(true);
  const [showCut, setShowCut] = useState(true);
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
    const { minX, minY, w, h } = boxOf(piece);
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
  const trace = Object.fromEntries((whyThisSize || []).map((r) => [r.id, r]));
  const tabs = TABS.filter((t) => t.id === 'all' || list.some((p) => p.piece_type === t.id));
  const single = tab === 'all' ? null : list.findIndex((p) => p.piece_type === tab);

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
                difference {fmt(armholeSleeve.cap_ease_cm)} cm{sleeveCap?.status ? ` · ${sleeveCap.status}` : ''}
              </small>
            )}
          </div>
        </div>
      )}
      {(warnings || []).map((w) => (
        <div key={w.code + w.field} role="status" className="alert warn" data-testid="pattern-warning" style={{ marginBottom: 8 }}>Please check: {w.message}</div>
      ))}

      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center', margin: '8px 0' }}>
        <div className="segmented" role="tablist" aria-label="Pattern pieces">
          {tabs.map((t) => (
            <button key={t.id} type="button" role="tab" aria-selected={tab === t.id} aria-pressed={tab === t.id}
                    data-testid={`tab-${t.id}`} onClick={() => setTab(t.id)}>{t.label}</button>
          ))}
        </div>
        <label className="form-hint" style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
          <input type="checkbox" checked={showSeam} data-testid="toggle-seam" onChange={(e) => setShowSeam(e.target.checked)} /> Sewing line
        </label>
        <label className="form-hint" style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
          <input type="checkbox" checked={showCut} data-testid="toggle-cut" onChange={(e) => setShowCut(e.target.checked)} disabled={!hasCut} /> Cutting line (seam allowance)
        </label>
        <span className="canvas-toolbar" role="group" aria-label="Zoom" style={{ position: 'static' }}>
          <button type="button" aria-label="Zoom out" onClick={() => setZoomIdx((z) => Math.max(0, z - 1))} disabled={zoomIdx === 0}>−</button>
          <span aria-live="polite">{Math.round(zoom * 100)}%</span>
          <button type="button" aria-label="Zoom in" onClick={() => setZoomIdx((z) => Math.min(ZOOMS.length - 1, z + 1))} disabled={zoomIdx === ZOOMS.length - 1}>+</button>
          <button type="button" aria-label="Reset zoom" onClick={() => setZoomIdx(2)} style={{ width: 'auto', padding: '0 8px', fontSize: 12 }}>Fit</button>
        </span>
      </div>

      <svg width="0" height="0" style={{ position: 'absolute' }} aria-hidden="true">
        <defs>
          <marker id="grain-arrow" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="4" markerHeight="4" orient="auto-start-reverse">
            <path d="M0 0 L10 5 L0 10 z" fill="#1b2620" />
          </marker>
        </defs>
      </svg>

      {single === null ? (
        <div className="pattern-canvas" ref={frameRef}>
          <div className="canvas-toolbar canvas-full" style={{ left: 'auto' }}>
            <button type="button" aria-label="Full screen" onClick={fullscreen}>⤢</button>
          </div>
          <div className="canvas-scroll" ref={scrollRef} onPointerDown={onPointerDown} onPointerMove={onPointerMove}
               onPointerUp={endDrag} onPointerLeave={endDrag}>
            <svg viewBox={viewBox} style={{ width: `${zoom * 100}%`, minWidth: `${zoom * 100}%`, height: `${zoom * 100}%`, display: 'block' }}
                 preserveAspectRatio="xMidYMid meet" role="img" aria-label="Pattern pieces preview, not to scale for printing">
              {laidOut.map(({ piece, idx, dx, dy, w, h, x0 }) => {
                const box = piece.cut_bounding_box || piece.bounding_box;
                return (
                  <g key={`${piece.name}-${idx}`} data-testid={`piece-${idx}`}>
                    <PieceShapes piece={piece} idx={idx} dx={dx} dy={dy} showSeam={showSeam} showCut={showCut} />
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
      ) : (
        <BlockView piece={list[single]} idx={single} unit={unit} trace={trace} zoom={zoom} showSeam={showSeam} showCut={showCut} sleeveCap={sleeveCap} />
      )}

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
        Pattern Preview — Not to Scale for Printing. Prototype custom pattern, generated from your measurements and the confirmed
        design{draftingMethod?.name ? ` using: ${draftingMethod.name}` : ''}. The calculation passed geometric validation only; confirm the fit
        with a test garment (toile) before cutting the final fabric.
        {hasCut ? ' Solid outline = cutting line (seam allowance included); dashed line = sewing line; triangles = notches.'
          : ' Seam allowance geometry is not part of this record.'}
        {draftingBlock?.block_label ? ` Block: ${draftingBlock.block_label}.` : ''}
        {ease?.fit_label ? ` ${ease.fit_label}: bust +${fmt(ease.bust_cm)} cm, waist +${fmt(ease.waist_cm)} cm, hip +${fmt(ease.hip_cm)} cm of ease.` : ''}
        {fabricWidth ? ` Fabric width reference: ${fabricWidth} cm.` : ''}
        {' '}The cutting layout on 36&quot;, 45&quot; and 60&quot; fabric is in the next step.
      </p>

      {Array.isArray(whyThisSize) && whyThisSize.length > 0 && (
        <details style={{ marginTop: 8 }} data-testid="why-this-size">
          <summary className="form-hint" style={{ cursor: 'pointer', fontWeight: 600 }}>Why this size? — how every dimension was calculated</summary>
          <div className="table-wrap" style={{ marginTop: 8 }}>
            <table className="hist-table" style={{ fontSize: 13 }}>
              <thead><tr><th>Dimension</th><th>Value</th><th>How it is calculated (cm)</th><th>From</th></tr></thead>
              <tbody>
                {whyThisSize.map((r) => (
                  <tr key={r.id} data-testid={`why-${r.id}`}>
                    <td>{r.label}</td>
                    <td style={{ whiteSpace: 'nowrap' }}>{lengthText(r.value_cm, unit)}</td>
                    <td>{r.formula}</td>
                    <td>{SOURCE_WORDS[r.source] || r.source}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {draftingMethod?.source?.title && (
            <p className="form-hint" style={{ marginTop: 6 }}>
              Drafting method: {draftingMethod.source.title}. “Project rule” = needed for this project and not covered by that source;
              it must be confirmed by a fitting trial.
            </p>
          )}
        </details>
      )}

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
