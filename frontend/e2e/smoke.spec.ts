import { expect, test, type Page } from "@playwright/test";

// Smoke tests against a running stack seeded with backend/eval/seed_apps.json.
const ADMIN_EMAIL = process.env.E2E_ADMIN_EMAIL ?? "admin@example.com";
const ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD ?? "";
const INDEX_TIMEOUT_MS = 60_000;
const SEARCH_TIMEOUT_MS = 30_000;
const READY_TIMEOUT_MS = 180_000;
const READY_POLL_MS = 2_000;

test.beforeAll(async ({ request }) => {
  test.setTimeout(READY_TIMEOUT_MS);
  // The API answers before the embedding model has loaded; wait for full readiness.
  await expect
    .poll(async () => (await request.get("/api/health/ready")).status(), {
      timeout: READY_TIMEOUT_MS,
      intervals: [READY_POLL_MS],
    })
    .toBe(200);
});

async function login(page: Page) {
  await page.goto("/");
  await expect(page).toHaveURL(/\/login/);
  await page.getByLabel("Email", { exact: true }).fill(ADMIN_EMAIL);
  await page.getByLabel("Password", { exact: true }).fill(ADMIN_PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: "Which app fits your use case?" })).toBeVisible();
}

test("search a seeded use case and see explained results", async ({ page }) => {
  await login(page);
  await page
    .getByLabel("Use case and requirements")
    .fill(
      "Muss:\n- Eingangsrechnungen per OCR auslesen\n- Export der Buchungen nach DATEV\nKann:\n- Freigabe per App",
    );
  await page.getByRole("button", { name: "Find matching apps" }).click();

  const first = page.getByTestId("result-tile").first();
  await expect(first).toBeVisible({ timeout: SEARCH_TIMEOUT_MS });
  await expect(first).toContainText("Belegfix");
  await expect(page.getByText("Requirements (3)")).toBeVisible();

  await first.click();
  const drawer = page.getByTestId("evidence-drawer");
  await expect(drawer.getByTestId("evidence-row").first()).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(drawer).toBeHidden();

  await page.getByText("Matrix", { exact: true }).click();
  await expect(page.getByRole("table", { name: "Coverage matrix" })).toBeVisible();
});

test("the catalog filters by keyword and facet", async ({ page }) => {
  await login(page);
  await expect(page.getByTestId("catalog-tile").first()).toBeVisible();
  await page.getByLabel("Use case and requirements").fill("Belegfix");
  await expect(page.getByRole("heading", { name: /matching "Belegfix"/ })).toBeVisible();
  await expect(page.getByTestId("catalog-tile").first()).toContainText("Belegfix");

  await page.getByLabel("Use case and requirements").fill("");
  const retired = page.getByRole("group", { name: "Lifecycle" }).getByRole("checkbox", { name: /retired/ });
  // The checkbox follows the URL, so wait for the state instead of using check().
  await retired.click();
  await expect(retired).toBeChecked();
  // The seed catalog has two retired apps, hidden until the facet selects them.
  await expect(page.getByTestId("catalog-tile")).toHaveCount(2);
  await expect(page.getByTestId("catalog-tile").first()).toContainText("retired");
});

test("an unknown use case yields the no-match banner", async ({ page }) => {
  await login(page);
  await page
    .getByLabel("Use case and requirements")
    .fill("- Simulation der Aerodynamik im Windkanal\n- CFD-Netzgenerierung für Tragflächen");
  await page.getByRole("button", { name: "Find matching apps" }).click();
  await expect(page.getByTestId("no-match")).toBeVisible({ timeout: SEARCH_TIMEOUT_MS });
});

