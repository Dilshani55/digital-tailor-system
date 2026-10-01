// Real end-to-end run: browser -> React -> Flask -> MongoDB -> classifier -> drafting -> nesting -> PDF.
import { test, expect } from '@playwright/test';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const API = process.env.E2E_API_URL || 'http://127.0.0.1:5055/api';
const IMAGE = path.resolve(process.env.E2E_IMAGE || '../ai_training/data/eval_real_product_set/images/blouse_01.jpg');
const MEAS = {
  bust_cm: 88, waist_cm: 70, hip_cm: 94, height_cm: 162, neck_cm: 36, shoulder_cm: 12, across_back_cm: 34,
  back_waist_length_cm: 40, armhole_depth_cm: 20, garment_length_cm: 65, bicep_cm: 28, sleeve_cm: 24, wrist_cm: 16,
};

// Set E2E_SHOT_DIR to save a full-page screenshot of every wizard step (visual evidence);
// set E2E_VIEWPORT=390x844 to run the same flow at phone size.
const [VW, VH] = (process.env.E2E_VIEWPORT || '').split('x').map(Number);
if (VW && VH) test.use({ viewport: { width: VW, height: VH } });
const shotter = (page) => async (name) => {
  if (!process.env.E2E_SHOT_DIR) return;
  fs.mkdirSync(process.env.E2E_SHOT_DIR, { recursive: true });
  await page.screenshot({ path: path.join(process.env.E2E_SHOT_DIR, `${name}.png`), fullPage: true });
};

