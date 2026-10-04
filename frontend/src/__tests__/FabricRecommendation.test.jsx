import { render, screen, fireEvent, waitFor, act, within } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { useState } from 'react';
import FabricRecommendation from '../components/FabricRecommendation';
import FabricDetailsModal from '../components/FabricDetailsModal';
import { completePreferences } from '../components/FabricPreferences';
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
    fireEvent.click(screen.getByRole('button', { name: 'Treat all properties equally' }));
  };
  beforeEach(() => { vi.clearAllMocks(); fabricAPI.getRecommendations.mockResolvedValue({ data: initial }); });

  it('requires all choices before comparing and shows measured sample values with the published source', async () => {
    renderIt();
    await screen.findByTestId('fabric-preferences');
    expect(screen.getByRole('button', { name: 'Find recommended fabrics' })).toBeDisabled();
    expect(screen.queryByTestId('other-fabrics')).not.toBeInTheDocument();
    expect(screen.queryByTestId('fabric-cubric-2022-y1-sp')).not.toBeInTheDocument();
    fillPreferences();
    fabricAPI.getRecommendations.mockResolvedValueOnce({ data: rankedResponse });
    fireEvent.click(screen.getByRole('button', { name: 'Find recommended fabrics' }));
    await screen.findByTestId('ranked-fabrics');
    expect(screen.getByTestId('fabric-cubric-2022-y1-sp')).toHaveTextContent('260.38 g/m²');
    fireEvent.click(screen.getAllByText('View Details')[0]);
    expect(screen.getByRole('heading', { name: 'About this material' })).toBeInTheDocument();
    expect(screen.getByRole('dialog')).toHaveTextContent('100% cotton');
    expect(screen.getByRole('cell', { name: '140.12 L/min' })).not.toBeVisible();
    fireEvent.click(screen.getByText('Measurement references'));
    expect(screen.getByRole('cell', { name: '140.12 L/min' })).toBeInTheDocument();
    expect(within(screen.getByRole('dialog')).getByRole('link', { name: study.citation })).toHaveAttribute('href', study.url);
    expect(screen.queryByText(/expert comparison/i)).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Select material' })).toBeEnabled();
  });

  it('sends the live choices, displays weights and passes the chosen preferences to the wizard', async () => {
    const select = vi.fn();
    renderIt({ onSelectFabric: select });
    await screen.findByTestId('fabric-preferences');
    fillPreferences();
    fabricAPI.getRecommendations.mockResolvedValueOnce({ data: rankedResponse });
    fireEvent.click(screen.getByRole('button', { name: 'Find recommended fabrics' }));
    await screen.findByTestId('ranked-fabrics');
    expect(fabricAPI.getRecommendations).toHaveBeenLastCalledWith({ confirmed_attributes: DESIGN, fit_preference: 'standard', user_preferences: answers });
    expect(select).not.toHaveBeenCalled();
    expect(screen.getByTestId('ranked-fabrics').querySelectorAll('article')).toHaveLength(1);
    expect(screen.getByTestId('other-fabrics').querySelectorAll('article')).toHaveLength(4);
    expect(screen.getByRole('heading', { name: 'Recommended materials' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Other materials' })).toBeInTheDocument();
    expect(document.querySelectorAll('.fabric-recommendation details')).toHaveLength(0);
    expect(screen.queryByText('AHP / TOPSIS')).not.toBeInTheDocument();
    expect(screen.getByTestId('fabric-preference-summary')).toHaveTextContent('Lighter fabric');
    expect(screen.queryByTestId('fabric-preferences')).not.toBeInTheDocument();
    fireEvent.click(screen.getAllByText('View Details')[0]);
    fireEvent.click(screen.getByText('Measurement references'));
    expect(screen.getAllByRole('cell', { name: '33.3%' })).toHaveLength(3);
    expect(screen.getByText(/Your comparison consistency ratio/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Select material' }));
    expect(select).toHaveBeenCalledWith(sampleRows[0].id, sampleRows[0].name, 'knit', answers);
  });

  it('clears a sample selected under old priorities when preferences are edited', async () => {
    const select = vi.fn();
    renderIt({ selectedFabricId: sampleRows[0].id, onSelectFabric: select });
    await screen.findByTestId('fabric-preferences');
    fireEvent.change(document.querySelector('#fabric-goal-mass'), { target: { value: 'cost' } });
    expect(select).toHaveBeenCalledWith('', '', undefined);
    expect(screen.getByTestId('fabric-ranking-status')).toHaveTextContent('Complete your fabric goals');
    expect(screen.queryByTestId('ranked-fabrics')).not.toBeInTheDocument();
  });

  it('keeps the entered answers and offers correction when comparisons are inconsistent', async () => {
    renderIt();
    await screen.findByTestId('fabric-preferences');
    fillPreferences();
    fireEvent.click(screen.getByRole('button', { name: 'Set priorities individually' }));
    answers.comparisons.forEach((c, i) => fireEvent.change(document.querySelector(`#fabric-pair-${c.left}-${c.right}`), { target: { value: i === 1 ? String(1/9) : '9' } }));
    fabricAPI.getRecommendations.mockRejectedValueOnce({ response: { data: { ...initial,
      error_code: 'INVALID_FABRIC_PREFERENCES', error: 'Your importance choices contradict each other.' } } });
    fireEvent.click(screen.getByRole('button', { name: 'Find recommended fabrics' }));
    await screen.findByText('Your importance choices contradict each other.');
    expect(document.querySelector('#fabric-goal-air_flow')).toHaveValue('benefit');
    expect(screen.getByRole('button', { name: 'Find recommended fabrics' })).toBeEnabled();
    expect(document.querySelector('#fabric-pairwise')).not.toHaveAttribute('hidden');
    expect(screen.queryByTestId('ranked-fabrics')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Treat all properties equally' }));
    expect(screen.queryByText('Your importance choices contradict each other.')).not.toBeInTheDocument();
    expect(document.querySelector('#fabric-pairwise')).toHaveAttribute('hidden');
  });

  it('recalculates retained complete preferences when returning to the fabric step', async () => {
    fabricAPI.getRecommendations.mockResolvedValueOnce({ data: initial }).mockResolvedValueOnce({ data: rankedResponse });
    renderIt({ preferences: answers });
    await screen.findByTestId('ranked-fabrics');
    expect(fabricAPI.getRecommendations).toHaveBeenCalledTimes(2);
    expect(fabricAPI.getRecommendations).toHaveBeenLastCalledWith(expect.objectContaining({ user_preferences: answers }));
  });

  it('makes importance an explicit choice and supports individual comparisons', async () => {
    renderIt();
    await screen.findByTestId('fabric-preferences');
    Object.entries(goals).forEach(([id, value]) => fireEvent.change(document.querySelector(`#fabric-goal-${id}`), { target: { value } }));
    expect(screen.getByRole('button', { name: 'Find recommended fabrics' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Treat all properties equally' })).toHaveAttribute('aria-pressed', 'false');
    fireEvent.click(screen.getByRole('button', { name: 'Set priorities individually' }));
    expect(document.querySelector('#fabric-pairwise')).not.toHaveAttribute('hidden');
    answers.comparisons.forEach((c) => fireEvent.change(document.querySelector(`#fabric-pair-${c.left}-${c.right}`), { target: { value: '3' } }));
    expect(screen.getByRole('button', { name: 'Find recommended fabrics' })).toBeEnabled();
    expect(fabricAPI.getRecommendations).toHaveBeenCalledOnce();
  });

  it('preserves a ranking when opening the editor, but invalidates it after a real edit', async () => {
    const select = vi.fn();
    fabricAPI.getRecommendations.mockResolvedValueOnce({ data: initial }).mockResolvedValueOnce({ data: rankedResponse });
    renderIt({ preferences: answers, selectedFabricId: sampleRows[0].id, onSelectFabric: select });
    await screen.findByTestId('ranked-fabrics');
    fireEvent.click(screen.getByRole('button', { name: 'Edit preferences' }));
    expect(select).not.toHaveBeenCalled();
    expect(screen.getByTestId('ranked-fabrics')).toBeInTheDocument();
    fireEvent.change(document.querySelector('#fabric-goal-mass'), { target: { value: 'benefit' } });
    expect(select).toHaveBeenCalledWith('', '', undefined);
    expect(screen.queryByTestId('ranked-fabrics')).not.toBeInTheDocument();
  });

  it('recommends all tied winners and keeps a selected alternative in Other materials', async () => {
    const tied = { ...rankedResponse, fabrics: rankedResponse.fabrics.map((f, i) => ({ ...f, rank: i < 4 ? 1 : 5 })) };
    fabricAPI.getRecommendations.mockResolvedValueOnce({ data: initial }).mockResolvedValueOnce({ data: tied });
    renderIt({ preferences: answers, selectedFabricId: sampleRows[4].id });
    const grid = await screen.findByTestId('ranked-fabrics');
    expect(grid.querySelectorAll('article')).toHaveLength(4);
    expect(screen.getAllByText('Recommended', { exact: true })).toHaveLength(4);
    expect(within(screen.getByTestId('other-fabrics')).getByTestId(`fabric-${sampleRows[4].id}`)).toHaveClass('selected');
    expect(screen.getByTestId('fabric-selection-summary')).toHaveTextContent(sampleRows[4].name);
  });

  it('allows direct selection and keeps keyboard focus inside evidence before returning it', async () => {
    const select = vi.fn();
    fabricAPI.getRecommendations.mockResolvedValueOnce({ data: initial }).mockResolvedValueOnce({ data: rankedResponse });
    renderIt({ preferences: answers, onSelectFabric: select });
    await screen.findByTestId('ranked-fabrics');
    const article = screen.getByTestId(`fabric-${sampleRows[0].id}`);
    fireEvent.click(article.querySelector('.fabric-select-btn'));
    expect(select).toHaveBeenCalledWith(sampleRows[0].id, sampleRows[0].name, 'knit', answers);
    const opener = article.querySelector('.fabric-details-btn');
    opener.focus();
    fireEvent.click(opener);
    const close = screen.getByRole('button', { name: 'Close modal' });
    const last = screen.getByRole('button', { name: 'Select material' });
    expect(close).toHaveFocus();
    fireEvent.keyDown(window, { key: 'Tab', shiftKey: true });
    expect(last).toHaveFocus();
    fireEvent.keyDown(window, { key: 'Tab' });
    expect(close).toHaveFocus();
    fireEvent.keyDown(window, { key: 'Escape' });
    expect(opener).toHaveFocus();
    expect(document.body.style.overflow).not.toBe('hidden');
  });

  it('rejects duplicate, missing and out-of-scale comparisons in retained preferences', () => {
    expect(completePreferences(study, answers)).toBe(true);
    expect(completePreferences(study, { ...answers, comparisons: [answers.comparisons[0], answers.comparisons[0], answers.comparisons[2]] })).toBe(false);
    expect(completePreferences(study, { ...answers, comparisons: answers.comparisons.slice(0, 2) })).toBe(false);
    expect(completePreferences(study, { ...answers, comparisons: answers.comparisons.map((c) => ({ ...c, ratio: 2 })) })).toBe(false);
  });

  it('keeps a selected other material visible without presenting it as recommended', async () => {
    fabricAPI.getRecommendations.mockResolvedValueOnce({ data: initial }).mockResolvedValueOnce({ data: rankedResponse });
    function Harness() {
      const [selected, setSelected] = useState('');
      return <FabricRecommendation confirmedAttributes={DESIGN} preferences={answers} selectedFabricId={selected} onSelectFabric={setSelected} />;
    }
    render(<Harness />);
    await screen.findByTestId('ranked-fabrics');
    const lower = screen.getByTestId(`fabric-${sampleRows[4].id}`).querySelector('.fabric-select-btn');
    lower.focus();
    fireEvent.click(lower);
    expect(within(screen.getByTestId('other-fabrics')).getByTestId(`fabric-${sampleRows[4].id}`)).toHaveClass('selected');
    expect(lower).toHaveFocus();
    expect(screen.getByTestId('ranked-fabrics').querySelectorAll('article')).toHaveLength(1);
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
    const grid = await screen.findByTestId('other-fabrics');
    expect(fabricAPI.getRecommendations).toHaveBeenCalledWith({ confirmed_attributes: DESIGN, fit_preference: 'loose' });
    expect(screen.getByText('Other materials')).toBeInTheDocument();
    expect(screen.getByTestId('fabric-ranking-status')).toHaveTextContent(/not available/);
    expect(grid.querySelectorAll('article')).toHaveLength(4);
    expect(grid).toHaveTextContent('110–130 GSM');
    expect(select).not.toHaveBeenCalled();
    expect(screen.queryByText('Recommended fabrics')).not.toBeInTheDocument();
  });

  it('keeps all compatible choices selectable and explains unsupported fabrics', async () => {
    const select = vi.fn();
    renderIt({ onSelectFabric: select, selectedFabricId: 'cotton-poplin' });
    await screen.findByTestId('other-fabrics');
    expect(select).not.toHaveBeenCalled();
    fireEvent.click(screen.getByTestId('fabric-silk-chiffon').querySelector('button'));
    expect(select).toHaveBeenCalledWith('silk-chiffon', 'Silk Chiffon', 'woven');
    const unsupported = screen.getByTestId('fabric-cotton-jersey-knit');
    expect(unsupported).toHaveTextContent('Not suitable for this design');
    expect(within(unsupported).getByRole('button', { name: 'Not available' })).toBeDisabled();
    fireEvent.click(within(unsupported).getByRole('button', { name: 'View Details' }));
    expect(screen.getByRole('heading', { name: 'About this material' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Select material' })).toBeDisabled();
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
    await screen.findByTestId('other-fabrics');
    expect(screen.getByTestId('fabric-ranking-status')).toHaveTextContent('not available');
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
    expect(screen.getByText('Recommended materials')).toBeInTheDocument();
    expect(select).not.toHaveBeenCalled();
    fireEvent.click(screen.getAllByText('View Details')[0]);
    fireEvent.click(screen.getByText('Measurement references'));
    expect(await screen.findByText('Recorded sample evidence')).toBeInTheDocument();
    expect(screen.getByRole('cell', { name: '120 g/m²' })).toBeInTheDocument();
    expect(screen.getByRole('cell', { name: 'Synthetic test record' })).toBeInTheDocument();
    expect(screen.getByText(/not a probability of fit/)).toBeInTheDocument();
  });

  it('lists the catalogue before design confirmation and allows a selection', async () => {
    const select = vi.fn();
    fabricAPI.getCatalog.mockResolvedValue({ data: { fabrics: FABRICS } });
    renderIt({ confirmedAttributes: null, onSelectFabric: select });
    expect(await screen.findByTestId('fabric-pending')).toHaveTextContent(/Confirm your design/);
    expect(screen.getByTestId('other-fabrics').querySelectorAll('article')).toHaveLength(4);
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
    await screen.findByTestId('other-fabrics');
  });

  it('opens unranked details without calling the fabric recommended and closes on Escape', async () => {
    renderIt();
    await screen.findByTestId('other-fabrics');
    fireEvent.click(screen.getAllByText('View Details')[0]);
    expect(await screen.findByText('About this material')).toBeInTheDocument();
    expect(screen.getByText('Care instructions')).toBeInTheDocument();
    expect(screen.getByText('Wash cold')).toBeInTheDocument();
    expect(screen.getByText('Material notes')).toBeInTheDocument();
    fireEvent.keyDown(window, { key: 'Escape' });
    await waitFor(() => expect(screen.queryByText('About this material')).not.toBeInTheDocument());
  });

  it('ignores stale responses after the design or fit changes', async () => {
    let finishOld;
    fabricAPI.getRecommendations.mockImplementationOnce(() => new Promise((resolve) => { finishOld = resolve; }));
    const select = vi.fn();
    const { rerender } = renderIt({ selectedFabricId: 'cotton-poplin', onSelectFabric: select });
    rerender(<FabricRecommendation confirmedAttributes={DESIGN} fitPreference="close" selectedFabricId="cotton-poplin" onSelectFabric={select} />);
    await screen.findByTestId('other-fabrics');
    await act(async () => finishOld({ data: { ...UNRANKED, fabrics: [{ ...FABRICS[0], compatible: false }] } }));
    expect(screen.getByTestId('other-fabrics').querySelectorAll('article')).toHaveLength(4);
    expect(select).not.toHaveBeenCalled();
  });

  it('handles image failures in the details modal', () => {
    render(<FabricDetailsModal fabric={{ ...FABRICS[0], local_image: '/broken.jpg' }} isSelected={false} onSelect={() => {}} onClose={() => {}} />);
    fireEvent.error(screen.getByAltText('Close-up fabric texture image of Cotton Poplin'));
    expect(screen.getByText('Image unavailable')).toBeInTheDocument();
  });
});
