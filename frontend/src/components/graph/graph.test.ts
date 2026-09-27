import { describe, expect, it } from "vitest";

import type { AppOut, InterfaceSummary, Landscape } from "../../api/hooks";
import { endpointOptions, fromValue, toValue } from "../interfaces/endpoint";
import { toPayload } from "../interfaces/InterfaceForm";
import { evidenceText, interfaceText } from "../search/format";
import { dimmedState, findNode, neighbourhood, neighbourIds } from "./graphModel";
import { layoutPositions } from "./layout";

const node = (id: string, name: string, kind: "app" | "system" = "app") => ({
  id,
  kind,
  name,
  slug: kind === "app" ? name.toLowerCase() : null,
  lifecycle_status: kind === "app" ? ("active" as const) : null,
  domains: [],
  degree: 1,
});
const edge = (id: string, source: string, target: string) => ({
  id,
  source,
  target,
  name: id,
  type: "rest_api" as const,
  status: "active" as const,
  bidirectional: false,
  data_objects: [],
  frequency: null,
});

const landscape: Landscape = {
  nodes: [node("a", "Belegfix"), node("b", "FinanzBuch"), node("c", "Wiki"), node("s", "SAP", "system")],
  edges: [edge("ab", "a", "b"), edge("as", "a", "s"), edge("cs", "c", "s")],
};

describe("graph model", () => {
  it("finds the one-hop neighbourhood in both directions", () => {
    expect([...neighbourIds(landscape.edges, "a")].sort()).toEqual(["a", "b", "s"]);
    expect([...neighbourIds(landscape.edges, "b")].sort()).toEqual(["a", "b"]);
  });

  it("dims everything outside the focused node's neighbourhood", () => {
    const dimmed = dimmedState(landscape, "b");
    expect([...dimmed.nodes].sort()).toEqual(["c", "s"]);
    expect([...dimmed.edges].sort()).toEqual(["as", "cs"]);
    expect(dimmedState(landscape, null).nodes.size).toBe(0);
  });

  it("finds nodes by prefix first, then by substring", () => {
    expect(findNode(landscape.nodes, "fin")?.id).toBe("b");
    expect(findNode(landscape.nodes, "fix")?.id).toBe("a");
    expect(findNode(landscape.nodes, "  ")).toBeUndefined();
  });

  it("builds an app's neighbourhood with directions from its interfaces", () => {
    const summary = (
      id: string,
      direction: InterfaceSummary["direction"],
      name: string,
      kind: "app" | "system",
    ) => ({
      id,
      name: id,
      direction,
      counterpart: { kind, id: `${name}-id`, name, slug: kind === "app" ? name.toLowerCase() : null },
      type: "rest_api" as const,
      data_objects: [],
      frequency: null,
      status: "active" as const,
    });
    const app = {
      id: "a1",
      slug: "belegfix",
      name: "Belegfix",
      lifecycle_status: "active",
      domains: ["finance"],
      interfaces: [
        summary("out", "outgoing", "FinanzBuch", "app"),
        summary("in", "incoming", "SAP", "system"),
        summary("both", "both", "SAP", "system"),
      ],
    } as unknown as AppOut;
    const graph = neighbourhood(app);
    expect(graph.nodes.map((n) => n.id)).toEqual(["app:a1", "app:FinanzBuch-id", "system:SAP-id"]);
    expect(graph.nodes[2]!.degree).toBe(2);
    expect(graph.edges.map((e) => [e.id, e.source, e.target, e.bidirectional])).toEqual([
      ["out", "app:a1", "app:FinanzBuch-id", false],
      ["in", "system:SAP-id", "app:a1", false],
      ["both", "app:a1", "system:SAP-id", true],
    ]);
  });

  it("lays out providers left of consumers", async () => {
    const positions = await layoutPositions(landscape);
    expect(positions.size).toBe(4);
    expect(positions.get("a")!.x).toBeLessThan(positions.get("b")!.x);
  });
});

describe("interface endpoints", () => {
  it("round-trips select values", () => {
    expect(toValue({ app: "belegfix" })).toBe("app:belegfix");
    expect(toValue({ system: "SAP S/4HANA" })).toBe("system:SAP S/4HANA");
    expect(toValue({ kind: "system", id: "1", name: "DATEV" })).toBe("system:DATEV");
    expect(fromValue("system:SAP S/4HANA")).toEqual({ system: "SAP S/4HANA" });
    expect(fromValue("app:belegfix")).toEqual({ app: "belegfix" });
  });

  it("offers a new external system for an unknown name and keeps it once chosen", () => {
    const apps = [{ slug: "belegfix", name: "Belegfix" }];
    const systems = [{ name: "DATEV" }];
    const typed = endpointOptions(apps, systems, "Bank");
    expect(typed.at(-1)).toEqual({
      group: "New",
      items: [{ value: "system:Bank", label: "New external system: Bank" }],
    });
    expect(endpointOptions(apps, systems, "datev").map((g) => g.group)).toEqual(["Apps", "External systems"]);

    const chosen = endpointOptions(apps, systems, "New external system: Bank", "system:Bank");
    expect(chosen[1]!.items).toContainEqual({ value: "system:Bank", label: "Bank" });
    // An app outside the loaded list still shows, so editing never loses the value.
    expect(endpointOptions(apps, systems, "", "app:ledger")[0]!.items).toContainEqual({
      value: "app:ledger",
      label: "ledger",
    });
  });

  it("turns form values into the API payload", () => {
    expect(
      toPayload({
        from: "app:belegfix",
        to: "system:SAP",
        name: "  Export ",
        type: "rest_api",
        data_objects: ["invoices"],
        frequency: "",
        status: "planned",
        bidirectional: true,
        description: " x ",
      }),
    ).toEqual({
      from: { app: "belegfix" },
      to: { system: "SAP" },
      name: "Export",
      type: "rest_api",
      data_objects: ["invoices"],
      frequency: null,
      status: "planned",
      bidirectional: true,
      description: "x",
    });
  });
});

describe("interface evidence text", () => {
  const iface = { name: "Invoice posting", direction: "outgoing", counterpart: { name: "SAP S/4HANA" } };

  it("names the other side from the matched app's point of view", () => {
    expect(interfaceText(iface)).toBe("Interface to SAP S/4HANA: Invoice posting");
    expect(interfaceText({ ...iface, direction: "incoming" })).toBe(
      "Interface from SAP S/4HANA: Invoice posting",
    );
    expect(interfaceText({ ...iface, direction: "both" })).toBe(
      "Interface with SAP S/4HANA: Invoice posting",
    );
  });

  it("is used for matrix cells and the CSV export", () => {
    const ev = {
      req_idx: 0,
      status: "covered" as const,
      similarity: 0.8,
      via: "interface",
      interface: iface,
    };
    expect(evidenceText(ev)).toBe("Interface to SAP S/4HANA: Invoice posting");
  });
});
