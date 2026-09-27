import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import type { ReactNode } from "react";
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from "vitest";

import { keys, useDeleteApp, useImport } from "./hooks";

const server = setupServer(
  http.delete("*/api/apps/:slug", () => new HttpResponse(null, { status: 204 })),
);

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => {
  server.resetHandlers();
  vi.unstubAllGlobals();
});
afterAll(() => server.close());

function setup<T>(hook: () => T) {
  const client = new QueryClient();
  const invalidate = vi.spyOn(client, "invalidateQueries");
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
  const invalidated = () => invalidate.mock.calls.map(([filters]) => filters?.queryKey);
  return { result: renderHook(hook, { wrapper }).result, invalidated };
}

describe("cache invalidation", () => {
  // Imports and app deletions change interfaces too, so the landscape must not stay stale.
  it("refreshes interface views after a committed import", async () => {
    // jsdom's FormData does not pass through MSW's fetch interceptor, so fetch is stubbed here.
    vi.stubGlobal("fetch", vi.fn(async () => Response.json({ committed: true })));
    const { result, invalidated } = setup(useImport);
    const file = new File(["{}"], "apps.json");
    await result.current.mutateAsync({ file, mode: "upsert", dryRun: false, skipInvalid: false });
    expect(invalidated()).toEqual(
      expect.arrayContaining([keys.apps, keys.interfaces, keys.landscape, keys.systems, keys.tags]),
    );
  });

  it("refreshes interface views after deleting an app", async () => {
    const { result, invalidated } = setup(useDeleteApp);
    await result.current.mutateAsync("belegfix");
    expect(invalidated()).toEqual(expect.arrayContaining([keys.apps, keys.interfaces, keys.landscape]));
  });
});
