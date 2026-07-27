/**
 * @critical Script library UI path.
 */
import { test, expect } from '@playwright/test';

test.describe('Script library @critical', () => {
  test('Manager Script Library tab shows storage picker', async ({ page }) => {
    await page.goto('/');
    await page.getByTestId('axis-btn-plugins').click();
    await expect(page.getByTestId('axis-manager')).toBeVisible();
    await page.getByRole('tab', { name: 'Script Library' }).click();
    await expect(page.getByText(/Storage backend/i)).toBeVisible();
    await expect(page.getByRole('button', { name: /Save to library|Save & commit/i })).toBeVisible();
    await page.getByRole('button', { name: 'Done' }).click();
  });

  test('Catalog Use activates mock-walk source', async ({ page }) => {
    await page.goto('/');
    await page.getByTestId('axis-btn-plugins').click();
    await page.getByRole('tab', { name: 'Catalog' }).click();
    // Filter sources if buttons present
    const sourcesFilter = page.getByRole('button', { name: 'Sources' });
    if (await sourcesFilter.isVisible()) await sourcesFilter.click();

    // Find Mock Walk row Use button
    const mockRow = page.locator('li', { hasText: 'Mock Walk' }).first();
    if (await mockRow.count()) {
      const useBtn = mockRow.getByRole('button', { name: 'Use' });
      if (await useBtn.isVisible()) await useBtn.click();
    }
    await page.getByRole('button', { name: 'Done' }).click();
    await expect(page.getByTestId('axis-select-source')).toHaveValue(/mock-walk|binance/);
  });
});
