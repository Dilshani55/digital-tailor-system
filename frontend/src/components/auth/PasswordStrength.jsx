export default function PasswordStrength({ password }) {
  if (!password) return null;

  let strength = 'Weak';
  let color = '#EF4444'; // Red
  let percent = '33%';

  // Basic strength heuristic
  if (password.length >= 8) {
    const hasLetters = /[a-zA-Z]/.test(password);
    const hasNumbers = /[0-9]/.test(password);
    const hasSpecial = /[^a-zA-Z0-9]/.test(password);

    if (hasLetters && hasNumbers && hasSpecial) {
      strength = 'Strong';
      color = '#10B981'; // Emerald Green
      percent = '100%';
    } else if (hasLetters && hasNumbers) {
      strength = 'Medium';
      color = '#F59E0B'; // Orange
      percent = '66%';
    }
  }

  return (
    <div style={{ marginTop: '8px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '11px', marginBottom: '4px' }}>
        <span style={{ color: '#58534C' }}>Password strength:</span>
        <span style={{ fontWeight: '700', color }}>{strength}</span>
      </div>
      <div style={{ width: '100%', height: '5px', background: '#E5E0D8', borderRadius: '4px', overflow: 'hidden' }}>
        <div style={{ width: percent, height: '100%', background: color, transition: 'width 0.2s ease-in-out' }}></div>
      </div>
    </div>
  );
}
