// Real IndexedDB persistence and account isolation; no trained image models needed.
import { test, expect } from '@playwright/test';

const API = process.env.E2E_API_URL || 'http://127.0.0.1:5055/api';
const password = 'E2e-Passw0rd!';

async function account(request, label) {
  const email = `draft_${label}_${Date.now()}@example.test`;
  const registered = await request.post(`${API}/auth/register`, { data: { full_name: `Draft ${label}`, email, password } });
  expect(registered.ok()).toBeTruthy();
  const loggedIn = await request.post(`${API}/auth/login`, { data: { email, password } });
  expect(loggedIn.ok()).toBeTruthy();
  return loggedIn.json();
}

async function switchAccount(page, session) {
  await page.goto('/auth');
  await page.evaluate(({ token, user }) => {
    localStorage.setItem('token', token);
    localStorage.setItem('user', JSON.stringify(user));
  }, session);
  await page.goto('/upload');
}

test('drafts survive refresh/navigation, stay with their account, and clear on Start new pattern or Finish', async ({ page, request }) => {
  page.on('dialog', (dialog) => dialog.accept());
  const first = await account(request, 'first');
  const second = await account(request, 'second');
  await switchAccount(page, first);
  await page.getByLabel('Customer name').fill('First account customer');
  await page.getByRole('button', { name: /^Step 3:/ }).click();
  await page.getByTestId('select-garment_type').selectOption('blouse');
  await page.getByTestId('select-neckline_type').selectOption('v-neck');
  await page.getByRole('button', { name: /^Step 4:/ }).click();
  await page.getByTestId('unit-in').click();
  await page.locator('#meas-bust_cm').fill('38.5');
  await page.getByRole('button', { name: /^Step 5:/ }).click();
  await page.getByTestId('fit-loose').click();
  await page.reload();
  await expect(page.getByRole('heading', { name: 'Choose fabric and fit' })).toBeVisible();
  await expect(page.getByTestId('fit-loose')).toHaveAttribute('aria-pressed', 'true');

  await switchAccount(page, second);
  await expect(page.getByRole('heading', { name: 'Customer and design' })).toBeVisible();
  await expect(page.getByLabel('Customer name')).toHaveValue('');
  await page.getByLabel('Customer name').fill('Second account customer');
  await page.getByRole('button', { name: /^Step 3:/ }).click();
  await page.getByTestId('select-garment_type').selectOption('t-shirt');

  await switchAccount(page, first);
  await expect(page.getByRole('heading', { name: 'Choose fabric and fit' })).toBeVisible();
  await page.getByRole('button', { name: /^Step 1:/ }).click();
  await expect(page.getByLabel('Customer name')).toHaveValue('First account customer');
  await page.getByRole('button', { name: /^Step 3:/ }).click();
  await expect(page.getByTestId('select-garment_type')).toHaveValue('blouse');
  await expect(page.getByTestId('select-neckline_type')).toHaveValue('v-neck');
  await expect(page.getByTestId('confirm-btn')).toBeDisabled();
  await page.getByRole('button', { name: /^Step 4:/ }).click();
  await expect(page.locator('#meas-bust_cm')).toHaveValue('38.5');
  await page.getByTestId('unit-cm').click();
  await expect(page.locator('#meas-bust_cm')).toHaveValue('97.79');
  await page.reload();
  await expect(page.locator('#meas-bust_cm')).toHaveValue('97.79');
  await page.getByTestId('unit-in').click();
  await expect(page.locator('#meas-bust_cm')).toHaveValue('38.5');

  await page.getByRole('button', { name: 'Start new pattern' }).click();
  await expect(page.getByRole('heading', { name: 'Customer and design' })).toBeVisible();
  await page.reload();
  await expect(page.getByLabel('Customer name')).toHaveValue('');
  await page.getByLabel('Customer name').fill('Draft to finish');
  await page.getByRole('button', { name: /^Step 8:/ }).click();
  await page.getByRole('button', { name: 'Finish', exact: true }).click();
  await page.waitForURL('**/dashboard');
  await page.goto('/upload');
  await expect(page.getByLabel('Customer name')).toHaveValue('');

  await switchAccount(page, second);
  await expect(page.getByTestId('select-garment_type')).toHaveValue('t-shirt');
  await page.getByRole('button', { name: /^Step 1:/ }).click();
  await expect(page.getByLabel('Customer name')).toHaveValue('Second account customer');
});
