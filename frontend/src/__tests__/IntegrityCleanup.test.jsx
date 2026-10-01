// Regression tests for the research-integrity cleanup (Step 1):
// the UI must never display fabricated results when real data is absent.
import { render, screen, waitFor } from '@testing-library/react';
import React from 'react';
import fs from 'node:fs';
import { fileURLToPath } from 'node:url';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import History from '../pages/History';
import { patternsAPI } from '../services/api';
import { formatResult, NOT_CALCULATED, CALCULATION_FAILED } from '../utils/results';

vi.mock('../services/api', () => ({
  patternsAPI: { getAll: vi.fn(), delete: vi.fn() },
  exportAPI: { download: vi.fn(), delete: vi.fn(), pdf: vi.fn() },
}));

const source = (rel) => fs.readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8');

describe('formatResult (fabric length / utilisation display)', () => {
  it('shows "Not calculated" when the backend produced no value', () => {
    for (const absent of [undefined, null, '', NaN]) {
      expect(formatResult(absent, 'm')).toBe(NOT_CALCULATED);
      expect(formatResult(absent, '%')).toBe(NOT_CALCULATED);
    }
  });

  it('shows "Calculation failed" when the calculation errored', () => {
    expect(formatResult(undefined, 'm', true)).toBe(CALCULATION_FAILED);
  });

  it('shows real values, including a genuine zero', () => {
    expect(formatResult(1.83, 'm')).toBe('1.83m');
    expect(formatResult(61.5, '%')).toBe('61.5%');
    expect(formatResult(0, '%')).toBe('0%');
  });
});

describe('Upload wizard contains no fabricated result fallbacks', () => {
  const upload = source('../pages/Upload.jsx');

  it.each([
    "'0.58m'", "'78.7%'", '|| 0.58', '|| 1.7', '|| 0.06',
    'Front ×1, Back ×1, Short Sleeve ×2', "|| 88) + 10", "|| 70) + 8", "|| 94) + 10",
  ])('does not contain %s', (fake) => {
    expect(upload).not.toContain(fake);
  });

  it('routes displayed results through formatResult', () => {
    expect(upload).toContain("from '../utils/results'");
  });

  it('does not swallow fabric-width recalculation errors', () => {
    expect(upload).not.toMatch(/catch \(err\) \{\}/);
  });
});

describe('History page shows stored data or "unavailable"', () => {
  beforeEach(() => vi.clearAllMocks());
  const renderHistory = () => render(<MemoryRouter><History /></MemoryRouter>);

  it('does not show hard-coded garment/fabric/efficiency values for records without them', async () => {
    patternsAPI.getAll.mockResolvedValue({ data: { patterns: [
      { pattern_id: 'p1', generated_at: '2026-09-01T10:00:00', exports: [{ export_id: 'e1', filename: 'pattern_abc.pdf' }] },
    ] } });
    renderHistory();
    await screen.findByText('Garment unavailable');
    expect(screen.getByText('Design details unavailable')).toBeTruthy();
    expect(screen.getByText(/Fabric unavailable/)).toBeTruthy();
    expect(screen.getByText('Fabric width unavailable')).toBeTruthy();
    expect(screen.getByText('Not calculated')).toBeTruthy();
    const text = document.body.textContent;
    for (const fake of ['V-neck', 'Short sleeve', '1.83', '71%', 'optimized']) {
      expect(text).not.toContain(fake);
    }
  });

  it('shows the real stored values when they exist', async () => {
    patternsAPI.getAll.mockResolvedValue({ data: { patterns: [{
      pattern_id: 'p2', generated_at: '2026-09-01T10:00:00', exports: [{ export_id: 'e2', filename: 'pattern_xyz.pdf' }],
      garment_type: 'crop-top', neckline_type: 'square-neck', sleeve_length: 'sleeveless',
      selected_fabric_name: 'Cotton Poplin', yardage_metres: 0.75,
      nesting_summary: { fabric_width_cm: 150, utilisation_percent: 43.2 },
    }] } });
    renderHistory();
    await screen.findByText('Crop top');
    expect(screen.getByText('Square neck · Sleeveless')).toBeTruthy();
    expect(screen.getByText('Cotton Poplin · 0.75 m')).toBeTruthy();
    expect(screen.getByText('150 cm fabric width')).toBeTruthy();
    expect(screen.getByText('43.2% utilisation')).toBeTruthy();
  });

  it('reports a load failure instead of pretending the library is empty', async () => {
    patternsAPI.getAll.mockRejectedValue(new Error('network'));
    renderHistory();
    const alert = await screen.findByRole('alert');
    expect(alert.textContent).toMatch(/Could not load/);
    expect(screen.queryByText('Your pattern library is empty')).toBeNull();
  });
});
