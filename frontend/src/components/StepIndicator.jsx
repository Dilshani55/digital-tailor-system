export default function StepIndicator({ currentStep, setStep, pdfDownloaded }) {
  const steps = [
    { id: 1, label: 'Upload design' },
    { id: 2, label: 'Measurements' },
    { id: 3, label: 'Generate pattern' },
    { id: 4, label: 'Download PDF' },
  ];

  return (
    <div className="wizard-steps">
      {steps.map((step) => {
        const isDone = currentStep > step.id || (step.id === 4 && pdfDownloaded);
        const isActive = currentStep === step.id && !(step.id === 4 && pdfDownloaded);
        const stateClass = isDone ? 'done' : isActive ? 'active' : 'idle';

        return (
          <div
            key={step.id}
            className={`wstep ${stateClass}`}
            style={{ cursor: 'pointer' }}
            onClick={() => setStep && setStep(step.id)}
          >
            <div className="wstep-num">
              {isDone ? '✓' : step.id}
            </div>
            <div className="wstep-lbl">{step.label}</div>
          </div>
        );
      })}
    </div>
  );
}
