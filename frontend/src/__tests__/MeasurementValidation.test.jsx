// Measurements: which ones a design needs, positive-number validation (no plausibility ranges), exact unit handling.
// They are ENTERED on the Measurements page (form, guide, field errors); the pattern wizard only SHOWS the chosen
// customer's saved measurements and checks them against the confirmed design.
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import Upload from '../pages/Upload';
import Measurements from '../pages/Measurements';
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
  longBell: { garment_type: 'blouse', neckline_type: 'v-neck', sleeve_length: 'long-sleeve', sleeve_style: 'bell-sleeve' },
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
    expect(requiredFor(D.longBell)).not.toContain('sleeve_end_cm');             // a bell sleeve flares instead
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

// ── the wizard's measurement step: shows the customer's saved measurements, nothing is typed there ──────────────
const PROFILE = { measurement_id: 'm1', client_name: 'Test Customer', fabric_type: 'woven', fit_preference: 'standard',
  created_at: '2026-10-01 09:00:00', ...VALID };

async function openMeasurementStep(design = D.shortBlouse, profiles = [PROFILE]) {
  measurementsAPI.getAll.mockResolvedValue({ data: { measurements: profiles } });
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
  await act(async () => {});                                          // the saved profiles have arrived
  return view;
}
const chooseCustomer = async (id = 'm1') => {
  await waitFor(() => expect(document.querySelector(`#saved-client-meas option[value="${id}"]`)).toBeTruthy());
  fireEvent.change(document.querySelector('#saved-client-meas'), { target: { value: id } });
};
const value = (key) => screen.queryByTestId(`meas-value-${key}`);
const shown = () => FIELD_KEYS.filter((k) => value(k));
const useThem = () => fireEvent.click(screen.getByText('Use these measurements'));

