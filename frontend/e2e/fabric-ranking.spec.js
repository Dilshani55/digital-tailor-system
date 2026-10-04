// Real React -> Flask -> MongoDB regression, independent of trained image-model availability.
// Test-user answers exercise elicitation; they are not research participant/expert responses.
import { test, expect } from '@playwright/test';

const API = process.env.E2E_API_URL || 'http://127.0.0.1:5055/api';
const measurements = { bust_cm: 88, waist_cm: 70, hip_cm: 94, shoulder_width_cm: 37,
  back_waist_length_cm: 40, shoulder_to_bust_cm: 25, waist_to_hip_cm: 20,
  garment_length_cm: 65, bicep_cm: 28, sleeve_cm: 24, sleeve_end_cm: 27 };

for (const garment of ['blouse', 't-shirt']) {
  test(`${garment}: published samples, user preferences and saved evidence`, async ({ page, request }, testInfo) => {
    const email = `fabric_e2e_${garment}_${Date.now()}@example.test`;
    const password = 'E2e-Passw0rd!';
    const registered = await request.post(`${API}/auth/register`, { data: { full_name: 'Fabric E2E Tester', email, password } });
    expect(registered.ok()).toBeTruthy();
    await page.goto('/auth');
    await page.locator('#login-email').fill(email);
    await page.locator('#login-password').fill(password);
    await page.getByRole('button', { name: 'Sign In' }).click();
    await page.waitForURL('**/dashboard');
    await page.goto('/upload');
    await page.getByLabel('Customer name').fill('Fabric regression customer');
    await page.getByRole('button', { name: 'Continue to upload' }).click();
    await page.getByRole('button', { name: /choose the design manually/i }).click();
    await page.getByTestId('select-garment_type').selectOption(garment);
    await page.getByTestId('select-neckline_type').selectOption('round-neck');
    await page.getByTestId('select-sleeve_length').selectOption('short-sleeve');
    await page.getByTestId('select-sleeve_style').selectOption('regular-sleeve');
    await page.getByTestId('confirm-btn').click();
    await page.getByRole('button', { name: 'Continue to measurements' }).click();
    for (const [key, value] of Object.entries(measurements)) {
      if (await page.locator(`#meas-${key}`).count()) await page.locator(`#meas-${key}`).fill(String(value));
    }
    await page.getByRole('button', { name: 'Save and continue' }).click();
    await expect(page.getByTestId('fabric-preferences')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Compare fabric samples' })).toBeDisabled();
    const middle = garment === 'blouse' ? 'thickness' : 'air_flow';
    for (const key of ['mass', middle, 'thermal_resistance']) {
      await page.locator(`#fabric-goal-${key}`).selectOption(key === 'air_flow' ? 'benefit' : 'cost');
    }
    for (const [left, right] of [['mass', middle], ['mass', 'thermal_resistance'], [middle, 'thermal_resistance']]) {
      await page.locator(`#fabric-pair-${left}-${right}`).selectOption('1');
    }
    await page.getByRole('button', { name: 'Compare fabric samples' }).click();
    await expect(page.getByTestId('ranked-fabrics')).toBeVisible();
    const first = page.getByTestId('ranked-fabrics').locator('article').first();
    await expect(first).toContainText('Rank 1');
    await page.screenshot({ path: testInfo.outputPath('ranked-samples.png'), fullPage: true });
    await first.getByRole('button', { name: 'View Details' }).click();
    await expect(page.getByRole('dialog')).toContainText('Your comparison consistency ratio: 0.000');
    await expect(page.getByRole('dialog').getByRole('cell', { name: '33.3%' })).toHaveCount(3);
    const sourceLink = page.getByRole('dialog').getByRole('link');
    await expect(sourceLink).toHaveAttribute('href', garment === 'blouse'
      ? 'https://jtatm.textiles.ncsu.edu/index.php/JTATM/article/view/3836'
      : 'https://pmc.ncbi.nlm.nih.gov/articles/PMC9104909/');
    await page.getByRole('button', { name: 'Select this sample' }).click();
    const generatedResponse = page.waitForResponse((r) => r.url().endsWith('/api/patterns/generate') && r.request().method() === 'POST');
    await page.getByRole('button', { name: 'Confirm and generate pattern' }).click();
    const generated = await (await generatedResponse).json();
    expect(generated.validation_passed).toBe(true);
    const snapshot = generated.fabric_selection_snapshot;
    expect(snapshot.ranking_audit.weight_source).toBe('user_preferences');
    expect(snapshot.ranking_audit.preferences.goals[middle]).toBe(middle === 'air_flow' ? 'benefit' : 'cost');
    expect(snapshot.construction).toBe(garment === 'blouse' ? 'woven' : 'knit');
    expect(snapshot.sample.values.mass.value).toBeGreaterThan(0);
    await expect(page.getByRole('heading', { name: 'Pattern preview' })).toBeVisible();
    await page.goto(`/patterns/${generated.pattern_id}`);
    await expect(page.getByTestId('saved-fabric-evidence')).toContainText(snapshot.sample.sample_id);
    await page.getByText('Your saved fabric priorities', { exact: true }).click();
    await expect(page.getByTestId('saved-fabric-evidence')).toContainText('33.3%');
  });
}
