import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import FabricRecommendation from '../components/FabricRecommendation';
import FabricDetailsModal from '../components/FabricDetailsModal';
import { fabricAPI } from '../services/api';

vi.mock('../services/api', () => ({
  fabricAPI: {
    getRecommendations: vi.fn(),
    getCatalog: vi.fn()
  }
}));

const base = (over) => ({
  simple_description: 'A fabric.', feel: 'Smooth', weight: 'Light', stretch: 'No Stretch', breathability: 'High — airy',
  drape: 'Crisp', best_garment_uses: ['Blouses'], climate_suitability: 'Warm weather', advantages: ['Crisp'],
  limitations: ['Creases'], care_instructions: 'Wash cold', sewing_difficulty: 'Beginner',
  technical_details: { construction: 'Plain weave', typical_gsm_range: 'Typical GSM range: 110 – 130 GSM (varies by supplier)' },
  construction: 'woven', drape_level: 2, opacity: 'opaque', gsm_range: { min: 110, max: 130 },
  compatible: true, incompatible_reason: null, warnings: [], score_reasons: [],
  ...over,
});

const FABRICS = [
  base({ id: 'cotton-poplin', name: 'Cotton Poplin', local_image: '/fabrics/cotton-poplin.jpg', recommended: true,
    recommendation_status: 'Recommended', recommendation_score: 80,
    explanation: 'Puff sleeve: a crisp light/medium fabric holds the gathered cap up.' }),
  base({ id: 'linen-blend', name: 'Linen Blend', local_image: '/fabrics/linen-blend.jpg', recommended: true,
    recommendation_status: 'Recommended', recommendation_score: 80, weight: 'Medium', gsm_range: { min: 160, max: 190 },
    explanation: 'Puff sleeve: a crisp light/medium fabric holds the gathered cap up.' }),
  base({ id: 'silk-chiffon', name: 'Silk Chiffon', local_image: '/fabrics/silk-chiffon.jpg', recommended: false,
    recommendation_status: 'Also compatible', recommendation_score: 35, opacity: 'sheer',
    warnings: ['Sheer — a lining would be needed; the pattern has no lining pieces.'], explanation: 'Compatible.' }),
  base({ id: 'cotton-jersey-knit', name: 'Cotton Jersey Knit', local_image: '/fabrics/cotton-jersey-knit.jpg', recommended: false,
    compatible: false, construction: 'knit', stretch: 'Stretchable', recommendation_status: 'Not compatible', recommendation_score: null,
    incompatible_reason: 'A blouse is drafted on the woven block with darts; a knit fabric is not compatible.',
    explanation: 'A blouse is drafted on the woven block with darts; a knit fabric is not compatible.' }),
];
const DESIGN = { garment_type: 'blouse', neckline_type: 'round-neck', sleeve_length: 'short-sleeve', sleeve_style: 'puff-sleeve' };

const renderIt = (props = {}) => render(
  <FabricRecommendation confirmedAttributes={DESIGN} fitPreference="standard" selectedFabricId="" onSelectFabric={() => {}} validationError="" {...props} />,
);

describe('FabricRecommendation (rule-based, design-aware)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    fabricAPI.getRecommendations.mockResolvedValue({
      data: { fabrics: FABRICS, recommendations: FABRICS, recommended_ids: ['cotton-poplin', 'linen-blend'], method: 'Rule-based' },
    });
  });

  it('asks for recommendations for the confirmed design and fit, and is labelled rule-based', async () => {
    renderIt({ fitPreference: 'loose' });
    await screen.findByTestId('recommended-fabrics');
    expect(fabricAPI.getRecommendations).toHaveBeenCalledWith({ confirmed_attributes: DESIGN, fit_preference: 'loose' });
    expect(screen.getByText('Rule-Based Fabric Recommendation')).toBeInTheDocument();
    expect(screen.getByText('Recommended fabrics')).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/AI-Assisted|Best Match|price|in stock/i);
  });

  it('shows the 2-4 recommended fabrics with real GSM and tags, and pre-selects the top one', async () => {
    const onSelect = vi.fn();
    renderIt({ onSelectFabric: onSelect });
    const rec = await screen.findByTestId('recommended-fabrics');
    expect(rec.textContent).toContain('Cotton Poplin');
    expect(rec.textContent).toContain('Linen Blend');
    expect(rec.textContent).toContain('110–130 GSM');
    expect(rec.textContent).not.toContain('Silk Chiffon');
    expect(onSelect).toHaveBeenCalledWith('cotton-poplin', 'Cotton Poplin', 'woven');
  });

  it('keeps other compatible fabrics selectable and lists incompatible ones with the reason', async () => {
    const onSelect = vi.fn();
    renderIt({ onSelectFabric: onSelect, selectedFabricId: 'cotton-poplin' });
    await screen.findByTestId('recommended-fabrics');
    expect(onSelect).not.toHaveBeenCalled();                            // a compatible choice is kept
    fireEvent.click(screen.getByText(/Other compatible fabrics \(1\)/));
    const others = screen.getByTestId('other-fabrics');
    expect(others.textContent).toMatch(/lining would be needed/);
    fireEvent.click(screen.getAllByText('Select Material').find((el) => others.contains(el)));
    expect(onSelect).toHaveBeenCalledWith('silk-chiffon', 'Silk Chiffon', 'woven');
    const bad = screen.getByTestId('incompatible-fabrics');
    expect(bad.textContent).toMatch(/Cotton Jersey Knit — A blouse is drafted on the woven block/);
    expect(screen.queryByTestId('fabric-cotton-jersey-knit')).toBeNull();   // not offered as a selectable card
  });

  it('replaces an incompatible previous choice with the top recommendation', async () => {
    const onSelect = vi.fn();
    renderIt({ onSelectFabric: onSelect, selectedFabricId: 'cotton-jersey-knit' });
    await waitFor(() => expect(onSelect).toHaveBeenCalledWith('cotton-poplin', 'Cotton Poplin', 'woven'));
  });

  it('shows the validation message and a retry on load failure', async () => {
    fabricAPI.getRecommendations.mockRejectedValueOnce(new Error('down'));
    renderIt({ validationError: 'Please choose a fabric before generating the pattern.' });
    expect(await screen.findByText(/could not be loaded/)).toBeInTheDocument();
    expect(screen.getByText('Please choose a fabric before generating the pattern.')).toBeInTheDocument();
    fireEvent.click(screen.getByText('Retry'));
    await screen.findByTestId('recommended-fabrics');
  });

  it('opens the details modal and closes on Escape', async () => {
    renderIt({ selectedFabricId: 'cotton-poplin' });
    await screen.findByTestId('recommended-fabrics');
    fireEvent.click(screen.getAllByText('View Details')[0]);
    await waitFor(() => {
      expect(screen.getByText('Why the system recommends it:')).toBeInTheDocument();
      expect(screen.getByText('Technical Details & Supplier Notes')).toBeInTheDocument();
    });
    fireEvent.keyDown(window, { key: 'Escape', code: 'Escape' });
    await waitFor(() => expect(screen.queryByText('Why the system recommends it:')).not.toBeInTheDocument());
  });

  it('handles an image loading error in the details modal with a fallback', () => {
    render(
      <FabricDetailsModal fabric={{ ...FABRICS[0], local_image: '/fabrics/broken-image.jpg' }}
                          isSelected={false} onSelect={() => {}} onClose={() => {}} />,
    );
    fireEvent.error(screen.getByAltText('Close-up fabric texture image of Cotton Poplin'));
    expect(screen.getByText('Texture Swatch')).toBeInTheDocument();
  });
});
