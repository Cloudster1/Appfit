import "@xyflow/react/dist/style.css";

import { Box, Center, Loader, useComputedColorScheme } from "@mantine/core";
import {
  Background,
  Controls,
  MarkerType,
  ReactFlow,
  ReactFlowProvider,
  useReactFlow,
  type EdgeMouseHandler,
  type NodeMouseHandler,
} from "@xyflow/react";
import { useEffect, useMemo, useState } from "react";

import type { Landscape } from "../../api/hooks";
import {
  FIT_VIEW_PADDING,
  GRAPH_FIT_DELAY_MS,
  GRAPH_FIT_MAX_ZOOM,
  GRAPH_FOCUS_DURATION_MS,
  GRAPH_MIN_ZOOM,
} from "../../config";
import { dimmedState, neighbourIds, type Position } from "./graphModel";
import { EDGE_TYPES, edgeColor, type GraphEdge } from "./InterfaceEdge";
import { layoutPositions } from "./layout";
import { NODE_TYPES, type GraphNode } from "./nodes";

type Props = {
  landscape: Landscape;
  height: number | string;
  focusId?: string | null;
  highlightId?: string | null;
  onNodeClick?: (nodeId: string) => void;
  onEdgeClick?: (edgeId: string) => void;
  onPaneClick?: () => void;
  // Small embedded graphs should not capture page scrolling.
  compact?: boolean;
};

function toElements(
  landscape: Landscape,
  positions: Map<string, Position>,
  focusId: string | null,
  highlightId: string | null,
): { nodes: GraphNode[]; edges: GraphEdge[] } {
  const dimmed = dimmedState(landscape, focusId);
  const nodes: GraphNode[] = landscape.nodes.map((n) => ({
    id: n.id,
    type: n.kind,
    position: positions.get(n.id) ?? { x: 0, y: 0 },
    data: {
      ...n,
      dimmed: dimmed.nodes.has(n.id),
      focused: n.id === focusId,
      highlighted: n.id === highlightId,
    },
  }));
  const edges: GraphEdge[] = landscape.edges.map((e) => {
    const marker = { type: MarkerType.ArrowClosed, color: edgeColor(e.type) };
    return {
      id: e.id,
      source: e.source,
      target: e.target,
      type: "interface",
      markerEnd: marker,
      markerStart: e.bidirectional ? { ...marker, orient: "auto-start-reverse" } : undefined,
      data: {
        ...e,
        dimmed: dimmed.edges.has(e.id),
        showLabel: Boolean(focusId) && !dimmed.edges.has(e.id),
      },
    };
  });
  return { nodes, edges };
}

function Graph({ landscape, height, focusId = null, highlightId = null, compact, ...handlers }: Props) {
  const colorScheme = useComputedColorScheme("light");
  const [positions, setPositions] = useState<Map<string, Position> | null>(null);
  const { fitView } = useReactFlow();

  useEffect(() => {
    let cancelled = false;
    void layoutPositions(landscape).then((p) => {
      if (!cancelled) setPositions(p);
    });
    return () => {
      cancelled = true;
    };
  }, [landscape]);

  // Fit everything, or zoom to the focused node and its neighbours.
  useEffect(() => {
    if (!positions) return;
    const nodes = focusId ? [...neighbourIds(landscape.edges, focusId)].map((id) => ({ id })) : undefined;
    const timer = setTimeout(
      () =>
        void fitView({
          nodes,
          padding: FIT_VIEW_PADDING,
          maxZoom: GRAPH_FIT_MAX_ZOOM,
          duration: focusId ? GRAPH_FOCUS_DURATION_MS : 0,
        }),
      GRAPH_FIT_DELAY_MS,
    );
    return () => clearTimeout(timer);
  }, [positions, focusId, landscape.edges, fitView]);

  const elements = useMemo(
    () => (positions ? toElements(landscape, positions, focusId, highlightId) : null),
    [landscape, positions, focusId, highlightId],
  );

  const onNodeClick: NodeMouseHandler = (_, node) => handlers.onNodeClick?.(node.id);
  const onEdgeClick: EdgeMouseHandler = (_, edge) => handlers.onEdgeClick?.(edge.id);

  return (
    <Box
      h={height}
      data-testid="landscape-graph"
      style={{ borderRadius: "var(--mantine-radius-lg)", overflow: "hidden" }}
    >
      {elements ? (
        <ReactFlow
          nodes={elements.nodes}
          edges={elements.edges}
          nodeTypes={NODE_TYPES}
          edgeTypes={EDGE_TYPES}
          colorMode={colorScheme}
          onNodeClick={onNodeClick}
          onEdgeClick={onEdgeClick}
          onPaneClick={handlers.onPaneClick}
          nodesDraggable
          nodesConnectable={false}
          zoomOnScroll={!compact}
          preventScrolling={!compact}
          fitView
          fitViewOptions={{ padding: FIT_VIEW_PADDING, maxZoom: GRAPH_FIT_MAX_ZOOM }}
          minZoom={GRAPH_MIN_ZOOM}
          proOptions={{ hideAttribution: true }}
        >
          <Background />
          <Controls showInteractive={false} />
        </ReactFlow>
      ) : (
        <Center h="100%">
          <Loader />
        </Center>
      )}
    </Box>
  );
}

/** Interfaces as a directed graph with an automatic left-to-right layout. */
export function LandscapeGraph(props: Props) {
  return (
    <ReactFlowProvider>
      <Graph {...props} />
    </ReactFlowProvider>
  );
}
