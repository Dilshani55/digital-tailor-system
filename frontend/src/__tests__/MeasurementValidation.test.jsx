// Measurement fields that depend on the confirmed design, positive-number validation (no plausibility ranges),
// exact unit handling, the sleeve-length guide and field-level errors in the React form.
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import Upload from '../pages/Upload';
import { measurementsAPI } from '../services/api';
import {
  FIELD_KEYS, LABELS, requiredFor, validateMeasurements, displayValue, canonicalCm, parseFieldErrors,
  buildPayload, parseEntry, toCm, MEASUREMENT_FIELDS, storedEntries, DESIGN_KEYS, LEGACY_KEYS, calculatedValues, softWarnings,
} from '../utils/measurementSchema';
import { GUIDES, MISTAKES } from '../utils/measurementGuides';
import { sleeveEnd } from '../components/MeasureFigure';

vi.mock('../services/api', () => ({
  imagesAPI: { upload: vi.fn(), analyse: vi.fn(), confirmAttributes: vi.fn() },
  measurementsAPI: { save: vi.fn(), getAll: vi.fn(), update: vi.fn() },
  patternsAPI: { generate: vi.fn() },
  exportAPI: { yardage: vi.fn(), estimates: vi.fn(), pdf: vi.fn(), download: vi.fn() },
  researchAPI: { submitFeedback: vi.fn() },
}));
vi.mock('../components/FabricRecommendation', () => ({ default: () => <div data-testid="fabric-stub" /> }));

// what a short-sleeved woven blouse needs (the optional design values are left empty = calculated)
const VALID = {
  bust_cm: 88, waist_cm: 70, hip_cm: 94, shoulder_width_cm: 37, back_waist_length_cm: 40, shoulder_to_bust_cm: 25,
  waist_to_hip_cm: 20, garment_length_cm: 65, bicep_cm: 28, sleeve_cm: 24, sleeve_end_cm: 27,
};
const BODICE = ['bust_cm', 'waist_cm', 'shoulder_width_cm', 'back_waist_length_cm', 'garment_length_cm'];
const BELOW_WAIST = ['hip_cm', 'waist_to_hip_cm'];
const OPTIONAL = ['neck_width_cm', 'front_neck_depth_cm', 'back_neck_depth_cm', 'armhole_depth_cm'];
const D = {
  sleevelessBlouse: { garment_type: 'blouse', neckline_type: 'round-neck', sleeve_length: 'sleeveless', sleeve_style: 'none' },
  shortBlouse: { garment_type: 'blouse', neckline_type: 'round-neck', sleeve_length: 'short-sleeve', sleeve_style: 'regular-sleeve' },
  longTshirt: { garment_type: 't-shirt', neckline_type: 'round-neck', sleeve_length: 'long-sleeve', sleeve_style: 'regular-sleeve' },
  longPuff: { garment_type: 'blouse', neckline_type: 'v-neck', sleeve_length: 'long-sleeve', sleeve_style: 'puff-sleeve' },
};

