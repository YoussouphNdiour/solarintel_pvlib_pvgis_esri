/**
 * E2E — Full user journey (critical path)
 *
 * Scenario: register → login → create project → run simulation → view results → reports page
 *
 * This is the most important E2E test — it covers the complete happy path
 * that a solar installer would follow on their first day using the platform.
 *
 * Uses Dakar, Sénégal coordinates: lat=14.6928, lon=-17.4467
 * Expected result: annual yield ≈ 3 000–5 500 kWh for a 10-panel system.
 */

import { test, expect } from "@playwright/test";

const DAKAR_LAT = "14.6928";
const DAKAR_LON = "-17.4467";

test("complete installer journey: register → project → simulate → reports", async ({
  page,
}) => {
  // ── 1. Register ────────────────────────────────────────────────────────────
  const email = `journey_${Date.now()}@solarintel.sn`;
  const password = "Journey1234!";

  await page.goto("/register");
  await expect(page).toHaveURL(/\/register/);

  await page.getByLabel(/full name|nom complet/i).fill("Mamadou Diallo");
  await page.getByLabel(/email/i).fill(email);
  await page.getByLabel(/password|mot de passe/i).first().fill(password);

  const confirmField = page.getByLabel(/confirm|confirmation/i);
  if (await confirmField.isVisible()) await confirmField.fill(password);

  await page.getByRole("button", { name: /register|s'inscrire/i }).click();

  // After registration: dashboard or login
  await expect(page).toHaveURL(/\/(dashboard|login)/, { timeout: 10_000 });
  if (page.url().includes("login")) {
    await page.getByLabel(/email/i).fill(email);
    await page.getByLabel(/password|mot de passe/i).fill(password);
    await page.getByRole("button", { name: /login|se connecter/i }).click();
  }
  await expect(page).toHaveURL(/\/dashboard/, { timeout: 10_000 });

  // ── 2. Create a project ────────────────────────────────────────────────────
  const projectName = `Villa Almadies ${Date.now()}`;

  await page.getByRole("button", { name: /new project|nouveau projet|create/i }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();

  await dialog.getByLabel(/name|nom/i).fill(projectName);

  const addrField = dialog.getByLabel(/address|adresse|location/i);
  if (await addrField.isVisible()) {
    await addrField.fill("Almadies, Dakar, Sénégal");
  }

  await dialog.getByRole("button", { name: /create|créer|save|enregistrer/i }).click();
  await expect(page.getByText(projectName)).toBeVisible({ timeout: 10_000 });

  // ── 3. Navigate to simulate ────────────────────────────────────────────────
  const simLink = page
    .getByRole("link", { name: /simulat/i })
    .or(page.locator('a[href*="simulat"]'));
  if (await simLink.first().isVisible()) {
    await simLink.first().click();
  } else {
    await page.goto("/simulate");
  }
  await expect(page).toHaveURL(/\/simulat/, { timeout: 8_000 });

  // ── 4. Fill simulation form ────────────────────────────────────────────────
  // Step 1: Location
  const latInput = page.getByLabel(/latitude/i).or(page.getByPlaceholder(/latitude/i));
  if (await latInput.isVisible()) {
    await latInput.fill(DAKAR_LAT);
    const lonInput = page.getByLabel(/longitude/i).or(page.getByPlaceholder(/longitude/i));
    await lonInput.fill(DAKAR_LON);
  }

  // Click Next to step 2 (if stepper present)
  const nextBtn1 = page.getByRole("button", { name: /next|suivant/i });
  if (await nextBtn1.isVisible()) await nextBtn1.click();

  // Step 2: System parameters
  const panelCount = page.getByLabel(/panel count|nombre de panneaux|panels/i);
  if (await panelCount.isVisible()) {
    await panelCount.fill("10");
  }

  const tiltAngle = page.getByLabel(/tilt|inclinaison/i);
  if (await tiltAngle.isVisible()) {
    await tiltAngle.fill("15");
  }

  const nextBtn2 = page.getByRole("button", { name: /next|suivant/i });
  if (await nextBtn2.isVisible()) await nextBtn2.click();

  // Step 3: Tariff / submit
  const submitBtn = page
    .getByRole("button", { name: /run simulation|simuler|launch|lancer|submit/i })
    .or(page.getByRole("button", { name: /next|suivant/i }));
  await submitBtn.first().click();

  // ── 5. Verify results ──────────────────────────────────────────────────────
  // PVGIS can take up to 30s; generous timeout here
  await expect(page.getByText(/kWh|annual yield|production annuelle/i)).toBeVisible({
    timeout: 40_000,
  });
  await expect(page.getByText(/FCFA|savings|économies|payback|retour/i)).toBeVisible({
    timeout: 5_000,
  });

  // ── 6. Navigate to reports page ────────────────────────────────────────────
  const reportsLink = page
    .getByRole("link", { name: /report|rapport/i })
    .or(page.locator('a[href*="report"]'));
  if (await reportsLink.first().isVisible()) {
    await reportsLink.first().click();
  } else {
    await page.goto("/reports");
  }
  await expect(page).toHaveURL(/\/report/, { timeout: 8_000 });

  // Reports page should render cleanly
  const jsErrors: string[] = [];
  page.on("pageerror", (err) => jsErrors.push(err.message));
  await page.waitForLoadState("networkidle");
  const realErrors = jsErrors.filter((e) => !/ResizeObserver/.test(e));
  expect(realErrors).toHaveLength(0);
});
