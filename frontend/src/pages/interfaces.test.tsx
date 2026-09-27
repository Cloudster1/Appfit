import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { Route, Routes } from "react-router";
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it } from "vitest";

import type { AppOut, InterfaceOut, Landscape, SearchResponse } from "../api/hooks";
import { renderWithProviders, sampleResponse } from "../test/utils";
import { AppDetailPage } from "./AppDetailPage";
import { AppsPage } from "./AppsPage";
import { LandscapePage } from "./LandscapePage";

const editor = {
  id: "u1",
  email: "editor@example.com",
  display_name: "Editor",
  role: "editor",
  auth_provider: "local",
  is_active: true,
  created_at: "2026-01-01T00:00:00Z",
  last_login_at: null,
};

const appNode = (id: string, name: string, slug: string) => ({
  id: `app:${id}`,
  kind: "app" as const,
  name,
  slug,
  lifecycle_status: "active" as const,
  domains: ["finance"],
  degree: 1,
});

const landscape: Landscape = {
  nodes: [
    appNode("a1", "Belegfix", "belegfix"),
    appNode("a2", "FinanzBuch", "finanzbuch"),
    {
      id: "system:s1",
      kind: "system",
      name: "SAP S/4HANA",
      slug: null,
      lifecycle_status: null,
      domains: [],
      degree: 1,
    },
  ],
  edges: [
    {
      id: "i1",
      source: "app:a1",
      target: "app:a2",
      name: "Buchungsstapel",
      type: "file_transfer",
      status: "active",
      bidirectional: false,
      data_objects: ["Buchungen"],
      frequency: "batch",
    },
    {
      id: "i2",
      source: "app:a1",
      target: "system:s1",
      name: "Rechnungen an SAP",
      type: "rest_api",
      status: "planned",
      bidirectional: false,
      data_objects: [],
      frequency: null,
    },
  ],
};

const iface: InterfaceOut = {
  id: "i1",
  from: { kind: "app", id: "a1", name: "Belegfix", slug: "belegfix", lifecycle_status: "active" },
  to: { kind: "app", id: "a2", name: "FinanzBuch", slug: "finanzbuch", lifecycle_status: "active" },
  name: "Buchungsstapel",
  type: "file_transfer",
  data_objects: ["Buchungen"],
  frequency: "batch",
  status: "active",
  bidirectional: false,
  description: "Monthly",
  indexed: true,
  updated_at: "2026-01-01T00:00:00Z",
};

