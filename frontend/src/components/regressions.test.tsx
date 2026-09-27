import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { use } from "react";
import { Route, Routes } from "react-router";
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from "vitest";

import { api } from "../api/client";
import type { AppListItem, AppOut } from "../api/hooks";
import { AppShellLayout } from "../layout/AppShellLayout";
import { AppDetailPage } from "../pages/AppDetailPage";
import { renderWithProviders } from "../test/utils";
import { EmbeddingStatusBadge } from "./common/badges";
import { CatalogTile } from "./portal/Tiles";
import { uniqueTags } from "./search/format";

// Regression tests for bugs found while verifying the running app.

const admin = {
  id: "u1",
  email: "admin@example.com",
  display_name: "Admin",
  role: "admin",
  auth_provider: "local",
  is_active: true,
  created_at: "2026-01-01T00:00:00Z",
  last_login_at: null,
};

const baseApp: AppOut = {
  id: "a1",
  slug: "doc-vault",
  name: "Doc Vault",
  short_description: "Archive",
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
  domains: [],
  maintainers: [],
  capabilities: [],
  interfaces: [],
  embedding_status: "pending",
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

let detailCalls = 0;
const server = setupServer(
  http.get("*/api/auth/me", () => HttpResponse.json(admin)),
  http.get("*/api/apps/doc-vault", () => {
    detailCalls += 1;
    return HttpResponse.json({ ...baseApp, embedding_status: detailCalls === 1 ? "pending" : "indexed" });
  }),
  http.get("*/api/apps/doc-vault/similar", () => HttpResponse.json([])),
);

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe("duplicate tag badges", () => {
  it("lists a name once even if it exists as tag, domain and tech", () => {
    expect(uniqueTags(["collaboration", "chat"], ["collaboration"], ["saas", "chat"])).toEqual([
      "collaboration",
      "chat",
      "saas",
    ]);
  });

  it("renders each tag once on a catalog tile", () => {
    const app: AppListItem = {
      id: "a1",
      slug: "team-chat",
      name: "Team Chat",
      short_description: "Chat",
      lifecycle_status: "active",
      license_type: null,
      vendor: null,
      tags: ["saas", "collaboration"],
      tech_stack: ["saas"],
      domains: [],
      maintainers: [],
      capability_count: 1,
      embedding_status: "indexed",
      updated_at: "2026-01-01T00:00:00Z",
    };
    renderWithProviders(<CatalogTile app={app} />);
    const tile = screen.getByTestId("catalog-tile");
    expect(within(tile).getAllByText("saas")).toHaveLength(1);
  });
});

describe("lazy pages", () => {
  const neverResolves = new Promise<never>(() => {});
  function SuspendingPage() {
    use(neverResolves);
    return <p>page content</p>;
  }

  it("keep the navigation visible while a page chunk is loading", async () => {
    renderWithProviders(
      <Routes>
        <Route element={<AppShellLayout />}>
          <Route index element={<SuspendingPage />} />
        </Route>
      </Routes>,
      { withAuth: true },
    );
    expect(await screen.findByRole("link", { name: "Apps" })).toBeInTheDocument();
    expect(screen.getByText("Admin")).toBeInTheDocument();
    expect(screen.queryByText("page content")).not.toBeInTheDocument();
  });
});

describe("embedding status badge", () => {
  it("uses a variant that can carry an icon (the dot variant overlapped the icon and text)", () => {
    renderWithProviders(<EmbeddingStatusBadge status="indexed" />);
    const badge = screen.getByText("indexed").closest(".mantine-Badge-root");
    expect(badge).toHaveAttribute("data-variant", "light");
  });
});

describe("app detail page", () => {
  it("refreshes while indexing is pending so the badge turns to indexed", async () => {
    detailCalls = 0;
    renderWithProviders(
      <Routes>
        <Route path="/apps/:slug" element={<AppDetailPage />} />
      </Routes>,
      { route: "/apps/doc-vault", withAuth: true },
    );
    expect(await screen.findByText("indexing")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText("indexed")).toBeInTheDocument(), { timeout: 6000 });
    expect(detailCalls).toBeGreaterThanOrEqual(2);
  });
});

describe("API client", () => {
  it("resolves fetch per request, so interceptors installed after import are used", async () => {
    const spy = vi.spyOn(globalThis, "fetch");
    await api.GET("/api/auth/me");
    expect(spy).toHaveBeenCalledTimes(1);
    const request = spy.mock.calls[0]![0] as Request;
    expect(request.url).toMatch(/^https?:\/\/.+\/api\/auth\/me$/);
    expect(request.headers.get("X-Requested-With")).toBe("XMLHttpRequest");
    spy.mockRestore();
  });
});
