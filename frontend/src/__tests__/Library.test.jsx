// The pattern library lists SAVED PATTERNS (the records the dashboard and customers page count), not only PDFs.
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import History from '../pages/History';
import PatternDetail from '../pages/PatternDetail';
import { exportAPI, patternsAPI } from '../services/api';
import { Route, Routes } from 'react-router-dom';

vi.mock('../services/api', () => ({
  patternsAPI: { getAll: vi.fn(), getOne: vi.fn(), delete: vi.fn() },
  exportAPI: { download: vi.fn(), delete: vi.fn(), pdf: vi.fn() },
}));

const WITH_PDF = {
  pattern_id: 'p1', garment_type: 'blouse', neckline_type: 'v-neck', sleeve_length: 'short-sleeve', customer_name: 'Amara Silva',
  selected_fabric_name: 'Cotton Poplin', yardage_metres: 1.4, generated_at: '2026-09-30T10:00:00', validation_passed: true,
  nesting_summary: { fabric_width_cm: 114.3, utilisation_percent: 61.2 },
  exports: [{ export_id: 'e2', file_available: true }, { export_id: 'e1', file_available: true }],
};
const NO_PDF = {
  pattern_id: 'p2', garment_type: 't-shirt', customer_name: null, yardage_metres: 0, generated_at: '2026-09-29T10:00:00',
  validation_passed: true, nesting_summary: {}, exports: [],
};
const list = (...patterns) => ({ data: { patterns } });
const renderLibrary = () => render(<MemoryRouter><History /></MemoryRouter>);

beforeEach(() => {
  vi.clearAllMocks();
  vi.spyOn(window, 'confirm').mockReturnValue(true);
});

