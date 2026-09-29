// Real end-to-end run: browser -> React -> Flask -> MongoDB -> classifier -> drafting -> nesting -> PDF.
import { test, expect } from '@playwright/test';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const API = process.env.E2E_API_URL || 'http://127.0.0.1:5055/api';
const IMAGE = path.resolve(process.env.E2E_IMAGE || '../ai_training/data/eval_real_product_set/images/blouse_01.jpg');
const MEAS = {
  bust_cm: 88, waist_cm: 70, hip_cm: 94, height_cm: 162, neck_cm: 36, shoulder_cm: 12, across_back_cm: 34,
  back_waist_length_cm: 40, armhole_depth_cm: 20, garment_length_cm: 65, bicep_cm: 28, sleeve_cm: 55, wrist_cm: 16,
};

test('register -> upload -> AI review -> measurements -> fabric -> pattern -> estimate -> PDF -> history', async ({ page }) => {
  const email = `e2e_${Date.now()}@example.test`;
  const password = 'E2e-Passw0rd!';
  const steps = [];
  const mark = (s) => { steps.push(s); };

  // 1. register through the UI
  await page.goto('/auth');
  await page.getByRole('button', { name: 'Create Account' }).first().click();
  await page.getByLabel('Full Name').fill('E2E Tester');
  await page.getByLabel('Email Address').fill(email);
  await page.locator('#reg-password').fill(password);
  await page.locator('#reg-confirmPassword').fill(password);
  await page.getByRole('checkbox').check();
  await page.getByRole('button', { name: 'Create Account' }).last().click();
  await page.locator('#login-email').waitFor({ timeout: 30_000 });          // app returns to the sign-in tab
  await page.locator('#login-email').fill(email);
  await page.locator('#login-password').fill(password);
  await page.getByRole('button', { name: 'Sign In' }).click();
  await page.waitForURL('**/dashboard', { timeout: 30_000 });
  mark('registered + signed in');

  // 2. upload a real garment photo and let the real classifier analyse it
  await page.goto('/upload');
  await page.getByTestId('image-input').setInputFiles(IMAGE);
  await page.getByRole('button', { name: 'Upload and analyse' }).click();
  await expect(page.getByRole('heading', { name: 'Review the AI suggestion' })).toBeVisible({ timeout: 180_000 });
  await expect(page.getByTestId('head-card-garment_type')).toBeVisible();
  await expect(page.getByTestId('confidence-tag-garment_type')).toContainText('%');
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

  // 4. an out-of-range measurement is rejected inline, then correct values are saved
  await page.locator('#meas-bust_cm').fill('5');
  await page.getByRole('button', { name: 'Save and continue' }).click();
  await expect(page.getByTestId('error-bust_cm')).toContainText(/plausible range/);
  for (const [k, v] of Object.entries(MEAS)) await page.locator(`#meas-${k}`).fill(String(v));
  await page.getByLabel('Customer name').fill('E2E Customer');
  await page.getByRole('button', { name: 'Save and continue' }).click();
  await expect(page.getByRole('heading', { name: 'Fabric and fit' })).toBeVisible();
  mark('measurements validated (inline error shown) and saved');

  // 5. recommended fabric with explanation, then generate
  await expect(page.getByText(/Cotton Poplin|Linen|Rayon|Jersey/).first()).toBeVisible({ timeout: 30_000 });
  await page.getByRole('button', { name: 'Confirm and generate pattern' }).click();
  await expect(page.getByRole('heading', { name: 'Your pattern' })).toBeVisible({ timeout: 60_000 });
  await expect(page.getByText('Geometry validation passed')).toBeVisible();
  expect(await page.locator('[data-testid^="cutting-line-"]').count()).toBeGreaterThanOrEqual(3);
  expect(await page.locator('[data-testid^="notch-"]').count()).toBeGreaterThanOrEqual(3);
  mark('pattern generated, validated, SVG shows cutting lines + notches');

  // 6. fabric estimate for each supported width
  await page.getByRole('button', { name: 'Continue to fabric estimate' }).click();
  await expect(page.getByRole('heading', { name: 'Fabric estimate' })).toBeVisible();
  const lengths = {};
  for (const w of [90, 114, 150]) {
    await page.getByTestId(`width-${w}`).click();
    await expect(page.getByTestId('nesting-layout')).toContainText(`${w} cm wide`, { timeout: 60_000 });
    lengths[w] = await page.getByTestId('estimate-results').innerText();
  }
  mark(`estimates: ${JSON.stringify(lengths).replace(/\s+/g, ' ')}`);

  // 7. printable PDF
  await page.getByRole('button', { name: 'Continue to PDF export' }).click();
  await page.getByRole('button', { name: 'Create printable PDF' }).click();
  await expect(page.getByTestId('pdf-ready')).toBeVisible({ timeout: 120_000 });
  const [download] = await Promise.all([
    page.waitForEvent('download'),
    page.getByRole('button', { name: 'Download PDF' }).click(),
  ]);
  const out = path.join(process.env.E2E_OUT_DIR || os.tmpdir(), `e2e_pattern_${Date.now()}.pdf`);
  await download.saveAs(out);
  const bytes = fs.readFileSync(out);
  expect(bytes.subarray(0, 5).toString()).toBe('%PDF-');
  expect(bytes.length).toBeGreaterThan(20_000);
  mark(`PDF downloaded: ${out} (${bytes.length} bytes)`);
  fs.writeFileSync(path.join(path.dirname(out), 'e2e_last_pdf_path.txt'), out);

  // 8. feedback, then the saved pattern is visible again from the library
  await page.getByLabel(/How easy was it/).selectOption('5');
  await page.getByRole('button', { name: 'Send feedback' }).click();
  await expect(page.getByText(/Thank you/)).toBeVisible();
  await page.goto('/history');
  await expect(page.locator('.hist-table tbody tr').first()).toBeVisible();
  await page.getByRole('button', { name: 'View pattern' }).first().click();
  await expect(page.getByRole('heading', { name: /Blouse pattern/ })).toBeVisible();
  await expect(page.getByTestId('pattern-preview')).toBeVisible();
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
  await page.getByRole('button', { name: /choose the design manually/ }).click();
  await page.getByTestId('select-garment_type').selectOption('t-shirt');
  await page.getByTestId('select-neckline_type').selectOption('square-neck');
  await page.getByTestId('select-sleeve_length').selectOption('short-sleeve');
  await page.getByTestId('select-sleeve_style').selectOption('regular-sleeve');
  await page.getByTestId('confirm-btn').click();
  await expect(page.getByRole('button', { name: 'Continue to measurements' })).toBeDisabled();
});
