// Pages that used to show invented values (fake notifications, a default pattern count of "2",
// made-up e-mail addresses, a hard-coded "ONLINE" database status) must now show only real data.
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import React from 'react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import Customers from '../pages/Customers';
import Measurements from '../pages/Measurements';
import Settings from '../pages/Settings';
import Navbar from '../components/Navbar';
import FabricComparison from '../components/FabricComparison';
import ResearcherDashboard from '../pages/ResearcherDashboard';
import { measurementsAPI, patternsAPI, exportAPI, imagesAPI, researchAPI } from '../services/api';
import { getPreferences } from '../utils/preferences';

vi.mock('../context/AuthContext', () => ({
  useAuth: () => ({ user: { full_name: 'Test User', email: 'test@example.com' }, logout: vi.fn() }),
}));
vi.mock('../services/api', () => ({
  measurementsAPI: { getAll: vi.fn(), save: vi.fn(), update: vi.fn(), delete: vi.fn() },
  patternsAPI: { getAll: vi.fn() },
  exportAPI: { getAll: vi.fn() },
  imagesAPI: { modelStatus: vi.fn() },
  researchAPI: {
    getComparisons: vi.fn(), addComparison: vi.fn(), deleteComparison: vi.fn(), getMetrics: vi.fn(),
    getCSVUrl: vi.fn(() => '#'), getComparisonCSVUrl: vi.fn(() => '#'),
  },
}));

const PROFILE = {
  measurement_id: 'm1', client_name: 'Amara Silva', email: null, bust_cm: 88, waist_cm: 70, hip_cm: 94, height_cm: 162,
  fabric_type: 'woven', created_at: '2026-09-01 10:00:00', complete: false,
};

beforeEach(() => {
  vi.clearAllMocks();
  window.localStorage.clear();
});

describe('Customers', () => {
  it('shows the real pattern count per customer and no invented e-mail', async () => {
    measurementsAPI.getAll.mockResolvedValue({ data: { measurements: [PROFILE, { ...PROFILE, measurement_id: 'm2', client_name: 'Nimali' }] } });
    patternsAPI.getAll.mockResolvedValue({ data: { patterns: [
      { pattern_id: 'p1', measurement_id: 'm1' }, { pattern_id: 'p2', measurement_id: 'm1' }, { pattern_id: 'p3', measurement_id: null },
    ] } });
    render(<MemoryRouter><Customers /></MemoryRouter>);
    expect(await screen.findByTestId('pattern-count-m1')).toHaveTextContent('2');
    expect(screen.getByTestId('pattern-count-m2')).toHaveTextContent('0');
    expect(document.body.textContent).not.toMatch(/@email\.com/);
    expect(screen.getAllByText('No e-mail recorded').length).toBeGreaterThan(0);
  });

  it('shows a dash, not a number, when the pattern count cannot be loaded', async () => {
    measurementsAPI.getAll.mockResolvedValue({ data: { measurements: [PROFILE] } });
    patternsAPI.getAll.mockRejectedValue(new Error('down'));
    render(<MemoryRouter><Customers /></MemoryRouter>);
    expect(await screen.findByTestId('pattern-count-m1')).toHaveTextContent('—');
  });

  it('reports a load failure instead of an empty customer list', async () => {
    measurementsAPI.getAll.mockRejectedValue(new Error('down'));
    patternsAPI.getAll.mockResolvedValue({ data: { patterns: [] } });
    render(<MemoryRouter><Customers /></MemoryRouter>);
    expect((await screen.findByRole('alert')).textContent).toMatch(/Failed to load/);
    expect(screen.queryByText(/No customer profiles found/)).toBeNull();
  });

  it('adds a customer with the core measurements and sends no invented e-mail or notes', async () => {
    measurementsAPI.getAll.mockResolvedValue({ data: { measurements: [] } });
    patternsAPI.getAll.mockResolvedValue({ data: { patterns: [] } });
    measurementsAPI.save.mockResolvedValue({ data: { measurement_id: 'new' } });
    render(<MemoryRouter><Customers /></MemoryRouter>);
    fireEvent.click(await screen.findByText('Add customer'));
    fireEvent.change(screen.getByLabelText('Full Name'), { target: { value: 'Kavindi' } });
    fireEvent.click(screen.getByText('Save Customer'));
    expect((await screen.findByTestId('customer-form-error')).textContent).toMatch(/Bust: Bust is required/);
    expect(measurementsAPI.save).not.toHaveBeenCalled();
    for (const [id, v] of [['bust_cm', 90], ['waist_cm', 72], ['hip_cm', 96], ['height_cm', 160]]) {
      fireEvent.change(screen.getByLabelText(new RegExp(`^${{ bust_cm: 'Bust', waist_cm: 'Waist', hip_cm: 'Hip', height_cm: 'Height' }[id]} \\(cm\\)`)), { target: { value: String(v) } });
    }
    fireEvent.click(screen.getByText('Save Customer'));
    await waitFor(() => expect(measurementsAPI.save).toHaveBeenCalled());
    const body = measurementsAPI.save.mock.calls[0][0];
    expect(body).toMatchObject({ client_name: 'Kavindi', bust_cm: 90, waist_cm: 72, hip_cm: 96, height_cm: 160, unit: 'cm' });
    expect(body).not.toHaveProperty('email');
    expect(body).not.toHaveProperty('notes');
  });
});

