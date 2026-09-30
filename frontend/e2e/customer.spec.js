// Real stack: customer profile created in the UI (honest validation) -> a pattern drafted for that customer
// is linked to it -> the saved pattern opens without any research/tailor-estimate UI -> Settings shows the
// real AI model state.
import { test, expect } from '@playwright/test';

const API = process.env.E2E_API_URL || 'http://127.0.0.1:5055/api';
const PASSWORD = 'E2e-Passw0rd!';
const MEAS = {
  bust_cm: 88, waist_cm: 70, hip_cm: 94, height_cm: 162, neck_cm: 36, shoulder_cm: 12, across_back_cm: 34,
  back_waist_length_cm: 40, armhole_depth_cm: 20, garment_length_cm: 65, bicep_cm: 28, sleeve_cm: 55, wrist_cm: 16,
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

  // 1. customer created in the UI with the four core measurements
  await page.goto('/customers');
  await page.getByRole('button', { name: 'Add customer' }).click();
  await page.getByLabel('Full Name').fill('Walk-in A');
  await page.getByRole('button', { name: 'Save Customer' }).click();
  await expect(page.getByTestId('customer-form-error')).toContainText('Bust is required');   // honest validation
  for (const [label, v] of [['Bust (cm)', 90], ['Waist (cm)', 72], ['Hip (cm)', 96], ['Height (cm)', 160]]) {
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

  // 4. settings reports the real model state, no invented server status
  await page.goto('/settings');
  await expect(page.getByTestId('model-state')).toContainText(/Available|Not available/);
  await expect(page.getByText(/ONLINE & CONNECTED/)).toHaveCount(0);

  expect(problems, problems.join('\n')).toEqual([]);
});
