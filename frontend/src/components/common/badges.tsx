import { Badge, Tooltip } from "@mantine/core";
import { IconCircleCheck, IconClockHour4 } from "@tabler/icons-react";

import { ICON_SIZE, LIFECYCLE_COLORS } from "../../config";

export function LifecycleBadge({ status }: { status: string }) {
  return (
    <Badge color={LIFECYCLE_COLORS[status] ?? "gray"} variant="light">
      {status}
    </Badge>
  );
}

export function EmbeddingStatusBadge({ status }: { status: "indexed" | "pending" }) {
  if (status === "indexed") {
    return (
      <Tooltip label="All texts are embedded with the active model and fully searchable">
        <Badge color="teal" variant="light" leftSection={<IconCircleCheck size={ICON_SIZE.xs} />}>
          indexed
        </Badge>
      </Tooltip>
    );
  }
  return (
    <Tooltip label="Embedding in progress; keyword search already works">
      <Badge color="orange" variant="light" leftSection={<IconClockHour4 size={ICON_SIZE.xs} />}>
        indexing
      </Badge>
    </Tooltip>
  );
}
