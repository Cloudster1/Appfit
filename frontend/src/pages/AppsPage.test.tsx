import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it } from "vitest";

import type { AppListItem } from "../api/hooks";
import { App } from "../App";
import { RequireRole } from "../auth/guards";
import { RESULTS_VIEW_STORAGE_KEY } from "../config";
import { renderWithProviders, sampleResponse } from "../test/utils";
import { AppsPage } from "./AppsPage";

const viewer = {
  id: "u1",
  email: "viewer@example.com",
  display_name: "Viewer",
  role: "viewer",
  auth_provider: "local",
  is_active: true,
  created_at: "2026-01-01T00:00:00Z",
  last_login_at: null,
};

function listItem(slug: string, name: string, extra: Partial<AppListItem> = {}): AppListItem {
  return {
    id: slug,
    slug,
    name,
    short_description: `${name} description`,
    lifecycle_status: "active",
    license_type: "commercial",
    vendor: null,
    tags: [],
    tech_stack: [],
    domains: ["finance"],
    maintainers: ["Team Finance IT"],
    capability_count: 4,
    embedding_status: "indexed",
    updated_at: "2026-01-01T00:00:00Z",
    ...extra,
  };
}

const catalog = [
  listItem("belegfix", "Belegfix"),
  listItem("talentscout", "TalentScout", { domains: ["hr"], embedding_status: "pending" }),
];
const facets = {
  lifecycle: [
    { value: "active", count: 2 },
    { value: "retired", count: 1 },
  ],
  license_type: [{ value: "commercial", count: 2 }],
  domain: [
    { value: "finance", count: 1 },
    { value: "hr", count: 1 },
  ],
};

let appsUrls: URL[] = [];
let facetUrls: URL[] = [];
let searchBodies: Record<string, unknown>[] = [];

const server = setupServer(
  http.get("*/api/auth/me", () => HttpResponse.json(viewer)),
  http.get("*/api/meta/search-config", () =>
    HttpResponse.json({
      model_id: "fake",
      thresholds: sampleResponse.thresholds,
      priority_weights: {},
      max_requirements: 30,
      capability_atomic_warn_len: 200,
    }),
  ),
  http.get("*/api/apps/facets", ({ request }) => {
    facetUrls.push(new URL(request.url));
    return HttpResponse.json(facets);
  }),
  http.get("*/api/apps", ({ request }) => {
    appsUrls.push(new URL(request.url));
    return HttpResponse.json({ items: catalog, total: catalog.length, page: 1, size: 24 });
  }),
  http.post("*/api/search", async ({ request }) => {
    searchBodies.push((await request.json()) as Record<string, unknown>);
    return HttpResponse.json(sampleResponse);
  }),
  http.post("*/api/search/:id/feedback", () => new HttpResponse(null, { status: 204 })),
);

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
beforeEach(() => {
  appsUrls = [];
  facetUrls = [];
  searchBodies = [];
  localStorage.clear();
});
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

const lastSearch = () => searchBodies.at(-1);
const catalogUrls = () => appsUrls.filter((u) => u.searchParams.get("size") === "24");

async function matchRequirements(text = "- OCR for invoices\n- Export to SAP") {
  fireEvent.change(screen.getByLabelText("Use case and requirements"), { target: { value: text } });
  fireEvent.click(screen.getByRole("button", { name: "Find matching apps" }));
  return screen.findByTestId("search-results");
}

