export default function PasswordStrength({ password }) {
  if (!password) return null;
  let strength = 'Weak';
  let color = '#b23b3b';
  let percent = '33%';
  if (password.length >= 8) {
    const letters = /[a-zA-Z]/.test(password);
    const numbers = /[0-9]/.test(password);
    const special = /[^a-zA-Z0-9]/.test(password);
    if (letters && numbers && special) { strength = 'Strong'; color = '#2c5b45'; percent = '100%'; }
    else if (letters && numbers) { strength = 'Medium'; color = '#b7791f'; percent = '66%'; }
  }
  return (
    <div className="strength" aria-live="polite">
      <span>Password strength: <strong style={{ color }}>{strength}</strong></span>
      <div className="strength-track"><i style={{ width: percent, background: color }} /></div>
    </div>
  );
}
