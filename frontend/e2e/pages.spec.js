// Every page renders, every sidebar link works, and nothing logs a JavaScript error.
import { test, expect } from '@playwright/test';

const API = process.env.E2E_API_URL || 'http://127.0.0.1:5055/api';

test('all pages and navigation links work with no console errors', async ({ page, request }) => {
  const problems = [];
  page.on('pageerror', (e) => problems.push(`pageerror: ${e.message}`));
  page.on('console', (m) => {
    if (m.type() !== 'error') return;
    const t = m.text();
    // third-party Google script blocked / offline is not an application error
    if (/accounts\.google|gsi\/client|Failed to load resource.*(google|gstatic)/i.test(t)) return;
    if (/status of 403/.test(t)) return;               // checked precisely below (only /research/ may answer 403)
    problems.push(`console: ${t}`);
  });
  // every API call must succeed, except the researcher-only endpoints answering 403 to an ordinary account
  page.on('response', (r) => {
    if (!r.url().includes('/api/') || r.status() < 400) return;
    if (r.status() === 403 && r.url().includes('/api/research/')) return;
    problems.push(`api ${r.status()} ${r.url()}`);
  });

  const email = `e2e_pages_${Date.now()}@example.test`;
  const reg = await request.post(`${API}/auth/register`, { data: { full_name: 'Pages Tester', email, password: 'E2e-Passw0rd!' } });
  expect(reg.ok()).toBeTruthy();

  // public pages
  await page.goto('/');
  await expect(page.getByRole('link', { name: /Start designing|Open workspace/ }).first()).toBeVisible();
  await page.goto('/auth');
  await expect(page.locator('#login-email')).toBeVisible();

  // sign in
  await page.locator('#login-email').fill(email);
  await page.locator('#login-password').fill('E2e-Passw0rd!');
  await page.getByRole('button', { name: 'Sign In' }).click();
  await page.waitForURL('**/dashboard', { timeout: 30_000 });

  // each protected page renders real content (empty states for a brand-new account)
  const pages = ['/dashboard', '/upload', '/history', '/fabric-savings', '/measurements', '/customers', '/settings'];
  for (const path of pages) {
    await page.goto(path);
    await expect(page.locator('.main-content')).toBeVisible();
    const text = (await page.locator('.main-content').innerText()).trim();
    expect(text.length, `${path} is blank`).toBeGreaterThan(20);
    expect(text, `${path} shows a raw error`).not.toMatch(/Traceback|undefined|NaN|\[object Object\]/);
    // only the content area scrolls: the browser page itself must not (no blank area below the app)
    const overflow = await page.evaluate(() => document.documentElement.scrollHeight - window.innerHeight);
    expect(overflow, `${path}: the page itself scrolls`).toBeLessThanOrEqual(1);
  }

  // empty state for a new user
  await page.goto('/history');
  await expect(page.getByText('Your pattern library is empty')).toBeVisible();

  // every sidebar link goes somewhere that renders
  await page.goto('/dashboard');
  const hrefs = await page.locator('.sidebar a.sidebar-item').evaluateAll((els) => els.map((e) => e.getAttribute('href')));
  expect(hrefs.length).toBeGreaterThanOrEqual(5);
  for (const href of hrefs) {
    await page.goto(href);
    await expect(page.locator('.main-content')).toBeVisible();
    expect((await page.locator('.main-content').innerText()).trim().length).toBeGreaterThan(20);
  }

  // unknown address falls back to the home page instead of a blank screen
  await page.goto('/this-page-does-not-exist');
  await expect(page).toHaveURL(/\/$/);

  // research features are not part of the customer app
  await page.goto('/dashboard');
  await expect(page.getByText(/Research(er)? Metrics/i)).toHaveCount(0);
  await page.goto('/researcher');
  await expect(page).toHaveURL(/\/$/);          // no such page: falls back to home

  expect(problems, problems.join('\n')).toEqual([]);
});
