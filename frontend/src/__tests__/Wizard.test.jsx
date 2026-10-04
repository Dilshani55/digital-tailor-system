// End-to-end behaviour of the 8-step creation wizard against a mocked API.
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import Upload from '../pages/Upload';
import { imagesAPI, measurementsAPI, patternsAPI, exportAPI, researchAPI } from '../services/api';
import { friendlyError, imageProblem } from '../utils/friendlyError';
import { readWizardDraft, saveWizardDraft, clearWizardDraft } from '../utils/wizardDraft';

vi.mock('../utils/wizardDraft', () => ({
  wizardOwner: () => 'test-user', readWizardDraft: vi.fn(), saveWizardDraft: vi.fn(), clearWizardDraft: vi.fn(),
}));

vi.mock('../services/api', () => ({
  imagesAPI: { upload: vi.fn(), analyse: vi.fn(), confirmAttributes: vi.fn(), modelStatus: vi.fn() },
  measurementsAPI: { save: vi.fn(), getAll: vi.fn(), update: vi.fn() },
  patternsAPI: { generate: vi.fn() },
  exportAPI: { yardage: vi.fn(), estimates: vi.fn(), pdf: vi.fn(), download: vi.fn() },
  researchAPI: { submitFeedback: vi.fn() },
}));
vi.mock('../components/FabricRecommendation', () => ({
  default: ({ onSelectFabric }) => (
    <>
    <button type="button" onClick={() => onSelectFabric('cotton-poplin', 'Cotton Poplin', 'woven')}>pick-poplin</button>
    <button type="button" onClick={() => onSelectFabric('alam-2013-f06', 'Cotton plain - F06', 'woven', {
      study_id: 'alam-ghosh-2013', goals: { mass: 'cost', thickness: 'cost', thermal_resistance: 'cost' }, comparisons: [
        { left: 'mass', right: 'thickness', ratio: 1 }, { left: 'mass', right: 'thermal_resistance', ratio: 1 },
        { left: 'thickness', right: 'thermal_resistance', ratio: 1 },
      ],
    })}>pick-published-sample</button>
    </>
  ),
}));

