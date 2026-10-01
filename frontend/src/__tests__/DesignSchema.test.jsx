// Phase 1 — design-feature contract (frontend side).
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import PredictionReview, { ACTIVE_TAXONOMY_OPTIONS } from '../components/PredictionReview';
import {
  HEADS, DESIGN_SCHEMA, supportOf, supportReport, consistencyError,
  IMPLEMENTED, APPROXIMATED, UNSUPPORTED,
} from '../utils/designSchema';

const pred = (label, confidence = 0.8) => ({
  label, confidence, top_3: [{ class_name: label, class_index: 0, confidence }],
  requires_user_confirmation: false, threshold_used: 0.5,
});
const garmentAttributes = {
  model_version: 'YOLOv8MultiTaskClassifier|stage=Stage_B|epoch=7|sha256=3b69a470ed5d',
  predictions: {
    garment_type: pred('blouse'),
    neckline_type: pred('v-neck', 0.5026),
    sleeve_length: pred('long-sleeve'),
    sleeve_style: pred('regular-sleeve'),
  },
  low_confidence_heads: [],
};

describe('designSchema', () => {
  it('has the four features and their selectable classes (2 / 4 / 3 / 4); no crop top, no off-shoulder', () => {
    expect(HEADS).toEqual(['garment_type', 'neckline_type', 'sleeve_length', 'sleeve_style']);
    const total = HEADS.reduce((n, h) => n + DESIGN_SCHEMA[h].length, 0);
    expect(total).toBe(13);
    expect(HEADS.map((h) => DESIGN_SCHEMA[h].length)).toEqual([2, 4, 3, 4]);
    expect(ACTIVE_TAXONOMY_OPTIONS.garment_type.map((o) => o.value)).toEqual(['blouse', 't-shirt']);
    expect(ACTIVE_TAXONOMY_OPTIONS.neckline_type.map((o) => o.value))
      .toEqual(['round-neck', 'v-neck', 'square-neck', 'collared-neck']);
    expect(ACTIVE_TAXONOMY_OPTIONS.sleeve_length.map((o) => o.value)).toEqual(['sleeveless', 'short-sleeve', 'long-sleeve']);
    expect(ACTIVE_TAXONOMY_OPTIONS.sleeve_style.map((o) => o.value)).toEqual(['none', 'regular-sleeve', 'puff-sleeve', 'bell-sleeve']);
  });

  it('every option has a support level and unsupported ones explain why', () => {
    HEADS.forEach((h) => DESIGN_SCHEMA[h].forEach((o) => {
      expect([IMPLEMENTED, APPROXIMATED, UNSUPPORTED]).toContain(o.support);
      if (o.support === UNSUPPORTED) expect(o.note.length).toBeGreaterThan(0);
    }));
  });

  it('reports unsupported selections instead of hiding them', () => {
    // collared neck has no geometry; puff sleeves exist, but not for a T-shirt
    const r = supportReport({ garment_type: 't-shirt', neckline_type: 'collared-neck',
      sleeve_length: 'short-sleeve', sleeve_style: 'puff-sleeve' });
    expect(r.supported).toBe(false);
    expect(r.unsupported.map((u) => u.value).sort()).toEqual(['collared-neck', 'puff-sleeve']);
    expect(supportReport({ garment_type: 'blouse', neckline_type: 'round-neck',
      sleeve_length: 'short-sleeve', sleeve_style: 'regular-sleeve' }).supported).toBe(true);
  });

  it('flags a sleeveless garment with a sleeve style', () => {
    expect(consistencyError({ sleeve_length: 'sleeveless', sleeve_style: 'puff-sleeve' })).toMatch(/sleeveless/);
    expect(consistencyError({ sleeve_length: 'sleeveless', sleeve_style: 'none' })).toBe('');
    expect(supportOf('neckline_type', 'not-a-neckline')).toBeNull();
  });
});

