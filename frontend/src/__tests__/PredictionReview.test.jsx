import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import PredictionReview, { ACTIVE_TAXONOMY_OPTIONS } from '../components/PredictionReview';

describe('PredictionReview Component', () => {
  const mockGarmentAttributes = {
    model_version: 'YOLOv8MultiTaskClassifier_v1.0',
    predictions: {
      garment_type: {
        label: 'blouse',
        class_index: 0,
        confidence: 0.9559,
        top_3: [
          { class_name: 'blouse', class_index: 0, confidence: 0.9559 },
          { class_name: 't-shirt', class_index: 1, confidence: 0.0441 },
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
        label: 'puff-sleeve',
        class_index: 1,
        confidence: 0.5942,
        top_3: [
          { class_name: 'puff-sleeve', class_index: 1, confidence: 0.5942 },
          { class_name: 'regular-sleeve', class_index: 0, confidence: 0.4058 },
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

    expect(screen.getByTestId('confidence-tag-garment_type')).toHaveTextContent('Model score 95.6%');
    expect(screen.getByTestId('confidence-tag-sleeve_length')).toHaveTextContent('Model score 38.5% · uncertain');
    expect(screen.getByTestId('low-confidence-alert')).toBeInTheDocument();
    expect(screen.getByTestId('low-confidence-alert')).toHaveTextContent('Sleeve Length');
    expect(screen.getByTestId('low-confidence-sleeve_length')).toHaveTextContent('Uncertain — please select');
    expect(screen.queryByTestId('low-confidence-garment_type')).toBeNull();
  });

  it('allows editing predicted values in select controls', () => {
    render(<PredictionReview garmentAttributes={mockGarmentAttributes} />);

    const selectGarment = screen.getByTestId('select-garment_type');
    expect(selectGarment.value).toBe('blouse');

    fireEvent.change(selectGarment, { target: { value: 't-shirt' } });
    expect(selectGarment.value).toBe('t-shirt');
  });

  it('calls onConfirm callback with user selections when confirmed', () => {
    const handleConfirm = vi.fn();
    render(<PredictionReview garmentAttributes={mockGarmentAttributes} onConfirm={handleConfirm} />);

    // the model said three-quarter-sleeve (outside the selectable classes): not pre-selected, the user must
    // choose; its puff-sleeve prediction is draftable for a blouse and is kept
    expect(screen.getByTestId('select-sleeve_length').value).toBe('');
    expect(screen.getByTestId('select-sleeve_style').value).toBe('puff-sleeve');
    fireEvent.change(screen.getByTestId('select-sleeve_length'), { target: { value: 'short-sleeve' } });
    const confirmBtn = screen.getByTestId('confirm-btn');
    fireEvent.click(confirmBtn);

    expect(handleConfirm).toHaveBeenCalledWith({
      garment_type: 'blouse',
      neckline_type: 'v-neck',
      sleeve_length: 'short-sleeve',
      sleeve_style: 'puff-sleeve',
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

  it('offers exactly the selectable classes in the dropdowns (2 / 4 / 3 / 3)', () => {
    render(<PredictionReview garmentAttributes={make()} />);
    const count = (head) => screen.getByTestId(`select-${head}`).querySelectorAll('option').length - 1;   // minus placeholder
    expect([count('garment_type'), count('neckline_type'), count('sleeve_length'), count('sleeve_style')]).toEqual([2, 4, 3, 3]);
    expect(ACTIVE_TAXONOMY_OPTIONS.sleeve_length.map((o) => o.value)).not.toContain('elbow-length');
  });
});

describe('uncertain predictions and honest score wording', () => {
  const p = (label, confidence, uncertain) => ({
    label, class_index: 0, confidence, uncertain, requires_user_confirmation: uncertain, threshold_used: 0.6,
    top_3: [{ class_name: label, class_index: 0, confidence }],
  });
  const make = (over = {}) => ({
    model_version: 'M-test',
    predictions: {
      garment_type: p('blouse', 0.93, false), neckline_type: p('round-neck', 0.9, false),
      sleeve_length: p('short-sleeve', 0.88, false), sleeve_style: p('regular-sleeve', 0.8, false), ...over,
    },
    low_confidence_heads: [], requires_user_confirmation: false,
  });

  it('an uncertain head is shown but NOT pre-selected, and says "please select"', () => {
    render(<PredictionReview garmentAttributes={make({ neckline_type: p('v-neck', 0.41, true) })} />);
    expect(screen.getByTestId('select-neckline_type').value).toBe('');
    const note = screen.getByTestId('low-confidence-neckline_type').textContent;
    expect(note).toMatch(/Uncertain — please select/);
    expect(note).toMatch(/V-Neck/);
    expect(note).toMatch(/41\.0%/);
    expect(screen.getByTestId('confirm-btn').disabled).toBe(true);
    expect(screen.getByTestId('select-garment_type').value).toBe('blouse');         // certain heads still pre-selected
  });

  it('says why when the neck area or the sleeve was not found in the photo', () => {
    render(<PredictionReview garmentAttributes={make({
      neckline_type: { ...p('v-neck', 0.97, true), part_found: false },
      sleeve_style: { ...p('puff-sleeve', 0.9, true), part_found: false },
    })} />);
    expect(screen.getByTestId('select-neckline_type').value).toBe('');                // a high score does not help
    expect(screen.getByTestId('low-confidence-neckline_type').textContent).toMatch(/neck area could not be found/);
    expect(screen.getByTestId('low-confidence-sleeve_style').textContent).toMatch(/sleeve could not be found/);
  });

  it('every head shows its own model score; a high score is not called "confident" or proof', () => {
    render(<PredictionReview garmentAttributes={make()} />);
    ['garment_type', 'neckline_type', 'sleeve_length', 'sleeve_style'].forEach((h) => {
      expect(screen.getByTestId(`confidence-tag-${h}`).textContent).toMatch(/^Model score \d+(\.\d)?%$/);
    });
    expect(document.body.textContent).not.toMatch(/High confidence|Confident|Verified/);
    expect(document.body.textContent).toMatch(/not proof/);
  });

  it('the user can correct an uncertain head and then confirm', () => {
    const onConfirm = vi.fn();
    render(<PredictionReview garmentAttributes={make({ sleeve_length: p('long-sleeve', 0.4, true) })} onConfirm={onConfirm} />);
    fireEvent.change(screen.getByTestId('select-sleeve_length'), { target: { value: 'short-sleeve' } });
    fireEvent.click(screen.getByTestId('confirm-btn'));
    expect(onConfirm).toHaveBeenCalledWith({
      garment_type: 'blouse', neckline_type: 'round-neck', sleeve_length: 'short-sleeve', sleeve_style: 'regular-sleeve' });
  });

  it('explains the difference between a blouse and a T-shirt', () => {
    render(<PredictionReview garmentAttributes={make({ garment_type: p('t-shirt', 0.95, false) })} />);
    expect(screen.getByTestId('garment-length-note').textContent).toMatch(/blouse is cut from woven fabric.*T-shirt from knit/);
    expect(screen.getByTestId('select-garment_type').value).toBe('t-shirt');
  });

  it('a stored prediction of a class that no longer exists (crop top) is shown but never pre-selected', () => {
    render(<PredictionReview garmentAttributes={make({ garment_type: p('crop-top', 0.95, false) })} />);
    expect(screen.getByTestId('select-garment_type').value).toBe('');
    expect(screen.getByTestId('outside-scope-garment_type').textContent).toMatch(/crop-top/);
    expect(screen.getByTestId('confirm-btn').disabled).toBe(true);
  });
});
