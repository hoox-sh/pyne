/**
 * @smoke AXIS critical path — load app, mock source, mock /run, open Manager.
 */
import { test, expect } from '@playwright/test';

test.describe('AXIS smoke @smoke', () => {
  test.beforeEach(async ({ page }) => {
    // Mock Pro API run endpoint (server engine)
    await page.route('**/run**', async (route) => {
      if (route.request().method() === 'OPTIONS') {
        await route.fulfill({ status: 204, headers: { 'Access-Control-Allow-Origin': '*' } });
        return;
      }
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          status: 'success',
          plots: [1, 2, 3, 4, 5],
          series: {},
          events: [],
          meta: { script_name: 'smoke', overlay: true, ms: 12 },
        }),
      });
    });

    // Avoid real exchange traffic during smoke
    await page.route('**/api.binance.com/**', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([]),
      }),
    );
  });

  test('loads shell with topbar and chart host', async ({ page }) => {
    await page.goto('/');
    await expect(page).toHaveTitle(/AXIS/i);
    await expect(page.getByTestId('axis-topbar')).toBeVisible();
    await expect(page.getByTestId('axis-brand')).toContainText('AXIS');
    await expect(page.locator('[data-axis-panes]')).toBeVisible();
  });

  test('loads mock-walk bars and runs mocked engine', async ({ page }) => {
    await page.goto('/');
    await page.getByTestId('axis-select-source').selectOption('mock-walk');
    await page.getByTestId('axis-btn-load').click();

    // Status bar should leave loading
    await expect(page.getByText(/Loaded \d+ bars|Ready|bars/i).first()).toBeVisible({
      timeout: 15_000,
    });

    await page.getByTestId('axis-select-engine').selectOption('server');
    await page.getByTestId('axis-btn-run').click();

    // After run, status or results should reflect success (no crash)
    await expect(page.getByTestId('axis-topbar')).toBeVisible();
    await page.waitForTimeout(500);
    // Page still interactive
    await expect(page.getByTestId('axis-btn-run')).toBeEnabled();
  });

  test('opens and closes plugin Manager', async ({ page }) => {
    await page.goto('/');
    await page.getByTestId('axis-btn-plugins').click();
    await expect(page.getByTestId('axis-manager')).toBeVisible();
    await expect(page.getByText('Catalog')).toBeVisible();
    await page.getByRole('button', { name: 'Done' }).click();
    await expect(page.getByTestId('axis-manager')).toHaveCount(0);
  });

  test('opens Settings dialog', async ({ page }) => {
    await page.goto('/');
    await page.getByTestId('axis-btn-settings').click();
    await expect(page.getByRole('dialog', { name: /Settings/i })).toBeVisible();
    await page.getByRole('button', { name: 'Cancel' }).click();
  });
});
