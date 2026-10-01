// Measurement fields that depend on the confirmed design, positive-number validation (no plausibility ranges),
// exact unit handling, the sleeve-length guide and field-level errors in the React form.
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import React from 'react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import Upload from '../pages/Upload';
import { measurementsAPI } from '../services/api';
import {
  FIELD_KEYS, LABELS, requiredFor, validateMeasurements, displayValue, canonicalCm, parseFieldErrors,
  buildPayload, parseEntry, toCm, MEASUREMENT_FIELDS,
} from '../utils/measurementSchema';
import { sleeveEnd } from '../components/MeasureFigure';

vi.mock('../services/api', () => ({
  imagesAPI: { upload: vi.fn(), analyse: vi.fn(), confirmAttributes: vi.fn() },
  measurementsAPI: { save: vi.fn(), getAll: vi.fn(), update: vi.fn() },
  patternsAPI: { generate: vi.fn() },
  exportAPI: { yardage: vi.fn(), estimates: vi.fn(), pdf: vi.fn(), download: vi.fn() },
  researchAPI: { submitFeedback: vi.fn() },
}));
vi.mock('../components/FabricRecommendation', () => ({ default: () => <div data-testid="fabric-stub" /> }));

const VALID = {
  bust_cm: 88, waist_cm: 70, hip_cm: 94, height_cm: 162, neck_cm: 36, shoulder_cm: 12, across_back_cm: 34,
  back_waist_length_cm: 40, armhole_depth_cm: 20, garment_length_cm: 65, bicep_cm: 28, sleeve_cm: 24, wrist_cm: 16,
};
const BODICE = ['bust_cm', 'waist_cm', 'neck_cm', 'shoulder_cm', 'across_back_cm', 'back_waist_length_cm',
  'armhole_depth_cm', 'garment_length_cm'];
const D = {
  sleevelessCrop: { garment_type: 'crop-top', neckline_type: 'round-neck', sleeve_length: 'sleeveless', sleeve_style: 'none' },
  shortBlouse: { garment_type: 'blouse', neckline_type: 'round-neck', sleeve_length: 'short-sleeve', sleeve_style: 'regular-sleeve' },
  longTshirt: { garment_type: 't-shirt', neckline_type: 'round-neck', sleeve_length: 'long-sleeve', sleeve_style: 'regular-sleeve' },
  longBell: { garment_type: 'blouse', neckline_type: 'v-neck', sleeve_length: 'long-sleeve', sleeve_style: 'bell-sleeve' },
};