describe('Measurement step in the pattern wizard (read-only)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    measurementsAPI.update.mockResolvedValue({ data: { measurement_id: 'm1', warnings: [] } });
  });

  it('has no measurement inputs: a new customer is sent to the Measurements page, with the name already typed', async () => {
    await openMeasurementStep(D.shortBlouse, []);
    expect(document.querySelectorAll('.wizard-body input[type="text"], .wizard-body input[inputmode="decimal"]').length).toBe(0);
    FIELD_KEYS.forEach((k) => expect(document.querySelector(`#meas-${k}`)).toBeNull());
    expect(screen.getByTestId('meas-none').textContent).toMatch(/No measurements yet/);      // nothing invented
    const add = screen.getByTestId('add-measurements');
    expect(add.getAttribute('href')).toBe('/measurements?new=1&from=pattern&name=Test%20Customer');
    expect(add.getAttribute('target')).toBe('_blank');                 // the pattern in progress is kept
    expect(screen.queryByTestId('edit-measurements')).toBeNull();      // nothing to edit yet
    useThem();
    expect(screen.getByRole('alert').textContent).toMatch(/Choose a saved customer, or add the customer's measurements/);
    expect(measurementsAPI.update).not.toHaveBeenCalled();
    expect(measurementsAPI.save).not.toHaveBeenCalled();
  });

  it('shows the chosen customer\'s saved values for exactly what the design uses, and an Edit link to that profile', async () => {
    await openMeasurementStep(D.sleevelessBlouse);
    await chooseCustomer();
    expect(new Set(shown())).toEqual(new Set([...BODICE, ...BELOW_WAIST, 'shoulder_to_bust_cm', 'bust_point_distance_cm', ...OPTIONAL]));
    ['body', 'neck'].forEach((g) => expect(screen.getByTestId(`meas-group-${g}`)).toBeTruthy());
    expect(screen.queryByTestId('meas-group-arm')).toBeNull();        // a sleeveless design uses no arm measurement
    expect(value('bust_cm').textContent).toBe('Bust around88 cm');
    expect(value('bust_cm').getAttribute('data-state')).toBe('saved');
    expect(value('armhole_depth_cm').textContent).toMatch(/calculated 19\.5 cm/);    // empty design value: the method's value
    expect(value('armhole_depth_cm').getAttribute('data-state')).toBe('empty');
    expect(screen.queryByTestId('meas-missing')).toBeNull();
    const edit = screen.getByTestId('edit-measurements');
    expect(edit.getAttribute('href')).toBe('/measurements?profile=m1&from=pattern');
    expect(edit.getAttribute('target')).toBe('_blank');
    expect(screen.getByTestId('add-measurements').getAttribute('href')).toBe('/measurements?new=1&from=pattern');
    ['wrist_cm', 'height_cm', 'neck_cm'].forEach((k) => expect(value(k)).toBeNull());
  });

  it('a sleeve shows its length, the upper arm and the arm at the sleeve end; a knit T-shirt has no bust-point values', async () => {
    const v = await openMeasurementStep(D.shortBlouse);
    await chooseCustomer();
    expect(shown()).toEqual(expect.arrayContaining(['bicep_cm', 'sleeve_cm', 'sleeve_end_cm', 'hip_cm', 'shoulder_to_bust_cm']));
    expect(value('sleeve_cm').textContent).toBe('Sleeve length24 cm');
    v.unmount();
    await openMeasurementStep(D.longTshirt);
    await chooseCustomer();
    expect(value('sleeve_end_cm')).toBeTruthy();
    expect(value('shoulder_to_bust_cm')).toBeNull();
    expect(value('bust_point_distance_cm')).toBeNull();
  });

  it('the unit switch changes only how the values are shown; a value typed in inches is shown as it was typed', async () => {
    const inches = { ...PROFILE, shoulder_width_cm: 14.25 * 2.54, original_values: { shoulder_width_cm: { value: 14.25, unit: 'in' } } };
    await openMeasurementStep(D.shortBlouse, [inches]);
    await chooseCustomer();
    expect(value('bust_cm').textContent).toMatch(/88 cm/);
    expect(value('shoulder_width_cm').textContent).toMatch(/36\.2 cm/);
    fireEvent.click(screen.getByTestId('unit-in'));
    expect(value('bust_cm').textContent).toMatch(/34\.65 in/);
    expect(value('shoulder_width_cm').textContent).toMatch(/14\.25 in/);             // exactly what was typed
    expect(value('armhole_depth_cm').textContent).toMatch(/calculated 7\.66 in/);
    fireEvent.click(screen.getByTestId('unit-cm'));
    expect(value('bust_cm').textContent).toMatch(/88 cm/);
  });

  it('names what the design still needs, estimates nothing, and does not continue until it is added', async () => {
    const noSleeve = { ...PROFILE, bicep_cm: null, sleeve_cm: null, sleeve_end_cm: null };
    await openMeasurementStep(D.shortBlouse, [noSleeve]);
    await chooseCustomer();
    expect(screen.getByTestId('meas-missing').textContent).toMatch(/This design also needs: Upper arm around, Sleeve length, Sleeve end around/);
    ['bicep_cm', 'sleeve_cm', 'sleeve_end_cm'].forEach((k) => {
      expect(value(k).getAttribute('data-state')).toBe('missing');
      expect(value(k).textContent).toMatch(/Missing$/);                // no estimated value
    });
    useThem();
    expect(screen.getByRole('heading', { name: 'Body measurements' })).toBeTruthy();   // still on this step
    expect(measurementsAPI.update).not.toHaveBeenCalled();
    // the same profile is enough for a sleeveless design
  });

  it('continuing links the saved profile to the design: values unchanged, the design sent for the server\'s check', async () => {
    await openMeasurementStep();
    await chooseCustomer();
    useThem();
    await screen.findByRole('heading', { name: 'Choose fabric and fit' });
    expect(measurementsAPI.save).not.toHaveBeenCalled();              // no new profile is created by the wizard
    expect(measurementsAPI.update).toHaveBeenCalledTimes(1);
    const [id, payload] = measurementsAPI.update.mock.calls[0];
    expect(id).toBe('m1');
    expect(payload.design).toEqual(D.shortBlouse);
    Object.entries(VALID).forEach(([k, v]) => expect(payload[k]).toBe(v));
    expect(payload.client_name).toBe('Test Customer');
    expect(payload).not.toHaveProperty('email');                      // no contact saved -> none invented
  });

  it('shows what was saved on the Measurements page when the user comes back: a new customer is chosen, an edit is shown', async () => {
    await openMeasurementStep(D.shortBlouse, []);
    expect(screen.getByTestId('meas-none')).toBeTruthy();
    measurementsAPI.getAll.mockResolvedValue({ data: { measurements: [PROFILE] } });   // saved in the other tab
    await act(async () => { window.dispatchEvent(new Event('focus')); });
    await screen.findByTestId('meas-summary');
    expect(document.querySelector('#saved-client-meas').value).toBe('m1');            // the customer just added
    expect(value('bust_cm').textContent).toMatch(/88 cm/);
    measurementsAPI.getAll.mockResolvedValue({ data: { measurements: [{ ...PROFILE, bust_cm: 91.5 }] } });   // edited there
    fireEvent.click(screen.getByTestId('refresh-measurements'));
    await waitFor(() => expect(value('bust_cm').textContent).toMatch(/91\.5 cm/));
  });

  it('a customer who existed before is never chosen automatically', async () => {
    await openMeasurementStep(D.shortBlouse, [PROFILE]);
    await act(async () => { window.dispatchEvent(new Event('focus')); });
    expect(screen.getByTestId('meas-none')).toBeTruthy();
    expect(document.querySelector('#saved-client-meas').value).toBe('');
  });

  it('with no confirmed design every saved value is shown; continuing explains, nothing is sent', async () => {
    await openMeasurementStep({ ...D.shortBlouse, neckline_type: 'halter-neck' });   // not selectable -> never confirmed
    expect(screen.getByTestId('design-selector')).toBeTruthy();
    await chooseCustomer();
    expect(shown()).toEqual(FIELD_KEYS);
    expect(screen.queryByTestId('meas-missing')).toBeNull();          // nothing is "missing" before the design is known
    expect(screen.getByText('Use these measurements').disabled).toBe(false);          // never a dead button
    useThem();
    expect(screen.getByRole('alert').textContent).toMatch(/confirm the design first/i);
    expect(measurementsAPI.update).not.toHaveBeenCalled();
  });

  it('confirming the design inside the step narrows the list to what that design uses', async () => {
    measurementsAPI.getAll.mockResolvedValue({ data: { measurements: [PROFILE] } });
    render(<MemoryRouter><Upload /></MemoryRouter>);
    fireEvent.click(screen.getByRole('button', { name: /^Step 4: Measurements/ }));
    await chooseCustomer();
    expect(value('shoulder_to_bust_cm')).toBeTruthy();
    Object.entries(D.longTshirt).forEach(([k, v]) => fireEvent.change(screen.getByTestId(`select-${k}`), { target: { value: v } }));
    fireEvent.click(screen.getByTestId('confirm-btn'));
    expect(screen.queryByTestId('design-selector')).toBeNull();
    expect(shown()).toEqual(expect.arrayContaining(['hip_cm', 'waist_to_hip_cm', 'bicep_cm', 'sleeve_cm', 'sleeve_end_cm']));
    expect(value('shoulder_to_bust_cm')).toBeNull();                  // a T-shirt has no bust dart
    expect(value('bust_cm').textContent).toMatch(/88 cm/);
  });

  it('names the measurement the server refuses and points to Edit; a general server error is shown as it is', async () => {
    measurementsAPI.update.mockRejectedValueOnce({ response: { status: 400, data: {
      error: 'Upper arm around: required', error_code: 'MEASUREMENT_VALIDATION_FAILED',
      field_errors: { bicep_cm: [{ code: 'REQUIRED', message: 'Upper arm around is required for this design.' }] } } } });
    await openMeasurementStep();
    await chooseCustomer();
    useThem();
    await waitFor(() => expect(screen.getByRole('alert').textContent).toMatch(/Please check these measurements with "Edit measurements": Upper arm around/));
    expect(value('bicep_cm').textContent).toMatch(/required for this design/);
    measurementsAPI.update.mockRejectedValueOnce({ response: { status: 500, data: { error: 'Database down' } } });
    useThem();
    await screen.findByText('Database down');
  });

  it('shows the server\'s "please check" notes without stopping', async () => {
    measurementsAPI.update.mockResolvedValue({ data: { measurement_id: 'm1', warnings: [
      { field: 'bust_cm', code: 'UNUSUAL_VALUE', message: 'Bust around 250 cm is outside the usual range.' }] } });
    await openMeasurementStep(D.shortBlouse, [{ ...PROFILE, bust_cm: 250 }]);
    await chooseCustomer();
    useThem();
    await screen.findByRole('heading', { name: 'Choose fabric and fit' });
    fireEvent.click(screen.getByRole('button', { name: /^Step 4: Measurements/ }));
    expect(screen.getByTestId('warning-bust_cm').textContent).toMatch(/Please check: Bust around 250 cm/);
    expect(measurementsAPI.update.mock.calls[0][1].bust_cm).toBe(250);                // sent exactly as saved
  });
});

