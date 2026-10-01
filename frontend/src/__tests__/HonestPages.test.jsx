// Pages that used to show invented values (fake notifications, a default pattern count of "2",
// made-up e-mail addresses, a hard-coded "ONLINE" database status) must now show only real data.
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import Customers from '../pages/Customers';
import Measurements from '../pages/Measurements';
import Settings from '../pages/Settings';
import Navbar from '../components/Navbar';
import Sidebar from '../components/Sidebar';
import PatternDetail from '../pages/PatternDetail';
import { authAPI, measurementsAPI, patternsAPI, imagesAPI } from '../services/api';
import LoginForm from '../components/auth/LoginForm';
import { getPreferences } from '../utils/preferences';

vi.mock('../context/AuthContext', () => ({
  useAuth: () => ({ user: { full_name: 'Test User', email: 'test@example.com' }, logout: vi.fn() }),
}));
vi.mock('../services/api', () => ({
  measurementsAPI: { getAll: vi.fn(), save: vi.fn(), update: vi.fn(), delete: vi.fn() },
  patternsAPI: { getAll: vi.fn(), getOne: vi.fn() },
  exportAPI: { getAll: vi.fn(), download: vi.fn() },
  imagesAPI: { modelStatus: vi.fn() },
  authAPI: { changePassword: vi.fn() },
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
    expect(screen.getByTestId('counts-unavailable').textContent).toMatch(/unknown, not zero/);
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
    patternsAPI.getAll.mockResolvedValue({ data: { patterns: [{ pattern_id: 'p1', garment_type: 'crop-top', yardage_metres: 0.9, generated_at: '2026-09-02T10:00:00',
      exports: [{ export_id: 'e1', exported_at: '2026-09-03T10:00:00' }] }] } });
    render(<MemoryRouter><Navbar /></MemoryRouter>);
    fireEvent.click(screen.getByRole('button', { name: 'Recent activity' }));
    const list = await screen.findByTestId('activity-list');
    await waitFor(() => expect(list.textContent).toMatch(/Crop top pattern generated · 0.9 m fabric/));
    expect(list.textContent).toMatch(/Printable PDF created/);
    expect(document.body.textContent).not.toMatch(/78\.7%|YOLOv8|ReportLab/);
  });

  it('says there is no activity for a new account', async () => {
    patternsAPI.getAll.mockResolvedValue({ data: { patterns: [] } });
    render(<MemoryRouter><Navbar /></MemoryRouter>);
    fireEvent.click(screen.getByRole('button', { name: 'Recent activity' }));
    expect(await screen.findByText(/No activity yet/)).toBeTruthy();
  });

  it('says the activity could not be loaded instead of "no activity"', async () => {
    patternsAPI.getAll.mockRejectedValue(new Error('down'));
    render(<MemoryRouter><Navbar /></MemoryRouter>);
    fireEvent.click(screen.getByRole('button', { name: 'Recent activity' }));
    expect(await screen.findByText(/could not be loaded/)).toBeTruthy();
    expect(screen.queryByText(/No activity yet/)).toBeNull();
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
    expect(document.querySelectorAll('input[id^="profile-"][inputmode="decimal"]').length).toBe(13);
    expect(document.querySelectorAll('input[type="number"]').length).toBe(0);      // number inputs silently drop "," and accept "1e2"
    fireEvent.focus(screen.getByLabelText(/Shoulder length \(cm\)/));
    expect(screen.getByTestId('measure-guide').textContent).toMatch(/\(neck point\) to the shoulder tip/);
    expect(document.body.textContent).not.toMatch(/Accepted range|plausible range|All 13 measurements/);
    expect(screen.getByLabelText(/^1\. Bust \(cm\)/)).toHaveValue('88');
  });

  it('keeps exactly what is typed, reports a mistyped value beside its field and keeps the other inputs', async () => {
    measurementsAPI.getAll.mockResolvedValue({ data: { measurements: [PROFILE] } });
    render(<MemoryRouter><Measurements /></MemoryRouter>);
    const bust = await screen.findByLabelText(/^1\. Bust \(cm\)/);
    for (const text of ['12.', '0.5', '.5', '88.50', '90,5']) {
      fireEvent.change(bust, { target: { value: text } });
      expect(bust).toHaveValue(text);                                       // never rewritten while typing
    }
    fireEvent.change(bust, { target: { value: '1e2' } });
    fireEvent.change(screen.getByLabelText(/^2\. Waist \(cm\)/), { target: { value: '71.25' } });
    fireEvent.click(screen.getByText('Save measurements'));
    expect((await screen.findByTestId('profile-error-bust_cm')).textContent).toMatch(/not a number/);
    expect(measurementsAPI.update).not.toHaveBeenCalled();
    expect(bust).toHaveValue('1e2');                                         // the wrong value stays for the user to fix
    expect(screen.getByLabelText(/^2\. Waist \(cm\)/)).toHaveValue('71.25');  // other inputs are kept
  });

  it('a decimal comma means a decimal point; nothing is multiplied by ten', async () => {
    measurementsAPI.getAll.mockResolvedValue({ data: { measurements: [PROFILE] } });
    measurementsAPI.update.mockResolvedValue({ data: {} });
    render(<MemoryRouter><Measurements /></MemoryRouter>);
    fireEvent.change(await screen.findByLabelText(/^1\. Bust \(cm\)/), { target: { value: '90,5' } });
    fireEvent.click(screen.getByText('Save measurements'));
    await waitFor(() => expect(measurementsAPI.update).toHaveBeenCalled());
    expect(measurementsAPI.update.mock.calls[0][1].bust_cm).toBe(90.5);
  });

  it('re-opening a profile shows each value as it was entered and saving again does not rewrite it', async () => {
    const inches = { ...PROFILE, bust_cm: 84.58200000000001, original_values: { bust_cm: { value: 33.3, unit: 'in' } } };
    measurementsAPI.getAll.mockResolvedValue({ data: { measurements: [inches] } });
    measurementsAPI.update.mockResolvedValue({ data: {} });
    render(<MemoryRouter><Measurements /></MemoryRouter>);
    expect(await screen.findByLabelText(/^1\. Bust \(cm\)/)).toHaveValue('84.58');      // shown in cm, no float noise
    fireEvent.click(screen.getByTestId('page-unit-in'));
    expect(screen.getByLabelText(/^1\. Bust \(in\)/)).toHaveValue('33.3');             // exactly as entered
    fireEvent.click(screen.getByText('Save measurements'));
    await waitFor(() => expect(measurementsAPI.update).toHaveBeenCalled());
    const body = measurementsAPI.update.mock.calls[0][1];
    expect(body.bust_cm).toBe(33.3);
    expect(body.units.bust_cm).toBe('in');
    expect(body).toMatchObject({ waist_cm: 70 });
    expect(body.units.waist_cm).toBe('cm');
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
    expect(screen.getByLabelText(/^1\. Bust \(in\)/)).toHaveValue('34.65');        // 88 cm shown in inches
    fireEvent.change(screen.getByLabelText(/^2\. Waist \(in\)/), { target: { value: '27.5' } });
    fireEvent.click(screen.getByText('Save measurements'));
    await waitFor(() => expect(measurementsAPI.update).toHaveBeenCalled());
    const body = measurementsAPI.update.mock.calls[0][1];
    expect(body).toMatchObject({ bust_cm: 88, waist_cm: 27.5 });                       // stored cm not rewritten
    expect(body.units).toMatchObject({ bust_cm: 'cm', waist_cm: 'in' });
  });
});

