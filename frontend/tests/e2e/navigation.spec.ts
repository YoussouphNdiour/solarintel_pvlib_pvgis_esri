/**
 * E2E — General navigation, page health, and PWA manifest
 *
 * Covers: page titles, 404 handling, sidebar navigation,
 * language switcher, PWA manifest meta tag, no console errors
 * on key pages.
 */

import { test, expect } from "@playwright/test";
import { registerAndLogin, TEST_USER, login } from "./helpers";

const user = { ...TEST_USER, email: `nav_spec_${Date.now()}@solarintel.sn` };

test.describe("Public pages", () => {
  test("/ redirects to /login or /dashboard", async ({ page }) => {
    await page.goto("/");
    await expect(page).toHaveURL(/\/(login|dashboard)/);
  });

  test("/login renders without JS errors", async ({ page }) => {
    const errors: string[] = [];
    page.on("pageerror", (err) => errors.push(err.message));

    await page.goto("/login");
    await page.waitForLoadState("domcontentloaded");

    const realErrors = errors.filter((e) => !/ResizeObserver|non-passive/.test(e));
    expect(realErrors).toHaveLength(0);
  });

  test("unknown route shows 404 page", async ({ page }) => {
    await page.goto("/this-does-not-exist-at-all");
    await expect(
      page.getByText(/404|not found|page introuvable/i),
    ).toBeVisible({ timeout: 5_000 });
  });

  test("PWA manifest is linked in the HTML head", async ({ page }) => {
    await page.goto("/");
    const manifestLink = page.locator('link[rel="manifest"]');
    await expect(manifestLink).toHaveCount(1);
    const href = await manifestLink.getAttribute("href");
    expect(href).toBeTruthy();
  });
});

test.describe("Authenticated navigation", () => {
  test.beforeEach(async ({ page }) => {
    await registerAndLogin(page, user);
  });

  test("page title is 'SolarIntel' or similar", async ({ page }) => {
    await expect(page).toHaveTitle(/solar|solarintel/i);
  });

  test("sidebar contains links to all major sections", async ({ page }) => {
    const links = ["dashboard", "simulat", "report", "monitor"];
    for (const href of links) {
      const link = page
        .getByRole("link")
        .filter({ hasText: new RegExp(href, "i") })
        .or(page.locator(`a[href*="${href}"]`));
      // At least one matching link exists in the sidebar/nav
      await expect(link.first()).toBeVisible({ timeout: 5_000 });
    }
  });

  test("navigating to /dashboard shows the dashboard", async ({ page }) => {
    await page.goto("/dashboard");
    await expect(page).toHaveURL(/\/dashboard/);
    await expect(page.getByRole("main")).toBeVisible();
  });

  test("navigating to /simulate shows the simulation page", async ({ page }) => {
    await page.goto("/simulate");
    await expect(page).toHaveURL(/\/simulat/);
    await expect(page.getByRole("main")).toBeVisible();
  });

  test("language switcher toggles between FR and Wolof if present", async ({ page }) => {
    const langBtn = page.getByRole("button", { name: /fr|wo|langue|language/i });
    if (await langBtn.isVisible()) {
      await langBtn.click();
      // After click, some text should change or a dropdown should appear
      await expect(
        page.getByText(/wolof|français|fr|wo/i).first(),
      ).toBeVisible({ timeout: 3_000 });
    }
    // If no language switcher is present, test passes trivially
  });
});

test.describe("Responsive layout", () => {
  test("dashboard renders correctly on mobile viewport", async ({ browser }) => {
    const context = await browser.newContext({
      viewport: { width: 375, height: 812 },
    });
    const page = await context.newPage();

    await registerAndLogin(page, {
      ...user,
      email: `mobile_${Date.now()}@solarintel.sn`,
    });

    await expect(page).toHaveURL(/\/dashboard/);
    // No horizontal overflow — body scroll width should not exceed viewport
    const scrollWidth = await page.evaluate(() => document.body.scrollWidth);
    const viewportWidth = 375;
    expect(scrollWidth).toBeLessThanOrEqual(viewportWidth + 5); // 5px tolerance

    await page.close();
    await context.close();
  });
});
