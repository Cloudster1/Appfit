import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { EMBEDDING_POLL_MS, PAGE_SIZE, RECENT_LOGS_LIMIT } from "../config";
import { api, rawFetch, unwrap, type Schemas } from "./client";

export type AppOut = Schemas["AppOut"];
export type AppIn = Schemas["AppIn"];
export type AppListItem = Schemas["AppListItem"];
export type UserOut = Schemas["UserOut"];
export type SearchRequest = Schemas["SearchRequest"];
export type SearchResponse = Schemas["SearchResponse"];
export type SearchResult = Schemas["SearchResult"];
export type ParsedRequirement = Schemas["ParsedRequirement"];
export type ImportReport = Schemas["ImportReport"];
export type TagOut = Schemas["TagOut"];
export type Role = Schemas["Role"];
export type Lifecycle = Schemas["LifecycleStatus"];
export type LicenseType = Schemas["LicenseType"];
export type InterfaceIn = Schemas["InterfaceIn"];
export type InterfaceOut = Schemas["InterfaceOut"];
export type InterfaceSummary = Schemas["InterfaceSummary"];
export type InterfaceType = Schemas["InterfaceType"];
export type InterfaceStatus = Schemas["InterfaceStatus"];
export type InterfaceFrequency = Schemas["InterfaceFrequency"];
export type EndpointOut = Schemas["EndpointOut"];
export type ExternalSystemOut = Schemas["ExternalSystemOut"];
export type Landscape = Schemas["Landscape"];
export type LandscapeNode = Schemas["LandscapeNode"];
export type LandscapeEdge = Schemas["LandscapeEdge"];
export type Combination = Schemas["Combination"];

export const keys = {
  me: ["me"] as const,
  apps: ["apps"] as const,
  app: (slug: string) => ["apps", "detail", slug] as const,
  similar: (slug: string) => ["apps", "similar", slug] as const,
  tags: ["tags"] as const,
  maintainers: ["maintainers"] as const,
  users: ["users"] as const,
  enums: ["meta", "enums"] as const,
  searchConfig: ["meta", "search-config"] as const,
  embeddingStatus: ["admin", "embeddings"] as const,
  searchLogs: ["admin", "search-logs"] as const,
  importRuns: ["admin", "import-runs"] as const,
  interfaces: ["interfaces"] as const,
  systems: ["external-systems"] as const,
  landscape: ["landscape"] as const,
};

export function useMe() {
  return useQuery({
    queryKey: keys.me,
    queryFn: async () => unwrap(await api.GET("/api/auth/me")),
    retry: false,
    staleTime: Infinity,
  });
}

export type AppFacets = Schemas["AppFacets"];

export type AppListParams = {
  q?: string;
  tags?: string[];
  status?: Schemas["LifecycleStatus"][];
  licenseTypes?: LicenseType[];
  domains?: string[];
  sort?: "name" | "updated" | "relevance";
  page?: number;
  size?: number;
};

function listQuery(params: AppListParams) {
  return {
    q: params.q || undefined,
    tags: params.tags,
    status: params.status,
    license_type: params.licenseTypes,
    domain: params.domains,
    sort: params.sort,
  };
}

export function useApps(params: AppListParams) {
  return useQuery({
    queryKey: [...keys.apps, "list", params],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/apps", {
          params: {
            query: { ...listQuery(params), page: params.page, size: params.size ?? PAGE_SIZE },
          },
        }),
      ),
    placeholderData: keepPreviousData,
  });
}

/** Value counts per facet for the same filters as the list; each facet ignores its own selection. */
export function useAppFacets(params: AppListParams) {
  return useQuery({
    queryKey: [...keys.apps, "facets", params],
    queryFn: async () => unwrap(await api.GET("/api/apps/facets", { params: { query: listQuery(params) } })),
    placeholderData: keepPreviousData,
  });
}

export function useApp(slug: string | undefined) {
  return useQuery({
    queryKey: keys.app(slug ?? ""),
    queryFn: async () => unwrap(await api.GET("/api/apps/{slug}", { params: { path: { slug: slug! } } })),
    enabled: Boolean(slug),
    refetchInterval: (query) =>
      query.state.data?.embedding_status === "pending" ? EMBEDDING_POLL_MS : false,
  });
}

export function useSimilarApps(slug: string) {
  return useQuery({
    queryKey: keys.similar(slug),
    queryFn: async () => unwrap(await api.GET("/api/apps/{slug}/similar", { params: { path: { slug } } })),
  });
}

export function useSaveApp(existingSlug?: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: AppIn) =>
      existingSlug
        ? unwrap(await api.PUT("/api/apps/{slug}", { params: { path: { slug: existingSlug } }, body }))
        : unwrap(await api.POST("/api/apps", { body })),
    onSuccess: (app) => {
      qc.invalidateQueries({ queryKey: keys.apps });
      qc.invalidateQueries({ queryKey: keys.tags });
      qc.setQueryData(keys.app(app.slug), app);
    },
  });
}

export function useDeleteApp() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (slug: string) =>
      unwrap(await api.DELETE("/api/apps/{slug}", { params: { path: { slug } } })),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.apps }),
  });
}

export function useTags() {
  return useQuery({ queryKey: keys.tags, queryFn: async () => unwrap(await api.GET("/api/tags")) });
}

export function useMaintainers() {
  return useQuery({
    queryKey: keys.maintainers,
    queryFn: async () => unwrap(await api.GET("/api/maintainers")),
  });
}

