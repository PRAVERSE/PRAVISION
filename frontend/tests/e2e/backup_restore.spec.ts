import { test, expect } from '@playwright/test';

test.describe('Test 6, 7 & 8 — Case Dossiers, Backup & Restore, Error Handling', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test('Case Dossiers View renders and lists saved investigations', async ({ page }) => {
    await page.locator('button:has-text("Case Dossiers")').first().click();
    await page.waitForTimeout(500);

    const main = page.locator('main');
    await expect(main).toBeVisible();
    await expect(main).toContainText('Case', { ignoreCase: true });
  });

  test('Automated Backup & Restore verification through API and browser session', async ({ page }) => {
    test.setTimeout(90000);
    // 1. Create a transient test case
    const caseRes = await page.request.post('/api/cases', {
      data: {
        title: 'Playwright Automated E2E Case',
        description: 'Automated Playwright backup verification test',
        classification: 'RESTRICTED',
        tags: ['playwright', 'e2e']
      }
    });
    expect(caseRes.ok()).toBeTruthy();
    const caseData = await caseRes.json();
    const caseId = caseData.id;

    // 2. Trigger automated backup for this case
    const backupRes = await page.request.post('/api/backup/run', {
      data: { case_id: caseId, sync_cloud: false }
    });
    expect(backupRes.ok()).toBeTruthy();
    const backupData = await backupRes.json();
    expect(backupData.status).toBe('verified');
    const backupId = backupData.backup_id;

    // 3. Download the encrypted backup archive
    const downloadRes = await page.request.get(`/api/backup/download/${backupId}`);
    expect(downloadRes.ok()).toBeTruthy();
    const backupBytes = await downloadRes.body();
    expect(backupBytes.length).toBeGreaterThan(0);

    // 4. Test dry-run restoration verification
    const restoreRes = await page.request.post('/api/backup/restore', {
      multipart: {
        file: {
          name: `${backupId}.pravision_bkp`,
          mimeType: 'application/octet-stream',
          buffer: backupBytes,
        },
        verify_only: 'true',
        prefix: 'E2E_VERIFY_'
      }
    });
    expect(restoreRes.ok()).toBeTruthy();
    const restoreData = await restoreRes.json();
    expect(restoreData.status).toBe('verified');
    expect(restoreData.backup_id).toBe(backupId);

    // 5. Cleanup test case
    const deleteRes = await page.request.delete(`/api/cases/${caseId}`);
    expect(deleteRes.ok()).toBeTruthy();
  });

  test('Error handling: Invalid form inputs, non-existent endpoints, and corrupted backups', async ({ page }) => {
    // Empty classification input
    const badClassify = await page.request.post('/api/classify', {
      data: { input: '   ' }
    });
    expect(badClassify.status()).toBe(400);

    // Non-existent case
    const badCase = await page.request.get('/api/cases/non-existent-case-id-9999');
    expect(badCase.status()).toBe(404);

    // Corrupted backup upload
    const corruptedRestore = await page.request.post('/api/backup/restore', {
      multipart: {
        file: {
          name: 'corrupted.pravision_bkp',
          mimeType: 'application/octet-stream',
          buffer: Buffer.from('NOT_A_VALID_AES_GCM_BACKUP_CONTAINER'),
        },
        verify_only: 'true'
      }
    });
    expect(corruptedRestore.status()).toBe(400);
  });
});

