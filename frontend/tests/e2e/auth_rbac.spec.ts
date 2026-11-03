import { test, expect } from '@playwright/test';

test.describe('PRAVISION Phase 2.5 Multi-User & RBAC End-to-End Suite', () => {

  test('should display Sign In trigger and open Security & RBAC modal', async ({ page }) => {
    await page.goto('/');

    // Header should contain Sign In button
    const signInBtn = page.getByRole('button', { name: /Sign In/i });
    await expect(signInBtn).toBeVisible({ timeout: 15000 });
    await signInBtn.click();

    // Verify Modal Header & Presets
    await expect(page.getByText('PRAVISION Security & RBAC')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Admin', exact: true })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Case Officer', exact: true })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Analyst', exact: true })).toBeVisible();
  });

  test('should authenticate as Administrator and display ADMIN role badge', async ({ page }) => {
    await page.goto('/');

    // Open modal
    const signInBtn = page.getByRole('button', { name: /Sign In/i });
    await signInBtn.click();

    // Fill Admin credentials
    await page.getByPlaceholder(/admin or case_officer/i).fill('admin');
    await page.getByPlaceholder(/security passphrase/i).fill('PravisionAdmin2026!');

    // Click Sign In
    const submitBtn = page.getByRole('button', { name: /Sign In/i }).last();
    await submitBtn.click();

    // Header should now display admin identity and ADMIN badge
    await expect(page.getByRole('button', { name: /admin ADMIN/i })).toBeVisible({ timeout: 15000 });

    // Sidebar should reflect ADMIN role
    await expect(page.getByText('ADMIN', { exact: true }).first()).toBeVisible();
  });

  test('should authenticate as Field Analyst and reflect role permissions', async ({ page }) => {
    await page.goto('/');

    // Open modal
    const signInBtn = page.getByRole('button', { name: /Sign In/i });
    await signInBtn.click();

    // Fill Analyst credentials
    await page.getByPlaceholder(/admin or case_officer/i).fill('analyst');
    await page.getByPlaceholder(/security passphrase/i).fill('PravisionAnalyst2026!');

    // Click Sign In
    const submitBtn = page.getByRole('button', { name: /Sign In/i }).last();
    await submitBtn.click();

    // Header should display analyst identity and ANALYST badge
    await expect(page.getByRole('button', { name: /analyst ANALYST/i })).toBeVisible({ timeout: 15000 });

    // Navigate to Case Dossiers view
    const casesNav = page.locator('aside').getByRole('button', { name: /Case Dossiers/i });
    await casesNav.click();
    await expect(page.getByText(/Case Dossiers/i).first()).toBeVisible();
  });

  test('should sign out successfully and restore unauthenticated state', async ({ page }) => {
    await page.goto('/');

    // Login first as Officer
    await page.getByRole('button', { name: /Sign In/i }).click();
    await page.getByPlaceholder(/admin or case_officer/i).fill('case_officer');
    await page.getByPlaceholder(/security passphrase/i).fill('PravisionOfficer2026!');
    await page.getByRole('button', { name: /Sign In/i }).last().click();

    const profileBtn = page.getByRole('button', { name: /case_officer CASE_OFFICER/i });
    await expect(profileBtn).toBeVisible({ timeout: 15000 });

    // Click profile button to open session management
    await profileBtn.click();

    // Click Sign Out
    const signOutBtn = page.getByRole('button', { name: /Sign Out Current Session/i });
    await expect(signOutBtn).toBeVisible();
    await signOutBtn.click();

    // Verify restoration of Sign In state
    await expect(page.getByRole('button', { name: /Sign In/i })).toBeVisible({ timeout: 10000 });
  });

});

