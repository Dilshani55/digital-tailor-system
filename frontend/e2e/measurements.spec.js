// Real browser, real backend: typing, decimals, cm/in, save, reload and edit on the Measurements page and in the
// wizard; and every wizard step opened directly shows its own controls (no invented results).
import { test, expect } from '@playwright/test';

const API = process.env.E2E_API_URL || 'http://127.0.0.1:5075/api';
const SHOTS = process.env.E2E_SHOT_DIR;
const PASSWORD = 'E2e-Passw0rd!';
// set E2E_VIEWPORT=390x844 to run the same checks at phone size
const [VW, VH] = (process.env.E2E_VIEWPORT || '').split('x').map(Number);
if (VW && VH) test.use({ viewport: { width: VW, height: VH } });

function watch(page) {
  const problems = [];
  page.on('pageerror', (e) => problems.push(`pageerror: ${e.message}`));
  page.on('console', (m) => {
    if (m.type() !== 'error') return;
    // Google sign-in script and web fonts come from the internet; a slow network is not an app error
    if (/accounts\.google|gsi\/client|Failed to load resource.*(google|gstatic)/i.test(`${m.text()} ${m.location().url}`)) return;
    problems.push(`console: ${m.text()} (${m.location().url})`);
  });
  page.on('response', (r) => { if (r.url().includes('/api/') && r.status() >= 400) problems.push(`api ${r.status()} ${r.url()}`); });
  return problems;
}

async function account(page, request, tag) {
  const email = `e2e_${tag}_${Date.now()}@example.test`;
  expect((await request.post(`${API}/auth/register`, { data: { full_name: 'Measure Tester', email, password: PASSWORD } })).ok()).toBeTruthy();
  const token = (await (await request.post(`${API}/auth/login`, { data: { email, password: PASSWORD } })).json()).token;
  await page.goto('/auth');
  await page.locator('#login-email').fill(email);
  await page.locator('#login-password').fill(PASSWORD);
  await page.getByRole('button', { name: 'Sign In' }).click();
  await page.waitForURL('**/dashboard', { timeout: 30_000 });
  return { Authorization: `Bearer ${token}` };
}

// type one key at a time, like a person, and return what the field showed after each key
async function typeSlowly(field, text) {
  await field.click();
  await field.press('Control+a');
  await field.press('Delete');
  const seen = [];
  for (const ch of text) {
    await field.pressSequentially(ch);
    seen.push(await field.inputValue());
  }
  return seen;
}
const shot = async (page, name) => { if (SHOTS) await page.screenshot({ path: `${SHOTS}/${name}.png`, fullPage: true }); };
// the app scrolls inside its own content area; the browser page itself must never scroll (no blank area below the app)
const pageOverflow = (page) => page.evaluate(() => document.documentElement.scrollHeight - window.innerHeight);

