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

const mockRecommendations = [
  {
    id: 'cotton-poplin',
    name: 'Cotton Poplin',
    local_image: '/fabrics/cotton-poplin.jpg',
    simple_description: 'Crisp plain-weave cotton fabric.',
    feel: 'Smooth, crisp',
    weight: 'Light',
    stretch: 'No Stretch',
    breathability: 'High',
    drape: 'Crisp and structured',
    best_garment_uses: ['Structured crop-tops', 'Blouses'],
    climate_suitability: 'Exceptional for tropical weather',
    advantages: ['Holds crisp structured shapes', 'Highly breathable'],
    limitations: ['Prone to creasing'],
    care_instructions: 'Machine wash cold',
    sewing_difficulty: 'Beginner friendly',
    technical_details: {
      construction: 'Plain weave',
      typical_gsm_range: 'Typical GSM range: 110 - 130 GSM (varies by supplier)',
      price_note: 'Price varies by supplier'
    },
    recommendation_status: 'Best Match',
    explanation: 'This material is recommended because it is light weight and provides crisp structural body.'
  },
  {
    id: 'cotton-jersey-knit',
    name: 'Cotton Jersey Knit',
    local_image: '/fabrics/cotton-jersey-knit.jpg',
    simple_description: 'Flexible single-knit fabric.',
    feel: 'Soft, stretchy',
    weight: 'Medium',
    stretch: 'Stretchable',
    breathability: 'High',
    drape: 'Soft fluid knit drape',
    best_garment_uses: ['T-shirts', 'Fitted tops'],
    climate_suitability: 'Great for active daily wear',
    advantages: ['Excellent elasticity', 'Wrinkle-resistant'],
    limitations: ['Curled raw edges'],
    care_instructions: 'Machine wash warm',
    sewing_difficulty: 'Intermediate',
    technical_details: {
      construction: 'Single jersey knit',
      typical_gsm_range: 'Typical GSM range: 170 - 200 GSM (varies by supplier)',
      price_note: 'Price varies by supplier'
    },
    recommendation_status: 'Suitable',
    explanation: 'This material is recommended for flexible knit movement.'
  }
];

describe('FabricRecommendation Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    fabricAPI.getRecommendations.mockResolvedValue({
      data: { recommendations: mockRecommendations }
    });
  });

  it('renders fabric cards grid with recommendation badges and descriptions', async () => {
    const handleSelect = vi.fn();
    render(
      <FabricRecommendation
        detectedFeatures={{ garment_type: 'crop-top' }}
        selectedFabricId="cotton-poplin"
        onSelectFabric={handleSelect}
        validationError=""
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Recommended Materials for Your Design')).toBeInTheDocument();
      expect(screen.getByText('Cotton Poplin')).toBeInTheDocument();
      expect(screen.getByText('Cotton Jersey Knit')).toBeInTheDocument();
      expect(screen.getByText('★ Best Match')).toBeInTheDocument();
    });
  });

  it('handles material selection when card or select button is clicked', async () => {
    const handleSelect = vi.fn();
    render(
      <FabricRecommendation
        detectedFeatures={{ garment_type: 'crop-top' }}
        selectedFabricId="cotton-poplin"
        onSelectFabric={handleSelect}
        validationError=""
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Cotton Jersey Knit')).toBeInTheDocument();
    });

    const selectButtons = screen.getAllByText('Select Material');
    fireEvent.click(selectButtons[0]);

    expect(handleSelect).toHaveBeenCalledWith('cotton-jersey-knit', 'Cotton Jersey Knit', 'knit');
  });

  it('displays validation error message when user attempts to proceed without selection', async () => {
    render(
      <FabricRecommendation
        detectedFeatures={{ garment_type: 'crop-top' }}
        selectedFabricId=""
        onSelectFabric={() => {}}
        validationError="Please select a recommended fabric material for your garment design before proceeding."
      />
    );

    await waitFor(() => {
      expect(
        screen.getByText('Please select a recommended fabric material for your garment design before proceeding.')
      ).toBeInTheDocument();
    });
  });

  it('opens details modal when View Details button is clicked and closes on Escape', async () => {
    render(
      <FabricRecommendation
        detectedFeatures={{ garment_type: 'crop-top' }}
        selectedFabricId="cotton-poplin"
        onSelectFabric={() => {}}
        validationError=""
      />
    );

    await waitFor(() => {
      expect(screen.getAllByText('View Details')[0]).toBeInTheDocument();
    });

    fireEvent.click(screen.getAllByText('View Details')[0]);

    await waitFor(() => {
      expect(screen.getByText('Why the system recommends it:')).toBeInTheDocument();
      expect(screen.getByText('Technical Details & Supplier Notes')).toBeInTheDocument();
    });

    // Press Escape to close modal
    fireEvent.keyDown(window, { key: 'Escape', code: 'Escape' });

    await waitFor(() => {
      expect(screen.queryByText('Why the system recommends it:')).not.toBeInTheDocument();
    });
  });

  it('handles image loading error with graceful fallback UI', () => {
    render(
      <FabricDetailsModal
        fabric={{ ...mockRecommendations[0], local_image: '/fabrics/broken-image.jpg' }}
        isSelected={false}
        onSelect={() => {}}
        onClose={() => {}}
      />
    );

    const img = screen.getByAltText('Close-up fabric texture image of Cotton Poplin');
    fireEvent.error(img);

    expect(screen.getByText('Texture Swatch')).toBeInTheDocument();
  });
});
