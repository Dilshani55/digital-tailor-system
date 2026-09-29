// Real upload + real M13 analysis: supported predictions are pre-selected; predictions outside the 15
// active classes are flagged (never remapped) and require manual confirmation.
import { test, expect } from '@playwright/test';
import path from 'node:path';

const API = process.env.E2E_API_URL || 'http://127.0.0.1:5055/api';
const IMG = (n) => path.resolve('../ai_training/data/eval_real_product_set/images', n);
const MESSAGE = 'The detected feature is outside the supported pattern scope. Please confirm the design manually.';

async function signIn(page, request) {
  const email = `e2e_scope_ai_${Date.now()}_${Math.floor(Math.random() * 1e6)}@example.test`;
  const res = await request.post(`${API}/auth/register`, { data: { full_name: 'Analysis Tester', email, password: 'E2e-Passw0rd!' } });
  expect(res.ok()).toBeTruthy();
  await page.goto('/auth');
  await page.locator('#login-email').fill(email);
  await page.locator('#login-password').fill('E2e-Passw0rd!');
  await page.getByRole('button', { name: 'Sign In' }).click();
  await page.waitForURL('**/dashboard', { timeout: 30_000 });
}

async function analyse(page, file) {
  await page.goto('/upload');
  await page.getByTestId('image-input').setInputFiles(IMG(file));
  await page.getByRole('button', { name: 'Upload and analyse' }).click();
  await expect(page.getByRole('heading', { name: 'Review the AI suggestion' })).toBeVisible({ timeout: 180_000 });
}

test('all four M13 predictions supported: pre-selected, no scope warning, confirm works unchanged', async ({ page, request }) => {
  await signIn(page, request);
  await analyse(page, 'blouse_19.jpg');            // M13: blouse / square-neck / long-sleeve / regular-sleeve
  await expect(page.getByTestId('outside-scope-alert')).toHaveCount(0);
  await expect(page.getByTestId('select-garment_type')).toHaveValue('blouse');
  await expect(page.getByTestId('select-neckline_type')).toHaveValue('square-neck');
  await expect(page.getByTestId('select-sleeve_length')).toHaveValue('long-sleeve');
  await expect(page.getByTestId('select-sleeve_style')).toHaveValue('regular-sleeve');
  for (const h of ['garment_type', 'neckline_type', 'sleeve_length', 'sleeve_style']) {
    await expect(page.getByTestId(`confidence-tag-${h}`)).toContainText('%');
  }
  await expect(page.getByTestId('confirm-btn')).toBeEnabled();
  await page.getByTestId('confirm-btn').click();
  await expect(page.getByTestId('confirmed-badge')).toBeVisible();
});

test('unsupported M13 predictions: exact message, nothing remapped, manual confirmation required', async ({ page, request }) => {
  await signIn(page, request);
  await analyse(page, 'blouse_02.jpg');            // M13: boat-neck / three-quarter-sleeve / flutter-sleeve
  await expect(page.getByTestId('outside-scope-alert')).toContainText(MESSAGE);
  for (const [head, label] of [['neckline_type', 'boat-neck'], ['sleeve_length', 'three-quarter-sleeve'], ['sleeve_style', 'flutter-sleeve']]) {
    await expect(page.getByTestId(`outside-scope-${head}`)).toContainText(label);          // genuine prediction still shown
    await expect(page.getByTestId(`select-${head}`)).toHaveValue('');                       // not replaced by a similar class
    await expect(page.getByTestId(`top-3-${head}`)).toContainText(label);
  }
  await expect(page.getByTestId('select-garment_type')).toHaveValue('blouse');             // the supported head is pre-selected
  await expect(page.getByTestId('confirm-btn')).toBeDisabled();

  // manual confirmation
  await page.getByTestId('select-neckline_type').selectOption('round-neck');
  await page.getByTestId('select-sleeve_length').selectOption('short-sleeve');
  await page.getByTestId('select-sleeve_style').selectOption('regular-sleeve');
  await expect(page.getByTestId('confirm-btn')).toBeEnabled();
  await page.getByTestId('confirm-btn').click();
  await expect(page.getByTestId('confirmed-badge')).toBeVisible();
  await page.getByRole('button', { name: 'Continue to measurements' }).click();
  await expect(page.getByRole('heading', { name: 'Body measurements' })).toBeVisible();

  // the API stored the genuine model output next to the user's choice (research evidence)
  const token = await page.evaluate(() => localStorage.getItem('token'));
  const list = await request.get(`${API}/images/`, { headers: { Authorization: `Bearer ${token}` } });
  const images = (await list.json()).images || [];
  const detail = await request.get(`${API}/images/${images[0].image_id}`, { headers: { Authorization: `Bearer ${token}` } });
  const body = await detail.json();
  expect(body.garment_attributes.predictions.neckline_type.label).toBe('boat-neck');
  expect(typeof body.garment_attributes.predictions.neckline_type.confidence).toBe('number');
  expect(body.confirmed_attributes.neckline_type).toBe('round-neck');
  expect(body.design_spec.provenance.neckline_type.source).toBe('user_corrected');
  expect(body.design_spec.provenance.neckline_type.predicted_label).toBe('boat-neck');
});