describe('Passwords', () => {
  const fillPw = (current, next, again = next) => {
    fireEvent.change(screen.getByLabelText('Current password'), { target: { value: current } });
    fireEvent.change(screen.getByLabelText('New password'), { target: { value: next } });
    fireEvent.change(screen.getByLabelText('New password again'), { target: { value: again } });
    fireEvent.click(screen.getByRole('button', { name: 'Change password' }));
  };

  it('checks the new password before calling the server', async () => {
    imagesAPI.modelStatus.mockResolvedValue({ data: { available: true } });
    render(<Settings />);
    fillPw('old-password-1', 'short');
    expect(screen.getByTestId('password-error').textContent).toMatch(/at least 8 characters/);
    fillPw('old-password-1', 'new-password-2', 'new-password-3');
    expect(screen.getByTestId('password-error').textContent).toMatch(/not the same/);
    expect(authAPI.changePassword).not.toHaveBeenCalled();
  });

  it('changes the password with the current one and clears the fields', async () => {
    imagesAPI.modelStatus.mockResolvedValue({ data: { available: true } });
    authAPI.changePassword.mockResolvedValue({ data: { message: 'Password changed.' } });
    render(<Settings />);
    fillPw('old-password-1', 'new-password-2');
    expect((await screen.findByTestId('password-done')).textContent).toMatch(/Password changed/);
    expect(authAPI.changePassword).toHaveBeenCalledWith({ current_password: 'old-password-1', new_password: 'new-password-2' });
    expect(screen.getByLabelText('Current password')).toHaveValue('');
    expect(screen.getByLabelText('New password')).toHaveValue('');
  });

  it('shows the reason from the server when the current password is wrong', async () => {
    imagesAPI.modelStatus.mockResolvedValue({ data: { available: true } });
    authAPI.changePassword.mockRejectedValue({ response: { status: 400, data: { error: 'The current password is not correct.', error_code: 'CURRENT_PASSWORD_WRONG' } } });
    render(<Settings />);
    fillPw('wrong-password', 'new-password-2');
    expect((await screen.findByTestId('password-error')).textContent).toMatch(/current password is not correct/);
    expect(screen.queryByTestId('password-done')).toBeNull();
  });

  it('says honestly that there is no reset e-mail', () => {
    render(<MemoryRouter><LoginForm onSubmit={() => {}} onSwitchTab={() => {}} /></MemoryRouter>);
    fireEvent.click(screen.getByRole('button', { name: 'Forgot password?' }));
    const note = screen.getByRole('status').textContent;
    expect(note).toMatch(/no e-mail service/);
    expect(note).toMatch(/Settings/);
    expect(note).not.toMatch(/link has been sent|check your inbox/i);
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
