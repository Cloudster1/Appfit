import {
  Alert,
  Badge,
  Button,
  Card,
  Group,
  Progress,
  SimpleGrid,
  Stack,
  Switch,
  Table,
  Text,
  Title,
  Tooltip,
} from "@mantine/core";
import { IconAlertTriangle, IconRefresh } from "@tabler/icons-react";
import { useState } from "react";

import { useEmbeddingStatus, useImportRuns, useReindex, useSearchConfig, useSearchLogs } from "../api/hooks";
import { notifyError } from "../components/common/notify";
import { QueryState } from "../components/common/QueryState";
import { pct } from "../components/search/format";
import { ICON_SIZE, NAME_COLUMN_MAX_WIDTH, PERCENT, TABLE_MIN_WIDTH } from "../config";

function EmbeddingCard() {
  const status = useEmbeddingStatus();
  const reindex = useReindex();
  const s = status.data;
  const total = s ? s.apps_total + s.capabilities_total + s.interfaces_total : 0;
  const done = s ? s.apps_indexed + s.capabilities_indexed + s.interfaces_indexed : 0;

  const run = async (scope: "stale" | "all") => {
    try {
      await reindex.mutateAsync(scope);
      void status.refetch();
    } catch (e) {
      notifyError(e, "Reindex failed");
    }
  };

  return (
    <Card withBorder>
      <QueryState isPending={status.isPending} error={status.error}>
        {s && (
          <Stack>
            <Group justify="space-between">
              <Title order={4}>Embeddings</Title>
              <Group gap="xs">
                <Badge color={s.model_loaded ? "teal" : s.model_error ? "red" : "orange"}>
                  {s.model_loaded ? "model loaded" : s.model_error ? "model error" : "model loading"}
                </Badge>
                <Badge color={s.worker_running ? "teal" : "gray"} variant="light">
                  worker {s.worker_running ? "running" : "stopped"}
                </Badge>
              </Group>
            </Group>
            <Text size="sm">
              Active model: <code>{s.model_id}</code>
            </Text>
            {s.model_error && (
              <Alert color="red" icon={<IconAlertTriangle />}>
                {s.model_error}
              </Alert>
            )}
            {s.worker_last_error && (
              <Alert color="orange" icon={<IconAlertTriangle />} title="Last worker error">
                {s.worker_last_error}
              </Alert>
            )}
            <Stack gap={0}>
              <Group justify="space-between">
                <Text size="sm">
                  {done} of {total} texts indexed ({s.apps_indexed}/{s.apps_total} apps,{" "}
                  {s.capabilities_indexed}/{s.capabilities_total} capabilities, {s.interfaces_indexed}/
                  {s.interfaces_total} interfaces)
                </Text>
                <Text size="sm" fw="bold">
                  {total ? pct(done / total) : "-"}
                </Text>
              </Group>
              <Progress value={total ? (done / total) * PERCENT : 0} animated={s.pending > 0} />
            </Stack>
            <Group gap="xs">
              <Button
                variant="light"
                leftSection={<IconRefresh size={ICON_SIZE.sm} />}
                loading={reindex.isPending}
                onClick={() => run("stale")}
              >
                Process pending
              </Button>
              <Tooltip label="Re-embeds everything, e.g. after changing the model">
                <Button variant="default" loading={reindex.isPending} onClick={() => run("all")}>
                  Rebuild full index
                </Button>
              </Tooltip>
            </Group>
          </Stack>
        )}
      </QueryState>
    </Card>
  );
}

function ThresholdsCard() {
  const config = useSearchConfig();
  const th = config.data?.thresholds;
  return (
    <Card withBorder>
      <Stack gap="xs">
        <Title order={4}>Match thresholds</Title>
        <Text size="sm" c="dimmed">
          Calibrated per embedding model (thresholds.yaml, overridable via MATCH_T_* environment variables).
        </Text>
        {th && (
          <Table withRowBorders={false}>
            <Table.Tbody>
              <Table.Tr>
                <Table.Td>Covered at similarity</Table.Td>
                <Table.Td fw="bold">{th.covered}</Table.Td>
              </Table.Tr>
              <Table.Tr>
                <Table.Td>Partial at similarity</Table.Td>
                <Table.Td fw="bold">{th.partial}</Table.Td>
              </Table.Tr>
              <Table.Tr>
                <Table.Td>No match below score</Table.Td>
                <Table.Td fw="bold">{th.nomatch}</Table.Td>
              </Table.Tr>
              <Table.Tr>
                <Table.Td>No match below coverage</Table.Td>
                <Table.Td fw="bold">{th.min_top_coverage}</Table.Td>
              </Table.Tr>
            </Table.Tbody>
          </Table>
        )}
      </Stack>
    </Card>
  );
}

