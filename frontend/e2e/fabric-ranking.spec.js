// Real React -> Flask -> MongoDB regression, independent of trained image-model availability.
// Test-user answers exercise elicitation; they are not research participant/expert responses.
import { test, expect } from '@playwright/test';

const API = process.env.E2E_API_URL || 'http://127.0.0.1:5055/api';
const measurements = { bust_cm: 88, waist_cm: 70, hip_cm: 94, shoulder_width_cm: 37,
  back_waist_length_cm: 40, shoulder_to_bust_cm: 25, waist_to_hip_cm: 20,
  garment_length_cm: 65, bicep_cm: 28, sleeve_cm: 24, sleeve_end_cm: 27 };

for (const device of ['desktop', 'phone']) {
test.describe(device, () => {
  test.use({ viewport: device === 'phone' ? { width: 390, height: 844 } : { width: 1440, height: 1000 } });
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
    await expect(page.getByRole('button', { name: 'Find recommended fabrics' })).toBeDisabled();
    await expect(page.locator('#fabric-pairwise')).toBeHidden();
    await page.screenshot({ path: testInfo.outputPath('fabric-preferences.png'), fullPage: true });
    const middle = garment === 'blouse' ? 'thickness' : 'air_flow';
    for (const key of ['mass', middle, 'thermal_resistance']) {
      await page.locator(`#fabric-goal-${key}`).selectOption(key === 'air_flow' ? 'benefit' : 'cost');
    }
    await expect(page.getByRole('button', { name: 'Find recommended fabrics' })).toBeDisabled();
    if (device === 'phone') {
      await page.getByRole('button', { name: 'Set priorities individually' }).click();
      for (const [left, right] of [['mass', middle], ['mass', 'thermal_resistance'], [middle, 'thermal_resistance']]) {
        await page.locator(`#fabric-pair-${left}-${right}`).selectOption(left === 'mass' ? '3' : '1');
      }
    } else {
      await page.getByRole('button', { name: 'Treat all properties equally' }).click();
    }
    await page.getByRole('button', { name: 'Find recommended fabrics' }).click();
    await expect(page.getByTestId('ranked-fabrics')).toBeVisible();
    await expect(page.getByTestId('ranked-fabrics').locator('article')).toHaveCount(1);
    await expect(page.getByRole('heading', { name: 'Recommended materials' })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Other materials' })).toBeVisible();
    await expect(page.locator('.fabric-recommendation details')).toHaveCount(0);
    await expect(page.getByText(/^Construction:.*drafting block/)).toHaveCount(0);
    await expect(page.getByTestId('fabric-preference-summary')).toBeVisible();
    await expect(page.getByTestId('fabric-preference-summary')).toContainText(device === 'phone' ? 'Most important: Fabric weight' : 'All properties equally important');
    await expect(page.getByTestId('fabric-selection-summary')).toHaveCount(0);
    const first = page.getByTestId('ranked-fabrics').locator('article').first();
    await expect(first).toContainText('Recommended');
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
    await page.screenshot({ path: testInfo.outputPath('ranked-samples.png'), fullPage: true });
    await first.getByRole('button', { name: 'View Details' }).click();
    await expect(page.getByRole('heading', { name: 'About this material' })).toBeVisible();
    await expect(page.getByRole('dialog')).toContainText('100% cotton');
    await page.screenshot({ path: testInfo.outputPath('material-details.png'), fullPage: true });
    await page.getByText('Measurement references', { exact: true }).click();
    await expect(page.getByRole('dialog')).toContainText('Your comparison consistency ratio: 0.000');
    if (device === 'phone') {
      await expect(page.getByRole('dialog').getByRole('cell', { name: '60.0%' })).toHaveCount(1);
      await expect(page.getByRole('dialog').getByRole('cell', { name: '20.0%' })).toHaveCount(2);
    } else {
      await expect(page.getByRole('dialog').getByRole('cell', { name: '33.3%' })).toHaveCount(3);
    }
    const sourceLink = page.getByRole('dialog').getByRole('link');
    await expect(sourceLink).toHaveAttribute('href', garment === 'blouse'
      ? 'https://jtatm.textiles.ncsu.edu/index.php/JTATM/article/view/3836'
      : 'https://pmc.ncbi.nlm.nih.gov/articles/PMC9104909/');
    await page.getByRole('button', { name: 'Close modal' }).focus();
    await expect(page.getByRole('button', { name: 'Close modal' })).toBeFocused();
    await page.keyboard.press('Shift+Tab');
    await expect(page.getByRole('button', { name: 'Select material' })).toBeFocused();
    await page.keyboard.press('Tab');
    await expect(page.getByRole('button', { name: 'Close modal' })).toBeFocused();
    await page.keyboard.press('Escape');
    await expect(first.getByRole('button', { name: 'View Details' })).toBeFocused();
    await first.getByRole('button', { name: 'Select fabric', exact: true }).click();
    if (device === 'desktop') {
      const last = page.getByTestId('other-fabrics').locator('article').filter({ has: page.getByRole('button', { name: 'Select fabric', exact: true }) }).first();
      const chosenId = await last.getAttribute('data-testid');
      await last.getByRole('button', { name: 'Select fabric', exact: true }).click();
      await expect(page.getByTestId('other-fabrics').getByTestId(chosenId)).toHaveClass(/selected/);
    }
    await expect(page.getByTestId('fabric-selection-summary')).toContainText('Selected fabric:');
    await page.getByRole('button', { name: 'Edit preferences' }).click();
    await expect(page.locator('#fabric-goal-mass')).toHaveValue('cost');
    await expect(page.getByTestId('fabric-selection-summary')).toBeVisible();
    // Opening the editor preserves the choice; an actual goal edit invalidates it.
    await page.locator('#fabric-goal-mass').selectOption('benefit');
    await expect(page.getByTestId('ranked-fabrics')).toHaveCount(0);
    await expect(page.getByTestId('fabric-selection-summary')).toHaveCount(0);
    await page.locator('#fabric-goal-mass').selectOption('cost');
    await page.getByRole('button', { name: 'Find recommended fabrics' }).click();
    await expect(first).toContainText('Recommended');
    await first.getByRole('button', { name: 'Select fabric', exact: true }).click();
    await page.reload();
    await expect(page.getByTestId('fabric-selection-summary')).toBeVisible();
    await expect(page.getByTestId('fabric-preference-summary')).toBeVisible();
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
    await expect(page.getByTestId('saved-fabric-evidence')).toContainText(device === 'phone' ? '60.0%' : '33.3%');
  });
}
});
}