const VALID = {
  bust_cm: 88, waist_cm: 70, hip_cm: 94, shoulder_width_cm: 37, back_waist_length_cm: 40, shoulder_to_bust_cm: 25,
  waist_to_hip_cm: 20, garment_length_cm: 65, bicep_cm: 28, sleeve_cm: 24, sleeve_end_cm: 27,
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
  readWizardDraft.mockResolvedValue(null);
  saveWizardDraft.mockResolvedValue(undefined);
  clearWizardDraft.mockResolvedValue(undefined);
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
// fills only the fields the confirmed design shows
const fill = () => Object.entries(VALID).forEach(([k, v]) => {
  const input = document.querySelector(`#meas-${k}`);
  if (input) fireEvent.change(input, { target: { value: String(v) } });
});
const stepButton = (label) => screen.getByText(label, { selector: '.wstep-lbl' }).closest('button');

const heading = (name) => screen.findByRole('heading', { name });

async function reloadWizard() {
  const saved = saveWizardDraft.mock.calls.at(-1)[1];
  cleanup();
  readWizardDraft.mockResolvedValue(saved);
  render(<MemoryRouter><Upload /></MemoryRouter>);
  await waitFor(() => expect(screen.getByRole('button', { name: 'Start new pattern' })).toBeVisible());
}

async function renderWizard() {
  render(<MemoryRouter><Upload /></MemoryRouter>);
  await heading('Customer and design');
}

async function startWizard({ name = 'Test Customer', contact = '', project = '' } = {}) {
  await renderWizard();
  fireEvent.change(screen.getByLabelText('Customer name'), { target: { value: name } });
  if (contact) fireEvent.change(screen.getByLabelText(/Contact \/ reference/), { target: { value: contact } });
  if (project) fireEvent.change(screen.getByLabelText(/Design \/ project name/), { target: { value: project } });
  fireEvent.click(screen.getByText('Continue to upload'));
}

async function reachStep4(opts) {
  await startWizard(opts);
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

  it('restores the fabric step and earlier customer, confirmed design, measurements and selected sample after reload', async () => {
    await reachStep4({ contact: 'amara@example.com', project: 'Refresh blouse' });
    fireEvent.click(screen.getByText('pick-published-sample'));
    fireEvent.click(screen.getByTestId('fit-loose'));
    await reloadWizard();
    await heading('Choose fabric and fit');
    expect(screen.queryByText('Fabric recommendations pending')).toBeNull();
    expect(screen.getByTestId('fit-loose')).toHaveAttribute('aria-pressed', 'true');
    expect(stepButton('AI review')).toHaveAttribute('data-status', 'done');
    expect(stepButton('Measurements')).toHaveAttribute('data-status', 'done');
    fireEvent.click(stepButton('Customer & design'));
    expect(screen.getByLabelText('Customer name')).toHaveValue('Test Customer');
    expect(screen.getByLabelText(/Contact \/ reference/)).toHaveValue('amara@example.com');
    expect(screen.getByLabelText(/Design \/ project name/)).toHaveValue('Refresh blouse');
    fireEvent.click(stepButton('AI review'));
    expect(screen.getByTestId('confirmed-badge')).toBeVisible();
    expect(screen.getByTestId('select-garment_type')).toHaveValue('blouse');
    expect(screen.getByRole('img', { name: 'Uploaded garment' })).toBeVisible();
    fireEvent.click(stepButton('Measurements'));
    expect(document.querySelector('#meas-bust_cm')).toHaveValue('88');
    expect(document.querySelector('#meas-sleeve_cm')).toHaveValue('24');
    fireEvent.click(stepButton('Fabric & fit'));
    fireEvent.click(screen.getByText('Confirm and generate pattern'));
    await heading('Pattern preview');
    expect(patternsAPI.generate).toHaveBeenLastCalledWith(expect.objectContaining({
      image_id: 'i1', measurement_id: 'm1', fabric_id: 'alam-2013-f06',
      confirmed_attributes: CONFIRMED, fabric_preferences: expect.objectContaining({ study_id: 'alam-ghosh-2013' }),
    }));
    expect(imagesAPI.upload).toHaveBeenCalledTimes(1);
    expect(imagesAPI.analyse).toHaveBeenCalledTimes(1);
    expect(measurementsAPI.save).toHaveBeenCalledTimes(1);
  });

  it('restores unconfirmed design edits and unsaved measurements with their original units', async () => {
    await startWizard();
    fireEvent.click(screen.getByText('Choose the design manually'));
    fireEvent.change(screen.getByTestId('select-garment_type'), { target: { value: 'blouse' } });
    fireEvent.change(screen.getByTestId('select-neckline_type'), { target: { value: 'v-neck' } });
    await reloadWizard();
    await heading('Review the AI suggestions');
    expect(screen.getByTestId('select-garment_type')).toHaveValue('blouse');
    expect(screen.getByTestId('select-neckline_type')).toHaveValue('v-neck');
    expect(screen.getByTestId('confirm-btn')).toBeDisabled();
    expect(screen.queryByTestId('confirmed-badge')).toBeNull();
    fireEvent.click(stepButton('Measurements'));
    fireEvent.click(screen.getByTestId('unit-in'));
    fireEvent.change(document.querySelector('#meas-bust_cm'), { target: { value: '38.5' } });
    fireEvent.click(screen.getByTestId('unit-cm'));
    await reloadWizard();
    await heading('Body measurements');
    expect(document.querySelector('#meas-bust_cm')).toHaveValue('97.79');
    fireEvent.click(screen.getByTestId('unit-in'));
    expect(document.querySelector('#meas-bust_cm')).toHaveValue('38.5');
    expect(stepButton('Measurements')).toHaveAttribute('data-status', 'pending');
    expect(measurementsAPI.save).not.toHaveBeenCalled();
  });

  it('restores pattern, estimate and PDF results without generating duplicates, and still invalidates changed inputs', async () => {
    await reachStep4();
    fireEvent.click(screen.getByText('pick-poplin'));
    fireEvent.click(screen.getByText('Confirm and generate pattern'));
    await heading('Pattern preview');
    await reloadWizard();
    await heading('Pattern preview');
    expect(screen.getByTestId('pattern-preview')).toBeVisible();
    fireEvent.click(screen.getByText('Continue to fabric estimate'));
    await screen.findByTestId('width-comparison');
    fireEvent.click(screen.getByTestId('width-60'));
    await waitFor(() => expect(screen.getByTestId('width-60')).toHaveTextContent('Selected'));
    await reloadWizard();
    await heading('Fabric estimate');
    expect(screen.getByTestId('width-60')).toHaveTextContent('Selected');
    expect(exportAPI.estimates).toHaveBeenCalledTimes(2);
    fireEvent.click(screen.getByText('Continue to PDF export'));
    fireEvent.click(screen.getByTestId('pdf-part-report'));
    fireEvent.click(screen.getByText('Create printable PDF'));
    await screen.findByTestId('pdf-ready');
    await reloadWizard();
    await screen.findByTestId('pdf-ready');
    expect(screen.getByTestId('pdf-part-report')).toBeChecked();
    expect(screen.getByRole('button', { name: 'Download PDF' })).toBeVisible();
    expect(patternsAPI.generate).toHaveBeenCalledTimes(1);
    expect(exportAPI.pdf).toHaveBeenCalledTimes(1);
    fireEvent.click(stepButton('Measurements'));
    fireEvent.change(document.querySelector('#meas-bust_cm'), { target: { value: '91.5' } });
    await reloadWizard();
    expect(stepButton('Pattern preview')).toHaveAttribute('data-status', 'stale');
    fireEvent.click(stepButton('Download PDF'));
    expect(screen.queryByTestId('pdf-ready')).toBeNull();
    expect(screen.getByTestId('step-empty')).toHaveTextContent('out of date');
  });

  it('waits for restoration before saving, so defaults never overwrite an existing draft', async () => {
    let restore;
    readWizardDraft.mockImplementationOnce(() => new Promise((resolve) => { restore = resolve; }));
    render(<MemoryRouter><Upload /></MemoryRouter>);
    expect(screen.getByText('Restoring your pattern draft…')).toBeVisible();
    expect(saveWizardDraft).not.toHaveBeenCalled();
    restore({ step: 1, meas: { client_name: 'Recovered customer' } });
    expect(await screen.findByLabelText('Customer name')).toHaveValue('Recovered customer');
  });

  it('warns when draft storage fails while keeping inputs usable', async () => {
    saveWizardDraft.mockRejectedValue(new Error('Quota exceeded'));
    await startWizard({ name: 'Keep my inputs' });
    expect(await screen.findByRole('alert')).toHaveTextContent('could not save this draft');
    fireEvent.click(stepButton('Customer & design'));
    expect(screen.getByLabelText('Customer name')).toHaveValue('Keep my inputs');
  });

  it('does not overwrite a draft after a restoration failure', async () => {
    readWizardDraft.mockRejectedValue(new Error('Storage unavailable'));
    await renderWizard();
    expect(screen.getByRole('alert')).toHaveTextContent('could not restore');
    fireEvent.change(screen.getByLabelText('Customer name'), { target: { value: 'Work in memory' } });
    fireEvent.click(stepButton('Measurements'));
    expect(saveWizardDraft).not.toHaveBeenCalled();
    fireEvent.click(stepButton('Customer & design'));
    expect(screen.getByLabelText('Customer name')).toHaveValue('Work in memory');
  });

  it('only clears a draft when Start new pattern is confirmed and leaves saved patterns alone', async () => {
    await reachStep4();
    const confirm = vi.spyOn(window, 'confirm').mockReturnValueOnce(false).mockReturnValueOnce(true);
    fireEvent.click(screen.getByRole('button', { name: 'Start new pattern' }));
    expect(clearWizardDraft).not.toHaveBeenCalled();
    expect(screen.getByRole('heading', { name: 'Choose fabric and fit' })).toBeVisible();
    fireEvent.click(screen.getByRole('button', { name: 'Start new pattern' }));
    await heading('Customer and design');
    expect(clearWizardDraft).toHaveBeenCalledWith('test-user');
    expect(screen.getByLabelText('Customer name')).toHaveValue('');
    expect(stepButton('AI review')).toHaveAttribute('data-status', 'pending');
    expect(stepButton('Measurements')).toHaveAttribute('data-status', 'pending');
    await reloadWizard();
    expect(screen.getByLabelText('Customer name')).toHaveValue('');
    confirm.mockRestore();
  });

  it('opens an explicitly selected customer in a fresh workflow rather than reviving a different customer draft', async () => {
    readWizardDraft.mockResolvedValue({ step: 5, meas: { client_name: 'Old draft customer' }, confirmedAttributes: CONFIRMED,
      isAttributesConfirmed: true, selectedFabricId: 'cotton-poplin', measurementId: 'old-m' });
    render(<MemoryRouter initialEntries={[{ pathname: '/upload', state: { selectedProfile: {
      measurement_id: 'new-m', client_name: 'Chosen customer', bust_cm: 90, waist_cm: 72, email: 'chosen@example.test',
    } } }]}><Upload /></MemoryRouter>);
    await heading('Customer and design');
    expect(screen.getByLabelText('Customer name')).toHaveValue('Chosen customer');
    expect(stepButton('AI review')).toHaveAttribute('data-status', 'pending');
    await reloadWizard();
    expect(screen.getByLabelText('Customer name')).toHaveValue('Chosen customer');
    fireEvent.click(stepButton('Measurements'));
    fireEvent.change(document.querySelector('#meas-bust_cm'), { target: { value: '92' } });
    await reloadWizard();
    expect(document.querySelector('#meas-bust_cm')).toHaveValue('92');
  });

  it('sends the selected source sample and preferences for server recomputation, and clears them for a catalogue choice', async () => {
    await reachStep4();
    fireEvent.click(screen.getByText('pick-published-sample'));
    fireEvent.click(screen.getByText('Confirm and generate pattern'));
    await heading('Pattern preview');
    expect(patternsAPI.generate.mock.calls[0][0]).toMatchObject({ fabric_id: 'alam-2013-f06',
      fabric_preferences: { study_id: 'alam-ghosh-2013', goals: { mass: 'cost' }, comparisons: expect.any(Array) } });
    fireEvent.click(stepButton('Fabric & fit'));
    await heading('Choose fabric and fit');
    fireEvent.click(screen.getByText('pick-poplin'));
    fireEvent.click(screen.getByRole('button', { name: 'Regenerate pattern' }));
    await heading('Pattern preview');
    expect(patternsAPI.generate.mock.calls[1][0]).not.toHaveProperty('fabric_preferences');
  });

  it('runs customer → upload → AI review → measurements → fabric → pattern → estimate → PDF → feedback', async () => {
    await reachStep4({ contact: 'amara@example.com', project: 'Wedding blouse' });
    expect(imagesAPI.upload).toHaveBeenCalledTimes(1);
    expect(imagesAPI.analyse).toHaveBeenCalledWith('i1');
    expect(imagesAPI.confirmAttributes).toHaveBeenCalledWith('i1', CONFIRMED);
    const saved = measurementsAPI.save.mock.calls[0][0];
    expect(saved).toMatchObject({ unit: 'cm', client_name: 'Test Customer', email: 'amara@example.com', design: CONFIRMED, sleeve_cm: 24 });
    expect(saved).not.toHaveProperty('wrist_cm');          // short sleeve: no wrist
    expect(saved).not.toHaveProperty('height_cm');         // no drafting calculation uses height
    expect(stepButton('Measurements').getAttribute('data-status')).toBe('done');

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
    await waitFor(() => expect(exportAPI.estimates).toHaveBeenCalledWith('p1', { selected_width_cm: 114.3, cutting_mode: 'auto', one_way: false }));
    expect((await screen.findAllByText('1.4 m')).length).toBeGreaterThan(0);
    const table = screen.getByTestId('width-comparison');
    ['36"', '45"', '60"', '91.44 cm', '114.3 cm', '152.4 cm', '1.8 m', '1.1 m'].forEach((t) => expect(table.textContent).toContain(t));
    expect(screen.getByTestId('nesting-layout')).toBeTruthy();
    fireEvent.click(screen.getByTestId('width-60'));
    await waitFor(() => expect(exportAPI.estimates).toHaveBeenLastCalledWith('p1', { selected_width_cm: 152.4, cutting_mode: 'auto', one_way: false }));
    fireEvent.click(screen.getByTestId('one-way'));                    // nap or a directional print: nothing may be turned
    await waitFor(() => expect(exportAPI.estimates).toHaveBeenLastCalledWith('p1', { selected_width_cm: 152.4, cutting_mode: 'auto', one_way: true }));
    expect(screen.getByTestId('estimate-explain').textContent).toMatch(/not automatically the best/);
    await waitFor(() => expect(screen.getByTestId('width-60').textContent).toBe('Selected'));

    fireEvent.click(screen.getByText('Continue to PDF export'));
    await heading('Printable pattern (PDF)');
    // only reduced-scale PDFs are offered: the one-page overview (default) and the full report - no 1:1 pages
    expect(screen.getByTestId('pdf-part-overview').checked).toBe(true);
    expect(screen.queryByTestId('pdf-part-pattern')).toBeNull();
    expect(screen.queryByTestId('pdf-part-all')).toBeNull();
    expect(screen.queryByTestId('tile-preview')).toBeNull();
    expect(screen.getByTestId('pdf-overview-note').textContent).toMatch(/not a real-size cutting template/);
    expect(screen.queryByText(/Actual size/)).toBeNull();
    expect(screen.getByTestId('pdf-contents').textContent).toMatch(/Pattern overview/);
    fireEvent.click(screen.getByText('Create printable PDF'));
    await screen.findByTestId('pdf-ready');
    expect(exportAPI.pdf).toHaveBeenCalledWith('p1', { part: 'overview', unit: 'cm' });
    fireEvent.click(screen.getByTestId('pdf-part-report'));           // another content needs another PDF
    expect(screen.queryByTestId('pdf-ready')).toBeNull();
    fireEvent.click(screen.getByText('Create printable PDF'));
    await screen.findByTestId('pdf-ready');
    expect(exportAPI.pdf).toHaveBeenLastCalledWith('p1', { part: 'report', unit: 'cm' });
    fireEvent.click(screen.getByRole('button', { name: 'Download PDF' }));
    await waitFor(() => expect(exportAPI.download).toHaveBeenCalledWith('e1'));

    await screen.findByLabelText(/How easy was it/);
    fireEvent.click(screen.getByText('Send feedback'));
    await waitFor(() => expect(researchAPI.submitFeedback).toHaveBeenCalledWith(expect.objectContaining({ pattern_id: 'p1' })));
    await screen.findByText(/Thank you/);
  });

  it('opens any step at any time and shows that step\'s real controls, with no invented results', async () => {
    await renderWizard();
    ['Upload image', 'AI review', 'Measurements', 'Fabric & fit', 'Pattern preview', 'Fabric estimate', 'Download PDF'].forEach((label) => {
      expect(stepButton(label).disabled).toBe(false);
      expect(stepButton(label).getAttribute('aria-label')).toMatch(/\(Pending\)/);
    });

    fireEvent.click(stepButton('AI review'));                          // manual feature selection, no photo needed
    expect(screen.getByTestId('fallback-notice')).toBeTruthy();
    ['garment_type', 'neckline_type', 'sleeve_length', 'sleeve_style'].forEach((h) => expect(screen.getByTestId(`select-${h}`).disabled).toBe(false));
    expect(screen.getByText(/Upload a photo for AI suggestions/)).toBeTruthy();

    fireEvent.click(stepButton('Measurements'));                       // design selector + unit toggle + fields
    expect(screen.getByTestId('design-selector')).toBeTruthy();
    expect(screen.getByTestId('unit-toggle')).toBeTruthy();
    expect(document.querySelector('#meas-bust_cm')).toBeTruthy();

    fireEvent.click(stepButton('Fabric & fit'));                       // fit choices + fabric list, recommendations pending
    expect(screen.getByTestId('step-empty').textContent).toMatch(/recommendations pending/i);
    expect(screen.getByTestId('fit-standard').getAttribute('aria-pressed')).toBe('true');
    fireEvent.click(screen.getByTestId('fit-loose'));
    expect(screen.getByTestId('fit-loose').getAttribute('aria-pressed')).toBe('true');
    expect(screen.getByText('pick-poplin')).toBeTruthy();

    fireEvent.click(stepButton('Pattern preview'));                    // frame + what is still needed
    expect(screen.getByTestId('step-empty').textContent).toMatch(/No pattern yet/);
    expect(screen.getByTestId('pattern-placeholder')).toBeTruthy();
    expect([...screen.getByTestId('readiness').querySelectorAll('li')].map((li) => li.dataset.done)).toEqual(['no', 'no', 'no']);
    expect(screen.queryByTestId('pattern-preview')).toBeNull();

    fireEvent.click(stepButton('Fabric estimate'));                    // layout control + the three widths, no numbers
    expect(screen.getByTestId('step-empty').textContent).toMatch(/No current pattern/);
    expect(screen.getByLabelText('Cutting layout').disabled).toBe(false);
    const widths = screen.getByTestId('width-choices');
    ['36" · 91.44 cm', '45" · 114.3 cm', '60" · 152.4 cm'].forEach((t) => expect(widths.textContent).toContain(t));
    fireEvent.click(screen.getByTestId('width-choice-60'));
    expect(screen.getByTestId('width-choice-60').getAttribute('aria-pressed')).toBe('true');
    expect(screen.getByTestId('estimate-results').textContent).not.toMatch(/\d/);     // "Not calculated", never a number
    expect(screen.queryByTestId('width-comparison')).toBeNull();

    fireEvent.click(stepButton('Download PDF'));                       // PDF contents + the create button explains
    expect(screen.getByTestId('step-empty').textContent).toMatch(/No pattern to export yet/);
    expect(screen.getByTestId('pdf-overview-note').textContent).toMatch(/Reduced scale/);   // never real size
    expect(screen.queryByText(/Calibration square/)).toBeNull();
    expect(screen.getByTestId('pdf-placeholder')).toBeTruthy();
    expect(screen.getByTestId('readiness').querySelectorAll('li')).toHaveLength(5);
    fireEvent.click(screen.getByText('Create printable PDF'));
    expect(screen.getByRole('alert').textContent).toMatch(/Generate the pattern first/);

    fireEvent.click(stepButton('Fabric & fit'));                       // the fit chosen earlier is still there
    expect(screen.getByTestId('fit-loose').getAttribute('aria-pressed')).toBe('true');
    fireEvent.click(screen.getByText('Confirm and generate pattern'));
    expect(screen.getByRole('alert').textContent).toMatch(/confirm a supported design/i);

    expect(patternsAPI.generate).not.toHaveBeenCalled();
    expect(exportAPI.estimates).not.toHaveBeenCalled();
    expect(exportAPI.pdf).not.toHaveBeenCalled();
  });

  it('a checklist button takes the user to the step that is still missing', async () => {
    await renderWizard();
    fireEvent.click(stepButton('Pattern preview'));
    fireEvent.click(screen.getByText('Go to measurements'));
    await heading('Body measurements');
    fireEvent.click(stepButton('Pattern preview'));
    fireEvent.click(screen.getByText('Generate pattern'));
    expect(screen.getByRole('alert').textContent).toMatch(/confirm a supported design/i);
    expect(patternsAPI.generate).not.toHaveBeenCalled();
  });

  it('the design can be chosen in the AI review step without a photo and is used for the pattern', async () => {
    await renderWizard();
    fireEvent.change(screen.getByLabelText('Customer name'), { target: { value: 'Test Customer' } });
    fireEvent.click(stepButton('AI review'));
    chooseDesign();
    expect(imagesAPI.confirmAttributes).not.toHaveBeenCalled();        // no photo: nothing to confirm on the server yet
    expect(stepButton('AI review').getAttribute('data-status')).toBe('done');
    expect(stepButton('Upload image').getAttribute('data-status')).toBe('done');
    fireEvent.click(screen.getByText('Continue to measurements'));
    fill();
    fireEvent.click(screen.getByText('Save and continue'));
    await heading('Choose fabric and fit');
    fireEvent.click(screen.getByText('pick-poplin'));
    fireEvent.click(screen.getByText('Confirm and generate pattern'));
    await heading('Pattern preview');
    expect(patternsAPI.generate.mock.calls[0][0]).toMatchObject({ image_id: 'manual', confirmed_attributes: CONFIRMED });
  });

  it('keeps entered data when jumping between steps', async () => {
    await renderWizard();
    fireEvent.change(screen.getByLabelText('Customer name'), { target: { value: 'Nadeesha' } });
    fireEvent.click(stepButton('Download PDF'));
    fireEvent.click(stepButton('Customer & design'));
    expect(screen.getByLabelText('Customer name').value).toBe('Nadeesha');
    expect(stepButton('Customer & design').getAttribute('data-status')).toBe('done');
  });

  it('asks for the customer name when the measurements are saved, not when navigating', async () => {
    await renderWizard();
    fireEvent.click(screen.getByText('Continue to upload'));
    expect(screen.getByTestId('image-input')).toBeTruthy();                   // navigation is not blocked
    fireEvent.click(screen.getByText('Choose the design manually'));
    await heading('Review the AI suggestions');
    chooseDesign();
    fireEvent.click(screen.getByText('Continue to measurements'));
    fill();
    fireEvent.click(screen.getByText('Save and continue'));
    expect(screen.getByRole('alert').textContent).toMatch(/customer name/);
    expect(measurementsAPI.save).not.toHaveBeenCalled();
  });

  it('marks the pattern, estimate and PDF as out of date when a measurement changes', async () => {
    await reachStep4();
    fireEvent.click(screen.getByText('pick-poplin'));
    fireEvent.click(screen.getByText('Confirm and generate pattern'));
    await heading('Pattern preview');
    expect(screen.getByTestId('pattern-preview')).toBeTruthy();
    fireEvent.click(stepButton('Measurements'));
    fireEvent.change(document.querySelector('#meas-bust_cm'), { target: { value: '91.5' } });
    expect(screen.getByTestId('meas-unsaved')).toBeTruthy();
    ['Measurements', 'Pattern preview'].forEach((label) => expect(stepButton(label).getAttribute('data-status')).toBe('stale'));
    fireEvent.click(stepButton('Pattern preview'));
    expect((await screen.findByTestId('step-empty')).textContent).toMatch(/generated again/);
    expect(screen.queryByTestId('pattern-preview')).toBeNull();               // the old pattern is not shown as current
    fireEvent.click(stepButton('Download PDF'));
    expect((await screen.findByTestId('step-empty')).textContent).toMatch(/out of date/);
    fireEvent.click(stepButton('Fabric & fit'));
    fireEvent.click(screen.getByText('Regenerate pattern'));
    expect(screen.getByRole('alert').textContent).toMatch(/save the measurements/i);   // stale values are not drafted
    expect(patternsAPI.generate).toHaveBeenCalledTimes(1);
  });

  it('changing the fabric after generation also requires regeneration', async () => {
    await reachStep4();
    fireEvent.click(screen.getByText('pick-poplin'));
    fireEvent.click(screen.getByText('Confirm and generate pattern'));
    await heading('Pattern preview');
    fireEvent.click(stepButton('Fabric & fit'));
    fireEvent.click(screen.getByTestId('fit-loose'));
    expect(stepButton('Pattern preview').getAttribute('data-status')).toBe('stale');
    expect(screen.getByText('Regenerate pattern')).toBeTruthy();
  });

  it('rejects a non-image or oversized file with a plain message', async () => {
    await startWizard();
    fireEvent.change(screen.getByTestId('image-input'), { target: { files: [new File(['x'], 'a.pdf', { type: 'application/pdf' })] } });
    expect(screen.getByRole('alert').textContent).toMatch(/JPG, PNG or WEBP/);
    expect(imagesAPI.upload).not.toHaveBeenCalled();
  });

  it('says which part of the photo was analysed and flags a garment that cannot be drafted', async () => {
    const region = (r) => ({ data: { confirmed_attributes: {}, garment_attributes: { predictions: {}, garment_region: r } } });
    imagesAPI.analyse.mockResolvedValueOnce(region({ used: 'garment_crop', supported_garment: true, note: null }));
    await startWizard();
    fireEvent.change(screen.getByTestId('image-input'), { target: { files: [new File(['x'], 'a.jpg', { type: 'image/jpeg' })] } });
    fireEvent.click(screen.getByText('Upload and analyse'));
    expect((await screen.findByTestId('garment-region')).textContent).toMatch(/garment area it found/);

    cleanup();
    imagesAPI.analyse.mockResolvedValueOnce(region({ used: 'garment_crop', supported_garment: false,
      note: 'This photo looks like a dress. Only blouses, T-shirts and crop tops can be drafted; the suggestions below may not apply.' }));
    await startWizard();
    fireEvent.change(screen.getByTestId('image-input'), { target: { files: [new File(['x'], 'b.jpg', { type: 'image/jpeg' })] } });
    fireEvent.click(screen.getByText('Upload and analyse'));
    const note = await screen.findByTestId('garment-region');
    expect(note.getAttribute('role')).toBe('alert');
    expect(note.textContent).toMatch(/looks like a dress/);
  });

  it('shows a friendly message (no stack trace) when the AI service fails', async () => {
    imagesAPI.analyse.mockRejectedValue({ response: { status: 500, data: { error: 'Traceback (most recent call last): File "C:\\x\\y.py"' } } });
    await startWizard();
    fireEvent.change(screen.getByTestId('image-input'), { target: { files: [new File(['x'], 'a.jpg', { type: 'image/jpeg' })] } });
    fireEvent.click(screen.getByText('Upload and analyse'));
    const alert = await screen.findByRole('alert');
    expect(alert.textContent).not.toMatch(/Traceback|C:\\/);
    expect(alert.textContent).toMatch(/could not analyse|problem/i);
  });

  it('says honestly when the AI model is unavailable and keeps the manual path open', async () => {
    imagesAPI.modelStatus.mockResolvedValue({ data: { available: false } });
    await startWizard();
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
    await startWizard();
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
    expect(screen.getAllByText(/outline self-intersects/).length).toBeGreaterThan(0);
    fireEvent.click(screen.getByText('Continue to fabric estimate'));
    expect((await screen.findByTestId('step-empty')).textContent).toMatch(/failed its automatic checks/);
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
    fireEvent.click(screen.getByText('Continue to PDF export'));
    expect(screen.getByTestId('pdf-needs').textContent).toMatch(/fabric estimate/);
    fireEvent.click(screen.getByText('Create printable PDF'));                   // no PDF without an estimate
    expect(screen.getAllByRole('alert').some((a) => /Calculate the fabric estimate/.test(a.textContent))).toBe(true);
    expect(exportAPI.pdf).not.toHaveBeenCalled();
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
