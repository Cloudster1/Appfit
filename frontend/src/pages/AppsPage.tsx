import {
  Alert,
  Box,
  Button,
  Drawer,
  Group,
  Pagination,
  SegmentedControl,
  Select,
  SimpleGrid,
  Stack,
  Text,
  Title,
} from "@mantine/core";
import { useDebouncedValue, useDisclosure, useLocalStorage } from "@mantine/hooks";
import { IconAdjustments, IconAlertTriangle, IconArrowLeft, IconPlus } from "@tabler/icons-react";
import { useRef, useState } from "react";
import { Link, useSearchParams } from "react-router";

import {
  useAppFacets,
  useApps,
  useParseRequirements,
  useSearch,
  useSearchConfig,
  type AppListParams,
  type LicenseType,
  type Lifecycle,
  type SearchRequest,
  type SearchResponse,
} from "../api/hooks";
import { useAuth } from "../auth/AuthProvider";
import { QueryState } from "../components/common/QueryState";
import { ConnectionsPanel } from "../components/portal/ConnectionsPanel";
import { EvidenceDrawer } from "../components/portal/EvidenceDrawer";
import { FacetPanel, type FacetSelection } from "../components/portal/FacetPanel";
import { SearchComposer, type ComposerMode } from "../components/portal/SearchComposer";
import { CatalogTile, GapTile, ResultTile } from "../components/portal/Tiles";
import { ComplianceMatrix } from "../components/search/ComplianceMatrix";
import { FeedbackButtons } from "../components/search/FeedbackButtons";
import { keywordFromText } from "../components/search/format";
import { NoMatchBanner } from "../components/search/NoMatchBanner";
import type { EditableRequirement } from "../components/search/RequirementEditor";
import {
  CATALOG_PAGE_SIZE,
  DEFAULT_SEARCH_LIFECYCLE,
  GAP_TIGHT,
  ICON_SIZE,
  INTRO_MAX_WIDTH,
  LIST_SEARCH_DEBOUNCE_MS,
  PORTAL_MAX_WIDTH,
  RESULTS_VIEW_STORAGE_KEY,
  SEARCH_RESULT_LIMIT,
  SORT_SELECT_WIDTH,
} from "../config";

export type ResultsView = "tiles" | "matrix";
type Sort = "name" | "updated";

const FALLBACK_MAX_REQUIREMENTS = 30;
const GRID_COLS = { base: 1, sm: 2, lg: 3 };

/** No lifecycle selected means every state except retired, for browsing and matching alike. */
function effectiveLifecycle(selected: string[]): Lifecycle[] {
  return (selected.length ? selected : [...DEFAULT_SEARCH_LIFECYCLE]) as Lifecycle[];
}

function searchFilters(sel: FacetSelection): SearchRequest["filters"] {
  return {
    lifecycle: effectiveLifecycle(sel.lifecycle),
    tags: [],
    domains: sel.domains,
    license_types: sel.licenseTypes as LicenseType[],
  };
}

function plural(n: number, word: string): string {
  return `${n} ${word}${n === 1 ? "" : "s"}`;
}