describe('PredictionReview keeps user corrections', () => {
  it('sends the user-corrected values (not the raw predictions) on confirm', () => {
    const onConfirm = vi.fn();
    render(<PredictionReview garmentAttributes={garmentAttributes} onConfirm={onConfirm} />);
    fireEvent.change(screen.getByTestId('select-neckline_type'), { target: { value: 'square-neck' } });
    fireEvent.change(screen.getByTestId('select-sleeve_length'), { target: { value: 'short-sleeve' } });
    fireEvent.click(screen.getByTestId('confirm-btn'));
    expect(onConfirm).toHaveBeenCalledWith({
      garment_type: 'blouse',          // accepted as predicted
      neckline_type: 'square-neck',    // corrected (model said v-neck)
      sleeve_length: 'short-sleeve',   // corrected (model said long-sleeve)
      sleeve_style: 'regular-sleeve',
    });
  });

  it('still shows the real model confidence next to each head', () => {
    render(<PredictionReview garmentAttributes={garmentAttributes} />);
    expect(screen.getByTestId('confidence-tag-neckline_type').textContent).toContain('50.3%');
  });

  it('shows a style the engine cannot draft, does not pre-select it, and disables it', () => {
    const attrs = { ...garmentAttributes, predictions: { ...garmentAttributes.predictions,
      garment_type: pred('t-shirt'), sleeve_style: pred('puff-sleeve') } };   // puff is not drafted for a T-shirt
    render(<PredictionReview garmentAttributes={attrs} />);
    expect(screen.getByTestId('not-draftable-sleeve_style').textContent).toMatch(/Puff Sleeve.*cannot be drafted/);
    expect(screen.getByTestId('select-sleeve_style').value).toBe('');                  // not silently kept
    expect(screen.getByTestId('select-sleeve_style').querySelector('option[value="puff-sleeve"]').disabled).toBe(true);
    expect(screen.getByTestId('confirm-btn').disabled).toBe(true);
  });

  it('never allows confirming a combination outside the draftable scope', () => {
    render(<PredictionReview garmentAttributes={garmentAttributes} />);
    fireEvent.change(screen.getByTestId('select-garment_type'), { target: { value: 't-shirt' } });
    fireEvent.change(screen.getByTestId('select-neckline_type'), { target: { value: 'square-neck' } });
    expect(screen.getByTestId('select-neckline_type').querySelector('option[value="square-neck"]').disabled).toBe(true);
    expect(screen.getByTestId('unsupported-alert').textContent).toMatch(/Neckline Type: Square Neck/);
    expect(screen.getByTestId('confirm-btn').disabled).toBe(true);
  });

  it('shows no unsupported alert for a fully supported design', () => {
    const attrs = { ...garmentAttributes, predictions: { ...garmentAttributes.predictions,
      neckline_type: pred('round-neck') } };
    render(<PredictionReview garmentAttributes={attrs} />);
    expect(screen.queryByTestId('unsupported-alert')).toBeNull();
  });

  it('blocks confirmation of a contradictory sleeveless + style selection', () => {
    const onConfirm = vi.fn();
    render(<PredictionReview garmentAttributes={garmentAttributes} onConfirm={onConfirm} />);
    fireEvent.change(screen.getByTestId('select-garment_type'), { target: { value: 'blouse' } });
    fireEvent.change(screen.getByTestId('select-sleeve_length'), { target: { value: 'sleeveless' } });
    expect(screen.getByTestId('consistency-error')).toBeTruthy();
    expect(screen.getByTestId('confirm-btn').disabled).toBe(true);
    fireEvent.change(screen.getByTestId('select-sleeve_style'), { target: { value: 'none' } });
    expect(screen.queryByTestId('consistency-error')).toBeNull();
    expect(screen.getByTestId('confirm-btn').disabled).toBe(false);
  });
});

describe('project scope', () => {
  const sel = (g, n, s, st) => ({ garment_type: g, neckline_type: n, sleeve_length: s, sleeve_style: st });
  it('accepts every in-scope combination', () => {
    const ok = [
      sel('blouse', 'square-neck', 'long-sleeve', 'regular-sleeve'),
      sel('t-shirt', 'v-neck', 'short-sleeve', 'regular-sleeve'),
      sel('blouse', 'round-neck', 'sleeveless', 'none'),
    ];
    ok.forEach((s) => expect(supportReport(s).supported).toBe(true));
  });
  it('rejects out-of-scope combinations with a reason', () => {
    const bad = [
      sel('t-shirt', 'square-neck', 'short-sleeve', 'regular-sleeve'),
      sel('t-shirt', 'round-neck', 'sleeveless', 'none'),
      sel('t-shirt', 'round-neck', 'short-sleeve', 'puff-sleeve'),
    ];
    bad.forEach((s) => {
      const r = supportReport(s);
      expect(r.supported).toBe(false);
      expect(r.unsupported[0].note).toMatch(/supported scope/);
    });
  });
});