// ── the Measurements page: where measurements are typed ─────────────────────────────────────────
const field = (key) => document.querySelector(`#profile-${key}`);
async function openPage(search = '', profiles = []) {
  measurementsAPI.getAll.mockResolvedValue({ data: { measurements: profiles } });
  const view = render(<MemoryRouter initialEntries={[`/measurements${search}`]}><Measurements /></MemoryRouter>);
  await screen.findByRole('heading', { name: 'Body measurements' });
  return view;
}
const savePage = () => fireEvent.click(screen.getByText('Save measurements'));

describe('Measurements page form', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    measurementsAPI.save.mockResolvedValue({ data: { measurement_id: 'm9', warnings: [] } });
    measurementsAPI.update.mockResolvedValue({ data: { measurement_id: 'm1', warnings: [] } });
  });

  it('opened from the wizard for a new customer: empty form with the name, a note, and nothing invented', async () => {
    await openPage('?new=1&from=pattern&name=Amara%20Silva', [PROFILE]);
    expect(screen.getByLabelText('Customer name').value).toBe('Amara Silva');
    expect(document.querySelector('#profile-select').value).toBe('');                 // not the first saved customer
    FIELD_KEYS.forEach((k) => expect(field(k).value).toBe(''));
    expect(screen.getByTestId('from-pattern-note').textContent).toMatch(/go back to the pattern tab/);
    fireEvent.change(field('bust_cm'), { target: { value: '88,5' } });               // decimal comma
    savePage();
    await waitFor(() => expect(measurementsAPI.save).toHaveBeenCalledTimes(1));
    expect(measurementsAPI.save.mock.calls[0][0]).toMatchObject({ client_name: 'Amara Silva', bust_cm: 88.5 });
  });

  it('opened from the wizard with Edit: that customer\'s profile, and saving updates it', async () => {
    const other = { ...PROFILE, measurement_id: 'm0', client_name: 'Someone Else', bust_cm: 100 };
    await openPage('?profile=m1&from=pattern', [other, PROFILE]);
    expect(document.querySelector('#profile-select').value).toBe('m1');
    expect(field('bust_cm').value).toBe('88');
    fireEvent.change(field('bust_cm'), { target: { value: '91.5' } });
    savePage();
    await waitFor(() => expect(measurementsAPI.update).toHaveBeenCalledTimes(1));
    expect(measurementsAPI.update.mock.calls[0][0]).toBe('m1');
    expect(measurementsAPI.update.mock.calls[0][1].bust_cm).toBe(91.5);
    expect(measurementsAPI.save).not.toHaveBeenCalled();
  });

  it('opened on its own: no note about a pattern', async () => {
    await openPage('', [PROFILE]);
    expect(screen.queryByTestId('from-pattern-note')).toBeNull();
    expect(field('bust_cm').value).toBe('88');
  });

  it('uses text inputs so nothing typed is dropped; a mistyped value is reported beside its field and nothing is saved', async () => {
    await openPage('?new=1&name=Test');
    expect(document.querySelectorAll('input[type="number"]').length).toBe(0);
    fireEvent.change(field('waist_cm'), { target: { value: '70' } });
    fireEvent.change(field('bust_cm'), { target: { value: '1e2' } });
    expect(field('bust_cm').value).toBe('1e2');
    savePage();
    expect((await screen.findByTestId('profile-error-bust_cm')).textContent).toMatch(/not a number/);
    expect(field('waist_cm').value).toBe('70');                       // other inputs preserved
    fireEvent.change(field('bust_cm'), { target: { value: '0' } });
    savePage();
    expect((await screen.findByTestId('profile-error-bust_cm')).textContent).toMatch(/greater than 0/);
    expect(measurementsAPI.save).not.toHaveBeenCalled();
    fireEvent.change(field('bust_cm'), { target: { value: '88' } });
    expect(screen.queryByTestId('profile-error-bust_cm')).toBeNull();                 // cleared as the field is edited
  });

  it('shows the calculated value of an empty design field, in the chosen unit, and hides it once a value is typed', async () => {
    await openPage('?new=1&name=Test');
    expect(screen.queryByTestId('calculated-armhole_depth_cm')).toBeNull();          // nothing to calculate from yet
    fireEvent.change(field('bust_cm'), { target: { value: '86.36' } });              // 34 in
    expect(screen.getByTestId('calculated-armhole_depth_cm').textContent).toMatch(/Calculated value: 19\.1 cm/);   // 7.5 in
    expect(screen.getByTestId('calculated-neck_width_cm').textContent).toMatch(/14\.4 cm/);
    fireEvent.click(screen.getByTestId('page-unit-in'));
    expect(screen.getByTestId('calculated-armhole_depth_cm').textContent).toMatch(/7\.5 in/);
    fireEvent.click(screen.getByTestId('page-unit-cm'));
    fireEvent.change(field('armhole_depth_cm'), { target: { value: '21' } });
    expect(screen.queryByTestId('calculated-armhole_depth_cm')).toBeNull();
  });

  it('warns about an unusual value beside its field but still saves it as entered', async () => {
    await openPage('?new=1&name=Test');
    fireEvent.change(field('bust_cm'), { target: { value: '250' } });
    expect(screen.getByTestId('warning-bust_cm').textContent).toMatch(/Please check/);
    savePage();
    await waitFor(() => expect(measurementsAPI.save).toHaveBeenCalledTimes(1));
    expect(measurementsAPI.save.mock.calls[0][0].bust_cm).toBe(250);
  });

  it('switching units changes only the display: no double conversion, values saved with the unit they were typed in', async () => {
    await openPage('?new=1&name=Test');
    fireEvent.change(field('bust_cm'), { target: { value: '88.9' } });
    fireEvent.click(screen.getByTestId('page-unit-in'));
    expect(field('bust_cm').value).toBe('35');                        // 88.9 cm shown as 35 in
    fireEvent.change(field('shoulder_width_cm'), { target: { value: '14.25' } });   // typed in inches
    fireEvent.click(screen.getByTestId('page-unit-cm'));
    fireEvent.click(screen.getByTestId('page-unit-in'));
    fireEvent.click(screen.getByTestId('page-unit-cm'));
    expect(field('bust_cm').value).toBe('88.9');                      // still exactly what was typed
    savePage();
    await waitFor(() => expect(measurementsAPI.save).toHaveBeenCalledTimes(1));
    const payload = measurementsAPI.save.mock.calls[0][0];
    expect(payload.bust_cm).toBe(88.9);
    expect(payload.units.bust_cm).toBe('cm');
    expect(payload.shoulder_width_cm).toBe(14.25);
    expect(payload.units.shoulder_width_cm).toBe('in');               // the server converts it once, exactly
  });

  it('shows how to measure the active field, with a common mistake, and moves the sleeve line with the entered length', async () => {
    await openPage('?new=1&name=Test');
    fireEvent.focus(field('sleeve_cm'));
    const guide = screen.getByTestId('profile-guide-sleeve_cm').textContent;
    expect(guide).toMatch(/How to measure/);
    expect(guide).toMatch(/from the shoulder tip down the outside of the arm to where you want the sleeve to end/);
    expect(guide).toMatch(/Common mistake: Start at the shoulder tip, not at the neck/);
    expect(screen.queryByTestId('profile-guide-bust_cm')).toBeNull();
    fireEvent.change(field('sleeve_cm'), { target: { value: '20' } });
    const shortEnd = screen.getByTestId('sleeve-guide-line').getAttribute('data-end');
    fireEvent.change(field('sleeve_cm'), { target: { value: '55' } });
    const longEnd = screen.getByTestId('sleeve-guide-line').getAttribute('data-end');
    expect(Number(longEnd.split(',')[1])).toBeGreaterThan(Number(shortEnd.split(',')[1]));
    fireEvent.change(field('sleeve_cm'), { target: { value: '60.96' } });
    const cmEnd = screen.getByTestId('sleeve-guide-line').getAttribute('data-end');
    fireEvent.click(screen.getByTestId('page-unit-in'));
    fireEvent.change(field('sleeve_cm'), { target: { value: '24' } });
    expect(screen.getByTestId('sleeve-guide-line').getAttribute('data-end')).toBe(cmEnd);   // 24 in == 60.96 cm
  });

  it('the body guide has a front and a back view and highlights the measurement being entered', async () => {
    await openPage('?new=1&name=Test');
    expect(screen.getByTestId('measure-view-front')).toBeTruthy();
    expect(screen.getByTestId('measure-view-back')).toBeTruthy();
    fireEvent.focus(field('bust_cm'));
    expect(screen.getByTestId('measure-figure').getAttribute('data-active-view')).toBe('front');
    expect(screen.getByTestId('guide-line-bust_cm').getAttribute('data-active')).toBe('yes');
    expect(screen.getByTestId('guide-line-waist_cm').getAttribute('data-active')).toBe('no');     // the others fade
    fireEvent.focus(field('back_waist_length_cm'));
    expect(screen.getByTestId('measure-figure').getAttribute('data-active-view')).toBe('back');
    expect(screen.getByTestId('measure-view-back').getAttribute('data-current')).toBe('yes');
    fireEvent.click(screen.getByRole('button', { name: 'How to measure Shoulder to shoulder' }));   // the info button
    expect(screen.getByTestId('profile-guide-shoulder_width_cm').textContent).toMatch(/tip of one shoulder to the tip of the other/);
  });

  it('displays structured server-side errors under the right field', async () => {
    measurementsAPI.save.mockRejectedValue({ response: { status: 400, data: {
      error: 'Bust around: not valid', error_code: 'MEASUREMENT_VALIDATION_FAILED',
      field_errors: { bust_cm: [{ code: 'NOT_POSITIVE', message: 'Bust around must be greater than 0.' }] } } } });
    await openPage('?new=1&name=Test');
    fireEvent.change(field('bust_cm'), { target: { value: '88' } });
    savePage();
    expect((await screen.findByTestId('profile-error-bust_cm')).textContent).toMatch(/greater than 0/);
  });
});