/** Catalog and requirement matching on one screen: facets, a search field and app tiles. */
export function AppsPage() {
  const [params, setParams] = useSearchParams();
  const selection: FacetSelection = {
    lifecycle: params.getAll("status"),
    domains: params.getAll("domain"),
    licenseTypes: params.getAll("license"),
  };
  const sort: Sort = params.get("sort") === "updated" ? "updated" : "name";
  const page = Number(params.get("page") ?? "1");

  const [mode, setMode] = useState<ComposerMode>("text");
  const [text, setText] = useState("");
  const [requirements, setRequirements] = useState<EditableRequirement[]>([]);
  const [result, setResult] = useState<SearchResponse | null>(null);
  const [lastRequest, setLastRequest] = useState<SearchRequest | null>(null);
  const [openAppId, setOpenAppId] = useState<string | null>(null);
  const [filtersOpen, filtersDrawer] = useDisclosure(false);
  const [view, setView] = useLocalStorage<ResultsView>({
    key: RESULTS_VIEW_STORAGE_KEY,
    defaultValue: "tiles",
  });

  const [debouncedText] = useDebouncedValue(text, LIST_SEARCH_DEBOUNCE_MS);
  const keyword = mode === "text" ? keywordFromText(debouncedText) : "";
  const listParams: AppListParams = {
    q: keyword,
    status: effectiveLifecycle(selection.lifecycle),
    domains: selection.domains,
    licenseTypes: selection.licenseTypes as LicenseType[],
  };
  const facets = useAppFacets(listParams);
  const search = useSearch();
  const parse = useParseRequirements();
  const config = useSearchConfig();
  const maxRequirements = config.data?.max_requirements ?? FALLBACK_MAX_REQUIREMENTS;

  const canSearch = mode === "text" ? Boolean(text.trim()) : requirements.some((r) => r.text.trim());

  const updateParams = (patch: Record<string, string | string[] | null>) => {
    const next = new URLSearchParams(params);
    for (const [key, value] of Object.entries(patch)) {
      next.delete(key);
      if (Array.isArray(value)) value.forEach((v) => next.append(key, v));
      else if (value) next.set(key, value);
    }
    if (!("page" in patch)) next.delete("page");
    setParams(next, { replace: true });
  };

  // Responses can arrive out of order; only the latest request may set the result.
  const latestSearch = useRef(0);
  const execute = async (body: SearchRequest) => {
    const seq = ++latestSearch.current;
    try {
      const res = await search.mutateAsync(body);
      if (seq !== latestSearch.current) return;
      setResult(res);
      setLastRequest(body);
      setRequirements(res.requirements.map((r) => ({ text: r.text, priority: r.priority ?? null })));
    } catch {
      // search.error renders the failure.
    }
  };

  const runSearch = () => {
    const body: SearchRequest = { limit: SEARCH_RESULT_LIMIT, filters: searchFilters(selection) };
    if (mode === "text") body.text = text;
    else
      body.requirements = requirements
        .filter((r) => r.text.trim())
        .map((r) => ({ ...r, text: r.text.trim() }));
    void execute(body);
  };

  const changeFilters = (next: FacetSelection) => {
    updateParams({ status: next.lifecycle, domain: next.domains, license: next.licenseTypes });
    // Filters apply to the current match right away, like they do to the catalog.
    if (result && lastRequest) void execute({ ...lastRequest, filters: searchFilters(next) });
  };

  const review = async () => {
    const res = await parse.mutateAsync(text);
    setRequirements(res.requirements.map((r) => ({ text: r.text, priority: r.priority ?? null })));
    setMode("list");
  };

  const backToCatalog = () => {
    latestSearch.current++;
    setResult(null);
    setLastRequest(null);
    setOpenAppId(null);
  };

  const activeFilters = selection.lifecycle.length + selection.domains.length + selection.licenseTypes.length;
  const facetPanel = <FacetPanel facets={facets.data} selected={selection} onChange={changeFilters} />;

  return (
    <Stack maw={PORTAL_MAX_WIDTH} mx="auto" gap="lg">
      <Stack gap={GAP_TIGHT}>
        <Title order={1} fz="h2" className="rb-display">
          Which app fits your use case?
        </Title>
        <Text c="dimmed" maw={INTRO_MAX_WIDTH}>
          Browse the catalog, or describe your requirements in German or English. Appfit ranks the apps and
          explains which capability covers each requirement.
        </Text>
      </Stack>

      <SearchComposer
        text={text}
        onTextChange={setText}
        mode={mode}
        onModeChange={setMode}
        requirements={requirements}
        onRequirementsChange={setRequirements}
        maxRequirements={maxRequirements}
        canSearch={canSearch}
        searching={search.isPending}
        parsing={parse.isPending}
        onSearch={runSearch}
        onReview={review}
      />

      {search.error && (
        <Alert color="red" icon={<IconAlertTriangle />} title="Search failed">
          {search.error.message}
        </Alert>
      )}

      <Box className="rb-portal">
        <Box visibleFrom="md">{facetPanel}</Box>
        <Stack gap="md">
          <Group hiddenFrom="md">
            <Button
              variant="default"
              size="xs"
              leftSection={<IconAdjustments size={ICON_SIZE.sm} />}
              onClick={filtersDrawer.open}
            >
              Filters{activeFilters ? ` (${activeFilters})` : ""}
            </Button>
          </Group>
          {result ? (
            <ResultsSection
              result={result}
              view={view}
              onViewChange={setView}
              onBack={backToCatalog}
              onOpen={setOpenAppId}
            />
          ) : (
            <CatalogSection
              listParams={listParams}
              keyword={keyword}
              sort={sort}
              page={page}
              onSort={(s) => updateParams({ sort: s === "name" ? null : s })}
              onPage={(p) => updateParams({ page: String(p) })}
              pendingRequirements={mode === "list" || text.trim().includes("\n")}
            />
          )}
        </Stack>
      </Box>

      <Drawer opened={filtersOpen} onClose={filtersDrawer.close} title="Filters" size="xs">
        {facetPanel}
      </Drawer>
      <EvidenceDrawer
        result={result?.results.find((r) => r.app.id === openAppId) ?? null}
        requirements={result?.requirements ?? []}
        onClose={() => setOpenAppId(null)}
      />
    </Stack>
  );
}

type CatalogProps = {
  listParams: AppListParams;
  keyword: string;
  sort: Sort;
  page: number;
  onSort: (sort: Sort) => void;
  onPage: (page: number) => void;
  pendingRequirements: boolean;
};

