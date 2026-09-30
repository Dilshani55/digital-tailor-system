// End-to-end behaviour of the 7-step creation wizard against a mocked API.
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import React from 'react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import Upload from '../pages/Upload';
import { imagesAPI, measurementsAPI, patternsAPI, exportAPI, researchAPI } from '../services/api';
import { friendlyError, imageProblem } from '../utils/friendlyError';

vi.mock('../services/api', () => ({
  imagesAPI: { upload: vi.fn(), analyse: vi.fn(), confirmAttributes: vi.fn(), modelStatus: vi.fn() },
  measurementsAPI: { save: vi.fn(), getAll: vi.fn(), update: vi.fn() },
  patternsAPI: { generate: vi.fn() },
  exportAPI: { yardage: vi.fn(), estimates: vi.fn(), pdf: vi.fn(), download: vi.fn() },
  researchAPI: { submitFeedback: vi.fn() },
}));
vi.mock('../components/MeasurementGuide', () => ({ default: () => <div data-testid="guide-stub" /> }));
vi.mock('../components/FabricRecommendation', () => ({
  default: ({ onSelectFabric }) => (
    <button type="button" onClick={() => onSelectFabric('cotton-poplin', 'Cotton Poplin', 'woven')}>pick-poplin</button>
  ),
}));

const VALID = {
  bust_cm: 88, waist_cm: 70, hip_cm: 94, height_cm: 162, neck_cm: 36, shoulder_cm: 12, across_back_cm: 34,
  back_waist_length_cm: 40, armhole_depth_cm: 20, garment_length_cm: 65, bicep_cm: 28, sleeve_cm: 55, wrist_cm: 16,
};
const CONFIRMED = { garment_type: 'blouse', neckline_type: 'round-neck', sleeve_length: 'short-sleeve', sleeve_style: 'regular-sleeve' };

const piece = {
  name: 'Front Bodice', piece_type: 'front_bodice', cut_count: 1, cut_on_fold: true,
  outline: [[0, 0], [20, 0], [20, 40], [0, 40]], cutting_line: [[0, -1], [21.5, -1], [21.5, 42], [0, 42]],
  bounding_box: { width_cm: 20, height_cm: 40, min_x: 0, min_y: 0 },
  cut_bounding_box: { width_cm: 21.5, height_cm: 43, min_x: 0, min_y: -1 },
  notches: [{ id: 'n1', point: [20, 20] }], darts: [], grain_line: { start: [10, 5], end: [10, 35] },
};
const ROW = (inches, cm, purchase, selected) => ({
  fabric_width_in: inches, fabric_width_cm: cm, fits: true, selected, usable_width_cm: cm / 2, cutting_mode: 'folded',
  cutting_method_simple: 'Fabric folded in half lengthwise', base_layout_length_cm: 120, purchasing_allowance_cm: 20,
  recommended_purchase_m: purchase, recommended_purchase_yd: 1.53, utilisation_percent: 41.2, waste_percent: 58.8,
  warnings: [],
  placed_pieces: [{ name: 'Front Bodice', x: 0, y: 0, width: 21.5, height: 43, polygon_coordinates: [[0, 0], [21.5, 0], [21.5, 43], [0, 43]] }],
});
const ESTIMATES = (selectedCm = 114.3) => ({ data: {
  selected_width_cm: selectedCm, method: 'test method', purchase_rule: 'test rule',
  estimates: [ROW(36, 91.44, 1.8, selectedCm === 91.44), ROW(45, 114.3, 1.4, selectedCm === 114.3), ROW(60, 152.4, 1.1, selectedCm === 152.4)],
} });

