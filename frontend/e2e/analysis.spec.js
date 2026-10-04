// Real upload + real analysis by the four garment models: scores stay in the stored evidence; a feature whose
// score is below its model's threshold is "uncertain - please select" (never pre-selected), the user corrects and
// confirms, and the genuine prediction is stored next to the user's choice.
import { test, expect } from '@playwright/test';
import path from 'node:path';

const API = process.env.E2E_API_URL || 'http://127.0.0.1:5055/api';
const IMG = (n) => path.resolve('../backend/training/data/eval_real_product_set/images', n);
const HEADS = ['garment_type', 'neckline_type', 'sleeve_length', 'sleeve_style'];

async function signIn(page, request) {
  page.on('dialog', (dialog) => dialog.accept());
  const email = `e2e_ai_${Date.now()}_${Math.floor(Math.random() * 1e6)}@example.test`;
  const res = await request.post(`${API}/auth/register`, { data: { full_name: 'Analysis Tester', email, password: 'E2e-Passw0rd!' } });
  expect(res.ok()).toBeTruthy();
  await page.goto('/auth');
  await page.locator('#login-email').fill(email);
  await page.locator('#login-password').fill('E2e-Passw0rd!');
  await page.getByRole('button', { name: 'Sign In' }).click();
  await page.waitForURL('**/dashboard', { timeout: 30_000 });
  return page.evaluate(() => localStorage.getItem('token'));
}

async function analyse(page, file) {
  await page.goto('/upload');
  await page.getByRole('button', { name: 'Start new pattern' }).click();
  await page.getByLabel('Customer name').fill('E2E Customer');
  await page.getByRole('button', { name: 'Continue to upload' }).click();
  await page.getByTestId('image-input').setInputFiles(IMG(file));
  await page.getByRole('button', { name: 'Upload and analyse' }).click();
  await expect(page.getByRole('heading', { name: 'Review the AI suggestions' })).toBeVisible({ timeout: 180_000 });
}

test('four models: scores hidden in UI, uncertain features not pre-selected, manual confirmation, evidence stored', async ({ page, request }) => {
  const token = await signIn(page, request);
  const auth = { Authorization: `Bearer ${token}` };

  // the server really loaded four separate models
  const status = await (await request.get(`${API}/images/model-status`, { headers: auth })).json();
  expect(status.available).toBe(true);
  expect(status.complete).toBe(true);
  expect(status.models.garment_type.architecture).toBe('MobileNetV3-Large');
  for (const h of ['neckline_type', 'sleeve_length', 'sleeve_style']) expect(status.models[h].architecture).toBe('YOLOv8n-cls');
  expect(new Set(HEADS.map((h) => status.models[h].sha256)).size).toBe(4);          // four different files

  await analyse(page, 'blouse_19.jpg');

  // Predictions remain visible, while model scores are kept out of the user interface.
  for (const h of HEADS) {
    await expect(page.getByTestId(`confidence-tag-${h}`)).toHaveCount(0);
    await expect(page.getByTestId(`top-3-${h}`)).toContainText('AI top 3:');
  }
  await expect(page.getByTestId('prediction-review-container')).not.toContainText(/%|Model score/);
  await expect(page.locator('body')).not.toContainText(/High confidence/);
  await expect(page.locator('body')).toContainText(/check every feature/);
  await expect(page.getByTestId('outside-scope-alert')).toHaveCount(0);            // the models only answer selectable classes
  await expect(page.locator('body')).not.toContainText(/crop.?top/i);
  await expect(page.getByTestId('select-garment_type').locator('option')).toHaveCount(3);     // placeholder + blouse + t-shirt

  // a feature is pre-selected only when its model is allowed to answer AND its score is high enough
  for (const h of HEADS) {
    const uncertain = await page.getByTestId(`low-confidence-${h}`).count() > 0;
    const value = await page.getByTestId(`select-${h}`).inputValue();
    const blocked = await page.getByTestId(`not-draftable-${h}`).count();
    if (uncertain) {
      expect(value, `${h} is uncertain but pre-selected`).toBe('');
      await expect(page.getByTestId(`low-confidence-${h}`)).toContainText('Uncertain — please select');
    } else if (!blocked) {
      expect(value, `${h} is confident but not pre-selected`).not.toBe('');
    }
    if (!status.models[h].answers_automatically && !(h === 'sleeve_style' && status.models.sleeve_length.answers_automatically)) {
      expect(uncertain, `${h} has no threshold and must always be uncertain`).toBe(true);
    }
  }

  // the user decides every feature
  await page.getByTestId('select-garment_type').selectOption('blouse');
  await page.getByTestId('select-neckline_type').selectOption('square-neck');
  await page.getByTestId('select-sleeve_length').selectOption('long-sleeve');
  await page.getByTestId('select-sleeve_style').selectOption('regular-sleeve');
  await expect(page.getByTestId('confirm-btn')).toBeEnabled();
  await page.getByTestId('confirm-btn').click();
  await expect(page.getByTestId('confirmed-badge')).toBeVisible();

  // the genuine prediction and score are stored next to the user's choice (research evidence)
  const list = await request.get(`${API}/images/`, { headers: auth });
  const first = ((await list.json()).images || [])[0];
  const body = await (await request.get(`${API}/images/${first.image_id}`, { headers: auth })).json();
  for (const h of HEADS) {
    const p = body.garment_attributes.predictions[h];
    expect(typeof p.label).toBe('string');
    expect(p.confidence).toBeGreaterThan(0);
    expect(body.design_spec.provenance[h].predicted_label).toBe(p.label);           // genuine output preserved
  }
  expect(body.confirmed_attributes.neckline_type).toBe('square-neck');
  expect(body.garment_attributes.model_version).toBe('garment-models-v1');
  expect(body.garment_attributes.checkpoint_sha256).toBe(status.checkpoint_sha256);
});

test('across real photos a feature is pre-selected exactly when its model is confident', async ({ page, request }) => {
  await signIn(page, request);
  const files = ['blouse_05.jpg', 'blouse_08.jpg', 't-shirt_04.jpg', 't-shirt_09.jpg', 'blouse_12.jpg', 't-shirt_12.jpg', 'blouse_16.jpg', 't-shirt_16.jpg'];
  const seen = { uncertain: 0, confident: 0 };
  for (const f of files) {
    await analyse(page, f);
    for (const h of HEADS) {
      const uncertain = await page.getByTestId(`low-confidence-${h}`).count() > 0;
      const value = await page.getByTestId(`select-${h}`).inputValue();
      if (uncertain) {
        expect(value, `${f} ${h}`).toBe('');                                          // never forced
        seen.uncertain += 1;
      } else if (await page.getByTestId(`not-draftable-${h}`).count()) {
        expect(value, `${f} ${h}`).toBe('');                                          // confident but not draftable: the note explains why
      } else {
        expect(value, `${f} ${h}`).not.toBe('');                                      // a confident, draftable suggestion is filled in
        seen.confident += 1;
      }
    }
    // a sleeveless garment never gets a sleeve style other than "none"
    const sleeve = await page.getByTestId('select-sleeve_length').inputValue();
    if (sleeve === 'sleeveless') expect(['', 'none']).toContain(await page.getByTestId('select-sleeve_style').inputValue());
  }
  console.log(`features over ${files.length} photos: ${seen.confident} filled in automatically, ${seen.uncertain} left as "please select"`);
  expect(seen.uncertain + seen.confident).toBeGreaterThan(0);
});
