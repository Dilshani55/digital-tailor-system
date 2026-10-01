import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import MeasurementGuide from '../components/MeasurementGuide';

// Mock Canvas and React Three Fiber to test R3F component cleanly in JSDOM
vi.mock('@react-three/fiber', () => ({
  Canvas: ({ children }) => <div data-testid="r3f-canvas">{children}</div>,
  useFrame: vi.fn(),
  useThree: () => ({ camera: {}, scene: {}, gl: {} })
}));

vi.mock('@react-three/drei', () => ({
  OrbitControls: () => <div data-testid="orbit-controls" />,
  useGLTF: vi.fn(() => ({ scene: { rotation: { y: 0 } } })),
  Html: ({ children }) => <div>{children}</div>
}));

describe('Interactive 3D Mannequin Viewer Component', () => {
  it('renders 3D mannequin viewer container with WebGL badge', () => {
    render(<MeasurementGuide activeField="bust_cm" />);
    expect(screen.getByText('Interactive 3D Female Mannequin Viewer & Protocol')).toBeInTheDocument();
    expect(screen.getByText('Real Three.js WebGL 3D')).toBeInTheDocument();
  });

  it('displays correct view labels for front, side, and back rotation angles', () => {
    render(<MeasurementGuide activeField="bust_cm" />);
    // Initial angle 0° -> FRONT VIEW (0°)
    expect(screen.getByText(/FRONT VIEW/i)).toBeInTheDocument();
  });

  it('updates view label and slider when preset view buttons are clicked', async () => {
    render(<MeasurementGuide activeField="bust_cm" />);

    const backButton = screen.getByText('Back (180°)');
    fireEvent.click(backButton);

    await waitFor(() => {
      expect(screen.getByText(/BACK VIEW \(180°\)/i)).toBeInTheDocument();
    });

    const rightButton = screen.getByText('Right (90°)');
    fireEvent.click(rightButton);

    await waitFor(() => {
      expect(screen.getByText(/RIGHT SIDE \(90°\)/i)).toBeInTheDocument();
    });
  });

  it('resets view angle to 0° when Reset button is clicked', async () => {
    render(<MeasurementGuide activeField="bust_cm" />);

    fireEvent.click(screen.getByText('Back (180°)'));
    await waitFor(() => {
      expect(screen.getByText(/BACK VIEW \(180°\)/i)).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Reset'));
    await waitFor(() => {
      expect(screen.getByText(/FRONT VIEW \(0°\)/i)).toBeInTheDocument();
    });
  });

  it('displays correct active field title and tailoring guidelines for bust, waist, hip, height', () => {
    const { rerender } = render(<MeasurementGuide activeField="bust_cm" />);
    expect(screen.getByText('Bust Circumference (Full Apex)')).toBeInTheDocument();

    rerender(<MeasurementGuide activeField="waist_cm" />);
    expect(screen.getByText('Waist Circumference (Natural Crease)')).toBeInTheDocument();

    rerender(<MeasurementGuide activeField="hip_cm" />);
    expect(screen.getByText('Hip Circumference (Fullest Buttocks)')).toBeInTheDocument();

    rerender(<MeasurementGuide activeField="height_cm" />);
    expect(screen.getByText('Total Body Height (Crown to Heel)')).toBeInTheDocument();
  });

  it('contains licensed 3D model attribution badge', () => {
    render(<MeasurementGuide activeField="bust_cm" />);
    expect(screen.getByText(/Licensed 3D Female Mannequin Model/i)).toBeInTheDocument();
    expect(screen.getByText(/CC-BY 4.0 Creative Commons Open Tailoring Asset/i)).toBeInTheDocument();
  });
});
