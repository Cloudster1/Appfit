import { ThemeIcon, Tooltip } from "@mantine/core";
import { IconCheck, IconMinus, IconX } from "@tabler/icons-react";

import { ICON_SIZE, STATUS_COLORS } from "../../config";
import { STATUS_TEXT as LABELS, type ReqStatus } from "./format";

const ICONS = { covered: IconCheck, partial: IconMinus, gap: IconX };

export function StatusIcon({ status, size = "sm" }: { status: ReqStatus; size?: "sm" | "md" }) {
  const Icon = ICONS[status];
  return (
    <Tooltip label={LABELS[status]}>
      <ThemeIcon
        color={STATUS_COLORS[status]}
        variant="light"
        size={size}
        radius="xl"
        aria-label={LABELS[status]}
      >
        <Icon size={size === "sm" ? ICON_SIZE.xs : ICON_SIZE.sm} />
      </ThemeIcon>
    </Tooltip>
  );
}