const belegfix: AppOut = {
  id: "a1",
  slug: "belegfix",
  name: "Belegfix",
  short_description: "Eingangsrechnungen",
  description: "",
  lifecycle_status: "active",
  license: null,
  license_type: null,
  vendor: null,
  version: null,
  homepage_url: null,
  repo_url: null,
  docs_url: null,
  links: [],
  extra: {},
  tags: [],
  tech_stack: [],
  domains: ["finance"],
  maintainers: [],
  capabilities: [],
  interfaces: [
    {
      id: "i1",
      name: "Buchungsstapel",
      direction: "outgoing",
      counterpart: iface.to,
      type: "file_transfer",
      data_objects: ["Buchungen"],
      frequency: "batch",
      status: "active",
    },
  ],
  embedding_status: "indexed",
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

let landscapeUrls: URL[] = [];
let savedBodies: { method: string; body: unknown }[] = [];

const server = setupServer(
  http.get("*/api/auth/me", () => HttpResponse.json(editor)),
  http.get("*/api/landscape", ({ request }) => {
    landscapeUrls.push(new URL(request.url));
    return HttpResponse.json(landscape);
  }),
  http.get("*/api/apps/facets", () =>
    HttpResponse.json({ lifecycle: [], license_type: [], domain: [{ value: "finance", count: 2 }] }),
  ),
  http.get("*/api/apps/belegfix", () => HttpResponse.json(belegfix)),
  http.get("*/api/apps/belegfix/similar", () => HttpResponse.json([])),
  http.get("*/api/apps", () => HttpResponse.json({ items: [], total: 0, page: 1, size: 24 })),
  http.get("*/api/external-systems", () => HttpResponse.json([])),
  http.get("*/api/interfaces/i1", () => HttpResponse.json(iface)),
  http.put("*/api/interfaces/i1", async ({ request }) => {
    savedBodies.push({ method: "PUT", body: await request.json() });
    return HttpResponse.json(iface);
  }),
  http.get("*/api/meta/search-config", () =>
    HttpResponse.json({
      model_id: "fake",
      thresholds: sampleResponse.thresholds,
      priority_weights: {},
      max_requirements: 30,
      capability_atomic_warn_len: 200,
    }),
  ),
);

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
beforeEach(() => {
  landscapeUrls = [];
  savedBodies = [];
});
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe("LandscapePage", () => {
  it("draws apps and external systems and filters by interface type", async () => {
    renderWithProviders(<LandscapePage />, { withAuth: true });
    await waitFor(() => expect(screen.getAllByTestId("graph-node-app")).toHaveLength(2));
    expect(screen.getByTestId("graph-node-system")).toHaveTextContent("SAP S/4HANA");
    expect(screen.getByText("3 systems and 2 interfaces.", { exact: false })).toBeInTheDocument();
    expect(screen.getByTestId("graph-legend")).toHaveTextContent("File transfer");

    const user = userEvent.setup();
    await user.click(within(screen.getByTestId("landscape-filters")).getByLabelText("Interface type"));
    await user.click(await screen.findByRole("option", { name: "REST API", hidden: true }));
    await waitFor(() => expect(landscapeUrls.at(-1)!.searchParams.getAll("type")).toEqual(["rest_api"]));
  });

  it("highlights a searched app and dims unrelated nodes", async () => {
    renderWithProviders(<LandscapePage />, { withAuth: true });
    await waitFor(() => expect(screen.getAllByTestId("graph-node-app")).toHaveLength(2));
    fireEvent.change(screen.getByRole("combobox", { name: "Find an app or system" }), {
      target: { value: "finanz" },
    });
    await waitFor(() => {
      const dimmed = screen.getAllByTestId(/graph-node-/).filter((n) => n.dataset.dimmed === "true");
      expect(dimmed.map((n) => n.textContent)).toEqual([expect.stringContaining("SAP S/4HANA")]);
    });
  });

  it("opens an app's interfaces when its node is clicked", async () => {
    renderWithProviders(<LandscapePage />, { withAuth: true });
    const nodes = await screen.findAllByTestId("graph-node-app");
    fireEvent.click(within(nodes[0]!).getByText("Belegfix"));
    expect(await screen.findByRole("link", { name: /Open app details/ })).toHaveAttribute(
      "href",
      "/apps/belegfix",
    );
    expect(screen.getAllByTestId("interface-row")[0]).toHaveTextContent("FinanzBuch");
  });
});

describe("App page interfaces", () => {
  it("lists interfaces and lets editors change one", async () => {
    renderWithProviders(
      <Routes>
        <Route path="/apps/:slug" element={<AppDetailPage />} />
      </Routes>,
      { route: "/apps/belegfix", withAuth: true },
    );
    const card = await screen.findByTestId("app-interfaces");
    const row = within(card).getByTestId("interface-row");
    expect(row).toHaveTextContent("FinanzBuch");
    expect(row).toHaveTextContent("Buchungen / Batch");
    expect(within(row).getByLabelText("Sends data to")).toBeInTheDocument();

    fireEvent.click(within(row).getByRole("button", { name: "Edit Buchungsstapel" }));
    const name = await screen.findByLabelText(/^Name/);
    expect(name).toHaveValue("Buchungsstapel");
    fireEvent.change(name, { target: { value: "Buchungsstapel DATEV" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(savedBodies).toHaveLength(1));
    expect(savedBodies[0]!.body).toMatchObject({
      from: { app: "belegfix" },
      to: { app: "finanzbuch" },
      name: "Buchungsstapel DATEV",
      type: "file_transfer",
      frequency: "batch",
    });
  });
});

describe("search results with interfaces", () => {
  const withInterfaces: SearchResponse = {
    ...sampleResponse,
    results: [
      {
        ...sampleResponse.results[0]!,
        evidence: [
          {
            ...sampleResponse.results[0]!.evidence[0]!,
            via: "interface",
            capability: null,
            interface: {
              id: "i2",
              name: "Rechnungen an SAP",
              direction: "outgoing",
              counterpart: { kind: "system", id: "s1", name: "SAP S/4HANA" },
              type: "rest_api",
              data_objects: [],
              frequency: null,
              status: "planned",
            },
          },
          ...sampleResponse.results[0]!.evidence.slice(1),
        ],
      },
      {
        ...sampleResponse.results[0]!,
        app: { ...sampleResponse.results[0]!.app, id: "x2", slug: "ledger", name: "Ledger" },
      },
    ],
    connections: landscape,
    combinations: [
      {
        apps: ["invoice-hub", "ledger"],
        covered: [0, 1],
        interface_id: "i1",
        interface_name: "Buchungsstapel",
        interface_status: "active",
      },
    ],
  };

  it("shows interface evidence and connected pairs that cover more together", async () => {
    server.use(http.post("*/api/search", () => HttpResponse.json(withInterfaces)));
    renderWithProviders(<AppsPage />, { withAuth: true });
    fireEvent.change(screen.getByLabelText("Use case and requirements"), { target: { value: "a\nb" } });
    fireEvent.click(screen.getByRole("button", { name: "Find matching apps" }));

    const card = await screen.findByTestId("combination-card");
    expect(card).toHaveTextContent("Invoice Hub + Ledger cover 2 of 3 together");
    expect(card).toHaveTextContent("Connected by Buchungsstapel");
    expect(
      within(screen.getByTestId("connections-panel")).getByTestId("landscape-graph"),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Invoice Hub, Strong match/ }));
    const drawer = await screen.findByTestId("evidence-drawer");
    expect(within(drawer).getByText("Interface to SAP S/4HANA: Rechnungen an SAP")).toBeInTheDocument();
    expect(within(drawer).getByText("Planned")).toBeInTheDocument();
  });
});
