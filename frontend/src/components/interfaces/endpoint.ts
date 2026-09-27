import type { EndpointOut, InterfaceIn } from "../../api/hooks";

export type EndpointRef = InterfaceIn["from"];

const APP = "app:";
const SYSTEM = "system:";

/** Select values: "app:<slug>" or "system:<name>". */
export function toValue(ref: EndpointRef | EndpointOut | null | undefined): string | null {
  if (!ref) return null;
  if ("kind" in ref) return ref.kind === "app" ? `${APP}${ref.slug}` : `${SYSTEM}${ref.name}`;
  if (ref.app) return `${APP}${ref.app}`;
  return ref.system ? `${SYSTEM}${ref.system}` : null;
}

export function fromValue(value: string): EndpointRef {
  return value.startsWith(SYSTEM) ? { system: value.slice(SYSTEM.length) } : { app: value.slice(APP.length) };
}

type Option = { value: string; label: string };
type Group = { group: string; items: Option[] };

/** Apps and external systems in one list; an unknown search term can become a new external system.

 The selected value always stays in the list (a newly typed system, or an app beyond the loaded page),
 so the select can show it. */
export function endpointOptions(
  apps: { slug: string; name: string }[],
  systems: { name: string }[],
  search: string,
  selected: string | null = null,
): Group[] {
  const systemItems = systems.map((s) => ({ value: `${SYSTEM}${s.name}`, label: s.name }));
  if (selected?.startsWith(SYSTEM) && !systemItems.some((i) => i.value === selected)) {
    systemItems.push({ value: selected, label: selected.slice(SYSTEM.length) });
  }
  const appItems = apps.map((a) => ({ value: `${APP}${a.slug}`, label: a.name }));
  if (selected?.startsWith(APP) && !appItems.some((i) => i.value === selected)) {
    appItems.push({ value: selected, label: selected.slice(APP.length) });
  }
  const groups: Group[] = [
    { group: "Apps", items: appItems },
    { group: "External systems", items: systemItems },
  ];
  const term = search.trim();
  const known = [...groups[0]!.items, ...systemItems].map((i) => i.label.toLowerCase());
  if (term && !known.includes(term.toLowerCase())) {
    groups.push({
      group: "New",
      items: [{ value: `${SYSTEM}${term}`, label: `New external system: ${term}` }],
    });
  }
  return groups.filter((g) => g.items.length > 0);
}