function stubAll() {
  vi.clearAllMocks();
  measurementsAPI.getAll.mockResolvedValue({ data: { measurements: [] } });
  imagesAPI.upload.mockResolvedValue({ data: { image_id: 'i1' } });
  imagesAPI.modelStatus.mockResolvedValue({ data: { available: true } });
  imagesAPI.analyse.mockResolvedValue({ data: { garment_attributes: null, confirmed_attributes: {} } });
  imagesAPI.confirmAttributes.mockResolvedValue({ data: { confirmed_attributes: CONFIRMED } });
  measurementsAPI.save.mockResolvedValue({ data: { measurement_id: 'm1' } });
  measurementsAPI.update.mockResolvedValue({ data: { profile_id: 'm1' } });
  patternsAPI.generate.mockResolvedValue({ data: {
    pattern_id: 'p1', validation_passed: true, validation: { passed: true, errors: [] }, pattern_pieces: [piece],
    armhole_sleeve: null, final_pattern: { transformations: [] },
  } });
  exportAPI.estimates.mockImplementation((id, body) => Promise.resolve(ESTIMATES(body.selected_width_cm)));
  exportAPI.pdf.mockResolvedValue({ data: { export_id: 'e1', pages: 14 } });
  exportAPI.download.mockResolvedValue({ data: new Blob(['%PDF']) });
  researchAPI.submitFeedback.mockResolvedValue({ data: {} });
  window.URL.createObjectURL = vi.fn(() => 'blob:x');
  window.URL.revokeObjectURL = vi.fn();
}

const chooseDesign = (over = {}) => {
  const d = { ...CONFIRMED, ...over };
  Object.entries(d).forEach(([k, v]) =>
    fireEvent.change(screen.getByTestId(`select-${k}`), { target: { value: v } }));
  fireEvent.click(screen.getByTestId('confirm-btn'));
};
const fill = () => Object.entries(VALID).forEach(([k, v]) =>
  fireEvent.change(document.querySelector(`#meas-${k}`), { target: { value: String(v) } }));

const heading = (name) => screen.findByRole('heading', { name });

function startWizard({ name = 'Test Customer', contact = '', project = '' } = {}) {
  render(<MemoryRouter><Upload /></MemoryRouter>);
  fireEvent.change(screen.getByLabelText('Customer name'), { target: { value: name } });
  if (contact) fireEvent.change(screen.getByLabelText(/Contact \/ reference/), { target: { value: contact } });
  if (project) fireEvent.change(screen.getByLabelText(/Design \/ project name/), { target: { value: project } });
  fireEvent.click(screen.getByText('Continue to upload'));
}

async function reachStep4(opts) {
  startWizard(opts);
  const file = new File(['x'], 'top.jpg', { type: 'image/jpeg' });
  fireEvent.change(screen.getByTestId('image-input'), { target: { files: [file] } });
  fireEvent.click(screen.getByText('Upload and analyse'));
  await heading('Review the AI suggestions');
  chooseDesign();
  await waitFor(() => expect(screen.getByText('Continue to measurements').disabled).toBe(false));
  fireEvent.click(screen.getByText('Continue to measurements'));
  fill();
  fireEvent.click(screen.getByText('Save and continue'));
  await heading('Choose fabric and fit');
}

