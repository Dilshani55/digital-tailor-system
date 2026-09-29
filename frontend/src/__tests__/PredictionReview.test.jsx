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

    // the model said three-quarter-sleeve, which is outside the selectable classes: the user must choose
    fireEvent.change(screen.getByTestId('select-sleeve_length'), { target: { value: 'long-sleeve' } });
    const confirmBtn = screen.getByTestId('confirm-btn');
    fireEvent.click(confirmBtn);

    expect(handleConfirm).toHaveBeenCalledWith({
      garment_type: 'crop-top',
      neckline_type: 'v-neck',
      sleeve_length: 'long-sleeve',
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

  it('renders manual selection fallback with empty selections when garmentAttributes is missing', () => {
    render(<PredictionReview garmentAttributes={null} />);

    expect(screen.getByTestId('fallback-notice')).toBeInTheDocument();
    expect(screen.getByTestId('select-garment_type')).toHaveValue('');
    expect(screen.getByTestId('select-neckline_type')).toHaveValue('');
    expect(screen.getByTestId('select-sleeve_length')).toHaveValue('');
    expect(screen.getByTestId('select-sleeve_style')).toHaveValue('');
    expect(screen.getByTestId('confirm-btn')).toBeDisabled();
  });
});

describe('predictions outside the supported scope (deployed M13 model still predicts 3/10/6/9)', () => {
  const top = (label, conf = 0.6) => ({
    label, class_index: 0, confidence: conf, requires_user_confirmation: false, threshold_used: 0.4,
    top_3: [{ class_name: label, class_index: 0, confidence: conf }],
  });
  const make = (over = {}) => ({
    model_version: 'M13-test',
    predictions: {
      garment_type: top('blouse', 0.9), neckline_type: top('round-neck'), sleeve_length: top('short-sleeve'),
      sleeve_style: top('regular-sleeve'), ...over,
    },
    low_confidence_heads: [], requires_user_confirmation: false,
  });
  const MESSAGE = 'The detected feature is outside the supported pattern scope. Please confirm the design manually.';

  it('supported predictions are pre-selected and raise no scope alert', () => {
    render(<PredictionReview garmentAttributes={make()} />);
    expect(screen.queryByTestId('outside-scope-alert')).toBeNull();
    expect(screen.getByTestId('select-neckline_type').value).toBe('round-neck');
    expect(screen.getByTestId('confirm-btn').disabled).toBe(false);
  });

  it.each([
    ['neckline_type', 'boat-neck'], ['neckline_type', 'scoop-neck'], ['sleeve_length', 'elbow-length'],
    ['sleeve_length', 'three-quarter-sleeve'], ['sleeve_style', 'bishop-sleeve'], ['sleeve_style', 'flutter-sleeve'],
  ])('%s = %s shows the exact message and is NOT remapped to a similar class', (head, label) => {
    render(<PredictionReview garmentAttributes={make({ [head]: top(label, 0.71) })} />);
    expect(screen.getByTestId('outside-scope-alert').textContent).toContain(MESSAGE);
    expect(screen.getByTestId(`outside-scope-${head}`).textContent).toContain(label);
    expect(screen.getByTestId(`outside-scope-${head}`).textContent).toContain('71%');   // genuine confidence still shown
    expect(screen.getByTestId(`select-${head}`).value).toBe('');                         // nothing pre-selected
    expect(screen.getByTestId('confirm-btn').disabled).toBe(true);                       // manual choice required
    expect(screen.getByTestId(`top-3-${head}`).textContent).toContain(label);            // raw prediction still visible
  });

  it('manual confirmation after an unsupported prediction sends only selectable values', () => {
    const onConfirm = vi.fn();
    render(<PredictionReview garmentAttributes={make({ neckline_type: top('boat-neck') })} onConfirm={onConfirm} />);
    fireEvent.change(screen.getByTestId('select-neckline_type'), { target: { value: 'square-neck' } });
    expect(screen.getByTestId('confirm-btn').disabled).toBe(false);
    fireEvent.click(screen.getByTestId('confirm-btn'));
    expect(onConfirm).toHaveBeenCalledWith({
      garment_type: 'blouse', neckline_type: 'square-neck', sleeve_length: 'short-sleeve', sleeve_style: 'regular-sleeve',
    });
  });

  it('offers exactly the 15 active classes in the dropdowns', () => {
    render(<PredictionReview garmentAttributes={make()} />);
    const count = (head) => screen.getByTestId(`select-${head}`).querySelectorAll('option').length - 1;   // minus placeholder
    expect([count('garment_type'), count('neckline_type'), count('sleeve_length'), count('sleeve_style')]).toEqual([3, 5, 3, 4]);
    expect(ACTIVE_TAXONOMY_OPTIONS.sleeve_length.map((o) => o.value)).not.toContain('elbow-length');
  });
});
