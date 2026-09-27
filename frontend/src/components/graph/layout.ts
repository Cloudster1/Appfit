import type { ELK } from "elkjs/lib/elk-api";

import type { Landscape } from "../../api/hooks";
import { GRAPH_LAYER_SPACING, GRAPH_NODE_HEIGHT, GRAPH_NODE_SPACING, GRAPH_NODE_WIDTH } from "../../config";
import type { Position } from "./graphModel";

let elkPromise: Promise<ELK> | null = null;

/** ELK runs in a web worker in the browser; tests (no Worker) use the bundled main-thread build. */
function getElk(): Promise<ELK> {
  elkPromise ??=
    typeof Worker === "undefined"
      ? import("elkjs/lib/elk.bundled.js").then((m) => new m.default())
      : Promise.all([import("elkjs/lib/elk-api"), import("elkjs/lib/elk-worker.min.js?url")]).then(
          ([api, worker]) => new api.default({ workerUrl: worker.default }),
        );
  return elkPromise;
}

/** Layered left-to-right layout: data flows from providers on the left to consumers on the right. */
export async function layoutPositions(landscape: Landscape): Promise<Map<string, Position>> {
  const elk = await getElk();
  const result = await elk.layout({
    id: "root",
    layoutOptions: {
      "elk.algorithm": "layered",
      "elk.direction": "RIGHT",
      "elk.layered.spacing.nodeNodeBetweenLayers": String(GRAPH_LAYER_SPACING),
      "elk.spacing.nodeNode": String(GRAPH_NODE_SPACING),
      "elk.layered.nodePlacement.strategy": "BRANDES_KOEPF",
      "elk.separateConnectedComponents": "true",
    },
    children: landscape.nodes.map((n) => ({ id: n.id, width: GRAPH_NODE_WIDTH, height: GRAPH_NODE_HEIGHT })),
    edges: landscape.edges.map((e) => ({ id: e.id, sources: [e.source], targets: [e.target] })),
  });
  return new Map((result.children ?? []).map((c) => [c.id, { x: c.x ?? 0, y: c.y ?? 0 }]));
}
