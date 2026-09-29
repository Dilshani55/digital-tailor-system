// Phase 4 — the preview renders API geometry only (no hard-coded pieces).
import { render, screen } from '@testing-library/react';
import fs from 'node:fs';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import PatternPreview, { piecePath, outlinePoints } from '../components/PatternPreview';

const source = (rel) => fs.readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8');

// Geometry in the same shape the API returns (cm). Values here are test data only.
const front = {
  name: 'Front Bodice', piece_type: 'front_bodice', cut_count: 1, cut_on_fold: true,
  segments: [
    { id: 'neckline', type: 'cubic', p: [[0, 7], [3.3, 7], [6, 3.9], [6, 0]] },
    { id: 'shoulder', type: 'line', p: [[6, 0], [17.4, 3.7]] },
    { id: 'armhole', type: 'cubic', p: [[17.4, 3.7], [17, 12], [20.6, 20], [24.5, 20]] },
    { id: 'side_seam_1', type: 'line', p: [[24.5, 20], [22, 42]] },
    { id: 'hem', type: 'line', p: [[22, 42], [0, 42]] },
    { id: 'centre_line', type: 'line', p: [[0, 42], [0, 7]] },
  ],
  outline: [[0, 7], [6, 0], [17.4, 3.7], [24.5, 20], [22, 42], [0, 42]],
  bounding_box: { width_cm: 24.5, height_cm: 42, min_x: 0, min_y: 0 },
  grain_line: { start: [12, 20], end: [12, 40] },
  fold_line: { start: [0, 7], end: [0, 42] },
  darts: [{ id: 'front_waist_dart', type: 'open', apex: [10, 25], leg_a: [8.7, 42], leg_b: [11.3, 42], intake_cm: 2.5 }],
};
const sleeve = {
  name: 'Sleeve (short)', piece_type: 'sleeve', cut_count: 2, cut_on_fold: false,
  segments: [
    { id: 'cap_left', type: 'cubic', p: [[0, 9], [0, 4], [7, 0], [16.5, 0]] },
    { id: 'hem', type: 'line', p: [[16.5, 0], [0, 22]] },
  ],
  bounding_box: { width_cm: 33, height_cm: 22, min_x: 0, min_y: 0 },
  grain_line: { start: [16.5, 9], end: [16.5, 22] }, darts: [],
};

describe('piecePath', () => {
  it('emits real cubic Bezier commands from segment data', () => {
    const d = piecePath(front);
    expect(d.startsWith('M 0 7')).toBe(true);
    expect((d.match(/ C /g) || []).length).toBe(2);           // neckline + armhole kept as curves
    expect(d).toContain('C 17 12, 20.6 20, 24.5 20');        // armhole control points preserved exactly
    expect(d.endsWith('Z')).toBe(true);
  });

  it('shifts every coordinate, including control points', () => {
    expect(piecePath(front, 10, 5)).toContain('C 27 17, 30.6 25, 34.5 25');
  });

  it('falls back to the flattened outline for records without segments', () => {
    const d = piecePath({ outline: [[0, 0], [4, 0], [4, 3]] });
    expect(d).toBe('M 0 0 L 4 0 L 4 3 Z');
    expect(outlinePoints({ outline: [{ x: 1, y: 2 }] })).toEqual([[1, 2]]);
  });
});

