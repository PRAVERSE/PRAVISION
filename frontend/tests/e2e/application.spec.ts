import { test, expect } from '@playwright/test';

test.describe('Test 1 — Application Startup & Health', () => {
  test('Application boots cleanly, renders header, command center, and backend is healthy', async ({ page }) => {
    // Collect console errors to detect any runtime failures
    const consoleErrors: string[] = [];
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        consoleErrors.push(msg.text());
      }
    });

    // 1. Navigate to application root
    await page.goto('/');

    // 2. Verify Title and Branding
    await expect(page.locator('text=PRAVISION').first()).toBeVisible();
    await expect(page.locator('text=Universal Intelligence Platform').first()).toBeVisible();

    // 3. Verify Command Center landing view is visible
    await expect(page.locator('text=Command Center').first()).toBeVisible();

    // 4. Verify no fatal unhandled React or bundle loading errors
    const fatalErrors = consoleErrors.filter(e => !e.includes('favicon') && !e.includes('WS parse error'));
    expect(fatalErrors).toHaveLength(0);

    // 5. Verify backend health endpoint via API
    const response = await page.request.get('/api/storage/status');
    expect(response.ok()).toBeTruthy();
    const statusData = await response.json();
    expect(statusData).toHaveProperty('database');
    expect(statusData).toHaveProperty('object_storage');
  });
});
