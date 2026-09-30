import { Check } from 'lucide-react';

export const WIZARD_STEPS = [
  { id: 1, label: 'Customer & design' },
  { id: 2, label: 'Upload image' },
  { id: 3, label: 'AI review' },
  { id: 4, label: 'Measurements' },
  { id: 5, label: 'Fabric & fit' },
  { id: 6, label: 'Pattern preview' },
  { id: 7, label: 'Fabric estimate' },
  { id: 8, label: 'Download PDF' },
];
export const LAST_STEP = WIZARD_STEPS.length;

/**
 * Progress indicator for the creation wizard. A step can be opened only if the user has already
 * reached it (maxStep), so nobody can skip the design confirmation or the measurements.
 */
export default function StepIndicator({ currentStep, setStep, maxStep = 1, pdfDownloaded = false }) {
  return (
    <nav className="wizard-steps" aria-label="Pattern creation progress">
      {WIZARD_STEPS.map((step) => {
        const reachable = step.id <= maxStep;
        const isDone = currentStep > step.id || (step.id === LAST_STEP && pdfDownloaded);
        const isActive = currentStep === step.id && !(step.id === LAST_STEP && pdfDownloaded);
        const stateClass = isDone ? 'done' : isActive ? 'active' : 'idle';
        return (
          <button type="button" key={step.id} className={`wstep ${stateClass}`} disabled={!reachable}
                  aria-current={isActive ? 'step' : undefined}
                  aria-label={`Step ${step.id}: ${step.label}${isDone ? ' (done)' : ''}`}
                  onClick={() => reachable && setStep && setStep(step.id)}>
            <span className="wstep-num" aria-hidden="true">{isDone ? <Check size={16} strokeWidth={3} /> : step.id}</span>
            <span className="wstep-lbl">{step.label}</span>
          </button>
        );
      })}
    </nav>
  );
}
