import { Avatar, Group, Paper, Stack, Text } from "@mantine/core";
import { Handle, Position, type Node, type NodeProps } from "@xyflow/react";

import type { LandscapeNode } from "../../api/hooks";
import {
  GAP_COMPACT,
  GRAPH_DIMMED_OPACITY,
  GRAPH_NODE_HEIGHT,
  GRAPH_NODE_WIDTH,
  LIFECYCLE_COLORS,
} from "../../config";
import { initials } from "../search/format";

export type GraphNodeData = LandscapeNode & { dimmed: boolean; focused: boolean; highlighted: boolean };
export type GraphNode = Node<GraphNodeData, "app" | "system">;

const HIDDEN_HANDLE = { opacity: 0, pointerEvents: "none" } as const;
const GRAPH_FOCUS_BORDER = 2;

function Frame({
  data,
  children,
  dashed,
}: {
  data: GraphNodeData;
  children: React.ReactNode;
  dashed?: boolean;
}) {
  const emphasis = data.focused || data.highlighted;
  return (
    <Paper
      w={GRAPH_NODE_WIDTH}
      h={GRAPH_NODE_HEIGHT}
      radius="md"
      px="xs"
      data-testid={`graph-node-${data.kind}`}
      data-dimmed={data.dimmed}
      style={{
        display: "flex",
        alignItems: "center",
        opacity: data.dimmed ? GRAPH_DIMMED_OPACITY : 1,
        border: `${emphasis ? GRAPH_FOCUS_BORDER : 1}px ${dashed ? "dashed" : "solid"} ${
          emphasis ? "var(--mantine-primary-color-filled)" : "var(--rb-tile-border)"
        }`,
        background: dashed ? "var(--rb-ground)" : undefined,
      }}
    >
      <Handle type="target" position={Position.Left} style={HIDDEN_HANDLE} />
      {children}
      <Handle type="source" position={Position.Right} style={HIDDEN_HANDLE} />
    </Paper>
  );
}

export function AppNode({ data }: NodeProps<GraphNode>) {
  const color = LIFECYCLE_COLORS[data.lifecycle_status ?? ""] ?? "gray";
  return (
    <Frame data={data}>
      <Group gap={GAP_COMPACT} wrap="nowrap" style={{ minWidth: 0 }}>
        <Avatar name={data.name} color="initials" variant="filled" radius="sm" size="sm" aria-hidden>
          {initials(data.name)}
        </Avatar>
        <Stack gap={0} style={{ minWidth: 0 }}>
          <Text size="sm" fw="bold" truncate="end" lh={1.2}>
            {data.name}
          </Text>
          <Text size="xs" c={color} truncate="end" lh={1.2}>
            {data.lifecycle_status}
            {data.domains[0] ? ` / ${data.domains[0]}` : ""}
          </Text>
        </Stack>
      </Group>
    </Frame>
  );
}

export function SystemNode({ data }: NodeProps<GraphNode>) {
  return (
    <Frame data={data} dashed>
      <Stack gap={0} style={{ minWidth: 0 }}>
        <Text size="sm" fw="bold" c="dimmed" truncate="end" lh={1.2}>
          {data.name}
        </Text>
        <Text size="xs" c="dimmed" lh={1.2}>
          external system
        </Text>
      </Stack>
    </Frame>
  );
}

export const NODE_TYPES = { app: AppNode, system: SystemNode };
