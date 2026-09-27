import { Anchor, Button, Checkbox, Group, Stack, Text } from "@mantine/core";
import { useState } from "react";

import type { AppFacets } from "../../api/hooks";
import { FACET_VISIBLE_VALUES, GAP_COMPACT } from "../../config";

export type FacetSelection = { lifecycle: string[]; domains: string[]; licenseTypes: string[] };

type FacetValue = { value: string; count: number };

type Props = {
  facets: AppFacets | undefined;
  selected: FacetSelection;
  onChange: (next: FacetSelection) => void;
};

const LICENSE_LABELS: Record<string, string> = {
  oss: "Open source",
  commercial: "Commercial",
  internal: "In-house",
  other: "Other",
};

function toggle(list: string[], value: string): string[] {
  return list.includes(value) ? list.filter((v) => v !== value) : [...list, value];
}

/** Selected values stay listed even when the other filters leave them with no apps. */
function withSelected(values: FacetValue[], selected: string[]): FacetValue[] {
  const missing = selected.filter((s) => !values.some((v) => v.value === s));
  return [...values, ...missing.map((value) => ({ value, count: 0 }))];
}

type GroupProps = {
  title: string;
  values: FacetValue[];
  selected: string[];
  onToggle: (value: string) => void;
  labels?: Record<string, string>;
  note?: string;
};

function FacetGroup({ title, values, selected, onToggle, labels, note }: GroupProps) {
  const [showAll, setShowAll] = useState(false);
  const all = withSelected(values, selected);
  const visible = showAll ? all : all.slice(0, FACET_VISIBLE_VALUES);
  if (all.length === 0) return null;
  return (
    <Stack gap={GAP_COMPACT} role="group" aria-label={title}>
      <Text size="xs" fw="bold" tt="uppercase" c="dimmed" className="rb-eyebrow">
        {title}
      </Text>
      {visible.map((v) => (
        <Checkbox
          key={v.value}
          size="xs"
          checked={selected.includes(v.value)}
          onChange={() => onToggle(v.value)}
          styles={{ body: { width: "100%" }, labelWrapper: { flex: 1 } }}
          label={
            <Group justify="space-between" wrap="nowrap" gap="xs">
              <Text size="sm" truncate="end">
                {labels?.[v.value] ?? v.value}
              </Text>
              <Text size="xs" c="dimmed" ff="monospace">
                {v.count}
              </Text>
            </Group>
          }
        />
      ))}
      {all.length > FACET_VISIBLE_VALUES && (
        <Anchor component="button" type="button" size="xs" onClick={() => setShowAll(!showAll)}>
          {showAll ? "Show fewer" : `Show all ${all.length}`}
        </Anchor>
      )}
      {note && (
        <Text size="xs" c="dimmed">
          {note}
        </Text>
      )}
    </Stack>
  );
}

/** Lifecycle, domain and license filters with app counts. */
export function FacetPanel({ facets, selected, onChange }: Props) {
  const active = selected.lifecycle.length + selected.domains.length + selected.licenseTypes.length;
  return (
    <Stack gap="lg" data-testid="facet-panel">
      <FacetGroup
        title="Lifecycle"
        values={facets?.lifecycle ?? []}
        selected={selected.lifecycle}
        onToggle={(v) => onChange({ ...selected, lifecycle: toggle(selected.lifecycle, v) })}
        note="Retired apps are hidden unless selected."
      />
      <FacetGroup
        title="Domain"
        values={facets?.domain ?? []}
        selected={selected.domains}
        onToggle={(v) => onChange({ ...selected, domains: toggle(selected.domains, v) })}
      />
      <FacetGroup
        title="License"
        values={facets?.license_type ?? []}
        selected={selected.licenseTypes}
        onToggle={(v) => onChange({ ...selected, licenseTypes: toggle(selected.licenseTypes, v) })}
        labels={LICENSE_LABELS}
      />
      {active > 0 && (
        <Button
          variant="subtle"
          size="xs"
          onClick={() => onChange({ lifecycle: [], domains: [], licenseTypes: [] })}
        >
          Clear filters
        </Button>
      )}
    </Stack>
  );
}
