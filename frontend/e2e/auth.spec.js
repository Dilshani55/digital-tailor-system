// Real stack: sign-in errors stay on screen, a session that is no longer valid signs the user out, the password
// is changed with the current one, and "forgot password" says honestly that there is no e-mail service.
import { test, expect } from '@playwright/test';

const API = process.env.E2E_API_URL || 'http://127.0.0.1:5075/api';
const OLD = 'E2e-Passw0rd!';
const NEW = 'E2e-N3w-Passw0rd!';

async function signIn(page, email, password) {
  await page.goto('/auth');
  await page.locator('#login-email').fill(email);
  await page.locator('#login-password').fill(password);
  await page.getByRole('button', { name: 'Sign In' }).click();
}

test('wrong password, invalid session, change password, forgot password', async ({ page, request }) => {
  const pageErrors = [];
  page.on('pageerror', (e) => pageErrors.push(e.message));
  const email = `e2e_auth_${Date.now()}@example.test`;
  expect((await request.post(`${API}/auth/register`, { data: { full_name: 'Auth Tester', email, password: OLD } })).ok()).toBeTruthy();

  // 1. a wrong password is reported on the form and the typed e-mail is kept (the page is not reloaded)
  await signIn(page, email, 'not-the-password');
  await expect(page.getByRole('alert')).toContainText(/Invalid email( address)? or password/i);
  await expect(page.locator('#login-email')).toHaveValue(email);
  await expect(page).toHaveURL(/\/auth$/);

  // 2. "forgot password" does not pretend to send an e-mail
  await page.getByRole('button', { name: 'Forgot password?' }).click();
  await expect(page.getByText(/no e-mail service/)).toBeVisible();
  await expect(page.getByText(/link has been sent|check your inbox/i)).toHaveCount(0);

  // 3. sign in, then the session becomes invalid (a token the server did not sign): the app signs out cleanly
  await page.locator('#login-password').fill(OLD);
  await page.getByRole('button', { name: 'Sign In' }).click();
  await page.waitForURL('**/dashboard', { timeout: 30_000 });
  const good = await page.evaluate(() => localStorage.getItem('token'));
  const [head, body] = good.split('.');
  await page.evaluate((t) => localStorage.setItem('token', t), `${head}.${body}.AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA`);
  await page.goto('/history');
  await page.waitForURL('**/auth', { timeout: 30_000 });
  expect(await page.evaluate(() => localStorage.getItem('token'))).toBeNull();
  const direct = await request.get(`${API}/patterns/`, { headers: { Authorization: `Bearer ${head}.${body}.AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA` } });
  expect([direct.status(), (await direct.json()).error_code]).toEqual([401, 'INVALID_TOKEN']);

  // 4. change the password under Settings: the current password is required
  await signIn(page, email, OLD);
  await page.waitForURL('**/dashboard', { timeout: 30_000 });
  await page.goto('/settings');
  await page.getByLabel('Current password').fill('not-the-password');
  await page.getByLabel('New password', { exact: true }).fill(NEW);
  await page.getByLabel('New password again').fill(NEW);
  await page.getByRole('button', { name: 'Change password' }).click();
  await expect(page.getByTestId('password-error')).toContainText(/current password is not correct/);
  await expect(page).toHaveURL(/\/settings$/);                       // a wrong current password does not sign the user out
  await page.getByLabel('Current password').fill(OLD);
  await page.getByRole('button', { name: 'Change password' }).click();
  await expect(page.getByTestId('password-done')).toContainText(/Password changed/);

  // 5. the old password no longer works, the new one does
  expect((await request.post(`${API}/auth/login`, { data: { email, password: OLD } })).status()).toBe(401);
  expect((await request.post(`${API}/auth/login`, { data: { email, password: NEW } })).status()).toBe(200);
  await page.evaluate(() => { localStorage.removeItem('token'); localStorage.removeItem('user'); });
  await signIn(page, email, NEW);
  await page.waitForURL('**/dashboard', { timeout: 30_000 });

  expect(pageErrors, pageErrors.join('\n')).toEqual([]);
});
