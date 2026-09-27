import { expect, test } from "@playwright/test";

// README screenshots of a running, seeded stack; runs only with SCREENSHOTS_DIR set (see CONTRIBUTING.md).
const OUT = process.env.SCREENSHOTS_DIR;
const ADMIN_EMAIL = process.env.E2E_ADMIN_EMAIL ?? "admin@example.com";
const ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD ?? "";
const VIEWPORT = { width: 1440, height: 900 };
const SEARCH_TIMEOUT_MS = 30_000;
const GRAPH_SETTLE_MS = 1_500;
const USE_CASE = [
  "Must have:",
  "- Eingangsrechnungen per OCR auslesen",
  "- Mehrstufige Freigabe von Rechnungen",
  "- Export der Buchungen an DATEV",
  "Nice to have:",
  "- E-Rechnungen im Format XRechnung empfangen",
].join("\n");

test.skip(!OUT, "set SCREENSHOTS_DIR to take the README screenshots");
test.use({ viewport: VIEWPORT, colorScheme: "light" });

test("README screenshots", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Email", { exact: true }).fill(ADMIN_EMAIL);
  await page.getByLabel("Password", { exact: true }).fill(ADMIN_PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: "Which app fits your use case?" })).toBeVisible();
  await expect(page.getByRole("link", { name: /Belegfix/ })).toBeVisible();
  await page.screenshot({ path: `${OUT}/catalog.png` });

  await page.getByLabel("Use case and requirements").fill(USE_CASE);
  await page.getByRole("button", { name: "Find matching apps" }).click();
  await expect(page.getByTestId("result-tile").first()).toBeVisible({ timeout: SEARCH_TIMEOUT_MS });
  await page.screenshot({ path: `${OUT}/search-results.png` });

  await page.getByText("Matrix", { exact: true }).click();
  await expect(page.getByRole("table", { name: "Coverage matrix" })).toBeVisible();
  await page.screenshot({ path: `${OUT}/coverage-matrix.png` });
  await page.getByText("Tiles", { exact: true }).click();

  await page.goto("/landscape");
  await expect(page.getByTestId("landscape-graph")).toBeVisible();
  await page.waitForTimeout(GRAPH_SETTLE_MS);
  await page.screenshot({ path: `${OUT}/landscape.png` });
});
