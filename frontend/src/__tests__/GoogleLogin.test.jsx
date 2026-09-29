import { render } from '@testing-library/react';
import fs from 'node:fs';
import { fileURLToPath } from 'node:url';
import { afterEach, describe, expect, it, vi } from 'vitest';
import GoogleLoginButton from '../components/auth/GoogleLoginButton';

vi.mock('../services/api', () => ({ authAPI: { googleLogin: vi.fn() } }));

const source = (rel) => fs.readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8');

describe('Google sign-in', () => {
  afterEach(() => vi.unstubAllEnvs());

  it('renders nothing (no fake sign-in) when no Google client id is configured', () => {
    vi.stubEnv('VITE_GOOGLE_CLIENT_ID', '');
    const { container } = render(<GoogleLoginButton onSuccess={() => {}} onFailure={() => {}} />);
    expect(container.innerHTML).toBe('');
  });

  it('contains no hard-coded accounts or fake tokens', () => {
    const src = source('../components/auth/GoogleLoginButton.jsx');
    for (const fake of ['mock-google', '@gmail.com', 'nsbm.ac.lk', 'Math.random', 'setTimeout']) {
      expect(src).not.toContain(fake);
    }
  });
});
