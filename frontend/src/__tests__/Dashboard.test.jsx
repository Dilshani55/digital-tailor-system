import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import React from 'react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import Dashboard from '../pages/Dashboard';
import FabricSavings from '../pages/FabricSavings';
import { exportAPI, patternsAPI } from '../services/api';

vi.mock('../context/AuthContext', () => ({
  useAuth: () => ({ user: { full_name: 'Dilshani Vitharana' } })
}));

vi.mock('../services/api', () => ({
  patternsAPI: { getAll: vi.fn() },
  exportAPI: { getAll: vi.fn() }
}));

function CurrentPath() {
  const location = useLocation();
  return <output data-testid="current-path">{location.pathname}</output>;
}

describe('Dashboard data and navigation', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    patternsAPI.getAll.mockResolvedValue({
      data: {
        patterns: [
          {
            pattern_id: 'pattern-a',
            garment_type: 'blouse',
            pieces_count: 3,
            yardage_metres: 1.2,
            selected_fabric_name: 'Cotton Poplin',
            nesting_summary: { waste_cm2: 12500, fabric_width_cm: 114, waste_percent: 28, fabric_length_cm: 120, cutting_mode: 'folded', total_pieces: 3 }
          },
          {
            pattern_id: 'pattern-b',
            garment_type: 't-shirt',
            pieces_count: 3,
            yardage_metres: 0,
            nesting_summary: { waste_cm2: 7500, fabric_width_cm: 150, waste_percent: 18, fabric_length_cm: 100, cutting_mode: 'folded', total_pieces: 3 }
          },
          { pattern_id: 'pattern-old', garment_type: 'crop-top', nesting_summary: {} }
        ]
      }
    });
    exportAPI.getAll.mockResolvedValue({ data: { exports: [{ export_id: 'export-a' }] } });
  });

  it('renders database-backed metrics and removes average efficiency', async () => {
    render(<MemoryRouter><Dashboard /></MemoryRouter>);

    expect(await screen.findByText('2.00 m²')).toBeInTheDocument();
    expect(screen.getByText('Patterns created')).toBeInTheDocument();
    expect(screen.getByText('PDF guides')).toBeInTheDocument();
    expect(screen.queryByText('Average efficiency')).not.toBeInTheDocument();
    expect(screen.getByText('From 2 saved fabric layouts')).toBeInTheDocument();
    expect(screen.getAllByText(/Fabric plan pending/)).toHaveLength(2);
  });

  it('opens the saved offcut detail page from the metric card', async () => {
    render(
      <MemoryRouter initialEntries={['/dashboard']}>
        <Routes>
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/fabric-savings" element={<FabricSavings />} />
          <Route path="/history" element={<div>Pattern library</div>} />
        </Routes>
        <CurrentPath />
      </MemoryRouter>
    );

    fireEvent.click(await screen.findByRole('button', { name: /potential reusable offcuts/i }));
    await waitFor(() => expect(screen.getByTestId('current-path')).toHaveTextContent('/fabric-savings'));
    expect(await screen.findByText('Total estimated offcut area')).toBeInTheDocument();
    expect(screen.getByText('2.000 m²')).toBeInTheDocument();
    expect(screen.getByText(/1 older pattern has no saved nesting breakdown/i)).toBeInTheDocument();
  });

  it('routes pattern and PDF metric cards to the pattern library', async () => {
    render(
      <MemoryRouter initialEntries={['/dashboard']}>
        <Routes>
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/history" element={<div>Pattern library</div>} />
        </Routes>
        <CurrentPath />
      </MemoryRouter>
    );

    fireEvent.click(await screen.findByRole('button', { name: /patterns created/i }));
    await waitFor(() => expect(screen.getByTestId('current-path')).toHaveTextContent('/history'));
  });
});