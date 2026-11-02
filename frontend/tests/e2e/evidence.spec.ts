import { test, expect } from '@playwright/test';

test.describe('Test 4 & 5 — Graph Analytics & Evidence Vault Lifecycle', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test('Gotham Link Graph renders analytical viewport', async ({ page }) => {
    await page.locator('button:has-text("Gotham Link Graph")').first().click();
    await page.waitForTimeout(500);

    const main = page.locator('main');
    await expect(main).toBeVisible();
    await expect(main).toContainText('Graph', { ignoreCase: true });
  });

  test('Evidence lifecycle: Upload, SHA-256 integrity, retrieval, and verification', async ({ page }) => {
    // 1. Create a synthetic test file
    const testContent = Buffer.from('PRAVISION_PLAYWRIGHT_EVIDENCE_INTEGRITY_CHECK_2026');

    // 2. Upload via API
    const uploadRes = await page.request.post('/api/storage/evidence/upload', {
      multipart: {
        file: {
          name: 'playwright_test_evidence.bin',
          mimeType: 'application/octet-stream',
          buffer: testContent,
        }
      }
    });

    expect(uploadRes.ok()).toBeTruthy();
    const upData = await uploadRes.json();
    expect(upData).toHaveProperty('file_key');
    expect(upData).toHaveProperty('file_hash');
    expect(upData.file_size).toBe(testContent.length);

    const fileKey = upData.file_key;
    const fileHash = upData.file_hash;

    // 3. Download and verify SHA-256 and byte equality
    const downloadRes = await page.request.get(`/api/storage/evidence/${fileKey}`);
    expect(downloadRes.ok()).toBeTruthy();
    const downloadedBuffer = await downloadRes.body();
    expect(downloadedBuffer).toEqual(testContent);

    // Verify response headers
    const returnedHash = downloadRes.headers()['x-evidence-sha256'];
    expect(returnedHash).toBe(fileHash);

    // 4. View Evidence Center in UI
    await page.locator('button:has-text("Evidence Center")').first().click();
    await page.waitForTimeout(400);
    const main = page.locator('main');
    await expect(main).toContainText('Evidence', { ignoreCase: true });
  });
});

