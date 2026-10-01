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
import Sidebar from '../components/Sidebar';
import PatternDetail from '../pages/PatternDetail';
import { measurementsAPI, patternsAPI, exportAPI, imagesAPI } from '../services/api';
import { getPreferences } from '../utils/preferences';

vi.mock('../context/AuthContext', () => ({
  useAuth: () => ({ user: { full_name: 'Test User', email: 'test@example.com' }, logout: vi.fn() }),
}));
vi.mock('../services/api', () => ({
  measurementsAPI: { getAll: vi.fn(), save: vi.fn(), update: vi.fn(), delete: vi.fn() },
  patternsAPI: { getAll: vi.fn(), getOne: vi.fn() },
  exportAPI: { getAll: vi.fn(), download: vi.fn() },
  imagesAPI: { modelStatus: vi.fn() },
  researchAPI: { submitFeedback: vi.fn() },
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

  it('adds a customer: measurements optional but must be positive numbers; nothing invented', async () => {
    measurementsAPI.getAll.mockResolvedValue({ data: { measurements: [] } });
    patternsAPI.getAll.mockResolvedValue({ data: { patterns: [] } });
    measurementsAPI.save.mockResolvedValue({ data: { measurement_id: 'new' } });
    render(<MemoryRouter><Customers /></MemoryRouter>);
    fireEvent.click(await screen.findByText('Add customer'));
    fireEvent.change(screen.getByLabelText('Full Name'), { target: { value: 'Kavindi' } });
    const field = (label) => screen.getByLabelText(new RegExp(`^${label} \\(cm\\)`));
    fireEvent.change(field('Bust'), { target: { value: '-90' } });
    fireEvent.click(screen.getByText('Save Customer'));
    expect((await screen.findByTestId('customer-form-error')).textContent).toMatch(/Bust: Must be greater than 0/);
    expect(measurementsAPI.save).not.toHaveBeenCalled();
    fireEvent.change(field('Bust'), { target: { value: '90.5' } });
    fireEvent.change(field('Waist'), { target: { value: '72' } });
    fireEvent.click(screen.getByText('Save Customer'));
    await waitFor(() => expect(measurementsAPI.save).toHaveBeenCalled());
    const body = measurementsAPI.save.mock.calls[0][0];
    expect(body).toMatchObject({ client_name: 'Kavindi', bust_cm: 90.5, waist_cm: 72, unit: 'cm' });
    expect(body).not.toHaveProperty('hip_cm');          // not entered -> not sent, never defaulted
    expect(body).not.toHaveProperty('height_cm');
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
    fireEvent.change(screen.getByLabelText(/Fabric width for the first estimate/), { target: { value: '152.4' } });
    expect(screen.getByRole('option', { name: '60" (152.4 cm)' })).toBeTruthy();
    fireEvent.click(screen.getByText('Save preferences'));
    expect(getPreferences()).toEqual({ unit: 'in', fabricWidth: 152.4 });
    expect(await screen.findByText(/abcdef0123456789…/)).toBeTruthy();
  });
});

describe('Measurements page', () => {
  it('uses the schema labels (shoulder LENGTH), all 13 optional fields and no plausibility ranges', async () => {
    measurementsAPI.getAll.mockResolvedValue({ data: { measurements: [PROFILE] } });
    render(<MemoryRouter><Measurements /></MemoryRouter>);
    expect(await screen.findByLabelText(/Shoulder length \(cm\)/)).toBeTruthy();
    expect(screen.queryByText(/Shoulder width/)).toBeNull();
    expect(document.querySelectorAll('input[id^="profile-"][type="number"]').length).toBe(13);
    fireEvent.focus(screen.getByLabelText(/Shoulder length \(cm\)/));
    expect(screen.getByTestId('measure-guide').textContent).toMatch(/\(neck point\) to the shoulder tip/);
    expect(document.body.textContent).not.toMatch(/Accepted range|plausible range|All 13 measurements/);
    expect(screen.getByLabelText(/^1\. Bust \(cm\)/)).toHaveValue(88);
  });

  it('shows the server’s field error next to the field', async () => {
    measurementsAPI.getAll.mockResolvedValue({ data: { measurements: [PROFILE] } });
    measurementsAPI.update.mockRejectedValue({ response: { status: 400, data: { field_errors: { waist_cm: [{ message: 'Waist cannot exceed bust by that much.' }] } } } });
    render(<MemoryRouter><Measurements /></MemoryRouter>);
    fireEvent.click(await screen.findByText('Save measurements'));
    expect((await screen.findByTestId('profile-error-waist_cm')).textContent).toMatch(/cannot exceed/);
  });

  it('switching the unit only changes the display; typed values are saved with their own unit', async () => {
    measurementsAPI.getAll.mockResolvedValue({ data: { measurements: [PROFILE] } });
    measurementsAPI.update.mockResolvedValue({ data: {} });
    render(<MemoryRouter><Measurements /></MemoryRouter>);
    fireEvent.click(await screen.findByTestId('page-unit-in'));
    expect(screen.getByLabelText(/^1\. Bust \(in\)/)).toHaveValue(34.65);          // 88 cm shown in inches
    fireEvent.change(screen.getByLabelText(/^2\. Waist \(in\)/), { target: { value: '27.5' } });
    fireEvent.click(screen.getByText('Save measurements'));
    await waitFor(() => expect(measurementsAPI.update).toHaveBeenCalled());
    const body = measurementsAPI.update.mock.calls[0][1];
    expect(body).toMatchObject({ bust_cm: 88, waist_cm: 27.5 });                       // stored cm not rewritten
    expect(body.units).toMatchObject({ bust_cm: 'cm', waist_cm: 'in' });
  });
});

describe('Customer workflow has no research features', () => {
  it('the navigation has no Research Metrics entry', () => {
    render(<MemoryRouter><Sidebar /></MemoryRouter>);
    expect(screen.queryByText(/Research(er)? Metrics/i)).toBeNull();
    expect(document.querySelector('a[href="/researcher"]')).toBeNull();
  });

  it('a saved pattern has no tailor-estimate input or comparison', async () => {
    patternsAPI.getOne.mockResolvedValue({ data: {
      pattern_id: 'p1', garment_type: 'blouse', design_attributes: {}, selected_fabric_name: 'Cotton Poplin',
      nesting_summary: {}, pattern_pieces: [], validation: { passed: true }, validation_passed: true, exports: [],
    } });
    render(<MemoryRouter initialEntries={['/patterns/p1']}><PatternDetail /></MemoryRouter>);
    await screen.findByText(/Blouse pattern/);
    expect(document.body.textContent).not.toMatch(/traditional|tailor.?s estimate|comparison/i);
  });
});