test('register -> upload -> AI review -> measurements -> fabric -> pattern -> estimate -> PDF -> history', async ({ page }) => {
  const email = `e2e_${Date.now()}@example.test`;
  const password = 'E2e-Passw0rd!';
  const steps = [];
  const mark = (s) => { steps.push(s); };
  const shot = shotter(page);

  // 1. register through the UI
  await page.goto('/auth');
  await page.getByRole('button', { name: 'Sign up' }).click();
  await page.getByLabel('Full Name').fill('E2E Tester');
  await page.getByLabel('Email Address').fill(email);
  await page.locator('#reg-password').fill(password);
  await page.locator('#reg-confirmPassword').fill(password);
  await page.getByRole('checkbox').check();
  await page.getByRole('button', { name: 'Create account' }).click();
  await page.locator('#login-email').waitFor({ timeout: 30_000 });          // app returns to the sign-in tab
  await page.locator('#login-email').fill(email);
  await page.locator('#login-password').fill(password);
  await page.getByRole('button', { name: 'Sign In' }).click();
  await page.waitForURL('**/dashboard', { timeout: 30_000 });
  mark('registered + signed in');

  // 2. upload a real garment photo and let the real classifier analyse it
  await page.goto('/upload');
  await page.getByLabel('Customer name').fill('E2E Customer');
  await page.getByRole('button', { name: 'Continue to upload' }).click();
  await page.getByTestId('image-input').setInputFiles(IMAGE);
  await shot('01-upload');
  await page.getByRole('button', { name: 'Upload and analyse' }).click();
  await expect(page.getByRole('heading', { name: 'Review the AI suggestions' })).toBeVisible({ timeout: 180_000 });
  await expect(page.getByTestId('head-card-garment_type')).toBeVisible();
  await expect(page.getByTestId('confidence-tag-garment_type')).toContainText('%');
  await shot('02-ai-review');
  mark('AI analysis returned 4 head predictions with confidences');

  // 3. edit the AI answer to a supported design and confirm it
  await page.getByTestId('select-garment_type').selectOption('blouse');
  await page.getByTestId('select-neckline_type').selectOption('round-neck');
  await page.getByTestId('select-sleeve_length').selectOption('short-sleeve');
  await page.getByTestId('select-sleeve_style').selectOption('regular-sleeve');
  await page.getByTestId('confirm-btn').click();
  await expect(page.getByTestId('confirmed-badge')).toBeVisible();
  await page.getByRole('button', { name: 'Continue to measurements' }).click();
  mark('design edited, validated as in-scope and confirmed');

  // 4. only the measurements this design needs; a non-positive value is rejected inline; units never double-convert
  await shot('03-measurements-empty');
  await expect(page.locator('#meas-wrist_cm')).toHaveCount(0);          // short sleeve: no wrist
  await expect(page.locator('#meas-height_cm')).toHaveCount(0);         // no drafting calculation uses height
  await expect(page.getByText(/All 13 measurements|Open the 3D measuring guide|full arm/)).toHaveCount(0);
  await page.locator('#meas-sleeve_cm').focus();
  await expect(page.getByTestId('guide-sleeve_cm')).toHaveText('උරහිසේ අග සිට ඔබට අත අවසන් වෙන්න අවශ්‍ය ස්ථානය දක්වා මනින්න.');
  await page.locator('#meas-bust_cm').fill('-5');
  await page.getByRole('button', { name: 'Save and continue' }).click();
  await expect(page.getByTestId('error-bust_cm')).toContainText(/greater than 0/);
  await shot('03b-measurement-inline-error');
  for (const [k, v] of Object.entries(MEAS)) {
    if (await page.locator(`#meas-${k}`).count()) await page.locator(`#meas-${k}`).fill(String(v));
  }
  await page.locator('#meas-bust_cm').fill('88.9');
  await page.getByTestId('unit-in').click();
  await expect(page.locator('#meas-bust_cm')).toHaveValue('35');
  await page.getByTestId('unit-cm').click();
  await expect(page.locator('#meas-bust_cm')).toHaveValue('88.9');      // exactly what was typed
  await page.getByRole('button', { name: 'Save and continue' }).click();
  await expect(page.getByRole('heading', { name: 'Choose fabric and fit' })).toBeVisible();
  await shot('04-fabric-and-fit');
  mark('only design measurements shown, non-positive value rejected inline, unit toggle kept typed values, saved');

  // 5. recommended fabric with explanation, then generate
  await expect(page.getByText(/Cotton Poplin|Linen|Rayon|Jersey/).first()).toBeVisible({ timeout: 30_000 });
  await page.getByRole('button', { name: 'Confirm and generate pattern' }).click();
  await expect(page.getByRole('heading', { name: 'Pattern preview' })).toBeVisible({ timeout: 60_000 });
  await expect(page.getByText('Geometry validation passed')).toBeVisible();
  expect(await page.locator('[data-testid^="cutting-line-"]').count()).toBeGreaterThanOrEqual(3);
  expect(await page.locator('[data-testid^="notch-"]').count()).toBeGreaterThanOrEqual(3);
  await shot('05-pattern-preview');
  mark('pattern generated, validated, SVG shows cutting lines + notches');

  // 6. fabric estimate for each supported width
  await page.getByRole('button', { name: 'Continue to fabric estimate' }).click();
  await expect(page.getByRole('heading', { name: 'Fabric estimate', exact: true })).toBeVisible();
  // all three standard widths are calculated together from the stored pieces
  const table = page.getByTestId('width-comparison');
  await expect(table).toBeVisible({ timeout: 60_000 });
  for (const t of ['36"', '45"', '60"', '91.44 cm', '114.3 cm', '152.4 cm']) await expect(table).toContainText(t);
  const lengths = {};
  for (const [inch, cm] of [[36, 91.44], [45, 114.3], [60, 152.4]]) {
    await page.getByTestId(`width-${inch}`).click();
    await expect(page.getByTestId(`width-${inch}`)).toHaveText('Selected', { timeout: 60_000 });
    await expect(page.getByTestId('nesting-layout')).toContainText(`${cm} cm wide`);
    lengths[inch] = await page.getByTestId(`estimate-row-${inch}`).innerText();
  }
  await shot('06-fabric-estimate');
  mark(`estimates: ${JSON.stringify(lengths).replace(/\s+/g, ' ')}`);

  // 7. printable PDF
  await page.getByRole('button', { name: 'Continue to PDF export' }).click();
  await page.getByRole('button', { name: 'Create printable PDF' }).click();
  await expect(page.getByTestId('pdf-ready')).toBeVisible({ timeout: 120_000 });
  await shot('07-pdf-ready');
  const [download] = await Promise.all([
    page.waitForEvent('download'),
    page.getByRole('button', { name: 'Download PDF', exact: true }).click(),
  ]);
  const out = path.join(process.env.E2E_OUT_DIR || os.tmpdir(), `e2e_pattern_${Date.now()}.pdf`);
  await download.saveAs(out);
  const bytes = fs.readFileSync(out);
  expect(bytes.subarray(0, 5).toString()).toBe('%PDF-');
  expect(bytes.length).toBeGreaterThan(20_000);
  mark(`PDF downloaded: ${out} (${bytes.length} bytes)`);
  fs.writeFileSync(path.join(path.dirname(out), 'e2e_last_pdf_path.txt'), out);

  // 8. feedback; then a measurement change makes the pattern/estimate/PDF out of date (free step navigation)
  await page.getByLabel(/How easy was it/).selectOption('5');
  await page.getByRole('button', { name: 'Send feedback' }).click();
  await expect(page.getByText(/Thank you/)).toBeVisible();
  await page.getByRole('button', { name: /^Step 4: Measurements/ }).click();
  await page.locator('#meas-bust_cm').fill('90');
  await expect(page.getByRole('button', { name: /^Step 6: Pattern preview \(Needs update\)/ })).toBeVisible();
  await page.getByRole('button', { name: /^Step 6: Pattern preview/ }).click();
  await expect(page.getByTestId('step-empty')).toContainText(/generated again/);
  await expect(page.getByTestId('pattern-preview')).toHaveCount(0);
  await page.getByRole('button', { name: /^Step 8: Download PDF/ }).click();
  await expect(page.getByTestId('step-empty')).toContainText(/out of date/);
  mark('free navigation: edited measurement marks pattern, estimate and PDF as needing regeneration');
  await page.goto('/history');
  await expect(page.locator('.library-item').first()).toBeVisible();
  await expect(page.locator('.library-item').first().locator('.tag').first()).toHaveText('PDF ready');
  await page.getByRole('button', { name: 'View pattern' }).first().click();
  await expect(page.getByRole('heading', { name: /Blouse pattern/ })).toBeVisible();
  await expect(page.getByTestId('pattern-preview')).toBeVisible();
  await shot('08-saved-pattern');
  mark('saved pattern re-opened from the library');

  console.log('E2E STEPS PASSED:\n - ' + steps.join('\n - '));
});

