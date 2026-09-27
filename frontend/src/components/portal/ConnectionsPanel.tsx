import { Badge, Card, Group, List, SimpleGrid, Stack, Text, Title } from "@mantine/core";
import { IconPlug } from "@tabler/icons-react";
import { lazy, Suspense } from "react";

import type { SearchResponse } from "../../api/hooks";
import { GAP_COMPACT, ICON_SIZE, INTERFACE_STATUS_LABELS } from "../../config";
import { miniGraphHeight } from "../graph/graphModel";
import { GraphFallback } from "../interfaces/AppInterfaces";

const LandscapeGraph = lazy(() =>
  import("../graph/LandscapeGraph").then((m) => ({ default: m.LandscapeGraph })),
);

const COMBINATION_COLS = { base: 1, md: 2 };

/** How the result apps are connected, and connected pairs that cover more requirements together. */
export function ConnectionsPanel({ result }: { result: SearchResponse }) {
  const { connections, combinations } = result;
  if (connections.edges.length === 0 && combinations.length === 0) return null;
  const names = new Map(result.results.map((r) => [r.app.slug, r.app.name]));
  const reqText = new Map(result.requirements.map((r) => [r.idx, r.text]));
  const total = result.requirements.length;

  return (
    <Stack gap="sm" data-testid="connections-panel">
      <Stack gap={0}>
        <Title order={3} fz="h4" className="rb-display">
          How they connect
        </Title>
        <Text size="sm" c="dimmed">
          Documented interfaces between these apps, and external systems two or more of them use.
        </Text>
      </Stack>
      {combinations.length > 0 && (
        <SimpleGrid cols={COMBINATION_COLS} spacing="sm">
          {combinations.map((c) => (
            <Card key={c.interface_id} withBorder radius="lg" data-testid="combination-card">
              <Stack gap="xs">
                <Text fw="bold">
                  {c.apps.map((s) => names.get(s) ?? s).join(" + ")} cover {c.covered.length} of {total}{" "}
                  together
                </Text>
                <Group gap={GAP_COMPACT} wrap="nowrap">
                  <IconPlug size={ICON_SIZE.sm} aria-hidden />
                  <Text size="sm">Connected by {c.interface_name}</Text>
                  {c.interface_status !== "active" && (
                    <Badge size="xs" variant="outline" color="yellow">
                      {INTERFACE_STATUS_LABELS[c.interface_status]}
                    </Badge>
                  )}
                </Group>
                <List size="xs" c="dimmed">
                  {c.covered.map((i) => (
                    <List.Item key={i}>{reqText.get(i)}</List.Item>
                  ))}
                </List>
              </Stack>
            </Card>
          ))}
        </SimpleGrid>
      )}
      {connections.edges.length > 0 && (
        <Suspense fallback={<GraphFallback height={miniGraphHeight(connections)} />}>
          <LandscapeGraph landscape={connections} height={miniGraphHeight(connections)} compact />
        </Suspense>
      )}
    </Stack>
  );
}