test("a newly created app becomes searchable after indexing", async ({ page }) => {
  const name = `E2E Kantinenplaner ${Date.now()}`;
  await login(page);
  await page.goto("/apps/new");
  await page.getByLabel("Name").fill(name);
  await page.getByLabel("Short description").fill("Speiseplan und Allergene für die Betriebskantine");
  await page
    .getByLabel("Add capabilities")
    .fill("Wöchentlicher Speiseplan für die Kantine\nKennzeichnung von Allergenen und Zusatzstoffen");
  await page.getByRole("button", { name: "Add", exact: true }).click();
  await page.getByRole("button", { name: "Save" }).click();

  await expect(page.getByRole("heading", { name })).toBeVisible();
  const slug = page.url().split("/apps/")[1]!;
  await expect(page.getByText("indexed", { exact: true })).toBeVisible({ timeout: INDEX_TIMEOUT_MS });

  await page.goto("/");
  await page.getByLabel("Use case and requirements").fill("- Kantinen-Speiseplan mit Allergenkennzeichnung");
  await page.getByRole("button", { name: "Find matching apps" }).click();
  await expect(page.getByTestId("result-tile").first()).toContainText(name, { timeout: SEARCH_TIMEOUT_MS });

  // Clean up so the seeded catalog stays unchanged for the next run.
  const response = await page.request.delete(`/api/apps/${slug}`, {
    headers: { "X-Requested-With": "XMLHttpRequest" },
  });
  expect(response.status()).toBe(204);
});

test("the landscape shows the seeded interfaces", async ({ page }) => {
  await login(page);
  await page.getByRole("link", { name: "Landscape" }).first().click();
  await expect(page.getByRole("heading", { name: "Integration landscape" })).toBeVisible();
  await expect(page.getByTestId("graph-node-app").first()).toBeVisible();
  expect(await page.getByTestId("graph-node-system").count()).toBeGreaterThan(0);

  await page.getByTestId("graph-node-app").filter({ hasText: "Belegfix" }).click();
  await expect(page.getByRole("link", { name: /Open app details/ })).toBeVisible();
  await expect(page.getByTestId("interface-row").filter({ hasText: "FinanzBuch Pro" })).toBeVisible();
});

test("a search uses interfaces as evidence and shows how apps connect", async ({ page }) => {
  await login(page);
  await page
    .getByLabel("Use case and requirements")
    .fill("Muss:\n- Arbeitszeiten am Terminal erfassen\n- Lohnabrechnung nach deutschem Recht");
  await page.getByRole("button", { name: "Find matching apps" }).click();
  await expect(page.getByTestId("combination-card").first()).toContainText("ZeitWerk + LohnPilot", {
    timeout: SEARCH_TIMEOUT_MS,
  });

  await page
    .getByLabel("Use case and requirements")
    .fill("- Integration mit SAP S/4HANA\n- Lagerplatzverwaltung");
  await page.getByRole("button", { name: "Find matching apps" }).click();
  const first = page.getByTestId("result-tile").first();
  await expect(first).toContainText("LagerLogix", { timeout: SEARCH_TIMEOUT_MS });
  await first.click();
  await expect(page.getByTestId("evidence-drawer")).toContainText(/Interface (to|with) SAP S\/4HANA/);
});

test("an editor documents an interface to a new external system", async ({ page }) => {
  const system = `E2E Bank ${Date.now()}`;
  await login(page);
  await page.goto("/apps/finanzbuch");
  await page.getByTestId("app-interfaces").getByRole("button", { name: "Add interface" }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByRole("combobox", { name: "To (receives the data)" }).fill(system);
  await page.getByRole("option", { name: `New external system: ${system}` }).click();
  await dialog.getByRole("textbox", { name: "Name" }).fill("Zahlungsdateien");
  await dialog.getByRole("button", { name: "Add interface" }).click();
  await expect(page.getByTestId("interface-row").filter({ hasText: system })).toBeVisible();

  await page.goto("/landscape");
  await expect(page.getByTestId("graph-node-system").filter({ hasText: system })).toBeVisible();

  // Clean up so the seeded catalog stays unchanged for the next run.
  const headers = { "X-Requested-With": "XMLHttpRequest" };
  const found = await (await page.request.get(`/api/interfaces?system=${encodeURIComponent(system)}`)).json();
  expect((await page.request.delete(`/api/interfaces/${found[0].id}`, { headers })).status()).toBe(204);
  const systems = await (await page.request.get("/api/external-systems")).json();
  const created = systems.find((s: { name: string }) => s.name === system);
  expect((await page.request.delete(`/api/external-systems/${created.id}`, { headers })).status()).toBe(204);
});
