// Real stack: customer profile created in the UI (honest validation) -> a pattern drafted for that customer
// is linked to it -> the saved pattern opens without any research/tailor-estimate UI -> Settings shows the
// real AI model state.
import { test, expect } from '@playwright/test';

const API = process.env.E2E_API_URL || 'http://127.0.0.1:5055/api';
const PASSWORD = 'E2e-Passw0rd!';
const MEAS = {
  bust_cm: 88, waist_cm: 70, hip_cm: 94, shoulder_width_cm: 37, back_waist_length_cm: 40, shoulder_to_bust_cm: 25,
  waist_to_hip_cm: 20, garment_length_cm: 65, bicep_cm: 28, sleeve_cm: 24, sleeve_end_cm: 27,
};

async function uiSignIn(page, email) {
  await page.goto('/auth');
  await page.locator('#login-email').fill(email);
  await page.locator('#login-password').fill(PASSWORD);
  await page.getByRole('button', { name: 'Sign In' }).click();
  await page.waitForURL('**/dashboard', { timeout: 30_000 });
}

function watchProblems(page) {
  const problems = [];
  page.on('pageerror', (e) => problems.push(`pageerror: ${e.message}`));
  page.on('response', (r) => {
    if (r.url().includes('/api/') && r.status() >= 400) problems.push(`api ${r.status()} ${r.url()}`);
  });
  return problems;
}

test('customer -> linked pattern -> saved pattern -> settings', async ({ page, request }) => {
  const problems = watchProblems(page);
  const email = `e2e_eval_${Date.now()}@example.test`;
  expect((await request.post(`${API}/auth/register`, { data: { full_name: 'Eval Tester', email, password: PASSWORD } })).ok()).toBeTruthy();
  const token = (await (await request.post(`${API}/auth/login`, { data: { email, password: PASSWORD } })).json()).token;
  const auth = { Authorization: `Bearer ${token}` };

  await uiSignIn(page, email);

  // 1. customer created in the UI; measurements are optional but must be numbers greater than 0
  await page.goto('/customers');
  await page.getByRole('button', { name: 'Add customer' }).click();
  await page.getByLabel('Full Name').fill('Walk-in A');
  await page.getByLabel('Bust around (cm)', { exact: true }).fill('0');
  await page.getByRole('button', { name: 'Save Customer' }).click();
  await expect(page.getByTestId('customer-form-error')).toContainText('greater than 0');   // honest validation
  for (const [label, v] of [['Bust around (cm)', 90], ['Waist around (cm)', 72], ['Hip around (cm)', 96], ['Shoulder to shoulder (cm)', 38]]) {
    await page.getByLabel(label, { exact: true }).fill(String(v));
  }
  await page.getByRole('button', { name: 'Save Customer' }).click();
  await expect(page.getByText('Walk-in A').first()).toBeVisible();
  await expect(page.getByText(/@email\.com/)).toHaveCount(0);

  // 2. a full profile + a pattern generated for it (manual design, real engine)
  const prof = await (await request.post(`${API}/measurements/`, { headers: auth, data: { client_name: 'Customer B', unit: 'cm', fabric_type: 'woven', ...MEAS } })).json();
  const gen = await request.post(`${API}/patterns/generate`, { headers: auth, data: {
    measurement_id: prof.measurement_id, image_id: 'manual', fabric_id: 'cotton-poplin', fabric_name: 'Cotton Poplin',
    confirmed_attributes: { garment_type: 'blouse', neckline_type: 'round-neck', sleeve_length: 'short-sleeve', sleeve_style: 'regular-sleeve' },
  } });
  expect(gen.status()).toBe(201);
  const patternId = (await gen.json()).pattern_id;

  await page.goto('/customers');
  await expect(page.getByTestId(`pattern-count-${prof.measurement_id}`)).toHaveText('1');

  // 3. the saved pattern opens with its geometry and no research / tailor-estimate features
  await page.goto(`/patterns/${patternId}`);
  await expect(page.getByTestId('pattern-preview')).toBeVisible();
  await expect(page.getByText(/traditional|tailor.?s estimate/i)).toHaveCount(0);
  // the stored pattern keeps its own calculations: block dimensions, the sleeve check and "Why this size?"
  await page.getByTestId('tab-back_bodice').click();
  await expect(page.getByTestId('block-back_bodice')).toBeVisible();
  await page.getByTestId('tab-sleeve').click();
  await expect(page.getByTestId('sleeve-cap-status')).toContainText(/^PASS/);
  await expect(page.getByTestId('why-this-size')).toContainText('Front width at the bust line');

  // 4. settings reports the real model state, no invented server status
  await page.goto('/settings');
  await expect(page.getByTestId('model-state')).toContainText(/Available|Not available/);
  await expect(page.getByText(/ONLINE & CONNECTED/)).toHaveCount(0);

  expect(problems, problems.join('\n')).toEqual([]);
});
