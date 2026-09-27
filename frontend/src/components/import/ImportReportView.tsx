import { Alert, Badge, Group, Paper, ScrollArea, SimpleGrid, Stack, Table, Text } from "@mantine/core";
import { IconAlertTriangle, IconInfoCircle } from "@tabler/icons-react";

import type { ImportReport } from "../../api/hooks";

const KIND_LABELS: Record<string, string> = { app: "App", system: "External system", interface: "Interface" };

const ACTION_COLORS: Record<string, string> = {
  created: "teal",
  updated: "indigo",
  unchanged: "gray",
  skipped: "yellow",
  invalid: "red",
};
const STAT_KEYS = ["created", "updated", "unchanged", "skipped", "invalid"] as const;
const TABLE_MAX_HEIGHT = 360;

export function ImportReportView({ report }: { report: ImportReport }) {
  return (
    <Stack data-testid="import-report">
      <SimpleGrid cols={{ base: 2, sm: STAT_KEYS.length }}>
        {STAT_KEYS.map((key) => (
          <Paper key={key} withBorder p="sm">
            <Text size="xs" c="dimmed" tt="uppercase" fw="bold">
              {key}
            </Text>
            <Text size="xl" fw="bold" c={report.stats[key] > 0 ? ACTION_COLORS[key] : undefined}>
              {report.stats[key]}
            </Text>
          </Paper>
        ))}
      </SimpleGrid>

      {report.errors.length > 0 && (
        <Alert color="red" icon={<IconAlertTriangle />} title={`${report.errors.length} error(s)`}>
          <Stack gap={0}>
            {report.errors.map((e, i) => (
              <Text key={i} size="sm">
                {KIND_LABELS[e.kind ?? "app"]} row {e.row}
                {e.slug ? ` (${e.slug})` : ""}
                {e.field ? `, ${e.field}` : ""}: {e.message}
              </Text>
            ))}
          </Stack>
        </Alert>
      )}
      {report.warnings.length > 0 && (
        <Alert color="yellow" icon={<IconInfoCircle />} title={`${report.warnings.length} warning(s)`}>
          <Stack gap={0}>
            {report.warnings.map((w, i) => (
              <Text key={i} size="sm">
                {w.row > 0 ? `Row ${w.row}: ` : ""}
                {w.message}
              </Text>
            ))}
          </Stack>
        </Alert>
      )}

      {report.items.length > 0 && (
        <ScrollArea.Autosize mah={TABLE_MAX_HEIGHT}>
          <Table striped>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Row</Table.Th>
                <Table.Th>Kind</Table.Th>
                <Table.Th>Item</Table.Th>
                <Table.Th>Action</Table.Th>
                <Table.Th>Changed fields</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {report.items.map((item) => (
                <Table.Tr key={`${item.kind}-${item.row}-${item.slug}`}>
                  <Table.Td>{item.row}</Table.Td>
                  <Table.Td>{KIND_LABELS[item.kind ?? "app"]}</Table.Td>
                  <Table.Td>{item.slug}</Table.Td>
                  <Table.Td>
                    <Badge color={ACTION_COLORS[item.action]} variant="light">
                      {item.action}
                    </Badge>
                  </Table.Td>
                  <Table.Td>
                    <Group gap="xs">
                      {item.changed_fields.map((f) => (
                        <Badge key={f} size="xs" variant="default">
                          {f}
                        </Badge>
                      ))}
                    </Group>
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </ScrollArea.Autosize>
      )}
    </Stack>
  );
}
