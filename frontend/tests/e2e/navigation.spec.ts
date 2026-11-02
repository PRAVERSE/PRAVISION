import { test, expect } from '@playwright/test';

test.describe('Test 2 — Route-Level & Component-Level Navigation', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('text=PRAVISION').first()).toBeVisible();
  });

  test('Navigates across analytical workspaces and lazy-loaded modules without error', async ({ page }) => {
    const consoleErrors: string[] = [];
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        consoleErrors.push(msg.text());
      }
    });

    const targetViews = [
      { navLabel: 'Case Dossiers', expectedContent: 'Case' },
      { navLabel: 'Gotham Link Graph', expectedContent: 'Graph' },
      { navLabel: 'Global Tactical Map', expectedContent: 'Geospatial' },
      { navLabel: 'Timeline Analysis', expectedContent: 'Timeline' },
      { navLabel: 'Threat Intel & IOCs', expectedContent: 'Threat' },
      { navLabel: 'Entity Database', expectedContent: 'Entit' },
      { navLabel: 'Evidence Center', expectedContent: 'Evidence' },
      { navLabel: 'AI Intelligence Copilot', expectedContent: 'Intelligence' },
      { navLabel: 'Tool Center (89)', expectedContent: 'Tool' },
      { navLabel: 'Reports & Export', expectedContent: 'Report' },
      { navLabel: 'System Admin', expectedContent: 'Settings' }
    ];

    for (const view of targetViews) {
      const navButton = page.locator(`button:has-text("${view.navLabel}")`).first();
      await expect(navButton).toBeVisible();
      await navButton.click();

      // Wait for lazy-loaded component to resolve
      await page.waitForTimeout(500);

      // Verify that the view renders without throwing a chunk error
      const mainContent = page.locator('main');
      await expect(mainContent).toBeVisible();
      await expect(mainContent).toContainText(view.expectedContent, { ignoreCase: true });
    }

    // Filter out transient or non-fatal third-party network messages (e.g. OpenSky CORS)
    const fatalErrors = consoleErrors.filter(e => 
      !e.includes('favicon') && 
      !e.includes('net::ERR_') &&
      !e.includes('opensky') &&
      !e.includes('CORS policy') &&
      !e.includes('WS communication error')
    );
    expect(fatalErrors).toHaveLength(0);
  });
});

