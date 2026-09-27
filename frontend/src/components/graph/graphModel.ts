import type { AppOut, Landscape, LandscapeEdge, LandscapeNode } from "../../api/hooks";
import { MINI_GRAPH_HEIGHT, SMALL_GRAPH_HEIGHT, SMALL_GRAPH_MAX_NODES } from "../../config";

export type Position = { x: number; y: number };

/** Node ids reached from a node by one edge, the node itself included. */
export function neighbourIds(edges: LandscapeEdge[], nodeId: string): Set<string> {
  const ids = new Set([nodeId]);
  for (const e of edges) {
    if (e.source === nodeId) ids.add(e.target);
    if (e.target === nodeId) ids.add(e.source);
  }
  return ids;
}

/** In focus mode everything outside the focused node's neighbourhood is dimmed. */
export function dimmedState(landscape: Landscape, focusId: string | null) {
  if (!focusId) return { nodes: new Set<string>(), edges: new Set<string>() };
  const keep = neighbourIds(landscape.edges, focusId);
  return {
    nodes: new Set(landscape.nodes.filter((n) => !keep.has(n.id)).map((n) => n.id)),
    edges: new Set(
      landscape.edges.filter((e) => e.source !== focusId && e.target !== focusId).map((e) => e.id),
    ),
  };
}

/** Case-insensitive name search; the best match starts with the query. */
export function findNode(nodes: LandscapeNode[], query: string): LandscapeNode | undefined {
  const q = query.trim().toLowerCase();
  if (!q) return undefined;
  return (
    nodes.find((n) => n.name.toLowerCase().startsWith(q)) ??
    nodes.find((n) => n.name.toLowerCase().includes(q))
  );
}

export function appNodeId(id: string): string {
  return `app:${id}`;
}

/** The one-hop neighbourhood of an app, built from its detail data (no extra request). */
export function neighbourhood(app: AppOut): Landscape {
  const centre = appNodeId(app.id);
  const nodes = new Map<string, LandscapeNode>([
    [
      centre,
      {
        id: centre,
        kind: "app",
        name: app.name,
        slug: app.slug,
        lifecycle_status: app.lifecycle_status,
        domains: app.domains,
        degree: app.interfaces.length,
      },
    ],
  ]);
  const edges: LandscapeEdge[] = [];
  for (const i of app.interfaces) {
    const other = `${i.counterpart.kind}:${i.counterpart.id}`;
    if (!nodes.has(other)) {
      nodes.set(other, {
        id: other,
        kind: i.counterpart.kind,
        name: i.counterpart.name,
        slug: i.counterpart.slug ?? null,
        lifecycle_status: i.counterpart.lifecycle_status ?? null,
        domains: [],
        degree: 0,
      });
    }
    nodes.get(other)!.degree += 1;
    const outgoing = i.direction !== "incoming";
    edges.push({
      id: i.id,
      source: outgoing ? centre : other,
      target: outgoing ? other : centre,
      name: i.name,
      type: i.type,
      status: i.status,
      bidirectional: i.direction === "both",
      data_objects: i.data_objects,
      frequency: i.frequency,
    });
  }
  return { nodes: [...nodes.values()], edges };
}

/** Embedded graphs with only a few nodes get a shorter box instead of a huge zoom. */
export function miniGraphHeight(landscape: Landscape): number {
  return landscape.nodes.length <= SMALL_GRAPH_MAX_NODES ? SMALL_GRAPH_HEIGHT : MINI_GRAPH_HEIGHT;
}
