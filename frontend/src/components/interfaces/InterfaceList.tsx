import { ActionIcon, Anchor, Badge, Group, Stack, Text, Tooltip } from "@mantine/core";
import { IconArrowLeft, IconArrowRight, IconArrowsLeftRight, IconEdit, IconTrash } from "@tabler/icons-react";
import { Link } from "react-router";

import type { EndpointOut, InterfaceSummary } from "../../api/hooks";
import {
  GAP_COMPACT,
  ICON_SIZE,
  INTERFACE_FREQUENCY_LABELS,
  INTERFACE_STATUS_LABELS,
  INTERFACE_TYPE_COLORS,
  INTERFACE_TYPE_LABELS,
} from "../../config";

const DIRECTION = {
  outgoing: { icon: IconArrowRight, label: "Sends data to" },
  incoming: { icon: IconArrowLeft, label: "Receives data from" },
  both: { icon: IconArrowsLeftRight, label: "Exchanges data with" },
} as const;
// Aligns the direction icon with the first text line.
const ICON_BASELINE_NUDGE = 2;
const STATUS_COLORS: Record<string, string> = { planned: "yellow", active: "green", deprecated: "gray" };

export function EndpointName({ endpoint }: { endpoint: EndpointOut }) {
  if (endpoint.kind === "app" && endpoint.slug) {
    return (
      <Anchor component={Link} to={`/apps/${endpoint.slug}`} size="sm" fw="bold">
        {endpoint.name}
      </Anchor>
    );
  }
  return (
    <Text span size="sm" fw="bold">
      {endpoint.name}{" "}
      <Text span size="xs" c="dimmed">
        (external)
      </Text>
    </Text>
  );
}

export function InterfaceBadges({ type, status }: { type: string; status: string }) {
  return (
    <>
      <Badge size="xs" variant="light" color={INTERFACE_TYPE_COLORS[type] ?? "gray"}>
        {INTERFACE_TYPE_LABELS[type] ?? type}
      </Badge>
      {status !== "active" && (
        <Badge size="xs" variant="outline" color={STATUS_COLORS[status] ?? "gray"}>
          {INTERFACE_STATUS_LABELS[status] ?? status}
        </Badge>
      )}
    </>
  );
}

type Props = {
  interfaces: InterfaceSummary[];
  onEdit?: (id: string) => void;
  onDelete?: (item: InterfaceSummary) => void;
};

/** An app's interfaces from its own point of view: direction, counterpart, type and data. */
export function InterfaceList({ interfaces, onEdit, onDelete }: Props) {
  if (interfaces.length === 0) {
    return (
      <Text size="sm" c="dimmed">
        No interfaces documented yet.
      </Text>
    );
  }
  return (
    <Stack gap="sm">
      {interfaces.map((i) => {
        const dir = DIRECTION[i.direction];
        return (
          <Group
            key={i.id}
            justify="space-between"
            wrap="nowrap"
            align="flex-start"
            data-testid="interface-row"
          >
            <Group gap={GAP_COMPACT} wrap="nowrap" align="flex-start" style={{ minWidth: 0 }}>
              <Tooltip label={dir.label}>
                <dir.icon
                  size={ICON_SIZE.sm}
                  aria-label={dir.label}
                  style={{ flexShrink: 0, marginTop: ICON_BASELINE_NUDGE }}
                />
              </Tooltip>
              <Stack gap={0} style={{ minWidth: 0 }}>
                <Group gap={GAP_COMPACT}>
                  <EndpointName endpoint={i.counterpart} />
                  <InterfaceBadges type={i.type} status={i.status} />
                </Group>
                <Text size="sm">{i.name}</Text>
                {(i.data_objects.length > 0 || i.frequency) && (
                  <Text size="xs" c="dimmed">
                    {[i.data_objects.join(", "), i.frequency ? INTERFACE_FREQUENCY_LABELS[i.frequency] : null]
                      .filter(Boolean)
                      .join(" / ")}
                  </Text>
                )}
              </Stack>
            </Group>
            {(onEdit || onDelete) && (
              <Group gap={0} wrap="nowrap">
                {onEdit && (
                  <ActionIcon variant="subtle" aria-label={`Edit ${i.name}`} onClick={() => onEdit(i.id)}>
                    <IconEdit size={ICON_SIZE.sm} />
                  </ActionIcon>
                )}
                {onDelete && (
                  <ActionIcon
                    variant="subtle"
                    color="red"
                    aria-label={`Delete ${i.name}`}
                    onClick={() => onDelete(i)}
                  >
                    <IconTrash size={ICON_SIZE.sm} />
                  </ActionIcon>
                )}
              </Group>
            )}
          </Group>
        );
      })}
    </Stack>
  );
}
