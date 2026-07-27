import { defineConfig, devices } from '@playwright/test';

/**
 * AXIS e2e — Chromium smoke by default.
 * webServer starts Vite on :4173 (preview) or :3000 (dev) via package scripts.
 */
export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: process.env.CI ? [['list'], ['html', { open: 'never' }]] : 'list',
  timeout: 60_000,
  expect: { timeout: 10_000 },
  use: {
    baseURL: process.env.AXIS_E2E_BASE || 'http://127.0.0.1:4173',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  webServer: {
    command: process.env.AXIS_E2E_CMD || 'bun run build && bun run preview -- --host 127.0.0.1 --port 4173',
    url: process.env.AXIS_E2E_BASE || 'http://127.0.0.1:4173',
    reuseExistingServer: !process.env.CI,
    timeout: 180_000,
  },
});
