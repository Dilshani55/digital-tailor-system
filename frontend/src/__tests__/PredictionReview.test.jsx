import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import PredictionReview, { ACTIVE_TAXONOMY_OPTIONS } from '../components/PredictionReview';

describe('PredictionReview Component', () => {
  const mockGarmentAttributes = {
    model_version: 'YOLOv8MultiTaskClassifier_v1.0',
    predictions: {
      garment_type: {
        label: 'crop-top',
        class_index: 2,
        confidence: 0.9559,
        top_3: [
          { class_name: 'crop-top', class_index: 2, confidence: 0.9559 },
          { class_name: 't-shirt', class_index: 1, confidence: 0.0439 },
          { class_name: 'blouse', class_index: 0, confidence: 0.0001 },
        ],
        requires_user_confirmation: false,
        threshold_used: 0.7,
      },
      neckline_type: {
        label: 'v-neck',
        class_index: 1,
        confidence: 0.5026,
        top_3: [
          { class_name: 'v-neck', class_index: 1, confidence: 0.5026 },
          { class_name: 'sweetheart-neck', class_index: 5, confidence: 0.1926 },
        ],
        requires_user_confirmation: false,
        threshold_used: 0.45,
      },
      sleeve_length: {
        label: 'three-quarter-sleeve',
        class_index: 4,
        confidence: 0.3847,
        top_3: [
          { class_name: 'three-quarter-sleeve', class_index: 4, confidence: 0.3847 },
          { class_name: 'long-sleeve', class_index: 5, confidence: 0.2945 },
        ],
        requires_user_confirmation: true,
        threshold_used: 0.5,
      },
      sleeve_style: {
        label: 'bell-sleeve',
        class_index: 3,
        confidence: 0.5942,
        top_3: [
          { class_name: 'bell-sleeve', class_index: 3, confidence: 0.5942 },
          { class_name: 'flutter-sleeve', class_index: 5, confidence: 0.1294 },
        ],
        requires_user_confirmation: false,
        threshold_used: 0.4,
      },
    },
    low_confidence_heads: ['sleeve_length'],
    requires_user_confirmation: true,
  };

  it('renders all four predicted heads', () => {
    render(<PredictionReview garmentAttributes={mockGarmentAttributes} />);

    expect(screen.getByTestId('head-card-garment_type')).toBeInTheDocument();
    expect(screen.getByTestId('head-card-neckline_type')).toBeInTheDocument();
    expect(screen.getByTestId('head-card-sleeve_length')).toBeInTheDocument();
    expect(screen.getByTestId('head-card-sleeve_style')).toBeInTheDocument();
  });

  it('displays confidence percentages and low-confidence warning', () => {
    render(<PredictionReview garmentAttributes={mockGarmentAttributes} />);

    expect(screen.getByTestId('confidence-tag-garment_type')).toHaveTextContent('95.6% High');
    expect(screen.getByTestId('confidence-tag-sleeve_length')).toHaveTextContent('38.5% Low');
    expect(screen.getByTestId('low-confidence-alert')).toBeInTheDocument();
    expect(screen.getByTestId('low-confidence-alert')).toHaveTextContent('Sleeve Length');
  });

  it('allows editing predicted values in select controls', () => {
    render(<PredictionReview garmentAttributes={mockGarmentAttributes} />);

    const selectGarment = screen.getByTestId('select-garment_type');
    expect(selectGarment.value).toBe('crop-top');

    fireEvent.change(selectGarment, { target: { value: 'blouse' } });
    expect(selectGarment.value).toBe('blouse');
  });

  it('calls onConfirm callback with user selections when confirmed', () => {
    const handleConfirm = vi.fn();
    render(<PredictionReview garmentAttributes={mockGarmentAttributes} onConfirm={handleConfirm} />);

    const confirmBtn = screen.getByTestId('confirm-btn');
    fireEvent.click(confirmBtn);

    expect(handleConfirm).toHaveBeenCalledWith({
      garment_type: 'crop-top',
      neckline_type: 'v-neck',
      sleeve_length: 'three-quarter-sleeve',
      sleeve_style: 'bell-sleeve',
    });
  });

  it('displays confirmed badge and edit & re-confirm button when confirmed', () => {
    const confirmedData = {
      garment_type: 'blouse',
      neckline_type: 'round-neck',
      sleeve_length: 'short-sleeve',
      sleeve_style: 'regular-sleeve',
    };

    render(
      <PredictionReview
        garmentAttributes={mockGarmentAttributes}
        confirmedAttributes={confirmedData}
      />
    );

    expect(screen.getByTestId('confirmed-badge')).toBeInTheDocument();
    expect(screen.getByTestId('edit-reconfirm-btn')).toBeInTheDocument();
  });

  it('rejects removed cold-shoulder-sleeve from options list', () => {
    const allOptionValues = Object.values(ACTIVE_TAXONOMY_OPTIONS)
      .flat()
      .map((opt) => opt.value);

    expect(allOptionValues).not.toContain('cold-shoulder-sleeve');
    expect(allOptionValues).not.toContain('cold_shoulder_sleeve');
  });

  it('renders manual selection fallback when garmentAttributes is missing', () => {
    render(<PredictionReview garmentAttributes={null} />);

    expect(screen.getByTestId('fallback-notice')).toBeInTheDocument();
    expect(screen.getByTestId('confirm-btn')).toBeInTheDocument();
  });
});
