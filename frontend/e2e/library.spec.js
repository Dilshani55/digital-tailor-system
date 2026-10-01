// Real stack: the dashboard, the customers page and the pattern library all show the SAME saved patterns.
// A saved pattern without a PDF is listed as "PDF pending"; deleting a PDF keeps the pattern; deleting a
// pattern updates every page; a failed request is shown as an error, never as an empty library or a zero.
import { test, expect } from '@playwright/test';

const API = process.env.E2E_API_URL || 'http://127.0.0.1:5055/api';
const PASSWORD = 'E2e-Passw0rd!';
const MEAS = {
  bust_cm: 88, waist_cm: 70, hip_cm: 94, height_cm: 162, neck_cm: 36, shoulder_cm: 12, across_back_cm: 34,
  back_waist_length_cm: 40, armhole_depth_cm: 20, garment_length_cm: 65, bicep_cm: 28, sleeve_cm: 24, wrist_cm: 16,
};
const DESIGN = { garment_type: 'blouse', neckline_type: 'round-neck', sleeve_length: 'short-sleeve', sleeve_style: 'regular-sleeve' };

const card = (page, name) => page.getByRole('button', { name });

test('dashboard, customers and library agree; PDF pending, PDF delete, pattern delete, load error', async ({ page, request }) => {
  const problems = [];
  let expectFailures = false;
  page.on('pageerror', (e) => problems.push(`pageerror: ${e.message}`));
  page.on('console', (m) => {
    if (m.type() !== 'error' || expectFailures) return;
    if (/accounts\.google|gsi\/client|Failed to load resource.*(google|gstatic)/i.test(m.text())) return;
    problems.push(`console: ${m.text()} (${m.location().url})`);
  });
  page.on('response', (r) => {
    if (r.status() >= 400 && !expectFailures) problems.push(`${r.status()} ${r.url()}`);
  });
  page.on('dialog', (d) => d.accept());

  const email = `e2e_library_${Date.now()}@example.test`;
  expect((await request.post(`${API}/auth/register`, { data: { full_name: 'Library Tester', email, password: PASSWORD } })).ok()).toBeTruthy();
  const token = (await (await request.post(`${API}/auth/login`, { data: { email, password: PASSWORD } })).json()).token;
  const auth = { Authorization: `Bearer ${token}` };

  // two saved patterns for one customer, made by the real engine; neither has a PDF yet
  const prof = await (await request.post(`${API}/measurements/`, { headers: auth, data: { client_name: 'Library Customer', unit: 'cm', fabric_type: 'woven', ...MEAS } })).json();
  const ids = [];
  for (const sleeve_length of ['short-sleeve', 'long-sleeve']) {
    const gen = await request.post(`${API}/patterns/generate`, { headers: auth, data: {
      measurement_id: prof.measurement_id, image_id: 'manual', fabric_id: 'cotton-poplin', confirmed_attributes: { ...DESIGN, sleeve_length },
    } });
    expect(gen.status()).toBe(201);
    ids.push((await gen.json()).pattern_id);
  }
  const [first, second] = ids;

  await page.goto('/auth');
  await page.locator('#login-email').fill(email);
  await page.locator('#login-password').fill(PASSWORD);
  await page.getByRole('button', { name: 'Sign In' }).click();
  await page.waitForURL('**/dashboard', { timeout: 30_000 });

  // 1. the three pages agree: 2 patterns, 0 PDFs, both listed as "PDF pending"
  await expect(card(page, /Patterns created/)).toContainText('2');
  await expect(card(page, /PDF guides/)).toContainText('0');
  await expect(card(page, /PDF guides/)).toContainText('2 saved patterns with PDF pending');
  await page.goto('/customers');
  await expect(page.getByTestId(`pattern-count-${prof.measurement_id}`)).toHaveText('2');
  await page.goto('/history');
  await expect(page.locator('.library-item')).toHaveCount(2);
  await expect(page.getByTestId(`pdf-status-${first}`)).toHaveText('PDF pending');
  await expect(page.getByTestId(`pdf-status-${second}`)).toHaveText('PDF pending');
  await expect(page.getByText('For Library Customer')).toHaveCount(2);

  // 2. create the pending PDF (real PDF generator) -> ready, downloadable; the dashboard follows
  const item = page.getByTestId(`library-item-${first}`);
  await item.getByRole('button', { name: 'Create PDF' }).click();
  await expect(page.getByTestId(`pdf-status-${first}`)).toHaveText('PDF ready');
  const download = page.waitForEvent('download');
  await item.getByRole('button', { name: 'Download PDF' }).click();
  expect((await download).suggestedFilename()).toMatch(/\.pdf$/);
  await page.goto('/dashboard');
  await expect(card(page, /Patterns created/)).toContainText('2');
  await expect(card(page, /PDF guides/)).toContainText('1');

  // 3. "Delete PDF only" keeps the pattern
  await page.goto('/history');
  await page.getByTestId(`library-item-${first}`).getByRole('button', { name: 'Delete PDF only' }).click();
  await expect(page.getByTestId(`pdf-status-${first}`)).toHaveText('PDF pending');
  await expect(page.locator('.library-item')).toHaveCount(2);
  expect((await (await request.get(`${API}/patterns/${first}`, { headers: auth })).json()).exports).toEqual([]);

  // 4. "Delete pattern" removes it everywhere; the customer and their measurements stay
  await page.getByTestId(`library-item-${first}`).getByRole('button', { name: 'Delete pattern' }).click();
  await expect(page.locator('.library-item')).toHaveCount(1);
  await expect(page.getByTestId(`library-item-${second}`)).toBeVisible();
  await page.goto('/dashboard');
  await expect(card(page, /Patterns created/)).toContainText('1');
  await page.goto('/customers');
  await expect(page.getByTestId(`pattern-count-${prof.measurement_id}`)).toHaveText('1');
  await expect(page.getByText('Library Customer')).toBeVisible();
  expect((await request.get(`${API}/measurements/${prof.measurement_id}`, { headers: auth })).ok()).toBeTruthy();

  // 5. the customer is deleted: their pattern is still listed and opens (customer simply not recorded)
  expect((await request.delete(`${API}/measurements/${prof.measurement_id}`, { headers: auth })).ok()).toBeTruthy();
  await page.goto('/history');
  await expect(page.getByTestId(`library-item-${second}`)).toContainText('Customer not recorded');
  await page.getByTestId(`library-item-${second}`).getByRole('button', { name: 'View pattern' }).click();
  await expect(page.getByTestId('pattern-preview')).toBeVisible();
  await expect(page.getByTestId('pdf-pending')).toBeVisible();
  await page.getByRole('button', { name: 'Create the PDF' }).click();           // PDF from the pattern's own saved measurements
  await expect(page.getByRole('button', { name: /^Download/ })).toBeVisible();

  expect(problems, problems.join('\n')).toEqual([]);

  // 6. a failed request is an error with a retry - not "your library is empty", not a zero
  expectFailures = true;
  await page.route('**/api/patterns/', (route) => route.fulfill({ status: 503, contentType: 'application/json', body: '{"error":"down"}' }));
  await page.goto('/history');
  await expect(page.getByTestId('library-error')).toBeVisible();
  await expect(page.getByText('Your pattern library is empty')).toHaveCount(0);
  await page.goto('/dashboard');
  await expect(card(page, /Patterns created/)).toContainText('—');
  await expect(page.getByText('No patterns yet')).toHaveCount(0);
  await page.unroute('**/api/patterns/');
  await page.getByRole('button', { name: 'Try again' }).click();
  await expect(card(page, /Patterns created/)).toContainText('1');
});