describe('Recent activity (header)', () => {
  it('lists only the user’s real patterns and PDFs', async () => {
    patternsAPI.getAll.mockResolvedValue({ data: { patterns: [{ pattern_id: 'p1', garment_type: 'crop-top', yardage_metres: 0.9, generated_at: '2026-09-02T10:00:00' }] } });
    exportAPI.getAll.mockResolvedValue({ data: { exports: [{ export_id: 'e1', exported_at: '2026-09-03T10:00:00' }] } });
    render(<MemoryRouter><Navbar /></MemoryRouter>);
    fireEvent.click(screen.getByRole('button', { name: 'Recent activity' }));
    const list = await screen.findByTestId('activity-list');
    await waitFor(() => expect(list.textContent).toMatch(/Crop top pattern generated · 0.9 m fabric/));
    expect(list.textContent).toMatch(/Printable PDF created/);
    expect(document.body.textContent).not.toMatch(/78\.7%|YOLOv8|ReportLab/);
  });

  it('says there is no activity for a new account', async () => {
    patternsAPI.getAll.mockResolvedValue({ data: { patterns: [] } });
    exportAPI.getAll.mockResolvedValue({ data: { exports: [] } });
    render(<MemoryRouter><Navbar /></MemoryRouter>);
    fireEvent.click(screen.getByRole('button', { name: 'Recent activity' }));
    expect(await screen.findByText(/No activity yet/)).toBeTruthy();
  });
});

describe('Settings', () => {
  it('shows no invented server status and reports the real model state', async () => {
    imagesAPI.modelStatus.mockResolvedValue({ data: { available: false } });
    render(<Settings />);
    await waitFor(() => expect(screen.getByTestId('model-state').textContent).toMatch(/Not available on this server/));
    expect(document.body.textContent).not.toMatch(/ONLINE & CONNECTED|localhost:27017|digital_tailor_db/);
    expect(screen.getByText('1.5 cm')).toBeTruthy();       // engine allowance, shown read-only
  });

  it('saves the defaults the wizard really uses', async () => {
    imagesAPI.modelStatus.mockResolvedValue({ data: { available: true, checkpoint_sha256: 'abcdef0123456789ffff' } });
    render(<Settings />);
    fireEvent.click(screen.getByRole('button', { name: 'Inches (in)' }));
    fireEvent.change(screen.getByLabelText(/Fabric width for the first estimate/), { target: { value: '150' } });
    fireEvent.click(screen.getByText('Save preferences'));
    expect(getPreferences()).toEqual({ unit: 'in', fabricWidth: 150 });
    expect(await screen.findByText(/abcdef0123456789…/)).toBeTruthy();
  });
});

describe('Measurements page', () => {
  it('uses the schema labels (shoulder LENGTH), all 13 fields and the real ranges', async () => {
    measurementsAPI.getAll.mockResolvedValue({ data: { measurements: [PROFILE] } });
    render(<MemoryRouter><Measurements /></MemoryRouter>);
    expect(await screen.findByLabelText(/Shoulder length \(cm\)/)).toBeTruthy();
    expect(screen.queryByText(/Shoulder width/)).toBeNull();
    expect(document.querySelectorAll('input[id^="profile-"][type="number"]').length).toBe(13);
    fireEvent.focus(screen.getByLabelText(/Shoulder length \(cm\)/));
    expect(screen.getByTestId('measure-guide').textContent).toMatch(/\(neck point\) to the shoulder tip.*8–20 cm/s);
    expect(screen.getByLabelText(/^1\. Bust \(cm\)/)).toHaveValue(88);
  });

  it('shows the server’s field error next to the field', async () => {
    measurementsAPI.getAll.mockResolvedValue({ data: { measurements: [PROFILE] } });
    measurementsAPI.update.mockRejectedValue({ response: { status: 400, data: { field_errors: { waist_cm: [{ message: 'Waist cannot exceed bust by that much.' }] } } } });
    render(<MemoryRouter><Measurements /></MemoryRouter>);
    fireEvent.click(await screen.findByText('Save measurements'));
    expect((await screen.findByTestId('profile-error-waist_cm')).textContent).toMatch(/cannot exceed/);
  });

  it('converts units exactly and saves in the unit the user sees', async () => {
    measurementsAPI.getAll.mockResolvedValue({ data: { measurements: [PROFILE] } });
    measurementsAPI.update.mockResolvedValue({ data: {} });
    render(<MemoryRouter><Measurements /></MemoryRouter>);
    fireEvent.click(await screen.findByTestId('page-unit-in'));
    expect(screen.getByLabelText(/^1\. Bust \(in\)/)).toHaveValue(34.65);
    fireEvent.click(screen.getByText('Save measurements'));
    await waitFor(() => expect(measurementsAPI.update).toHaveBeenCalled());
    expect(measurementsAPI.update.mock.calls[0][1]).toMatchObject({ unit: 'in', bust_cm: 34.65 });
  });
});