describe('Pattern library', () => {
  it('lists a saved pattern that has no PDF yet as "PDF pending" instead of hiding it', async () => {
    patternsAPI.getAll.mockResolvedValue(list(WITH_PDF, NO_PDF));
    renderLibrary();
    expect(await screen.findByTestId('pdf-status-p1')).toHaveTextContent('PDF ready');
    expect(screen.getByTestId('pdf-status-p2')).toHaveTextContent('PDF pending');
    expect(screen.getByText('For Amara Silva')).toBeInTheDocument();
    expect(screen.getByText('Customer not recorded')).toBeInTheDocument();
    const pending = within(screen.getByTestId('library-item-p2'));
    expect(pending.queryByRole('button', { name: 'Download PDF' })).toBeNull();
    expect(pending.getByRole('button', { name: 'Create PDF' })).toBeInTheDocument();
  });

  it('says the PDF file is missing when its record exists but the file does not', async () => {
    patternsAPI.getAll.mockResolvedValue(list({ ...WITH_PDF, exports: [{ export_id: 'e1', file_available: false }] }));
    renderLibrary();
    expect(await screen.findByTestId('pdf-status-p1')).toHaveTextContent('PDF file missing');
    expect(screen.queryByRole('button', { name: 'Download PDF' })).toBeNull();
  });

  it('creates the pending PDF and refreshes the list', async () => {
    patternsAPI.getAll.mockResolvedValueOnce(list(NO_PDF))
      .mockResolvedValue(list({ ...NO_PDF, exports: [{ export_id: 'e9', file_available: true }] }));
    exportAPI.pdf.mockResolvedValue({ data: { export_id: 'e9' } });
    renderLibrary();
    fireEvent.click(await screen.findByRole('button', { name: 'Create PDF' }));
    await waitFor(() => expect(screen.getByTestId('pdf-status-p2')).toHaveTextContent('PDF ready'));
    expect(exportAPI.pdf).toHaveBeenCalledWith('p2');
  });

  it('"Delete PDF only" removes the PDF records and keeps the pattern', async () => {
    patternsAPI.getAll.mockResolvedValueOnce(list(WITH_PDF)).mockResolvedValue(list({ ...WITH_PDF, exports: [] }));
    exportAPI.delete.mockResolvedValue({});
    renderLibrary();
    fireEvent.click(await screen.findByRole('button', { name: 'Delete PDF only' }));
    await waitFor(() => expect(screen.getByTestId('pdf-status-p1')).toHaveTextContent('PDF pending'));
    expect(exportAPI.delete.mock.calls.map((c) => c[0])).toEqual(['e2', 'e1']);
    expect(patternsAPI.delete).not.toHaveBeenCalled();
    expect(window.confirm.mock.calls[0][0]).toMatch(/pattern itself is kept/);
  });

  it('"Delete pattern" deletes the pattern, refreshes, and does nothing when not confirmed', async () => {
    patternsAPI.getAll.mockResolvedValueOnce(list(WITH_PDF, NO_PDF)).mockResolvedValue(list(NO_PDF));
    patternsAPI.delete.mockResolvedValue({});
    renderLibrary();
    const item = within(await screen.findByTestId('library-item-p1'));
    window.confirm.mockReturnValueOnce(false);
    fireEvent.click(item.getByRole('button', { name: 'Delete pattern' }));
    expect(patternsAPI.delete).not.toHaveBeenCalled();
    fireEvent.click(item.getByRole('button', { name: 'Delete pattern' }));
    await waitFor(() => expect(screen.queryByTestId('library-item-p1')).toBeNull());
    expect(patternsAPI.delete).toHaveBeenCalledWith('p1');
    expect(exportAPI.delete).not.toHaveBeenCalled();
    expect(screen.getByTestId('library-item-p2')).toBeInTheDocument();
  });

  it('keeps the pattern on screen and explains when a delete fails', async () => {
    patternsAPI.getAll.mockResolvedValue(list(NO_PDF));
    patternsAPI.delete.mockRejectedValue({ response: { status: 500, data: {} } });
    renderLibrary();
    fireEvent.click(await screen.findByRole('button', { name: 'Delete pattern' }));
    expect((await screen.findByRole('alert')).textContent).toMatch(/server had a problem/);
    expect(screen.getByTestId('library-item-p2')).toBeInTheDocument();
  });

  it('a loading failure is an error with a retry, never "your library is empty"', async () => {
    patternsAPI.getAll.mockRejectedValueOnce(new Error('down')).mockResolvedValue(list(NO_PDF));
    renderLibrary();
    expect(await screen.findByTestId('library-error')).toBeInTheDocument();
    expect(screen.queryByText('Your pattern library is empty')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: /try again/i }));
    expect(await screen.findByTestId('library-item-p2')).toBeInTheDocument();
    expect(screen.queryByTestId('library-error')).toBeNull();
  });

  it('says the library is empty only when the server answered with no patterns', async () => {
    patternsAPI.getAll.mockResolvedValue(list());
    renderLibrary();
    expect(await screen.findByText('Your pattern library is empty')).toBeInTheDocument();
  });
});

describe('Saved pattern page', () => {
  const open = () => render(
    <MemoryRouter initialEntries={['/patterns/p2']}>
      <Routes>
        <Route path="/patterns/:patternId" element={<PatternDetail />} />
        <Route path="/history" element={<div>library page</div>} />
      </Routes>
    </MemoryRouter>,
  );

  it('opens a pattern whose customer, photo and PDF are all missing without crashing', async () => {
    patternsAPI.getOne.mockResolvedValue({ data: { pattern_id: 'p2', garment_type: 'blouse', pattern_pieces: [], exports: [] } });
    open();
    expect(await screen.findByTestId('pdf-pending')).toBeInTheDocument();
    expect(screen.getByText(/Design details not available/)).toBeInTheDocument();
  });

  it('creates the PDF and deletes the pattern from the page', async () => {
    patternsAPI.getOne.mockResolvedValueOnce({ data: { pattern_id: 'p2', garment_type: 'blouse', pattern_pieces: [], exports: [] } })
      .mockResolvedValue({ data: { pattern_id: 'p2', garment_type: 'blouse', pattern_pieces: [], exports: [{ export_id: 'e1', exported_at: '2026-09-30T10:00:00' }] } });
    exportAPI.pdf.mockResolvedValue({ data: {} });
    patternsAPI.delete.mockResolvedValue({});
    open();
    fireEvent.click(await screen.findByRole('button', { name: /create the pdf/i }));
    expect(await screen.findByRole('button', { name: /download/i })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /delete pattern/i }));
    expect(await screen.findByText('library page')).toBeInTheDocument();
    expect(patternsAPI.delete).toHaveBeenCalledWith('p2');
  });
});
