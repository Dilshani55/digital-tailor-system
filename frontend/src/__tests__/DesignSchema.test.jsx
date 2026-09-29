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
  it('has the four classifier heads and the 28-label taxonomy', () => {
    expect(HEADS).toEqual(['garment_type', 'neckline_type', 'sleeve_length', 'sleeve_style']);
    const total = HEADS.reduce((n, h) => n + DESIGN_SCHEMA[h].length, 0);
    expect(total).toBe(28);
    expect(ACTIVE_TAXONOMY_OPTIONS.neckline_type).toHaveLength(10);
  });

  it('every option has a support level and unsupported ones explain why', () => {
    HEADS.forEach((h) => DESIGN_SCHEMA[h].forEach((o) => {
      expect([IMPLEMENTED, APPROXIMATED, UNSUPPORTED]).toContain(o.support);
      if (o.support === UNSUPPORTED) expect(o.note.length).toBeGreaterThan(0);
    }));
  });

  it('reports unsupported selections instead of hiding them', () => {
    const r = supportReport({ garment_type: 'blouse', neckline_type: 'halter-neck',
      sleeve_length: 'short-sleeve', sleeve_style: 'puff-sleeve' });
    expect(r.supported).toBe(false);
    expect(r.unsupported.map((u) => u.value).sort()).toEqual(['halter-neck', 'puff-sleeve']);
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
    fireEvent.change(screen.getByTestId('select-sleeve_length'), { target: { value: 'elbow-length' } });
    fireEvent.click(screen.getByTestId('confirm-btn'));
    expect(onConfirm).toHaveBeenCalledWith({
      garment_type: 'blouse',          // accepted as predicted
      neckline_type: 'square-neck',    // corrected (model said v-neck)
      sleeve_length: 'elbow-length',   // corrected (model said long-sleeve)
      sleeve_style: 'regular-sleeve',
    });
  });

  it('still shows the real model confidence next to each head', () => {
    render(<PredictionReview garmentAttributes={garmentAttributes} />);
    expect(screen.getByTestId('confidence-tag-neckline_type').textContent).toContain('50.3%');
  });

  it('shows an unsupported alert and a per-head note for a style the engine cannot draft', () => {
    const attrs = { ...garmentAttributes, predictions: { ...garmentAttributes.predictions,
      sleeve_style: pred('puff-sleeve') } };
    render(<PredictionReview garmentAttributes={attrs} />);
    expect(screen.getByTestId('unsupported-alert').textContent).toMatch(/Puff Sleeve/);
    expect(screen.getByTestId('support-note-sleeve_style').textContent).toMatch(/Unsupported/);
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
    fireEvent.change(screen.getByTestId('select-sleeve_length'), { target: { value: 'sleeveless' } });
    expect(screen.getByTestId('consistency-error')).toBeTruthy();
    expect(screen.getByTestId('confirm-btn').disabled).toBe(true);
    fireEvent.change(screen.getByTestId('select-sleeve_style'), { target: { value: 'none' } });
    expect(screen.queryByTestId('consistency-error')).toBeNull();
    expect(screen.getByTestId('confirm-btn').disabled).toBe(false);
  });
});