describe('measurementSchema utils', () => {
  it('reads the 16 fields from the shared requirement file: plain names, a guide and a common mistake each, no rejecting ranges', () => {
    expect(FIELD_KEYS).toHaveLength(16);
    expect(LABELS.sleeve_cm).toBe('Sleeve length');
    expect(LABELS.bust_cm).toBe('Bust around');
    expect(LABELS.bicep_cm).toBe('Upper arm around');
    expect(LABELS.sleeve_end_cm).toBe('Sleeve end around');
    expect(LABELS.back_waist_length_cm).toBe('Back neck to waist');
    MEASUREMENT_FIELDS.forEach((f) => {
      expect(f).not.toHaveProperty('min');
      expect(GUIDES[f.key].length, f.key).toBeGreaterThan(40);
      expect(MISTAKES[f.key].length, f.key).toBeGreaterThan(15);
      expect(['front', 'back']).toContain(f.view);
      expect(f.label).not.toMatch(/circumference|girth|thoracic|posterior|distal/i);
    });
    expect(DESIGN_KEYS).toEqual(['bust_point_distance_cm', ...OPTIONAL]);
    expect(LEGACY_KEYS).toEqual(['neck_cm', 'height_cm', 'shoulder_cm', 'across_back_cm', 'wrist_cm']);
    LEGACY_KEYS.forEach((k) => expect(FIELD_KEYS).not.toContain(k));  // never asked for any more
  });

  it('requires exactly what the design needs (same rules as the backend)', () => {
    expect(new Set(requiredFor(D.sleevelessBlouse))).toEqual(new Set([...BODICE, ...BELOW_WAIST, 'shoulder_to_bust_cm']));   // no arm measurements
    const short = requiredFor(D.shortBlouse);
    expect(short).toEqual(expect.arrayContaining(['hip_cm', 'bicep_cm', 'sleeve_cm', 'sleeve_end_cm', 'shoulder_to_bust_cm']));
    expect(requiredFor(D.longTshirt)).toContain('sleeve_end_cm');
    expect(requiredFor(D.longTshirt)).not.toContain('shoulder_to_bust_cm');     // a knit T-shirt has no bust dart
    expect(requiredFor(D.longPuff)).toContain('sleeve_end_cm');                 // every sleeve narrows to the arm at its end
    Object.values(D).forEach((d) => [...DESIGN_KEYS, ...LEGACY_KEYS].forEach((k) => expect(requiredFor(d)).not.toContain(k)));
  });

  it('reports missing, non-numeric, non-finite, zero and negative values; accepts large values and decimals', () => {
    const errors = validateMeasurements(
      { ...VALID, bust_cm: '', waist_cm: 'abc', hip_cm: 0, shoulder_width_cm: -5, back_waist_length_cm: Infinity, bicep_cm: 'NaN',
        garment_length_cm: 260, sleeve_cm: '24.75' }, FIELD_KEYS);
    expect(errors.bust_cm).toMatch(/required/);
    expect(errors.waist_cm).toMatch(/not a number/);
    expect(errors.hip_cm).toMatch(/greater than 0/);
    expect(errors.shoulder_width_cm).toMatch(/greater than 0/);
    expect(errors.back_waist_length_cm).toMatch(/finite/);
    expect(errors.bicep_cm).toMatch(/not a number/);
    expect(errors).not.toHaveProperty('garment_length_cm');          // an unusual value is never an error
    expect(errors).not.toHaveProperty('sleeve_cm');                  // decimals are fine
  });

  it('warns about values that may be a typing or unit mistake, without rejecting them', () => {
    expect(softWarnings({ bust_cm: 88, waist_cm: 70 })).toEqual([]);
    const w = softWarnings({ bust_cm: 34 });                         // inches typed while cm was selected
    expect(w).toHaveLength(1);
    expect(w[0].field).toBe('bust_cm');
    expect(w[0].message).toMatch(/unit \(cm \/ inch\)/);
    expect(validateMeasurements({ bust_cm: 34 }, [])).toEqual({});     // still accepted
  });

  it('shows what the drafting method calculates when a design value is left empty', () => {
    const inch = 2.54;
    const c = calculatedValues({ bust_cm: 34 * inch });              // the drafting source's sample figure
    expect(c.neck_width_cm / 2 / inch).toBeCloseTo(34 / 12, 10);     // 1/12 bust each side (2 3/4 in in the source)
    expect(c.front_neck_depth_cm / inch).toBeCloseTo(34 / 12 + 0.25, 10);
    expect(c.back_neck_depth_cm).toBeCloseTo(inch, 10);
    expect(c.armhole_depth_cm / inch).toBeCloseTo(7.5, 10);          // 1/4 bust - 1 in
    expect(calculatedValues({ bust_cm: 29 * inch }).armhole_depth_cm / inch).toBeCloseTo(29 / 4 - 0.5, 10);   // small bust
    expect(c.bust_point_distance_cm / inch).toBeCloseTo(6.8, 10);
    expect(calculatedValues({})).toEqual({});                        // nothing without the bust
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
    const payload = buildPayload({ bust_cm: '34.5', waist_cm: '', hip_cm: 'x', bicep_cm: '36.2' }, { bust_cm: 'in' }, 'cm');
    expect(payload).toEqual({ unit: 'cm', units: { bust_cm: 'in', bicep_cm: 'cm' }, bust_cm: 34.5, bicep_cm: 36.2 });
    expect(buildPayload({ bust_cm: 88, sleeve_end_cm: 16 }, {}, 'cm', ['bust_cm'])).toEqual({ unit: 'cm', units: { bust_cm: 'cm' }, bust_cm: 88 });
    expect(parseEntry('   ')).toEqual({ missing: true });
  });

  it('reads only plain decimals: a comma is a decimal point, anything else is reported and never guessed', () => {
    expect(parseEntry('88.5')).toEqual({ value: 88.5 });
    expect(parseEntry(' 88.50 ')).toEqual({ value: 88.5 });
    expect(parseEntry('12.')).toEqual({ value: 12 });
    expect(parseEntry('.5')).toEqual({ value: 0.5 });
    expect(parseEntry('90,5')).toEqual({ value: 90.5 });            // phone keypads in some languages type a comma
    expect(parseEntry('034')).toEqual({ value: 34 });
    expect(parseEntry(88.5)).toEqual({ value: 88.5 });
    for (const bad of ['1e2', '1,234.5', '88cm', '8 8', '+5', '0x10', '.', ',', '1.2.3']) {
      expect(parseEntry(bad).error, bad).toMatch(/not a number/);
    }
    expect(parseEntry('-5').error).toMatch(/greater than 0/);
    expect(parseEntry('0').error).toMatch(/greater than 0/);
    expect(parseEntry('0.0').error).toMatch(/greater than 0/);
  });

  it('opens a saved profile with every value as it was entered, in the unit it was entered in', () => {
    const p = { bust_cm: 84.58200000000001, waist_cm: 70, hip_cm: null, bicep_cm: 36.5, armhole_cm: 20, neck_cm: 36, wrist_cm: 16,
      original_values: { bust_cm: { value: 33.3, unit: 'in' }, waist_cm: { value: 70, unit: 'cm' },
        bicep_cm: { value: 99, unit: 'in' } } };                    // stale original (does not match the stored cm)
    const { values, units } = storedEntries(p);
    expect(values.bust_cm).toBe('33.3');
    expect(units).toEqual({ bust_cm: 'in' });
    expect(values.waist_cm).toBe('70');
    expect(values.bicep_cm).toBe('36.5');                            // falls back to the stored centimetres
    expect(values.hip_cm).toBe('');
    expect(values.armhole_depth_cm).toBe('20');                      // legacy field name
    expect(values.shoulder_width_cm).toBe('');                       // an old profile does not have it: asked for, not guessed
    expect(values).not.toHaveProperty('neck_cm');                    // no longer part of the form
    expect(canonicalCm(values, units).bust_cm).toBeCloseTo(84.582, 10);
    expect(storedEntries(null).values.bust_cm).toBe('');
  });

  it('flattens structured backend errors', () => {
    const err = { response: { data: { field_errors: {
      sleeve_end_cm: [{ code: 'NOT_DRAFTABLE', message: 'Sleeve end around is larger than the sleeve.' }] } } } };
    expect(parseFieldErrors(err)).toEqual({ sleeve_end_cm: 'Sleeve end around is larger than the sleeve.' });
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
    openMeasurementStep(D.sleevelessBlouse);
    expect(screen.queryByTestId('design-selector')).toBeNull();      // the design really was confirmed
    // what the design needs, plus its optional design values (and the bust-point distance: it has a bust dart)
    expect(new Set(shown())).toEqual(new Set([...BODICE, ...BELOW_WAIST, 'shoulder_to_bust_cm', 'bust_point_distance_cm', ...OPTIONAL]));
    expect(screen.queryByTestId('sleeve-guide-line')).toBeNull();     // no sleeve highlight for sleeveless
    ['body', 'neck'].forEach((g) => expect(screen.getByTestId(`meas-group-${g}`)).toBeTruthy());
    expect(screen.queryByTestId('meas-group-arm')).toBeNull();        // no arm group for a sleeveless design
    expect(screen.getByLabelText(/^Neckline width/).closest('.meas-field').textContent).toMatch(/optional/);
    expect(screen.getByLabelText(/^Bust around/).closest('.meas-field').textContent).not.toMatch(/optional/);
    expect(document.body.textContent).not.toMatch(/All 13 measurements/);
  });

  it('a sleeve asks for its length, the upper arm and the arm at the sleeve end; a knit T-shirt has no bust-point fields', () => {
    const v = openMeasurementStep(D.shortBlouse);
    expect(shown()).toEqual(expect.arrayContaining(['bicep_cm', 'sleeve_cm', 'sleeve_end_cm', 'hip_cm', 'shoulder_to_bust_cm']));
    ['wrist_cm', 'height_cm', 'neck_cm', 'shoulder_cm', 'across_back_cm'].forEach((k) => expect(input(k)).toBeNull());
    expect(screen.getByLabelText(/^Sleeve length/)).toBeTruthy();
    expect(screen.getByLabelText(/^Upper arm around/)).toBeTruthy();
    expect(document.body.textContent).not.toMatch(/full arm/i);
    v.unmount();
    openMeasurementStep(D.longTshirt);
    expect(input('sleeve_end_cm')).toBeTruthy();
    expect(input('shoulder_to_bust_cm')).toBeNull();
    expect(input('bust_point_distance_cm')).toBeNull();
  });

  it('shows the calculated value of an empty design field and hides it once a value is typed', () => {
    openMeasurementStep();
    expect(screen.queryByTestId('calculated-armhole_depth_cm')).toBeNull();          // nothing to calculate from yet
    fireEvent.change(input('bust_cm'), { target: { value: '86.36' } });              // 34 in
    expect(screen.getByTestId('calculated-armhole_depth_cm').textContent).toMatch(/Calculated value: 19\.1 cm/);   // 7.5 in
    expect(screen.getByTestId('calculated-neck_width_cm').textContent).toMatch(/14\.4 cm/);
    fireEvent.click(screen.getByTestId('unit-in'));
    expect(screen.getByTestId('calculated-armhole_depth_cm').textContent).toMatch(/7\.5 in/);
    fireEvent.click(screen.getByTestId('unit-cm'));
    fireEvent.change(input('armhole_depth_cm'), { target: { value: '21' } });
    expect(screen.queryByTestId('calculated-armhole_depth_cm')).toBeNull();
  });

  it('warns about an unusual value beside its field but still saves it', async () => {
    openMeasurementStep();
    fillAll({ ...VALID, bust_cm: 250 });
    expect(screen.getByTestId('warning-bust_cm').textContent).toMatch(/Please check/);
    save();
    await waitFor(() => expect(measurementsAPI.save).toHaveBeenCalledTimes(1));
    expect(measurementsAPI.save.mock.calls[0][0].bust_cm).toBe(250);                 // saved exactly as entered
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
    expect(screen.getByTestId('error-sleeve_end_cm').textContent).toMatch(/required/);
    OPTIONAL.forEach((k) => expect(screen.queryByTestId(`error-${k}`)).toBeNull());   // design values are optional
    expect(measurementsAPI.save).not.toHaveBeenCalled();
  });

  it('rejects zero, negative and non-numbers but not unusual sizes', () => {
    openMeasurementStep();
    fillAll({ ...VALID, bust_cm: 0, waist_cm: -4, bicep_cm: 'abc', garment_length_cm: 180 });
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
    expect(screen.getByLabelText(/Bust around \(in\)/)).toBeTruthy();
    fireEvent.change(input('shoulder_width_cm'), { target: { value: '14.25' } });   // typed in inches
    fireEvent.click(screen.getByTestId('unit-cm'));
    fireEvent.click(screen.getByTestId('unit-in'));
    fireEvent.click(screen.getByTestId('unit-cm'));
    expect(input('bust_cm').value).toBe('88.9');                    // still exactly what was typed
    save();
    await waitFor(() => expect(measurementsAPI.save).toHaveBeenCalledTimes(1));
    const payload = measurementsAPI.save.mock.calls[0][0];
    expect(payload.bust_cm).toBe(88.9);
    expect(payload.units.bust_cm).toBe('cm');
    expect(payload.shoulder_width_cm).toBe(14.25);
    expect(payload.units.shoulder_width_cm).toBe('in');             // the server converts it once, exactly
  });

  it('shows one guide instruction next to the active field and moves the sleeve line with the entered length', () => {
    openMeasurementStep();
    fireEvent.focus(input('sleeve_cm'));
    const guide = screen.getByTestId('guide-sleeve_cm').textContent;
    expect(guide).toMatch(/How to measure/);
    expect(guide).toMatch(/from the shoulder tip down the outside of the arm to where you want the sleeve to end/);
    expect(guide).toMatch(/Common mistake: Start at the shoulder tip, not at the neck/);
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

  it('the body guide has a front and a back view and highlights the measurement being entered', () => {
    openMeasurementStep();
    expect(screen.getByTestId('measure-view-front')).toBeTruthy();
    expect(screen.getByTestId('measure-view-back')).toBeTruthy();
    fireEvent.focus(input('bust_cm'));
    expect(screen.getByTestId('measure-figure').getAttribute('data-active-view')).toBe('front');
    expect(screen.getByTestId('guide-line-bust_cm').getAttribute('data-active')).toBe('yes');
    expect(screen.getByTestId('guide-line-waist_cm').getAttribute('data-active')).toBe('no');     // the others fade
    expect(screen.getByTestId('guide-point-bust_cm-0')).toBeTruthy();                               // start and end points
    expect(screen.getByTestId('guide-point-bust_cm-1')).toBeTruthy();
    fireEvent.focus(input('back_waist_length_cm'));
    expect(screen.getByTestId('measure-figure').getAttribute('data-active-view')).toBe('back');
    expect(screen.getByTestId('measure-view-back').getAttribute('data-current')).toBe('yes');
    expect(screen.getByTestId('measure-view-front').getAttribute('data-current')).toBe('no');
    expect(screen.getByTestId('guide-line-back_waist_length_cm').getAttribute('data-active')).toBe('yes');
    fireEvent.click(screen.getByRole('button', { name: 'How to measure Shoulder to shoulder' }));   // the info button
    expect(screen.getByTestId('guide-shoulder_width_cm').textContent).toMatch(/tip of one shoulder to the tip of the other/);
  });

  it('displays structured server-side errors under the right field', async () => {
    measurementsAPI.save.mockRejectedValue({ response: { status: 400, data: {
      error: 'Upper arm around: required', error_code: 'MEASUREMENT_VALIDATION_FAILED',
      field_errors: { bicep_cm: [{ code: 'REQUIRED', message: 'Upper arm around is required for this design.' }] } } } });
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

  it('with no confirmed design the step shows a design selector and every measurement; saving explains, nothing is sent', () => {
    openMeasurementStep({ ...D.shortBlouse, neckline_type: 'halter-neck' });   // not selectable -> never confirmed
    expect(screen.getByTestId('design-selector')).toBeTruthy();
    expect(shown()).toEqual(FIELD_KEYS);                              // the same fields as the Measurements page: a new customer can be measured completely
    expect(screen.getByTestId('base-fields-note').textContent).toMatch(/All measurements can be entered now\. The first 5/);
    expect(screen.queryByTestId('meas-need-bust_cm')).toBeNull();     // needed for every design
    expect(screen.getByTestId('meas-need-hip_cm').textContent).toMatch(/needed for some designs/);
    expect(screen.getByTestId('meas-need-sleeve_cm').textContent).toMatch(/needed for some designs/);
    expect(screen.getByTestId('meas-need-neck_width_cm').textContent).toMatch(/optional/);
    expect(document.querySelector('#saved-client-meas')).toBeTruthy();
    expect(screen.getByTestId('meas-source-note').textContent).toMatch(/For a new customer, type them here/);
    expect(document.querySelector('.wizard-body a[target="_blank"]')).toBeNull();     // nothing sends the user to another tab
    fireEvent.change(input('bust_cm'), { target: { value: '88.5' } });
    expect(screen.getByText('Save and continue').disabled).toBe(false);       // navigation / saving is never a dead button
    save();
    expect(screen.getByRole('alert').textContent).toMatch(/confirm the design first/i);
    expect(measurementsAPI.save).not.toHaveBeenCalled();
    expect(input('bust_cm').value).toBe('88.5');                      // the typed value is kept
  });

  it('confirming the design inside the measurement step adds the fields it needs and keeps typed values', () => {
    render(<MemoryRouter><Upload /></MemoryRouter>);
    fireEvent.change(screen.getByLabelText('Customer name'), { target: { value: 'Test Customer' } });
    fireEvent.click(screen.getByRole('button', { name: /^Step 4: Measurements/ }));
    fireEvent.change(input('bust_cm'), { target: { value: '34.5' } });
    fireEvent.change(input('sleeve_cm'), { target: { value: '23' } });         // a sleeve can be measured before the design is known
    expect(input('shoulder_to_bust_cm')).toBeTruthy();
    Object.entries(D.longTshirt).forEach(([k, v]) => fireEvent.change(screen.getByTestId(`select-${k}`), { target: { value: v } }));
    fireEvent.click(screen.getByTestId('confirm-btn'));
    expect(screen.queryByTestId('design-selector')).toBeNull();
    expect(shown()).toEqual(expect.arrayContaining(['hip_cm', 'waist_to_hip_cm', 'bicep_cm', 'sleeve_cm', 'sleeve_end_cm']));
    expect(input('shoulder_to_bust_cm')).toBeNull();                  // a T-shirt has no bust dart: the field goes away
    expect(screen.queryByTestId('meas-need-sleeve_cm')).toBeNull();   // now required by the confirmed design
    expect(input('bust_cm').value).toBe('34.5');
    expect(input('sleeve_cm').value).toBe('23');
  });

  it('a saved customer chosen in the step has their measurements filled in; a change made here updates that profile', async () => {
    const saved = { measurement_id: 'm7', client_name: 'Amara Silva', fabric_type: 'woven', fit_preference: 'standard', ...VALID,
      shoulder_width_cm: 14.25 * 2.54, original_values: { shoulder_width_cm: { value: 14.25, unit: 'in' } } };
    measurementsAPI.getAll.mockResolvedValue({ data: { measurements: [saved] } });
    measurementsAPI.update.mockResolvedValue({ data: { measurement_id: 'm7', warnings: [] } });
    openMeasurementStep();
    await waitFor(() => expect(document.querySelector('#saved-client-meas option[value="m7"]')).toBeTruthy());
    shown().forEach((k) => expect(input(k).value).toBe(''));           // nothing until a customer is chosen
    fireEvent.change(document.querySelector('#saved-client-meas'), { target: { value: 'm7' } });
    expect(screen.getByTestId('meas-source-note').textContent).toMatch(/saved for this customer/);
    Object.entries(VALID).filter(([k]) => k !== 'shoulder_width_cm').forEach(([k, v]) => expect(input(k).value).toBe(String(v)));
    fireEvent.click(screen.getByTestId('unit-in'));
    expect(input('shoulder_width_cm').value).toBe('14.25');           // shown as it was typed
    fireEvent.click(screen.getByTestId('unit-cm'));
    expect(input('armhole_depth_cm').value).toBe('');                 // an empty design value stays empty (calculated)
    fireEvent.change(input('bust_cm'), { target: { value: '91.5' } });
    save();
    await waitFor(() => expect(measurementsAPI.update).toHaveBeenCalledTimes(1));
    const [id, payload] = measurementsAPI.update.mock.calls[0];
    expect(id).toBe('m7');                                            // the same profile, no second one
    expect(payload).toMatchObject({ client_name: 'Amara Silva', bust_cm: 91.5, waist_cm: 70, shoulder_width_cm: 14.25, design: D.shortBlouse });
    expect(payload.units.shoulder_width_cm).toBe('in');
    expect(measurementsAPI.save).not.toHaveBeenCalled();
    // back to "new customer": the form is empty again, the saved customer's numbers are not carried over
    fireEvent.click(screen.getByRole('button', { name: /^Step 4: Measurements/ }));
    fireEvent.change(document.querySelector('#saved-client-meas'), { target: { value: '' } });
    shown().forEach((k) => expect(input(k).value).toBe(''));
  });

  it('uses text inputs so nothing typed is dropped, and reports a mistyped value beside its field', async () => {
    openMeasurementStep();
    expect(document.querySelectorAll('input[type="number"]').length).toBe(0);
    fillAll(VALID);
    fireEvent.change(input('bust_cm'), { target: { value: '1e2' } });
    expect(input('bust_cm').value).toBe('1e2');
    save();
    expect((await screen.findByTestId('error-bust_cm')).textContent).toMatch(/not a number/);
    expect(input('waist_cm').value).toBe('70');                       // other inputs preserved
    expect(measurementsAPI.save).not.toHaveBeenCalled();
    fireEvent.change(input('bust_cm'), { target: { value: '88,5' } });
    save();
    await waitFor(() => expect(measurementsAPI.save).toHaveBeenCalled());
    expect(measurementsAPI.save.mock.calls[0][0].bust_cm).toBe(88.5);
  });
});