test('Measurements page: typing, decimals, cm/in, save, reload, edit', async ({ page, request }) => {
  const problems = watch(page);
  const auth = await account(page, request, 'meas');
  const profile = async () => (await (await request.get(`${API}/measurements/`, { headers: auth })).json()).measurements[0];

  await page.goto('/measurements');
  const bust = page.locator('#profile-bust_cm');
  const waist = page.locator('#profile-waist_cm');

  // every keystroke stays on screen exactly as typed
  expect(await typeSlowly(bust, '88.5')).toEqual(['8', '88', '88.', '88.5']);
  expect(await typeSlowly(bust, '0.5')).toEqual(['0', '0.', '0.5']);
  expect(await typeSlowly(bust, '90,5')).toEqual(['9', '90', '90,', '90,5']);          // the comma is not dropped (was "905")

  // a profile needs a name, not every measurement; a mistyped value is reported beside its field
  await page.locator('#profile-name').fill('Decimal Customer');
  await typeSlowly(bust, '1e2');
  await typeSlowly(waist, '70.25');
  await page.getByRole('button', { name: 'Save measurements' }).click();
  await expect(page.getByTestId('profile-error-bust_cm')).toContainText('not a number');
  await expect(waist).toHaveValue('70.25');                                           // other inputs kept
  expect(await profile()).toBeUndefined();                                            // nothing was saved

  // inches: typed in inches, shown in cm, back in inches unchanged (no double conversion)
  await page.getByTestId('page-unit-in').click();
  await expect(waist).toHaveValue('27.66');                                           // 70.25 cm shown in inches
  await typeSlowly(bust, '33.3');
  await page.getByTestId('page-unit-cm').click();
  await expect(bust).toHaveValue('84.58');
  await expect(waist).toHaveValue('70.25');                                           // typed cm value untouched
  await page.getByTestId('page-unit-in').click();
  await expect(bust).toHaveValue('33.3');
  await shot(page, 'measurements-page-inches');
  expect(await pageOverflow(page)).toBeLessThanOrEqual(1);
  await page.getByRole('button', { name: 'Save measurements' }).click();
  await expect(page.getByText('New measurement profile saved.')).toBeVisible();
  let saved = await profile();
  expect(saved.bust_cm).toBeCloseTo(33.3 * 2.54, 9);                                  // exact: 1 in = 2.54 cm
  expect(saved.waist_cm).toBe(70.25);
  expect(saved.original_values.bust_cm).toEqual({ value: 33.3, unit: 'in' });
  expect(saved.hip_cm ?? null).toBeNull();                                            // optional fields are not forced or invented

  // reload: the saved profile opens with the same values, no float noise
  await page.reload();
  await expect(bust).toHaveValue('84.58');
  await expect(waist).toHaveValue('70.25');
  await page.getByTestId('page-unit-in').click();
  await expect(bust).toHaveValue('33.3');

  // edit one field and save: the untouched inch value is not rewritten
  await typeSlowly(page.locator('#profile-hip_cm'), '37.5');
  await page.getByRole('button', { name: 'Save measurements' }).click();
  await expect(page.getByText('Measurements updated.')).toBeVisible();
  saved = await profile();
  expect(saved.hip_cm).toBeCloseTo(95.25, 9);
  expect(saved.bust_cm).toBeCloseTo(33.3 * 2.54, 9);
  expect(saved.original_values.bust_cm).toEqual({ value: 33.3, unit: 'in' });
  expect((await (await request.get(`${API}/measurements/`, { headers: auth })).json()).measurements).toHaveLength(1);

  // zero and negative values are refused beside the field, by the page and by the server
  await page.getByTestId('page-unit-cm').click();
  await typeSlowly(waist, '0');
  await page.getByRole('button', { name: 'Save measurements' }).click();
  await expect(page.getByTestId('profile-error-waist_cm')).toContainText('greater than 0');
  expect((await profile()).waist_cm).toBe(70.25);
  const direct = await request.put(`${API}/measurements/${saved.measurement_id}`, { headers: auth, data: { unit: 'cm', waist_cm: -4 } });
  expect(direct.status()).toBe(400);
  problems.splice(0, problems.length, ...problems.filter((p) => !/api 400/.test(p)));

  // a very large value is not clamped or replaced (no fixed body-size limits)
  await typeSlowly(waist, '212.75');
  await page.getByRole('button', { name: 'Save measurements' }).click();
  await expect(page.getByText('Measurements updated.')).toBeVisible();
  expect((await profile()).waist_cm).toBe(212.75);

  expect(problems, problems.join('\n')).toEqual([]);
});