describe("AppsPage catalog", () => {
  it("shows the catalog as tiles with facet counts, hiding retired apps by default", async () => {
    renderWithProviders(<AppsPage />, { withAuth: true });
    const tiles = await screen.findAllByTestId("catalog-tile");
    expect(tiles).toHaveLength(2);
    expect(tiles[0]).toHaveAttribute("href", "/apps/belegfix");
    expect(within(tiles[1]!).getByText("indexing")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "2 apps" })).toBeInTheDocument();

    const lifecycle = await screen.findByRole("group", { name: "Lifecycle" });
    expect(within(lifecycle).getByText("retired")).toBeInTheDocument();
    expect(catalogUrls().at(-1)!.searchParams.getAll("status")).toEqual([
      "idea",
      "pilot",
      "active",
      "deprecated",
    ]);
  });

  it("filters by facet and sends the selection to list and facet requests", async () => {
    renderWithProviders(<AppsPage />, { withAuth: true });
    const domain = await screen.findByRole("group", { name: "Domain" });
    fireEvent.click(within(domain).getByRole("checkbox", { name: /hr/ }));
    await waitFor(() => expect(catalogUrls().at(-1)!.searchParams.getAll("domain")).toEqual(["hr"]));
    expect(facetUrls.at(-1)!.searchParams.getAll("domain")).toEqual(["hr"]);
    expect(screen.getByRole("button", { name: "Clear filters" })).toBeInTheDocument();
  });

  it("uses a single line as catalog keyword but not a requirement list", async () => {
    renderWithProviders(<AppsPage />, { withAuth: true });
    await screen.findAllByTestId("catalog-tile");
    const input = screen.getByLabelText("Use case and requirements");

    fireEvent.change(input, { target: { value: "invoice" } });
    await waitFor(() => expect(catalogUrls().at(-1)!.searchParams.get("q")).toBe("invoice"));
    expect(catalogUrls().at(-1)!.searchParams.get("sort")).toBe("relevance");
    expect(await screen.findByRole("heading", { name: '2 apps matching "invoice"' })).toBeInTheDocument();

    fireEvent.change(input, { target: { value: "invoice\nexport to SAP" } });
    expect(screen.getByTestId("match-hint")).toBeInTheDocument();
    await waitFor(() => expect(catalogUrls().at(-1)!.searchParams.get("q")).toBeNull());
    expect(searchBodies).toHaveLength(0);
  });

  it("redirects the old catalog route to the apps page", async () => {
    renderWithProviders(<App />, { withAuth: true, route: "/apps" });
    expect(await screen.findByRole("heading", { name: "Which app fits your use case?" })).toBeInTheDocument();
  });
});

