import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import FabricRecommendation from '../components/FabricRecommendation';
import FabricDetailsModal from '../components/FabricDetailsModal';
import { fabricAPI } from '../services/api';
import published from '../../../backend/app/data/published_fabric_samples.json';

vi.mock('../services/api', () => ({ fabricAPI: { getRecommendations: vi.fn(), getCatalog: vi.fn() } }));
const base = (over) => ({
  simple_description: 'A fabric.', feel: 'Smooth', weight: 'Light', stretch: 'No Stretch', breathability: 'High — airy',
  drape: 'Crisp', best_garment_uses: ['Blouses'], climate_suitability: 'Warm weather', advantages: ['Crisp'],
  limitations: ['Creases'], care_instructions: 'Wash cold', sewing_difficulty: 'Beginner',
  technical_details: { construction: 'Plain weave', typical_gsm_range: 'Typical GSM range: 110–130 GSM (varies by supplier)' },
  construction: 'woven', gsm_range: { min: 110, max: 130 }, compatible: true, warnings: [],
  recommended: false, recommendation_status: 'Compatible — unranked', recommendation_score: null,
  explanation: 'Supported by this drafting block.', ...over,
});

describe('published samples with explicit user preferences', () => {
  const study = published.studies[0];
  const sampleRows = study.samples.map((s) => ({ id: s.fabric_id, name: s.label, construction: 'knit',
    study_id: study.id, source_url: study.url, reference_source: study.citation, research_sample: s,
    simple_description: 'Identified cotton knit sample.', compatible: true, rank: null,
    explanation: 'Set your preferences to compare.', recommendation_status: 'Published sample — unranked' }));
  const initial = { fabrics: [...sampleRows, { ...FABRICS[0], compatible: false }],
    published_study: { ...study, samples: undefined, sample_count: 5 },
    ranking_status: 'awaiting_preferences', ranking_message: 'Set your preferences to compare the samples.' };
  const goals = { mass: 'cost', air_flow: 'benefit', thermal_resistance: 'cost' };
  const answers = { study_id: study.id, goals, comparisons: [
    { left: 'mass', right: 'air_flow', ratio: 1 }, { left: 'mass', right: 'thermal_resistance', ratio: 1 },
    { left: 'air_flow', right: 'thermal_resistance', ratio: 1 },
  ] };
  const rankedResponse = { ...initial, fabrics: sampleRows.map((f, i) => ({ ...f, rank: i + 1,
    topsis_closeness: .8 - i / 10, explanation: `Test API ranking: ${i + 1}` })), ranking_status: 'ranked',
    ranking_audit: { profile_id: study.id, weight_source: 'user_preferences', preferences: answers,
      criteria: study.criteria.map((c) => ({ ...c, objective: goals[c.id] })),
      ahp: { weights: [1/3, 1/3, 1/3], consistency_ratio: 0 }, scope_note: study.scope_note } };
  const fillPreferences = () => {
    Object.entries(goals).forEach(([id, value]) => fireEvent.change(document.querySelector(`#fabric-goal-${id}`), { target: { value } }));
    answers.comparisons.forEach((c) => fireEvent.change(document.querySelector(`#fabric-pair-${c.left}-${c.right}`), { target: { value: '1' } }));
  };
  beforeEach(() => { vi.clearAllMocks(); fabricAPI.getRecommendations.mockResolvedValue({ data: initial }); });

  it('requires all choices before comparing and shows measured sample values with the published source', async () => {
    renderIt();
    await screen.findByTestId('fabric-preferences');
    expect(screen.getByRole('button', { name: 'Compare fabric samples' })).toBeDisabled();
    expect(screen.getByTestId('published-fabrics').querySelectorAll('article')).toHaveLength(5);
    expect(screen.getByTestId('fabric-cubric-2022-y1-sp')).toHaveTextContent('Measured weight: 260.38 g/m²');
    fireEvent.click(screen.getAllByText('View Details')[0]);
    expect(screen.getByRole('cell', { name: '140.12 L/min' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: study.citation })).toHaveAttribute('href', study.url);
    expect(screen.queryByText(/expert comparison/i)).not.toBeInTheDocument();
  });

  it('sends the live choices, displays weights and passes the chosen preferences to the wizard', async () => {
    const select = vi.fn();
    renderIt({ onSelectFabric: select });
    await screen.findByTestId('fabric-preferences');
    fillPreferences();
    fabricAPI.getRecommendations.mockResolvedValueOnce({ data: rankedResponse });
    fireEvent.click(screen.getByRole('button', { name: 'Compare fabric samples' }));
    await screen.findByTestId('ranked-fabrics');
    expect(fabricAPI.getRecommendations).toHaveBeenLastCalledWith({ confirmed_attributes: DESIGN, fit_preference: 'standard', user_preferences: answers });
    expect(select).not.toHaveBeenCalled();
    fireEvent.click(screen.getAllByText('View Details')[0]);
    expect(screen.getAllByRole('cell', { name: '33.3%' })).toHaveLength(3);
    expect(screen.getByText(/Your comparison consistency ratio/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Select this sample' }));
    expect(select).toHaveBeenCalledWith(sampleRows[0].id, sampleRows[0].name, 'knit', answers);
  });

  it('clears a sample selected under old priorities when preferences are edited', async () => {
    const select = vi.fn();
    renderIt({ selectedFabricId: sampleRows[0].id, onSelectFabric: select });
    await screen.findByTestId('fabric-preferences');
    fireEvent.change(document.querySelector('#fabric-goal-mass'), { target: { value: 'cost' } });
    expect(select).toHaveBeenCalledWith('', '', undefined);
    expect(screen.getByTestId('fabric-ranking-status')).toHaveTextContent('Preferences changed');
    expect(screen.queryByTestId('ranked-fabrics')).not.toBeInTheDocument();
  });

  it('keeps the entered answers and offers correction when comparisons are inconsistent', async () => {
    renderIt();
    await screen.findByTestId('fabric-preferences');
    fillPreferences();
    fabricAPI.getRecommendations.mockRejectedValueOnce({ response: { data: { ...initial,
      error_code: 'INVALID_FABRIC_PREFERENCES', error: 'Your importance choices contradict each other.' } } });
    fireEvent.click(screen.getByRole('button', { name: 'Compare fabric samples' }));
    await screen.findByText('Your importance choices contradict each other.');
    expect(document.querySelector('#fabric-goal-air_flow')).toHaveValue('benefit');
    expect(screen.getByRole('button', { name: 'Compare fabric samples' })).toBeEnabled();
    expect(screen.queryByTestId('ranked-fabrics')).not.toBeInTheDocument();
  });

  it('recalculates retained complete preferences when returning to the fabric step', async () => {
    fabricAPI.getRecommendations.mockResolvedValueOnce({ data: initial }).mockResolvedValueOnce({ data: rankedResponse });
    renderIt({ preferences: answers });
    await screen.findByTestId('ranked-fabrics');
    expect(fabricAPI.getRecommendations).toHaveBeenCalledTimes(2);
    expect(fabricAPI.getRecommendations).toHaveBeenLastCalledWith(expect.objectContaining({ user_preferences: answers }));
  });
});
const FABRICS = [
  base({ id: 'cotton-poplin', name: 'Cotton Poplin', local_image: '/fabrics/cotton-poplin.jpg' }),
  base({ id: 'linen-blend', name: 'Linen Blend', weight: 'Medium', gsm_range: { min: 160, max: 190 } }),
  base({ id: 'silk-chiffon', name: 'Silk Chiffon', warnings: ['Check the sample: lining may be needed.'] }),
  base({ id: 'cotton-jersey-knit', name: 'Cotton Jersey Knit', compatible: false, construction: 'knit',
    incompatible_reason: 'This system drafts blouses on its woven block; choose a woven fabric.' }),
];
const DESIGN = { garment_type: 'blouse', neckline_type: 'round-neck', sleeve_length: 'short-sleeve', sleeve_style: 'puff-sleeve' };
const UNRANKED = { fabrics: FABRICS, ranking_status: 'awaiting_data',
  ranking_message: 'Fabric sample data and recorded expert comparisons are not available. Choose a compatible fabric below.' };
const renderIt = (props = {}) => render(<FabricRecommendation confirmedAttributes={DESIGN} selectedFabricId="" onSelectFabric={() => {}} {...props} />);

describe('FabricRecommendation with AHP/TOPSIS data readiness', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    fabricAPI.getRecommendations.mockResolvedValue({ data: UNRANKED });
  });

  it('requests the confirmed design and fit and shows compatible fabrics without invented recommendations', async () => {
    const select = vi.fn();
    renderIt({ fitPreference: 'loose', onSelectFabric: select });
    const grid = await screen.findByTestId('compatible-fabrics');
    expect(fabricAPI.getRecommendations).toHaveBeenCalledWith({ confirmed_attributes: DESIGN, fit_preference: 'loose' });
    expect(screen.getByText('Compatible fabrics')).toBeInTheDocument();
    expect(screen.getByTestId('fabric-ranking-status')).toHaveTextContent(/not available/);
    expect(grid.querySelectorAll('article')).toHaveLength(3);
    expect(grid).toHaveTextContent('Catalogue guide: 110–130 GSM');
    expect(select).not.toHaveBeenCalled();
    expect(screen.queryByText('Recommended fabrics')).not.toBeInTheDocument();
  });

  it('keeps all compatible choices selectable and explains unsupported fabrics', async () => {
    const select = vi.fn();
    renderIt({ onSelectFabric: select, selectedFabricId: 'cotton-poplin' });
    await screen.findByTestId('compatible-fabrics');
    expect(select).not.toHaveBeenCalled();
    expect(screen.getByTestId('fabric-silk-chiffon')).toHaveTextContent(/lining/);
    fireEvent.click(screen.getByTestId('fabric-silk-chiffon').querySelector('button'));
    expect(select).toHaveBeenCalledWith('silk-chiffon', 'Silk Chiffon', 'woven');
    expect(screen.getByTestId('incompatible-fabrics')).toHaveTextContent(/Cotton Jersey Knit/);
    expect(screen.queryByTestId('fabric-cotton-jersey-knit')).not.toBeInTheDocument();
  });

  it('clears an incompatible selection without silently replacing it', async () => {
    const select = vi.fn();
    renderIt({ onSelectFabric: select, selectedFabricId: 'cotton-jersey-knit' });
    expect(await screen.findByTestId('fabric-replaced')).toHaveTextContent(/cannot be used.*choose another fabric/i);
    expect(select).toHaveBeenCalledOnce();
    expect(select).toHaveBeenCalledWith('', '', undefined);
  });

  it('does not present an invalid or indistinguishable dataset as a ranking', async () => {
    fabricAPI.getRecommendations.mockResolvedValue({ data: { ...UNRANKED, ranking_status: 'invalid_data', ranking_message: 'Ranking unavailable: incomplete data.' } });
    renderIt();
    await screen.findByTestId('compatible-fabrics');
    expect(screen.getByTestId('fabric-ranking-status')).toHaveTextContent('incomplete data');
    expect(screen.queryByText('AHP / TOPSIS')).not.toBeInTheDocument();
  });

  it('shows a data-backed sample ranking and its evidence while requiring an explicit choice', async () => {
    const select = vi.fn();
    const sample = { sample_id: 'SYNTHETIC-P1', label: 'Synthetic test poplin', values: {
      mass: { value: 120, unit: 'g/m2', source: 'Synthetic test record' },
    } };
    fabricAPI.getRecommendations.mockResolvedValue({ data: { fabrics: [
      { ...FABRICS[0], recommended: true, rank: 1, topsis_closeness: .8, research_sample: sample,
        explanation: 'Synthetic test sample: relative closeness 0.800.', recommendation_status: 'Top ranked sample' },
      ...FABRICS.slice(1),
    ], ranking_status: 'ranked', ranking_message: 'Samples compared using recorded data.', ranking_audit: {
      criteria: [{ id: 'mass', label: 'Areal density' }], ahp: { weights: [1], consistency_ratio: 0 }, profile_source: 'Synthetic study',
    } } });
    renderIt({ onSelectFabric: select });
    await screen.findByTestId('ranked-fabrics');
    expect(screen.getByText('AHP / TOPSIS')).toBeInTheDocument();
    expect(screen.getByText('Ranked fabric samples')).toBeInTheDocument();
    expect(select).not.toHaveBeenCalled();
    fireEvent.click(screen.getAllByText('View Details')[0]);
    expect(await screen.findByText('Recorded sample evidence')).toBeInTheDocument();
    expect(screen.getByRole('cell', { name: '120 g/m2' })).toBeInTheDocument();
    expect(screen.getByRole('cell', { name: 'Synthetic test record' })).toBeInTheDocument();
    expect(screen.getByText(/not a probability of fit/)).toBeInTheDocument();
  });

  it('lists the catalogue before design confirmation and allows a selection', async () => {
    const select = vi.fn();
    fabricAPI.getCatalog.mockResolvedValue({ data: { fabrics: FABRICS } });
    renderIt({ confirmedAttributes: null, onSelectFabric: select });
    expect(await screen.findByTestId('fabric-pending')).toHaveTextContent(/Recommendations pending/);
    expect(screen.getByTestId('catalogue-fabrics').querySelectorAll('article')).toHaveLength(4);
    expect(fabricAPI.getRecommendations).not.toHaveBeenCalled();
    fireEvent.click(screen.getByTestId('fabric-cotton-jersey-knit').querySelector('button'));
    expect(select).toHaveBeenCalledWith('cotton-jersey-knit', 'Cotton Jersey Knit', 'knit');
  });

  it('shows validation errors and retries a failed request', async () => {
    fabricAPI.getRecommendations.mockRejectedValueOnce(new Error('down'));
    renderIt({ validationError: 'Choose a compatible fabric.' });
    expect(await screen.findByText(/could not be loaded/)).toBeInTheDocument();
    expect(screen.getByText('Choose a compatible fabric.')).toBeInTheDocument();
    fireEvent.click(screen.getByText('Retry'));
    await screen.findByTestId('compatible-fabrics');
  });

  it('opens unranked details without calling the fabric recommended and closes on Escape', async () => {
    renderIt();
    await screen.findByTestId('compatible-fabrics');
    fireEvent.click(screen.getAllByText('View Details')[0]);
    expect(await screen.findByText('Fabric selection:')).toBeInTheDocument();
    expect(screen.getByText('Technical Details & Supplier Notes')).toBeInTheDocument();
    fireEvent.keyDown(window, { key: 'Escape' });
    await waitFor(() => expect(screen.queryByText('Fabric selection:')).not.toBeInTheDocument());
  });

  it('ignores stale responses after the design or fit changes', async () => {
    let finishOld;
    fabricAPI.getRecommendations.mockImplementationOnce(() => new Promise((resolve) => { finishOld = resolve; }));
    const select = vi.fn();
    const { rerender } = renderIt({ selectedFabricId: 'cotton-poplin', onSelectFabric: select });
    rerender(<FabricRecommendation confirmedAttributes={DESIGN} fitPreference="close" selectedFabricId="cotton-poplin" onSelectFabric={select} />);
    await screen.findByTestId('compatible-fabrics');
    await act(async () => finishOld({ data: { ...UNRANKED, fabrics: [{ ...FABRICS[0], compatible: false }] } }));
    expect(screen.getByTestId('compatible-fabrics').querySelectorAll('article')).toHaveLength(3);
    expect(select).not.toHaveBeenCalled();
  });

  it('handles image failures in the details modal', () => {
    render(<FabricDetailsModal fabric={{ ...FABRICS[0], local_image: '/broken.jpg' }} isSelected={false} onSelect={() => {}} onClose={() => {}} />);
    fireEvent.error(screen.getByAltText('Close-up fabric texture image of Cotton Poplin'));
    expect(screen.getByText('Texture Swatch')).toBeInTheDocument();
  });
});
