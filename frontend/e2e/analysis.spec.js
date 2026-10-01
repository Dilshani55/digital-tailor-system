// Real upload + real M40 analysis (3/5/3/4 model): every head shows its own model score, unreliable heads are
// "uncertain - please select" (never pre-selected), the user corrects and confirms, and the genuine prediction is stored.
import { test, expect } from '@playwright/test';
import path from 'node:path';

const API = process.env.E2E_API_URL || 'http://127.0.0.1:5055/api';
const IMG = (n) => path.resolve('../backend/training/data/eval_real_product_set/images', n);
const HEADS = ['garment_type', 'neckline_type', 'sleeve_length', 'sleeve_style'];

async function signIn(page, request) {
  const email = `e2e_ai_${Date.now()}_${Math.floor(Math.random() * 1e6)}@example.test`;
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
  await page.getByLabel('Customer name').fill('E2E Customer');
  await page.getByRole('button', { name: 'Continue to upload' }).click();
  await page.getByTestId('image-input').setInputFiles(IMG(file));
  await page.getByRole('button', { name: 'Upload and analyse' }).click();
  await expect(page.getByRole('heading', { name: 'Review the AI suggestions' })).toBeVisible({ timeout: 180_000 });
}

test('M40 analysis: separate scores, uncertain heads not pre-selected, honest wording, manual confirmation', async ({ page, request }) => {
  await signIn(page, request);
  await analyse(page, 'blouse_19.jpg');

  // every head shows its OWN model score, worded as a score (not as proof)
  for (const h of HEADS) {
    await expect(page.getByTestId(`confidence-tag-${h}`)).toHaveText(/^Model score \d+(\.\d)?%( · uncertain)?$/);
    await expect(page.getByTestId(`top-3-${h}`)).toContainText('%');
  }
  await expect(page.locator('body')).not.toContainText(/High confidence/);
  await expect(page.locator('body')).toContainText(/not proof/);

  // garment type, neckline and sleeve design never reach the accuracy target on validation -> always "please select"
  for (const h of ['garment_type', 'neckline_type', 'sleeve_style']) {
    await expect(page.getByTestId(`select-${h}`)).toHaveValue('');
    await expect(page.getByTestId(`low-confidence-${h}`)).toContainText('Uncertain — please select');
  }
  await expect(page.getByTestId('garment-length-note')).toContainText('crop top and a T-shirt can look alike');
  await expect(page.getByTestId('confirm-btn')).toBeDisabled();
  await expect(page.getByTestId('outside-scope-alert')).toHaveCount(0);        // M40 only outputs selectable classes

  // the user decides every feature
  await page.getByTestId('select-garment_type').selectOption('blouse');
  await page.getByTestId('select-neckline_type').selectOption('square-neck');
  const length = page.getByTestId('select-sleeve_length');
  if ((await length.inputValue()) === '') await length.selectOption('long-sleeve');
  await page.getByTestId('select-sleeve_style').selectOption('regular-sleeve');
  await expect(page.getByTestId('confirm-btn')).toBeEnabled();
  await page.getByTestId('confirm-btn').click();
  await expect(page.getByTestId('confirmed-badge')).toBeVisible();

  // the genuine prediction and score are stored next to the user's choice (research evidence)
  const token = await page.evaluate(() => localStorage.getItem('token'));
  const list = await request.get(`${API}/images/`, { headers: { Authorization: `Bearer ${token}` } });
  const first = ((await list.json()).images || [])[0];
  const body = await (await request.get(`${API}/images/${first.image_id}`, { headers: { Authorization: `Bearer ${token}` } })).json();
  for (const h of HEADS) {
    const p = body.garment_attributes.predictions[h];
    expect(typeof p.label).toBe('string');
    expect(p.confidence).toBeGreaterThan(0);
    expect(body.design_spec.provenance[h].predicted_label).toBe(p.label);           // genuine output preserved
  }
  expect(body.confirmed_attributes.neckline_type).toBe('square-neck');
  expect(body.garment_attributes.predictions.garment_type.uncertain).toBe(true);
  expect(body.garment_attributes.model_version).toContain('YOLOv8MultiTaskClassifier');
});

test('hidden or unclear feature: a low score keeps sleeve length as "please select"', async ({ page, request }) => {
  await signIn(page, request);
  // find a benchmark photo where the model itself is unsure of the sleeve length (score below 0.70)
  const files = ['blouse_05.jpg', 'blouse_08.jpg', 'crop-top_03.jpg', 'crop-top_08.jpg', 't-shirt_04.jpg', 't-shirt_09.jpg',
    'blouse_12.jpg', 'crop-top_12.jpg', 't-shirt_12.jpg', 'blouse_16.jpg', 'crop-top_16.jpg', 't-shirt_16.jpg'];
  let seenUncertain = false;
  for (const f of files) {
    await analyse(page, f);
    const tag = await page.getByTestId('confidence-tag-sleeve_length').innerText();
    const value = await page.getByTestId('select-sleeve_length').inputValue();
    if (/uncertain/.test(tag)) {
      expect(value).toBe('');                                                          // not forced
      await expect(page.getByTestId('low-confidence-sleeve_length')).toContainText('Uncertain — please select');
      seenUncertain = true;
      break;
    }
    if (await page.getByTestId('not-draftable-sleeve_length').count()) {               // confident but not draftable (e.g. crop-top + long sleeve)
      expect(value).toBe('');                                                          // -> never forced, the note explains why
      continue;
    }
    expect(value).not.toBe('');                                                        // a confident, draftable prediction is pre-selected
  }
  expect(seenUncertain, 'no low-score sleeve-length photo found among the samples').toBe(true);
});