describe('creation wizard — full workflow', () => {
  beforeEach(stubAll);

  it('runs customer → upload → AI review → measurements → fabric → pattern → estimate → PDF → feedback', async () => {
    await reachStep4({ contact: 'amara@example.com', project: 'Wedding blouse' });
    expect(imagesAPI.upload).toHaveBeenCalledTimes(1);
    expect(imagesAPI.analyse).toHaveBeenCalledWith('i1');
    expect(imagesAPI.confirmAttributes).toHaveBeenCalledWith('i1', CONFIRMED);
    expect(measurementsAPI.save.mock.calls[0][0]).toMatchObject({ unit: 'cm', client_name: 'Test Customer', email: 'amara@example.com' });

    fireEvent.click(screen.getByText('pick-poplin'));
    fireEvent.click(screen.getByText('Confirm and generate pattern'));
    await heading('Pattern preview');
    expect(measurementsAPI.update).toHaveBeenCalledWith('m1', { fabric_type: 'woven', fit_preference: 'standard' });
    expect(patternsAPI.generate.mock.calls[0][0]).toMatchObject({
      measurement_id: 'm1', image_id: 'i1', fabric_id: 'cotton-poplin', confirmed_attributes: CONFIRMED,
      project_name: 'Wedding blouse',
    });
    expect(screen.getByTestId('pattern-preview')).toBeTruthy();
    expect(screen.getByTestId('cutting-line-0')).toBeTruthy();       // seam-allowance geometry is drawn

    fireEvent.click(screen.getByText('Continue to fabric estimate'));
    await heading('Fabric estimate');
    await waitFor(() => expect(exportAPI.estimates).toHaveBeenCalledWith('p1', { selected_width_cm: 114.3, cutting_mode: 'auto' }));
    expect((await screen.findAllByText('1.4 m')).length).toBeGreaterThan(0);
    const table = screen.getByTestId('width-comparison');
    ['36"', '45"', '60"', '91.44 cm', '114.3 cm', '152.4 cm', '1.8 m', '1.1 m'].forEach((t) => expect(table.textContent).toContain(t));
    expect(screen.getByTestId('nesting-layout')).toBeTruthy();
    fireEvent.click(screen.getByTestId('width-60'));
    await waitFor(() => expect(exportAPI.estimates).toHaveBeenLastCalledWith('p1', { selected_width_cm: 152.4, cutting_mode: 'auto' }));
    await waitFor(() => expect(screen.getByTestId('width-60').textContent).toBe('Selected'));

    fireEvent.click(screen.getByText('Continue to PDF export'));
    await heading('Printable pattern (PDF)');
    expect(screen.getByText(/100% \/ Actual size/)).toBeTruthy();
    expect(screen.getByTestId('tile-preview')).toBeTruthy();
    fireEvent.click(screen.getByText('Create printable PDF'));
    await screen.findByTestId('pdf-ready');
    expect(screen.getByTestId('pdf-ready').textContent).toMatch(/14 pages/);
    fireEvent.click(screen.getByRole('button', { name: 'Download PDF' }));
    await waitFor(() => expect(exportAPI.download).toHaveBeenCalledWith('e1'));

    await screen.findByLabelText(/How easy was it/);
    fireEvent.click(screen.getByText('Send feedback'));
    await waitFor(() => expect(researchAPI.submitFeedback).toHaveBeenCalledWith(expect.objectContaining({ pattern_id: 'p1' })));
    await screen.findByText(/Thank you/);
  });

  it('cannot open later steps before earlier ones are done', () => {
    render(<MemoryRouter><Upload /></MemoryRouter>);
    ['Upload image', 'AI review', 'Measurements', 'Fabric & fit', 'Pattern preview', 'Fabric estimate', 'Download PDF'].forEach((label) =>
      expect(screen.getByText(label, { selector: '.wstep-lbl' }).closest('button').disabled).toBe(true));
  });

  it('asks for the customer name before continuing', () => {
    render(<MemoryRouter><Upload /></MemoryRouter>);
    fireEvent.click(screen.getByText('Continue to upload'));
    expect(screen.getByRole('alert').textContent).toMatch(/customer name/);
    expect(screen.queryByTestId('image-input')).toBeNull();
  });

  it('rejects a non-image or oversized file with a plain message', () => {
    startWizard();
    fireEvent.change(screen.getByTestId('image-input'), { target: { files: [new File(['x'], 'a.pdf', { type: 'application/pdf' })] } });
    expect(screen.getByRole('alert').textContent).toMatch(/JPG, PNG or WEBP/);
    expect(imagesAPI.upload).not.toHaveBeenCalled();
  });

  it('shows a friendly message (no stack trace) when the AI service fails', async () => {
    imagesAPI.analyse.mockRejectedValue({ response: { status: 500, data: { error: 'Traceback (most recent call last): File "C:\\x\\y.py"' } } });
    startWizard();
    fireEvent.change(screen.getByTestId('image-input'), { target: { files: [new File(['x'], 'a.jpg', { type: 'image/jpeg' })] } });
    fireEvent.click(screen.getByText('Upload and analyse'));
    const alert = await screen.findByRole('alert');
    expect(alert.textContent).not.toMatch(/Traceback|C:\\/);
    expect(alert.textContent).toMatch(/could not analyse|problem/i);
  });

  it('says honestly when the AI model is unavailable and keeps the manual path open', async () => {
    imagesAPI.modelStatus.mockResolvedValue({ data: { available: false } });
    startWizard();
    await screen.findByTestId('model-unavailable');
    fireEvent.change(screen.getByTestId('image-input'), { target: { files: [new File(['x'], 'a.jpg', { type: 'image/jpeg' })] } });
    expect(screen.getByText('Upload and analyse').disabled).toBe(true);
    fireEvent.click(screen.getByText('Choose the design manually'));
    await heading('Review the AI suggestions');
    expect(screen.getByTestId('fallback-notice')).toBeTruthy();
    expect(imagesAPI.analyse).not.toHaveBeenCalled();
  });

  it('turns a 503 from the analyse call into the model-unavailable message', async () => {
    imagesAPI.analyse.mockRejectedValue({ response: { status: 503, data: { error_code: 'MODEL_UNAVAILABLE', error: 'x' } } });
    startWizard();
    fireEvent.change(screen.getByTestId('image-input'), { target: { files: [new File(['x'], 'a.jpg', { type: 'image/jpeg' })] } });
    fireEvent.click(screen.getByText('Upload and analyse'));
    const alert = await screen.findByRole('alert');
    expect(alert.textContent).toMatch(/not available right now.*choose the design manually/);
  });

  it('sends the user back to the design step when the server rejects the design', async () => {
    await reachStep4();
    patternsAPI.generate.mockRejectedValue({ response: { status: 422, data: { error_code: 'UNSUPPORTED_DESIGN', error: 'raw' } } });
    fireEvent.click(screen.getByText('pick-poplin'));
    fireEvent.click(screen.getByText('Confirm and generate pattern'));
    await heading('Review the AI suggestions');
    expect(screen.getByRole('alert').textContent).toMatch(/outside what the system can draft/);
  });

  it('blocks the fabric estimate when the pattern failed validation', async () => {
    patternsAPI.generate.mockResolvedValue({ data: {
      pattern_id: 'p1', validation_passed: false, fabric_estimate_blocked: true,
      validation: { passed: false, errors: ['Front Bodice: outline self-intersects'] }, pattern_pieces: [piece],
    } });
    await reachStep4();
    fireEvent.click(screen.getByText('pick-poplin'));
    fireEvent.click(screen.getByText('Confirm and generate pattern'));
    await heading('Pattern preview');
    expect(screen.getByText('Continue to fabric estimate').disabled).toBe(true);
    expect(screen.getAllByText(/outline self-intersects/).length).toBeGreaterThan(0);
    expect(exportAPI.estimates).not.toHaveBeenCalled();
  });

  it('shows an honest failure (not a number) when the estimate cannot be calculated', async () => {
    exportAPI.estimates.mockResolvedValue({ data: { selected_width_cm: 114.3, method: 'm', purchase_rule: 'r', estimates: [
      ROW(36, 91.44, 1.8, false),
      { fabric_width_in: 45, fabric_width_cm: 114.3, fits: false, selected: true, error_code: 'PIECE_DOES_NOT_FIT',
        error: 'A pattern piece is wider than the fabric.' },
      ROW(60, 152.4, 1.1, false),
    ] } });
    await reachStep4();
    fireEvent.click(screen.getByText('pick-poplin'));
    fireEvent.click(screen.getByText('Confirm and generate pattern'));
    await heading('Pattern preview');
    fireEvent.click(screen.getByText('Continue to fabric estimate'));
    expect((await screen.findAllByText(/wider than the fabric/)).length).toBeGreaterThan(0);
    expect(screen.getByTestId('estimate-row-45').textContent).toMatch(/Does not fit/);
    expect(screen.getByTestId('width-45').disabled).toBe(true);
    expect(screen.getAllByText('Calculation failed').length).toBeGreaterThan(0);
    expect(screen.getByText('Continue to PDF export').disabled).toBe(true);
  });
});

describe('friendlyError / imageProblem', () => {
  it('maps codes, hides internals and handles network failures', () => {
    expect(friendlyError({ response: { data: { error_code: 'INVALID_FABRIC_WIDTH' } } })).toMatch(/valid fabric width/);
    expect(friendlyError({ response: { status: 500, data: { error: 'Traceback boom' } } })).toMatch(/server had a problem/);
    expect(friendlyError({ code: 'ERR_NETWORK', request: {} })).toMatch(/Cannot reach the server/);
    expect(friendlyError({ response: { status: 413, data: {} } })).toMatch(/too large/);
    expect(friendlyError(null, 'fallback')).toBe('fallback');
  });
  it('validates image files', () => {
    expect(imageProblem(null)).toBeTruthy();
    expect(imageProblem({ type: 'image/gif', size: 5 })).toMatch(/JPG/);
    expect(imageProblem({ type: 'image/png', size: 17 * 1024 * 1024 })).toMatch(/16 MB/);
    expect(imageProblem({ type: 'image/webp', size: 1000 })).toBe('');
  });
});
