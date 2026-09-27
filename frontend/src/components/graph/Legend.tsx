import { Box, Group, Text } from "@mantine/core";

import { GAP_COMPACT, INTERFACE_TYPE_LABELS } from "../../config";
import { edgeColor } from "./InterfaceEdge";

const SWATCH_WIDTH = 18;
const SWATCH_HEIGHT = 3;

function Swatch({ color, dashed }: { color: string; dashed?: boolean }) {
  return (
    <Box
      w={SWATCH_WIDTH}
      h={SWATCH_HEIGHT}
      style={{ borderTop: `${SWATCH_HEIGHT}px ${dashed ? "dashed" : "solid"} ${color}` }}
      aria-hidden
    />
  );
}

/** Colours per interface type, plus how planned interfaces and external systems look. */
export function Legend({ types }: { types: string[] }) {
  return (
    <Group gap="md" data-testid="graph-legend">
      {types.map((t) => (
        <Group key={t} gap={GAP_COMPACT} wrap="nowrap">
          <Swatch color={edgeColor(t)} />
          <Text size="xs">{INTERFACE_TYPE_LABELS[t] ?? t}</Text>
        </Group>
      ))}
      <Group gap={GAP_COMPACT} wrap="nowrap">
        <Swatch color="var(--mantine-color-dimmed)" dashed />
        <Text size="xs">planned</Text>
      </Group>
      <Group gap={GAP_COMPACT} wrap="nowrap">
        <Box
          w={SWATCH_WIDTH}
          h={SWATCH_WIDTH / 2}
          style={{ border: "1px dashed var(--mantine-color-dimmed)" }}
        />
        <Text size="xs">external system</Text>
      </Group>
    </Group>
  );
}
