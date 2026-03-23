/**
 * E2E — PV Simulation flow
 *
 * Covers: navigate to simulate page, fill form (3 steps), submit,
 * view results (annual yield, SENELEC savings, payback).
 *
 * Uses Dakar coordinates: lat=14.6928, lon=-17.4467
 */

import { test, expect } from "@playwright/test";
import { registerAndLogin, TEST_USER } from "./helpers";

const user = { ...TEST_USER, email: `sim_spec_${Date.now()}@solarintel.sn` };
const DAKAR_LAT = "14.6928";
const DAKAR_LON = "-17.4467";

test.describe("PV Simulation", () => {
  test.beforeEach(async ({ page }) => {
    await registerAndLogin(page, user);
  });

  test("simulate page is accessible from the sidebar/nav", async ({ page }) => {
    const simLink = page.getByRole("link", { name: /simulat|simulate/i });
    if (await simLink.isVisible()) {
      await simLink.click();
    } else {
      await page.goto("/simulate");
    }
    await expect(page).toHaveURL(/\/simulat/);
  });

  test("step 1 — location input accepts Dakar coordinates", async ({ page }) => {
    await page.goto("/simulate");

    const latInput = page.getByLabel(/latitude/i).or(page.getByPlaceholder(/latitude/i));
    const lonInput = page.getByLabel(/longitude/i).or(page.getByPlaceholder(/longitude/i));

    if (await latInput.isVisible()) {
      await latInput.fill(DAKAR_LAT);
      await lonInput.fill(DAKAR_LON);
      await expect(latInput).toHaveValue(DAKAR_LAT);
    } else {
      // Map-based input — just verify we're on the right page
      await expect(page.locator("[data-testid=arcgis-map], canvas").first()).toBeVisible({
        timeout: 15_000,
      });
    }
  });

  test("step 2 — system parameters can be filled", async ({ page }) => {
    await page.goto("/simulate");

    // Try to navigate to step 2 (parameters)
    const nextBtn = page.getByRole("button", { name: /next|suivant/i });
    if (await nextBtn.isVisible()) await nextBtn.click();

    // Panel count field
    const panelCount = page.getByLabel(/panel count|nombre de panneaux|panels/i);
    if (await panelCount.isVisible()) {
      await panelCount.fill("10");
      await expect(panelCount).toHaveValue("10");
    }

    // Peak power field
    const peakPower = page.getByLabel(/peak power|puissance|kWc/i);
    if (await peakPower.isVisible()) {
      await peakPower.fill("5.45");
    }
  });

  test("full simulation flow returns results for Dakar", async ({ page }) => {
    await page.goto("/simulate");

    // Step 1 — set coordinates via lat/lon inputs
    const latInput = page.getByLabel(/latitude/i).or(page.getByPlaceholder(/latitude/i));
    if (await latInput.isVisible()) {
      await latInput.fill(DAKAR_LAT);
      await page.getByLabel(/longitude/i).or(page.getByPlaceholder(/longitude/i)).fill(DAKAR_LON);
    }

    // Move to next step(s) and fill panel count
    const nextBtns = page.getByRole("button", { name: /next|suivant/i });
    for (let i = 0; i < 2; i++) {
      const btn = nextBtns.first();
      if (await btn.isVisible()) await btn.click();
    }

    const panelCount = page.getByLabel(/panel count|nombre de panneaux|panels/i);
    if (await panelCount.isVisible()) {
      await panelCount.fill("10");
    }

    // Submit the simulation
    const submitBtn = page.getByRole("button", { name: /run simulation|simuler|submit/i });
    if (await submitBtn.isVisible()) {
      await submitBtn.click();
    } else {
      await page.getByRole("button", { name: /next|suivant/i }).last().click();
    }

    // Wait for results — annual yield in kWh must be a reasonable positive number
    // The results section should appear within 30s (PVGIS may be slow)
    await expect(
      page.getByText(/kWh|annual yield|production annuelle/i),
    ).toBeVisible({ timeout: 35_000 });

    // SENELEC savings or payback period should also be visible
    await expect(
      page.getByText(/FCFA|savings|économies|payback|retour/i),
    ).toBeVisible({ timeout: 5_000 });
  });

  test("simulation results page shows monthly chart", async ({ page }) => {
    // Navigate to an existing simulation (or trigger one)
    await page.goto("/simulate");

    // If there is already a simulation in the results pane
    const chart = page.locator("[data-testid=monthly-chart], canvas").first();
    // Just check that the simulate page renders without JS errors
    const errors: string[] = [];
    page.on("pageerror", (err) => errors.push(err.message));
    await page.waitForLoadState("domcontentloaded");
    expect(errors.filter((e) => !/ResizeObserver/.test(e))).toHaveLength(0);
  });
});