export function useEnums() {
  return useQuery({
    queryKey: keys.enums,
    queryFn: async () => unwrap(await api.GET("/api/meta/enums")),
    staleTime: Infinity,
  });
}

export function useSearchConfig() {
  return useQuery({
    queryKey: keys.searchConfig,
    queryFn: async () => unwrap(await api.GET("/api/meta/search-config")),
  });
}

export function useParseRequirements() {
  return useMutation({
    mutationFn: async (text: string) => unwrap(await api.POST("/api/search/parse", { body: { text } })),
  });
}

export function useSearch() {
  return useMutation({
    mutationFn: async (body: SearchRequest) => unwrap(await api.POST("/api/search", { body })),
  });
}

export function useSearchFeedback() {
  return useMutation({
    mutationFn: async (args: { logId: string; body: Schemas["FeedbackIn"] }) =>
      unwrap(
        await api.POST("/api/search/{log_id}/feedback", {
          params: { path: { log_id: args.logId } },
          body: args.body,
        }),
      ),
  });
}

export type ImportOptions = {
  file: File;
  mode: "upsert" | "create_only";
  dryRun: boolean;
  skipInvalid: boolean;
};

export function useImport() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (opts: ImportOptions): Promise<ImportReport> => {
      const form = new FormData();
      form.append("file", opts.file);
      const query = new URLSearchParams({
        mode: opts.mode,
        dry_run: String(opts.dryRun),
        skip_invalid: String(opts.skipInvalid),
      });
      const response = await rawFetch(`/api/import?${query}`, { method: "POST", body: form });
      return (await response.json()) as ImportReport;
    },
    onSuccess: (report) => {
      if (report.committed) {
        qc.invalidateQueries({ queryKey: keys.apps });
        qc.invalidateQueries({ queryKey: keys.tags });
      }
    },
  });
}

export function useUsers() {
  return useQuery({ queryKey: keys.users, queryFn: async () => unwrap(await api.GET("/api/users")) });
}

export function useCreateUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: Schemas["UserCreate"]) => unwrap(await api.POST("/api/users", { body })),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.users }),
  });
}

export function useUpdateUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (args: { id: string; body: Schemas["UserUpdate"] }) =>
      unwrap(
        await api.PATCH("/api/users/{user_id}", { params: { path: { user_id: args.id } }, body: args.body }),
      ),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.users }),
  });
}

export function useEmbeddingStatus() {
  return useQuery({
    queryKey: keys.embeddingStatus,
    queryFn: async () => unwrap(await api.GET("/api/admin/embeddings/status")),
    refetchInterval: (query) =>
      query.state.data && (query.state.data.pending > 0 || !query.state.data.model_loaded)
        ? EMBEDDING_POLL_MS
        : false,
  });
}

export function useReindex() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (scope: "stale" | "all") =>
      unwrap(await api.POST("/api/admin/embeddings/reindex", { body: { scope } })),
    onSuccess: (status) => qc.setQueryData(keys.embeddingStatus, status),
  });
}

export function useSearchLogs(filter: { onlyFeedback: boolean; onlyNoMatch: boolean }) {
  return useQuery({
    queryKey: [...keys.searchLogs, filter],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/admin/search-logs", {
          params: {
            query: {
              only_feedback: filter.onlyFeedback,
              only_no_match: filter.onlyNoMatch,
              size: RECENT_LOGS_LIMIT,
            },
          },
        }),
      ),
  });
}

export function useImportRuns() {
  return useQuery({
    queryKey: keys.importRuns,
    queryFn: async () => unwrap(await api.GET("/api/admin/import-runs")),
  });
}

export type LandscapeFilters = {
  domains: string[];
  lifecycle: Lifecycle[];
  types: InterfaceType[];
  statuses: InterfaceStatus[];
  includeSystems: boolean;
  includeUnconnected: boolean;
};

export function useLandscape(f: LandscapeFilters) {
  return useQuery({
    queryKey: [...keys.landscape, f],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/landscape", {
          params: {
            query: {
              domain: f.domains,
              lifecycle: f.lifecycle,
              type: f.types,
              status: f.statuses,
              include_systems: f.includeSystems,
              include_unconnected: f.includeUnconnected,
            },
          },
        }),
      ),
    placeholderData: keepPreviousData,
  });
}

export function useInterface(id: string | null) {
  return useQuery({
    queryKey: [...keys.interfaces, "detail", id],
    queryFn: async () =>
      unwrap(await api.GET("/api/interfaces/{interface_id}", { params: { path: { interface_id: id! } } })),
    enabled: Boolean(id),
  });
}

export function useExternalSystems() {
  return useQuery({
    queryKey: keys.systems,
    queryFn: async () => unwrap(await api.GET("/api/external-systems")),
  });
}

/** Interfaces change app details, the landscape and the list of external systems. */
function invalidateInterfaceViews(qc: ReturnType<typeof useQueryClient>) {
  for (const key of [keys.interfaces, keys.landscape, keys.systems, keys.apps]) {
    qc.invalidateQueries({ queryKey: key });
  }
}

export function useSaveInterface(id?: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: InterfaceIn) =>
      id
        ? unwrap(
            await api.PUT("/api/interfaces/{interface_id}", { params: { path: { interface_id: id } }, body }),
          )
        : unwrap(await api.POST("/api/interfaces", { body })),
    onSuccess: () => invalidateInterfaceViews(qc),
  });
}

export function useDeleteInterface() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) =>
      unwrap(await api.DELETE("/api/interfaces/{interface_id}", { params: { path: { interface_id: id } } })),
    onSuccess: () => invalidateInterfaceViews(qc),
  });
}