describe('Traditional vs system fabric comparison', () => {
  it('saves a comparison with only the entered values and shows the server-computed difference', async () => {
    researchAPI.getComparisons.mockResolvedValueOnce({ data: { comparisons: [] } });
    researchAPI.addComparison.mockResolvedValue({ data: {} });
    researchAPI.getComparisons.mockResolvedValueOnce({ data: { comparisons: [{
      comparison_id: 'c1', fabric_width_cm: 114, traditional_estimate_m: 2, system_purchase_m: 1.4,
      system_layout_length_cm: 120, system_cutting_mode: 'folded', difference_m: 0.6, relative_difference_percent: 30,
      estimate_source: 'tailor', estimator_label: 'Tailor A',
    }] } });
    render(<FabricComparison patternId="p1" defaultWidth={114} />);
    await screen.findByText(/No comparison recorded/);
    fireEvent.click(screen.getByText('Save comparison'));
    expect((await screen.findByRole('alert')).textContent).toMatch(/traditional estimate in metres/);
    fireEvent.change(screen.getByLabelText('Traditional estimate (m)'), { target: { value: '2' } });
    fireEvent.change(screen.getByLabelText(/Estimator label/), { target: { value: 'Tailor A' } });
    fireEvent.click(screen.getByText('Save comparison'));
    await waitFor(() => expect(researchAPI.addComparison).toHaveBeenCalledWith({
      pattern_id: 'p1', fabric_width_cm: 114, cutting_mode: 'auto', traditional_estimate_m: 2,
      estimate_source: 'tailor', estimator_label: 'Tailor A', notes: undefined,
    }));
    const table = await screen.findByTestId('comparison-table');
    expect(table.textContent).toMatch(/\+0\.6 m/);
    expect(table.textContent).toMatch(/1\.4 m/);
  });
});

describe('Researcher dashboard: fabric comparison summary', () => {
  const base = { available: true, total_participants: 0, total_patterns: 0, model_evaluation: { available: false },
    avg_correction_rate: null, avg_fabric_savings: null, avg_processing_time: null, usability_score: null, feedbacks: [] };

  it('says "Not measured" when no comparison exists', async () => {
    researchAPI.getMetrics.mockResolvedValue({ data: { ...base, fabric_comparison: null } });
    render(<ResearcherDashboard />);
    expect((await screen.findByTestId('fabric-comparison-summary')).textContent).toMatch(/Not measured — no traditional estimate/);
  });

  it('shows the real summary when comparisons exist', async () => {
    researchAPI.getMetrics.mockResolvedValue({ data: { ...base, fabric_comparison: {
      n: 3, patterns: 2, mean_difference_m: 0.1, median_difference_m: 0, sd_difference_m: 0.36,
      mean_relative_difference_percent: 1.7, system_lower_count: 1, system_higher_count: 1, equal_count: 1,
      definition: 'difference = traditional estimate - system recommended purchase, same fabric width', note: 'Descriptive only.',
    } } });
    render(<ResearcherDashboard />);
    const card = await screen.findByTestId('fabric-comparison-summary');
    expect(card.textContent).toMatch(/3 \(2\)/);
    expect(card.textContent).toMatch(/0\.100 m/);
    expect(card.textContent).toMatch(/1 \/ 1 \/ 1/);
  });

  it('shows only the access message (no "no data" card) to a non-researcher', async () => {
    researchAPI.getMetrics.mockRejectedValue({ response: { status: 403 } });
    render(<ResearcherDashboard />);
    expect((await screen.findByRole('alert')).textContent).toMatch(/only available to researcher accounts/);
    expect(screen.queryByText('No research data available')).toBeNull();
  });
});