describe('measurementSchema utils', () => {
  it('reads the 13 fields from the shared requirement file, with no ranges', () => {
    expect(FIELD_KEYS).toHaveLength(13);
    expect(LABELS.sleeve_cm).toBe('Sleeve length');
    MEASUREMENT_FIELDS.forEach((f) => expect(f).not.toHaveProperty('min'));
  });

  it('requires exactly what the design needs (same rules as the backend)', () => {
    expect(requiredFor(D.sleevelessCrop)).toEqual(BODICE);
    const short = requiredFor(D.shortBlouse);
    expect(short).toEqual(expect.arrayContaining(['hip_cm', 'bicep_cm', 'sleeve_cm']));
    expect(short).not.toContain('wrist_cm');
    expect(requiredFor(D.longTshirt)).toContain('wrist_cm');
    expect(requiredFor(D.longBell)).not.toContain('wrist_cm');
    Object.values(D).forEach((d) => expect(requiredFor(d)).not.toContain('height_cm'));
  });

  it('reports missing, non-numeric, non-finite, zero and negative values; accepts large values and decimals', () => {
    const errors = validateMeasurements(
      { ...VALID, bust_cm: '', waist_cm: 'abc', hip_cm: 0, height_cm: -5, neck_cm: Infinity, shoulder_cm: 'NaN',
        garment_length_cm: 260, sleeve_cm: '24.75' }, FIELD_KEYS);
    expect(errors.bust_cm).toMatch(/required/);
    expect(errors.waist_cm).toMatch(/not a number/);
    expect(errors.hip_cm).toMatch(/greater than 0/);
    expect(errors.height_cm).toMatch(/greater than 0/);
    expect(errors.neck_cm).toMatch(/finite/);
    expect(errors.shoulder_cm).toMatch(/not a number/);
    expect(errors).not.toHaveProperty('garment_length_cm');          // no plausibility range
    expect(errors).not.toHaveProperty('sleeve_cm');                  // decimals are fine
  });

  it('converts exactly and never twice: switching the display unit keeps what was typed', () => {
    expect(toCm(34.5, 'in')).toBeCloseTo(87.63, 10);
    expect(displayValue('88.9', 'cm', 'cm')).toBe('88.9');
    expect(displayValue('88.9', 'cm', 'in')).toBe('35');             // shown, not stored
    expect(displayValue('88.9', 'cm', 'cm')).toBe('88.9');           // back again: unchanged
    expect(displayValue('13.337', 'in', 'cm')).toBe('33.88');
    expect(displayValue('', 'cm', 'in')).toBe('');
    const cm = canonicalCm({ bust_cm: '34.5', waist_cm: '70.25' }, { bust_cm: 'in' });
    expect(cm.bust_cm).toBeCloseTo(87.63, 10);
    expect(cm.waist_cm).toBe(70.25);
  });

  it('builds a payload of entered numbers only, each with the unit it was typed in', () => {
    const payload = buildPayload({ bust_cm: '34.5', waist_cm: '', hip_cm: 'x', neck_cm: '36.2' }, { bust_cm: 'in' }, 'cm');
    expect(payload).toEqual({ unit: 'cm', units: { bust_cm: 'in', neck_cm: 'cm' }, bust_cm: 34.5, neck_cm: 36.2 });
    expect(buildPayload({ bust_cm: 88, wrist_cm: 16 }, {}, 'cm', ['bust_cm'])).toEqual({ unit: 'cm', units: { bust_cm: 'cm' }, bust_cm: 88 });
    expect(parseEntry('   ')).toEqual({ missing: true });
  });

  it('flattens structured backend errors', () => {
    const err = { response: { data: { field_errors: {
      wrist_cm: [{ code: 'NOT_DRAFTABLE', message: 'Sleeve width at the bicep must exceed the wrist width.' }] } } } };
    expect(parseFieldErrors(err)).toEqual({ wrist_cm: 'Sleeve width at the bicep must exceed the wrist width.' });
    expect(parseFieldErrors({ response: { data: { error: 'Boom' } } })).toEqual({ _form: 'Boom' });
    expect(parseFieldErrors({})._form).toBeTruthy();
  });

  it('draws a longer sleeve guide line for a longer sleeve and the same line for equal cm / inch values', () => {
    const short = sleeveEnd(20);
    const long = sleeveEnd(55);
    expect(long[1]).toBeGreaterThan(short[1]);
    expect(sleeveEnd(toCm(24, 'in'))).toEqual(sleeveEnd(60.96));
  });
});

// ── the wizard's measurement step ─────────────────────────────────────────────
function openMeasurementStep(design = D.shortBlouse) {
  const view = render(<MemoryRouter><Upload /></MemoryRouter>);
  fireEvent.change(screen.getByLabelText('Customer name'), { target: { value: 'Test Customer' } });
  fireEvent.click(screen.getByText('Continue to upload'));
  fireEvent.click(screen.getByText('Choose the design manually'));
  const set = (testId, value) => fireEvent.change(screen.getByTestId(testId), { target: { value } });
  set('select-garment_type', design.garment_type);
  set('select-neckline_type', design.neckline_type);
  set('select-sleeve_length', design.sleeve_length);
  set('select-sleeve_style', design.sleeve_style);
  fireEvent.click(screen.getByTestId('confirm-btn'));
  fireEvent.click(screen.getByText('Continue to measurements'));
  return view;
}

const input = (key) => document.querySelector(`#meas-${key}`);
const shown = () => FIELD_KEYS.filter((k) => input(k));
const fillAll = (values) => Object.entries(values).forEach(([k, v]) => {
  if (input(k)) fireEvent.change(input(k), { target: { value: String(v) } });
});
const save = () => fireEvent.click(screen.getByText('Save and continue'));

