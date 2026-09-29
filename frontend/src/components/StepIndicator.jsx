export const WIZARD_STEPS = [
  { id: 1, label: 'Upload' },
  { id: 2, label: 'AI review' },
  { id: 3, label: 'Measurements' },
  { id: 4, label: 'Fabric & fit' },
  { id: 5, label: 'Pattern preview' },
  { id: 6, label: 'Fabric estimate' },
  { id: 7, label: 'PDF export' },
];

/**
 * Progress bar for the creation wizard. A step can be opened only if the user has already
 * reached it (maxStep), so nobody can skip the design confirmation or the measurements.
 */
export default function StepIndicator({ currentStep, setStep, maxStep = 1, pdfDownloaded = false }) {
  return (
    <nav className="wizard-steps" aria-label="Pattern creation progress">
      {WIZARD_STEPS.map((step) => {
        const reachable = step.id <= maxStep;
        const isDone = currentStep > step.id || (step.id === 7 && pdfDownloaded);
        const isActive = currentStep === step.id && !(step.id === 7 && pdfDownloaded);
        const stateClass = isDone ? 'done' : isActive ? 'active' : 'idle';
        return (
          <button
            type="button"
            key={step.id}
            className={`wstep ${stateClass}`}
            disabled={!reachable}
            aria-current={isActive ? 'step' : undefined}
            onClick={() => reachable && setStep && setStep(step.id)}
          >
            <span className="wstep-num">{isDone ? '✓' : step.id}</span>
            <span className="wstep-lbl">{step.label}</span>
          </button>
        );
      })}
    </nav>
  );
}
