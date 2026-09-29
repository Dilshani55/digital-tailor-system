// Real stack: customer profile -> pattern linked to that customer -> traditional-vs-system fabric
// comparison (system value recomputed by the real nesting) -> researcher summary; plus the honest
// AI model status in Settings. The researcher account must be listed in the backend's
// RESEARCHER_EMAILS (default for this test: e2e_researcher@example.test).
import { test, expect } from '@playwright/test';

const API = process.env.E2E_API_URL || 'http://127.0.0.1:5055/api';
const RESEARCHER = process.env.E2E_RESEARCHER_EMAIL || 'e2e_researcher@example.test';
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

test('customer -> linked pattern -> traditional estimate comparison -> researcher summary', async ({ page, request, browser }) => {
  const problems = watchProblems(page);
  const email = `e2e_eval_${Date.now()}@example.test`;
  expect((await request.post(`${API}/auth/register`, { data: { full_name: 'Eval Tester', email, password: PASSWORD } })).ok()).toBeTruthy();
  await request.post(`${API}/auth/register`, { data: { full_name: 'E2E Researcher', email: RESEARCHER, password: PASSWORD } }); // may already exist
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

  // 3. traditional estimate on the saved pattern; system value recomputed for the same width
  await page.goto(`/patterns/${patternId}`);
  const cmp = page.getByTestId('fabric-comparison');
  await expect(cmp.getByText('No comparison recorded for this pattern yet.')).toBeVisible();
  await cmp.getByLabel('Fabric width').selectOption('150');
  await cmp.getByLabel('Traditional estimate (m)').fill('2');
  await cmp.getByLabel('Estimator label (optional)').fill('Tailor A');
  await cmp.getByRole('button', { name: 'Save comparison' }).click();
  await expect(cmp.getByTestId('comparison-table')).toContainText('Tailor A');
  const stored = (await (await request.get(`${API}/research/fabric-comparisons?pattern_id=${patternId}`, { headers: auth })).json()).comparisons;
  expect(stored).toHaveLength(1);
  const est = await (await request.post(`${API}/export/yardage/${patternId}`, { headers: auth, data: { fabric_width_cm: 150, cutting_mode: 'auto' } })).json();
  expect(stored[0].system_purchase_m).toBe(est.purchasing_recommended_m);          // same real nesting result
  expect(stored[0].difference_m).toBeCloseTo(2 - est.purchasing_recommended_m, 3);
  await expect(cmp.getByTestId('comparison-table')).toContainText(`${est.purchasing_recommended_m} m`);

  // 4. settings reports the real model state, no invented server status
  await page.goto('/settings');
  await expect(page.getByTestId('model-state')).toContainText(/Available|Not available/);
  await expect(page.getByText(/ONLINE & CONNECTED/)).toHaveCount(0);

  // 5. the researcher sees the comparison in the study summary (pseudonymised elsewhere)
  const ctx = await browser.newContext();
  const rpage = await ctx.newPage();
  const rproblems = watchProblems(rpage);
  await uiSignIn(rpage, RESEARCHER);
  await rpage.goto('/researcher');
  const summary = rpage.getByTestId('fabric-comparison-summary');
  await expect(summary).toBeVisible({ timeout: 20_000 });
  await expect(summary).not.toContainText('no traditional estimate has been recorded');
  await expect(summary).toContainText(/Comparisons \(patterns\)\d+ \(\d+\)/);   // study-wide count (grows across runs)
  await ctx.close();

  expect(problems.filter((p) => !/\/auth\/register/.test(p)), problems.join('\n')).toEqual([]);
  expect(rproblems, rproblems.join('\n')).toEqual([]);
});
