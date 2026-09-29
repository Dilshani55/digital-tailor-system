// Phase 2 — measurement validation, unit conversion and field-level errors in the React form.
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import React from 'react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import Upload from '../pages/Upload';
import { measurementsAPI } from '../services/api';
import {
  FIELD_KEYS, CORE_FIELDS, validateMeasurements, convertDisplayValues, parseFieldErrors,
  buildPayload, parseEntry, toCm, rangeText, MEASUREMENT_FIELDS,
} from '../utils/measurementSchema';

vi.mock('../services/api', () => ({
  imagesAPI: { upload: vi.fn(), analyse: vi.fn(), confirmAttributes: vi.fn() },
  measurementsAPI: { save: vi.fn(), getAll: vi.fn() },
  patternsAPI: { generate: vi.fn() },
  exportAPI: { yardage: vi.fn(), pdf: vi.fn(), download: vi.fn() },
  researchAPI: { submitFeedback: vi.fn() },
}));
// Heavy 3D / recommendation widgets are irrelevant here.
vi.mock('../components/MeasurementGuide', () => ({ default: () => <div data-testid="guide-stub" /> }));
vi.mock('../components/FabricRecommendation', () => ({ default: () => <div data-testid="fabric-stub" /> }));

const VALID = {
  bust_cm: 88, waist_cm: 70, hip_cm: 94, height_cm: 162, neck_cm: 36, shoulder_cm: 12, across_back_cm: 34,
  back_waist_length_cm: 40, armhole_depth_cm: 20, garment_length_cm: 65, bicep_cm: 28, sleeve_cm: 55, wrist_cm: 16,
};

describe('measurementSchema utils', () => {
  it('defines the 13 fields with the core four', () => {
    expect(FIELD_KEYS).toHaveLength(13);
    expect(CORE_FIELDS).toEqual(['bust_cm', 'waist_cm', 'hip_cm', 'height_cm']);
  });

  it('accepts typical measurements', () => {
    expect(validateMeasurements(VALID, 'cm')).toEqual({});
  });

  it('reports missing, non-numeric, non-finite, zero, negative and implausible values per field', () => {
    const errors = validateMeasurements(
      { ...VALID, bust_cm: '', waist_cm: 'abc', hip_cm: 0, height_cm: -5, neck_cm: Infinity, shoulder_cm: 99 }, 'cm');
    expect(errors.bust_cm).toMatch(/required/);
    expect(errors.waist_cm).toMatch(/not a number/);
    expect(errors.hip_cm).toMatch(/greater than 0/);
    expect(errors.height_cm).toMatch(/greater than 0/);
    expect(errors.neck_cm).toMatch(/finite/);
    expect(errors.shoulder_cm).toMatch(/plausible range/);
    expect(Object.keys(errors)).not.toContain('sleeve_cm');
  });

  it('checks every range boundary', () => {
    MEASUREMENT_FIELDS.forEach((f) => {
      expect(validateMeasurements({ [f.key]: f.min }, 'cm', [])).toEqual({});
      expect(validateMeasurements({ [f.key]: f.max }, 'cm', [])).toEqual({});
      expect(validateMeasurements({ [f.key]: f.min - 0.01 }, 'cm', [])[f.key]).toBeTruthy();
      expect(validateMeasurements({ [f.key]: f.max + 0.01 }, 'cm', [])[f.key]).toBeTruthy();
    });
  });

  it('validates in the entered unit (inches converted before the range check)', () => {
    expect(validateMeasurements({ bust_cm: 34.65 }, 'in', [])).toEqual({});     // 88 cm
    expect(validateMeasurements({ bust_cm: 88 }, 'in', [])).toHaveProperty('bust_cm');  // 223 cm
  });

  it('converts between units with the exact 2.54 factor and keeps blanks blank', () => {
    const inches = convertDisplayValues({ bust_cm: 88.9, waist_cm: '' }, 'cm', 'in');
    expect(inches.bust_cm).toBe(35);
    expect(inches.waist_cm).toBe('');
    expect(convertDisplayValues({ bust_cm: 35 }, 'in', 'cm').bust_cm).toBe(88.9);
    expect(toCm(34.5, 'in')).toBe(87.63);
    expect(rangeText({ min: 60, max: 160 })).toBe('60–160 cm (23.6–63.0 in)');
  });

  it('builds a payload of entered numbers only, never inventing missing fields', () => {
    const payload = buildPayload({ bust_cm: '88.5', waist_cm: '', hip_cm: 'x' }, 'in');
    expect(payload).toEqual({ unit: 'in', bust_cm: 88.5 });
    expect(parseEntry('   ')).toEqual({ missing: true });
  });

  it('flattens structured backend errors', () => {
    const err = { response: { data: { field_errors: {
      wrist_cm: [{ code: 'RELATION', message: 'Wrist must be smaller than bicep.' }],
      bust_cm: [{ code: 'OUT_OF_RANGE', message: 'Bust outside range.' }] } } } };
    expect(parseFieldErrors(err)).toEqual({ wrist_cm: 'Wrist must be smaller than bicep.', bust_cm: 'Bust outside range.' });
    expect(parseFieldErrors({ response: { data: { error: 'Boom' } } })).toEqual({ _form: 'Boom' });
    expect(parseFieldErrors({})._form).toBeTruthy();
  });
});

