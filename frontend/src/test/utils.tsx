import { MantineProvider } from "@mantine/core";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter } from "react-router";

import type { SearchResponse } from "../api/hooks";
import { AuthProvider } from "../auth/AuthProvider";

export function renderWithProviders(ui: ReactElement, { route = "/", withAuth = false } = {}) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const tree = (
    <MantineProvider>
      <QueryClientProvider client={client}>
        <MemoryRouter initialEntries={[route]}>
          {withAuth ? <AuthProvider>{ui}</AuthProvider> : ui}
        </MemoryRouter>
      </QueryClientProvider>
    </MantineProvider>
  );
  return render(tree);
}

export const sampleResponse: SearchResponse = {
  status: "ok",
  requirements: [
    { idx: 0, text: "OCR for invoices", priority: "must", weight: 1 },
    { idx: 1, text: "Export to SAP", priority: null, weight: 1 },
    { idx: 2, text: "Canteen menu", priority: "could", weight: 0.3 },
  ],
  results: [
    {
      app: {
        id: "11111111-1111-1111-1111-111111111111",
        slug: "invoice-hub",
        name: "Invoice Hub",
        short_description: "Invoice processing",
        lifecycle_status: "active",
        vendor: "ACME",
        tags: ["finance"],
        tech_stack: ["java"],
        domains: ["accounting"],
        maintainers: ["Team Finance IT"],
      },
      final: 0.82,
      coverage: 0.8,
      soft: 0.9,
      label: "strong",
      flags: [],
      signals: { rrf: 0.04, summary_rank: 1, capability_rank: 1, fts_rank: 2 },
      evidence: [
        {
          req_idx: 0,
          status: "covered",
          score: 0.81,
          similarity: 0.81,
          via: "capability",
          capability: { id: "c1", kind: "capability", text: "OCR extraction of invoice data" },
          keyword_hits: ["ocr"],
        },
        {
          req_idx: 1,
          status: "partial",
          score: 0.6,
          similarity: 0.6,
          via: "summary",
          capability: null,
          keyword_hits: [],
        },
        {
          req_idx: 2,
          status: "gap",
          score: 0.2,
          similarity: 0.2,
          via: "capability",
          capability: null,
          keyword_hits: [],
        },
      ],
      recommended: true,
    },
  ],
  catalog_gaps: [2],
  connections: { nodes: [], edges: [] },
  combinations: [],
  thresholds: { model: "fake", covered: 0.65, partial: 0.52, nomatch: 0.4, min_top_coverage: 0.34 },
  candidates_considered: 4,
  duration_ms: 42,
  search_log_id: "22222222-2222-2222-2222-222222222222",
};
