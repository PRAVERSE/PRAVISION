import { test, expect } from '@playwright/test';

test.describe('Test 3 & 9 — Investigation Intake & Seven-Mode Regression', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test('Submits synthetic investigation and verifies automatic classification', async ({ page }) => {
    // Navigate to Universal Intake
    await page.locator('button:has-text("Universal Intake")').first().click();
    await page.waitForTimeout(400);

    // Locate the intake input field
    const inputField = page.locator('input[type="text"]').first();
    await expect(inputField).toBeVisible();

    // Type a synthetic email target
    await inputField.fill('osint.verification.alpha@pravision.local');

    // Trigger classification via API check
    const classifyRes = await page.request.post('/api/classify', {
      data: { input: 'osint.verification.alpha@pravision.local' }
    });
    expect(classifyRes.ok()).toBeTruthy();
    const classification = await classifyRes.json();
    expect(classification.detected_type).toBe('email');
    expect(classification.mode).toBe('mode_3_email');
  });

  test('Seven Investigation Modes Regression: All 7 modes remain accessible', async ({ page }) => {
    const modes = [
      { name: '1. Identity / Username', navLabel: 'Username Intelligence', textCheck: 'Username' },
      { name: '2. Media Forensics', navLabel: 'Image Forensics', textCheck: 'Image' },
      { name: '3. Email Intelligence', navLabel: 'Email Intelligence', textCheck: 'Email' },
      { name: '4. Phone Intelligence', navLabel: 'Phone Intelligence', textCheck: 'Phone' },
      { name: '5. Website / Domain', navLabel: 'Domain & Web Intel', textCheck: 'Domain' },
      { name: '6. Infrastructure / Asset', navLabel: 'Infrastructure Recon', textCheck: 'Infra' },
      { name: '7. Global Situational', navLabel: 'Universal Intake', textCheck: 'Intake' }
    ];

    for (const m of modes) {
      const btn = page.locator(`button:has-text("${m.navLabel}")`).first();
      await expect(btn).toBeVisible();
      await btn.click();
      await page.waitForTimeout(300);

      const main = page.locator('main');
      await expect(main).toContainText(m.textCheck, { ignoreCase: true });
    }
  });
});

