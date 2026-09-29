import { useEffect, useRef, useState } from 'react';
import { authAPI } from '../../services/api';
import { friendlyError } from '../../utils/friendlyError';

const GIS_SRC = 'https://accounts.google.com/gsi/client';
export const googleClientId = () => import.meta.env.VITE_GOOGLE_CLIENT_ID || '';

/**
 * "Continue with Google" using Google Identity Services. The browser receives a signed ID token
 * from Google and the backend verifies it with Google before issuing a session. The button is
 * shown only when VITE_GOOGLE_CLIENT_ID is configured; otherwise nothing is rendered (no fake sign-in).
 */
export default function GoogleLoginButton({ onSuccess, onFailure, parentLoading }) {
  const clientId = googleClientId();
  const holder = useRef(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!clientId) return undefined;
    let cancelled = false;
    const init = () => {
      if (cancelled || !window.google?.accounts?.id || !holder.current) return;
      window.google.accounts.id.initialize({
        client_id: clientId,
        callback: async (resp) => {
          setBusy(true);
          try {
            const res = await authAPI.googleLogin({ credential: resp.credential });
            onSuccess(res.data);
          } catch (err) {
            onFailure(friendlyError(err, 'Google sign-in did not complete. Please try again.'));
          } finally {
            setBusy(false);
          }
        },
      });
      window.google.accounts.id.renderButton(holder.current, { theme: 'outline', size: 'large', width: 320, text: 'continue_with' });
    };
    if (window.google?.accounts?.id) {
      init();
    } else {
      const script = document.createElement('script');
      script.src = GIS_SRC;
      script.async = true;
      script.onload = init;
      script.onerror = () => onFailure('Google sign-in could not be loaded. Check your connection.');
      document.head.appendChild(script);
    }
    return () => { cancelled = true; };
  }, [clientId, onSuccess, onFailure]);

  if (!clientId) return null;
  return (
    <div aria-busy={busy || parentLoading} style={{ display: 'flex', justifyContent: 'center', opacity: busy || parentLoading ? 0.6 : 1 }}>
      <div ref={holder} />
    </div>
  );
}
