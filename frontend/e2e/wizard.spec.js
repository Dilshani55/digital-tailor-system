// Real end-to-end run: browser -> React -> Flask -> MongoDB -> classifier -> drafting -> nesting -> PDF.
import { test, expect } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const API = process.env.E2E_API_URL || 'http://127.0.0.1:5055/api';
const IMAGE = path.resolve(process.env.E2E_IMAGE || '../backend/training/data/eval_real_product_set/images/blouse_01.jpg');
const MEAS = {
  bust_cm: 88, waist_cm: 70, hip_cm: 94, shoulder_width_cm: 37, back_waist_length_cm: 40, shoulder_to_bust_cm: 25,
  waist_to_hip_cm: 20, garment_length_cm: 65, bicep_cm: 28, sleeve_cm: 24, sleeve_end_cm: 27,
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
  await expect(page.locator('#meas-sleeve_end_cm')).toHaveCount(1);     // the arm where this sleeve ends
  await expect(page.locator('#meas-wrist_cm')).toHaveCount(0);          // old field: stored, never asked
  await expect(page.locator('#meas-height_cm')).toHaveCount(0);         // no drafting calculation uses height
  await expect(page.locator('#meas-neck_cm')).toHaveCount(0);           // nor the neck circumference
  for (const g of ['body', 'arm', 'neck']) await expect(page.getByTestId(`meas-group-${g}`)).toBeVisible();
  await expect(page.getByText(/All 13 measurements|Open the 3D measuring guide|full arm/)).toHaveCount(0);
  await page.locator('#meas-sleeve_cm').focus();
  await expect(page.getByTestId('guide-sleeve_cm')).toContainText('How to measure');
  await expect(page.getByTestId('guide-sleeve_cm')).toContainText('Common mistake:');
  await expect(page.getByTestId('guide-line-sleeve_cm')).toHaveAttribute('data-active', 'yes');   // drawn on the figure
  await page.locator('#meas-shoulder_width_cm').focus();
  await expect(page.getByTestId('measure-figure')).toHaveAttribute('data-active-view', 'back');   // measured on the back
  await page.locator('#meas-bust_cm').focus();
  await expect(page.getByTestId('measure-figure')).toHaveAttribute('data-active-view', 'front');
  await page.locator('#meas-bust_cm').fill('-5');
  await page.getByRole('button', { name: 'Save and continue' }).click();
  await expect(page.getByTestId('error-bust_cm')).toContainText(/greater than 0/);
  await shot('03b-measurement-inline-error');
  for (const [k, v] of Object.entries(MEAS)) {
    if (await page.locator(`#meas-${k}`).count()) await page.locator(`#meas-${k}`).fill(String(v));
  }
  // design values left empty: the method's calculated value is shown, not saved as if it were measured
  await expect(page.getByTestId('calculated-armhole_depth_cm')).toContainText('Calculated value');
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
  // front, back and sleeve blocks with their dimensions; the sleeve cap is checked against the armhole
  for (const tab of ['front_bodice', 'back_bodice', 'sleeve']) {
    await page.getByTestId(`tab-${tab}`).click();
    await expect(page.getByTestId(`block-${tab}`)).toBeVisible();
    expect(await page.locator('[data-testid^="dim-row-"]').count()).toBeGreaterThanOrEqual(4);
  }
  await expect(page.getByTestId('sleeve-cap-report')).toContainText('Bodice armhole seam');
  await expect(page.getByTestId('sleeve-cap-status')).toContainText(/^(PASS|REVIEW)/);
  await expect(page.getByTestId('why-this-size')).toContainText('Front width at the bust line');
  await page.getByTestId('tab-all').click();
  await page.getByTestId('toggle-cut').click();
  await expect(page.locator('[data-testid^="cutting-line-"]')).toHaveCount(0);        // sewing line only
  await page.getByTestId('toggle-cut').click();
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
  // lengths in metres and yards, areas, and a one-way (nap) layout that is never shorter than the two-way one
  for (const t of ['yd', 'm²', 'yd²']) await expect(table).toContainText(t);
  await expect(page.getByTestId('estimate-explain')).toBeVisible();
  const before = await page.getByTestId('estimate-row-45').innerText();
  await page.getByTestId('one-way').check();
  await expect(page.getByTestId('width-comparison')).toContainText(/one.way/i, { timeout: 60_000 });
  mark(`one-way estimate: ${(await page.getByTestId('estimate-row-45').innerText()).replace(/\s+/g, ' ')} (two-way: ${before.replace(/\s+/g, ' ')})`);
  await page.getByTestId('one-way').uncheck();
  await expect(page.getByTestId('estimate-row-45')).not.toContainText('one-way', { timeout: 60_000 });
  expect(await page.getByTestId('estimate-row-45').innerText()).toBe(before);         // the same layout as before
  await shot('06-fabric-estimate');
  mark(`estimates: ${JSON.stringify(lengths).replace(/\s+/g, ' ')}`);

  // 7. printable PDF
  await page.getByRole('button', { name: 'Continue to PDF export' }).click();
  await expect(page.getByTestId('pdf-part-overview')).toBeChecked();    // default: one page at a reduced scale, not real size
  await expect(page.getByTestId('pdf-overview-note')).toBeVisible();
  await page.getByRole('button', { name: 'Create printable PDF' }).click();
  await expect(page.getByTestId('pdf-ready')).toContainText(/1 page · A4 · reduced scale 1:\d+, not real size/, { timeout: 120_000 });
  await shot('07a-pdf-overview-ready');
  await expect(page.getByTestId('pdf-part-report')).toBeVisible();
  await expect(page.getByTestId('pdf-part-pattern')).toBeVisible();
  await page.getByTestId('pdf-part-all').check();                       // the rest of this run checks the whole file, incl. the 1:1 pages
  await expect(page.getByTestId('pdf-overview-note')).toHaveCount(0);
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
  // the PDF's own vector data: A4 pages, a 5.00 x 5.00 cm calibration square, the required sections
  const python = path.resolve('../backend/venv/Scripts/python.exe');
  if (fs.existsSync(python)) {
    const report = JSON.parse(execFileSync(python, [path.resolve('../backend/tools/verify_pdf.py'), out], { encoding: 'utf-8' }));
    expect(report.passed, JSON.stringify(report.checks)).toBe(true);
    expect(report.calibration_squares_cm).toEqual([[5, 5]]);
    mark(`PDF verified digitally: ${report.pages} A4 pages, calibration square ${report.calibration_squares_cm[0].join(' x ')} cm`);
  }
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
  await expect(page.getByTestId('design-selector')).toBeVisible();                    // ... the step asks for the design
  await expect(page.getByTestId('design-selector').getByTestId('confirm-btn')).toBeDisabled();
  await expect(page.locator('#meas-sleeve_cm')).toHaveCount(0);                       // no design-specific fields yet
  await page.locator('#meas-bust_cm').fill('88');
  await page.getByRole('button', { name: 'Save and continue' }).click();
  await expect(page.getByRole('alert')).toContainText(/confirm the design first/i);   // ... and nothing is saved or drafted
  await page.getByRole('button', { name: /^Step 5:/ }).click();
  await page.getByRole('button', { name: /generate pattern/i }).click();
  await expect(page.getByRole('alert').first()).toContainText(/confirm a supported design/i);
  await expect(page.getByTestId('pattern-preview')).toHaveCount(0);
});
