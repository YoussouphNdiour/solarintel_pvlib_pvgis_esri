import { defineConfig, devices } from "@playwright/test";

/**
 * Playwright E2E configuration for SolarIntel v2.
 *
 * Runs against the Vite dev server (started automatically by webServer).
 * The backend must be available at VITE_API_BASE_URL (default: http://localhost:8000).
 *
 * Run all tests: npx playwright test
 * Run a single suite: npx playwright test tests/e2e/auth.spec.ts
 * UI mode: npx playwright test --ui
 */

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL ?? "http://localhost:5173";
const API_URL = process.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 2 : undefined,

  reporter: [
    ["html", { outputFolder: "playwright-report", open: "never" }],
    ["list"],
  ],

  use: {
    baseURL: BASE_URL,
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
    // Default timeout per action (click, fill, etc.)
    actionTimeout: 10_000,
    navigationTimeout: 20_000,
    locale: "fr-FR",
    timezoneId: "Africa/Dakar",
  },

  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
    {
      name: "firefox",
      use: { ...devices["Desktop Firefox"] },
    },
    // Mobile viewport (Pixel 5)
    {
      name: "mobile-chrome",
      use: { ...devices["Pixel 5"] },
    },
  ],

  // Automatically start the Vite dev server before running tests
  webServer: {
    command: "npm run dev",
    url: BASE_URL,
    reuseExistingServer: !process.env.CI,
    env: {
      VITE_API_BASE_URL: API_URL,
    },
    timeout: 60_000,
  },

  // Global timeout per test
  timeout: 60_000,
  expect: { timeout: 8_000 },
});