describe('Measurement form in the Upload wizard', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    measurementsAPI.getAll.mockResolvedValue({ data: { measurements: [] } });
    measurementsAPI.save.mockResolvedValue({ data: { measurement_id: 'm1' } });
  });

  it('shows only the measurements the confirmed design needs', () => {
    openMeasurementStep(D.sleevelessCrop);
    expect(shown()).toEqual(BODICE);                                 // no hip, height, bicep, sleeve, wrist
    expect(screen.queryByTestId('sleeve-guide-line')).toBeNull();     // no sleeve highlight for sleeveless
    expect(document.body.textContent).not.toMatch(/All 13 measurements/);
  });

  it('short sleeve: asks for the sleeve length but not the wrist; long plain sleeve: asks for the wrist', () => {
    const v = openMeasurementStep(D.shortBlouse);
    expect(shown()).toEqual(expect.arrayContaining(['bicep_cm', 'sleeve_cm', 'hip_cm']));
    expect(input('wrist_cm')).toBeNull();
    expect(input('height_cm')).toBeNull();
    expect(screen.getByLabelText(/^Sleeve length/)).toBeTruthy();
    expect(document.body.textContent).not.toMatch(/full arm/i);
    v.unmount();
    openMeasurementStep(D.longTshirt);
    expect(input('wrist_cm')).toBeTruthy();
  });

  it('starts empty: no invented default measurements', () => {
    openMeasurementStep();
    shown().forEach((k) => expect(input(k).value).toBe(''));
  });

  it('shows required errors for the design fields and does not call the API', () => {
    openMeasurementStep();
    save();
    expect(screen.getByTestId('error-bust_cm').textContent).toMatch(/required/);
    expect(screen.getByTestId('error-sleeve_cm').textContent).toMatch(/required/);
    expect(screen.queryByTestId('error-wrist_cm')).toBeNull();
    expect(measurementsAPI.save).not.toHaveBeenCalled();
  });

  it('rejects zero, negative and non-numbers but not unusual sizes', () => {
    openMeasurementStep();
    fillAll({ ...VALID, bust_cm: 0, waist_cm: -4, neck_cm: 'abc', garment_length_cm: 180 });
    save();
    expect(screen.getByTestId('error-bust_cm').textContent).toMatch(/greater than 0/);
    expect(screen.getByTestId('error-waist_cm').textContent).toMatch(/greater than 0/);
    expect(screen.queryByTestId('error-garment_length_cm')).toBeNull();     // no arbitrary range
    expect(measurementsAPI.save).not.toHaveBeenCalled();
  });

  it('clears a field error as the user edits that field', () => {
    openMeasurementStep();
    save();
    expect(screen.getByTestId('error-bust_cm')).toBeTruthy();
    fireEvent.change(input('bust_cm'), { target: { value: '88' } });
    expect(screen.queryByTestId('error-bust_cm')).toBeNull();
  });

  it('saves the design fields exactly as typed (decimals kept), with their units and the design', async () => {
    openMeasurementStep();
    fillAll({ ...VALID, bust_cm: '88.75', sleeve_cm: '24.5' });
    save();
    await waitFor(() => expect(measurementsAPI.save).toHaveBeenCalledTimes(1));
    const payload = measurementsAPI.save.mock.calls[0][0];
    expect(payload.bust_cm).toBe(88.75);
    expect(payload.sleeve_cm).toBe(24.5);
    expect(payload.units.bust_cm).toBe('cm');
    expect(payload.design).toEqual(D.shortBlouse);
    expect(Object.keys(payload).filter((k) => k.endsWith('_cm')).sort()).toEqual(requiredFor(D.shortBlouse).slice().sort());
    expect(payload.client_name).toBe('Test Customer');
    expect(payload).not.toHaveProperty('email');                    // no contact entered -> none invented
  });

  it('switching units changes only the display: no double conversion, values saved with the unit they were typed in', async () => {
    openMeasurementStep();
    fillAll(VALID);
    fireEvent.change(input('bust_cm'), { target: { value: '88.9' } });
    fireEvent.click(screen.getByTestId('unit-in'));
    expect(input('bust_cm').value).toBe('35');                      // 88.9 cm shown as 35 in
    expect(screen.getByLabelText(/Bust \(in\)/)).toBeTruthy();
    fireEvent.change(input('neck_cm'), { target: { value: '14.25' } });   // typed in inches
    fireEvent.click(screen.getByTestId('unit-cm'));
    fireEvent.click(screen.getByTestId('unit-in'));
    fireEvent.click(screen.getByTestId('unit-cm'));
    expect(input('bust_cm').value).toBe('88.9');                    // still exactly what was typed
    save();
    await waitFor(() => expect(measurementsAPI.save).toHaveBeenCalledTimes(1));
    const payload = measurementsAPI.save.mock.calls[0][0];
    expect(payload.bust_cm).toBe(88.9);
    expect(payload.units.bust_cm).toBe('cm');
    expect(payload.neck_cm).toBe(14.25);
    expect(payload.units.neck_cm).toBe('in');                       // the server converts it once, exactly
  });

  it('shows one guide instruction next to the active field and moves the sleeve line with the entered length', () => {
    openMeasurementStep();
    fireEvent.focus(input('sleeve_cm'));
    expect(screen.getByTestId('guide-sleeve_cm').textContent).toBe('උරහිසේ අග සිට ඔබට අත අවසන් වෙන්න අවශ්‍ය ස්ථානය දක්වා මනින්න.');
    expect(screen.queryByTestId('guide-bust_cm')).toBeNull();
    fireEvent.change(input('sleeve_cm'), { target: { value: '20' } });
    const shortEnd = screen.getByTestId('sleeve-guide-line').getAttribute('data-end');
    fireEvent.change(input('sleeve_cm'), { target: { value: '55' } });
    const longEnd = screen.getByTestId('sleeve-guide-line').getAttribute('data-end');
    expect(Number(longEnd.split(',')[1])).toBeGreaterThan(Number(shortEnd.split(',')[1]));
    fireEvent.change(input('sleeve_cm'), { target: { value: '60.96' } });
    const cmEnd = screen.getByTestId('sleeve-guide-line').getAttribute('data-end');
    fireEvent.click(screen.getByTestId('unit-in'));
    fireEvent.change(input('sleeve_cm'), { target: { value: '24' } });
    expect(screen.getByTestId('sleeve-guide-line').getAttribute('data-end')).toBe(cmEnd);   // 24 in == 60.96 cm
    expect(screen.queryByText(/Open the 3D measuring guide/)).toBeNull();
    expect(screen.getByRole('complementary', { name: 'Measurement guide' })).toBeTruthy();
  });

  it('displays structured server-side errors under the right field', async () => {
    measurementsAPI.save.mockRejectedValue({ response: { status: 400, data: {
      error: 'Bicep: required', error_code: 'MEASUREMENT_VALIDATION_FAILED',
      field_errors: { bicep_cm: [{ code: 'REQUIRED', message: 'Bicep is required for this design.' }] } } } });
    openMeasurementStep();
    fillAll(VALID);
    save();
    const msg = await screen.findByTestId('error-bicep_cm');
    expect(msg.textContent).toMatch(/required for this design/);
  });

  it('shows a general server error without pretending it is a field error', async () => {
    measurementsAPI.save.mockRejectedValue({ response: { status: 500, data: { error: 'Database down' } } });
    openMeasurementStep();
    fillAll(VALID);
    save();
    await screen.findByText('Database down');
    expect(screen.queryByTestId('error-bust_cm')).toBeNull();
  });

  it('an unsupported or unconfirmed design shows no measurement fields and saves nothing', () => {
    openMeasurementStep({ ...D.shortBlouse, neckline_type: 'halter-neck' });
    expect(input('bust_cm')).toBeNull();
    expect(screen.getByTestId('step-empty').textContent).toMatch(/Confirm the design first/);
    expect(screen.getByText('Save and continue').disabled).toBe(true);
    expect(measurementsAPI.save).not.toHaveBeenCalled();
  });
});
