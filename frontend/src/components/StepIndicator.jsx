import { Check, RefreshCw } from 'lucide-react';

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

const STATUS_TEXT = { done: 'Completed', pending: 'Pending', stale: 'Needs update' };

/**
 * Progress indicator for the creation wizard. Every step can be opened at any time (entered data is kept);
 * `status` ({stepId: 'done' | 'pending' | 'stale'}) comes from the real wizard state, not from the order in
 * which the steps were visited. The actions inside a step (save, generate, export) do their own validation.
 */
export default function StepIndicator({ currentStep, setStep, status = {} }) {
  return (
    <nav className="wizard-steps" aria-label="Pattern creation progress">
      {WIZARD_STEPS.map((step) => {
        const state = status[step.id] || 'pending';
        const isActive = currentStep === step.id;
        const stateClass = isActive ? 'active' : state === 'done' ? 'done' : state === 'stale' ? 'stale' : 'idle';
        return (
          <button type="button" key={step.id} className={`wstep ${stateClass}`}
                  aria-current={isActive ? 'step' : undefined}
                  aria-label={`Step ${step.id}: ${step.label} (${STATUS_TEXT[state]})`}
                  data-status={state}
                  onClick={() => setStep && setStep(step.id)}>
            <span className="wstep-num" aria-hidden="true">
              {state === 'done' && !isActive ? <Check size={16} strokeWidth={3} />
                : state === 'stale' && !isActive ? <RefreshCw size={14} strokeWidth={2.6} /> : step.id}
            </span>
            <span className="wstep-lbl">{step.label}</span>
          </button>
        );
      })}
    </nav>
  );
}
