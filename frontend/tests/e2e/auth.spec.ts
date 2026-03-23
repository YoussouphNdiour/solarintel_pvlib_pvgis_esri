/**
 * E2E — Authentication flows
 *
 * Covers: register, login, logout, protected routes, error states.
 */

import { test, expect } from "@playwright/test";
import { TEST_USER, fillRegisterForm, registerAndLogin, login } from "./helpers";

const user = {
  ...TEST_USER,
  email: `auth_spec_${Date.now()}@solarintel.sn`,
};

test.describe("Registration", () => {
  test("shows register form with all required fields", async ({ page }) => {
    await page.goto("/register");
    await expect(page.getByLabel(/email/i)).toBeVisible();
    await expect(page.getByLabel(/password|mot de passe/i).first()).toBeVisible();
    await expect(
      page.getByRole("button", { name: /register|s'inscrire/i }),
    ).toBeVisible();
  });

  test("registers a new user and redirects to dashboard", async ({ page }) => {
    await registerAndLogin(page, user);
    await expect(page).toHaveURL(/\/dashboard/);
  });

  test("shows validation error for duplicate email", async ({ page }) => {
    // Register once
    await registerAndLogin(page, user);
    // Logout
    const logoutBtn = page.getByRole("button", { name: /logout|déconnexion/i });
    if (await logoutBtn.isVisible()) await logoutBtn.click();
    await expect(page).toHaveURL(/\/login/);

    // Try to register again with the same email
    await page.goto("/register");
    await fillRegisterForm(page, user);
    await page.getByRole("button", { name: /register|s'inscrire/i }).click();

    await expect(
      page.getByText(/already exists|déjà utilisé|already registered/i),
    ).toBeVisible({ timeout: 8_000 });
  });

  test("shows validation error for weak password", async ({ page }) => {
    await page.goto("/register");
    await page.getByLabel(/email/i).fill(`weak_pw_${Date.now()}@solarintel.sn`);
    await page.getByLabel(/password|mot de passe/i).first().fill("123");
    await page.getByRole("button", { name: /register|s'inscrire/i }).click();

    await expect(
      page.getByText(/password|mot de passe|trop court|too short/i),
    ).toBeVisible({ timeout: 5_000 });
  });
});

test.describe("Login", () => {
  test.beforeAll(async ({ browser }) => {
    // Pre-register user so login tests have a valid account
    const page = await browser.newPage();
    await registerAndLogin(page, user);
    await page.close();
  });

  test("login with correct credentials redirects to dashboard", async ({ page }) => {
    await login(page, user.email, user.password);
    await expect(page).toHaveURL(/\/dashboard/);
  });

  test("login with wrong password shows error", async ({ page }) => {
    await page.goto("/login");
    await page.getByLabel(/email/i).fill(user.email);
    await page.getByLabel(/password|mot de passe/i).fill("WrongPassword999!");
    await page.getByRole("button", { name: /login|se connecter/i }).click();

    await expect(
      page.getByText(/invalid|incorrect|unauthorized|mauvais/i),
    ).toBeVisible({ timeout: 8_000 });
  });

  test("login with unknown email shows error", async ({ page }) => {
    await page.goto("/login");
    await page.getByLabel(/email/i).fill("nobody@unknown.sn");
    await page.getByLabel(/password|mot de passe/i).fill("Whatever1234!");
    await page.getByRole("button", { name: /login|se connecter/i }).click();

    await expect(
      page.getByText(/invalid|not found|n'existe pas/i),
    ).toBeVisible({ timeout: 8_000 });
  });
});

test.describe("Protected routes", () => {
  test("unauthenticated user is redirected to /login from /dashboard", async ({ page }) => {
    await page.goto("/dashboard");
    await expect(page).toHaveURL(/\/login/);
  });

  test("unauthenticated user is redirected to /login from /simulate", async ({ page }) => {
    await page.goto("/simulate");
    await expect(page).toHaveURL(/\/login/);
  });
});

test.describe("Logout", () => {
  test("logout clears session and redirects to login", async ({ page }) => {
    await login(page, user.email, user.password);
    await expect(page).toHaveURL(/\/dashboard/);

    const logoutBtn = page.getByRole("button", { name: /logout|déconnexion/i });
    await expect(logoutBtn).toBeVisible();
    await logoutBtn.click();

    await expect(page).toHaveURL(/\/login/);

    // Visiting a protected route after logout re-redirects
    await page.goto("/dashboard");
    await expect(page).toHaveURL(/\/login/);
  });
});
