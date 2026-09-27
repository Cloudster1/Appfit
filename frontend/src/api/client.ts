import createClient, { type Middleware } from "openapi-fetch";

import { API_CSRF_HEADER } from "../config";
import type { components, paths } from "./schema";

export type Schemas = components["schemas"];

const HTTP_UNAUTHORIZED = 401;
export const UNAUTHORIZED_EVENT = "appfit:unauthorized";

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

const unauthorizedMiddleware: Middleware = {
  onResponse({ request, response }) {
    if (response.status === HTTP_UNAUTHORIZED && !request.url.endsWith("/api/auth/login")) {
      window.dispatchEvent(new Event(UNAUTHORIZED_EVENT));
    }
    return response;
  },
};

export const api = createClient<paths>({
  baseUrl: window.location.origin,
  credentials: "include",
  headers: API_CSRF_HEADER,
  // Resolve fetch per call so test interceptors (MSW) that patch it later are honored.
  fetch: (request) => globalThis.fetch(request),
});
api.use(unauthorizedMiddleware);

type ValidationItem = { loc?: (string | number)[]; msg?: string };

export function errorMessage(detail: unknown, fallback = "Request failed"): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return (detail as ValidationItem[])
      .map((d) => `${(d.loc ?? []).filter((p) => p !== "body").join(".")}: ${d.msg ?? "invalid"}`)
      .join("; ");
  }
  return fallback;
}

/** Unwrap an openapi-fetch result: return data or throw an ApiError with the server's detail. */
export function unwrap<T>(result: { data?: T; error?: unknown; response: Response }): T {
  if (result.error !== undefined || !result.response.ok) {
    const detail = (result.error as { detail?: unknown } | undefined)?.detail;
    throw new ApiError(result.response.status, errorMessage(detail, result.response.statusText));
  }
  return result.data as T;
}

/** Plain fetch for endpoints openapi-fetch cannot model well (multipart upload, file download). */
export async function rawFetch(url: string, init: RequestInit = {}): Promise<Response> {
  const response = await fetch(url, {
    credentials: "include",
    ...init,
    headers: { ...API_CSRF_HEADER, ...(init.headers ?? {}) },
  });
  if (response.status === HTTP_UNAUTHORIZED) window.dispatchEvent(new Event(UNAUTHORIZED_EVENT));
  if (!response.ok) {
    let detail: unknown;
    try {
      detail = ((await response.json()) as { detail?: unknown }).detail;
    } catch {
      detail = undefined;
    }
    throw new ApiError(response.status, errorMessage(detail, response.statusText));
  }
  return response;
}