describe("AppsPage matching", () => {
  it("ranks apps as tiles with score, requirement dots and the catalog gap", async () => {
    renderWithProviders(<AppsPage />, { withAuth: true });
    await matchRequirements();

    expect(lastSearch()).toMatchObject({
      text: "- OCR for invoices\n- Export to SAP",
      limit: 10,
      filters: { lifecycle: ["idea", "pilot", "active", "deprecated"], domains: [], license_types: [] },
    });
    const [tile] = screen.getAllByTestId("result-tile");
    expect(tile).toHaveAttribute("data-best", "true");
    expect(within(tile!).getByText("82%")).toBeInTheDocument();
    expect(within(tile!).getByText("Strong match")).toBeInTheDocument();
    expect(within(tile!).getByText("Team Finance IT")).toBeInTheDocument();
    const dots = within(tile!).getByTestId("requirement-dots").children;
    expect([...dots].map((d) => d.getAttribute("data-status"))).toEqual(["covered", "partial", "gap"]);
    expect(screen.getByTestId("catalog-gaps")).toHaveTextContent("Canteen menu");
    expect(screen.queryByTestId("catalog")).not.toBeInTheDocument();
    // The parsed requirements become editable for the next search.
    expect(screen.getByText("Requirements (3)")).toBeInTheDocument();
  });

  it("opens the evidence for a tile in a drawer", async () => {
    renderWithProviders(<AppsPage />, { withAuth: true });
    await matchRequirements();
    fireEvent.click(screen.getByRole("button", { name: /Invoice Hub, Strong match/ }));
    const drawer = await screen.findByTestId("evidence-drawer");
    expect(within(drawer).getAllByTestId("evidence-row")).toHaveLength(3);
    expect(within(drawer).getByText("OCR extraction of invoice data")).toBeInTheDocument();
    expect(within(drawer).getByText("Covers 1 of 1 must-haves")).toBeInTheDocument();
    expect(within(drawer).getByRole("link", { name: /Open app details/ })).toHaveAttribute(
      "href",
      "/apps/invoice-hub",
    );
  });

  it("switches to the matrix view and remembers the choice", async () => {
    const first = renderWithProviders(<AppsPage />, { withAuth: true });
    await matchRequirements();
    fireEvent.click(screen.getByText("Matrix"));
    expect(screen.getByRole("table", { name: "Coverage matrix" })).toBeInTheDocument();
    expect(screen.queryByTestId("result-tile")).not.toBeInTheDocument();
    expect(localStorage.getItem(RESULTS_VIEW_STORAGE_KEY)).toContain("matrix");
    first.unmount();

    renderWithProviders(<AppsPage />, { withAuth: true });
    await matchRequirements();
    expect(screen.getByRole("table", { name: "Coverage matrix" })).toBeInTheDocument();
  });

  it("re-runs the match with the same requirements when a facet changes", async () => {
    renderWithProviders(<AppsPage />, { withAuth: true });
    await matchRequirements();
    const domain = await screen.findByRole("group", { name: "Domain" });
    fireEvent.click(within(domain).getByRole("checkbox", { name: /finance/ }));
    await waitFor(() => expect(searchBodies).toHaveLength(2));
    expect(lastSearch()).toMatchObject({
      text: "- OCR for invoices\n- Export to SAP",
      filters: { domains: ["finance"] },
    });
  });

  it("sends the structured requirement list after switching modes", async () => {
    renderWithProviders(<AppsPage />, { withAuth: true });
    await matchRequirements("anything\nelse");
    fireEvent.click(screen.getByText("Requirements (3)"));
    fireEvent.click(screen.getByRole("button", { name: "Remove requirement 3" }));
    fireEvent.click(screen.getByRole("button", { name: "Find matching apps" }));
    await waitFor(() =>
      expect(lastSearch()).toMatchObject({
        requirements: [
          { text: "OCR for invoices", priority: "must" },
          { text: "Export to SAP", priority: null },
        ],
      }),
    );
  });

  it("returns to the catalog", async () => {
    renderWithProviders(<AppsPage />, { withAuth: true });
    await matchRequirements();
    fireEvent.click(screen.getByRole("button", { name: "Back to catalog" }));
    expect(await screen.findByTestId("catalog")).toBeInTheDocument();
    expect(screen.queryByTestId("search-results")).not.toBeInTheDocument();
  });

  it("shows the no-match banner and marks candidates as not recommended", async () => {
    server.use(
      http.post("*/api/search", () =>
        HttpResponse.json({
          ...sampleResponse,
          status: "no_match",
          catalog_gaps: [0, 1, 2],
          results: sampleResponse.results.map((r) => ({ ...r, recommended: false })),
        }),
      ),
    );
    renderWithProviders(<AppsPage />, { withAuth: true });
    await matchRequirements("wind tunnel\naerodynamics");
    expect(screen.getByTestId("no-match")).toBeInTheDocument();
    expect(screen.getByText("Closest candidates (not recommended)")).toBeInTheDocument();
    const [tile] = screen.getAllByTestId("result-tile");
    expect(tile).toHaveAttribute("data-muted", "true");
    expect(tile).toHaveAttribute("data-best", "false");
  });
});

describe("RequireRole", () => {
  it("blocks viewers from editor pages", async () => {
    renderWithProviders(
      <RequireRole min="editor">
        <div>secret editor page</div>
      </RequireRole>,
      { withAuth: true },
    );
    expect(await screen.findByText(/requires the editor role/)).toBeInTheDocument();
    expect(screen.queryByText("secret editor page")).not.toBeInTheDocument();
  });
});
