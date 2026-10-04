// Pages that used to show invented values (fake notifications, a default pattern count of "2",
// made-up e-mail addresses, a hard-coded "ONLINE" database status) must now show only real data.
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
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

  it('adds a customer with profile details only and requires a name', async () => {
    measurementsAPI.getAll.mockResolvedValue({ data: { measurements: [] } });
    patternsAPI.getAll.mockResolvedValue({ data: { patterns: [] } });
    measurementsAPI.save.mockResolvedValue({ data: { measurement_id: 'new' } });
    render(<MemoryRouter><Customers /></MemoryRouter>);
    fireEvent.click(await screen.findByText('Add customer'));
    expect(screen.queryByRole('spinbutton')).toBeNull();
    expect(screen.queryByText(/The other drafting measurements/)).toBeNull();
    fireEvent.click(screen.getByText('Save Customer'));
    expect((await screen.findByTestId('customer-form-error')).textContent).toMatch(/Please enter the customer name/);
    expect(measurementsAPI.save).not.toHaveBeenCalled();
    fireEvent.change(screen.getByLabelText('Full Name'), { target: { value: '  Kavindi  ' } });
    fireEvent.click(screen.getByText('Save Customer'));
    await waitFor(() => expect(measurementsAPI.save).toHaveBeenCalled());
    expect(measurementsAPI.save).toHaveBeenCalledWith({ client_name: 'Kavindi' });
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
  it.each(['create', 'update'])('clears all inputs after a successful %s and saves the next customer as a new profile', async (mode) => {
    measurementsAPI.getAll.mockResolvedValue({ data: { measurements: [PROFILE] } })
      .mockResolvedValueOnce({ data: { measurements: mode === 'update' ? [PROFILE] : [] } });
    measurementsAPI.save.mockResolvedValue({ data: { measurement_id: 'next' } });
    let finishSave;
    const pendingSave = new Promise((resolve) => { finishSave = resolve; });
    const saveMethod = mode === 'update' ? measurementsAPI.update : measurementsAPI.save;
    saveMethod.mockReturnValueOnce(pendingSave);
    render(<MemoryRouter><Measurements /></MemoryRouter>);

    const name = await screen.findByLabelText('Customer name');
    fireEvent.change(name, { target: { value: 'First customer' } });
    fireEvent.click(screen.getByTestId('page-unit-in'));
    const fields = [...document.querySelectorAll('input[id^="profile-"][inputmode="decimal"]')];
    expect(fields).toHaveLength(16);
    fields.forEach((field) => fireEvent.change(field, { target: { value: '12.5' } }));
    fireEvent.change(screen.getByLabelText('Usual fabric construction'), { target: { value: 'knit' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save measurements' }));

    expect(saveMethod).toHaveBeenCalledTimes(1);
    expect(name).toHaveValue('First customer');
    fields.forEach((field) => expect(field).toHaveValue('12.5')); // kept until the save succeeds
    expect(screen.queryByText('Customer saved successfully.')).toBeNull();

    await act(async () => finishSave({ data: { measurement_id: 'm1', warnings: [{ field: 'bust_cm', message: 'Check this saved value.' }] } }));
    expect(screen.getByRole('status')).toHaveTextContent('Customer saved successfully.');
    expect(name).toHaveValue('');
    fields.forEach((field) => expect(field).toHaveValue(''));
    expect(screen.getByLabelText('Profile')).toHaveValue('');
    expect(screen.getByLabelText('Usual fabric construction')).toHaveValue('woven');
    expect(screen.getByTestId('page-unit-cm')).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByRole('option', { name: 'Amara Silva' })).toBeTruthy();

    fireEvent.change(name, { target: { value: 'Next customer' } });
    expect(screen.queryByText('Customer saved successfully.')).toBeNull();
    fireEvent.change(screen.getByLabelText(/^Bust around \(cm\)/), { target: { value: '91' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save measurements' }));
    await waitFor(() => expect(measurementsAPI.save).toHaveBeenCalledTimes(mode === 'create' ? 2 : 1));
    const nextPayload = measurementsAPI.save.mock.calls.at(-1)[0];
    expect(nextPayload).toMatchObject({ client_name: 'Next customer', bust_cm: 91, units: { bust_cm: 'cm' } });
    expect(nextPayload.waist_cm).toBeUndefined();
    expect(measurementsAPI.update).toHaveBeenCalledTimes(mode === 'update' ? 1 : 0);
    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('Customer saved successfully.'));
  });

  it('still clears the form and confirms a successful save if refreshing the profile list fails', async () => {
    measurementsAPI.getAll.mockRejectedValue(new Error('refresh unavailable'))
      .mockResolvedValueOnce({ data: { measurements: [] } });
    measurementsAPI.save.mockResolvedValue({ data: { measurement_id: 'new' } });
    render(<MemoryRouter><Measurements /></MemoryRouter>);
    fireEvent.change(await screen.findByLabelText('Customer name'), { target: { value: 'Kavindi' } });
    fireEvent.change(screen.getByLabelText(/^Bust around \(cm\)/), { target: { value: '88' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save measurements' }));
    expect(await screen.findByRole('status')).toHaveTextContent('Customer saved successfully.');
    await waitFor(() => expect(measurementsAPI.getAll).toHaveBeenCalledTimes(2));
    expect(screen.getByLabelText('Customer name')).toHaveValue('');
    expect(screen.getByLabelText(/^Bust around \(cm\)/)).toHaveValue('');
    expect(screen.queryByRole('alert')).toBeNull();
  });

  it('uses the schema labels, all 16 optional fields, a front/back guide and no rejecting ranges', async () => {
    measurementsAPI.getAll.mockResolvedValue({ data: { measurements: [PROFILE] } });
    render(<MemoryRouter><Measurements /></MemoryRouter>);
    expect(await screen.findByLabelText(/^Shoulder to shoulder \(cm\)/)).toBeTruthy();
    expect(screen.queryByLabelText(/Neck around|Height|Wrist/)).toBeNull();      // no longer asked for
    expect(document.querySelectorAll('input[id^="profile-"][inputmode="decimal"]').length).toBe(16);
    expect(document.querySelectorAll('input[type="number"]').length).toBe(0);      // number inputs silently drop "," and accept "1e2"
    fireEvent.focus(screen.getByLabelText(/^Shoulder to shoulder \(cm\)/));
    expect(screen.getByTestId('measure-guide').textContent).toMatch(/tip of one shoulder to the tip of the other/);
    expect(screen.getByTestId('measure-guide').textContent).toMatch(/Common mistake/);
    expect(screen.getByTestId('measure-figure').getAttribute('data-active-view')).toBe('back');
    expect(document.body.textContent).not.toMatch(/Accepted range|plausible range|All 13 measurements/);
    expect(screen.getByLabelText(/^Bust around \(cm\)/)).toHaveValue('88');
  });

  it('keeps exactly what is typed, reports a mistyped value beside its field and keeps the other inputs', async () => {
    measurementsAPI.getAll.mockResolvedValue({ data: { measurements: [PROFILE] } });
    render(<MemoryRouter><Measurements /></MemoryRouter>);
    const bust = await screen.findByLabelText(/^Bust around \(cm\)/);
    for (const text of ['12.', '0.5', '.5', '88.50', '90,5']) {
      fireEvent.change(bust, { target: { value: text } });
      expect(bust).toHaveValue(text);                                       // never rewritten while typing
    }
    fireEvent.change(bust, { target: { value: '1e2' } });
    fireEvent.change(screen.getByLabelText(/^Waist around \(cm\)/), { target: { value: '71.25' } });
    fireEvent.click(screen.getByText('Save measurements'));
    expect((await screen.findByTestId('profile-error-bust_cm')).textContent).toMatch(/not a number/);
    expect(measurementsAPI.update).not.toHaveBeenCalled();
    expect(bust).toHaveValue('1e2');                                         // the wrong value stays for the user to fix
    expect(screen.getByLabelText(/^Waist around \(cm\)/)).toHaveValue('71.25');  // other inputs are kept
  });

  it('a decimal comma means a decimal point; nothing is multiplied by ten', async () => {
    measurementsAPI.getAll.mockResolvedValue({ data: { measurements: [PROFILE] } });
    measurementsAPI.update.mockResolvedValue({ data: {} });
    render(<MemoryRouter><Measurements /></MemoryRouter>);
    fireEvent.change(await screen.findByLabelText(/^Bust around \(cm\)/), { target: { value: '90,5' } });
    fireEvent.click(screen.getByText('Save measurements'));
    await waitFor(() => expect(measurementsAPI.update).toHaveBeenCalled());
    expect(measurementsAPI.update.mock.calls[0][1].bust_cm).toBe(90.5);
  });

  it('re-opening a profile shows each value as it was entered and saving again does not rewrite it', async () => {
    const inches = { ...PROFILE, bust_cm: 84.58200000000001, original_values: { bust_cm: { value: 33.3, unit: 'in' } } };
    measurementsAPI.getAll.mockResolvedValue({ data: { measurements: [inches] } });
    measurementsAPI.update.mockResolvedValue({ data: {} });
    render(<MemoryRouter><Measurements /></MemoryRouter>);
    expect(await screen.findByLabelText(/^Bust around \(cm\)/)).toHaveValue('84.58');      // shown in cm, no float noise
    fireEvent.click(screen.getByTestId('page-unit-in'));
    expect(screen.getByLabelText(/^Bust around \(in\)/)).toHaveValue('33.3');             // exactly as entered
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
    expect(screen.getByLabelText('Customer name')).toHaveValue('Amara Silva');
    expect(screen.getByLabelText('Profile')).toHaveValue('m1');
    expect(screen.getByLabelText(/^Bust around \(cm\)/)).toHaveValue('88');
    expect(screen.getByLabelText(/^Waist around \(cm\)/)).toHaveValue('70');
    expect(screen.queryByText('Customer saved successfully.')).toBeNull();
  });

  it('switching the unit only changes the display; typed values are saved with their own unit', async () => {
    measurementsAPI.getAll.mockResolvedValue({ data: { measurements: [PROFILE] } });
    measurementsAPI.update.mockResolvedValue({ data: {} });
    render(<MemoryRouter><Measurements /></MemoryRouter>);
    fireEvent.click(await screen.findByTestId('page-unit-in'));
    expect(screen.getByLabelText(/^Bust around \(in\)/)).toHaveValue('34.65');        // 88 cm shown in inches
    fireEvent.change(screen.getByLabelText(/^Waist around \(in\)/), { target: { value: '27.5' } });
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
