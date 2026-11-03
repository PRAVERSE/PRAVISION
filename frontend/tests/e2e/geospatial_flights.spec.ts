import { test, expect } from '@playwright/test';

test.describe('PRAVISION Phase 2.5 OpenSky Flight Telemetry & Geospatial Suite', () => {

  test('should load Global Tactical Map and display OpenSky attribution and telemetry layer', async ({ page }) => {
    // Collect console errors to verify no CORS errors
    const corsErrors: string[] = [];
    page.on('console', msg => {
      if (msg.type() === 'error' && msg.text().includes('Access-Control-Allow-Origin')) {
        corsErrors.push(msg.text());
      }
    });

    await page.goto('/');

    // Navigate to Global Tactical Map
    const mapNav = page.getByRole('complementary').getByRole('button', { name: /Global Tactical Map/i });
    await expect(mapNav).toBeVisible({ timeout: 15000 });
    await mapNav.click();

    // Verify map controls appear
    await expect(page.getByText('Global Geospatial Layers')).toBeVisible({ timeout: 15000 });
    await expect(page.getByRole('button', { name: /Aircraft/i })).toBeVisible();
    await expect(page.getByRole('button', { name: /Seismic/i })).toBeVisible();
    await expect(page.getByRole('button', { name: /Investigation Evidence/i })).toBeVisible();

    // Verify OpenSky attribution banner
    await expect(page.getByText(/The OpenSky Network/i)).toBeVisible({ timeout: 15000 });

    // Verify zero CORS errors occurred in browser
    expect(corsErrors).toHaveLength(0);
  });

});

