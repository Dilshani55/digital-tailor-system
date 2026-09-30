import { useState } from 'react';
import { Eye, EyeOff, Lock } from 'lucide-react';

export default function PasswordInput({ id, name, value, onChange, placeholder, required, autoComplete, invalid }) {
  const [show, setShow] = useState(false);
  return (
    <div className="password-wrap input-icon">
      <Lock size={17} aria-hidden="true" />
      <input id={id} type={show ? 'text' : 'password'} name={name} value={value} onChange={onChange}
             placeholder={placeholder} required={required} autoComplete={autoComplete}
             aria-invalid={invalid ? 'true' : 'false'} className="glass-input" />
      <button type="button" className="password-toggle" aria-label={show ? 'Hide password' : 'Show password'} onClick={() => setShow(!show)}>
        {show ? <EyeOff size={18} /> : <Eye size={18} />}
      </button>
    </div>
  );
}