function SearchLogCard() {
  const [onlyFeedback, setOnlyFeedback] = useState(false);
  const [onlyNoMatch, setOnlyNoMatch] = useState(false);
  const logs = useSearchLogs({ onlyFeedback, onlyNoMatch });
  return (
    <Card withBorder>
      <Stack>
        <Group justify="space-between">
          <Title order={4}>Recent searches</Title>
          <Group>
            <Switch
              label="With feedback"
              checked={onlyFeedback}
              onChange={(e) => setOnlyFeedback(e.currentTarget.checked)}
            />
            <Switch
              label="No match"
              checked={onlyNoMatch}
              onChange={(e) => setOnlyNoMatch(e.currentTarget.checked)}
            />
          </Group>
        </Group>
        <QueryState isPending={logs.isPending} error={logs.error}>
          <Table.ScrollContainer minWidth={TABLE_MIN_WIDTH}>
            <Table striped>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>When</Table.Th>
                  <Table.Th>Query</Table.Th>
                  <Table.Th>Top result</Table.Th>
                  <Table.Th>Feedback</Table.Th>
                  <Table.Th ta="right">ms</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {logs.data?.items.map((log) => {
                  const top = log.results[0] as { slug?: string; final?: number } | undefined;
                  const fb = log.feedback as { rating?: string; expected_app_slug?: string } | null;
                  return (
                    <Table.Tr key={log.id}>
                      <Table.Td>
                        <Text size="xs">{new Date(log.created_at).toLocaleString()}</Text>
                      </Table.Td>
                      <Table.Td maw={NAME_COLUMN_MAX_WIDTH}>
                        <Text size="sm" lineClamp={2}>
                          {log.query_text}
                        </Text>
                      </Table.Td>
                      <Table.Td>
                        {log.no_match ? (
                          <Badge color="orange">no match</Badge>
                        ) : (
                          <Text size="sm">
                            {top?.slug} {top?.final !== undefined && `(${pct(top.final)})`}
                          </Text>
                        )}
                      </Table.Td>
                      <Table.Td>
                        {fb && (
                          <Badge color={fb.rating === "up" ? "teal" : "red"} variant="light">
                            {fb.rating}
                            {fb.expected_app_slug ? `: expected ${fb.expected_app_slug}` : ""}
                          </Badge>
                        )}
                      </Table.Td>
                      <Table.Td ta="right">{log.duration_ms}</Table.Td>
                    </Table.Tr>
                  );
                })}
              </Table.Tbody>
            </Table>
          </Table.ScrollContainer>
        </QueryState>
      </Stack>
    </Card>
  );
}

function ImportRunsCard() {
  const runs = useImportRuns();
  return (
    <Card withBorder>
      <Stack gap="xs">
        <Title order={4}>Recent imports</Title>
        <QueryState isPending={runs.isPending} error={runs.error}>
          <Table striped>
            <Table.Tbody>
              {runs.data?.map((r) => (
                <Table.Tr key={r.id}>
                  <Table.Td>
                    <Text size="xs">{new Date(r.created_at).toLocaleString()}</Text>
                  </Table.Td>
                  <Table.Td>{r.filename}</Table.Td>
                  <Table.Td>
                    <Badge variant="light" color={r.dry_run ? "gray" : "indigo"}>
                      {r.dry_run ? "dry run" : r.mode}
                    </Badge>
                  </Table.Td>
                  <Table.Td>
                    <Text size="xs">
                      {Object.entries(r.stats)
                        .filter(([k, v]) => k !== "total" && Number(v) > 0)
                        .map(([k, v]) => `${v} ${k}`)
                        .join(", ") || "-"}
                    </Text>
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </QueryState>
      </Stack>
    </Card>
  );
}

export function SystemPage() {
  return (
    <Stack>
      <Title order={2}>System</Title>
      <SimpleGrid cols={{ base: 1, md: 2 }}>
        <EmbeddingCard />
        <ThresholdsCard />
      </SimpleGrid>
      <SearchLogCard />
      <ImportRunsCard />
    </Stack>
  );
}
