import { BaseEdge, EdgeLabelRenderer, getBezierPath, type Edge, type EdgeProps } from "@xyflow/react";

import type { LandscapeEdge } from "../../api/hooks";
import {
  GRAPH_DEPRECATED_OPACITY,
  GRAPH_DIMMED_OPACITY,
  GRAPH_EDGE_WIDTH,
  INTERFACE_TYPE_COLORS,
  INTERFACE_TYPE_LABELS,
} from "../../config";

export type GraphEdgeData = LandscapeEdge & { dimmed: boolean; showLabel: boolean };
export type GraphEdge = Edge<GraphEdgeData, "interface">;

const PLANNED_DASH = "6 4";

export function edgeColor(type: string): string {
  return `var(--mantine-color-${INTERFACE_TYPE_COLORS[type] ?? "gray"}-6)`;
}

export function InterfaceEdge(props: EdgeProps<GraphEdge>) {
  const { id, data, selected, markerEnd, markerStart } = props;
  const [path, labelX, labelY] = getBezierPath(props);
  if (!data) return null;
  const opacity = data.dimmed
    ? GRAPH_DIMMED_OPACITY
    : data.status === "deprecated"
      ? GRAPH_DEPRECATED_OPACITY
      : 1;
  const summary = `${data.name} (${INTERFACE_TYPE_LABELS[data.type] ?? data.type}, ${data.status})${
    data.data_objects.length ? `: ${data.data_objects.join(", ")}` : ""
  }`;
  return (
    <g data-testid="graph-edge" data-status={data.status} data-dimmed={data.dimmed}>
      <title>{summary}</title>
      <BaseEdge
        id={id}
        path={path}
        markerEnd={markerEnd}
        markerStart={markerStart}
        style={{
          stroke: edgeColor(data.type),
          strokeWidth: selected ? GRAPH_EDGE_WIDTH * 2 : GRAPH_EDGE_WIDTH,
          strokeDasharray: data.status === "planned" ? PLANNED_DASH : undefined,
          opacity,
        }}
      />
      {(data.showLabel || selected) && (
        <EdgeLabelRenderer>
          <div
            className="nodrag nopan rb-edge-label"
            style={{ transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)` }}
          >
            {data.name}
          </div>
        </EdgeLabelRenderer>
      )}
    </g>
  );
}

export const EDGE_TYPES = { interface: InterfaceEdge };