describe('PatternPreview', () => {
  it('is labelled not-to-scale and prototype / geometry-validated only', () => {
    render(<PatternPreview pieces={[front, sleeve]} />);
    expect(screen.getByText(/Pattern Preview — Not to Scale for Printing/)).toBeTruthy();
    const text = document.body.textContent;
    expect(text).toMatch(/geometry validated only/);
    expect(text).toMatch(/not fit-tested or professionally validated/);
    expect(text).not.toMatch(/true-scale|Download true-scale|already included/i);
  });

  it('draws one path per API piece with curves, darts, fold and grain lines', () => {
    const { container } = render(<PatternPreview pieces={[front, sleeve]} />);
    expect(container.querySelectorAll('[data-testid^="piece-"]')).toHaveLength(2);
    const paths = [...container.querySelectorAll('svg path')].map((p) => p.getAttribute('d'));
    expect(paths.filter((d) => d.includes(' C ')).length).toBe(2);
    expect(container.querySelectorAll('svg polyline')).toHaveLength(1);       // the front dart
    expect(container.querySelectorAll('svg line').length).toBeGreaterThanOrEqual(3);   // fold + 2 grain lines
    expect(screen.getByText('FRONT BODICE')).toBeTruthy();
    expect(screen.getByText(/24\.5 × 42\.0 cm/)).toBeTruthy();                // label comes from bounding_box
  });

  it('shows cut quantities and fold status from the geometry metadata', () => {
    render(<PatternPreview pieces={[front, sleeve]} />);
    expect(screen.getByText(/Front Bodice × 1 \(cut on fold\)/)).toBeTruthy();
    expect(screen.getByText(/Sleeve \(short\) × 2/)).toBeTruthy();
  });

  it('shows armhole and sleeve-cap seam numbers and validation success', () => {
    render(<PatternPreview pieces={[front]} validation={{ passed: true, errors: [] }}
      armholeSleeve={{ front_armhole_seam_cm: 19.47, back_armhole_seam_cm: 19.19, total_armhole_seam_cm: 38.62,
        sleeve_cap_seam_cm: 40.62, cap_ease_cm: 2 }} />);
    expect(screen.getByText('Geometry validation passed')).toBeTruthy();
    expect(screen.getByTestId('armhole-sleeve').textContent).toMatch(/38\.6 cm .* 40\.6 cm .* ease 2\.0 cm/);
  });

  it('shows validation errors when geometry validation failed', () => {
    render(<PatternPreview pieces={[front]} validation={{ passed: false, errors: ['Front Bodice: outline self-intersects'] }} />);
    expect(screen.getByText('Geometry validation failed')).toBeTruthy();
    expect(screen.getByText(/outline self-intersects/)).toBeTruthy();
  });

  it('lists design transformations, flagging ones that were not applied', () => {
    render(<PatternPreview pieces={[front]} transformations={[
      { id: 'neckline', type: 'v_neckline', status: 'applied' },
      { id: 'neckline_style', type: 'round_neckline', status: 'not_applied_fallback_round', note: 'scoop NOT applied' },
    ]} />);
    const list = screen.getByTestId('transformations').textContent;
    expect(list).toMatch(/v neckline/);
    expect(list).toMatch(/not applied fallback round/);
  });

  it('renders an honest empty state without inventing pieces', () => {
    render(<PatternPreview pieces={[]} />);
    expect(screen.getByText(/No pattern geometry available yet/)).toBeTruthy();
    expect(document.querySelectorAll('svg path')).toHaveLength(0);
  });
});

describe('Upload step 3 uses the real renderer', () => {
  const upload = source('../pages/Upload.jsx');
  it('contains no hard-coded piece dimensions, shapes or fixed dart claims', () => {
    for (const fake of ['44cm × 40cm', '46cm × 42cm', 'BACK BODICE', 'M 0 0 L 140 0', 'Fitted Bust Dart',
      'Aldrich', '27.5cm × 22cm']) {
      expect(upload).not.toContain(fake);
    }
  });
  it('renders PatternPreview from the API response', () => {
    expect(upload).toContain('<PatternPreview');
    expect(upload).toContain('patternData?.pattern_pieces');
    expect(upload).toContain('patternData?.armhole_sleeve');
  });
});

describe('preview component source', () => {
  it('defines no piece dimensions of its own', () => {
    const src = source('../components/PatternPreview.jsx');
    expect(src).not.toMatch(/width_cm:\s*\d|height_cm:\s*\d/);
    expect(src).toContain('Not to Scale for Printing');
  });
});
