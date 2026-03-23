/**
 * Shared helpers and fixtures for SolarIntel E2E tests.
 */

import { type Page, expect } from "@playwright/test";

// ── Test credentials ─────────────────────────────────────────────────────────

export const TEST_USER = {
  email: `e2e_${Date.now()}@solarintel.sn`,
  password: "E2eTest1234!",
  fullName: "E2E Technicien",
  role: "technicien" as const,
};

export const ADMIN_USER = {
  email: `e2e_admin_${Date.now()}@solarintel.sn`,
  password: "E2eAdmin1234!",
  fullName: "E2E Admin",
  role: "admin" as const,
};

// ── Page helpers ─────────────────────────────────────────────────────────────

/**
 * Fill in the registration form and submit.
 * Assumes the page is already at /register.
 */
export async function fillRegisterForm(
  page: Page,
  user: typeof TEST_USER,
): Promise<void> {
  await page.getByLabel(/full name|nom complet/i).fill(user.fullName);
  await page.getByLabel(/email/i).fill(user.email);
  await page.getByLabel(/password|mot de passe/i).first().fill(user.password);
  // Confirm password if present
  const confirm = page.getByLabel(/confirm|confirmation/i);
  if (await confirm.isVisible()) {
    await confirm.fill(user.password);
  }
  // Role selector (optional — skip if not shown)
  const roleSelect = page.getByLabel(/role/i);
  if (await roleSelect.isVisible()) {
    await roleSelect.selectOption(user.role);
  }
}

/**
 * Register a new user via the UI and return to dashboard.
 */
export async function registerAndLogin(
  page: Page,
  user: typeof TEST_USER,
): Promise<void> {
  await page.goto("/register");
  await fillRegisterForm(page, user);
  await page.getByRole("button", { name: /register|s'inscrire/i }).click();
  // After registration, app redirects to dashboard or login
  await expect(page).toHaveURL(/\/(dashboard|login)/);
  // If redirected to login, sign in
  if (page.url().includes("login")) {
    await page.getByLabel(/email/i).fill(user.email);
    await page.getByLabel(/password|mot de passe/i).fill(user.password);
    await page.getByRole("button", { name: /login|se connecter/i }).click();
    await expect(page).toHaveURL(/\/dashboard/);
  }
}

/**
 * Log in an existing user.
 */
export async function login(
  page: Page,
  email: string,
  password: string,
): Promise<void> {
  await page.goto("/login");
  await page.getByLabel(/email/i).fill(email);
  await page.getByLabel(/password|mot de passe/i).fill(password);
  await page.getByRole("button", { name: /login|se connecter/i }).click();
  await expect(page).toHaveURL(/\/dashboard/);
}

/**
 * Wait for a toast or alert to appear containing the given text.
 */
export async function waitForToast(page: Page, text: string | RegExp): Promise<void> {
  await expect(
    page.locator('[role="alert"], [data-toast], .toast, .notification').filter({ hasText: text }),
  ).toBeVisible({ timeout: 5_000 });
}
