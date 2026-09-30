// Illustration of A4 tiling for the saved pieces: the pieces are placed side by side and the grid of A4
// printable areas (19.0 x 27.7 cm, 1 cm overlap — the same constants as the PDF) is drawn over them.
// The PDF arranges the pieces itself; the real page count comes from the server.
const TILE_W = 19.0;
const TILE_H = 27.7;
const OVERLAP = 1.0;
const GAP = 2.0;

export default function TilePreview({ pieces = [], pages }) {
  const list = pieces.filter((p) => Array.isArray(p?.cutting_line) && p.cutting_line.length > 2);
  if (!list.length) return null;
  let x = 0;
  const placed = list.map((p) => {
    const xs = p.cutting_line.map((q) => q[0]);
    const ys = p.cutting_line.map((q) => q[1]);
    const minX = Math.min(...xs);
    const minY = Math.min(...ys);
    const w = Math.max(...xs) - minX;
    const h = Math.max(...ys) - minY;
    const at = { p, dx: x - minX, dy: -minY, w, h, x0: x };
    x += w + GAP;
    return at;
  });
  const width = x - GAP;
  const height = Math.max(...placed.map((q) => q.h));
  const stepX = TILE_W - OVERLAP;
  const stepY = TILE_H - OVERLAP;
  const cols = Math.max(1, Math.ceil((width - OVERLAP) / stepX));
  const rows = Math.max(1, Math.ceil((height - OVERLAP) / stepY));
  const W = cols * stepX + OVERLAP;
  const H = rows * stepY + OVERLAP;
  return (
    <figure style={{ margin: 0 }} data-testid="tile-preview">
      <svg viewBox={`-1 -1 ${W + 2} ${H + 2}`} role="img"
           aria-label={`Illustration of the pattern pieces on a grid of ${cols} by ${rows} A4 tiles`}>
        <rect x="0" y="0" width={W} height={H} fill="#fbfcfa" />
        {placed.map(({ p, dx, dy }, i) => (
          <polygon key={`${p.name}-${i}`} points={p.cutting_line.map((q) => `${q[0] + dx},${q[1] + dy}`).join(' ')}
                   fill="#f3eee2" stroke="#2c5b45" strokeWidth="0.35" />
        ))}
        {Array.from({ length: cols }, (_, c) => Array.from({ length: rows }, (__, r) => (
          <g key={`${c}-${r}`}>
            <rect x={c * stepX} y={r * stepY} width={TILE_W} height={TILE_H} fill="none" stroke="#8a948e" strokeWidth="0.25" strokeDasharray="1 0.8" />
            <text x={c * stepX + 0.8} y={r * stepY + 2} fontSize="1.8" fill="#56625b">{String.fromCharCode(65 + r)}{c + 1}</text>
          </g>
        )))}
        <rect x="0.8" y={H - 5.8} width="5" height="5" fill="none" stroke="#1b2620" strokeWidth="0.3" />
      </svg>
      <figcaption className="form-hint" style={{ marginTop: 8 }}>
        Illustration of A4 tiling (19 × 27.7 cm printable area, 1 cm overlap) with the 5 × 5 cm test square.
        {pages ? ` The generated PDF has ${pages} pages.` : ''}
      </figcaption>
    </figure>
  );
}
