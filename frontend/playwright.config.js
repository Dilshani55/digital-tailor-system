import { defineConfig } from '@playwright/test';

// Full-stack browser test. It needs the real backend (with MongoDB) and the frontend dev server;
// see docs/TESTING.md ("End-to-end") for the exact commands. URLs can be overridden with
// E2E_BASE_URL (frontend) and E2E_API_URL (backend /api).
export default defineConfig({
  testDir: './e2e',
  timeout: 300_000,
  expect: { timeout: 60_000 },
  workers: 1,
  reporter: [['list']],
  outputDir: 'test-results',
  use: {
    baseURL: process.env.E2E_BASE_URL || 'http://127.0.0.1:3055',
    channel: process.env.E2E_BROWSER_CHANNEL || 'chrome',
    headless: true,
    acceptDownloads: true,
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
  },
});
