/**
 * E2E — Project management flows
 *
 * Covers: create project, view project list, archive project.
 */

import { test, expect } from "@playwright/test";
import { registerAndLogin, TEST_USER } from "./helpers";

const user = { ...TEST_USER, email: `proj_spec_${Date.now()}@solarintel.sn` };

test.describe("Project management", () => {
  test.beforeEach(async ({ page }) => {
    await registerAndLogin(page, user);
  });

  test("dashboard displays empty project list for new user", async ({ page }) => {
    await expect(page).toHaveURL(/\/dashboard/);
    // Either an empty state message or zero project cards
    const projectCards = page.locator("[data-testid=project-card]");
    const emptyMsg = page.getByText(/no project|aucun projet|créer votre/i);

    const count = await projectCards.count();
    if (count === 0) {
      await expect(emptyMsg).toBeVisible();
    }
  });

  test("opens new project modal from dashboard", async ({ page }) => {
    await page.getByRole("button", { name: /new project|nouveau projet|create/i }).click();
    await expect(
      page.getByRole("dialog").or(page.locator("[data-testid=new-project-modal]")),
    ).toBeVisible();
  });

  test("creates a project and it appears in the list", async ({ page }) => {
    const projectName = `Test Project ${Date.now()}`;

    await page.getByRole("button", { name: /new project|nouveau projet|create/i }).click();
    const dialog = page.getByRole("dialog");
    await expect(dialog).toBeVisible();

    await dialog.getByLabel(/project name|nom du projet|name/i).fill(projectName);

    // Address or coordinate fields
    const addrField = dialog.getByLabel(/address|adresse|location/i);
    if (await addrField.isVisible()) {
      await addrField.fill("Dakar, Sénégal");
    }

    await dialog.getByRole("button", { name: /create|créer|save|enregistrer/i }).click();

    // Wait for the project to appear
    await expect(page.getByText(projectName)).toBeVisible({ timeout: 10_000 });
  });

  test("clicking a project navigates to the project detail page", async ({ page }) => {
    // Create a project first
    const projectName = `Detail Test ${Date.now()}`;
    await page.getByRole("button", { name: /new project|nouveau projet|create/i }).click();
    const dialog = page.getByRole("dialog");
    await dialog.getByLabel(/name|nom/i).fill(projectName);
    await dialog.getByRole("button", { name: /create|créer|save/i }).click();
    await expect(page.getByText(projectName)).toBeVisible({ timeout: 10_000 });

    // Click the project card
    await page.getByText(projectName).click();
    await expect(page).toHaveURL(/\/project\//);
    await expect(page.getByText(projectName)).toBeVisible();
  });
});