test('out-of-scope design cannot be confirmed through the UI', async ({ page, request }) => {
  const email = `e2e_scope_${Date.now()}@example.test`;
  const res = await request.post(`${API}/auth/register`, { data: { full_name: 'Scope Tester', email, password: 'E2e-Passw0rd!' } });
  expect(res.ok()).toBeTruthy();
  await page.goto('/auth');
  await page.locator('#login-email').fill(email);
  await page.locator('#login-password').fill('E2e-Passw0rd!');
  await page.getByRole('button', { name: 'Sign In' }).click();
  await page.waitForURL('**/dashboard', { timeout: 30_000 });
  await page.goto('/upload');
  await page.getByLabel('Customer name').fill('E2E Customer');
  await page.getByRole('button', { name: 'Continue to upload' }).click();
  await page.getByRole('button', { name: /choose the design manually/i }).click();
  await page.getByTestId('select-garment_type').selectOption('t-shirt');
  // combinations the engine cannot draft are not selectable at all
  await expect(page.getByTestId('select-neckline_type').locator('option[value="square-neck"]')).toBeDisabled();
  await expect(page.getByTestId('select-neckline_type').locator('option[value="collared-neck"]')).toBeDisabled();
  await expect(page.getByTestId('select-sleeve_length').locator('option[value="sleeveless"]')).toBeDisabled();
  await page.getByTestId('select-neckline_type').selectOption('round-neck');
  await page.getByTestId('select-sleeve_length').selectOption('short-sleeve');
  await expect(page.getByTestId('select-sleeve_style').locator('option[value="puff-sleeve"]')).toBeDisabled();
  await expect(page.getByTestId('confirm-btn')).toBeDisabled();            // style still missing
  await page.getByRole('button', { name: 'Continue to measurements' }).click();       // navigation is free ...
  await expect(page.getByTestId('step-empty')).toContainText(/Confirm the design first/);   // ... but nothing is drafted
  await expect(page.locator('#meas-bust_cm')).toHaveCount(0);
});
