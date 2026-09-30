export default function LoadingSpinner({ message = 'Loading…' }) {
  return (
    <div className="loading" role="status" aria-live="polite">
      <span className="spinner" aria-hidden="true" />
      <p>{message}</p>
    </div>
  );
}