// ── the wizard's measurement step ─────────────────────────────────────────────
function openMeasurementStep({ neckline = 'round-neck', sleeveStyle = 'regular-sleeve' } = {}) {
  const view = render(<MemoryRouter><Upload /></MemoryRouter>);
  fireEvent.click(screen.getByText('No photo — choose the design manually'));
  const set = (testId, value) => fireEvent.change(screen.getByTestId(testId), { target: { value } });
  set('select-garment_type', 'blouse');
  set('select-neckline_type', neckline);
  set('select-sleeve_length', 'short-sleeve');
  set('select-sleeve_style', sleeveStyle);
  fireEvent.click(screen.getByTestId('confirm-btn'));
  const next = screen.getByText('Continue to measurements');
  if (!next.disabled) fireEvent.click(next);
  return view;
}

const input = (key) => document.querySelector(`#meas-${key}`);
const fillAll = (values) => Object.entries(values).forEach(([k, v]) =>
  fireEvent.change(input(k), { target: { value: String(v) } }));
const save = () => fireEvent.click(screen.getByText('Save and continue'));

describe('Measurement form in the Upload wizard', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    measurementsAPI.getAll.mockResolvedValue({ data: { measurements: [] } });
    measurementsAPI.save.mockResolvedValue({ data: { measurement_id: 'm1' } });
  });

  it('starts empty: no invented default measurements', () => {
    openMeasurementStep();
    FIELD_KEYS.forEach((k) => expect(input(k).value).toBe(''));
  });

  it('shows required errors per field and does not call the API', () => {
    openMeasurementStep();
    save();
    expect(screen.getByTestId('error-bust_cm').textContent).toMatch(/required/);
    expect(screen.getByTestId('error-wrist_cm').textContent).toMatch(/required/);
    expect(measurementsAPI.save).not.toHaveBeenCalled();
  });

  it('shows plausible-range and non-positive errors', () => {
    openMeasurementStep();
    fillAll({ ...VALID, bust_cm: 5, waist_cm: -4 });
    save();
    expect(screen.getByTestId('error-bust_cm').textContent).toMatch(/plausible range/);
    expect(screen.getByTestId('error-waist_cm').textContent).toMatch(/greater than 0/);
    expect(screen.queryByTestId('error-hip_cm')).toBeNull();
    expect(measurementsAPI.save).not.toHaveBeenCalled();
  });

  it('clears a field error as the user edits that field', () => {
    openMeasurementStep();
    save();
    expect(screen.getByTestId('error-bust_cm')).toBeTruthy();
    fireEvent.change(input('bust_cm'), { target: { value: '88' } });
    expect(screen.queryByTestId('error-bust_cm')).toBeNull();
  });

  it('saves valid cm values with an explicit unit and entered numbers only', async () => {
    openMeasurementStep();
    fillAll(VALID);
    save();
    await waitFor(() => expect(measurementsAPI.save).toHaveBeenCalledTimes(1));
    const payload = measurementsAPI.save.mock.calls[0][0];
    expect(payload.unit).toBe('cm');
    FIELD_KEYS.forEach((k) => expect(payload[k]).toBe(VALID[k]));
    expect(payload.fabric_type).toBe('woven');
  });

  it('supports inches: toggling converts displayed values and the raw entry is sent with unit "in"', async () => {
    openMeasurementStep();
    fillAll({ bust_cm: 88.9 });
    fireEvent.click(screen.getByTestId('unit-in'));
    expect(input('bust_cm').value).toBe('35');                      // 88.9 cm shown as 35 in
    expect(screen.getByLabelText(/Bust \(in\)/)).toBeTruthy();
    fillAll({ ...Object.fromEntries(Object.entries(VALID).map(([k, v]) => [k, +(v / 2.54).toFixed(2)])) });
    save();
    await waitFor(() => expect(measurementsAPI.save).toHaveBeenCalledTimes(1));
    const payload = measurementsAPI.save.mock.calls[0][0];
    expect(payload.unit).toBe('in');
    expect(payload.bust_cm).toBeCloseTo(88 / 2.54, 1);              // raw inches; server converts once
  });

  it('rejects centimetre-sized numbers typed while inches are selected', () => {
    openMeasurementStep();
    fireEvent.click(screen.getByTestId('unit-in'));
    fillAll(VALID);
    save();
    expect(screen.getByTestId('error-bust_cm').textContent).toMatch(/plausible range/);
    expect(measurementsAPI.save).not.toHaveBeenCalled();
  });

  it('displays structured server-side errors under the right field', async () => {
    measurementsAPI.save.mockRejectedValue({ response: { status: 400, data: {
      error: 'Wrist: must be smaller than bicep', error_code: 'MEASUREMENT_VALIDATION_FAILED',
      field_errors: { wrist_cm: [{ code: 'RELATION', message: 'Wrist (24 cm) must be smaller than bicep (20 cm).' }] } } } });
    openMeasurementStep();
    fillAll(VALID);
    save();
    const msg = await screen.findByTestId('error-wrist_cm');
    expect(msg.textContent).toMatch(/must be smaller than bicep/);
  });

  it('shows a general server error without pretending it is a field error', async () => {
    measurementsAPI.save.mockRejectedValue({ response: { status: 500, data: { error: 'Database down' } } });
    openMeasurementStep();
    fillAll(VALID);
    save();
    await screen.findByText('Database down');
    expect(screen.queryByTestId('error-bust_cm')).toBeNull();
  });

  it('does not let an unsupported design reach the measurement step', () => {
    openMeasurementStep({ neckline: 'halter-neck' });
    expect(screen.getByText('Continue to measurements').disabled).toBe(true);
    expect(document.querySelector('#meas-bust_cm')).toBeNull();
    expect(measurementsAPI.save).not.toHaveBeenCalled();
  });

  it('does not let an out-of-scope combination through (t-shirt with square neck)', () => {
    const view = render(<MemoryRouter><Upload /></MemoryRouter>);
    fireEvent.click(screen.getByText('No photo — choose the design manually'));
    const set = (id, v) => fireEvent.change(screen.getByTestId(id), { target: { value: v } });
    set('select-garment_type', 't-shirt');
    set('select-neckline_type', 'square-neck');
    set('select-sleeve_length', 'short-sleeve');
    set('select-sleeve_style', 'regular-sleeve');
    fireEvent.click(screen.getByTestId('confirm-btn'));
    expect(screen.getByText('Continue to measurements').disabled).toBe(true);
    view.unmount();
  });

  it('only lets the user open steps they have already reached', () => {
    render(<MemoryRouter><Upload /></MemoryRouter>);
    expect(screen.getByText('Measurements', { selector: '.wstep-lbl' }).closest('button').disabled).toBe(true);
    expect(screen.getByText('Upload', { selector: '.wstep-lbl' }).closest('button').disabled).toBe(false);
  });
});
