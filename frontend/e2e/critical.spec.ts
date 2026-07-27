/**
 * @critical AXIS product journeys — mock network only.
 */
import { test, expect } from '@playwright/test';

test.describe('AXIS critical journeys @critical', () => {
  test.beforeEach(async ({ page }) => {
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
          series: { close: [1, 2, 3, 4, 5] },
          events: [
            { kind: 'entry', id: 'L', direction: 'long', bar_time: 1, ohlc: [100, 101, 99, 100] },
            { kind: 'close', id: 'L', bar_time: 5, ohlc: [110, 111, 109, 110] },
          ],
          meta: { script_name: 'critical', overlay: true, ms: 8 },
        }),
      });
    });
    await page.route('**/api.binance.com/**', (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: '[]' }),
    );
  });

  test('load mock-walk → run → Results drawer opens', async ({ page }) => {
    await page.goto('/');
    await page.getByTestId('axis-select-source').selectOption('mock-walk');
    await page.getByTestId('axis-btn-load').click();
    await expect(page.getByTestId('axis-statusbar')).toBeVisible({ timeout: 15_000 });

    await page.getByTestId('axis-select-engine').selectOption('server');
    await page.getByTestId('axis-btn-run').click();

    // Runner opens results panel on non-silent run
    await expect(page.getByTestId('axis-results')).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText('Strategy').first()).toBeVisible();
  });

  test('Results toggle and Indicators panel', async ({ page }) => {
    await page.goto('/');
    await page.getByTestId('axis-btn-results').click();
    await expect(page.getByTestId('axis-results')).toBeVisible();
    await page.getByTestId('axis-btn-results').click();
    await expect(page.getByTestId('axis-results')).toHaveCount(0);

    await page.getByTestId('axis-btn-indicators').click();
    await expect(page.getByTestId('axis-indicators')).toBeVisible();
  });

  test('drawing toolbar after bars load', async ({ page }) => {
    await page.goto('/');
    await page.getByTestId('axis-select-source').selectOption('mock-walk');
    await page.getByTestId('axis-btn-load').click();
    await expect(page.getByTestId('axis-drawing-toolbar')).toBeVisible({ timeout: 15_000 });
  });

  test('Settings dialog has testid and closes', async ({ page }) => {
    await page.goto('/');
    await page.getByTestId('axis-btn-settings').click();
    await expect(page.getByTestId('axis-settings')).toBeVisible();
    await page.getByRole('button', { name: 'Cancel' }).click();
    await expect(page.getByTestId('axis-settings')).toHaveCount(0);
  });
});
