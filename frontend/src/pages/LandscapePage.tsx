import {
  Alert,
  Autocomplete,
  Box,
  Button,
  CloseButton,
  Collapse,
  Group,
  MultiSelect,
  Paper,
  Stack,
  Switch,
  Text,
  Title,
} from "@mantine/core";
import { useDisclosure, useMediaQuery } from "@mantine/hooks";
import { IconAdjustments, IconArrowRight, IconPlus, IconSearch } from "@tabler/icons-react";
import { lazy, Suspense, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router";

import {
  useApp,
  useAppFacets,
  useInterface,
  useLandscape,
  type InterfaceStatus,
  type InterfaceType,
  type Landscape,
  type LandscapeFilters,
  type Lifecycle,
} from "../api/hooks";
import { useAuth } from "../auth/AuthProvider";
import { LifecycleBadge } from "../components/common/badges";
import { QueryState } from "../components/common/QueryState";
import { findNode } from "../components/graph/graphModel";
import { Legend } from "../components/graph/Legend";
import { GraphFallback } from "../components/interfaces/AppInterfaces";
import { InterfaceForm } from "../components/interfaces/InterfaceForm";
import { EndpointName, InterfaceBadges, InterfaceList } from "../components/interfaces/InterfaceList";
import {
  DEFAULT_SEARCH_LIFECYCLE,
  GAP_TIGHT,
  ICON_SIZE,
  INTERFACE_FREQUENCY_LABELS,
  INTERFACE_STATUS_LABELS,
  INTERFACE_TYPE_LABELS,
  LANDSCAPE_HEIGHT,
  LANDSCAPE_MIN_HEIGHT,
} from "../config";

const LandscapeGraph = lazy(() =>
  import("../components/graph/LandscapeGraph").then((m) => ({ default: m.LandscapeGraph })),
);

const LIFECYCLE_OPTIONS = [...DEFAULT_SEARCH_LIFECYCLE, "retired"];
const FILTER_WIDTH = 200;
// Below the sm breakpoint the filters fold away behind a button.
const NARROW_QUERY = "(max-width: 48em)";

type Selection = { kind: "node"; id: string } | { kind: "edge"; id: string } | null;

function useFilters(): [LandscapeFilters, (patch: Partial<LandscapeFilters>) => void] {
  const [params, setParams] = useSearchParams();
  const filters: LandscapeFilters = {
    domains: params.getAll("domain"),
    lifecycle: params.getAll("lifecycle") as Lifecycle[],
    types: params.getAll("type") as InterfaceType[],
    statuses: params.getAll("status") as InterfaceStatus[],
    includeSystems: params.get("systems") !== "0",
    includeUnconnected: params.get("unconnected") === "1",
  };
  const update = (patch: Partial<LandscapeFilters>) => {
    const next = { ...filters, ...patch };
    const out = new URLSearchParams();
    next.domains.forEach((v) => out.append("domain", v));
    next.lifecycle.forEach((v) => out.append("lifecycle", v));
    next.types.forEach((v) => out.append("type", v));
    next.statuses.forEach((v) => out.append("status", v));
    if (!next.includeSystems) out.set("systems", "0");
    if (next.includeUnconnected) out.set("unconnected", "1");
    setParams(out, { replace: true });
  };
  return [filters, update];
}

function options(values: string[], labels?: Record<string, string>) {
  return values.map((value) => ({ value, label: labels?.[value] ?? value }));
}

/** Filters above the graph, so the graph can use the full page width. */
function FilterBar({
  filters,
  onChange,
}: {
  filters: LandscapeFilters;
  onChange: (p: Partial<LandscapeFilters>) => void;
}) {
  const facets = useAppFacets({});
  const common = { size: "xs", clearable: true, w: FILTER_WIDTH } as const;
  return (
    <Group gap="sm" align="flex-end" data-testid="landscape-filters">
      <MultiSelect
        {...common}
        label="Domain"
        placeholder="All domains"
        searchable
        data={options((facets.data?.domain ?? []).map((d) => d.value))}
        value={filters.domains}
        onChange={(domains) => onChange({ domains })}
      />
      <MultiSelect
        {...common}
        label="Lifecycle"
        placeholder="All but retired"
        data={options(LIFECYCLE_OPTIONS)}
        value={filters.lifecycle}
        onChange={(lifecycle) => onChange({ lifecycle: lifecycle as Lifecycle[] })}
      />
      <MultiSelect
        {...common}
        label="Interface type"
        placeholder="All types"
        data={options(Object.keys(INTERFACE_TYPE_LABELS), INTERFACE_TYPE_LABELS)}
        value={filters.types}
        onChange={(types) => onChange({ types: types as InterfaceType[] })}
      />
      <MultiSelect
        {...common}
        label="Interface status"
        placeholder="All states"
        data={options(Object.keys(INTERFACE_STATUS_LABELS), INTERFACE_STATUS_LABELS)}
        value={filters.statuses}
        onChange={(statuses) => onChange({ statuses: statuses as InterfaceStatus[] })}
      />
      <Stack gap={GAP_TIGHT} pb={GAP_TIGHT}>
        <Switch
          size="xs"
          label="External systems"
          checked={filters.includeSystems}
          onChange={(e) => onChange({ includeSystems: e.currentTarget.checked })}
        />
        <Switch
          size="xs"
          label="Apps without interfaces"
          checked={filters.includeUnconnected}
          onChange={(e) => onChange({ includeUnconnected: e.currentTarget.checked })}
        />
      </Stack>
    </Group>
  );
}

function NodeDetails({ landscape, nodeId }: { landscape: Landscape; nodeId: string }) {
  const node = landscape.nodes.find((n) => n.id === nodeId);
  const app = useApp(node?.kind === "app" ? (node.slug ?? undefined) : undefined);
  if (!node) return null;
  if (node.kind === "system") {
    const edges = landscape.edges.filter((e) => e.source === nodeId || e.target === nodeId);
    return (
      <Stack>
        <Text size="sm" c="dimmed">
          External system, connected to {edges.length} app{edges.length === 1 ? "" : "s"} in this view.
        </Text>
        {edges.map((e) => (
          <Text key={e.id} size="sm">
            {e.name}
          </Text>
        ))}
      </Stack>
    );
  }
  return (
    <QueryState isPending={app.isPending} error={app.error}>
      {app.data && (
        <Stack>
          <Group gap="xs">
            <LifecycleBadge status={app.data.lifecycle_status} />
          </Group>
          <Text size="sm">{app.data.short_description}</Text>
          <InterfaceList interfaces={app.data.interfaces} />
          <Group>
            <Button
              component={Link}
              to={`/apps/${app.data.slug}`}
              rightSection={<IconArrowRight size={ICON_SIZE.sm} />}
            >
              Open app details
            </Button>
          </Group>
        </Stack>
      )}
    </QueryState>
  );
}

function EdgeDetails({ edgeId, onEdit }: { edgeId: string; onEdit?: () => void }) {
  const iface = useInterface(edgeId);
  return (
    <QueryState isPending={iface.isPending} error={iface.error}>
      {iface.data && (
        <Stack data-testid="interface-details">
          <Group gap="xs">
            <InterfaceBadges type={iface.data.type} status={iface.data.status} />
          </Group>
          <Group gap="xs">
            <EndpointName endpoint={iface.data.from} />
            <Text size="sm">{iface.data.bidirectional ? "<->" : "->"}</Text>
            <EndpointName endpoint={iface.data.to} />
          </Group>
          {iface.data.data_objects.length > 0 && (
            <Text size="sm">
              <Text span c="dimmed" size="sm">
                Data:{" "}
              </Text>
              {iface.data.data_objects.join(", ")}
            </Text>
          )}
          {iface.data.frequency && (
            <Text size="sm">
              <Text span c="dimmed" size="sm">
                Frequency:{" "}
              </Text>
              {INTERFACE_FREQUENCY_LABELS[iface.data.frequency]}
            </Text>
          )}
          {iface.data.description && <Text size="sm">{iface.data.description}</Text>}
          {onEdit && (
            <Group>
              <Button variant="light" onClick={onEdit}>
                Edit interface
              </Button>
            </Group>
          )}
        </Stack>
      )}
    </QueryState>
  );
}

/** The integration landscape: apps and external systems as nodes, interfaces as directed edges. */
export function LandscapePage() {
  const { hasRole } = useAuth();
  const [filters, setFilters] = useFilters();
  const landscape = useLandscape(filters);
  const [selection, setSelection] = useState<Selection>(null);
  const [search, setSearch] = useState("");
  const [adding, setAdding] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const editing = useInterface(editingId);
  const narrow = useMediaQuery(NARROW_QUERY);
  const [filtersOpen, { toggle: toggleFilters }] = useDisclosure(false);

  const data = landscape.data;
  const highlight = data ? (findNode(data.nodes, search)?.id ?? null) : null;
  const focusId = selection?.kind === "node" ? selection.id : highlight;
  const types = useMemo(() => [...new Set(data?.edges.map((e) => e.type) ?? [])].sort(), [data]);
  const title =
    selection?.kind === "node" ? data?.nodes.find((n) => n.id === selection.id)?.name : "Interface";

  return (
    <Stack gap="md">
      <Group justify="space-between" align="flex-end">
        <Stack gap={0}>
          <Title order={1} fz="h2" className="rb-display">
            Integration landscape
          </Title>
          <Text c="dimmed" size="sm">
            {data ? `${data.nodes.length} systems and ${data.edges.length} interfaces. ` : ""}
            Click an app to zoom to its neighbours, or an arrow for the interface.
          </Text>
        </Stack>
        <Group gap="xs">
          <Autocomplete
            aria-label="Find an app or system"
            placeholder="Find an app or system"
            leftSection={<IconSearch size={ICON_SIZE.sm} />}
            data={[...new Set(data?.nodes.map((n) => n.name) ?? [])]}
            value={search}
            onChange={(v) => {
              setSearch(v);
              setSelection(null);
            }}
            size="xs"
          />
          {hasRole("editor") && (
            <Button size="xs" leftSection={<IconPlus size={ICON_SIZE.sm} />} onClick={() => setAdding(true)}>
              Add interface
            </Button>
          )}
        </Group>
      </Group>

      {narrow ? (
        <Stack gap="xs">
          <Group>
            <Button
              variant="default"
              size="xs"
              leftSection={<IconAdjustments size={ICON_SIZE.sm} />}
              onClick={toggleFilters}
            >
              Filters
            </Button>
          </Group>
          <Collapse expanded={filtersOpen}>
            <FilterBar filters={filters} onChange={setFilters} />
          </Collapse>
        </Stack>
      ) : (
        <FilterBar filters={filters} onChange={setFilters} />
      )}
      <Legend types={types} />

      <Box className={selection ? "rb-landscape rb-landscape-open" : "rb-landscape"}>
        <Stack gap="xs" style={{ minWidth: 0 }}>
          <QueryState isPending={landscape.isPending} error={landscape.error}>
            {data && data.nodes.length === 0 ? (
              <Alert color="gray">No interfaces match these filters.</Alert>
            ) : (
              data && (
                <Suspense fallback={<GraphFallback height={LANDSCAPE_HEIGHT} />}>
                  <Box mih={LANDSCAPE_MIN_HEIGHT}>
                    <LandscapeGraph
                      landscape={data}
                      height={LANDSCAPE_HEIGHT}
                      focusId={focusId}
                      highlightId={highlight}
                      onNodeClick={(id) => setSelection({ kind: "node", id })}
                      onEdgeClick={(id) => setSelection({ kind: "edge", id })}
                      onPaneClick={() => setSelection(null)}
                    />
                  </Box>
                </Suspense>
              )
            )}
          </QueryState>
        </Stack>

        {selection && (
          <Paper
            withBorder
            radius="lg"
            p="md"
            data-testid="landscape-details"
            className="rb-landscape-details"
          >
            <Stack>
              <Group justify="space-between" wrap="nowrap" align="flex-start">
                <Text className="rb-display" fw="bold" fz="xl">
                  {title}
                </Text>
                <CloseButton aria-label="Close details" onClick={() => setSelection(null)} />
              </Group>
              {selection.kind === "node" && data && <NodeDetails landscape={data} nodeId={selection.id} />}
              {selection.kind === "edge" && (
                <EdgeDetails
                  edgeId={selection.id}
                  onEdit={hasRole("editor") ? () => setEditingId(selection.id) : undefined}
                />
              )}
            </Stack>
          </Paper>
        )}
      </Box>

      <InterfaceForm opened={adding} onClose={() => setAdding(false)} />
      <InterfaceForm
        opened={Boolean(editingId && editing.data)}
        onClose={() => setEditingId(null)}
        existing={editing.data ?? null}
      />
    </Stack>
  );
}
