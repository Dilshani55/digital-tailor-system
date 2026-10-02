// Phase 4 — the preview renders API geometry only (no hard-coded pieces).
import { fireEvent, render, screen } from '@testing-library/react';
import fs from 'node:fs';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import PatternPreview, { piecePath, outlinePoints, lengthText } from '../components/PatternPreview';

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
    expect(text).toMatch(/passed geometric validation only/);
    expect(text).toMatch(/confirm the fit with a test garment \(toile\)/);
    expect(text).not.toMatch(/perfect fit|industry standard|100% accurate|scientifically validated/i);
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
    expect(screen.getByTestId('armhole-sleeve').textContent).toMatch(/38\.6 cm .* 40\.6 cm .* difference 2\.0 cm/);
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

describe('PatternPreview: blocks with dimensions, why this size, sleeve check', () => {
  const dims = [
    { id: 'neck_width', label: 'Neck width', value_cm: 6, a: [0, 0], b: [6, 0], kind: 'linear', trace: 'front_neck_width' },
    { id: 'bust_width', label: 'Bust width', value_cm: 24.5, a: [0, 20], b: [24.5, 20], kind: 'linear', trace: 'front_bust_width' },
    { id: 'armhole_curve', label: 'Armhole curve', value_cm: 22.2, a: [19, 12], b: [19, 12], kind: 'curve', trace: null },
  ];
  const withDims = { ...front, dimensions: dims, cutting_line: [[0, 6], [7, -1], [26, 19], [24, 44], [0, 44]] };
  const sleeveDims = { ...sleeve, dimensions: [{ id: 'sleeve_width', label: 'Sleeve width', value_cm: 33, a: [0, 9], b: [33, 9], kind: 'linear', trace: 'sleeve_width' }] };
  const why = [
    { id: 'front_bust_width', label: 'Front width at the bust line', value_cm: 24.5, formula: '(88 + 8.89) / 4 + 1.27', source: 'method' },
    { id: 'front_neck_width', label: 'Front neck width', value_cm: 6, formula: 'back neck width 6.64 - 0.64', source: 'method' },
    { id: 'sleeve_width', label: 'Sleeve width at the underarm', value_cm: 33, formula: 'upper arm 28 + ease 7.62', source: 'extension' },
    { id: 'seam_allowance_side', label: 'Seam allowance: side', value_cm: 1.5, formula: 'outside the sewing line', source: 'seam' },
  ];
  const cap = { has_sleeve: true, bodice_armhole_seam_cm: 40.79, sleeve_cap_seam_cm: 42.07, difference_cm: 1.28,
    allowed_cm: [0.5, 4.5], difference_is: 'sleeve-cap ease', status: 'PASS', note: 'The sleeve cap fits the armhole.' };
  const show = (extra = {}) => render(<PatternPreview pieces={[withDims, sleeveDims]} whyThisSize={why} sleeveCap={cap} {...extra} />);

  it('has a tab for all pieces and one for each block that exists', () => {
    show();
    expect(screen.getByTestId('tab-all').getAttribute('aria-selected')).toBe('true');
    expect(screen.getByTestId('tab-front_bodice')).toBeTruthy();
    expect(screen.getByTestId('tab-sleeve')).toBeTruthy();
    expect(screen.queryByTestId('tab-back_bodice')).toBeNull();       // no back piece in this record: no invented tab
  });

  it('draws each dimension as a numbered line on the block and lists it with its calculation', () => {
    show();
    fireEvent.click(screen.getByTestId('tab-front_bodice'));
    const block = screen.getByTestId('block-front_bodice');
    expect(block.textContent).toMatch(/Cut 1 on fold/);
    dims.forEach((d) => expect(screen.getByTestId(`dim-${d.id}`)).toBeTruthy());
    expect(screen.getByTestId('dim-bust_width').querySelector('line')).toBeTruthy();
    expect(screen.getByTestId('dim-armhole_curve').querySelector('line')).toBeNull();      // a curve length: a marker, not a straight line
    const row = screen.getByTestId('dim-row-bust_width').textContent;
    expect(row).toMatch(/Bust width: 24\.5 cm \(9\.65 in\)/);
    expect(row).toMatch(/\(88 \+ 8\.89\) \/ 4 \+ 1\.27 — drafting method/);              // traceable to the customer's bust
    expect(screen.getByTestId('dim-row-armhole_curve').textContent).toMatch(/22\.2 cm/);
  });

  it('highlights the line on the drawing when its row is pointed at', () => {
    show();
    fireEvent.click(screen.getByTestId('tab-front_bodice'));
    expect(screen.getByTestId('dim-bust_width').getAttribute('data-active')).toBe('no');
    fireEvent.mouseEnter(screen.getByTestId('dim-row-bust_width'));
    expect(screen.getByTestId('dim-bust_width').getAttribute('data-active')).toBe('yes');
    expect(screen.getByTestId('dim-neck_width').getAttribute('data-active')).toBe('no');
    fireEvent.mouseLeave(screen.getByTestId('dim-row-bust_width'));
    expect(screen.getByTestId('dim-bust_width').getAttribute('data-active')).toBe('no');
  });

  it('shows lengths in the selected unit first', () => {
    show({ unit: 'in' });
    fireEvent.click(screen.getByTestId('tab-front_bodice'));
    expect(screen.getByTestId('dim-row-bust_width').textContent).toMatch(/Bust width: 9\.65 in \(24\.5 cm\)/);
    expect(lengthText(2.54, 'in')).toBe('1.00 in (2.5 cm)');
    expect(lengthText(2.54)).toBe('2.5 cm (1.00 in)');
    expect(lengthText(undefined)).toBe('—');
  });

  it('the sleeve tab reports the armhole against the sleeve cap with PASS or REVIEW', () => {
    show();
    fireEvent.click(screen.getByTestId('tab-sleeve'));
    const report = screen.getByTestId('sleeve-cap-report').textContent;
    expect(report).toMatch(/Bodice armhole seam40\.8 cm/);
    expect(report).toMatch(/Sleeve cap seam42\.1 cm/);
    expect(report).toMatch(/Difference1\.3 cm/);
    expect(report).toMatch(/Allowed sleeve-cap ease0\.5 to 4\.5 cm/);
    expect(screen.getByTestId('sleeve-cap-status').textContent).toMatch(/^PASS/);
  });

  it('can show the sewing line and the cutting line separately', () => {
    show();
    expect(screen.getByTestId('cutting-line-0')).toBeTruthy();
    expect(screen.getByTestId('seam-line-0')).toBeTruthy();
    fireEvent.click(screen.getByTestId('toggle-cut'));
    expect(screen.queryByTestId('cutting-line-0')).toBeNull();        // sewing line only
    expect(screen.getByTestId('seam-line-0')).toBeTruthy();
    fireEvent.click(screen.getByTestId('toggle-cut'));
    fireEvent.click(screen.getByTestId('toggle-seam'));
    expect(screen.getByTestId('cutting-line-0')).toBeTruthy();        // cutting line only
    expect(screen.queryByTestId('seam-line-0')).toBeNull();
  });

  it('"Why this size?" lists every calculation with where its rule comes from', () => {
    show({ draftingMethod: { name: 'Direct-measurement draft', source: { title: 'Pattern Making and Grading' } } });
    const table = screen.getByTestId('why-this-size');
    why.forEach((r) => expect(screen.getByTestId(`why-${r.id}`)).toBeTruthy());
    expect(screen.getByTestId('why-front_bust_width').textContent).toMatch(/drafting method/);
    expect(screen.getByTestId('why-sleeve_width').textContent).toMatch(/project rule/);
    expect(screen.getByTestId('why-seam_allowance_side').textContent).toMatch(/seam allowance/);
    expect(table.textContent).toMatch(/Pattern Making and Grading/);
    expect(table.textContent).not.toMatch(/Aldrich/);
  });

  it('shows the engine\'s warnings without hiding the pattern', () => {
    show({ warnings: [{ field: 'bicep_cm', code: 'SLEEVE_CAP_REVIEW', message: 'The cap height was changed a lot.' }] });
    expect(screen.getByTestId('pattern-warning').textContent).toMatch(/Please check: The cap height was changed a lot/);
    expect(screen.getByTestId('piece-0')).toBeTruthy();
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