function CatalogSection({
  listParams,
  keyword,
  sort,
  page,
  onSort,
  onPage,
  pendingRequirements,
}: CatalogProps) {
  const { hasRole } = useAuth();
  const apps = useApps({
    ...listParams,
    sort: keyword ? "relevance" : sort,
    page,
    size: CATALOG_PAGE_SIZE,
  });
  const total = apps.data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / CATALOG_PAGE_SIZE));

  return (
    <Stack gap="md" data-testid="catalog">
      <Group justify="space-between" align="flex-end">
        <Stack gap={0}>
          <Title order={2} fz="h3" className="rb-display">
            {apps.data ? plural(total, "app") : "Apps"}
            {keyword && ` matching "${keyword}"`}
          </Title>
          <Text size="sm" c="dimmed">
            {keyword ? "Sorted by relevance" : "The application catalog"}
          </Text>
        </Stack>
        <Group gap="xs">
          {!keyword && (
            <Select
              size="xs"
              aria-label="Sort by"
              w={SORT_SELECT_WIDTH}
              allowDeselect={false}
              value={sort}
              onChange={(v) => onSort((v as Sort | null) ?? "name")}
              data={[
                { value: "name", label: "Name" },
                { value: "updated", label: "Recently updated" },
              ]}
            />
          )}
          {hasRole("editor") && (
            <Button size="xs" component={Link} to="/apps/new" leftSection={<IconPlus size={ICON_SIZE.sm} />}>
              New app
            </Button>
          )}
        </Group>
      </Group>

      {pendingRequirements && (
        <Alert color="cobalt" variant="light" data-testid="match-hint">
          Several lines are read as requirements. Press &quot;Find matching apps&quot; to rank the catalog
          against them.
        </Alert>
      )}

      <QueryState isPending={apps.isPending} error={apps.error}>
        <SimpleGrid cols={GRID_COLS} spacing="md">
          {apps.data?.items.map((app) => (
            <CatalogTile key={app.id} app={app} />
          ))}
        </SimpleGrid>
        {apps.data?.items.length === 0 && (
          <Text c="dimmed" ta="center" py="xl">
            No apps match these filters.
          </Text>
        )}
        {totalPages > 1 && (
          <Group justify="center">
            <Pagination total={totalPages} value={page} onChange={onPage} />
          </Group>
        )}
      </QueryState>
    </Stack>
  );
}

type ResultsProps = {
  result: SearchResponse;
  view: ResultsView;
  onViewChange: (view: ResultsView) => void;
  onBack: () => void;
  onOpen: (appId: string) => void;
};

function ResultsSection({ result, view, onViewChange, onBack, onOpen }: ResultsProps) {
  const noMatch = result.status === "no_match";
  const count = result.results.length;
  const showMatrix = view === "matrix" && count > 0;

  return (
    <Stack gap="md" data-testid="search-results">
      <Group justify="space-between" align="flex-end">
        <Stack gap={0}>
          <Title order={2} fz="h3" className="rb-display">
            {noMatch
              ? "No good match"
              : `${plural(count, "app")} ${count === 1 ? "fits" : "fit"} your requirements`}
          </Title>
          <Text size="sm" c="dimmed">
            {plural(result.requirements.length, "requirement")}, {result.candidates_considered} candidate apps
            checked in {result.duration_ms} ms
          </Text>
        </Stack>
        <Group gap="xs">
          {count > 0 && (
            <SegmentedControl
              size="xs"
              aria-label="Result view"
              value={view}
              onChange={(v) => onViewChange(v as ResultsView)}
              data={[
                { value: "tiles", label: "Tiles" },
                { value: "matrix", label: "Matrix" },
              ]}
            />
          )}
          <Button
            variant="default"
            size="xs"
            leftSection={<IconArrowLeft size={ICON_SIZE.sm} />}
            onClick={onBack}
          >
            Back to catalog
          </Button>
        </Group>
      </Group>

      {noMatch && <NoMatchBanner gaps={result.catalog_gaps} requirements={result.requirements} />}
      {noMatch && count > 0 && (
        <Text fw="bold" size="sm">
          Closest candidates (not recommended)
        </Text>
      )}
      {!noMatch && count === 0 && (
        <Alert color="gray">No apps with any evidence for these requirements.</Alert>
      )}

      {showMatrix ? (
        <ComplianceMatrix
          results={result.results}
          requirements={result.requirements}
          gaps={result.catalog_gaps}
        />
      ) : (
        <SimpleGrid cols={GRID_COLS} spacing="md">
          {result.results.map((r, i) => (
            <ResultTile
              key={r.app.id}
              result={r}
              requirements={result.requirements}
              best={i === 0 && !noMatch}
              onOpen={() => onOpen(r.app.id)}
            />
          ))}
          {!noMatch && result.catalog_gaps.length > 0 && (
            <GapTile gaps={result.catalog_gaps} requirements={result.requirements} />
          )}
        </SimpleGrid>
      )}

      <ConnectionsPanel result={result} />
      {result.search_log_id && <FeedbackButtons key={result.search_log_id} logId={result.search_log_id} />}
    </Stack>
  );
}