test('wizard: every step opened directly shows its controls; measurements in the wizard keep what was typed', async ({ page, request }) => {
  const problems = watch(page);
  const auth = await account(page, request, 'steps');
  const step = (n) => page.getByRole('button', { name: new RegExp(`^Step ${n}:`) });

  await page.goto('/upload');

  // step 3 without a photo: manual feature selection
  await step(3).click();
  await expect(page.getByTestId('fallback-notice')).toBeVisible();
  for (const h of ['garment_type', 'neckline_type', 'sleeve_length', 'sleeve_style']) await expect(page.getByTestId(`select-${h}`)).toBeEnabled();
  await shot(page, 'step3-no-photo');

  // step 5 without a design: fit choices and the fabric catalogue, recommendations pending
  await step(5).click();
  await expect(page.getByTestId('fabric-pending')).toBeVisible();
  await expect(page.getByTestId('catalogue-fabrics').locator('article')).toHaveCount(10);
  await expect(page.getByTestId('recommended-fabrics')).toHaveCount(0);
  await page.getByTestId('fit-loose').click();
  await page.getByTestId('fabric-cotton-jersey-knit').getByRole('button').first().click();
  await expect(page.getByTestId('fabric-construction')).toContainText('Knit');
  await shot(page, 'step5-no-design');

  // steps 6-8 without a pattern: structure and next action, no numbers
  await step(6).click();
  await expect(page.getByTestId('pattern-placeholder')).toBeVisible();
  await expect(page.getByTestId('readiness').locator('li[data-done="yes"]')).toHaveCount(1);     // the fabric chosen above
  await expect(page.getByTestId('pattern-preview')).toHaveCount(0);
  await shot(page, 'step6-no-pattern');
  await step(7).click();
  await expect(page.getByTestId('width-choices').locator('button')).toHaveCount(3);
  await expect(page.getByTestId('estimate-results')).not.toContainText(/\d/);
  await expect(page.getByTestId('width-comparison')).toHaveCount(0);
  await shot(page, 'step7-no-pattern');
  await step(8).click();
  await expect(page.getByTestId('pdf-placeholder')).toBeVisible();
  await page.getByRole('button', { name: 'Create printable PDF' }).click();
  await expect(page.getByRole('alert')).toContainText('Generate the pattern first');
  await shot(page, 'step8-no-pattern');

  // step 4 without a design: design selector + every measurement, as on the Measurements page
  await step(4).click();
  await expect(page.getByTestId('design-selector')).toBeVisible();
  await expect(page.locator('.meas-grid input')).toHaveCount(16);
  await expect(page.getByTestId('meas-need-hip_cm')).toContainText('needed for some designs');
  await expect(page.locator('#saved-client-meas')).toBeVisible();                    // saved customers can be chosen in this step
  await expect(page.getByTestId('meas-source-note')).toContainText('For a new customer, type them here');
  expect(await typeSlowly(page.locator('#meas-bust_cm'), '88,5')).toEqual(['8', '88', '88,', '88,5']);
  await shot(page, 'step4-no-design');
  expect(await pageOverflow(page)).toBeLessThanOrEqual(1);
  await page.getByRole('button', { name: 'Save and continue' }).click();
  await expect(page.getByRole('alert')).toContainText(/confirm the design first/i);

  // the knit jersey chosen earlier cannot be used for a woven blouse: it is cleared and explained, not swapped silently
  for (const [h, v] of Object.entries({ garment_type: 'blouse', neckline_type: 'round-neck', sleeve_length: 'long-sleeve', sleeve_style: 'regular-sleeve' })) {
    await page.getByTestId(`select-${h}`).selectOption(v);
  }
  await page.getByTestId('confirm-btn').click();
  await expect(page.getByTestId('design-selector')).toHaveCount(0);
  await expect(page.locator('.meas-grid input')).toHaveCount(16);                    // long-sleeve blouse: all 11 measurements + 5 optional design values
  await expect(page.getByTestId('meas-need-hip_cm')).toHaveCount(0);                 // now required by the confirmed design
  await expect(page.locator('#meas-bust_cm')).toHaveValue('88,5');                   // kept through the design change

  // inches in the wizard: the sleeve guide line follows the value; toggling never rewrites what was typed
  await page.getByTestId('unit-in').click();
  await expect(page.locator('#meas-bust_cm')).toHaveValue('34.84');
  const inches = { waist_cm: '27.5', hip_cm: '37', shoulder_width_cm: '14.5', back_waist_length_cm: '15.75', shoulder_to_bust_cm: '10',
    waist_to_hip_cm: '8', garment_length_cm: '25.5', bicep_cm: '11', sleeve_cm: '8', sleeve_end_cm: '6.25' };
  for (const [k, v] of Object.entries(inches)) await page.locator(`#meas-${k}`).fill(v);
  await page.locator('#meas-sleeve_cm').focus();
  const shortEnd = await page.getByTestId('sleeve-guide-line').getAttribute('data-end');
  await page.locator('#meas-sleeve_cm').fill('23');
  const longEnd = await page.getByTestId('sleeve-guide-line').getAttribute('data-end');
  expect(Number(longEnd.split(',')[1])).toBeGreaterThan(Number(shortEnd.split(',')[1]));
  await expect(page.getByTestId('guide-sleeve_cm')).toBeVisible();
  await expect(page.getByText(/3D measuring guide/)).toHaveCount(0);
  await shot(page, 'step4-inches');
  await page.getByTestId('unit-cm').click();
  await expect(page.locator('#meas-sleeve_cm')).toHaveValue('58.42');
  await expect(page.locator('#meas-bust_cm')).toHaveValue('88,5');
  await page.getByTestId('unit-in').click();
  await expect(page.locator('#meas-sleeve_cm')).toHaveValue('23');

  // a mistake beside its field; the rest stays
  await page.locator('#meas-sleeve_end_cm').fill('-6');
  await page.getByRole('button', { name: 'Save and continue' }).click();
  await expect(page.getByTestId('error-sleeve_end_cm')).toContainText('greater than 0');
  await expect(page.locator('#meas-waist_cm')).toHaveValue('27.5');
  await page.locator('#meas-sleeve_end_cm').fill('6.25');
  await page.getByRole('button', { name: 'Save and continue' }).click();
  await expect(page.getByRole('alert')).toContainText(/customer name/);
  await step(1).click();
  await page.locator('#client-name').fill('Wizard Customer');
  await step(4).click();
  await expect(page.locator('#meas-waist_cm')).toHaveValue('27.5');                   // still there after leaving the step
  await page.getByRole('button', { name: 'Save and continue' }).click();
  await expect(page.getByRole('heading', { name: 'Choose fabric and fit' })).toBeVisible();

  const saved = (await (await request.get(`${API}/measurements/`, { headers: auth })).json()).measurements[0];
  expect(saved.bust_cm).toBe(88.5);
  expect(saved.sleeve_cm).toBeCloseTo(58.42, 9);
  expect(saved.original_values.sleeve_cm).toEqual({ value: 23, unit: 'in' });
  expect(saved.height_cm ?? null).toBeNull();                                         // not needed by this design: not asked, not invented
  expect(saved.armhole_depth_cm ?? null).toBeNull();                                  // optional design value left empty: calculated, not stored
  expect(saved.neck_width_cm ?? null).toBeNull();

  await expect(page.getByTestId('fabric-replaced')).toContainText(/Cotton Jersey Knit cannot be used/);
  await expect(page.getByTestId('fit-loose')).toHaveAttribute('aria-pressed', 'true'); // the fit chosen before the design is kept
  await page.getByRole('button', { name: /generate pattern/i }).click();
  await expect(page.getByRole('alert').first()).toContainText(/choose a fabric/i);
  await page.getByTestId('fabric-cotton-poplin').getByRole('button').first().click();
  await page.getByRole('button', { name: /generate pattern/i }).click();
  await expect(page.getByTestId('pattern-preview')).toBeVisible();

  // a fit change afterwards invalidates the pattern, the estimate and the PDF
  await step(5).click();
  await page.getByTestId('fit-close').click();
  await expect(page.getByRole('button', { name: /^Step 6: Pattern preview \(Needs update\)/ })).toBeVisible();
  await step(7).click();
  await expect(page.getByTestId('step-empty')).toContainText(/generate it again/);
  await expect(page.getByTestId('estimate-results')).not.toContainText(/\d/);

  expect(problems, problems.join('\n')).toEqual([]);
});
