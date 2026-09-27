import { Anchor, Button, Group, Stack, Table, Text } from "@mantine/core";
import { IconDownload } from "@tabler/icons-react";
import type { CSSProperties } from "react";
import { Link } from "react-router";

import type { ParsedRequirement, SearchResult } from "../../api/hooks";
import {
  GAP_COMPACT,
  GAP_TIGHT,
  ICON_SIZE,
  LABEL_COLORS,
  MATRIX_CSV_DELIMITER,
  MATRIX_REQUIREMENT_WIDTH,
  MATRIX_TOP_APPS,
  PRIORITY_LABELS,
  STATUS_COLORS,
  TABLE_MIN_WIDTH,
} from "../../config";
import { countStatuses, evidenceText, FLAG_TEXT, LABEL_TEXT, matrixCsv, mustHaves, pct } from "./format";
import { StatusIcon } from "./StatusIcon";

type Props = { results: SearchResult[]; requirements: ParsedRequirement[]; gaps: number[] };

const UTF8_BOM = String.fromCharCode(0xfeff);
const STATUS_WORD = { covered: "covered", partial: "partial", gap: "gap" } as const;

function downloadCsv(content: string) {
  // A BOM lets spreadsheet programs detect UTF-8 (umlauts in German requirements).
  const blob = new Blob([UTF8_BOM, content], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "appfit-requirement-fit.csv";
  link.click();
  URL.revokeObjectURL(url);
}

/** Requirements as rows, apps as columns; each cell names the capability that matched. */
export function ComplianceMatrix({ results, requirements, gaps }: Props) {
  const top = results.slice(0, MATRIX_TOP_APPS);
  const gapSet = new Set(gaps);
  const anyMust = requirements.some((r) => r.priority === "must");

  return (
    <Stack gap="xs">
      <Group justify="space-between">
        <Text size="sm" c="dimmed">
          {requirements.length} requirements, top {top.length} apps. Hover a symbol for its meaning.
        </Text>
        <Button
          variant="default"
          size="xs"
          leftSection={<IconDownload size={ICON_SIZE.sm} />}
          onClick={() => downloadCsv(matrixCsv(top, requirements, MATRIX_CSV_DELIMITER))}
        >
          Export CSV
        </Button>
      </Group>
      <Table.ScrollContainer minWidth={TABLE_MIN_WIDTH}>
        <Table withTableBorder withColumnBorders verticalSpacing="sm" aria-label="Coverage matrix">
          <Table.Thead>
            <Table.Tr>
              <Table.Th w={MATRIX_REQUIREMENT_WIDTH}>Requirement</Table.Th>
              {top.map((r) => (
                <Table.Th key={r.app.id} data-testid={`matrix-app-${r.app.slug}`}>
                  <Anchor component={Link} to={`/apps/${r.app.slug}`} fw="bold">
                    {r.app.name}
                  </Anchor>
                  <Group gap={GAP_COMPACT} align="baseline" wrap="nowrap">
                    <Text ff="monospace" fz="lg" fw={600}>
                      {pct(r.final)}
                    </Text>
                    <Text size="xs" c={LABEL_COLORS[r.label]} fw={600}>
                      {LABEL_TEXT[r.label]}
                    </Text>
                  </Group>
                  {r.flags.map((f) => (
                    <Text key={f} size="xs" c="red">
                      {FLAG_TEXT[f] ?? f}
                    </Text>
                  ))}
                </Table.Th>
              ))}
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {requirements.map((req) => (
              <Table.Tr key={req.idx}>
                <Table.Td>
                  {req.priority && (
                    <Text
                      span
                      ff="monospace"
                      fz="xs"
                      fw={600}
                      tt="uppercase"
                      c={req.priority === "must" ? "cobalt" : "dimmed"}
                      mr={GAP_COMPACT}
                    >
                      {PRIORITY_LABELS[req.priority]}
                    </Text>
                  )}
                  <Text span size="sm">
                    {req.text}
                  </Text>
                  {gapSet.has(req.idx) && (
                    <Text size="xs" c="red" fw={600} data-testid={`matrix-gap-${req.idx}`}>
                      Catalog gap: no app covers this
                    </Text>
                  )}
                </Table.Td>
                {top.map((r) => {
                  const ev = r.evidence.find((e) => e.req_idx === req.idx);
                  if (!ev) return <Table.Td key={r.app.id} />;
                  const detail = evidenceText(ev);
                  return (
                    <Table.Td
                      key={r.app.id}
                      className="rb-cell"
                      style={
                        {
                          "--rb-cell-color": `var(--mantine-color-${STATUS_COLORS[ev.status]}-filled)`,
                        } as CSSProperties
                      }
                      data-testid={`cell-${req.idx}-${r.app.slug}`}
                      data-status={ev.status}
                    >
                      <Group gap={GAP_COMPACT} wrap="nowrap">
                        <StatusIcon status={ev.status} />
                        <Text size="sm" fw={600}>
                          {STATUS_WORD[ev.status]}
                        </Text>
                        {ev.via !== "none" && (
                          <Text size="xs" ff="monospace" c="dimmed" ml="auto" title="Similarity">
                            {pct(ev.similarity)}
                          </Text>
                        )}
                      </Group>
                      {detail && (
                        <Text
                          size="xs"
                          c="dimmed"
                          mt={GAP_TIGHT}
                          fs={ev.via === "summary" ? "italic" : undefined}
                        >
                          {detail}
                        </Text>
                      )}
                    </Table.Td>
                  );
                })}
              </Table.Tr>
            ))}
          </Table.Tbody>
          <Table.Tfoot>
            <Table.Tr>
              <Table.Th>{anyMust ? "Must-haves covered" : "Requirements covered"}</Table.Th>
              {top.map((r) => {
                const must = mustHaves(r, requirements);
                const counts = countStatuses(r.evidence);
                return (
                  <Table.Th key={r.app.id} data-testid={`matrix-total-${r.app.slug}`}>
                    {anyMust
                      ? `${must.covered} of ${must.total}`
                      : `${counts.covered} of ${r.evidence.length}`}
                  </Table.Th>
                );
              })}
            </Table.Tr>
          </Table.Tfoot>
        </Table>
      </Table.ScrollContainer>
    </Stack>
  );
}
