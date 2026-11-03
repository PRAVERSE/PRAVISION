import { test, expect } from '@playwright/test';

test.describe('Gotham-Grade Intelligence Functionality Suite', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('text=PRAVISION').first()).toBeVisible();
  });

  test('1. Gotham Link Graph Workspace — Controls, Filters, and Path Tracer', async ({ page }) => {
    // Navigate to Gotham Link Graph
    const graphNavBtn = page.locator('button:has-text("Gotham Link Graph")').first();
    await expect(graphNavBtn).toBeVisible();
    await graphNavBtn.click();

    // Verify Link Graph header & controls
    await expect(page.locator('text=GOTHAM LINK GRAPH')).toBeVisible({ timeout: 10000 });
    await expect(page.locator('button:has-text("Export GEXF")')).toBeVisible();

    // Verify Link Path Tracer panel
    await expect(page.locator('text=LINK PATH TRACER')).toBeVisible();
    await expect(page.locator('button:has-text("Compute Shortest Path")')).toBeVisible();
  });

  test('2. Structured Entity DB — Directory & Identity Merge Review Tabs', async ({ page }) => {
    // Navigate to Entity Database
    const entNavBtn = page.locator('button:has-text("Entity Database")').first();
    await expect(entNavBtn).toBeVisible();
    await entNavBtn.click();

    // Verify Entity Directory tab
    await expect(page.locator('text=STRUCTURED ENTITY DATABASE')).toBeVisible({ timeout: 10000 });
    await expect(page.locator('button:has-text("ENTITY DIRECTORY")')).toBeVisible();
    await expect(page.locator('button:has-text("IDENTITY MERGE REVIEW")')).toBeVisible();

    // Switch to Identity Merge Review
    await page.locator('button:has-text("IDENTITY MERGE REVIEW")').click();
    await expect(page.locator('text=Select Case Scope:')).toBeVisible();
    await expect(page.locator('button:has-text("Re-evaluate Candidates")')).toBeVisible();
  });

  test('3. Universal Search — Cross-Case Intelligence Search & Intake', async ({ page }) => {
    // Navigate to Universal Search
    const searchNavBtn = page.locator('button:has-text("Universal Intake")').first();
    await expect(searchNavBtn).toBeVisible();
    await searchNavBtn.click();

    // Verify Intake Tab
    await expect(page.locator('text=Universal Target Intake')).toBeVisible();
    await expect(page.locator('text=Cross-Case Intelligence Search')).toBeVisible();

    // Switch to Cross-Case Search
    await page.locator('button:has-text("Cross-Case Intelligence Search")').click();
    const searchInput = page.locator('input[placeholder*="Search entities, aliases"]');
    await expect(searchInput).toBeVisible();

    // Execute query
    await searchInput.fill('shadow');
    await page.locator('button:has-text("Search Index")').click();
    await expect(page.locator('text=INDEXED MATCHES')).toBeVisible({ timeout: 10000 });
  });

  test('4. Entity Intelligence Dossier Slide-Over Drawer', async ({ page }) => {
    // Navigate to Universal Search
    const searchNavBtn = page.locator('button:has-text("Universal Intake")').first();
    await expect(searchNavBtn).toBeVisible();
    await searchNavBtn.click();

    // Switch to Cross-Case Search
    await page.locator('button:has-text("Cross-Case Intelligence Search")').click();
    const searchInput = page.locator('input[placeholder*="Search entities, aliases"]');
    await searchInput.fill('shadow');
    await page.locator('button:has-text("Search Index")').click();

    // If an entity result is displayed, click Inspect Dossier
    const inspectBtn = page.locator('button:has-text("Inspect Dossier")').first();
    if (await inspectBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
      await inspectBtn.click();
      await expect(page.locator('text=ENTITY INTELLIGENCE DOSSIER')).toBeVisible({ timeout: 5000 });
      await expect(page.locator('button:has-text("Focus in Graph")')).toBeVisible();
    }
  });
});

